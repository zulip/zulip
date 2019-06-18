# -*- coding: utf-8 -*-
import json
import httpretty
from types import SimpleNamespace
from mock import MagicMock, patch
from typing import Dict, List

from django.http import HttpRequest

from zerver.decorator import api_key_only_webhook_view
from zerver.lib.bot_config import ConfigError
from zerver.lib.exceptions import InvalidJSONError, JsonableError
from zerver.lib.test_classes import ZulipTestCase, WebhookTestCase
from zerver.lib.webhooks.common import \
    validate_extract_webhook_http_header, \
    MISSING_EVENT_HEADER_MESSAGE, MissingHTTPEventHeader, \
    INVALID_JSON_MESSAGE, get_fixture_http_headers, standardize_headers, \
    ThirdPartyAPIAmbassador, generate_api_token_auth_handler, \
    ThirdPartyAPICallbackError
from zerver.models import get_user, get_realm, UserProfile
from zerver.lib.users import get_api_key
from zerver.lib.send_email import FromAddress
from zerver.lib.test_helpers import HostRequestMock


class WebhooksCommonTestCase(ZulipTestCase):
    def test_webhook_http_header_header_exists(self) -> None:
        webhook_bot = get_user('webhook-bot@zulip.com', get_realm('zulip'))
        request = HostRequestMock()
        request.META['HTTP_X_CUSTOM_HEADER'] = 'custom_value'
        request.user = webhook_bot

        header_value = validate_extract_webhook_http_header(request, 'X_CUSTOM_HEADER',
                                                            'test_webhook')

        self.assertEqual(header_value, 'custom_value')

    def test_webhook_http_header_header_does_not_exist(self) -> None:
        webhook_bot = get_user('webhook-bot@zulip.com', get_realm('zulip'))
        webhook_bot.last_reminder = None
        notification_bot = self.notification_bot()
        request = HostRequestMock()
        request.user = webhook_bot
        request.path = 'some/random/path'

        exception_msg = "Missing the HTTP event header 'X_CUSTOM_HEADER'"
        with self.assertRaisesRegex(MissingHTTPEventHeader, exception_msg):
            validate_extract_webhook_http_header(request, 'X_CUSTOM_HEADER',
                                                 'test_webhook')

        msg = self.get_last_message()
        expected_message = MISSING_EVENT_HEADER_MESSAGE.format(
            bot_name=webhook_bot.full_name,
            request_path=request.path,
            header_name='X_CUSTOM_HEADER',
            integration_name='test_webhook',
            support_email=FromAddress.SUPPORT
        ).rstrip()
        self.assertEqual(msg.sender.email, notification_bot.email)
        self.assertEqual(msg.content, expected_message)

    def test_notify_bot_owner_on_invalid_json(self) -> None:
        @api_key_only_webhook_view('ClientName', notify_bot_owner_on_invalid_json=False)
        def my_webhook_no_notify(request: HttpRequest, user_profile: UserProfile) -> None:
            raise InvalidJSONError("Malformed JSON")

        @api_key_only_webhook_view('ClientName', notify_bot_owner_on_invalid_json=True)
        def my_webhook_notify(request: HttpRequest, user_profile: UserProfile) -> None:
            raise InvalidJSONError("Malformed JSON")

        webhook_bot_email = 'webhook-bot@zulip.com'
        webhook_bot_realm = get_realm('zulip')
        webhook_bot = get_user(webhook_bot_email, webhook_bot_realm)
        webhook_bot_api_key = get_api_key(webhook_bot)
        request = HostRequestMock()
        request.POST['api_key'] = webhook_bot_api_key
        request.host = "zulip.testserver"
        expected_msg = INVALID_JSON_MESSAGE.format(webhook_name='ClientName')

        last_message_id = self.get_last_message().id
        with self.assertRaisesRegex(JsonableError, "Malformed JSON"):
            my_webhook_no_notify(request)  # type: ignore # mypy doesn't seem to apply the decorator

        # First verify that without the setting, it doesn't send a PM to bot owner.
        msg = self.get_last_message()
        self.assertEqual(msg.id, last_message_id)
        self.assertNotEqual(msg.content, expected_msg.strip())

        # Then verify that with the setting, it does send such a message.
        with self.assertRaisesRegex(JsonableError, "Malformed JSON"):
            my_webhook_notify(request)  # type: ignore # mypy doesn't seem to apply the decorator
        msg = self.get_last_message()
        self.assertNotEqual(msg.id, last_message_id)
        self.assertEqual(msg.sender.email, self.notification_bot().email)
        self.assertEqual(msg.content, expected_msg.strip())

    @patch("zerver.lib.webhooks.common.importlib.import_module")
    def test_get_fixture_http_headers_for_success(self, import_module_mock: MagicMock) -> None:
        def fixture_to_headers(fixture_name: str) -> Dict[str, str]:
            # A sample function which would normally perform some
            # extra operations before returning a dictionary
            # corresponding to the fixture name passed. For this test,
            # we just return a fixed dictionary.
            return {"key": "value"}

        fake_module = SimpleNamespace(fixture_to_headers=fixture_to_headers)
        import_module_mock.return_value = fake_module

        headers = get_fixture_http_headers("some_integration", "complex_fixture")
        self.assertEqual(headers, {"key": "value"})

    def test_get_fixture_http_headers_for_non_existant_integration(self) -> None:
        headers = get_fixture_http_headers("some_random_nonexistant_integration", "fixture_name")
        self.assertEqual(headers, {})

    @patch("zerver.lib.webhooks.common.importlib.import_module")
    def test_get_fixture_http_headers_with_no_fixtures_to_headers_function(
        self,
        import_module_mock: MagicMock
    ) -> None:

        fake_module = SimpleNamespace()
        import_module_mock.return_value = fake_module

        self.assertEqual(
            get_fixture_http_headers("some_integration", "simple_fixture"),
            {}
        )

    def test_standardize_headers(self) -> None:
        self.assertEqual(standardize_headers({}), {})

        raw_headers = {"Content-Type": "text/plain", "X-Event-Type": "ping"}
        djangoified_headers = standardize_headers(raw_headers)
        expected_djangoified_headers = {"CONTENT_TYPE": "text/plain", "HTTP_X_EVENT_TYPE": "ping"}
        self.assertEqual(djangoified_headers, expected_djangoified_headers)


class MissingEventHeaderTestCase(WebhookTestCase):
    STREAM_NAME = 'groove'
    URL_TEMPLATE = '/api/v1/external/groove?stream={stream}&api_key={api_key}'

    # This tests the validate_extract_webhook_http_header function with
    # an actual webhook, instead of just making a mock
    def test_missing_event_header(self) -> None:
        self.subscribe(self.test_user, self.STREAM_NAME)
        result = self.client_post(self.url, self.get_body('ticket_state_changed'),
                                  content_type="application/x-www-form-urlencoded")
        self.assert_json_error(result, "Missing the HTTP event header 'X_GROOVE_EVENT'")

        webhook_bot = get_user('webhook-bot@zulip.com', get_realm('zulip'))
        webhook_bot.last_reminder = None
        notification_bot = self.notification_bot()
        msg = self.get_last_message()
        expected_message = MISSING_EVENT_HEADER_MESSAGE.format(
            bot_name=webhook_bot.full_name,
            request_path='/api/v1/external/groove',
            header_name='X_GROOVE_EVENT',
            integration_name='Groove',
            support_email=FromAddress.SUPPORT
        ).rstrip()
        if msg.sender.email != notification_bot.email:  # nocoverage
            # This block seems to fire occasionally; debug output:
            print(msg)
            print(msg.content)
        self.assertEqual(msg.sender.email, notification_bot.email)
        self.assertEqual(msg.content, expected_message)

    def get_body(self, fixture_name: str) -> str:
        return self.webhook_fixture_data("groove", fixture_name, file_type="json")


class ThirdPartyAPIAmbassadorTestCase(ZulipTestCase):
    def test_only_bots_can_become_ambassabors(self) -> None:
        hamlet = self.example_user("hamlet")
        with self.assertRaises(ValueError):
            ThirdPartyAPIAmbassador(hamlet)

        webhook_bot = get_user('webhook-bot@zulip.com', get_realm('zulip'))
        real_ambassador = ThirdPartyAPIAmbassador(webhook_bot)
        self.assertIsNotNone(real_ambassador)

    def test_auth_handler_called_during_initialization_and_persistent_request_kwargs_set(self) -> None:
        webhook_bot = get_user('webhook-bot@zulip.com', get_realm('zulip'))
        sample_params = {"sample_param": "val"}

        def sample_auth_handler(ambassador: ThirdPartyAPIAmbassador) -> None:
            # Do some calculations, read some config data, authenticate, etc.
            ambassador.update_persistent_request_kwargs(params=sample_params)

        ambassador_v1 = ThirdPartyAPIAmbassador(webhook_bot)
        ambassador_v2 = ThirdPartyAPIAmbassador(
            bot=webhook_bot,
            authentication_handler=sample_auth_handler
        )

        self.assertEqual(ambassador_v1._persistent_request_kwargs, {'data': {}, 'json': {}, 'params': {}, 'headers': {}})
        self.assertEqual(ambassador_v2._persistent_request_kwargs, {'data': {}, 'json': {}, 'params': {"sample_param": "val"}, 'headers': {}})

    @httpretty.activate
    def test_http_api_callback_method(self) -> None:

        counter = 0
        logs = ""

        def sample_preprocessor(ambassador: ThirdPartyAPIAmbassador) -> None:
            # For the sake of an example, we keep things simple
            nonlocal counter
            counter += 1

        def sample_postprocessor(ambassador: ThirdPartyAPIAmbassador) -> None:
            nonlocal logs
            response = ambassador.result
            assert response is not None
            content = json.loads(response.content.decode("utf-8"))["msg"]
            if counter < 3:
                logs += "{}{}, ".format(response.status_code, content)
            else:
                logs += "{}{}".format(response.status_code, content)

        def request_callback(request: HttpRequest, uri: str, response_headers: Dict[str, str]) -> List[object]:
            number = json.loads(request.body.decode("utf-8"))["number"]
            return [200, response_headers, json.dumps({"msg": number})]

        httpretty.register_uri(httpretty.POST, "https://example.com/api", body=request_callback)
        ambassador = ThirdPartyAPIAmbassador(bot=get_user('webhook-bot@zulip.com', get_realm('zulip')),
                                             request_preprocessor=sample_preprocessor,
                                             request_postprocessor=sample_postprocessor)

        for i in range(1, 4):
            ambassador.http_api_callback("https://example.com/api", json={"number": i})

        self.assertEqual(counter, 3)
        self.assertEqual(logs, "2001, 2002, 2003")
        self.assertEqual(len(ambassador.response_log), 3)
        recent_result = ambassador.result
        assert recent_result is not None
        self.assertEqual(json.loads(recent_result.content.decode("utf-8")), {"msg": 3})

    @httpretty.activate
    def test_http_api_callback_method_with_relative_addressing(self) -> None:
        def request_callback(request: HttpRequest, uri: str, response_headers: Dict[str, str]) -> List[object]:
            return [200, response_headers, json.dumps({"msg": "success"})]

        httpretty.register_uri(httpretty.GET, "https://example.com/api", body=request_callback)

        ambassador = ThirdPartyAPIAmbassador(bot=get_user('webhook-bot@zulip.com', get_realm('zulip')))

        with self.assertRaises(ValueError):
            ambassador.http_api_callback("/api", "get")

        ambassador = ThirdPartyAPIAmbassador(bot=get_user('webhook-bot@zulip.com', get_realm('zulip')),
                                             root_url="https://example.com")
        result = ambassador.http_api_callback("/api", "get")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(json.loads(result.content.decode("utf-8")), {"msg": "success"})

    @httpretty.activate
    def test_raise_third_party_api_callback_error(self) -> None:
        def request_callback(request: HttpRequest, uri: str, response_headers: Dict[str, str]) -> List[object]:
            return [500, response_headers, "Server-side error"]

        httpretty.register_uri(httpretty.GET, "https://example.com/api", body=request_callback)
        ambassador = ThirdPartyAPIAmbassador(bot=get_user('webhook-bot@zulip.com', get_realm('zulip')))

        try:
            ambassador.http_api_callback("https://example.com/api", method="get")
            raise AssertionError("ThirdPartyAPICallbackError not raised.")
        except ThirdPartyAPICallbackError as e:
            self.assertEqual(str(e), "API Callback to https://example.com/api via. the \"Zulip Webhook Bot\" bot failed with status 500.")
        except Exception:  # nocoverage
            raise AssertionError("ThirdPartyAPICallbackError not raised.")

class ApiTokenAuthHandlerTestCase(ZulipTestCase):
    def test_api_token_auth_handler_with_invalid_mode_but_well_configured(self) -> None:
        auth_handler = generate_api_token_auth_handler(mode="asdf", param_key="urltoken", config_element_key="my_config_key")
        webhook_bot = get_user('webhook-bot@zulip.com', get_realm('zulip'))
        webhook_bot.botconfigdata_set.create(key="my_config_key", value="val")
        with self.assertRaises(ValueError):
            ThirdPartyAPIAmbassador(webhook_bot, authentication_handler=auth_handler)

    def test_api_token_auth_handler_with_valid_mode_but_misconfigured(self) -> None:
        auth_handler = generate_api_token_auth_handler(mode="form", param_key="urltoken", config_element_key="my_config_key")
        webhook_bot = get_user('webhook-bot@zulip.com', get_realm('zulip'))
        with self.assertRaises(ConfigError):
            ThirdPartyAPIAmbassador(webhook_bot, authentication_handler=auth_handler)
        webhook_bot.botconfigdata_set.create(key="some_config_key", value="val")
        with self.assertRaises(ConfigError):
            ThirdPartyAPIAmbassador(webhook_bot, authentication_handler=auth_handler)

    def test_api_token_auth_handler_with_valid_mode_and_well_configured(self) -> None:
        webhook_bot = get_user('webhook-bot@zulip.com', get_realm('zulip'))
        webhook_bot.botconfigdata_set.create(key="my_config_key", value="val")

        options = {
            "url": "params",
            "form": "data",
            "json": "json",
            "headers": "headers"
        }

        for k, v in options.items():
            auth_handler = generate_api_token_auth_handler(mode=k, param_key="urltoken", config_element_key="my_config_key")
            ambassador = ThirdPartyAPIAmbassador(webhook_bot, authentication_handler=auth_handler)
            self.assertEqual(ambassador._persistent_request_kwargs[v], {"urltoken": "val"})
