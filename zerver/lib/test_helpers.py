from __future__ import absolute_import
from __future__ import print_function
from contextlib import contextmanager
from typing import (cast, Any, Callable, Dict, Generator, Iterable, List, Mapping, Optional,
    Sized, Tuple, Union)

from django.conf import settings
from django.test import TestCase
from django.test.client import (
    BOUNDARY, MULTIPART_CONTENT, encode_multipart,
)
from django.template import loader
from django.http import HttpResponse
from django.db.utils import IntegrityError
from django.utils.translation import ugettext as _

from zerver.lib.initial_password import initial_password
from zerver.lib.db import TimeTrackingCursor
from zerver.lib.handlers import allocate_handler_id
from zerver.lib.str_utils import force_text
from zerver.lib import cache
from zerver.lib import event_queue
from zerver.worker import queue_processors

from zerver.lib.actions import (
    check_send_message, create_stream_if_needed, bulk_add_subscriptions,
    get_display_recipient, bulk_remove_subscriptions
)

from zerver.models import (
    get_realm,
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

import base64
import mock
import os
import re
import sys
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
def queries_captured(include_savepoints=False):
    # type: (Optional[bool]) -> Generator[List[Dict[str, Union[str, binary_type]]], None, None]
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
        return wrapper_execute(self, super(TimeTrackingCursor, self).executemany, sql, params) # type: ignore # https://github.com/JukkaL/mypy/issues/1167
    TimeTrackingCursor.executemany = cursor_executemany # type: ignore # https://github.com/JukkaL/mypy/issues/1167

    yield queries

    TimeTrackingCursor.execute = old_execute # type: ignore # https://github.com/JukkaL/mypy/issues/1167
    TimeTrackingCursor.executemany = old_executemany # type: ignore # https://github.com/JukkaL/mypy/issues/1167


def make_client(name):
    # type: (str) -> Client
    client, _ = Client.objects.get_or_create(name=name)
    return client

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
        # type: (text_type) -> None
        self.host = host

    def get_host(self):
        # type: () -> text_type
        return self.host

INSTRUMENTING = os.environ.get('TEST_INSTRUMENT_URL_COVERAGE', '') == 'TRUE'
INSTRUMENTED_CALLS = [] # type: List[Dict[str, Any]]

UrlFuncT = Callable[..., HttpResponse] # TODO: make more specific

def instrument_url(f):
    # type: (UrlFuncT) -> UrlFuncT
    if not INSTRUMENTING:
        return f
    else:
        def wrapper(self, url, info={}, **kwargs):
            # type: (Any, text_type, Dict[str, Any], **Any) -> HttpResponse
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

def write_instrumentation_reports(full_suite):
    # type: (bool) -> None
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

        if full_suite:
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


        if full_suite and len(untested_patterns):
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
