# -*- coding: utf-8 -*-
import mock
import re
import os
from collections import defaultdict

from typing import Any, Dict, Iterable, List, Optional, Text, Tuple
from django.test import TestCase
from django.http import HttpResponse, HttpRequest
from django.test.client import RequestFactory
from django.conf import settings

from zerver.forms import OurAuthenticationForm
from zerver.lib.actions import do_deactivate_realm, do_deactivate_user, \
    do_reactivate_user, do_reactivate_realm
from zerver.lib.initial_password import initial_password
from zerver.lib.test_helpers import (
    HostRequestMock,
)
from zerver.lib.test_classes import (
    ZulipTestCase,
    WebhookTestCase,
)
from zerver.lib.response import json_response
from zerver.lib.user_agent import parse_user_agent
from zerver.lib.request import \
    REQ, has_request_variables, RequestVariableMissingError, \
    RequestVariableConversionError, JsonableError
from zerver.decorator import (
    api_key_only_webhook_view,
    authenticated_json_post_view, authenticated_json_view,
    authenticate_notify,
    get_client_name, internal_notify_view, is_local_addr,
    rate_limit, validate_api_key, logged_in_and_active,
    return_success_on_head_request
)
from zerver.lib.validator import (
    check_string, check_dict, check_dict_only, check_bool, check_float, check_int, check_list, Validator,
    check_variable_type, equals, check_none_or, check_url,
)
from zerver.models import \
    get_realm, get_user, UserProfile, Client, Realm, Recipient

import ujson

class DecoratorTestCase(TestCase):
    def test_get_client_name(self):
        # type: () -> None
        class Request(object):
            def __init__(self, GET, POST, META):
                # type: (Dict[str, str], Dict[str, str], Dict[str, str]) -> None
                self.GET = GET
                self.POST = POST
                self.META = META

        req = Request(
            GET=dict(),
            POST=dict(),
            META=dict(),
        )

        self.assertEqual(get_client_name(req, is_browser_view=True), 'website')
        self.assertEqual(get_client_name(req, is_browser_view=False), 'Unspecified')

        req = Request(
            GET=dict(),
            POST=dict(),
            META=dict(HTTP_USER_AGENT='Mozilla/bla bla bla'),
        )

        self.assertEqual(get_client_name(req, is_browser_view=True), 'website')
        self.assertEqual(get_client_name(req, is_browser_view=False), 'Mozilla')

        req = Request(
            GET=dict(),
            POST=dict(),
            META=dict(HTTP_USER_AGENT='ZulipDesktop/bla bla bla'),
        )

        self.assertEqual(get_client_name(req, is_browser_view=True), 'ZulipDesktop')
        self.assertEqual(get_client_name(req, is_browser_view=False), 'ZulipDesktop')

        req = Request(
            GET=dict(),
            POST=dict(),
            META=dict(HTTP_USER_AGENT='ZulipMobile/bla bla bla'),
        )

        self.assertEqual(get_client_name(req, is_browser_view=True), 'ZulipMobile')
        self.assertEqual(get_client_name(req, is_browser_view=False), 'ZulipMobile')

        req = Request(
            GET=dict(client='fancy phone'),
            POST=dict(),
            META=dict(),
        )

        self.assertEqual(get_client_name(req, is_browser_view=True), 'fancy phone')
        self.assertEqual(get_client_name(req, is_browser_view=False), 'fancy phone')

    def test_REQ_converter(self):
        # type: () -> None

        def my_converter(data):
            # type: (str) -> List[str]
            lst = ujson.loads(data)
            if not isinstance(lst, list):
                raise ValueError('not a list')
            if 13 in lst:
                raise JsonableError('13 is an unlucky number!')
            return lst

        @has_request_variables
        def get_total(request, numbers=REQ(converter=my_converter)):
            # type: (HttpRequest, Iterable[int]) -> int
            return sum(numbers)

        class Request(object):
            GET = {}  # type: Dict[str, str]
            POST = {}  # type: Dict[str, str]

        request = Request()

        with self.assertRaises(RequestVariableMissingError):
            get_total(request)

        request.POST['numbers'] = 'bad_value'
        with self.assertRaises(RequestVariableConversionError) as cm:
            get_total(request)
        self.assertEqual(str(cm.exception), "Bad value for 'numbers': bad_value")

        request.POST['numbers'] = ujson.dumps('{fun: unfun}')
        with self.assertRaises(JsonableError) as cm:
            get_total(request)
        self.assertEqual(str(cm.exception), 'Bad value for \'numbers\': "{fun: unfun}"')

        request.POST['numbers'] = ujson.dumps([2, 3, 5, 8, 13, 21])
        with self.assertRaises(JsonableError) as cm:
            get_total(request)
        self.assertEqual(str(cm.exception), "13 is an unlucky number!")

        request.POST['numbers'] = ujson.dumps([1, 2, 3, 4, 5, 6])
        result = get_total(request)
        self.assertEqual(result, 21)

    def test_REQ_converter_and_validator_invalid(self):
        # type: () -> None
        with self.assertRaisesRegex(AssertionError, "converter and validator are mutually exclusive"):
            @has_request_variables
            def get_total(request, numbers=REQ(validator=check_list(check_int),
                                               converter=lambda: None)):
                # type: (HttpRequest, Iterable[int]) -> int
                return sum(numbers)  # nocoverage -- isn't intended to be run

    def test_REQ_validator(self):
        # type: () -> None

        @has_request_variables
        def get_total(request, numbers=REQ(validator=check_list(check_int))):
            # type: (HttpRequest, Iterable[int]) -> int
            return sum(numbers)

        class Request(object):
            GET = {}  # type: Dict[str, str]
            POST = {}  # type: Dict[str, str]

        request = Request()

        with self.assertRaises(RequestVariableMissingError):
            get_total(request)

        request.POST['numbers'] = 'bad_value'
        with self.assertRaises(JsonableError) as cm:
            get_total(request)
        self.assertEqual(str(cm.exception), 'Argument "numbers" is not valid JSON.')

        request.POST['numbers'] = ujson.dumps([1, 2, "what?", 4, 5, 6])
        with self.assertRaises(JsonableError) as cm:
            get_total(request)
        self.assertEqual(str(cm.exception), 'numbers[2] is not an integer')

        request.POST['numbers'] = ujson.dumps([1, 2, 3, 4, 5, 6])
        result = get_total(request)
        self.assertEqual(result, 21)

    def test_REQ_argument_type(self):
        # type: () -> None
        @has_request_variables
        def get_payload(request, payload=REQ(argument_type='body')):
            # type: (HttpRequest, Dict[str, Dict]) -> Dict[str, Dict]
            return payload

        class MockRequest(object):
            body = {}  # type: Any

        request = MockRequest()

        request.body = 'notjson'
        with self.assertRaises(JsonableError) as cm:
            get_payload(request)
        self.assertEqual(str(cm.exception), 'Malformed JSON')

        request.body = '{"a": "b"}'
        self.assertEqual(get_payload(request), {'a': 'b'})

        # Test we properly handle an invalid argument_type.
        with self.assertRaises(Exception) as cm:
            @has_request_variables
            def test(request, payload=REQ(argument_type="invalid")):
                # type: (HttpRequest, Dict[str, Dict]) -> None
                pass  # nocoverage # this function isn't meant to be called
            test(request)

    def test_api_key_only_webhook_view(self):
        # type: () -> None
        @api_key_only_webhook_view('ClientName')
        def my_webhook(request, user_profile):
            # type: (HttpRequest, UserProfile) -> Text
            return user_profile.email

        @api_key_only_webhook_view('ClientName')
        def my_webhook_raises_exception(request, user_profile):
            # type: (HttpRequest, UserProfile) -> None
            raise Exception("raised by webhook function")

        webhook_bot_email = 'webhook-bot@zulip.com'
        webhook_bot_realm = get_realm('zulip')
        webhook_bot = get_user(webhook_bot_email, webhook_bot_realm)
        webhook_bot_api_key = webhook_bot.api_key
        webhook_client_name = "ZulipClientNameWebhook"

        request = HostRequestMock()
        request.POST['api_key'] = 'not_existing_api_key'

        with self.assertRaisesRegex(JsonableError, "Invalid API key"):
            my_webhook(request)

        # Start a valid request here
        request.POST['api_key'] = webhook_bot_api_key

        with self.settings(REALMS_HAVE_SUBDOMAINS=True):
            with mock.patch('logging.warning') as mock_warning:
                with self.assertRaisesRegex(JsonableError,
                                            "Account is not associated with this subdomain"):
                    api_result = my_webhook(request)

                mock_warning.assert_called_with(
                    "User {} attempted to access API on wrong "
                    "subdomain {}".format(webhook_bot_email, ''))

            with mock.patch('logging.warning') as mock_warning:
                with self.assertRaisesRegex(JsonableError,
                                            "Account is not associated with this subdomain"):
                    request.host = "acme." + settings.EXTERNAL_HOST
                    api_result = my_webhook(request)

                mock_warning.assert_called_with(
                    "User {} attempted to access API on wrong "
                    "subdomain {}".format(webhook_bot_email, 'acme'))

        request.host = "zulip.testserver"
        # Test when content_type is application/json and request.body
        # is valid JSON; exception raised in the webhook function
        # should be re-raised
        with mock.patch('zerver.decorator.webhook_logger.exception') as mock_exception:
            with self.assertRaisesRegex(Exception, "raised by webhook function"):
                request.body = "{}"
                request.content_type = 'application/json'
                my_webhook_raises_exception(request)

        # Test when content_type is not application/json; exception raised
        # in the webhook function should be re-raised
        with mock.patch('zerver.decorator.webhook_logger.exception') as mock_exception:
            with self.assertRaisesRegex(Exception, "raised by webhook function"):
                request.body = "notjson"
                request.content_type = 'text/plain'
                my_webhook_raises_exception(request)

        # Test when content_type is application/json but request.body
        # is not valid JSON; invalid JSON should be logged and the
        # exception raised in the webhook function should be re-raised
        with mock.patch('zerver.decorator.webhook_logger.exception') as mock_exception:
            with self.assertRaisesRegex(Exception, "raised by webhook function"):
                request.body = "invalidjson"
                request.content_type = 'application/json'
                my_webhook_raises_exception(request)

            message = """
user: {email} ({realm})
client: {client_name}
URL: {path_info}
content_type: {content_type}
body:

{body}
                """
            mock_exception.assert_called_with(message.format(
                email=webhook_bot_email,
                realm=webhook_bot_realm.string_id,
                client_name=webhook_client_name,
                path_info=request.META.get('PATH_INFO'),
                content_type=request.content_type,
                body=request.body,
            ))

        with self.settings(RATE_LIMITING=True):
            with mock.patch('zerver.decorator.rate_limit_user') as rate_limit_mock:
                api_result = my_webhook(request)

        # Verify rate limiting was attempted.
        self.assertTrue(rate_limit_mock.called)

        # Verify decorator set the magic _email field used by some of our back end logging.
        self.assertEqual(request._email, webhook_bot_email)

        # Verify the main purpose of the decorator, which is that it passed in the
        # user_profile to my_webhook, allowing it return the correct
        # email for the bot (despite the API caller only knowing the API key).
        self.assertEqual(api_result, webhook_bot_email)

        # Now deactivate the user
        webhook_bot.is_active = False
        webhook_bot.save()
        with self.assertRaisesRegex(JsonableError, "Account not active"):
            my_webhook(request)

        # Reactive the user, but deactivate their realm.
        webhook_bot.is_active = True
        webhook_bot.save()
        webhook_bot.realm.deactivated = True
        webhook_bot.realm.save()
        with self.assertRaisesRegex(JsonableError, "Realm for account has been deactivated"):
            my_webhook(request)


class RateLimitTestCase(TestCase):
    def errors_disallowed(self):
        # type: () -> mock
        # Due to what is probably a hack in rate_limit(),
        # some tests will give a false positive (or succeed
        # for the wrong reason), unless we complain
        # about logging errors.  There might be a more elegant way
        # make logging errors fail than what I'm doing here.
        class TestLoggingErrorException(Exception):
            pass
        return mock.patch('logging.error', side_effect=TestLoggingErrorException)

    def test_internal_local_clients_skip_rate_limiting(self):
        # type: () -> None
        class Client(object):
            name = 'internal'

        class Request(object):
            client = Client()
            META = {'REMOTE_ADDR': '127.0.0.1'}

        req = Request()

        def f(req):
            # type: (Any) -> str
            return 'some value'

        f = rate_limit()(f)

        with self.settings(RATE_LIMITING=True):
            with mock.patch('zerver.decorator.rate_limit_user') as rate_limit_mock:
                with self.errors_disallowed():
                    self.assertEqual(f(req), 'some value')

        self.assertFalse(rate_limit_mock.called)

    def test_debug_clients_skip_rate_limiting(self):
        # type: () -> None
        class Client(object):
            name = 'internal'

        class Request(object):
            client = Client()
            META = {'REMOTE_ADDR': '3.3.3.3'}

        req = Request()

        def f(req):
            # type: (Any) -> str
            return 'some value'

        f = rate_limit()(f)

        with self.settings(RATE_LIMITING=True):
            with mock.patch('zerver.decorator.rate_limit_user') as rate_limit_mock:
                with self.errors_disallowed():
                    with self.settings(DEBUG_RATE_LIMITING=True):
                        self.assertEqual(f(req), 'some value')

        self.assertFalse(rate_limit_mock.called)

    def test_rate_limit_setting_of_false_bypasses_rate_limiting(self):
        # type: () -> None
        class Client(object):
            name = 'external'

        class Request(object):
            client = Client()
            META = {'REMOTE_ADDR': '3.3.3.3'}
            user = 'stub'  # any non-None value here exercises the correct code path

        req = Request()

        def f(req):
            # type: (Any) -> str
            return 'some value'

        f = rate_limit()(f)

        with self.settings(RATE_LIMITING=False):
            with mock.patch('zerver.decorator.rate_limit_user') as rate_limit_mock:
                with self.errors_disallowed():
                    self.assertEqual(f(req), 'some value')

        self.assertFalse(rate_limit_mock.called)

    def test_rate_limiting_happens_in_normal_case(self):
        # type: () -> None
        class Client(object):
            name = 'external'

        class Request(object):
            client = Client()
            META = {'REMOTE_ADDR': '3.3.3.3'}
            user = 'stub'  # any non-None value here exercises the correct code path

        req = Request()

        def f(req):
            # type: (Any) -> str
            return 'some value'

        f = rate_limit()(f)

        with self.settings(RATE_LIMITING=True):
            with mock.patch('zerver.decorator.rate_limit_user') as rate_limit_mock:
                with self.errors_disallowed():
                    self.assertEqual(f(req), 'some value')

        self.assertTrue(rate_limit_mock.called)

class ValidatorTestCase(TestCase):
    def test_check_string(self):
        # type: () -> None
        x = "hello"  # type: Any
        self.assertEqual(check_string('x', x), None)

        x = 4
        self.assertEqual(check_string('x', x), 'x is not a string')

    def test_check_bool(self):
        # type: () -> None
        x = True  # type: Any
        self.assertEqual(check_bool('x', x), None)

        x = 4
        self.assertEqual(check_bool('x', x), 'x is not a boolean')

    def test_check_int(self):
        # type: () -> None
        x = 5  # type: Any
        self.assertEqual(check_int('x', x), None)

        x = [{}]
        self.assertEqual(check_int('x', x), 'x is not an integer')

    def test_check_float(self):
        # type: () -> None
        x = 5.5  # type: Any
        self.assertEqual(check_float('x', x), None)

        x = 5
        self.assertEqual(check_float('x', x), 'x is not a float')

        x = [{}]
        self.assertEqual(check_float('x', x), 'x is not a float')

    def test_check_list(self):
        # type: () -> None
        x = 999  # type: Any
        error = check_list(check_string)('x', x)
        self.assertEqual(error, 'x is not a list')

        x = ["hello", 5]
        error = check_list(check_string)('x', x)
        self.assertEqual(error, 'x[1] is not a string')

        x = [["yo"], ["hello", "goodbye", 5]]
        error = check_list(check_list(check_string))('x', x)
        self.assertEqual(error, 'x[1][2] is not a string')

        x = ["hello", "goodbye", "hello again"]
        error = check_list(check_string, length=2)('x', x)
        self.assertEqual(error, 'x should have exactly 2 items')

    def test_check_dict(self):
        # type: () -> None
        keys = [
            ('names', check_list(check_string)),
            ('city', check_string),
        ]  # type: List[Tuple[str, Validator]]

        x = {
            'names': ['alice', 'bob'],
            'city': 'Boston',
        }  # type: Any
        error = check_dict(keys)('x', x)
        self.assertEqual(error, None)

        x = 999
        error = check_dict(keys)('x', x)
        self.assertEqual(error, 'x is not a dict')

        x = {}
        error = check_dict(keys)('x', x)
        self.assertEqual(error, 'names key is missing from x')

        x = {
            'names': ['alice', 'bob', {}]
        }
        error = check_dict(keys)('x', x)
        self.assertEqual(error, 'x["names"][2] is not a string')

        x = {
            'names': ['alice', 'bob'],
            'city': 5
        }
        error = check_dict(keys)('x', x)
        self.assertEqual(error, 'x["city"] is not a string')

        # test dict_only
        x = {
            'names': ['alice', 'bob'],
            'city': 'Boston',
        }
        error = check_dict_only(keys)('x', x)
        self.assertEqual(error, None)

        x = {
            'names': ['alice', 'bob'],
            'city': 'Boston',
            'state': 'Massachusetts',
        }
        error = check_dict_only(keys)('x', x)
        self.assertEqual(error, 'Unexpected arguments: state')

    def test_encapsulation(self):
        # type: () -> None
        # There might be situations where we want deep
        # validation, but the error message should be customized.
        # This is an example.
        def check_person(val):
            # type: (Any) -> Optional[str]
            error = check_dict([
                ('name', check_string),
                ('age', check_int),
            ])('_', val)
            if error:
                return 'This is not a valid person'
            return None

        person = {'name': 'King Lear', 'age': 42}
        self.assertEqual(check_person(person), None)

        nonperson = 'misconfigured data'
        self.assertEqual(check_person(nonperson), 'This is not a valid person')

    def test_check_variable_type(self):
        # type: () -> None
        x = 5  # type: Any
        self.assertEqual(check_variable_type([check_string, check_int])('x', x), None)

        x = 'x'
        self.assertEqual(check_variable_type([check_string, check_int])('x', x), None)

        x = [{}]
        self.assertEqual(check_variable_type([check_string, check_int])('x', x), 'x is not an allowed_type')

    def test_equals(self):
        # type: () -> None
        x = 5  # type: Any
        self.assertEqual(equals(5)('x', x), None)
        self.assertEqual(equals(6)('x', x), 'x != 6 (5 is wrong)')

    def test_check_none_or(self):
        # type: () -> None
        x = 5  # type: Any
        self.assertEqual(check_none_or(check_int)('x', x), None)
        x = None
        self.assertEqual(check_none_or(check_int)('x', x), None)
        x = 'x'
        self.assertEqual(check_none_or(check_int)('x', x), 'x is not an integer')

    def test_check_url(self):
        # type: () -> None
        url = "http://127.0.0.1:5002/"  # type: Any
        check_url('url', url)

        url = "http://zulip-bots.example.com/"
        check_url('url', url)

        url = "http://127.0.0"
        with self.assertRaises(JsonableError):
            check_url('url', url)

class DeactivatedRealmTest(ZulipTestCase):
    def test_send_deactivated_realm(self):
        # type: () -> None
        """
        rest_dispatch rejects requests in a deactivated realm, both /json and api

        """
        realm = get_realm("zulip")
        do_deactivate_realm(get_realm("zulip"))

        result = self.client_post("/json/messages", {"type": "private",
                                                     "content": "Test message",
                                                     "client": "test suite",
                                                     "to": self.example_email("othello")})
        self.assert_json_error_contains(result, "Not logged in", status_code=401)

        # Even if a logged-in session was leaked, it still wouldn't work
        realm.deactivated = False
        realm.save()
        self.login(self.example_email("hamlet"))
        realm.deactivated = True
        realm.save()

        result = self.client_post("/json/messages", {"type": "private",
                                                     "content": "Test message",
                                                     "client": "test suite",
                                                     "to": self.example_email("othello")})
        self.assert_json_error_contains(result, "has been deactivated", status_code=400)

        result = self.client_post("/api/v1/messages", {"type": "private",
                                                       "content": "Test message",
                                                       "client": "test suite",
                                                       "to": self.example_email("othello")},
                                  **self.api_auth(self.example_email("hamlet")))
        self.assert_json_error_contains(result, "has been deactivated", status_code=401)

    def test_fetch_api_key_deactivated_realm(self):
        # type: () -> None
        """
        authenticated_json_view views fail in a deactivated realm

        """
        realm = get_realm("zulip")
        user_profile = self.example_user('hamlet')
        email = user_profile.email
        test_password = "abcd1234"
        user_profile.set_password(test_password)

        self.login(email)
        realm.deactivated = True
        realm.save()
        result = self.client_post("/json/fetch_api_key", {"password": test_password})
        self.assert_json_error_contains(result, "has been deactivated", status_code=400)

    def test_login_deactivated_realm(self):
        # type: () -> None
        """
        logging in fails in a deactivated realm

        """
        do_deactivate_realm(get_realm("zulip"))
        result = self.login_with_return(self.example_email("hamlet"),
                                        subdomain="zulip")
        self.assert_in_response("has been deactivated", result)

    def test_webhook_deactivated_realm(self):
        # type: () -> None
        """
        Using a webhook while in a deactivated realm fails

        """
        do_deactivate_realm(get_realm("zulip"))
        user_profile = self.example_user("hamlet")
        url = "/api/v1/external/jira?api_key=%s&stream=jira_custom" % (
            user_profile.api_key,)
        data = self.fixture_data('jira', "created_v2")
        result = self.client_post(url, data,
                                  content_type="application/json")
        self.assert_json_error_contains(result, "has been deactivated", status_code=400)

class LoginRequiredTest(ZulipTestCase):
    def test_login_required(self):
        # type: () -> None
        """
        Verifies the zulip_login_required decorator blocks deactivated users.
        """
        user_profile = self.example_user('hamlet')
        email = user_profile.email

        # Verify fails if logged-out
        result = self.client_get('/accounts/accept_terms/')
        self.assertEqual(result.status_code, 302)

        # Verify succeeds once logged-in
        self.login(email)
        result = self.client_get('/accounts/accept_terms/')
        self.assert_in_response("I agree to the", result)

        # Verify fails if user deactivated (with session still valid)
        user_profile.is_active = False
        user_profile.save()
        result = self.client_get('/accounts/accept_terms/')
        self.assertEqual(result.status_code, 302)

        # Verify succeeds if user reactivated
        do_reactivate_user(user_profile)
        self.login(email)
        result = self.client_get('/accounts/accept_terms/')
        self.assert_in_response("I agree to the", result)

        # Verify fails if realm deactivated
        user_profile.realm.deactivated = True
        user_profile.realm.save()
        result = self.client_get('/accounts/accept_terms/')
        self.assertEqual(result.status_code, 302)

class FetchAPIKeyTest(ZulipTestCase):
    def test_fetch_api_key_success(self):
        # type: () -> None
        email = self.example_email("cordelia")

        self.login(email)
        result = self.client_post("/json/fetch_api_key", {"password": initial_password(email)})
        self.assert_json_success(result)

    def test_fetch_api_key_wrong_password(self):
        # type: () -> None
        email = self.example_email("cordelia")

        self.login(email)
        result = self.client_post("/json/fetch_api_key", {"password": "wrong_password"})
        self.assert_json_error_contains(result, "password is incorrect")

class InactiveUserTest(ZulipTestCase):
    def test_send_deactivated_user(self):
        # type: () -> None
        """
        rest_dispatch rejects requests from deactivated users, both /json and api

        """
        user_profile = self.example_user('hamlet')
        email = user_profile.email
        self.login(email)
        do_deactivate_user(user_profile)

        result = self.client_post("/json/messages", {"type": "private",
                                                     "content": "Test message",
                                                     "client": "test suite",
                                                     "to": self.example_email("othello")})
        self.assert_json_error_contains(result, "Not logged in", status_code=401)

        # Even if a logged-in session was leaked, it still wouldn't work
        do_reactivate_user(user_profile)
        self.login(email)
        user_profile.is_active = False
        user_profile.save()

        result = self.client_post("/json/messages", {"type": "private",
                                                     "content": "Test message",
                                                     "client": "test suite",
                                                     "to": self.example_email("othello")})
        self.assert_json_error_contains(result, "Account not active", status_code=400)

        result = self.client_post("/api/v1/messages", {"type": "private",
                                                       "content": "Test message",
                                                       "client": "test suite",
                                                       "to": self.example_email("othello")},
                                  **self.api_auth(self.example_email("hamlet")))
        self.assert_json_error_contains(result, "Account not active", status_code=401)

    def test_fetch_api_key_deactivated_user(self):
        # type: () -> None
        """
        authenticated_json_view views fail with a deactivated user

        """
        user_profile = self.example_user('hamlet')
        email = user_profile.email
        test_password = "abcd1234"
        user_profile.set_password(test_password)
        user_profile.save()

        self.login(email, password=test_password)
        user_profile.is_active = False
        user_profile.save()
        result = self.client_post("/json/fetch_api_key", {"password": test_password})
        self.assert_json_error_contains(result, "Account not active", status_code=400)

    def test_login_deactivated_user(self):
        # type: () -> None
        """
        logging in fails with an inactive user

        """
        user_profile = self.example_user('hamlet')
        do_deactivate_user(user_profile)

        result = self.login_with_return(self.example_email("hamlet"))
        self.assert_in_response(
            "Sorry for the trouble, but your account has been deactivated",
            result)

    def test_login_deactivated_mirror_dummy(self):
        # type: () -> None
        """
        logging in fails with an inactive user

        """
        user_profile = self.example_user('hamlet')
        user_profile.is_mirror_dummy = True
        user_profile.save()

        password = initial_password(user_profile.email)
        request = mock.MagicMock()
        request.get_host.return_value = 'zulip.testserver'

        # Test a mirror-dummy active user.
        form = OurAuthenticationForm(request,
                                     data={'username': user_profile.email,
                                           'password': password})
        with self.settings(AUTHENTICATION_BACKENDS=('zproject.backends.EmailAuthBackend',)):
            self.assertTrue(form.is_valid())

        # Test a mirror-dummy deactivated user.
        do_deactivate_user(user_profile)
        user_profile.save()

        form = OurAuthenticationForm(request,
                                     data={'username': user_profile.email,
                                           'password': password})
        with self.settings(AUTHENTICATION_BACKENDS=('zproject.backends.EmailAuthBackend',)):
            self.assertFalse(form.is_valid())
            self.assertIn("Please enter a correct email", str(form.errors))

        # Test a non-mirror-dummy deactivated user.
        user_profile.is_mirror_dummy = False
        user_profile.save()

        form = OurAuthenticationForm(request,
                                     data={'username': user_profile.email,
                                           'password': password})
        with self.settings(AUTHENTICATION_BACKENDS=('zproject.backends.EmailAuthBackend',)):
            self.assertFalse(form.is_valid())
            self.assertIn("your account has been deactivated", str(form.errors))

    def test_webhook_deactivated_user(self):
        # type: () -> None
        """
        Deactivated users can't use webhooks

        """
        user_profile = self.example_user('hamlet')
        do_deactivate_user(user_profile)

        url = "/api/v1/external/jira?api_key=%s&stream=jira_custom" % (
            user_profile.api_key,)
        data = self.fixture_data('jira', "created_v2")
        result = self.client_post(url, data,
                                  content_type="application/json")
        self.assert_json_error_contains(result, "Account not active", status_code=400)


class TestIncomingWebhookBot(ZulipTestCase):
    def setUp(self):
        # type: () -> None
        zulip_realm = get_realm('zulip')
        self.webhook_bot = get_user('webhook-bot@zulip.com', zulip_realm)

    def test_webhook_bot_permissions(self):
        # type: () -> None
        result = self.client_post("/api/v1/messages", {
            "type": "private",
            "content": "Test message",
            "client": "test suite",
            "to": self.example_email("othello")
        }, **self.api_auth("webhook-bot@zulip.com"))
        self.assert_json_success(result)
        post_params = {"anchor": 1, "num_before": 1, "num_after": 1}
        result = self.client_get("/api/v1/messages", dict(post_params),
                                 **self.api_auth("webhook-bot@zulip.com"))
        self.assert_json_error(result, 'This API is not available to incoming webhook bots.',
                               status_code=401)

class TestValidateApiKey(ZulipTestCase):
    def setUp(self):
        # type: () -> None
        zulip_realm = get_realm('zulip')
        self.webhook_bot = get_user('webhook-bot@zulip.com', zulip_realm)
        self.default_bot = get_user('default-bot@zulip.com', zulip_realm)

    def test_validate_api_key_if_profile_does_not_exist(self):
        # type: () -> None
        with self.assertRaises(JsonableError):
            validate_api_key(HostRequestMock(), 'email@doesnotexist.com', 'api_key')

    def test_validate_api_key_if_api_key_does_not_match_profile_api_key(self):
        # type: () -> None
        with self.assertRaises(JsonableError):
            validate_api_key(HostRequestMock(), self.webhook_bot.email, 'not_32_length')

        with self.assertRaises(JsonableError):
            validate_api_key(HostRequestMock(), self.webhook_bot.email, self.default_bot.api_key)

    def test_validate_api_key_if_profile_is_not_active(self):
        # type: () -> None
        self._change_is_active_field(self.default_bot, False)
        with self.assertRaises(JsonableError):
            validate_api_key(HostRequestMock(), self.default_bot.email, self.default_bot.api_key)
        self._change_is_active_field(self.default_bot, True)

    def test_validate_api_key_if_profile_is_incoming_webhook_and_is_webhook_is_unset(self):
        # type: () -> None
        with self.assertRaises(JsonableError):
            validate_api_key(HostRequestMock(), self.webhook_bot.email, self.webhook_bot.api_key)

    def test_validate_api_key_if_profile_is_incoming_webhook_and_is_webhook_is_set(self):
        # type: () -> None
        profile = validate_api_key(HostRequestMock(host="zulip.testserver"),
                                   self.webhook_bot.email, self.webhook_bot.api_key,
                                   is_webhook=True)
        self.assertEqual(profile.pk, self.webhook_bot.pk)

    def test_valid_api_key_if_user_is_on_wrong_subdomain(self):
        # type: () -> None
        with self.settings(REALMS_HAVE_SUBDOMAINS=True):
            with self.settings(RUNNING_INSIDE_TORNADO=False):
                with mock.patch('logging.warning') as mock_warning:
                    with self.assertRaisesRegex(JsonableError,
                                                "Account is not associated with this subdomain"):
                        validate_api_key(HostRequestMock(host=settings.EXTERNAL_HOST),
                                         self.default_bot.email,
                                         self.default_bot.api_key)

                    mock_warning.assert_called_with(
                        "User {} attempted to access API on wrong "
                        "subdomain {}".format(self.default_bot.email, ''))

                with mock.patch('logging.warning') as mock_warning:
                    with self.assertRaisesRegex(JsonableError,
                                                "Account is not associated with this subdomain"):
                        validate_api_key(HostRequestMock(host='acme.' + settings.EXTERNAL_HOST),
                                         self.default_bot.email,
                                         self.default_bot.api_key)

                    mock_warning.assert_called_with(
                        "User {} attempted to access API on wrong "
                        "subdomain {}".format(self.default_bot.email, 'acme'))

    def _change_is_active_field(self, profile, value):
        # type: (UserProfile, bool) -> None
        profile.is_active = value
        profile.save()

class TestInternalNotifyView(TestCase):
    BORING_RESULT = 'boring'

    class Request(object):
        def __init__(self, POST, META):
            # type: (Dict, Dict) -> None
            self.POST = POST
            self.META = META
            self.method = 'POST'

    def internal_notify(self, is_tornado, req):
        # type: (bool, HttpRequest) -> HttpResponse
        boring_view = lambda req: self.BORING_RESULT
        return internal_notify_view(is_tornado)(boring_view)(req)

    def test_valid_internal_requests(self):
        # type: () -> None
        secret = 'random'
        req = self.Request(
            POST=dict(secret=secret),
            META=dict(REMOTE_ADDR='127.0.0.1'),
        )  # type: HttpRequest

        with self.settings(SHARED_SECRET=secret):
            self.assertTrue(authenticate_notify(req))
            self.assertEqual(self.internal_notify(False, req), self.BORING_RESULT)
            self.assertEqual(req._email, 'internal')

            with self.assertRaises(RuntimeError):
                self.internal_notify(True, req)

        req._tornado_handler = 'set'
        with self.settings(SHARED_SECRET=secret):
            self.assertTrue(authenticate_notify(req))
            self.assertEqual(self.internal_notify(True, req), self.BORING_RESULT)
            self.assertEqual(req._email, 'internal')

            with self.assertRaises(RuntimeError):
                self.internal_notify(False, req)

    def test_internal_requests_with_broken_secret(self):
        # type: () -> None
        secret = 'random'
        req = self.Request(
            POST=dict(secret=secret),
            META=dict(REMOTE_ADDR='127.0.0.1'),
        )

        with self.settings(SHARED_SECRET='broken'):
            self.assertFalse(authenticate_notify(req))
            self.assertEqual(self.internal_notify(True, req).status_code, 403)

    def test_external_requests(self):
        # type: () -> None
        secret = 'random'
        req = self.Request(
            POST=dict(secret=secret),
            META=dict(REMOTE_ADDR='3.3.3.3'),
        )

        with self.settings(SHARED_SECRET=secret):
            self.assertFalse(authenticate_notify(req))
            self.assertEqual(self.internal_notify(True, req).status_code, 403)

    def test_is_local_address(self):
        # type: () -> None
        self.assertTrue(is_local_addr('127.0.0.1'))
        self.assertTrue(is_local_addr('::1'))
        self.assertFalse(is_local_addr('42.43.44.45'))

class TestHumanUsersOnlyDecorator(ZulipTestCase):
    def test_human_only_endpoints(self):
        # type: () -> None
        post_endpoints = [
            "/api/v1/users/me/presence",
            "/api/v1/users/me/apns_device_token",
            "/api/v1/users/me/android_gcm_reg_id",
            "/api/v1/users/me/hotspots",
        ]
        for endpoint in post_endpoints:
            result = self.client_post(endpoint, **self.api_auth('default-bot@zulip.com'))
            self.assert_json_error(result, "This endpoint does not accept bot requests.")

        patch_endpoints = [
            "/api/v1/settings",
            "/api/v1/settings/display",
            "/api/v1/settings/notifications",
            "/api/v1/settings/ui",
            "/api/v1/users/me/profile_data"
        ]
        for endpoint in patch_endpoints:
            result = self.client_patch(endpoint, **self.api_auth('default-bot@zulip.com'))
            self.assert_json_error(result, "This endpoint does not accept bot requests.")

        delete_endpoints = [
            "/api/v1/users/me/apns_device_token",
            "/api/v1/users/me/android_gcm_reg_id",
        ]
        for endpoint in delete_endpoints:
            result = self.client_delete(endpoint, **self.api_auth('default-bot@zulip.com'))
            self.assert_json_error(result, "This endpoint does not accept bot requests.")

class TestAuthenticatedJsonPostViewDecorator(ZulipTestCase):
    def test_authenticated_json_post_view_if_everything_is_correct(self):
        # type: () -> None
        user_email = self.example_email('hamlet')
        user_realm = get_realm('zulip')
        self._login(user_email, user_realm)
        response = self._do_test(user_email)
        self.assertEqual(response.status_code, 200)

    def test_authenticated_json_post_view_if_subdomain_is_invalid(self):
        # type: () -> None
        user_email = self.example_email('hamlet')
        user_realm = get_realm('zulip')
        self._login(user_email, user_realm)
        with self.settings(REALMS_HAVE_SUBDOMAINS=True):
            with mock.patch('logging.warning') as mock_warning, \
                    mock.patch('zerver.decorator.get_subdomain', return_value=''):
                self.assert_json_error_contains(self._do_test(user_email),
                                                "Account is not associated with this "
                                                "subdomain")
                mock_warning.assert_called_with(
                    "User {} attempted to access API on wrong "
                    "subdomain {}".format(user_email, ''))

            with mock.patch('logging.warning') as mock_warning, \
                    mock.patch('zerver.decorator.get_subdomain', return_value='acme'):
                self.assert_json_error_contains(self._do_test(user_email),
                                                "Account is not associated with this "
                                                "subdomain")
                mock_warning.assert_called_with(
                    "User {} attempted to access API on wrong "
                    "subdomain {}".format(user_email, 'acme'))

    def test_authenticated_json_post_view_if_user_is_incoming_webhook(self):
        # type: () -> None
        user_email = 'webhook-bot@zulip.com'
        user_realm = get_realm('zulip')
        self._login(user_email, user_realm, password="test")  # we set a password because user is a bot
        self.assert_json_error_contains(self._do_test(user_email), "Webhook bots can only access webhooks")

    def test_authenticated_json_post_view_if_user_is_not_active(self):
        # type: () -> None
        user_email = self.example_email('hamlet')
        user_realm = get_realm('zulip')
        self._login(user_email, user_realm, password="test")
        # Get user_profile after _login so that we have the latest data.
        user_profile = get_user(user_email, user_realm)
        # we deactivate user manually because do_deactivate_user removes user session
        user_profile.is_active = False
        user_profile.save()
        self.assert_json_error_contains(self._do_test(user_email), "Account not active")
        do_reactivate_user(user_profile)

    def test_authenticated_json_post_view_if_user_realm_is_deactivated(self):
        # type: () -> None
        user_email = self.example_email('hamlet')
        user_realm = get_realm('zulip')
        user_profile = get_user(user_email, user_realm)
        self._login(user_email, user_realm)
        # we deactivate user's realm manually because do_deactivate_user removes user session
        user_profile.realm.deactivated = True
        user_profile.realm.save()
        self.assert_json_error_contains(self._do_test(user_email), "Realm for account has been deactivated")
        do_reactivate_realm(user_profile.realm)

    def _do_test(self, user_email):
        # type: (Text) -> HttpResponse
        data = {"status": '"started"'}
        return self.client_post(r'/json/tutorial_status', data)

    def _login(self, user_email, user_realm, password=None):
        # type: (Text, Realm, str) -> None
        if password:
            user_profile = get_user(user_email, user_realm)
            user_profile.set_password(password)
            user_profile.save()
        self.login(user_email, password)

class TestAuthenticatedJsonViewDecorator(ZulipTestCase):
    def test_authenticated_json_view_if_subdomain_is_invalid(self):
        # type: () -> None
        user_email = self.example_email("hamlet")
        self.login(user_email)
        with self.settings(REALMS_HAVE_SUBDOMAINS=True):
            with mock.patch('logging.warning') as mock_warning, \
                    mock.patch('zerver.decorator.get_subdomain', return_value=''):
                self.assert_json_error_contains(self._do_test(str(user_email)),
                                                "Account is not associated with this "
                                                "subdomain")
                mock_warning.assert_called_with(
                    "User {} attempted to access API on wrong "
                    "subdomain {}".format(user_email, ''))

            with mock.patch('logging.warning') as mock_warning, \
                    mock.patch('zerver.decorator.get_subdomain', return_value='acme'):
                self.assert_json_error_contains(self._do_test(str(user_email)),
                                                "Account is not associated with this "
                                                "subdomain")
                mock_warning.assert_called_with(
                    "User {} attempted to access API on wrong "
                    "subdomain {}".format(user_email, 'acme'))

    def _do_test(self, user_email):
        # type: (str) -> HttpResponse
        data = {"status": '"started"'}
        return self.client_post(r'/json/tutorial_status', data)

class TestZulipLoginRequiredDecorator(ZulipTestCase):
    def test_zulip_login_required_if_subdomain_is_invalid(self):
        # type: () -> None
        user_email = self.example_email("hamlet")
        self.login(user_email)

        with self.settings(REALMS_HAVE_SUBDOMAINS=True):
            with mock.patch('zerver.decorator.get_subdomain', return_value='zulip'):
                result = self.client_get('/accounts/accept_terms/')
                self.assertEqual(result.status_code, 200)

            with mock.patch('zerver.decorator.get_subdomain', return_value=''):
                result = self.client_get('/accounts/accept_terms/')
                self.assertEqual(result.status_code, 302)

            with mock.patch('zerver.decorator.get_subdomain', return_value='acme'):
                result = self.client_get('/accounts/accept_terms/')
                self.assertEqual(result.status_code, 302)

class TestRequireServerAdminDecorator(ZulipTestCase):
    def test_require_server_admin_decorator(self):
        # type: () -> None
        user_email = self.example_email('hamlet')
        user_realm = get_realm('zulip')
        self.login(user_email)

        result = self.client_get('/activity')
        self.assertEqual(result.status_code, 302)

        user_profile = get_user(user_email, user_realm)
        user_profile.is_staff = True
        user_profile.save()

        result = self.client_get('/activity')
        self.assertEqual(result.status_code, 200)

class ReturnSuccessOnHeadRequestDecorator(ZulipTestCase):
    def test_return_success_on_head_request_returns_200_if_request_method_is_head(self):
        # type: () -> None
        class HeadRequest(object):
            method = 'HEAD'

        request = HeadRequest()

        @return_success_on_head_request
        def test_function(request):
            # type: (HttpRequest) -> HttpResponse
            return json_response(msg=u'from_test_function')  # nocoverage. isn't meant to be called

        response = test_function(request)
        self.assert_json_success(response)
        self.assertNotEqual(ujson.loads(response.content).get('msg'), u'from_test_function')

    def test_return_success_on_head_request_returns_normal_response_if_request_method_is_not_head(self):
            # type: () -> None
            class HeadRequest(object):
                method = 'POST'

            request = HeadRequest()

            @return_success_on_head_request
            def test_function(request):
                # type: (HttpRequest) -> HttpResponse
                return json_response(msg=u'from_test_function')

            response = test_function(request)
            self.assertEqual(ujson.loads(response.content).get('msg'), u'from_test_function')

class RestAPITest(ZulipTestCase):
    def test_method_not_allowed(self):
        # type: () -> None
        self.login(self.example_email("hamlet"))
        result = self.client_patch('/json/users')
        self.assertEqual(result.status_code, 405)
        self.assert_in_response('Method Not Allowed', result)

    def test_options_method(self):
        # type: () -> None
        self.login(self.example_email("hamlet"))
        result = self.client_options('/json/users')
        self.assertEqual(result.status_code, 204)
        self.assertEqual(str(result['Allow']), 'GET, POST')

        result = self.client_options('/json/streams/15')
        self.assertEqual(result.status_code, 204)
        self.assertEqual(str(result['Allow']), 'DELETE, PATCH')

    def test_http_accept_redirect(self):
        # type: () -> None
        result = self.client_get('/json/users',
                                 HTTP_ACCEPT='text/html')
        self.assertEqual(result.status_code, 302)
        self.assertTrue(result["Location"].endswith("/login/?next=/json/users"))

class TestUserAgentParsing(ZulipTestCase):
    def test_user_agent_parsing(self):
        # type: () -> None
        """Test for our user agent parsing logic, using a large data set."""
        user_agents_parsed = defaultdict(int)  # type: Dict[str, int]
        user_agents_path = os.path.join(settings.DEPLOY_ROOT, "zerver/fixtures/user_agents_unique")
        parse_errors = []
        for line in open(user_agents_path).readlines():
            line = line.strip()
            match = re.match('^(?P<count>[0-9]+) "(?P<user_agent>.*)"$', line)
            self.assertIsNotNone(match)
            groupdict = match.groupdict()
            count = groupdict["count"]
            user_agent = groupdict["user_agent"]
            ret = parse_user_agent(user_agent)
            self.assertIsNotNone(ret)
            if ret is None:  # nocoverage
                parse_errors.append(line)
                continue
            user_agents_parsed[ret["name"]] += int(count)

        self.assertEqual(len(parse_errors), 0)
