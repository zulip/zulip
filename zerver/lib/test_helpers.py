from __future__ import absolute_import
from typing import Any, Callable, Generator, Iterable, Tuple

from django.test import TestCase

from zerver.lib.initial_password import initial_password
from zerver.lib.db import TimeTrackingCursor
from zerver.lib.handlers import allocate_handler_id
from zerver.lib import cache
from zerver.lib import event_queue
from zerver.worker import queue_processors

from zerver.lib.actions import (
    check_send_message, create_stream_if_needed, do_add_subscription,
    get_display_recipient,
)

from zerver.lib.handlers import allocate_handler_id

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
)

import base64
import os
import re
import time
import ujson
from six.moves import urllib

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
    # type: () -> Generator[List[Tuple[str, str, str]], None, None]
    cache_queries = []
    def my_cache_get(key, cache_name=None):
        cache_queries.append(('get', key, cache_name))
        return None

    def my_cache_get_many(keys, cache_name=None):
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
        return wrapper_execute(self, super(TimeTrackingCursor, self).execute, sql, params)  # type: ignore # https://github.com/JukkaL/mypy/issues/1167
    TimeTrackingCursor.execute = cursor_execute # type: ignore # https://github.com/JukkaL/mypy/issues/1167

    def cursor_executemany(self, sql, params=()):
        return wrapper_execute(self, super(TimeTrackingCursor, self).executemany, sql, params)  # type: ignore # https://github.com/JukkaL/mypy/issues/1167
    TimeTrackingCursor.executemany = cursor_executemany # type: ignore # https://github.com/JukkaL/mypy/issues/1167

    yield queries

    TimeTrackingCursor.execute = old_execute # type: ignore # https://github.com/JukkaL/mypy/issues/1167
    TimeTrackingCursor.executemany = old_executemany # type: ignore # https://github.com/JukkaL/mypy/issues/1167


def find_key_by_email(address):
    from django.core.mail import outbox
    key_regex = re.compile("accounts/do_confirm/([a-f0-9]{40})>")
    for message in reversed(outbox):
        if address in message.to:
            return key_regex.search(message.body).groups()[0]

def message_ids(result):
    return set(message['id'] for message in result['messages'])

def message_stream_count(user_profile):
    return UserMessage.objects. \
        select_related("message"). \
        filter(user_profile=user_profile). \
        count()

def most_recent_usermessage(user_profile):
    query = UserMessage.objects. \
        select_related("message"). \
        filter(user_profile=user_profile). \
        order_by('-message')
    return query[0] # Django does LIMIT here

def most_recent_message(user_profile):
    usermessage = most_recent_usermessage(user_profile)
    return usermessage.message

def get_user_messages(user_profile):
    query = UserMessage.objects. \
        select_related("message"). \
        filter(user_profile=user_profile). \
        order_by('message')
    return [um.message for um in query]

class DummyObject(object):
    pass

class DummyTornadoRequest(object):
    def __init__(self):
        self.connection = DummyObject()
        self.connection.stream = DummyStream() # type: ignore # monkey-patching here

class DummyHandler(object):
    def __init__(self, assert_callback):
        self.assert_callback = assert_callback
        self.request = DummyTornadoRequest()
        allocate_handler_id(self)

    # Mocks RequestHandler.async_callback, which wraps a callback to
    # handle exceptions.  We return the callback as-is.
    def async_callback(self, cb):
        return cb

    def write(self, response):
        raise NotImplemented

    def zulip_finish(self, response, *ignore):
        if self.assert_callback:
            self.assert_callback(response)


class DummySession(object):
    session_key = "0"

class DummyStream(object):
    def closed(self):
        return False

class POSTRequestMock(object):
    method = "POST"

    def __init__(self, post_data, user_profile, assert_callback=None):
        self.REQUEST = self.POST = post_data
        self.user = user_profile
        self._tornado_handler = DummyHandler(assert_callback)
        self.session = DummySession()
        self._log_data = {} # type: Dict[str, Any]
        self.META = {'PATH_INFO': 'test'}

class AuthedTestCase(TestCase):
    # Helper because self.client.patch annoying requires you to urlencode
    def client_patch(self, url, info={}, **kwargs):
        info = urllib.parse.urlencode(info)
        return self.client.patch(url, info, **kwargs)
    def client_put(self, url, info={}, **kwargs):
        info = urllib.parse.urlencode(info)
        return self.client.put(url, info, **kwargs)
    def client_delete(self, url, info={}, **kwargs):
        info = urllib.parse.urlencode(info)
        return self.client.delete(url, info, **kwargs)

    def login(self, email, password=None):
        if password is None:
            password = initial_password(email)
        return self.client.post('/accounts/login/',
                                {'username': email, 'password': password})

    def register(self, username, password, domain="zulip.com"):
        self.client.post('/accounts/home/',
                         {'email': username + "@" + domain})
        return self.submit_reg_form_for_user(username, password, domain=domain)

    def submit_reg_form_for_user(self, username, password, domain="zulip.com"):
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
        if email not in API_KEYS:
            API_KEYS[email] =  get_user_profile_by_email(email).api_key
        return API_KEYS[email]

    def api_auth(self, email):
        credentials = "%s:%s" % (email, self.get_api_key(email))
        return {
            'HTTP_AUTHORIZATION': 'Basic ' + base64.b64encode(credentials)
            }

    def get_streams(self, email):
        """
        Helper function to get the stream names for a user
        """
        user_profile = get_user_profile_by_email(email)
        subs = Subscription.objects.filter(
            user_profile    = user_profile,
            active          = True,
            recipient__type = Recipient.STREAM)
        return [get_display_recipient(sub.recipient) for sub in subs]

    def send_message(self, sender_name, recipient_list, message_type,
                     content="test content", subject="test", **kwargs):
        sender = get_user_profile_by_email(sender_name)
        if message_type == Recipient.PERSONAL:
            message_type_name = "private"
        else:
            message_type_name = "stream"
        if isinstance(recipient_list, six.string_types):
            recipient_list = [recipient_list]
        (sending_client, _) = Client.objects.get_or_create(name="test suite")

        return check_send_message(
            sender, sending_client, message_type_name, recipient_list, subject,
            content, forged=False, forged_timestamp=None,
            forwarder_user_profile=sender, realm=sender.realm, **kwargs)

    def get_old_messages(self, anchor=1, num_before=100, num_after=100):
        post_params = {"anchor": anchor, "num_before": num_before,
                       "num_after": num_after}
        result = self.client.get("/json/messages", dict(post_params))
        data = ujson.loads(result.content)
        return data['messages']

    def users_subscribed_to_stream(self, stream_name, realm_domain):
        realm = get_realm(realm_domain)
        stream = Stream.objects.get(name=stream_name, realm=realm)
        recipient = Recipient.objects.get(type_id=stream.id, type=Recipient.STREAM)
        subscriptions = Subscription.objects.filter(recipient=recipient, active=True)

        return [subscription.user_profile for subscription in subscriptions]

    def assert_json_success(self, result):
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
        self.assertEqual(result.status_code, status_code)
        json = ujson.loads(result.content)
        self.assertEqual(json.get("result"), "error")
        return json['msg']

    def assert_json_error(self, result, msg, status_code=400):
        """
        Invalid POSTs return an error status code and JSON of the form
        {"result": "error", "msg": "reason"}.
        """
        self.assertEqual(self.get_json_error(result, status_code=status_code), msg)

    def assert_length(self, queries, count, exact=False):
        actual_count = len(queries)
        if exact:
            return self.assertTrue(actual_count == count,
                                   "len(%s) == %s, != %s" % (queries, actual_count, count))
        return self.assertTrue(actual_count <= count,
                               "len(%s) == %s, > %s" % (queries, actual_count, count))

    def assert_json_error_contains(self, result, msg_substring):
        self.assertIn(msg_substring, self.get_json_error(result))

    def fixture_data(self, type, action, file_type='json'):
        return open(os.path.join(os.path.dirname(__file__),
                                 "../fixtures/%s/%s_%s.%s" % (type, type, action, file_type))).read()

    # Subscribe to a stream directly
    def subscribe_to_stream(self, email, stream_name, realm=None):
        realm = get_realm(resolve_email_to_domain(email))
        stream = get_stream(stream_name, realm)
        if stream is None:
            stream, _ = create_stream_if_needed(realm, stream_name)
        user_profile = get_user_profile_by_email(email)
        do_add_subscription(user_profile, stream, no_log=True)

    # Subscribe to a stream by making an API request
    def common_subscribe_to_streams(self, email, streams, extra_post_data = {}, invite_only=False):
        post_data = {'subscriptions': ujson.dumps([{"name": stream} for stream in streams]),
                     'invite_only': ujson.dumps(invite_only)}
        post_data.update(extra_post_data)
        result = self.client.post("/api/v1/users/me/subscriptions", post_data, **self.api_auth(email))
        return result

    def send_json_payload(self, email, url, payload, stream_name=None, **post_params):
        if stream_name != None:
            self.subscribe_to_stream(email, stream_name)

        result = self.client.post(url, payload, **post_params)
        self.assert_json_success(result)

        # Check the correct message was sent
        msg = Message.objects.filter().order_by('-id')[0]
        self.assertEqual(msg.sender.email, email)
        self.assertEqual(get_display_recipient(msg.recipient), stream_name)

        return msg

    def get_last_message(self):
        return Message.objects.latest('id')
