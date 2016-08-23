from __future__ import absolute_import
from __future__ import print_function
from contextlib import contextmanager
from typing import (cast, Any, Callable, Dict, Generator, Iterable, List, Mapping, Optional,
    Sized, Tuple, Union)

from django.test import TestCase
from django.test.client import (
    BOUNDARY, MULTIPART_CONTENT, encode_multipart,
)
from django.template import loader
from django.http import HttpResponse
from django.utils.translation import ugettext as _

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

from zerver.lib.request import JsonableError


import base64
import os
import re
import time
import ujson
import unittest
from six.moves import urllib
from six import text_type, binary_type
from zerver.lib.str_utils import NonBinaryStr

from contextlib import contextmanager
import six

API_KEYS = {} # type: Dict[text_type, text_type]

skip_py3 = unittest.skipIf(six.PY3, "Expected failure on Python 3")

@contextmanager
def simulated_queue_client(client):
    # type: (type) -> Generator[None, None, None]
    real_SimpleQueueClient = queue_processors.SimpleQueueClient
    queue_processors.SimpleQueueClient = client # type: ignore # https://github.com/JukkaL/mypy/issues/1152
    yield
    queue_processors.SimpleQueueClient = real_SimpleQueueClient # type: ignore # https://github.com/JukkaL/mypy/issues/1152

@contextmanager
def tornado_redirected_to_list(lst):
    # type: (List[Mapping[str, Any]]) -> Generator[None, None, None]
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
    # type: () -> Generator[List[Dict[str, Union[str, binary_type]]], None, None]
    '''
    Allow a user to capture just the queries executed during
    the with statement.
    '''

    queries = [] # type: List[Dict[str, Union[str, binary_type]]]

    def wrapper_execute(self, action, sql, params=()):
        # type: (TimeTrackingCursor, Callable, NonBinaryStr, Iterable[Any]) -> None
        start = time.time()
        try:
            return action(sql, params)
        finally:
            stop = time.time()
            duration = stop - start
            queries.append({
                'sql': self.mogrify(sql, params).decode('utf-8'),
                'time': "%.3f" % duration,
            })

    old_execute = TimeTrackingCursor.execute
    old_executemany = TimeTrackingCursor.executemany

    def cursor_execute(self, sql, params=()):
        # type: (TimeTrackingCursor, NonBinaryStr, Iterable[Any]) -> None
        return wrapper_execute(self, super(TimeTrackingCursor, self).execute, sql, params) # type: ignore # https://github.com/JukkaL/mypy/issues/1167
    TimeTrackingCursor.execute = cursor_execute # type: ignore # https://github.com/JukkaL/mypy/issues/1167

    def cursor_executemany(self, sql, params=()):
        # type: (TimeTrackingCursor, NonBinaryStr, Iterable[Any]) -> None
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

class DummyHandler(object):
    def __init__(self):
        # type: (Callable) -> None
        allocate_handler_id(self)

class POSTRequestMock(object):
    method = "POST"

    def __init__(self, post_data, user_profile):
        # type: (Dict[str, Any], UserProfile) -> None
        self.REQUEST = self.POST = post_data
        self.user = user_profile
        self._tornado_handler = DummyHandler()
        self._log_data = {} # type: Dict[str, Any]
        self.META = {'PATH_INFO': 'test'}

INSTRUMENTING = os.environ.get('TEST_INSTRUMENT_URL_COVERAGE', '') == 'TRUE'
INSTRUMENTED_CALLS = []

def instrument_url(f):
    if not INSTRUMENTING:
        return f
    else:
        def wrapper(self, url, info={}, **kwargs):
            start = time.time()
            result = f(self, url, info, **kwargs)
            delay = time.time() - start
            test_name = self.id()
            if '?' in url:
                url, extra_info = url.split('?', 1)
            else:
                extra_info = ''

            INSTRUMENTED_CALLS.append(dict(
                url=url,
                status_code=result.status_code,
                method=f.__name__,
                delay=delay,
                extra_info=extra_info,
                info=info,
                test_name=test_name,
                kwargs=kwargs))
            return result
        return wrapper

def write_instrumentation_reports():
    # type: () -> None
    if INSTRUMENTING:
        calls = INSTRUMENTED_CALLS
        var_dir = 'var' # TODO make sure path is robust here
        fn = os.path.join(var_dir, 'url_coverage.txt')
        with open(fn, 'w') as f:
            for call in calls:
                try:
                    line = ujson.dumps(call)
                    f.write(line + '\n')
                except OverflowError:
                    print('''
                        A JSON overflow error was encountered while
                        producing the URL coverage report.  Sometimes
                        this indicates that a test is passing objects
                        into methods like client_post(), which is
                        unnecessary and leads to false positives.
                        ''')
                    print(call)

        print('URL coverage report is in %s' % (fn,))
        print('Try running: ./tools/analyze-url-coverage')

        # Find our untested urls.
        from zproject.urls import urlpatterns
        untested_patterns = []
        for pattern in urlpatterns:
            for call in calls:
                url = call['url']
                if url.startswith('/'):
                    url = url[1:]
                if pattern.regex.match(url):
                    break
            else:
                untested_patterns.append(pattern.regex.pattern)

        fn = os.path.join(var_dir, 'untested_url_report.txt')
        with open(fn, 'w') as f:
            f.write('untested urls\n')
            for untested_pattern in sorted(untested_patterns):
                f.write('  %s\n' % (untested_pattern,))
        print('Untested-url report is in %s' % (fn,))


class ZulipTestCase(TestCase):
    '''
    WRAPPER_COMMENT:

    We wrap calls to self.client.{patch,put,get,post,delete} for various
    reasons.  Some of this has to do with fixing encodings before calling
    into the Django code.  Some of this has to do with providing a future
    path for instrumentation.  Some of it's just consistency.

    The linter will prevent direct calls to self.client.foo, so the wrapper
    functions have to fake out the linter by using a local variable called
    django_client to fool the regext.
    '''

    @instrument_url
    def client_patch(self, url, info={}, **kwargs):
        # type: (text_type, Dict[str, Any], **Any) -> HttpResponse
        """
        We need to urlencode, since Django's function won't do it for us.
        """
        encoded = urllib.parse.urlencode(info)
        django_client = self.client # see WRAPPER_COMMENT
        return django_client.patch(url, encoded, **kwargs)

    @instrument_url
    def client_patch_multipart(self, url, info={}, **kwargs):
        # type: (text_type, Dict[str, Any], **Any) -> HttpResponse
        """
        Use this for patch requests that have file uploads or
        that need some sort of multi-part content.  In the future
        Django's test client may become a bit more flexible,
        so we can hopefully eliminate this.  (When you post
        with the Django test client, it deals with MULTIPART_CONTENT
        automatically, but not patch.)
        """
        encoded = encode_multipart(BOUNDARY, info)
        django_client = self.client # see WRAPPER_COMMENT
        return django_client.patch(
            url,
            encoded,
            content_type=MULTIPART_CONTENT,
            **kwargs)

    @instrument_url
    def client_put(self, url, info={}, **kwargs):
        # type: (text_type, Dict[str, Any], **Any) -> HttpResponse
        encoded = urllib.parse.urlencode(info)
        django_client = self.client # see WRAPPER_COMMENT
        return django_client.put(url, encoded, **kwargs)

    @instrument_url
    def client_delete(self, url, info={}, **kwargs):
        # type: (text_type, Dict[str, Any], **Any) -> HttpResponse
        encoded = urllib.parse.urlencode(info)
        django_client = self.client # see WRAPPER_COMMENT
        return django_client.delete(url, encoded, **kwargs)

    @instrument_url
    def client_post(self, url, info={}, **kwargs):
        django_client = self.client # see WRAPPER_COMMENT
        return django_client.post(url, info, **kwargs)

    @instrument_url
    def client_get(self, url, info={}, **kwargs):
        django_client = self.client # see WRAPPER_COMMENT
        return django_client.get(url, info, **kwargs)

    def login_with_return(self, email, password=None):
        # type: (text_type, Optional[text_type]) -> HttpResponse
        if password is None:
            password = initial_password(email)
        return self.client_post('/accounts/login/',
                                {'username': email, 'password': password})

    def login(self, email, password=None, fails=False):
        # type: (text_type, Optional[text_type], bool) -> HttpResponse
        if password is None:
            password = initial_password(email)
        if not fails:
            self.assertTrue(self.client.login(username=email, password=password))
        else:
            self.assertFalse(self.client.login(username=email, password=password))

    def register(self, username, password, domain="zulip.com"):
        # type: (text_type, text_type, text_type) -> HttpResponse
        self.client_post('/accounts/home/',
                         {'email': username + "@" + domain})
        return self.submit_reg_form_for_user(username, password, domain=domain)

    def submit_reg_form_for_user(self, username, password, domain="zulip.com"):
        # type: (text_type, text_type, text_type) -> HttpResponse
        """
        Stage two of the two-step registration process.

        If things are working correctly the account should be fully
        registered after this call.
        """
        return self.client_post('/accounts/register/',
                                {'full_name': username, 'password': password,
                                 'key': find_key_by_email(username + '@' + domain),
                                 'terms': True})

    def get_api_key(self, email):
        # type: (text_type) -> text_type
        if email not in API_KEYS:
            API_KEYS[email] = get_user_profile_by_email(email).api_key
        return API_KEYS[email]

    def api_auth(self, email):
        # type: (text_type) -> Dict[str, text_type]
        credentials = u"%s:%s" % (email, self.get_api_key(email))
        return {
            'HTTP_AUTHORIZATION': u'Basic ' + base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
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
        # type: (text_type, Union[text_type, List[text_type]], int, text_type, text_type, **Any) -> int
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
        result = self.client_get("/json/messages", dict(post_params))
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
        # type: (HttpResponse, text_type, int) -> None
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
        # type: (HttpResponse, text_type, int) -> None
        self.assertIn(msg_substring, self.get_json_error(result, status_code=status_code))

    def assert_equals_response(self, string, response):
        # type: (text_type, HttpResponse) -> None
        self.assertEqual(string, response.content.decode('utf-8'))

    def assert_in_response(self, substring, response):
        # type: (text_type, HttpResponse) -> None
        self.assertIn(substring, response.content.decode('utf-8'))

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
        # type: (text_type, Iterable[text_type], Dict[str, Any], bool) -> HttpResponse
        post_data = {'subscriptions': ujson.dumps([{"name": stream} for stream in streams]),
                     'invite_only': ujson.dumps(invite_only)}
        post_data.update(extra_post_data)
        result = self.client_post("/api/v1/users/me/subscriptions", post_data, **self.api_auth(email))
        return result

    def send_json_payload(self, email, url, payload, stream_name=None, **post_params):
        # type: (text_type, text_type, Union[text_type, Dict[str, Any]], Optional[text_type], **Any) -> Message
        if stream_name is not None:
            self.subscribe_to_stream(email, stream_name)

        result = self.client_post(url, payload, **post_params)
        self.assert_json_success(result)

        # Check the correct message was sent
        msg = self.get_last_message()
        self.assertEqual(msg.sender.email, email)
        if stream_name is not None:
            self.assertEqual(get_display_recipient(msg.recipient), stream_name)
        # TODO: should also validate recipient for private messages

        return msg

    def get_last_message(self):
        # type: () -> Message
        return Message.objects.latest('id')

    def get_second_to_last_message(self):
        # type: () -> Message
        return Message.objects.all().order_by('-id')[1]

def get_all_templates():
    # type: () -> List[str]
    templates = []

    relpath = os.path.relpath
    isfile = os.path.isfile
    path_exists = os.path.exists

    def is_valid_template(p, n):
        # type: (text_type, text_type) -> bool
        return not n.startswith('.') and not n.startswith('__init__') and isfile(p)

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
            for dirpath, dirnames, fnames in os.walk(template_dir):
                process(template_dir, dirpath, fnames)

    return templates
