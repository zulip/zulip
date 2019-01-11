from contextlib import contextmanager
from typing import (
    Any, Callable, Dict, Generator, Iterable, Iterator, List, Mapping,
    Optional, Tuple, Union, IO, TypeVar
)

from django.core import signing
from django.urls.resolvers import LocaleRegexURLResolver
from django.conf import settings
from django.test import override_settings
from django.template import loader
from django.http import HttpResponse, HttpResponseRedirect
from django.db.migrations.state import StateApps
from boto.s3.connection import S3Connection
from boto.s3.bucket import Bucket

import zerver.lib.upload
from zerver.lib.upload import S3UploadBackend, LocalUploadBackend
from zerver.lib.avatar import avatar_url
from zerver.lib.cache import get_cache_backend
from zerver.lib.db import TimeTrackingCursor
from zerver.lib import cache
from zerver.tornado import event_queue
from zerver.tornado.handlers import allocate_handler_id
from zerver.worker import queue_processors
from zerver.lib.integrations import WEBHOOK_INTEGRATIONS

from zerver.lib.actions import (
    get_stream_recipient,
)

from zerver.models import (
    get_stream,
    Client,
    Message,
    Subscription,
    UserMessage,
    UserProfile,
)

if False:
    # Avoid an import cycle; we only need these for type annotations.
    from zerver.lib.test_classes import ZulipTestCase, MigrationsTestCase

import collections
import mock
import os
import re
import sys
import time
import ujson
from moto import mock_s3_deprecated

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
def stub_event_queue_user_events(event_queue_return: Any, user_events_return: Any) -> Iterator[None]:
    with mock.patch('zerver.lib.events.request_event_queue',
                    return_value=event_queue_return):
        with mock.patch('zerver.lib.events.get_user_events',
                        return_value=user_events_return):
            yield

@contextmanager
def simulated_queue_client(client: Callable[..., Any]) -> Iterator[None]:
    real_SimpleQueueClient = queue_processors.SimpleQueueClient
    queue_processors.SimpleQueueClient = client  # type: ignore # https://github.com/JukkaL/mypy/issues/1152
    yield
    queue_processors.SimpleQueueClient = real_SimpleQueueClient  # type: ignore # https://github.com/JukkaL/mypy/issues/1152

@contextmanager
def tornado_redirected_to_list(lst: List[Mapping[str, Any]]) -> Iterator[None]:
    real_event_queue_process_notification = event_queue.process_notification
    event_queue.process_notification = lambda notice: lst.append(notice)
    # process_notification takes a single parameter called 'notice'.
    # lst.append takes a single argument called 'object'.
    # Some code might call process_notification using keyword arguments,
    # so mypy doesn't allow assigning lst.append to process_notification
    # So explicitly change parameter name to 'notice' to work around this problem
    yield
    event_queue.process_notification = real_event_queue_process_notification

class EventInfo:
    def populate(self, call_args_list: List[Any]) -> None:
        args = call_args_list[0][0]
        self.realm_id = args[0]
        self.payload = args[1]
        self.user_ids = args[2]

@contextmanager
def capture_event(event_info: EventInfo) -> Iterator[None]:
    # Use this for simple endpoints that throw a single event
    # in zerver.lib.actions.
    with mock.patch('zerver.lib.actions.send_event') as m:
        yield

    if len(m.call_args_list) == 0:
        raise AssertionError('No event was sent inside actions.py')

    if len(m.call_args_list) > 1:
        raise AssertionError('Too many events sent by action')

    event_info.populate(m.call_args_list)

@contextmanager
def simulated_empty_cache() -> Generator[
        List[Tuple[str, Union[str, List[str]], str]], None, None]:
    cache_queries = []  # type: List[Tuple[str, Union[str, List[str]], str]]

    def my_cache_get(key: str, cache_name: Optional[str]=None) -> Optional[Dict[str, Any]]:
        cache_queries.append(('get', key, cache_name))
        return None

    def my_cache_get_many(keys: List[str], cache_name: Optional[str]=None) -> Dict[str, Any]:  # nocoverage -- simulated code doesn't use this
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
def queries_captured(include_savepoints: Optional[bool]=False) -> Generator[
        List[Dict[str, Union[str, bytes]]], None, None]:
    '''
    Allow a user to capture just the queries executed during
    the with statement.
    '''

    queries = []  # type: List[Dict[str, Union[str, bytes]]]

    def wrapper_execute(self: TimeTrackingCursor,
                        action: Callable[[str, Iterable[Any]], None],
                        sql: str,
                        params: Iterable[Any]=()) -> None:
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

    def cursor_execute(self: TimeTrackingCursor, sql: str,
                       params: Iterable[Any]=()) -> None:
        return wrapper_execute(self, super(TimeTrackingCursor, self).execute, sql, params)  # type: ignore # https://github.com/JukkaL/mypy/issues/1167
    TimeTrackingCursor.execute = cursor_execute  # type: ignore # https://github.com/JukkaL/mypy/issues/1167

    def cursor_executemany(self: TimeTrackingCursor, sql: str,
                           params: Iterable[Any]=()) -> None:
        return wrapper_execute(self, super(TimeTrackingCursor, self).executemany, sql, params)  # type: ignore # https://github.com/JukkaL/mypy/issues/1167 # nocoverage -- doesn't actually get used in tests
    TimeTrackingCursor.executemany = cursor_executemany  # type: ignore # https://github.com/JukkaL/mypy/issues/1167

    yield queries

    TimeTrackingCursor.execute = old_execute  # type: ignore # https://github.com/JukkaL/mypy/issues/1167
    TimeTrackingCursor.executemany = old_executemany  # type: ignore # https://github.com/JukkaL/mypy/issues/1167

@contextmanager
def stdout_suppressed() -> Iterator[IO[str]]:
    """Redirect stdout to /dev/null."""

    with open(os.devnull, 'a') as devnull:
        stdout, sys.stdout = sys.stdout, devnull
        yield stdout
        sys.stdout = stdout

def get_test_image_file(filename: str) -> IO[Any]:
    test_avatar_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../tests/images'))
    return open(os.path.join(test_avatar_dir, filename), 'rb')

def avatar_disk_path(user_profile: UserProfile, medium: bool=False, original: bool=False) -> str:
    avatar_url_path = avatar_url(user_profile, medium)
    avatar_disk_path = os.path.join(settings.LOCAL_UPLOADS_DIR, "avatars",
                                    avatar_url_path.split("/")[-2],
                                    avatar_url_path.split("/")[-1].split("?")[0])
    if original:
        return avatar_disk_path.replace(".png", ".original")
    return avatar_disk_path

def make_client(name: str) -> Client:
    client, _ = Client.objects.get_or_create(name=name)
    return client

def find_key_by_email(address: str) -> Optional[str]:
    from django.core.mail import outbox
    key_regex = re.compile("accounts/do_confirm/([a-z0-9]{24})>")
    for message in reversed(outbox):
        if address in message.to:
            return key_regex.search(message.body).groups()[0]
    return None  # nocoverage -- in theory a test might want this case, but none do

def message_stream_count(user_profile: UserProfile) -> int:
    return UserMessage.objects. \
        select_related("message"). \
        filter(user_profile=user_profile). \
        count()

def most_recent_usermessage(user_profile: UserProfile) -> UserMessage:
    query = UserMessage.objects. \
        select_related("message"). \
        filter(user_profile=user_profile). \
        order_by('-message')
    return query[0]  # Django does LIMIT here

def most_recent_message(user_profile: UserProfile) -> Message:
    usermessage = most_recent_usermessage(user_profile)
    return usermessage.message

def get_subscription(stream_name: str, user_profile: UserProfile) -> Subscription:
    stream = get_stream(stream_name, user_profile.realm)
    recipient = get_stream_recipient(stream.id)
    return Subscription.objects.get(user_profile=user_profile,
                                    recipient=recipient, active=True)

def get_user_messages(user_profile: UserProfile) -> List[Message]:
    query = UserMessage.objects. \
        select_related("message"). \
        filter(user_profile=user_profile). \
        order_by('message')
    return [um.message for um in query]

class DummyHandler:
    def __init__(self) -> None:
        allocate_handler_id(self)  # type: ignore # this is a testing mock

class POSTRequestMock:
    method = "POST"

    def __init__(self, post_data: Dict[str, Any], user_profile: Optional[UserProfile]) -> None:
        self.GET = {}  # type: Dict[str, Any]
        self.POST = post_data
        self.user = user_profile
        self._tornado_handler = DummyHandler()
        self._log_data = {}  # type: Dict[str, Any]
        self.META = {'PATH_INFO': 'test'}
        self.path = ''

class HostRequestMock:
    """A mock request object where get_host() works.  Useful for testing
    routes that use Zulip's subdomains feature"""

    def __init__(self, user_profile: UserProfile=None, host: str=settings.EXTERNAL_HOST) -> None:
        self.host = host
        self.GET = {}  # type: Dict[str, Any]
        self.POST = {}  # type: Dict[str, Any]
        self.META = {'PATH_INFO': 'test'}
        self.path = ''
        self.user = user_profile
        self.method = ''
        self.body = ''
        self.content_type = ''
        self._email = ''

    def get_host(self) -> str:
        return self.host

class MockPythonResponse:
    def __init__(self, text: str, status_code: int) -> None:
        self.text = text
        self.status_code = status_code

    @property
    def ok(self) -> bool:
        return self.status_code == 200

INSTRUMENTING = os.environ.get('TEST_INSTRUMENT_URL_COVERAGE', '') == 'TRUE'
INSTRUMENTED_CALLS = []  # type: List[Dict[str, Any]]

UrlFuncT = Callable[..., HttpResponse]  # TODO: make more specific

def append_instrumentation_data(data: Dict[str, Any]) -> None:
    INSTRUMENTED_CALLS.append(data)

def instrument_url(f: UrlFuncT) -> UrlFuncT:
    if not INSTRUMENTING:  # nocoverage -- option is always enabled; should we remove?
        return f
    else:
        def wrapper(self: 'ZulipTestCase', url: str, info: Dict[str, Any]={},
                    **kwargs: Any) -> HttpResponse:
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

def write_instrumentation_reports(full_suite: bool, include_webhooks: bool) -> None:
    if INSTRUMENTING:
        calls = INSTRUMENTED_CALLS

        from zproject.urls import urlpatterns, v1_api_and_json_patterns

        # Find our untested urls.
        pattern_cnt = collections.defaultdict(int)  # type: Dict[str, int]

        def re_strip(r: Any) -> str:
            return str(r).lstrip('^').rstrip('$')

        def find_patterns(patterns: List[Any], prefixes: List[str]) -> None:
            for pattern in patterns:
                find_pattern(pattern, prefixes)

        def cleanup_url(url: str) -> str:
            if url.startswith('/'):
                url = url[1:]
            if url.startswith('http://testserver/'):
                url = url[len('http://testserver/'):]
            if url.startswith('http://zulip.testserver/'):
                url = url[len('http://zulip.testserver/'):]
            if url.startswith('http://testserver:9080/'):
                url = url[len('http://testserver:9080/'):]
            return url

        def find_pattern(pattern: Any, prefixes: List[str]) -> None:

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

        exempt_patterns = set([
            # We exempt some patterns that are called via Tornado.
            'api/v1/events',
            'api/v1/events/internal',
            'api/v1/register',
            # We also exempt some development environment debugging
            # static content URLs, since the content they point to may
            # or may not exist.
            'coverage/(?P<path>.*)',
            'node-coverage/(?P<path>.*)',
            'docs/(?P<path>.*)',
            'casper/(?P<path>.*)',
        ] + [webhook.url for webhook in WEBHOOK_INTEGRATIONS if not include_webhooks])

        untested_patterns -= exempt_patterns

        var_dir = 'var'  # TODO make sure path is robust here
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

def get_all_templates() -> List[str]:
    templates = []

    relpath = os.path.relpath
    isfile = os.path.isfile
    path_exists = os.path.exists

    def is_valid_template(p: str, n: str) -> bool:
        return 'webhooks' not in p \
               and not n.startswith('.') \
               and not n.startswith('__init__') \
               and not n.endswith('.md') \
               and not n.endswith('.source.html') \
               and isfile(p)

    def process(template_dir: str, dirname: str, fnames: Iterable[str]) -> None:
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

def load_subdomain_token(response: HttpResponse) -> Dict[str, Any]:
    assert isinstance(response, HttpResponseRedirect)
    token = response.url.rsplit('/', 1)[1]
    return signing.loads(token, salt='zerver.views.auth.log_into_subdomain')

FuncT = TypeVar('FuncT', bound=Callable[..., None])

def use_s3_backend(method: FuncT) -> FuncT:
    @mock_s3_deprecated
    @override_settings(LOCAL_UPLOADS_DIR=None)
    def new_method(*args: Any, **kwargs: Any) -> Any:
        zerver.lib.upload.upload_backend = S3UploadBackend()
        try:
            return method(*args, **kwargs)
        finally:
            zerver.lib.upload.upload_backend = LocalUploadBackend()
    return new_method

def create_s3_buckets(*bucket_names: Tuple[str]) -> List[Bucket]:
    conn = S3Connection(settings.S3_KEY, settings.S3_SECRET_KEY)
    buckets = [conn.create_bucket(name) for name in bucket_names]
    return buckets

def use_db_models(method: Callable[..., None]) -> Callable[..., None]:
    def method_patched_with_mock(self: 'MigrationsTestCase', apps: StateApps) -> None:
        ArchivedAttachment = apps.get_model('zerver', 'ArchivedAttachment')
        ArchivedMessage = apps.get_model('zerver', 'ArchivedMessage')
        ArchivedUserMessage = apps.get_model('zerver', 'ArchivedUserMessage')
        Attachment = apps.get_model('zerver', 'Attachment')
        BotConfigData = apps.get_model('zerver', 'BotConfigData')
        BotStorageData = apps.get_model('zerver', 'BotStorageData')
        Client = apps.get_model('zerver', 'Client')
        CustomProfileField = apps.get_model('zerver', 'CustomProfileField')
        CustomProfileFieldValue = apps.get_model('zerver', 'CustomProfileFieldValue')
        DefaultStream = apps.get_model('zerver', 'DefaultStream')
        DefaultStreamGroup = apps.get_model('zerver', 'DefaultStreamGroup')
        EmailChangeStatus = apps.get_model('zerver', 'EmailChangeStatus')
        Huddle = apps.get_model('zerver', 'Huddle')
        Message = apps.get_model('zerver', 'Message')
        MultiuseInvite = apps.get_model('zerver', 'MultiuseInvite')
        MutedTopic = apps.get_model('zerver', 'MutedTopic')
        PreregistrationUser = apps.get_model('zerver', 'PreregistrationUser')
        PushDeviceToken = apps.get_model('zerver', 'PushDeviceToken')
        Reaction = apps.get_model('zerver', 'Reaction')
        Realm = apps.get_model('zerver', 'Realm')
        RealmAuditLog = apps.get_model('zerver', 'RealmAuditLog')
        RealmDomain = apps.get_model('zerver', 'RealmDomain')
        RealmEmoji = apps.get_model('zerver', 'RealmEmoji')
        RealmFilter = apps.get_model('zerver', 'RealmFilter')
        Recipient = apps.get_model('zerver', 'Recipient')
        ScheduledEmail = apps.get_model('zerver', 'ScheduledEmail')
        ScheduledMessage = apps.get_model('zerver', 'ScheduledMessage')
        Service = apps.get_model('zerver', 'Service')
        Stream = apps.get_model('zerver', 'Stream')
        Subscription = apps.get_model('zerver', 'Subscription')
        UserActivity = apps.get_model('zerver', 'UserActivity')
        UserActivityInterval = apps.get_model('zerver', 'UserActivityInterval')
        UserGroup = apps.get_model('zerver', 'UserGroup')
        UserGroupMembership = apps.get_model('zerver', 'UserGroupMembership')
        UserHotspot = apps.get_model('zerver', 'UserHotspot')
        UserMessage = apps.get_model('zerver', 'UserMessage')
        UserPresence = apps.get_model('zerver', 'UserPresence')
        UserProfile = apps.get_model('zerver', 'UserProfile')

        zerver_models_patch = mock.patch.multiple(
            'zerver.models',
            ArchivedAttachment=ArchivedAttachment,
            ArchivedMessage=ArchivedMessage,
            ArchivedUserMessage=ArchivedUserMessage,
            Attachment=Attachment,
            BotConfigData=BotConfigData,
            BotStorageData=BotStorageData,
            Client=Client,
            CustomProfileField=CustomProfileField,
            CustomProfileFieldValue=CustomProfileFieldValue,
            DefaultStream=DefaultStream,
            DefaultStreamGroup=DefaultStreamGroup,
            EmailChangeStatus=EmailChangeStatus,
            Huddle=Huddle,
            Message=Message,
            MultiuseInvite=MultiuseInvite,
            MutedTopic=MutedTopic,
            PreregistrationUser=PreregistrationUser,
            PushDeviceToken=PushDeviceToken,
            Reaction=Reaction,
            Realm=Realm,
            RealmAuditLog=RealmAuditLog,
            RealmDomain=RealmDomain,
            RealmEmoji=RealmEmoji,
            RealmFilter=RealmFilter,
            Recipient=Recipient,
            ScheduledEmail=ScheduledEmail,
            ScheduledMessage=ScheduledMessage,
            Service=Service,
            Stream=Stream,
            Subscription=Subscription,
            UserActivity=UserActivity,
            UserActivityInterval=UserActivityInterval,
            UserGroup=UserGroup,
            UserGroupMembership=UserGroupMembership,
            UserHotspot=UserHotspot,
            UserMessage=UserMessage,
            UserPresence=UserPresence,
            UserProfile=UserProfile
        )
        zerver_test_helpers_patch = mock.patch.multiple(
            'zerver.lib.test_helpers',
            Client=Client,
            Message=Message,
            Subscription=Subscription,
            UserMessage=UserMessage,
            UserProfile=UserProfile,
        )

        zerver_test_classes_patch = mock.patch.multiple(
            'zerver.lib.test_classes',
            Client=Client,
            Message=Message,
            Realm=Realm,
            Recipient=Recipient,
            Stream=Stream,
            Subscription=Subscription,
            UserProfile=UserProfile,
        )

        with zerver_models_patch,\
                zerver_test_helpers_patch,\
                zerver_test_classes_patch:
            method(self, apps)
    return method_patched_with_mock
