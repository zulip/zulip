import collections
import itertools
import os
import re
import sys
import time
from collections.abc import Callable, Iterable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from typing import IO, TYPE_CHECKING, Any, TypeVar, Union, cast
from unittest import mock
from unittest.mock import patch

import boto3.session
import dns.rdtypes.ANY.TXT
import dns.resolver
import fakeldap
import ldap
import orjson
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.backends.base import SessionBase
from django.db.migrations.state import StateApps
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.http.request import QueryDict
from django.http.response import HttpResponseBase
from django.test import override_settings
from django.urls import URLResolver
from moto.core.decorator import mock_aws
from mypy_boto3_s3.service_resource import Bucket
from typing_extensions import ParamSpec, override

from zerver.actions.realm_settings import do_set_realm_user_default_setting
from zerver.actions.user_settings import do_change_user_setting
from zerver.lib import cache
from zerver.lib.avatar import avatar_url
from zerver.lib.cache import get_cache_backend
from zerver.lib.db import Params, Query, TimeTrackingCursor
from zerver.lib.integrations import WEBHOOK_INTEGRATIONS
from zerver.lib.per_request_cache import flush_per_request_caches
from zerver.lib.rate_limiter import RateLimitedIPAddr, rules
from zerver.lib.request import RequestNotes
from zerver.lib.types import AnalyticsDataUploadLevel
from zerver.lib.upload.s3 import S3UploadBackend
from zerver.models import Client, Message, RealmUserDefault, Subscription, UserMessage, UserProfile
from zerver.models.clients import clear_client_cache, get_client
from zerver.models.realms import get_realm
from zerver.models.streams import get_stream
from zerver.tornado.handlers import AsyncDjangoHandler, allocate_handler_id
from zilencer.models import RemoteZulipServer
from zproject.backends import ExternalAuthDataDict, ExternalAuthResult

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as TestHttpResponse

    # Avoid an import cycle; we only need these for type annotations.
    from zerver.lib.test_classes import MigrationsTestCase, ZulipTestCase


class MockLDAP(fakeldap.MockLDAP):
    class LDAPError(ldap.LDAPError):
        pass

    class INVALID_CREDENTIALS(ldap.INVALID_CREDENTIALS):  # noqa: N801
        pass

    class NO_SUCH_OBJECT(ldap.NO_SUCH_OBJECT):  # noqa: N801
        pass

    class ALREADY_EXISTS(ldap.ALREADY_EXISTS):  # noqa: N801
        pass


@contextmanager
def stub_event_queue_user_events(
    event_queue_return: Any, user_events_return: Any
) -> Iterator[None]:
    with (
        mock.patch("zerver.lib.events.request_event_queue", return_value=event_queue_return),
        mock.patch("zerver.lib.events.get_user_events", return_value=user_events_return),
    ):
        yield


class activate_push_notification_service(override_settings):  # noqa: N801
    """
    Activating the push notification service involves a few different settings
    that are logically related, and ordinarily set correctly in computed_settings.py
    based on the admin-configured settings.
    Having tests deal with overriding all the necessary settings every time they
    want to simulate using the push notification service would be too
    cumbersome, so we provide a convenient helper.
    Can be used as either a context manager or a decorator applied to a test method
    or class, just like original override_settings.
    """

    def __init__(
        self, zulip_services_url: str | None = None, submit_usage_statistics: bool = False
    ) -> None:
        if zulip_services_url is None:
            zulip_services_url = settings.ZULIP_SERVICES_URL
        assert zulip_services_url is not None

        # Ordinarily the ANALYTICS_DATA_UPLOAD_LEVEL setting is computed based on these
        # ZULIP_SERVICE_* configured settings; but because these settings here won't get
        # processed through computed_settings, we need to set ANALYTICS_DATA_UPLOAD_LEVEL
        # manually.
        # The logic here is:
        # (1) If the currently active ANALYTICS_DATA_UPLOAD_LEVEL is lower than what's
        #     demanded to enable push notifications, then we need to override it to
        #     this minimum level (i.e. BILLING).
        # (2) Otherwise, the test must have already somehow set up a higher level
        #     of data upload, so we should leave it alone.
        if settings.ANALYTICS_DATA_UPLOAD_LEVEL < AnalyticsDataUploadLevel.BILLING:
            analytics_data_upload_level = AnalyticsDataUploadLevel.BILLING
        else:  # nocoverage
            analytics_data_upload_level = settings.ANALYTICS_DATA_UPLOAD_LEVEL

        # Finally, the data upload level can be elevated by the submit_usage_statistics
        # argument.
        if submit_usage_statistics:
            analytics_data_upload_level = AnalyticsDataUploadLevel.ALL

        super().__init__(
            ZULIP_SERVICES_URL=zulip_services_url,
            ANALYTICS_DATA_UPLOAD_LEVEL=analytics_data_upload_level,
            ZULIP_SERVICE_PUSH_NOTIFICATIONS=True,
            ZULIP_SERVICE_SUBMIT_USAGE_STATISTICS=submit_usage_statistics,
        )


@contextmanager
def cache_tries_captured() -> Iterator[list[tuple[str, str | list[str], str | None]]]:
    cache_queries: list[tuple[str, str | list[str], str | None]] = []

    orig_get = cache.cache_get
    orig_get_many = cache.cache_get_many

    def my_cache_get(key: str, cache_name: str | None = None) -> dict[str, Any] | None:
        cache_queries.append(("get", key, cache_name))
        return orig_get(key, cache_name)

    def my_cache_get_many(keys: list[str], cache_name: str | None = None) -> dict[str, Any]:
        cache_queries.append(("getmany", keys, cache_name))
        return orig_get_many(keys, cache_name)

    with mock.patch.multiple(cache, cache_get=my_cache_get, cache_get_many=my_cache_get_many):
        yield cache_queries


@contextmanager
def simulated_empty_cache() -> Iterator[list[tuple[str, str | list[str], str | None]]]:
    cache_queries: list[tuple[str, str | list[str], str | None]] = []

    def my_cache_get(key: str, cache_name: str | None = None) -> dict[str, Any] | None:
        cache_queries.append(("get", key, cache_name))
        return None

    def my_cache_get_many(
        keys: list[str], cache_name: str | None = None
    ) -> dict[str, Any]:  # nocoverage -- simulated code doesn't use this
        cache_queries.append(("getmany", keys, cache_name))
        return {}

    with mock.patch.multiple(cache, cache_get=my_cache_get, cache_get_many=my_cache_get_many):
        yield cache_queries


@dataclass
class CapturedQuery:
    sql: str
    time: str


@contextmanager
def queries_captured(
    include_savepoints: bool = False, keep_cache_warm: bool = False
) -> Iterator[list[CapturedQuery]]:
    """
    Allow a user to capture just the queries executed during
    the with statement.
    """

    queries: list[CapturedQuery] = []

    def cursor_execute(self: TimeTrackingCursor, sql: Query, vars: Params | None = None) -> None:
        start = time.time()
        try:
            return super(TimeTrackingCursor, self).execute(sql, vars)
        finally:
            stop = time.time()
            duration = stop - start
            if include_savepoints or not isinstance(sql, str) or "SAVEPOINT" not in sql:
                queries.append(
                    CapturedQuery(
                        sql=self.mogrify(sql, vars).decode(),
                        time=f"{duration:.3f}",
                    )
                )

    def cursor_executemany(
        self: TimeTrackingCursor, sql: Query, vars_list: Iterable[Params]
    ) -> None:  # nocoverage -- doesn't actually get used in tests
        vars_list, vars_list1 = itertools.tee(vars_list)
        start = time.time()
        try:
            return super(TimeTrackingCursor, self).executemany(sql, vars_list)
        finally:
            stop = time.time()
            duration = stop - start
            queries.extend(
                CapturedQuery(
                    sql=self.mogrify(sql, vars).decode(),
                    time=f"{duration:.3f}",
                )
                for vars in vars_list1
            )

    if not keep_cache_warm:
        cache = get_cache_backend(None)
        cache.clear()
        flush_per_request_caches()
        clear_client_cache()
    with mock.patch.multiple(
        TimeTrackingCursor, execute=cursor_execute, executemany=cursor_executemany
    ):
        yield queries


@contextmanager
def stdout_suppressed() -> Iterator[IO[str]]:
    """Redirect stdout to /dev/null."""

    with open(os.devnull, "a") as devnull:
        stdout, sys.stdout = sys.stdout, devnull
        try:
            yield stdout
        finally:
            sys.stdout = stdout


def reset_email_visibility_to_everyone_in_zulip_realm() -> None:
    """
    This function is used to reset email visibility for all users and
    RealmUserDefault object in the zulip realm in development environment
    to "EMAIL_ADDRESS_VISIBILITY_EVERYONE" since the default value is
    "EMAIL_ADDRESS_VISIBILITY_ADMINS". This function is needed in
    tests that want "email" field of users to be set to their real email.
    """
    realm = get_realm("zulip")
    realm_user_default = RealmUserDefault.objects.get(realm=realm)
    do_set_realm_user_default_setting(
        realm_user_default,
        "email_address_visibility",
        RealmUserDefault.EMAIL_ADDRESS_VISIBILITY_EVERYONE,
        acting_user=None,
    )
    users = UserProfile.objects.filter(realm=realm)
    for user in users:
        do_change_user_setting(
            user,
            "email_address_visibility",
            UserProfile.EMAIL_ADDRESS_VISIBILITY_EVERYONE,
            acting_user=None,
        )


def get_test_image_file(filename: str) -> IO[bytes]:
    test_avatar_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../tests/images"))
    return open(os.path.join(test_avatar_dir, filename), "rb")


def read_test_image_file(filename: str) -> bytes:
    with get_test_image_file(filename) as img_file:
        return img_file.read()


def avatar_disk_path(
    user_profile: UserProfile, medium: bool = False, original: bool = False
) -> str:
    avatar_url_path = avatar_url(user_profile, medium)
    assert avatar_url_path is not None
    assert settings.LOCAL_UPLOADS_DIR is not None
    assert settings.LOCAL_AVATARS_DIR is not None
    avatar_disk_path = os.path.join(
        settings.LOCAL_AVATARS_DIR,
        avatar_url_path.split("/")[-2],
        avatar_url_path.split("/")[-1],
    )
    if original:
        return avatar_disk_path.replace(".png", ".original")
    return avatar_disk_path


def make_client(name: str) -> Client:
    client, _ = Client.objects.get_or_create(name=name)
    return client


def find_key_by_email(address: str) -> str | None:
    from django.core.mail import outbox

    key_regex = re.compile(r"accounts/do_confirm/([a-z0-9]{24})>")
    for message in reversed(outbox):
        if address in message.to:
            match = key_regex.search(str(message.body))
            assert match is not None
            [key] = match.groups()
            return key
    return None  # nocoverage -- in theory a test might want this case, but none do


def message_stream_count(user_profile: UserProfile) -> int:
    return UserMessage.objects.select_related("message").filter(user_profile=user_profile).count()


def most_recent_usermessage(user_profile: UserProfile) -> UserMessage:
    query = (
        UserMessage.objects.select_related("message")
        .filter(user_profile=user_profile)
        .order_by("-message")
    )
    return query[0]  # Django does LIMIT here


def most_recent_message(user_profile: UserProfile) -> Message:
    usermessage = most_recent_usermessage(user_profile)
    return usermessage.message


def get_subscription(stream_name: str, user_profile: UserProfile) -> Subscription:
    stream = get_stream(stream_name, user_profile.realm)
    recipient_id = stream.recipient_id
    assert recipient_id is not None
    return Subscription.objects.get(
        user_profile=user_profile, recipient_id=recipient_id, active=True
    )


def get_user_messages(user_profile: UserProfile) -> list[Message]:
    query = (
        UserMessage.objects.select_related("message")
        .filter(user_profile=user_profile)
        .order_by("message")
    )
    return [um.message for um in query]


class DummyHandler(AsyncDjangoHandler):
    def __init__(self) -> None:
        self.handler_id = allocate_handler_id(self)


dummy_handler = DummyHandler()


class HostRequestMock(HttpRequest):
    """A mock request object where get_host() works.  Useful for testing
    routes that use Zulip's subdomains feature"""

    # The base class HttpRequest declares GET and POST as immutable
    # QueryDict objects. The implementation of HostRequestMock
    # requires POST to be mutable, and we have some use cases that
    # modify GET, so GET and POST are both redeclared as mutable.

    GET: QueryDict  # type: ignore[assignment] # See previous comment.
    POST: QueryDict  # type: ignore[assignment] # See previous comment.

    def __init__(
        self,
        post_data: Mapping[str, Any] = {},
        user_profile: UserProfile | None = None,
        remote_server: RemoteZulipServer | None = None,
        host: str = settings.EXTERNAL_HOST,
        client_name: str | None = None,
        meta_data: dict[str, Any] | None = None,
        tornado_handler: AsyncDjangoHandler | None = None,
        path: str = "",
    ) -> None:
        self.host = host
        self.GET = QueryDict(mutable=True)
        self.method = ""

        # Convert any integer parameters passed into strings, even
        # though of course the HTTP API would do so.  Ideally, we'd
        # get rid of this abstraction entirely and just use the HTTP
        # API directly, but while it exists, we need this code
        self.POST = QueryDict(mutable=True)
        for key in post_data:
            self.POST[key] = str(post_data[key])
            self.method = "POST"

        if meta_data is None:
            self.META = {"PATH_INFO": "test"}
        else:
            self.META = meta_data
        self.path = path
        self.user = user_profile or AnonymousUser()
        self._body = orjson.dumps(post_data)
        self.content_type = ""
        self.session = SessionBase()

        RequestNotes.set_notes(
            self,
            RequestNotes(
                client_name="",
                log_data={},
                tornado_handler_id=None if tornado_handler is None else tornado_handler.handler_id,
                client=get_client(client_name) if client_name is not None else None,
                remote_server=remote_server,
            ),
        )

    @override
    def get_host(self) -> str:
        return self.host


INSTRUMENTING = os.environ.get("TEST_INSTRUMENT_URL_COVERAGE", "") == "TRUE"
INSTRUMENTED_CALLS: list[dict[str, Any]] = []

UrlFuncT = TypeVar("UrlFuncT", bound=Callable[..., HttpResponseBase])  # TODO: make more specific


def append_instrumentation_data(data: dict[str, Any]) -> None:
    INSTRUMENTED_CALLS.append(data)


def instrument_url(f: UrlFuncT) -> UrlFuncT:
    # TODO: Type this with ParamSpec to preserve the function signature.
    if not INSTRUMENTING:  # nocoverage -- option is always enabled; should we remove?
        return f
    else:

        def wrapper(
            self: "ZulipTestCase", url: str, info: object = {}, **kwargs: bool | str
        ) -> HttpResponseBase:
            start = time.time()
            result = f(self, url, info, **kwargs)
            delay = time.time() - start
            test_name = self.id()
            if "?" in url:
                url, extra_info = url.split("?", 1)
            else:
                extra_info = ""

            if isinstance(info, HostRequestMock):
                info = "<HostRequestMock>"
            elif isinstance(info, bytes):
                info = "<bytes>"
            elif isinstance(info, dict):
                info = {
                    k: "<file object>" if hasattr(v, "read") and callable(v.read) else v
                    for k, v in info.items()
                }

            append_instrumentation_data(
                dict(
                    url=url,
                    status_code=result.status_code,
                    method=f.__name__,
                    delay=delay,
                    extra_info=extra_info,
                    info=info,
                    test_name=test_name,
                    kwargs=kwargs,
                )
            )
            return result

        return cast(UrlFuncT, wrapper)  # https://github.com/python/mypy/issues/1927


def write_instrumentation_reports(full_suite: bool, include_webhooks: bool) -> None:
    if INSTRUMENTING:
        calls = INSTRUMENTED_CALLS

        from zproject.urls import urlpatterns, v1_api_and_json_patterns

        # Find our untested urls.
        pattern_cnt: dict[str, int] = collections.defaultdict(int)

        def re_strip(r: str) -> str:
            assert r.startswith(r"^")
            if r.endswith(r"$"):
                return r[1:-1]
            else:
                assert r.endswith(r"\Z")
                return r[1:-2]

        def find_patterns(patterns: list[Any], prefixes: list[str]) -> None:
            for pattern in patterns:
                find_pattern(pattern, prefixes)

        def cleanup_url(url: str) -> str:
            url = url.removeprefix("/")
            url = url.removeprefix("http://testserver/")
            url = url.removeprefix("http://zulip.testserver/")
            url = url.removeprefix("http://testserver:9080/")
            return url

        def find_pattern(pattern: Any, prefixes: list[str]) -> None:
            if isinstance(pattern, type(URLResolver)):
                return  # nocoverage -- shouldn't actually happen

            if hasattr(pattern, "url_patterns"):
                return

            canon_pattern = prefixes[0] + re_strip(pattern.pattern.regex.pattern)
            cnt = 0
            for call in calls:
                if "pattern" in call:
                    continue

                url = cleanup_url(call["url"])

                for prefix in prefixes:
                    if url.startswith(prefix):
                        match_url = url.removeprefix(prefix)
                        if pattern.resolve(match_url):
                            if call["status_code"] in [200, 204, 301, 302]:
                                cnt += 1
                            call["pattern"] = canon_pattern
            pattern_cnt[canon_pattern] += cnt

        find_patterns(urlpatterns, ["", "en/", "de/"])
        find_patterns(v1_api_and_json_patterns, ["api/v1/", "json/"])

        assert len(pattern_cnt) > 100
        untested_patterns = {p.replace("\\", "") for p in pattern_cnt if pattern_cnt[p] == 0}

        exempt_patterns = {
            # We exempt some patterns that are called via Tornado.
            "api/v1/events",
            "api/v1/events/internal",
            "api/v1/register",
            # We also exempt some development environment debugging
            # static content URLs, since the content they point to may
            # or may not exist.
            "coverage/(?P<path>.+)",
            "config-error/(?P<error_name>[^/]+)",
            "confirmation_key/",
            "node-coverage/(?P<path>.+)",
            "docs/",
            "docs/(?P<path>.+)",
            "casper/(?P<path>.+)",
            "static/(?P<path>.*)",
            "flush_caches",
            "external_content/(?P<digest>[^/]+)/(?P<received_url>[^/]+)",
            # Such endpoints are only used in certain test cases that can be skipped
            "testing/(?P<path>.+)",
            # These are SCIM2 urls overridden from django-scim2 to return Not Implemented.
            # We actually test them, but it's not being detected as a tested pattern,
            # possibly due to the use of re_path. TODO: Investigate and get them
            # recognized as tested.
            "scim/v2/",
            "scim/v2/.search",
            "scim/v2/Bulk",
            "scim/v2/Me",
            "scim/v2/ResourceTypes(?:/(?P<uuid>[^/]+))?",
            "scim/v2/Schemas(?:/(?P<uuid>[^/]+))?",
            "scim/v2/ServiceProviderConfig",
            "scim/v2/Groups(?:/(?P<uuid>[^/]+))?",
            "scim/v2/Groups/.search",
            # This endpoint only returns 500 and 404 codes, so it doesn't get picked up
            # by find_pattern above and therefore needs to be exempt.
            "self-hosted-billing/not-configured/",
            *(webhook.url for webhook in WEBHOOK_INTEGRATIONS if not include_webhooks),
        }

        untested_patterns -= exempt_patterns

        var_dir = "var"  # TODO make sure path is robust here
        fn = os.path.join(var_dir, "url_coverage.txt")
        with open(fn, "wb") as f:
            f.writelines(orjson.dumps(call, option=orjson.OPT_APPEND_NEWLINE) for call in calls)

        if full_suite:
            print(f"INFO: URL coverage report is in {fn}")

        if full_suite and len(untested_patterns):  # nocoverage -- test suite error handling
            print("\nERROR: Some URLs are untested!  Here's the list of untested URLs:")
            for untested_pattern in sorted(untested_patterns):
                print(f"   {untested_pattern}")
            sys.exit(1)


def load_subdomain_token(response: Union["TestHttpResponse", HttpResponse]) -> ExternalAuthDataDict:
    assert isinstance(response, HttpResponseRedirect)
    token = response.url.rsplit("/", 1)[1]
    data = ExternalAuthResult(
        request=mock.MagicMock(), login_token=token, delete_stored_data=False
    ).data_dict
    assert data is not None
    return data


P = ParamSpec("P")


def use_s3_backend(method: Callable[P, None]) -> Callable[P, None]:
    @mock_aws
    @override_settings(LOCAL_UPLOADS_DIR=None)
    @override_settings(LOCAL_AVATARS_DIR=None)
    @override_settings(LOCAL_FILES_DIR=None)
    def new_method(*args: P.args, **kwargs: P.kwargs) -> None:
        backend = S3UploadBackend()
        with (
            mock.patch("zerver.worker.thumbnail.upload_backend", backend),
            mock.patch("zerver.lib.upload.upload_backend", backend),
            mock.patch("zerver.views.tusd.upload_backend", backend),
        ):
            return method(*args, **kwargs)

    return new_method


def create_s3_buckets(*bucket_names: str) -> list[Bucket]:
    session = boto3.session.Session(settings.S3_KEY, settings.S3_SECRET_KEY)
    s3 = session.resource("s3")
    buckets = [s3.create_bucket(Bucket=name) for name in bucket_names]
    return buckets


TestCaseT = TypeVar("TestCaseT", bound="MigrationsTestCase")


def use_db_models(
    method: Callable[[TestCaseT, StateApps], None],
) -> Callable[[TestCaseT, StateApps], None]:  # nocoverage
    def method_patched_with_mock(self: TestCaseT, apps: StateApps) -> None:
        ArchivedAttachment = apps.get_model("zerver", "ArchivedAttachment")
        ArchivedMessage = apps.get_model("zerver", "ArchivedMessage")
        ArchivedUserMessage = apps.get_model("zerver", "ArchivedUserMessage")
        Attachment = apps.get_model("zerver", "Attachment")
        BotConfigData = apps.get_model("zerver", "BotConfigData")
        BotStorageData = apps.get_model("zerver", "BotStorageData")
        Client = apps.get_model("zerver", "Client")
        CustomProfileField = apps.get_model("zerver", "CustomProfileField")
        CustomProfileFieldValue = apps.get_model("zerver", "CustomProfileFieldValue")
        DefaultStream = apps.get_model("zerver", "DefaultStream")
        DefaultStreamGroup = apps.get_model("zerver", "DefaultStreamGroup")
        EmailChangeStatus = apps.get_model("zerver", "EmailChangeStatus")
        DirectMessageGroup = apps.get_model("zerver", "DirectMessageGroup")
        Message = apps.get_model("zerver", "Message")
        MultiuseInvite = apps.get_model("zerver", "MultiuseInvite")
        OnboardingStep = apps.get_model("zerver", "OnboardingStep")
        PreregistrationUser = apps.get_model("zerver", "PreregistrationUser")
        PushDeviceToken = apps.get_model("zerver", "PushDeviceToken")
        Reaction = apps.get_model("zerver", "Reaction")
        Realm = apps.get_model("zerver", "Realm")
        RealmAuditLog = apps.get_model("zerver", "RealmAuditLog")
        RealmDomain = apps.get_model("zerver", "RealmDomain")
        RealmEmoji = apps.get_model("zerver", "RealmEmoji")
        RealmFilter = apps.get_model("zerver", "RealmFilter")
        Recipient = apps.get_model("zerver", "Recipient")
        Recipient.PERSONAL = 1
        Recipient.STREAM = 2
        Recipient.DIRECT_MESSAGE_GROUP = 3
        ScheduledEmail = apps.get_model("zerver", "ScheduledEmail")
        ScheduledMessage = apps.get_model("zerver", "ScheduledMessage")
        Service = apps.get_model("zerver", "Service")
        Stream = apps.get_model("zerver", "Stream")
        Subscription = apps.get_model("zerver", "Subscription")
        UserActivity = apps.get_model("zerver", "UserActivity")
        UserActivityInterval = apps.get_model("zerver", "UserActivityInterval")
        UserGroup = apps.get_model("zerver", "UserGroup")
        UserGroupMembership = apps.get_model("zerver", "UserGroupMembership")
        UserMessage = apps.get_model("zerver", "UserMessage")
        UserPresence = apps.get_model("zerver", "UserPresence")
        UserProfile = apps.get_model("zerver", "UserProfile")
        UserTopic = apps.get_model("zerver", "UserTopic")

        zerver_models_patch = mock.patch.multiple(
            "zerver.models",
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
            DirectMessageGroup=DirectMessageGroup,
            Message=Message,
            MultiuseInvite=MultiuseInvite,
            UserTopic=UserTopic,
            OnboardingStep=OnboardingStep,
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
            UserMessage=UserMessage,
            UserPresence=UserPresence,
            UserProfile=UserProfile,
        )
        zerver_test_helpers_patch = mock.patch.multiple(
            "zerver.lib.test_helpers",
            Client=Client,
            Message=Message,
            Subscription=Subscription,
            UserMessage=UserMessage,
            UserProfile=UserProfile,
        )

        zerver_test_classes_patch = mock.patch.multiple(
            "zerver.lib.test_classes",
            Client=Client,
            Message=Message,
            Realm=Realm,
            Recipient=Recipient,
            Stream=Stream,
            Subscription=Subscription,
            UserProfile=UserProfile,
        )

        with zerver_models_patch, zerver_test_helpers_patch, zerver_test_classes_patch:
            method(self, apps)

    return method_patched_with_mock


def create_dummy_file(filename: str) -> str:
    filepath = os.path.join(settings.TEST_WORKER_DIR, filename)
    with open(filepath, "w") as f:
        f.write("zulip!")
    return filepath


def zulip_reaction_info() -> dict[str, str]:
    return dict(
        emoji_name="zulip",
        emoji_code="zulip",
        reaction_type="zulip_extra_emoji",
    )


@contextmanager
def mock_queue_publish(
    method_to_patch: str,
    **kwargs: object,
) -> Iterator[mock.MagicMock]:
    inner = mock.MagicMock(**kwargs)

    # This helper ensures that events published to the queues are
    # serializable as JSON; unserializable events would make RabbitMQ
    # crash in production.
    def verify_serialize(
        queue_name: str,
        event: dict[str, object],
        processor: Callable[[object], None] | None = None,
    ) -> None:
        marshalled_event = orjson.loads(orjson.dumps(event))
        assert marshalled_event == event
        inner(queue_name, event, processor)

    with mock.patch(method_to_patch, side_effect=verify_serialize):
        yield inner


@contextmanager
def ratelimit_rule(
    range_seconds: int,
    num_requests: int,
    domain: str = "api_by_user",
) -> Iterator[None]:
    """Temporarily add a rate-limiting rule to the rate limiter"""
    RateLimitedIPAddr("127.0.0.1", domain=domain).clear_history()

    domain_rules = rules.get(domain, []).copy()
    domain_rules.append((range_seconds, num_requests))
    domain_rules.sort(key=lambda x: x[0])

    with patch.dict(rules, {domain: domain_rules}), override_settings(RATE_LIMITING=True):
        yield


def consume_response(response: HttpResponseBase) -> None:
    assert response.streaming
    collections.deque(response, maxlen=0)


def dns_txt_answer(name_str: str, txt: str) -> dns.resolver.Answer:
    name = dns.name.from_text(name_str)
    rdclass = dns.rdataclass.IN
    rdtype = dns.rdatatype.TXT
    response = dns.message.make_query(
        name, rdtype, rdclass, flags=dns.flags.QR | dns.flags.RA | dns.flags.RD
    )
    response.find_rrset(dns.message.ANSWER, name, rdclass, rdtype, create=True).add(
        dns.rdtypes.ANY.TXT.TXT(rdclass, rdtype, txt)
    )
    return dns.resolver.Answer(name, rdtype, rdclass, response)
