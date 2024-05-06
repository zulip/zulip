from http.cookies import SimpleCookie
from typing import TYPE_CHECKING, Any
from unittest import mock

import orjson
from django.conf import settings
from django.core import mail
from django.utils import translation
from typing_extensions import override

from zerver.lib.email_notifications import enqueue_welcome_emails
from zerver.lib.i18n import get_browser_language_code
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import HostRequestMock
from zerver.management.commands import makemessages
from zerver.models.streams import get_realm_stream

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as TestHttpResponse


class EmailTranslationTestCase(ZulipTestCase):
    def test_email_translation(self) -> None:
        def check_translation(phrase: str, request_type: str, *args: Any, **kwargs: Any) -> None:
            with self.captureOnCommitCallbacks(execute=True):
                if request_type == "post":
                    self.client_post(*args, **kwargs)
                elif request_type == "patch":
                    self.client_patch(*args, **kwargs)

            email_message = mail.outbox[0]
            self.assertIn(phrase, email_message.body)

            for i in range(len(mail.outbox)):
                mail.outbox.pop()

        hamlet = self.example_user("hamlet")
        hamlet.default_language = "de"
        hamlet.save()
        realm = hamlet.realm
        realm.default_language = "de"
        realm.save()
        stream = get_realm_stream("Denmark", realm.id)
        invite_expires_in_minutes = 2 * 24 * 60
        self.login_user(hamlet)

        check_translation(
            "Wir haben eine Anfrage erhalten",
            "patch",
            "/json/settings",
            {"email": "hamlets-new@zulip.com"},
        )
        check_translation(
            "Incrível!",
            "post",
            "/accounts/home/",
            {"email": "new-email@zulip.com"},
            HTTP_ACCEPT_LANGUAGE="pt",
        )
        check_translation("Danke für", "post", "/accounts/find/", {"emails": hamlet.delivery_email})
        check_translation(
            "Hallo",
            "post",
            "/json/invites",
            {
                "invitee_emails": "new-email@zulip.com",
                "stream_ids": orjson.dumps([stream.id]).decode(),
                "invite_expires_in_minutes": invite_expires_in_minutes,
            },
        )

        with self.settings(DEVELOPMENT_LOG_EMAILS=True):
            enqueue_welcome_emails(hamlet)
        check_translation("Hier findest du einige Tipps", "")


class TranslationTestCase(ZulipTestCase):
    """
    Translations strings should change with locale. URLs should be locale
    aware.
    """

    @override
    def tearDown(self) -> None:
        translation.activate(settings.LANGUAGE_CODE)
        super().tearDown()

    # e.g. self.client_post(url) if method is "post"
    def fetch(
        self, method: str, url: str, expected_status: int, **kwargs: Any
    ) -> "TestHttpResponse":
        response = getattr(self, f"client_{method}")(url, **kwargs)
        self.assertEqual(
            response.status_code,
            expected_status,
            msg=f"Expected {expected_status}, received {response.status_code} for {method} to {url}",
        )
        return response

    def test_accept_language_header(self) -> None:
        languages = [
            ("en", "Sign up"),
            ("de", "Registrieren"),
            ("sr", "Региструјте се"),
            ("zh-hans", "注册"),
        ]

        for lang, word in languages:
            response = self.fetch("get", "/integrations/", 200, HTTP_ACCEPT_LANGUAGE=lang)
            self.assert_in_response(word, response)

    def test_cookie(self) -> None:
        languages = [
            ("en", "Sign up"),
            ("de", "Registrieren"),
            ("sr", "Региструјте се"),
            ("zh-hans", "注册"),
        ]

        for lang, word in languages:
            # Applying str function to LANGUAGE_COOKIE_NAME to convert Unicode
            # into an ascii otherwise SimpleCookie will raise an exception
            self.client.cookies = SimpleCookie({str(settings.LANGUAGE_COOKIE_NAME): lang})

            response = self.fetch("get", "/integrations/", 200)
            self.assert_in_response(word, response)

    def test_i18n_urls(self) -> None:
        languages = [
            ("en", "Sign up"),
            ("de", "Registrieren"),
            ("sr", "Региструјте се"),
            ("zh-hans", "注册"),
        ]

        for lang, word in languages:
            response = self.fetch("get", f"/{lang}/integrations/", 200)
            self.assert_in_response(word, response)

    def test_get_browser_language_code(self) -> None:
        req = HostRequestMock()
        self.assertIsNone(get_browser_language_code(req))

        req = HostRequestMock()
        req.META["HTTP_ACCEPT_LANGUAGE"] = "de"
        self.assertEqual(get_browser_language_code(req), "de")

        req = HostRequestMock()
        req.META["HTTP_ACCEPT_LANGUAGE"] = "en-GB,en;q=0.8"
        self.assertEqual(get_browser_language_code(req), "en-gb")

        # Case when unsupported language has higher weight.
        req = HostRequestMock()
        req.META["HTTP_ACCEPT_LANGUAGE"] = "en-IND;q=0.9,de;q=0.8"
        self.assertEqual(get_browser_language_code(req), "de")

        # Browser locale is set to unsupported language.
        req = HostRequestMock()
        req.META["HTTP_ACCEPT_LANGUAGE"] = "en-IND"
        self.assertIsNone(get_browser_language_code(req))

        req = HostRequestMock()
        req.META["HTTP_ACCEPT_LANGUAGE"] = "*"
        self.assertIsNone(get_browser_language_code(req))


class JsonTranslationTestCase(ZulipTestCase):
    @override
    def tearDown(self) -> None:
        translation.activate(settings.LANGUAGE_CODE)
        super().tearDown()

    @mock.patch("zerver.lib.request._")
    def test_json_error(self, mock_gettext: Any) -> None:
        dummy_value = "this arg is bad: '{var_name}' (translated to German)"
        mock_gettext.return_value = dummy_value

        self.login("hamlet")
        result = self.client_post("/json/invites", HTTP_ACCEPT_LANGUAGE="de")

        expected_error = "this arg is bad: 'invitee_emails' (translated to German)"
        self.assert_json_error_contains(result, expected_error, status_code=400)

    @mock.patch("zerver.views.auth._")
    def test_jsonable_error(self, mock_gettext: Any) -> None:
        dummy_value = "Some other language"
        mock_gettext.return_value = dummy_value

        self.login("hamlet")
        result = self.client_post("/de/accounts/login/jwt/")

        self.assert_json_error_contains(result, dummy_value, status_code=400)


class FrontendRegexTestCase(ZulipTestCase):
    def test_regexes(self) -> None:
        command = makemessages.Command()

        data = [
            (
                "{{#tr}}english text with {variable}{{/tr}}{{/tr}}",
                "english text with {variable}",
            ),
            ('{{t "english text" }}, "extra"}}', "english text"),
            ("{{t 'english text' }}, 'extra'}}", "english text"),
            ("{{> template var=(t 'english text') }}, 'extra'}}", "english text"),
        ]

        for input_text, expected in data:
            result = command.extract_strings(input_text)
            self.assert_length(result, 1)
            self.assertEqual(result[0], expected)
