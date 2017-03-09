from __future__ import absolute_import
from __future__ import print_function
from contextlib import contextmanager
from typing import (cast, Any, Callable, Dict, Generator, Iterable, Iterator, List, Mapping,
                    Optional, Set, Sized, Tuple, Union, IO)

from django.core.urlresolvers import LocaleRegexURLResolver
from django.conf import settings
from django.test import TestCase
from django.test.client import (
    BOUNDARY, MULTIPART_CONTENT, encode_multipart,
)
from django.template import loader
from django.http import HttpResponse
from django.db.utils import IntegrityError

from zerver.lib.avatar import avatar_url
from zerver.lib.cache import get_cache_backend
from zerver.lib.initial_password import initial_password
from zerver.lib.db import TimeTrackingCursor
from zerver.lib.str_utils import force_text
from zerver.lib import cache
from zerver.tornado import event_queue
from zerver.tornado.handlers import allocate_handler_id
from zerver.worker import queue_processors

from zerver.lib.actions import (
    check_send_message, create_stream_if_needed, bulk_add_subscriptions,
    get_display_recipient, bulk_remove_subscriptions
)

from zerver.models import (
    get_recipient,
    get_stream,
    get_user_profile_by_email,
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

import collections
import base64
import mock
import os
import re
import sys
import time
import ujson
import unittest
from six.moves import urllib
from six import binary_type
from typing import Text
from zerver.lib.str_utils import NonBinaryStr

from contextlib import contextmanager
import six
import fakeldap
import ldap

class MockLDAP(fakeldap.MockLDAP):
    class LDAPError(ldap.LDAPError):
        pass

    class INVALID_CREDENTIALS(ldap.INVALID_CREDENTIALS):
        pass

    class NO_SUCH_OBJECT(ldap.NO_SUCH_OBJECT):
        pass

    class ALREADY_EXISTS(ldap.ALREADY_EXISTS):
        pass

@contextmanager
def simulated_queue_client(client):
    # type: (type) -> Iterator[None]
    real_SimpleQueueClient = queue_processors.SimpleQueueClient
    queue_processors.SimpleQueueClient = client # type: ignore # https://github.com/JukkaL/mypy/issues/1152
    yield
    queue_processors.SimpleQueueClient = real_SimpleQueueClient # type: ignore # https://github.com/JukkaL/mypy/issues/1152

@contextmanager
def tornado_redirected_to_list(lst):
    # type: (List[Mapping[str, Any]]) -> Iterator[None]
    real_event_queue_process_notification = event_queue.process_notification
    event_queue.process_notification = lambda notice: lst.append(notice)
    # process_notification takes a single parameter called 'notice'.
    # lst.append takes a single argument called 'object'.
    # Some code might call process_notification using keyword arguments,
    # so mypy doesn't allow assigning lst.append to process_notification
    # So explicitly change parameter name to 'notice' to work around this problem
    yield
    event_queue.process_notification = real_event_queue_process_notification

@contextmanager
def simulated_empty_cache():
    # type: () -> Generator[List[Tuple[str, Union[Text, List[Text]], Text]], None, None]
    cache_queries = [] # type: List[Tuple[str, Union[Text, List[Text]], Text]]

    def my_cache_get(key, cache_name=None):
        # type: (Text, Optional[str]) -> Optional[Dict[Text, Any]]
        cache_queries.append(('get', key, cache_name))
        return None

    def my_cache_get_many(keys, cache_name=None):  # nocoverage -- simulated code doesn't use this
        # type: (List[Text], Optional[str]) -> Dict[Text, Any]
        cache_queries.append(('getmany', keys, cache_name))
        return {}

    old_get = cache.cache_get
    old_get_many = cache.cache_get_many
    cache.cache_get = my_cache_get
    cache.cache_get_many = my_cache_get_many
    yield cache_queries
    cache.cache_get = old_get
    cache.cache_get_many = old_get_many

@contextmanager
def queries_captured(include_savepoints=False):
    # type: (Optional[bool]) -> Generator[List[Dict[str, Union[str, binary_type]]], None, None]
    '''
    Allow a user to capture just the queries executed during
    the with statement.
    '''

    queries = [] # type: List[Dict[str, Union[str, binary_type]]]

    def wrapper_execute(self, action, sql, params=()):
        # type: (TimeTrackingCursor, Callable, NonBinaryStr, Iterable[Any]) -> None
        cache = get_cache_backend(None)
        cache.clear()
        start = time.time()
        try:
            return action(sql, params)
        finally:
            stop = time.time()
            duration = stop - start
            if include_savepoints or ('SAVEPOINT' not in sql):
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
        return wrapper_execute(self, super(TimeTrackingCursor, self).executemany, sql, params) # type: ignore # https://github.com/JukkaL/mypy/issues/1167 # nocoverage -- doesn't actually get used in tests
    TimeTrackingCursor.executemany = cursor_executemany # type: ignore # https://github.com/JukkaL/mypy/issues/1167

    yield queries

    TimeTrackingCursor.execute = old_execute # type: ignore # https://github.com/JukkaL/mypy/issues/1167
    TimeTrackingCursor.executemany = old_executemany # type: ignore # https://github.com/JukkaL/mypy/issues/1167

@contextmanager
def stdout_suppressed():
    # type: () -> Iterator[IO[str]]
    """Redirect stdout to /dev/null."""

    with open(os.devnull, 'a') as devnull:
        stdout, sys.stdout = sys.stdout, devnull  # type: ignore
        yield stdout
        sys.stdout = stdout

def get_test_image_file(filename):
    # type: (str) -> IO[Any]
    test_avatar_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../tests/images'))
    return open(os.path.join(test_avatar_dir, filename), 'rb')

def avatar_disk_path(user_profile, medium=False):
    # type: (UserProfile, bool) -> str
    avatar_url_path = avatar_url(user_profile, medium)
    avatar_disk_path = os.path.join(settings.LOCAL_UPLOADS_DIR, "avatars",
                                    avatar_url_path.split("/")[-2],
                                    avatar_url_path.split("/")[-1].split("?")[0])
    return avatar_disk_path

def make_client(name):
    # type: (str) -> Client
    client, _ = Client.objects.get_or_create(name=name)
    return client

def find_key_by_email(address):
    # type: (Text) -> Optional[Text]
    from django.core.mail import outbox
    key_regex = re.compile("accounts/do_confirm/([a-f0-9]{40})>")
    for message in reversed(outbox):
        if address in message.to:
            return key_regex.search(message.body).groups()[0]
    return None  # nocoverage -- in theory a test might want this case, but none do

def find_pattern_in_email(address, pattern):
    # type: (Text, Text) -> Optional[Text]
    from django.core.mail import outbox
    key_regex = re.compile(pattern)
    for message in reversed(outbox):
        if address in message.to:
            return key_regex.search(message.body).group(0)
    return None  # nocoverage -- in theory a test might want this case, but none do

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

def get_subscription(stream_name, user_profile):
    # type: (Text, UserProfile) -> Subscription
    stream = get_stream(stream_name, user_profile.realm)
    recipient = get_recipient(Recipient.STREAM, stream.id)
    return Subscription.objects.get(user_profile=user_profile,
                                    recipient=recipient, active=True)

def get_user_messages(user_profile):
    # type: (UserProfile) -> List[Message]
    query = UserMessage.objects. \
        select_related("message"). \
        filter(user_profile=user_profile). \
        order_by('message')
    return [um.message for um in query]

class DummyHandler(object):
    def __init__(self):
        # type: () -> None
        allocate_handler_id(self)  # type: ignore # this is a testing mock

class POSTRequestMock(object):
    method = "POST"

    def __init__(self, post_data, user_profile):
        # type: (Dict[str, Any], UserProfile) -> None
        self.GET = {}  # type: Dict[str, Any]
        self.POST = post_data
        self.user = user_profile
        self._tornado_handler = DummyHandler()
        self._log_data = {} # type: Dict[str, Any]
        self.META = {'PATH_INFO': 'test'}

class HostRequestMock(object):
    """A mock request object where get_host() works.  Useful for testing
    routes that use Zulip's subdomains feature"""

    def __init__(self, host=settings.EXTERNAL_HOST):
        # type: (Text) -> None
        self.host = host

    def get_host(self):
        # type: () -> Text
        return self.host

class MockPythonResponse(object):
    def __init__(self, text, status_code):
        # type: (Text, int) -> None
        self.text = text
        self.status_code = status_code

    @property
    def ok(self):
        # type: () -> bool
        return self.status_code == 200

INSTRUMENTING = os.environ.get('TEST_INSTRUMENT_URL_COVERAGE', '') == 'TRUE'
INSTRUMENTED_CALLS = [] # type: List[Dict[str, Any]]

UrlFuncT = Callable[..., HttpResponse] # TODO: make more specific

def append_instrumentation_data(data):
    # type: (Dict[str, Any]) -> None
    INSTRUMENTED_CALLS.append(data)

def instrument_url(f):
    # type: (UrlFuncT) -> UrlFuncT
    if not INSTRUMENTING:  # nocoverage -- option is always enabled; should we remove?
        return f
    else:
        def wrapper(self, url, info={}, **kwargs):
            # type: (Any, Text, Dict[str, Any], **Any) -> HttpResponse
            start = time.time()
            result = f(self, url, info, **kwargs)
            delay = time.time() - start
            test_name = self.id()
            if '?' in url:
                url, extra_info = url.split('?', 1)
            else:
                extra_info = ''

            append_instrumentation_data(dict(
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

def write_instrumentation_reports(full_suite):
    # type: (bool) -> None
    if INSTRUMENTING:
        calls = INSTRUMENTED_CALLS

        from zproject.urls import urlpatterns, v1_api_and_json_patterns

        # Find our untested urls.
        pattern_cnt = collections.defaultdict(int) # type: Dict[str, int]

        def re_strip(r):
            # type: (Any) -> str
            return str(r).lstrip('^').rstrip('$')

        def find_patterns(patterns, prefixes):
            # type: (List[Any], List[str]) -> None
            for pattern in patterns:
                find_pattern(pattern, prefixes)

        def cleanup_url(url):
            # type: (str) -> str
            if url.startswith('/'):
                url = url[1:]
            if url.startswith('http://testserver/'):
                url = url[len('http://testserver/'):]
            if url.startswith('http://zulip.testserver/'):
                url = url[len('http://zulip.testserver/'):]
            if url.startswith('http://testserver:9080/'):
                url = url[len('http://testserver:9080/'):]
            return url

        def find_pattern(pattern, prefixes):
            # type: (Any, List[str]) -> None

            if isinstance(pattern, type(LocaleRegexURLResolver)):
                return  # nocoverage -- shouldn't actually happen

            if hasattr(pattern, 'url_patterns'):
                return

            canon_pattern = prefixes[0] + re_strip(pattern.regex.pattern)
            cnt = 0
            for call in calls:
                if 'pattern' in call:
                    continue

                url = cleanup_url(call['url'])

                for prefix in prefixes:
                    if url.startswith(prefix):
                        match_url = url[len(prefix):]
                        if pattern.regex.match(match_url):
                            if call['status_code'] in [200, 204, 301, 302]:
                                cnt += 1
                            call['pattern'] = canon_pattern
            pattern_cnt[canon_pattern] += cnt

        find_patterns(urlpatterns, ['', 'en/', 'de/'])
        find_patterns(v1_api_and_json_patterns, ['api/v1/', 'json/'])

        assert len(pattern_cnt) > 100
        untested_patterns = set([p for p in pattern_cnt if pattern_cnt[p] == 0])

        # We exempt some patterns that are called via Tornado.
        exempt_patterns = set([
            'api/v1/events',
            'api/v1/register',
        ])

        untested_patterns -= exempt_patterns

        var_dir = 'var' # TODO make sure path is robust here
        fn = os.path.join(var_dir, 'url_coverage.txt')
        with open(fn, 'w') as f:
            for call in calls:
                try:
                    line = ujson.dumps(call)
                    f.write(line + '\n')
                except OverflowError:  # nocoverage -- test suite error handling
                    print('''
                        A JSON overflow error was encountered while
                        producing the URL coverage report.  Sometimes
                        this indicates that a test is passing objects
                        into methods like client_post(), which is
                        unnecessary and leads to false positives.
                        ''')
                    print(call)

        if full_suite:
            print('INFO: URL coverage report is in %s' % (fn,))
            print('INFO: Try running: ./tools/create-test-api-docs')

        if full_suite and len(untested_patterns):  # nocoverage -- test suite error handling
            print("\nERROR: Some URLs are untested!  Here's the list of untested URLs:")
            for untested_pattern in sorted(untested_patterns):
                print("   %s" % (untested_pattern,))
            sys.exit(1)

def get_all_templates():
    # type: () -> List[str]
    templates = []

    relpath = os.path.relpath
    isfile = os.path.isfile
    path_exists = os.path.exists

    def is_valid_template(p, n):
        # type: (Text, Text) -> bool
        return 'webhooks' not in p \
               and not n.startswith('.') \
               and not n.startswith('__init__') \
               and not n.endswith('.md') \
               and isfile(p)

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
