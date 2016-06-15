from __future__ import absolute_import
from typing import cast, Any, Callable, Generator, Iterable, Tuple, Sized, Union, Optional

from django.test import TestCase
from django.template import loader
from django.http import HttpResponse

from zerver.lib.initial_password import initial_password
from zerver.lib.db import TimeTrackingCursor
from zerver.lib.handlers import allocate_handler_id
from zerver.lib.str_utils import force_text
from zerver.lib import cache
from zerver.lib import event_queue
from zerver.worker import queue_processors

from zerver.lib.actions import (
    check_send_message, create_stream_if_needed, do_add_subscription,
    get_display_recipient,
)

from zerver.models import (
    get_realm,
    get_stream,
    get_user_profile_by_email,
    resolve_email_to_domain,
    Client,
    Message,
    Realm,
    Recipient,
    Stream,
    Subscription,
    UserMessage,
    UserProfile,
)

import base64
import os
import re
import time
import ujson
from six.moves import urllib
from six import text_type

from contextlib import contextmanager
import six

API_KEYS = {} # type: Dict[str, str]

@contextmanager
def stub(obj, name, f):
    # type: (Any, str, Callable[..., Any]) -> Generator[None, None, None]
    old_f = getattr(obj, name)
    setattr(obj, name, f)
    yield
    setattr(obj, name, old_f)

@contextmanager
def simulated_queue_client(client):
    # type: (Any) -> Generator[None, None, None]
    real_SimpleQueueClient = queue_processors.SimpleQueueClient
    queue_processors.SimpleQueueClient = client # type: ignore # https://github.com/JukkaL/mypy/issues/1152
    yield
    queue_processors.SimpleQueueClient = real_SimpleQueueClient # type: ignore # https://github.com/JukkaL/mypy/issues/1152

@contextmanager
def tornado_redirected_to_list(lst):
    # type: (List) -> Generator[None, None, None]
    real_event_queue_process_notification = event_queue.process_notification
    event_queue.process_notification = lst.append
    yield
    event_queue.process_notification = real_event_queue_process_notification

@contextmanager
def simulated_empty_cache():
    # type: () -> Generator[List[Tuple[str, Union[text_type, List[text_type]], text_type]], None, None]
    cache_queries = [] # type: List[Tuple[str, Union[text_type, List[text_type]], text_type]]
    def my_cache_get(key, cache_name=None):
        # type: (text_type, Optional[str]) -> Any
        cache_queries.append(('get', key, cache_name))
        return None

    def my_cache_get_many(keys, cache_name=None):
        # type: (List[text_type], Optional[str]) -> Dict[text_type, Any]
        cache_queries.append(('getmany', keys, cache_name))
        return None

    old_get = cache.cache_get
    old_get_many = cache.cache_get_many
    cache.cache_get = my_cache_get
    cache.cache_get_many = my_cache_get_many
    yield cache_queries
    cache.cache_get = old_get
    cache.cache_get_many = old_get_many

@contextmanager
def queries_captured():
    # type: () -> Generator[List[Dict[str, str]], None, None]
    '''
    Allow a user to capture just the queries executed during
    the with statement.
    '''

    queries = []

    def wrapper_execute(self, action, sql, params=()):
        # type: (TimeTrackingCursor, Callable, str, Iterable[Any]) -> None
        start = time.time()
        try:
            return action(sql, params)
        finally:
            stop = time.time()
            duration = stop - start
            queries.append({
                'sql': self.mogrify(sql, params),
                'time': "%.3f" % duration,
            })

    old_execute = TimeTrackingCursor.execute
    old_executemany = TimeTrackingCursor.executemany

    def cursor_execute(self, sql, params=()):
        # type: (TimeTrackingCursor, str, Iterable[Any]) -> None
        return wrapper_execute(self, super(TimeTrackingCursor, self).execute, sql, params) # type: ignore # https://github.com/JukkaL/mypy/issues/1167
    TimeTrackingCursor.execute = cursor_execute # type: ignore # https://github.com/JukkaL/mypy/issues/1167

    def cursor_executemany(self, sql, params=()):
        # type: (TimeTrackingCursor, str, Iterable[Any]) -> None
        return wrapper_execute(self, super(TimeTrackingCursor, self).executemany, sql, params) # type: ignore # https://github.com/JukkaL/mypy/issues/1167
    TimeTrackingCursor.executemany = cursor_executemany # type: ignore # https://github.com/JukkaL/mypy/issues/1167

    yield queries

    TimeTrackingCursor.execute = old_execute # type: ignore # https://github.com/JukkaL/mypy/issues/1167
    TimeTrackingCursor.executemany = old_executemany # type: ignore # https://github.com/JukkaL/mypy/issues/1167


def find_key_by_email(address):
    # type: (text_type) -> text_type
    from django.core.mail import outbox
    key_regex = re.compile("accounts/do_confirm/([a-f0-9]{40})>")
    for message in reversed(outbox):
        if address in message.to:
            return key_regex.search(message.body).groups()[0]

def message_ids(result):
    # type: (Dict[str, Any]) -> Set[int]
    return set(message['id'] for message in result['messages'])

def message_stream_count(user_profile):
    # type: (UserProfile) -> int
    return UserMessage.objects. \
        select_related("message"). \
        filter(user_profile=user_profile). \
        count()

def most_recent_usermessage(user_profile):
    # type: (UserProfile) -> UserMessage
    query = UserMessage.objects. \
        select_related("message"). \
        filter(user_profile=user_profile). \
        order_by('-message')
    return query[0] # Django does LIMIT here

def most_recent_message(user_profile):
    # type: (UserProfile) -> Message
    usermessage = most_recent_usermessage(user_profile)
    return usermessage.message

def get_user_messages(user_profile):
    # type: (UserProfile) -> List[Message]
    query = UserMessage.objects. \
        select_related("message"). \
        filter(user_profile=user_profile). \
        order_by('message')
    return [um.message for um in query]

class DummyObject(object):
    pass

class DummyTornadoRequest(object):
    def __init__(self):
        # type: () -> None
        self.connection = DummyObject()
        self.connection.stream = DummyStream() # type: ignore # monkey-patching here

class DummyHandler(object):
    def __init__(self, assert_callback):
        # type: (Any) -> None
        self.assert_callback = assert_callback
        self.request = DummyTornadoRequest()
        allocate_handler_id(self)

    # Mocks RequestHandler.async_callback, which wraps a callback to
    # handle exceptions.  We return the callback as-is.
    def async_callback(self, cb):
        # type: (Callable) -> Callable
        return cb

    def write(self, response):
        # type: (str) -> None
        raise NotImplemented

    def zulip_finish(self, response, *ignore):
        # type: (HttpResponse, *Any) -> None
        if self.assert_callback:
            self.assert_callback(response)


class DummySession(object):
    session_key = "0"

class DummyStream(object):
    def closed(self):
        # type: () -> bool
        return False

class POSTRequestMock(object):
    method = "POST"

    def __init__(self, post_data, user_profile, assert_callback=None):
        # type: (Dict[str, Any], UserProfile, Optional[Callable]) -> None
        self.REQUEST = self.POST = post_data
        self.user = user_profile
        self._tornado_handler = DummyHandler(assert_callback)
        self.session = DummySession()
        self._log_data = {} # type: Dict[str, Any]
        self.META = {'PATH_INFO': 'test'}

class AuthedTestCase(TestCase):
    # Helper because self.client.patch annoying requires you to urlencode

    def client_patch(self, url, info={}, **kwargs):
        # type: (str, Dict[str, Any], **Any) -> HttpResponse
        encoded = urllib.parse.urlencode(info)
        return self.client.patch(url, encoded, **kwargs)

    def client_put(self, url, info={}, **kwargs):
        # type: (str, Dict[str, Any], **Any) -> HttpResponse
        encoded = urllib.parse.urlencode(info)
        return self.client.put(url, encoded, **kwargs)

    def client_delete(self, url, info={}, **kwargs):
        # type: (str, Dict[str, Any], **Any) -> HttpResponse
        encoded = urllib.parse.urlencode(info)
        return self.client.delete(url, encoded, **kwargs)

    def login(self, email, password=None):
        # type: (text_type, Optional[text_type]) -> HttpResponse
        if password is None:
            password = initial_password(email)
        return self.client.post('/accounts/login/',
                                {'username': email, 'password': password})

    def register(self, username, password, domain="zulip.com"):
        # type: (text_type, text_type, text_type) -> HttpResponse
        self.client.post('/accounts/home/',
                         {'email': username + "@" + domain})
        return self.submit_reg_form_for_user(username, password, domain=domain)

    def submit_reg_form_for_user(self, username, password, domain="zulip.com"):
        # type: (text_type, text_type, text_type) -> HttpResponse
        """
        Stage two of the two-step registration process.

        If things are working correctly the account should be fully
        registered after this call.
        """
        return self.client.post('/accounts/register/',
                                {'full_name': username, 'password': password,
                                 'key': find_key_by_email(username + '@' + domain),
                                 'terms': True})

    def get_api_key(self, email):
        # type: (str) -> str
        if email not in API_KEYS:
            API_KEYS[email] = get_user_profile_by_email(email).api_key
        return API_KEYS[email]

    def api_auth(self, email):
        # type: (str) -> Dict[str, str]
        credentials = "%s:%s" % (email, self.get_api_key(email))
        return {
            'HTTP_AUTHORIZATION': 'Basic ' + base64.b64encode(credentials)
        }

    def get_streams(self, email):
        # type: (text_type) -> List[text_type]
        """
        Helper function to get the stream names for a user
        """
        user_profile = get_user_profile_by_email(email)
        subs = Subscription.objects.filter(
            user_profile=user_profile,
            active=True,
            recipient__type=Recipient.STREAM)
        return [cast(text_type, get_display_recipient(sub.recipient)) for sub in subs]

    def send_message(self, sender_name, raw_recipients, message_type,
                     content=u"test content", subject=u"test", **kwargs):
        # type: (str, Union[text_type, List[text_type]], int, text_type, text_type, **Any) -> int
        sender = get_user_profile_by_email(sender_name)
        if message_type == Recipient.PERSONAL:
            message_type_name = "private"
        else:
            message_type_name = "stream"
        if isinstance(raw_recipients, six.string_types):
            recipient_list = [raw_recipients]
        else:
            recipient_list = raw_recipients
        (sending_client, _) = Client.objects.get_or_create(name="test suite")

        return check_send_message(
            sender, sending_client, message_type_name, recipient_list, subject,
            content, forged=False, forged_timestamp=None,
            forwarder_user_profile=sender, realm=sender.realm, **kwargs)

    def get_old_messages(self, anchor=1, num_before=100, num_after=100):
        # type: (int, int, int) -> List[Dict[str, Any]]
        post_params = {"anchor": anchor, "num_before": num_before,
                       "num_after": num_after}
        result = self.client.get("/json/messages", dict(post_params))
        data = ujson.loads(result.content)
        return data['messages']

    def users_subscribed_to_stream(self, stream_name, realm_domain):
        # type: (text_type, text_type) -> List[UserProfile]
        realm = get_realm(realm_domain)
        stream = Stream.objects.get(name=stream_name, realm=realm)
        recipient = Recipient.objects.get(type_id=stream.id, type=Recipient.STREAM)
        subscriptions = Subscription.objects.filter(recipient=recipient, active=True)

        return [subscription.user_profile for subscription in subscriptions]

    def assert_json_success(self, result):
        # type: (HttpResponse) -> Dict[str, Any]
        """
        Successful POSTs return a 200 and JSON of the form {"result": "success",
        "msg": ""}.
        """
        self.assertEqual(result.status_code, 200, result)
        json = ujson.loads(result.content)
        self.assertEqual(json.get("result"), "success")
        # We have a msg key for consistency with errors, but it typically has an
        # empty value.
        self.assertIn("msg", json)
        return json

    def get_json_error(self, result, status_code=400):
        # type: (HttpResponse, int) -> Dict[str, Any]
        self.assertEqual(result.status_code, status_code)
        json = ujson.loads(result.content)
        self.assertEqual(json.get("result"), "error")
        return json['msg']

    def assert_json_error(self, result, msg, status_code=400):
        # type: (HttpResponse, str, int) -> None
        """
        Invalid POSTs return an error status code and JSON of the form
        {"result": "error", "msg": "reason"}.
        """
        self.assertEqual(self.get_json_error(result, status_code=status_code), msg)

    def assert_length(self, queries, count, exact=False):
        # type: (Sized, int, bool) -> None
        actual_count = len(queries)
        if exact:
            return self.assertTrue(actual_count == count,
                                   "len(%s) == %s, != %s" % (queries, actual_count, count))
        return self.assertTrue(actual_count <= count,
                               "len(%s) == %s, > %s" % (queries, actual_count, count))

    def assert_json_error_contains(self, result, msg_substring, status_code=400):
        # type: (HttpResponse, str, int) -> None
        self.assertIn(msg_substring, self.get_json_error(result, status_code=status_code))

    def fixture_data(self, type, action, file_type='json'):
        # type: (text_type, text_type, text_type) -> text_type
        return force_text(open(os.path.join(os.path.dirname(__file__),
                                            "../fixtures/%s/%s_%s.%s" % (type, type, action, file_type))).read())

    # Subscribe to a stream directly
    def subscribe_to_stream(self, email, stream_name, realm=None):
        # type: (text_type, text_type, Optional[Realm]) -> None
        if realm is None:
            realm = get_realm(resolve_email_to_domain(email))
        stream = get_stream(stream_name, realm)
        if stream is None:
            stream, _ = create_stream_if_needed(realm, stream_name)
        user_profile = get_user_profile_by_email(email)
        do_add_subscription(user_profile, stream, no_log=True)

    # Subscribe to a stream by making an API request
    def common_subscribe_to_streams(self, email, streams, extra_post_data={}, invite_only=False):
        # type: (str, Iterable[text_type], Dict[str, Any], bool) -> HttpResponse
        post_data = {'subscriptions': ujson.dumps([{"name": stream} for stream in streams]),
                     'invite_only': ujson.dumps(invite_only)}
        post_data.update(extra_post_data)
        result = self.client.post("/api/v1/users/me/subscriptions", post_data, **self.api_auth(email))
        return result

    def send_json_payload(self, email, url, payload, stream_name=None, **post_params):
        # type: (text_type, text_type, Dict[str, Any], Optional[text_type], **Any) -> Message
        if stream_name is not None:
            self.subscribe_to_stream(email, stream_name)

        result = self.client.post(url, payload, **post_params)
        self.assert_json_success(result)

        # Check the correct message was sent
        msg = self.get_last_message()
        self.assertEqual(msg.sender.email, email)
        self.assertEqual(get_display_recipient(msg.recipient), stream_name)

        return msg

    def get_last_message(self):
        # type: () -> Message
        return Message.objects.latest('id')

    def get_second_to_last_message(self):
        return Message.objects.all().order_by('-id')[1]

def get_all_templates():
    # type: () -> List[str]
    templates = []

    relpath = os.path.relpath
    isfile = os.path.isfile
    path_exists = os.path.exists

    is_valid_template = lambda p, n: not n.startswith('.') and isfile(p)

    def process(template_dir, dirname, fnames):
        # type: (str, str, Iterable[str]) -> None
        for name in fnames:
            path = os.path.join(dirname, name)
            if is_valid_template(path, name):
                templates.append(relpath(path, template_dir))

    for engine in loader.engines.all():
        template_dirs = [d for d in engine.template_dirs if path_exists(d)]
        for template_dir in template_dirs:
            template_dir = os.path.normpath(template_dir)
            os.path.walk(template_dir, process, template_dir)

    return templates
