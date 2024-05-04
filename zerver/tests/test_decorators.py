import base64
import os
import re
import uuid
from collections import defaultdict
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, Tuple, Union
from unittest import mock, skipUnless

import orjson
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.http import HttpRequest, HttpResponse
from django.utils.timezone import now as timezone_now
from typing_extensions import override

from zerver.actions.create_realm import do_create_realm
from zerver.actions.create_user import do_reactivate_user
from zerver.actions.realm_settings import do_deactivate_realm
from zerver.actions.user_settings import do_change_user_setting
from zerver.actions.users import change_user_is_active, do_deactivate_user
from zerver.decorator import (
    authenticate_internal_api,
    authenticated_json_view,
    authenticated_rest_api_view,
    authenticated_uploads_api_view,
    internal_api_view,
    process_client,
    public_json_view,
    return_success_on_head_request,
    validate_api_key,
    web_public_view,
    webhook_view,
    zulip_login_required,
    zulip_otp_required_if_logged_in,
)
from zerver.forms import OurAuthenticationForm
from zerver.lib.cache import dict_to_items_tuple, ignore_unhashable_lru_cache, items_tuple_to_dict
from zerver.lib.exceptions import (
    AccessDeniedError,
    InvalidAPIKeyError,
    InvalidAPIKeyFormatError,
    JsonableError,
    UnsupportedWebhookEventTypeError,
)
from zerver.lib.initial_password import initial_password
from zerver.lib.rate_limiter import is_local_addr
from zerver.lib.request import RequestNotes, RequestVariableMissingError
from zerver.lib.response import json_response, json_success
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import HostRequestMock, dummy_handler, queries_captured
from zerver.lib.user_agent import parse_user_agent
from zerver.lib.users import get_api_key
from zerver.lib.utils import generate_api_key, has_api_key_format
from zerver.middleware import LogRequests, parse_client
from zerver.models import Client, Realm, UserProfile
from zerver.models.realms import get_realm
from zerver.models.users import get_user

if settings.ZILENCER_ENABLED:
    from zilencer.models import RemoteZulipServer

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as TestHttpResponse


class DecoratorTestCase(ZulipTestCase):
    def test_parse_client(self) -> None:
        req = HostRequestMock()
        self.assertEqual(parse_client(req), ("Unspecified", None))

        req = HostRequestMock()
        req.META["HTTP_USER_AGENT"] = (
            "ZulipElectron/4.0.3 Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_3) AppleWebKit/537.36 (KHTML, like Gecko) Zulip/4.0.3 Chrome/66.0.3359.181 Electron/3.1.10 Safari/537.36"
        )
        self.assertEqual(parse_client(req), ("ZulipElectron", "4.0.3"))

        req = HostRequestMock()
        req.META["HTTP_USER_AGENT"] = "ZulipDesktop/0.4.4 (Mac)"
        self.assertEqual(parse_client(req), ("ZulipDesktop", "0.4.4"))

        req = HostRequestMock()
        req.META["HTTP_USER_AGENT"] = "ZulipMobile/26.22.145 (Android 10)"
        self.assertEqual(parse_client(req), ("ZulipMobile", "26.22.145"))

        req = HostRequestMock()
        req.META["HTTP_USER_AGENT"] = "ZulipMobile/26.22.145 (iOS 13.3.1)"
        self.assertEqual(parse_client(req), ("ZulipMobile", "26.22.145"))

        # TODO: This should ideally be Firefox.
        req = HostRequestMock()
        req.META["HTTP_USER_AGENT"] = (
            "Mozilla/5.0 (X11; Linux x86_64; rv:73.0) Gecko/20100101 Firefox/73.0"
        )
        self.assertEqual(parse_client(req), ("Mozilla", None))

        # TODO: This should ideally be Chrome.
        req = HostRequestMock()
        req.META["HTTP_USER_AGENT"] = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.43 Safari/537.36"
        )
        self.assertEqual(parse_client(req), ("Mozilla", None))

        # TODO: This should ideally be Mobile Safari if we had better user-agent parsing.
        req = HostRequestMock()
        req.META["HTTP_USER_AGENT"] = (
            "Mozilla/5.0 (Linux; Android 8.0.0; SM-G930F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.132 Mobile Safari/537.36"
        )
        self.assertEqual(parse_client(req), ("Mozilla", None))

        post_req_with_client = HostRequestMock()
        post_req_with_client.POST["client"] = "test_client_1"
        post_req_with_client.META["HTTP_USER_AGENT"] = "ZulipMobile/26.22.145 (iOS 13.3.1)"
        self.assertEqual(parse_client(post_req_with_client), ("test_client_1", None))

        get_req_with_client = HostRequestMock()
        get_req_with_client.GET["client"] = "test_client_2"
        get_req_with_client.META["HTTP_USER_AGENT"] = "ZulipMobile/26.22.145 (iOS 13.3.1)"
        self.assertEqual(parse_client(get_req_with_client), ("test_client_2", None))

    def test_unparsable_user_agent(self) -> None:
        request = HttpRequest()
        request.POST["param"] = "test"
        request.META["HTTP_USER_AGENT"] = "mocked should fail"
        with mock.patch(
            "zerver.middleware.parse_client", side_effect=JsonableError("message")
        ) as m, self.assertLogs(level="ERROR"):
            LogRequests(lambda request: HttpResponse()).process_request(request)
        request_notes = RequestNotes.get_notes(request)
        self.assertEqual(request_notes.client_name, "Unparsable")
        m.assert_called_once()

    def logger_output(self, output_string: str, type: str, logger: str) -> str:
        return f"{type.upper()}:zulip.zerver.{logger}:{output_string}"

    def test_webhook_view(self) -> None:
        @webhook_view("ClientName")
        def my_webhook(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
            return json_response(msg=user_profile.email)

        @webhook_view("ClientName")
        def my_webhook_raises_exception(
            request: HttpRequest, user_profile: UserProfile
        ) -> HttpResponse:
            raise Exception("raised by webhook function")

        @webhook_view("ClientName")
        def my_webhook_raises_exception_unsupported_event(
            request: HttpRequest, user_profile: UserProfile
        ) -> HttpResponse:
            raise UnsupportedWebhookEventTypeError("test_event")

        webhook_bot_email = "webhook-bot@zulip.com"
        webhook_bot_realm = get_realm("zulip")
        webhook_bot = get_user(webhook_bot_email, webhook_bot_realm)
        webhook_bot_api_key = get_api_key(webhook_bot)

        request = HostRequestMock()
        request.POST["api_key"] = "X" * 32

        with self.assertRaisesRegex(JsonableError, "Invalid API key"):
            my_webhook(request)

        # Start a valid request here
        request = HostRequestMock()
        request.POST["api_key"] = webhook_bot_api_key
        with self.assertLogs(level="WARNING") as m:
            with self.assertRaisesRegex(
                JsonableError, "Account is not associated with this subdomain"
            ):
                api_result = my_webhook(request)
        self.assertEqual(
            m.output,
            [
                "WARNING:root:User {} ({}) attempted to access API on wrong subdomain ({})".format(
                    webhook_bot_email, "zulip", ""
                )
            ],
        )

        request = HostRequestMock()
        request.POST["api_key"] = webhook_bot_api_key
        with self.assertLogs(level="WARNING") as m:
            with self.assertRaisesRegex(
                JsonableError, "Account is not associated with this subdomain"
            ):
                request.host = "acme." + settings.EXTERNAL_HOST
                api_result = my_webhook(request)
        self.assertEqual(
            m.output,
            [
                "WARNING:root:User {} ({}) attempted to access API on wrong subdomain ({})".format(
                    webhook_bot_email, "zulip", "acme"
                )
            ],
        )

        # Test when content_type is application/json and request.body
        # is valid JSON; exception raised in the webhook function
        # should be re-raised

        request = HostRequestMock()
        request.host = "zulip.testserver"
        request.POST["api_key"] = webhook_bot_api_key
        with self.assertLogs("zulip.zerver.webhooks", level="INFO") as log:
            with self.assertRaisesRegex(Exception, "raised by webhook function"):
                request._body = b"{}"
                request.content_type = "application/json"
                my_webhook_raises_exception(request)

        # Test when content_type is not application/json; exception raised
        # in the webhook function should be re-raised

        request = HostRequestMock()
        request.host = "zulip.testserver"
        request.POST["api_key"] = webhook_bot_api_key
        with self.assertLogs("zulip.zerver.webhooks", level="INFO") as log:
            with self.assertRaisesRegex(Exception, "raised by webhook function"):
                request._body = b"notjson"
                request.content_type = "text/plain"
                my_webhook_raises_exception(request)

        # Test when content_type is application/json but request.body
        # is not valid JSON; invalid JSON should be logged and the
        # exception raised in the webhook function should be re-raised
        request = HostRequestMock()
        request.host = "zulip.testserver"
        request.POST["api_key"] = webhook_bot_api_key
        with self.assertLogs("zulip.zerver.webhooks", level="ERROR") as log:
            with self.assertRaisesRegex(Exception, "raised by webhook function"):
                request._body = b"invalidjson"
                request.content_type = "application/json"
                request.META["HTTP_X_CUSTOM_HEADER"] = "custom_value"
                my_webhook_raises_exception(request)

        self.assertIn(
            self.logger_output("raised by webhook function\n", "error", "webhooks"), log.output[0]
        )

        # Test when an unsupported webhook event occurs
        request = HostRequestMock()
        request.host = "zulip.testserver"
        request.POST["api_key"] = webhook_bot_api_key
        exception_msg = (
            "The 'test_event' event isn't currently supported by the ClientName webhook; ignoring"
        )
        with self.assertLogs("zulip.zerver.webhooks.unsupported", level="ERROR") as log:
            with self.assertRaisesRegex(UnsupportedWebhookEventTypeError, exception_msg):
                request._body = b"invalidjson"
                request.content_type = "application/json"
                request.META["HTTP_X_CUSTOM_HEADER"] = "custom_value"
                my_webhook_raises_exception_unsupported_event(request)

        self.assertIn(
            self.logger_output(exception_msg, "error", "webhooks.unsupported"), log.output[0]
        )

        request = HostRequestMock()
        request.host = "zulip.testserver"
        request.POST["api_key"] = webhook_bot_api_key
        with self.settings(RATE_LIMITING=True):
            with mock.patch("zerver.decorator.rate_limit_user") as rate_limit_mock:
                api_result = orjson.loads(my_webhook(request).content).get("msg")

        # Verify rate limiting was attempted.
        self.assertTrue(rate_limit_mock.called)

        # Verify the main purpose of the decorator, which is that it passed in the
        # user_profile to my_webhook, allowing it return the correct
        # email for the bot (despite the API caller only knowing the API key).
        self.assertEqual(api_result, webhook_bot_email)

        # Now deactivate the user
        change_user_is_active(webhook_bot, False)
        request = HostRequestMock()
        request.host = "zulip.testserver"
        request.POST["api_key"] = webhook_bot_api_key
        with self.assertRaisesRegex(JsonableError, "Account is deactivated"):
            my_webhook(request)

        # Reactive the user, but deactivate their realm.
        change_user_is_active(webhook_bot, True)
        webhook_bot.realm.deactivated = True
        webhook_bot.realm.save()
        request = HostRequestMock()
        request.host = "zulip.testserver"
        request.POST["api_key"] = webhook_bot_api_key
        with self.assertRaisesRegex(JsonableError, "This organization has been deactivated"):
            my_webhook(request)


class SkipRateLimitingTest(ZulipTestCase):
    def test_authenticated_rest_api_view(self) -> None:
        @authenticated_rest_api_view(skip_rate_limiting=False)
        def my_rate_limited_view(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
            return json_success(request)  # nocoverage # mock prevents this from being called

        @authenticated_rest_api_view(skip_rate_limiting=True)
        def my_unlimited_view(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
            return json_success(request)

        request = HostRequestMock(host="zulip.testserver")
        request.META["HTTP_AUTHORIZATION"] = self.encode_email(self.example_email("hamlet"))
        request.method = "POST"
        with mock.patch("zerver.decorator.rate_limit_user") as rate_limit_mock:
            result = my_unlimited_view(request)

        self.assert_json_success(result)
        self.assertFalse(rate_limit_mock.called)

        request = HostRequestMock(host="zulip.testserver")
        request.META["HTTP_AUTHORIZATION"] = self.encode_email(self.example_email("hamlet"))
        request.method = "POST"
        with mock.patch("zerver.decorator.rate_limit_user") as rate_limit_mock:
            result = my_rate_limited_view(request)

        # Don't assert json_success, since it'll be the rate_limit mock object
        self.assertTrue(rate_limit_mock.called)

    def test_authenticated_uploads_api_view(self) -> None:
        @authenticated_uploads_api_view(skip_rate_limiting=False)
        def my_rate_limited_view(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
            return json_success(request)  # nocoverage # mock prevents this from being called

        @authenticated_uploads_api_view(skip_rate_limiting=True)
        def my_unlimited_view(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
            return json_success(request)

        request = HostRequestMock(host="zulip.testserver")
        request.method = "POST"
        request.POST["api_key"] = get_api_key(self.example_user("hamlet"))
        with mock.patch("zerver.decorator.rate_limit_user") as rate_limit_mock:
            result = my_unlimited_view(request)

        self.assert_json_success(result)
        self.assertFalse(rate_limit_mock.called)

        request = HostRequestMock(host="zulip.testserver")
        request.method = "POST"
        request.POST["api_key"] = get_api_key(self.example_user("hamlet"))
        with mock.patch("zerver.decorator.rate_limit_user") as rate_limit_mock:
            result = my_rate_limited_view(request)

        # Don't assert json_success, since it'll be the rate_limit mock object
        self.assertTrue(rate_limit_mock.called)

    def test_authenticated_json_view(self) -> None:
        def my_view(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
            return json_success(request)

        my_rate_limited_view = authenticated_json_view(my_view, skip_rate_limiting=False)
        my_unlimited_view = authenticated_json_view(my_view, skip_rate_limiting=True)

        request = HostRequestMock(host="zulip.testserver")
        request.method = "POST"
        request.user = self.example_user("hamlet")
        with mock.patch("zerver.decorator.rate_limit_user") as rate_limit_mock:
            result = my_unlimited_view(request)

        self.assert_json_success(result)
        self.assertFalse(rate_limit_mock.called)

        request = HostRequestMock(host="zulip.testserver")
        request.method = "POST"
        request.user = self.example_user("hamlet")
        with mock.patch("zerver.decorator.rate_limit_user") as rate_limit_mock:
            result = my_rate_limited_view(request)

        # Don't assert json_success, since it'll be the rate_limit mock object
        self.assertTrue(rate_limit_mock.called)


class DecoratorLoggingTestCase(ZulipTestCase):
    def test_authenticated_rest_api_view_logging(self) -> None:
        @authenticated_rest_api_view(webhook_client_name="ClientName")
        def my_webhook_raises_exception(
            request: HttpRequest, user_profile: UserProfile
        ) -> HttpResponse:
            raise Exception("raised by webhook function")

        webhook_bot_email = "webhook-bot@zulip.com"

        request = HostRequestMock()
        request.META["HTTP_AUTHORIZATION"] = self.encode_email(webhook_bot_email)
        request.method = "POST"
        request.host = "zulip.testserver"

        request._body = b"{}"
        request.content_type = "text/plain"

        with self.assertLogs("zulip.zerver.webhooks") as logger:
            with self.assertRaisesRegex(Exception, "raised by webhook function"):
                my_webhook_raises_exception(request)

        self.assertIn("raised by webhook function", logger.output[0])

    def test_authenticated_rest_api_view_logging_unsupported_event(self) -> None:
        @authenticated_rest_api_view(webhook_client_name="ClientName")
        def my_webhook_raises_exception(
            request: HttpRequest, user_profile: UserProfile
        ) -> HttpResponse:
            raise UnsupportedWebhookEventTypeError("test_event")

        webhook_bot_email = "webhook-bot@zulip.com"

        request = HostRequestMock()
        request.META["HTTP_AUTHORIZATION"] = self.encode_email(webhook_bot_email)
        request.method = "POST"
        request.host = "zulip.testserver"

        request._body = b"{}"
        request.content_type = "text/plain"

        with mock.patch(
            "zerver.decorator.webhook_unsupported_events_logger.exception"
        ) as mock_exception:
            exception_msg = "The 'test_event' event isn't currently supported by the ClientName webhook; ignoring"
            with self.assertRaisesRegex(UnsupportedWebhookEventTypeError, exception_msg):
                my_webhook_raises_exception(request)

        mock_exception.assert_called_once()
        self.assertIsInstance(mock_exception.call_args.args[0], UnsupportedWebhookEventTypeError)
        self.assertEqual(mock_exception.call_args.args[0].event_type, "test_event")
        self.assertEqual(mock_exception.call_args.args[0].msg, exception_msg)
        self.assertEqual(mock_exception.call_args.kwargs, {"extra": {"request": request}})

    def test_authenticated_rest_api_view_with_non_webhook_view(self) -> None:
        @authenticated_rest_api_view()
        def non_webhook_view_raises_exception(
            request: HttpRequest, user_profile: UserProfile
        ) -> HttpResponse:
            raise Exception("raised by a non-webhook view")

        request = HostRequestMock()
        request.META["HTTP_AUTHORIZATION"] = self.encode_email("aaron@zulip.com")
        request.method = "POST"
        request.host = "zulip.testserver"

        request._body = b"{}"
        request.content_type = "application/json"

        with mock.patch("zerver.decorator.webhook_logger.exception") as mock_exception:
            with self.assertRaisesRegex(Exception, "raised by a non-webhook view"):
                non_webhook_view_raises_exception(request)

        self.assertFalse(mock_exception.called)

    def test_authenticated_rest_api_view_errors(self) -> None:
        user_profile = self.example_user("hamlet")
        api_key = get_api_key(user_profile)
        credentials = f"{user_profile.email}:{api_key}"
        api_auth = "Digest " + base64.b64encode(credentials.encode()).decode()
        result = self.client_post("/api/v1/external/zendesk", {}, HTTP_AUTHORIZATION=api_auth)
        self.assert_json_error(result, "This endpoint requires HTTP basic authentication.")

        api_auth = "Basic " + base64.b64encode(b"foo").decode()
        result = self.client_post("/api/v1/external/zendesk", {}, HTTP_AUTHORIZATION=api_auth)
        self.assert_json_error(
            result, "Invalid authorization header for basic auth", status_code=401
        )

        result = self.client_post("/api/v1/external/zendesk", {})
        self.assert_json_error(
            result, "Missing authorization header for basic auth", status_code=401
        )


class RateLimitTestCase(ZulipTestCase):
    @staticmethod
    @public_json_view
    def ratelimited_json_view(
        req: HttpRequest, maybe_user_profile: Union[AnonymousUser, UserProfile], /
    ) -> HttpResponse:
        return HttpResponse("some value")

    @staticmethod
    @web_public_view
    def ratelimited_web_view(req: HttpRequest) -> HttpResponse:
        return HttpResponse("some value")

    def check_rate_limit_public_or_user_views(
        self,
        remote_addr: str,
        client_name: str,
        expect_rate_limit: bool,
        check_web_view: bool = False,
    ) -> None:
        META = {"REMOTE_ADDR": remote_addr, "PATH_INFO": "test"}

        request = HostRequestMock(host="zulip.testserver", client_name=client_name, meta_data=META)
        view_func = self.ratelimited_web_view if check_web_view else self.ratelimited_json_view

        with mock.patch(
            "zerver.lib.rate_limiter.RateLimitedUser"
        ) as rate_limit_user_mock, mock.patch(
            "zerver.lib.rate_limiter.RateLimitedIPAddr"
        ) as rate_limit_ip_mock:
            self.assert_in_success_response(["some value"], view_func(request))
        self.assertEqual(rate_limit_ip_mock.called, expect_rate_limit)
        self.assertFalse(rate_limit_user_mock.called)

        # We need to recreate the request, because process_client mutates client on
        # the associated RequestNotes, causing the request to be incorrectly rate limited, since
        # should_rate_limit checks the client to determine if rate limiting should be skipped.
        user = self.example_user("hamlet")
        request = HostRequestMock(
            user_profile=user, host="zulip.testserver", client_name=client_name, meta_data=META
        )
        with mock.patch(
            "zerver.lib.rate_limiter.RateLimitedUser"
        ) as rate_limit_user_mock, mock.patch(
            "zerver.lib.rate_limiter.RateLimitedIPAddr"
        ) as rate_limit_ip_mock:
            self.assert_in_success_response(["some value"], view_func(request))
        self.assertEqual(rate_limit_user_mock.called, expect_rate_limit)
        self.assertFalse(rate_limit_ip_mock.called)

    def test_internal_local_clients_skip_rate_limiting(self) -> None:
        with self.settings(RATE_LIMITING=True):
            self.check_rate_limit_public_or_user_views(
                remote_addr="127.0.0.1", client_name="internal", expect_rate_limit=False
            )

    def test_debug_clients_skip_rate_limiting(self) -> None:
        with self.settings(DEBUG_RATE_LIMITING=True, RATE_LIMITING=True):
            # Rate limiting is skipped for internal clients with an external address
            # when DEBUG_RATE_LIMITING is True.
            self.check_rate_limit_public_or_user_views(
                remote_addr="3.3.3.3", client_name="internal", expect_rate_limit=False
            )

    def test_rate_limit_setting_of_false_bypasses_rate_limiting(self) -> None:
        with self.settings(RATE_LIMITING=False):
            self.check_rate_limit_public_or_user_views(
                remote_addr="3.3.3.3", client_name="external", expect_rate_limit=False
            )

    def test_rate_limiting_happens_in_normal_case(self) -> None:
        with self.settings(RATE_LIMITING=True):
            self.check_rate_limit_public_or_user_views(
                remote_addr="3.3.3.3", client_name="external", expect_rate_limit=True
            )

    def test_rate_limiting_web_public_views(self) -> None:
        with self.settings(RATE_LIMITING=True):
            self.check_rate_limit_public_or_user_views(
                remote_addr="3.3.3.3",
                client_name="external",
                expect_rate_limit=True,
                check_web_view=True,
            )

    @skipUnless(settings.ZILENCER_ENABLED, "requires zilencer")
    def test_rate_limiting_happens_if_remote_server(self) -> None:
        user = self.example_user("hamlet")
        server_uuid = str(uuid.uuid4())
        server = RemoteZulipServer(
            uuid=server_uuid,
            api_key="magic_secret_api_key",
            hostname="demo.example.com",
            last_updated=timezone_now(),
        )
        server.save()

        with self.settings(RATE_LIMITING=True), mock.patch(
            "zilencer.auth.rate_limit_remote_server"
        ) as rate_limit_mock:
            result = self.uuid_post(
                server_uuid,
                "/api/v1/remotes/push/unregister/all",
                {"user_id": user.id},
                subdomain="",
            )
            self.assert_json_success(result)

        self.assertTrue(rate_limit_mock.called)


class DeactivatedRealmTest(ZulipTestCase):
    def test_send_deactivated_realm(self) -> None:
        """
        rest_dispatch rejects requests in a deactivated realm, both /json and api

        """
        realm = get_realm("zulip")
        do_deactivate_realm(get_realm("zulip"), acting_user=None)

        result = self.client_post(
            "/json/messages",
            {
                "type": "private",
                "content": "Test message",
                "to": self.example_email("othello"),
            },
        )
        self.assert_json_error_contains(result, "Not logged in", status_code=401)

        # Even if a logged-in session was leaked, it still wouldn't work
        realm.deactivated = False
        realm.save()
        self.login("hamlet")
        realm.deactivated = True
        realm.save()

        result = self.client_post(
            "/json/messages",
            {
                "type": "private",
                "content": "Test message",
                "to": self.example_email("othello"),
            },
        )
        self.assert_json_error_contains(
            result, "This organization has been deactivated", status_code=401
        )

        result = self.api_post(
            self.example_user("hamlet"),
            "/api/v1/messages",
            {
                "type": "private",
                "content": "Test message",
                "to": self.example_email("othello"),
            },
        )
        self.assert_json_error_contains(
            result, "This organization has been deactivated", status_code=401
        )

    def test_fetch_api_key_deactivated_realm(self) -> None:
        """
        authenticated_json_view views fail in a deactivated realm

        """
        realm = get_realm("zulip")
        user_profile = self.example_user("hamlet")
        test_password = "abcd1234"
        user_profile.set_password(test_password)

        self.login_user(user_profile)
        realm.deactivated = True
        realm.save()
        result = self.client_post("/json/fetch_api_key", {"password": test_password})
        self.assert_json_error_contains(
            result, "This organization has been deactivated", status_code=401
        )

    def test_webhook_deactivated_realm(self) -> None:
        """
        Using a webhook while in a deactivated realm fails

        """
        do_deactivate_realm(get_realm("zulip"), acting_user=None)
        user_profile = self.example_user("hamlet")
        api_key = get_api_key(user_profile)
        url = f"/api/v1/external/jira?api_key={api_key}&stream=jira_custom"
        data = self.webhook_fixture_data("jira", "created_v2")
        result = self.client_post(url, data, content_type="application/json")
        self.assert_json_error_contains(
            result, "This organization has been deactivated", status_code=401
        )


class LoginRequiredTest(ZulipTestCase):
    def test_login_required(self) -> None:
        """
        Verifies the zulip_login_required decorator blocks deactivated users.
        """
        user_profile = self.example_user("hamlet")

        # Verify fails if logged-out
        result = self.client_get("/accounts/accept_terms/")
        self.assertEqual(result.status_code, 302)

        # Verify succeeds once logged-in
        self.login_user(user_profile)
        result = self.client_get("/accounts/accept_terms/")
        self.assert_in_response("I agree to the", result)

        # Verify fails if user deactivated (with session still valid)
        change_user_is_active(user_profile, False)
        result = self.client_get("/accounts/accept_terms/")
        self.assertEqual(result.status_code, 302)

        # Verify succeeds if user reactivated
        do_reactivate_user(user_profile, acting_user=None)
        self.login_user(user_profile)
        result = self.client_get("/accounts/accept_terms/")
        self.assert_in_response("I agree to the", result)

        # Verify fails if realm deactivated
        user_profile.realm.deactivated = True
        user_profile.realm.save()
        result = self.client_get("/accounts/accept_terms/")
        self.assertEqual(result.status_code, 302)


class FetchAPIKeyTest(ZulipTestCase):
    def test_fetch_api_key_success(self) -> None:
        user = self.example_user("cordelia")
        self.login_user(user)
        result = self.client_post(
            "/json/fetch_api_key", dict(password=initial_password(user.delivery_email))
        )
        self.assert_json_success(result)

    def test_fetch_api_key_email_address_visibility(self) -> None:
        user = self.example_user("cordelia")
        do_change_user_setting(
            user,
            "email_address_visibility",
            UserProfile.EMAIL_ADDRESS_VISIBILITY_ADMINS,
            acting_user=None,
        )

        self.login_user(user)
        result = self.client_post(
            "/json/fetch_api_key", dict(password=initial_password(user.delivery_email))
        )
        self.assert_json_success(result)

    def test_fetch_api_key_wrong_password(self) -> None:
        self.login("cordelia")
        result = self.client_post("/json/fetch_api_key", dict(password="wrong_password"))
        self.assert_json_error_contains(result, "Password is incorrect")


class InactiveUserTest(ZulipTestCase):
    def test_send_deactivated_user(self) -> None:
        """
        rest_dispatch rejects requests from deactivated users, both /json and api

        """
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)
        with self.captureOnCommitCallbacks(execute=True):
            do_deactivate_user(user_profile, acting_user=None)

        result = self.client_post(
            "/json/messages",
            {
                "type": "private",
                "content": "Test message",
                "to": self.example_email("othello"),
            },
        )
        self.assert_json_error_contains(result, "Not logged in", status_code=401)

        # Even if a logged-in session was leaked, it still wouldn't work
        do_reactivate_user(user_profile, acting_user=None)
        self.login_user(user_profile)
        change_user_is_active(user_profile, False)

        result = self.client_post(
            "/json/messages",
            {
                "type": "private",
                "content": "Test message",
                "to": self.example_email("othello"),
            },
        )
        self.assert_json_error_contains(result, "Account is deactivated", status_code=401)

        result = self.api_post(
            self.example_user("hamlet"),
            "/api/v1/messages",
            {
                "type": "private",
                "content": "Test message",
                "to": self.example_email("othello"),
            },
        )
        self.assert_json_error_contains(result, "Account is deactivated", status_code=401)

    def test_fetch_api_key_deactivated_user(self) -> None:
        """
        authenticated_json_view views fail with a deactivated user

        """
        user_profile = self.example_user("hamlet")
        email = user_profile.delivery_email
        test_password = "abcd1234"
        user_profile.set_password(test_password)
        user_profile.save()

        self.login_by_email(email, password=test_password)
        change_user_is_active(user_profile, False)

        result = self.client_post("/json/fetch_api_key", {"password": test_password})
        self.assert_json_error_contains(result, "Account is deactivated", status_code=401)

    def test_login_deactivated_user(self) -> None:
        """
        logging in fails with an inactive user

        """
        user_profile = self.example_user("hamlet")
        do_deactivate_user(user_profile, acting_user=None)

        result = self.login_with_return(user_profile.delivery_email)
        self.assert_in_response(
            f"Your account {user_profile.delivery_email} has been deactivated.", result
        )

    def test_login_deactivated_mirror_dummy(self) -> None:
        """
        logging in fails with an inactive user

        """
        user_profile = self.example_user("hamlet")
        user_profile.is_mirror_dummy = True
        user_profile.save()

        password = initial_password(user_profile.delivery_email)
        request = mock.MagicMock()
        request.get_host.return_value = "zulip.testserver"

        payload = dict(
            username=user_profile.delivery_email,
            password=password,
        )

        # Test a mirror-dummy active user.
        form = OurAuthenticationForm(request, payload)
        with self.settings(AUTHENTICATION_BACKENDS=("zproject.backends.EmailAuthBackend",)):
            self.assertTrue(form.is_valid())

        # Test a mirror-dummy deactivated user.
        do_deactivate_user(user_profile, acting_user=None)
        user_profile.save()

        form = OurAuthenticationForm(request, payload)
        with self.settings(AUTHENTICATION_BACKENDS=("zproject.backends.EmailAuthBackend",)):
            self.assertFalse(form.is_valid())
            self.assertIn("Please enter a correct email", str(form.errors))

        # Test a non-mirror-dummy deactivated user.
        user_profile.is_mirror_dummy = False
        user_profile.save()

        form = OurAuthenticationForm(request, payload)
        with self.settings(AUTHENTICATION_BACKENDS=("zproject.backends.EmailAuthBackend",)):
            self.assertFalse(form.is_valid())
            self.assertIn(
                f"Your account {user_profile.delivery_email} has been deactivated",
                str(form.errors),
            )

    def test_webhook_deactivated_user(self) -> None:
        """
        Deactivated users can't use webhooks

        """
        user_profile = self.example_user("hamlet")
        do_deactivate_user(user_profile, acting_user=None)

        api_key = get_api_key(user_profile)
        url = f"/api/v1/external/jira?api_key={api_key}&stream=jira_custom"
        data = self.webhook_fixture_data("jira", "created_v2")
        result = self.client_post(url, data, content_type="application/json")
        self.assert_json_error_contains(result, "Account is deactivated", status_code=401)


class TestIncomingWebhookBot(ZulipTestCase):
    def test_webhook_bot_permissions(self) -> None:
        webhook_bot = self.example_user("webhook_bot")
        othello = self.example_user("othello")
        payload = dict(
            type="private",
            content="Test message",
            to=orjson.dumps([othello.email]).decode(),
        )

        result = self.api_post(webhook_bot, "/api/v1/messages", payload)
        self.assert_json_success(result)
        post_params = {"anchor": 1, "num_before": 1, "num_after": 1}
        result = self.api_get(webhook_bot, "/api/v1/messages", dict(post_params))
        self.assert_json_error(
            result, "This API is not available to incoming webhook bots.", status_code=401
        )


class TestValidateApiKey(ZulipTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        zulip_realm = get_realm("zulip")
        self.webhook_bot = get_user("webhook-bot@zulip.com", zulip_realm)
        self.default_bot = get_user("default-bot@zulip.com", zulip_realm)

    def test_has_api_key_format(self) -> None:
        self.assertFalse(has_api_key_format("TooShort"))
        # Has an invalid character:
        self.assertFalse(has_api_key_format("32LONGXXXXXXXXXXXXXXXXXXXXXXXXX-"))
        # Too long:
        self.assertFalse(has_api_key_format("33LONGXXXXXXXXXXXXXXXXXXXXXXXXXXX"))

        self.assertTrue(has_api_key_format("VIzRVw2CspUOnEm9Yu5vQiQtJNkvETkp"))
        for i in range(10):
            self.assertTrue(has_api_key_format(generate_api_key()))

    def test_validate_api_key_if_profile_does_not_exist(self) -> None:
        with self.assertRaises(JsonableError):
            validate_api_key(
                HostRequestMock(), "email@doesnotexist.com", "VIzRVw2CspUOnEm9Yu5vQiQtJNkvETkp"
            )

    def test_validate_api_key_if_api_key_does_not_match_profile_api_key(self) -> None:
        with self.assertRaises(InvalidAPIKeyFormatError):
            validate_api_key(HostRequestMock(), self.webhook_bot.email, "not_32_length")

        with self.assertRaises(InvalidAPIKeyError):
            # We use default_bot's key but webhook_bot's email address to test
            # the logic when an API key is passed and it doesn't belong to the
            # user whose email address has been provided.
            api_key = get_api_key(self.default_bot)
            validate_api_key(HostRequestMock(), self.webhook_bot.email, api_key)

    def test_validate_api_key_if_profile_is_not_active(self) -> None:
        change_user_is_active(self.default_bot, False)
        with self.assertRaises(JsonableError):
            api_key = get_api_key(self.default_bot)
            validate_api_key(HostRequestMock(), self.default_bot.email, api_key)
        change_user_is_active(self.default_bot, True)

    def test_validate_api_key_if_profile_is_incoming_webhook_and_is_webhook_is_unset(self) -> None:
        with self.assertRaises(JsonableError), self.assertLogs(level="WARNING") as root_warn_log:
            api_key = get_api_key(self.webhook_bot)
            validate_api_key(HostRequestMock(), self.webhook_bot.email, api_key)
        self.assertEqual(
            root_warn_log.output,
            [
                "WARNING:root:User webhook-bot@zulip.com (zulip) attempted to access API on wrong subdomain ()"
            ],
        )

    def test_validate_api_key_if_profile_is_incoming_webhook_and_is_webhook_is_set(self) -> None:
        api_key = get_api_key(self.webhook_bot)
        profile = validate_api_key(
            HostRequestMock(host="zulip.testserver"),
            self.webhook_bot.email,
            api_key,
            allow_webhook_access=True,
        )
        self.assertEqual(profile.id, self.webhook_bot.id)

    def test_validate_api_key_if_email_is_case_insensitive(self) -> None:
        api_key = get_api_key(self.default_bot)
        profile = validate_api_key(
            HostRequestMock(host="zulip.testserver"), self.default_bot.email.upper(), api_key
        )
        self.assertEqual(profile.id, self.default_bot.id)

    def test_valid_api_key_if_user_is_on_wrong_subdomain(self) -> None:
        with self.settings(RUNNING_INSIDE_TORNADO=False):
            api_key = get_api_key(self.default_bot)
            with self.assertLogs(level="WARNING") as m:
                with self.assertRaisesRegex(
                    JsonableError, "Account is not associated with this subdomain"
                ):
                    validate_api_key(
                        HostRequestMock(host=settings.EXTERNAL_HOST),
                        self.default_bot.email,
                        api_key,
                    )
            self.assertEqual(
                m.output,
                [
                    "WARNING:root:User {} ({}) attempted to access API on wrong subdomain ({})".format(
                        self.default_bot.email, "zulip", ""
                    )
                ],
            )

            with self.assertLogs(level="WARNING") as m:
                with self.assertRaisesRegex(
                    JsonableError, "Account is not associated with this subdomain"
                ):
                    validate_api_key(
                        HostRequestMock(host="acme." + settings.EXTERNAL_HOST),
                        self.default_bot.email,
                        api_key,
                    )
            self.assertEqual(
                m.output,
                [
                    "WARNING:root:User {} ({}) attempted to access API on wrong subdomain ({})".format(
                        self.default_bot.email, "zulip", "acme"
                    )
                ],
            )


class TestInternalNotifyView(ZulipTestCase):
    BORING_RESULT = "boring"

    def internal_notify(self, is_tornado: bool, req: HttpRequest) -> HttpResponse:
        boring_view = lambda req: json_response(msg=self.BORING_RESULT)
        return internal_api_view(is_tornado)(boring_view)(req)

    def test_valid_internal_requests(self) -> None:
        secret = "random"
        request = HostRequestMock(
            post_data=dict(secret=secret),
            meta_data=dict(REMOTE_ADDR="127.0.0.1"),
        )

        with self.settings(SHARED_SECRET=secret):
            self.assertTrue(authenticate_internal_api(request))
            self.assertEqual(
                orjson.loads(self.internal_notify(False, request).content).get("msg"),
                self.BORING_RESULT,
            )
            self.assertEqual(RequestNotes.get_notes(request).requester_for_logs, "internal")

            with self.assertRaises(RuntimeError):
                self.internal_notify(True, request)

        request = HostRequestMock(
            post_data=dict(secret=secret),
            meta_data=dict(REMOTE_ADDR="127.0.0.1"),
            tornado_handler=dummy_handler,
        )
        with self.settings(SHARED_SECRET=secret):
            self.assertTrue(authenticate_internal_api(request))
            self.assertEqual(
                orjson.loads(self.internal_notify(True, request).content).get("msg"),
                self.BORING_RESULT,
            )
            self.assertEqual(RequestNotes.get_notes(request).requester_for_logs, "internal")

            with self.assertRaises(RuntimeError):
                self.internal_notify(False, request)

    def test_internal_requests_with_broken_secret(self) -> None:
        request = HostRequestMock(
            post_data=dict(data="something"),
            meta_data=dict(REMOTE_ADDR="127.0.0.1"),
        )

        with self.settings(SHARED_SECRET="random"):
            with self.assertRaises(RequestVariableMissingError) as context:
                self.internal_notify(True, request)
            self.assertEqual(context.exception.http_status_code, 400)

        with self.settings(SHARED_SECRET=None):
            with self.assertRaises(RequestVariableMissingError) as context:
                self.internal_notify(True, request)
            self.assertEqual(context.exception.http_status_code, 400)

        secret = "random"
        request = HostRequestMock(
            post_data=dict(secret=secret),
            meta_data=dict(REMOTE_ADDR="127.0.0.1"),
        )

        with self.settings(SHARED_SECRET="broken"):
            self.assertFalse(authenticate_internal_api(request))
            with self.assertRaises(AccessDeniedError) as access_denied_error:
                self.internal_notify(True, request)
            self.assertEqual(access_denied_error.exception.http_status_code, 403)

    def test_external_requests(self) -> None:
        secret = "random"
        request = HostRequestMock(
            post_data=dict(secret=secret),
            meta_data=dict(REMOTE_ADDR="3.3.3.3"),
        )

        with self.settings(SHARED_SECRET=secret):
            self.assertFalse(authenticate_internal_api(request))
            with self.assertRaises(AccessDeniedError) as context:
                self.internal_notify(True, request)
            self.assertEqual(context.exception.http_status_code, 403)

    def test_is_local_address(self) -> None:
        self.assertTrue(is_local_addr("127.0.0.1"))
        self.assertTrue(is_local_addr("::1"))
        self.assertFalse(is_local_addr("42.43.44.45"))


class TestHumanUsersOnlyDecorator(ZulipTestCase):
    def test_human_only_endpoints(self) -> None:
        default_bot = self.example_user("default_bot")

        post_endpoints = [
            "/api/v1/users/me/apns_device_token",
            "/api/v1/users/me/android_gcm_reg_id",
            "/api/v1/users/me/onboarding_steps",
            "/api/v1/users/me/presence",
            "/api/v1/users/me/tutorial_status",
        ]
        for endpoint in post_endpoints:
            result = self.api_post(default_bot, endpoint)
            self.assert_json_error(result, "This endpoint does not accept bot requests.")

        patch_endpoints = [
            "/api/v1/settings",
            "/api/v1/settings/display",
            "/api/v1/settings/notifications",
            "/api/v1/users/me/profile_data",
        ]
        for endpoint in patch_endpoints:
            result = self.api_patch(default_bot, endpoint)
            self.assert_json_error(result, "This endpoint does not accept bot requests.")

        delete_endpoints = [
            "/api/v1/users/me/apns_device_token",
            "/api/v1/users/me/android_gcm_reg_id",
        ]
        for endpoint in delete_endpoints:
            result = self.api_delete(default_bot, endpoint)
            self.assert_json_error(result, "This endpoint does not accept bot requests.")


class TestAuthenticatedRequirePostDecorator(ZulipTestCase):
    def test_authenticated_html_post_view_with_get_request(self) -> None:
        self.login("hamlet")
        with self.assertLogs(level="WARNING") as mock_warning:
            result = self.client_get(r"/accounts/register/", {"stream": "Verona"})
            self.assertEqual(result.status_code, 405)
            self.assertEqual(
                mock_warning.output, ["WARNING:root:Method Not Allowed (GET): /accounts/register/"]
            )

        with self.assertLogs(level="WARNING") as mock_warning:
            result = self.client_get(r"/accounts/logout/", {"stream": "Verona"})
            self.assertEqual(result.status_code, 405)
            self.assertEqual(
                mock_warning.output, ["WARNING:root:Method Not Allowed (GET): /accounts/logout/"]
            )

    def test_authenticated_json_post_view_with_get_request(self) -> None:
        self.login("hamlet")
        with self.assertLogs(level="WARNING") as mock_warning:
            result = self.client_get(r"/api/v1/dev_fetch_api_key", {"stream": "Verona"})
            self.assertEqual(result.status_code, 405)
            self.assertEqual(
                mock_warning.output,
                ["WARNING:root:Method Not Allowed (GET): /api/v1/dev_fetch_api_key"],
            )


class TestAuthenticatedJsonViewDecorator(ZulipTestCase):
    def test_authenticated_json_view_if_user_not_logged_in(self) -> None:
        user = self.example_user("hamlet")
        self.assert_json_error_contains(
            self._do_test(user.delivery_email),
            "Not logged in: API authentication or user session required",
            status_code=401,
        )

    def test_authenticated_json_view_if_subdomain_is_invalid(self) -> None:
        user = self.example_user("hamlet")
        email = user.delivery_email
        self.login_user(user)

        with self.assertLogs(level="WARNING") as m, mock.patch(
            "zerver.decorator.get_subdomain", return_value=""
        ):
            self.assert_json_error_contains(
                self._do_test(email), "Account is not associated with this subdomain"
            )
        self.assertEqual(
            m.output,
            [
                "WARNING:root:User {} ({}) attempted to access API on wrong subdomain ({})".format(
                    email, "zulip", ""
                )
            ],
        )

        with self.assertLogs(level="WARNING") as m, mock.patch(
            "zerver.decorator.get_subdomain", return_value="acme"
        ):
            self.assert_json_error_contains(
                self._do_test(email), "Account is not associated with this subdomain"
            )
        self.assertEqual(
            m.output,
            [
                "WARNING:root:User {} ({}) attempted to access API on wrong subdomain ({})".format(
                    email, "zulip", "acme"
                )
            ],
        )

    def test_authenticated_json_view_if_user_is_incoming_webhook(self) -> None:
        bot = self.example_user("webhook_bot")
        bot.set_password("test")
        bot.save()
        self.login_by_email(bot.email, password="test")
        self.assert_json_error_contains(
            self._do_test(bot.delivery_email), "Webhook bots can only access webhooks"
        )

    def test_authenticated_json_view_if_user_is_not_active(self) -> None:
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)
        # we deactivate user manually because do_deactivate_user removes user session
        change_user_is_active(user_profile, False)
        self.assert_json_error_contains(
            self._do_test(user_profile.delivery_email), "Account is deactivated", status_code=401
        )

    def test_authenticated_json_view_if_user_realm_is_deactivated(self) -> None:
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)
        # we deactivate user's realm manually because do_deactivate_user removes user session
        user_profile.realm.deactivated = True
        user_profile.realm.save()
        self.assert_json_error_contains(
            self._do_test(user_profile.delivery_email),
            "This organization has been deactivated",
            status_code=401,
        )

    def _do_test(self, user_email: str) -> "TestHttpResponse":
        data = {"password": initial_password(user_email)}
        return self.client_post(r"/accounts/webathena_kerberos_login/", data)


class TestPublicJsonViewDecorator(ZulipTestCase):
    def test_access_public_json_view_when_logged_in(self) -> None:
        hamlet = self.example_user("hamlet")

        @public_json_view
        def public_view(
            request: HttpRequest, maybe_user_profile: Union[UserProfile, AnonymousUser]
        ) -> HttpResponse:
            self.assertEqual(maybe_user_profile, hamlet)
            return json_success(request)

        result = public_view(HostRequestMock(host="zulip.testserver", user_profile=hamlet))
        self.assert_json_success(result)


class TestZulipLoginRequiredDecorator(ZulipTestCase):
    def test_zulip_login_required_if_subdomain_is_invalid(self) -> None:
        self.login("hamlet")

        with mock.patch("zerver.decorator.get_subdomain", return_value="zulip"):
            result = self.client_get("/accounts/accept_terms/")
            self.assertEqual(result.status_code, 200)

        with mock.patch("zerver.decorator.get_subdomain", return_value=""):
            result = self.client_get("/accounts/accept_terms/")
            self.assertEqual(result.status_code, 302)

        with mock.patch("zerver.decorator.get_subdomain", return_value="acme"):
            result = self.client_get("/accounts/accept_terms/")
            self.assertEqual(result.status_code, 302)

    def test_2fa_failure(self) -> None:
        @zulip_login_required
        def test_view(request: HttpRequest) -> HttpResponse:
            return HttpResponse("Success")

        meta_data = {
            "SERVER_NAME": "localhost",
            "SERVER_PORT": 80,
            "PATH_INFO": "",
        }
        user = hamlet = self.example_user("hamlet")
        self.login_user(hamlet)
        request = HostRequestMock(
            client_name="", user_profile=user, meta_data=meta_data, host="zulip.testserver"
        )
        request.session = self.client.session

        with mock.patch("zerver.lib.users.is_verified", lambda _: False):
            response = test_view(request)
            self.assertEqual(response.content.decode(), "Success")

        with self.settings(TWO_FACTOR_AUTHENTICATION_ENABLED=True):
            user = hamlet = self.example_user("hamlet")
            self.login_user(hamlet)
            request = HostRequestMock(
                client_name="", user_profile=user, meta_data=meta_data, host="zulip.testserver"
            )
            request.session = self.client.session
            assert type(request.user) is UserProfile
            self.create_default_device(request.user)

            with mock.patch("zerver.lib.users.is_verified", lambda _: False):
                response = test_view(request)

            self.assertEqual(response.status_code, 302)

            response_url = response["Location"].split("?")[0]
            self.assertEqual(response_url, settings.HOME_NOT_LOGGED_IN)

    def test_2fa_success(self) -> None:
        @zulip_login_required
        def test_view(request: HttpRequest) -> HttpResponse:
            return HttpResponse("Success")

        with self.settings(TWO_FACTOR_AUTHENTICATION_ENABLED=True):
            meta_data = {
                "SERVER_NAME": "localhost",
                "SERVER_PORT": 80,
                "PATH_INFO": "",
            }
            user = hamlet = self.example_user("hamlet")
            self.login_user(hamlet)
            request = HostRequestMock(
                client_name="", user_profile=user, meta_data=meta_data, host="zulip.testserver"
            )
            request.session = self.client.session
            assert type(request.user) is UserProfile
            self.create_default_device(request.user)

            with mock.patch("zerver.lib.users.is_verified", lambda _: True):
                response = test_view(request)
                self.assertEqual(response.content.decode(), "Success")

    def test_otp_not_authenticated(self) -> None:
        @zulip_otp_required_if_logged_in()
        def test_view(request: HttpRequest) -> HttpResponse:
            return HttpResponse("Success")

        with self.settings(TWO_FACTOR_AUTHENTICATION_ENABLED=True):
            request = HostRequestMock()
            response = test_view(request)
            self.assertEqual(response.content.decode(), "Success")


class TestRequireDecorators(ZulipTestCase):
    def test_require_server_admin_decorator(self) -> None:
        realm_owner = self.example_user("desdemona")
        self.login_user(realm_owner)

        result = self.client_get("/activity")
        self.assertEqual(result.status_code, 302)

        server_admin = self.example_user("iago")
        self.login_user(server_admin)
        self.assertEqual(server_admin.is_staff, True)

        result = self.client_get("/activity")
        self.assertEqual(result.status_code, 200)

    def test_require_non_guest_user_decorator(self) -> None:
        guest_user = self.example_user("polonius")
        self.login_user(guest_user)
        result = self.common_subscribe_to_streams(guest_user, ["Denmark"], allow_fail=True)
        self.assert_json_error(result, "Not allowed for guest users")

        outgoing_webhook_bot = self.example_user("outgoing_webhook_bot")
        result = self.api_get(outgoing_webhook_bot, "/api/v1/bots")
        self.assert_json_error(result, "This endpoint does not accept bot requests.")

        guest_user = self.example_user("polonius")
        self.login_user(guest_user)
        result = self.client_get("/json/bots")
        self.assert_json_error(result, "Not allowed for guest users")


class ReturnSuccessOnHeadRequestDecorator(ZulipTestCase):
    def test_returns_200_if_request_method_is_head(self) -> None:
        class HeadRequest(HostRequestMock):
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                super().__init__(*args, **kwargs)
                self.method = "HEAD"

        request = HeadRequest()

        @return_success_on_head_request
        def test_function(request: HttpRequest) -> HttpResponse:
            return json_response(msg="from_test_function")  # nocoverage. isn't meant to be called

        response = test_function(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"")

    def test_returns_normal_response_if_request_method_is_not_head(self) -> None:
        class HeadRequest(HostRequestMock):
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                super().__init__(*args, **kwargs)
                self.method = "POST"

        request = HeadRequest()

        @return_success_on_head_request
        def test_function(request: HttpRequest) -> HttpResponse:
            return json_response(msg="from_test_function")

        response = test_function(request)
        self.assertEqual(orjson.loads(response.content).get("msg"), "from_test_function")


class RestAPITest(ZulipTestCase):
    def test_method_not_allowed(self) -> None:
        self.login("hamlet")
        result = self.client_patch("/json/users")
        self.assertEqual(result.status_code, 405)
        self.assert_in_response("Method Not Allowed", result)

        with self.settings(ZILENCER_ENABLED=True):
            result = self.client_patch("/api/v1/remotes/push/register")
            self.assertEqual(result.status_code, 405)
            self.assert_in_response("Method Not Allowed", result)

    def test_options_method(self) -> None:
        self.login("hamlet")
        result = self.client_options("/json/users")
        self.assertEqual(result.status_code, 204)
        self.assertEqual(str(result["Allow"]), "GET, HEAD, POST")

        result = self.client_options("/json/streams/15")
        self.assertEqual(result.status_code, 204)
        self.assertEqual(str(result["Allow"]), "DELETE, GET, HEAD, PATCH")

    def test_http_accept_redirect(self) -> None:
        result = self.client_get("/json/users", HTTP_ACCEPT="text/html")
        self.assertEqual(result.status_code, 302)
        self.assertTrue(result["Location"].endswith("/login/?next=%2Fjson%2Fusers"))


class TestUserAgentParsing(ZulipTestCase):
    def test_user_agent_parsing(self) -> None:
        """Test for our user agent parsing logic, using a large data set."""
        user_agents_parsed: Dict[str, int] = defaultdict(int)
        user_agents_path = os.path.join(
            settings.DEPLOY_ROOT, "zerver/tests/fixtures/user_agents_unique"
        )
        with open(user_agents_path) as f:
            for line in f:
                line = line.strip()
                match = re.match(r'^(?P<count>[0-9]+) "(?P<user_agent>.*)"$', line)
                assert match is not None
                groupdict = match.groupdict()
                count = groupdict["count"]
                user_agent = groupdict["user_agent"]
                ret = parse_user_agent(user_agent)
                user_agents_parsed[ret["name"]] += int(count)


class TestIgnoreUnhashableLRUCache(ZulipTestCase):
    def test_cache_hit(self) -> None:
        @ignore_unhashable_lru_cache()
        def f(arg: Any) -> Any:
            return arg

        # Check hashable argument.
        result = f(1)
        info = f.cache_info()
        # First one should be a miss.
        self.assertEqual(info.hits, 0)
        self.assertEqual(info.misses, 1)
        self.assertEqual(info.currsize, 1)
        self.assertEqual(result, 1)

        result = f(1)
        info = f.cache_info()
        # Second one should be a hit.
        self.assertEqual(info.hits, 1)
        self.assertEqual(info.misses, 1)
        self.assertEqual(info.currsize, 1)
        self.assertEqual(result, 1)

        # Check unhashable argument.
        result = f({1: 2})
        info = f.cache_info()
        # Cache should not be used.
        self.assertEqual(info.hits, 1)
        self.assertEqual(info.misses, 1)
        self.assertEqual(info.currsize, 1)
        self.assertEqual(result, {1: 2})

        # Clear cache.
        f.cache_clear()
        info = f.cache_info()
        self.assertEqual(info.hits, 0)
        self.assertEqual(info.misses, 0)
        self.assertEqual(info.currsize, 0)

    def test_cache_hit_dict_args(self) -> None:
        @ignore_unhashable_lru_cache()
        @items_tuple_to_dict
        def g(arg: Any) -> Any:
            return arg

        # Not used as a decorator on the definition to allow calling
        # cache_info and cache_clear
        f = dict_to_items_tuple(g)

        # Check hashable argument.
        result = f(1)
        info = g.cache_info()
        # First one should be a miss.
        self.assertEqual(info.hits, 0)
        self.assertEqual(info.misses, 1)
        self.assertEqual(info.currsize, 1)
        self.assertEqual(result, 1)

        result = f(1)
        info = g.cache_info()
        # Second one should be a hit.
        self.assertEqual(info.hits, 1)
        self.assertEqual(info.misses, 1)
        self.assertEqual(info.currsize, 1)
        self.assertEqual(result, 1)

        # Check dict argument.
        result = f({1: 2})
        info = g.cache_info()
        # First one is a miss
        self.assertEqual(info.hits, 1)
        self.assertEqual(info.misses, 2)
        self.assertEqual(info.currsize, 2)
        self.assertEqual(result, {1: 2})

        result = f({1: 2})
        info = g.cache_info()
        # Second one should be a hit.
        self.assertEqual(info.hits, 2)
        self.assertEqual(info.misses, 2)
        self.assertEqual(info.currsize, 2)
        self.assertEqual(result, {1: 2})

        # Clear cache.
        g.cache_clear()
        info = g.cache_info()
        self.assertEqual(info.hits, 0)
        self.assertEqual(info.misses, 0)
        self.assertEqual(info.currsize, 0)


class TestRequestNotes(ZulipTestCase):
    def test_request_notes_realm(self) -> None:
        """
        This test verifies that .realm gets set correctly on the request notes
        depending on the subdomain.
        """

        def mock_home(expected_realm: Optional[Realm]) -> Callable[[HttpRequest], HttpResponse]:
            def inner(request: HttpRequest) -> HttpResponse:
                self.assertEqual(RequestNotes.get_notes(request).realm, expected_realm)
                return HttpResponse()

            return inner

        zulip_realm = get_realm("zulip")

        # We don't need to test if user is logged in here, so we patch zulip_login_required.
        with mock.patch("zerver.views.home.zulip_login_required", lambda f: mock_home(zulip_realm)):
            result = self.client_get("/", subdomain="zulip")
            self.assertEqual(result.status_code, 200)

        # When a request is made to the root subdomain and there is no realm on it,
        # no realm can be set on the request notes.
        with mock.patch("zerver.views.home.zulip_login_required", lambda f: mock_home(None)):
            result = self.client_get("/", subdomain="")
            self.assertEqual(result.status_code, 404)

        root_subdomain_realm = do_create_realm("", "Root Domain")
        # Now test that that realm does get set, if it exists, for requests
        # to the root subdomain.
        with mock.patch(
            "zerver.views.home.zulip_login_required", lambda f: mock_home(root_subdomain_realm)
        ):
            result = self.client_get("/", subdomain="")
            self.assertEqual(result.status_code, 200)

        # Only the root subdomain allows requests to it without having a realm.
        # Requests to non-root subdomains get stopped by the middleware and
        # an error page is returned before the request hits the view.
        with mock.patch("zerver.views.home.zulip_login_required") as mock_home_real:
            result = self.client_get("/", subdomain="invalid")
            self.assertEqual(result.status_code, 404)
            self.assert_in_response(
                "There is no Zulip organization hosted at this subdomain.", result
            )
            mock_home_real.assert_not_called()


class ClientTestCase(ZulipTestCase):
    def test_process_client(self) -> None:
        def request_user_agent(user_agent: str) -> Tuple[Client, str]:
            request = HttpRequest()
            request.META["HTTP_USER_AGENT"] = user_agent
            LogRequests(lambda request: HttpResponse()).process_request(request)
            process_client(request)
            notes = RequestNotes.get_notes(request)
            assert notes.client is not None
            assert notes.client_name is not None
            return notes.client, notes.client_name

        self.assertEqual(Client.objects.filter(name="ZulipThingy").count(), 0)
        with queries_captured(keep_cache_warm=True) as queries:
            client, client_name = request_user_agent("ZulipThingy/1.0.0")
        self.assertEqual(client.name, "ZulipThingy")
        self.assertEqual(client_name, "ZulipThingy")
        self.assertEqual(Client.objects.filter(name="ZulipThingy").count(), 1)
        self.assert_length(queries, 2)

        # Ensure our in-memory cache prevents another database hit
        with queries_captured(keep_cache_warm=True) as queries:
            client, client_name = request_user_agent(
                "ZulipThingy/1.0.0",
            )
        self.assertEqual(client.name, "ZulipThingy")
        self.assertEqual(client_name, "ZulipThingy")
        self.assert_length(queries, 0)

        # This operates on the extracted value, so different ZulipThingy versions don't cause another DB query
        with queries_captured(keep_cache_warm=True) as queries:
            client, client_name = request_user_agent(
                "ZulipThingy/2.0.0",
            )
        self.assertEqual(client.name, "ZulipThingy")
        self.assertEqual(client_name, "ZulipThingy")
        self.assert_length(queries, 0)

        # If we clear the memory cache we see a database query but get
        # the same client-id back.
        with queries_captured(keep_cache_warm=False) as queries:
            fresh_client, client_name = request_user_agent(
                "ZulipThingy/2.0.0",
            )
        self.assertEqual(fresh_client.name, "ZulipThingy")
        self.assertEqual(client, fresh_client)
        self.assert_length(queries, 1)

        # Ensure that long parsed user-agents (longer than 30 characters) work
        with queries_captured(keep_cache_warm=True) as queries:
            client, client_name = request_user_agent(
                "very-long-name-goes-here-and-somewhere-else (client@example.com)"
            )
        self.assertEqual(client.name, "very-long-name-goes-here-and-s")
        # client_name has the full name still, though
        self.assertEqual(client_name, "very-long-name-goes-here-and-somewhere-else")
        self.assert_length(queries, 2)

        # Longer than that uses the same in-memory cache key, so no database queries
        with queries_captured(keep_cache_warm=True) as queries:
            client, client_name = request_user_agent(
                "very-long-name-goes-here-and-still-works (client@example.com)"
            )
        self.assertIsNotNone(client)
        self.assertEqual(client.name, "very-long-name-goes-here-and-s")
        # client_name has the full name still, though
        self.assertEqual(client_name, "very-long-name-goes-here-and-still-works")
        self.assert_length(queries, 0)
