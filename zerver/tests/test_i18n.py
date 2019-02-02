# -*- coding: utf-8 -*-

from typing import Any

import mock
import ujson
from django.test import TestCase
from django.utils import translation
from django.conf import settings
from django.http import HttpResponse
from django.core import mail
from http.cookies import SimpleCookie

from zerver.models import get_realm_stream
from zerver.lib.test_classes import (
    ZulipTestCase,
)
from zerver.management.commands import makemessages
from zerver.lib.notifications import enqueue_welcome_emails

class EmailTranslationTestCase(ZulipTestCase):
    def test_email_translation(self) -> None:
        def check_translation(phrase: str, request_type: str, *args: Any, **kwargs: Any) -> None:
            if request_type == "post":
                self.client_post(*args, **kwargs)
            elif request_type == "patch":  # nocoverage: see comment below
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
        self.login(hamlet.email)

        # TODO: Uncomment and replace with translation once we have German translations for the strings
        # in confirm_new_email.txt.
        # Also remove the "nocoverage" from check_translation above.
        # check_translation("Viele Grüße", "patch", "/json/settings", {"email": "hamlets-new@zulip.com"})
        check_translation("Incrível!", "post", "/accounts/home/", {"email": "new-email@zulip.com"}, HTTP_ACCEPT_LANGUAGE="pt")
        check_translation("Danke, dass Du", "post", '/accounts/find/', {'emails': hamlet.email})
        check_translation("Hallo", "post", "/json/invites",  {"invitee_emails": "new-email@zulip.com",
                                                              "stream_ids": ujson.dumps([stream.id])})

        with self.settings(DEVELOPMENT_LOG_EMAILS=True):
            enqueue_welcome_emails(hamlet)
        check_translation("Viele Grüße", "")

class TranslationTestCase(ZulipTestCase):
    """
    Tranlations strings should change with locale. URLs should be locale
    aware.
    """

    def tearDown(self) -> None:
        translation.activate(settings.LANGUAGE_CODE)

    # e.g. self.client_post(url) if method is "post"
    def fetch(self, method: str, url: str, expected_status: int, **kwargs: Any) -> HttpResponse:
        response = getattr(self.client, method)(url, **kwargs)
        self.assertEqual(response.status_code, expected_status,
                         msg="Expected %d, received %d for %s to %s" % (
                             expected_status, response.status_code, method, url))
        return response

    def test_accept_language_header(self) -> None:
        languages = [('en', u'Sign up'),
                     ('de', u'Registrieren'),
                     ('sr', u'Упишите се'),
                     ('zh-hans', u'注册'),
                     ]

        for lang, word in languages:
            response = self.fetch('get', '/integrations/', 200,
                                  HTTP_ACCEPT_LANGUAGE=lang)
            self.assert_in_response(word, response)

    def test_cookie(self) -> None:
        languages = [('en', u'Sign up'),
                     ('de', u'Registrieren'),
                     ('sr', u'Упишите се'),
                     ('zh-hans', u'注册'),
                     ]

        for lang, word in languages:
            # Applying str function to LANGUAGE_COOKIE_NAME to convert unicode
            # into an ascii otherwise SimpleCookie will raise an exception
            self.client.cookies = SimpleCookie({str(settings.LANGUAGE_COOKIE_NAME): lang})  # type: ignore # https://github.com/python/typeshed/issues/1476

            response = self.fetch('get', '/integrations/', 200)
            self.assert_in_response(word, response)

    def test_i18n_urls(self) -> None:
        languages = [('en', u'Sign up'),
                     ('de', u'Registrieren'),
                     ('sr', u'Упишите се'),
                     ('zh-hans', u'注册'),
                     ]

        for lang, word in languages:
            response = self.fetch('get', '/{}/integrations/'.format(lang), 200)
            self.assert_in_response(word, response)


class JsonTranslationTestCase(ZulipTestCase):
    def tearDown(self) -> None:
        translation.activate(settings.LANGUAGE_CODE)

    @mock.patch('zerver.lib.request._')
    def test_json_error(self, mock_gettext: Any) -> None:
        dummy_value = "this arg is bad: '{var_name}' (translated to German)"
        mock_gettext.return_value = dummy_value

        email = self.example_email('hamlet')
        self.login(email)
        result = self.client_post("/json/invites",
                                  HTTP_ACCEPT_LANGUAGE='de')

        expected_error = u"this arg is bad: 'invitee_emails' (translated to German)"
        self.assert_json_error_contains(result,
                                        expected_error,
                                        status_code=400)

    @mock.patch('zerver.views.auth._')
    def test_jsonable_error(self, mock_gettext: Any) -> None:
        dummy_value = "Some other language"
        mock_gettext.return_value = dummy_value

        email = self.example_email('hamlet')
        self.login(email)
        result = self.client_get("/de/accounts/login/jwt/")

        self.assert_json_error_contains(result,
                                        dummy_value,
                                        status_code=400)


class FrontendRegexTestCase(TestCase):
    def test_regexes(self) -> None:
        command = makemessages.Command()

        data = [
            ('{{#tr context}}english text with __variable__{{/tr}}{{/tr}}',
             'english text with __variable__'),

            ('{{t "english text" }}, "extra"}}',
             'english text'),

            ("{{t 'english text' }}, 'extra'}}",
             'english text'),

            ('i18n.t("english text"), "extra",)',
             'english text'),

            ('i18n.t("english text", context), "extra",)',
             'english text'),

            ("i18n.t('english text'), 'extra',)",
             'english text'),

            ("i18n.t('english text', context), 'extra',)",
             'english text'),
        ]

        for input_text, expected in data:
            result = command.extract_strings(input_text)
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0], expected)
