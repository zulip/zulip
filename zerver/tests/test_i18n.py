# -*- coding: utf-8 -*-
from __future__ import absolute_import

from typing import Any

import mock
from django.test import TestCase
from django.conf import settings
from django.http import HttpResponse
from http.cookies import SimpleCookie

from zerver.lib.test_helpers import AuthedTestCase


class TranslationTestCase(TestCase):
    """
    Tranlations strings should change with locale. URLs should be locale
    aware.
    """

    # e.g. self.client.post(url) if method is "post"
    def fetch(self, method, url, expected_status, **kwargs):
        # type: (str, str, int, **Any) -> HttpResponse
        response = getattr(self.client, method)(url, **kwargs)
        self.assertEqual(response.status_code, expected_status,
                         msg="Expected %d, received %d for %s to %s" % (
                expected_status, response.status_code, method, url))
        return response

    def test_accept_language_header(self):
        # type: () -> None
        languages = [('en', 'Register'),
                     ('de', 'Registrieren'),
                     ('sr', 'Региструј се'),
                     ('zh-cn', '注册'),
                     ]

        for lang, word in languages:
            response = self.fetch('get', '/integrations/', 200,
                                  HTTP_ACCEPT_LANGUAGE=lang)
            self.assertTrue(word in response.content)

    def test_cookie(self):
        # type: () -> None
        languages = [('en', 'Register'),
                     ('de', 'Registrieren'),
                     ('sr', 'Региструј се'),
                     ('zh-cn', '注册'),
                     ]

        for lang, word in languages:
            self.client.cookies = SimpleCookie({settings.LANGUAGE_COOKIE_NAME: lang})

            response = self.fetch('get', '/integrations/', 200)
            self.assertTrue(word in response.content)

    def test_i18n_urls(self):
        # type: () -> None
        languages = [('en', 'Register'),
                     ('de', 'Registrieren'),
                     ('sr', 'Региструј се'),
                     ('zh-cn', '注册'),
                     ]

        for lang, word in languages:
            response = self.fetch('get', '/{}/integrations/'.format(lang), 200)
            self.assertTrue(word in response.content)


class JsonTranslationTestCase(AuthedTestCase):
    @mock.patch('zerver.lib.request._')
    def test_json_error(self, mock_gettext):
        dummy_value = "Some other language '%s'"
        mock_gettext.return_value = dummy_value

        self.login("hamlet@zulip.com")
        result = self.client.post("/json/refer_friend",
                                  HTTP_ACCEPT_LANGUAGE='de')

        self.assert_json_error_contains(result,
                                        dummy_value % 'email',
                                        status_code=400)

    @mock.patch('zerver.views._')
    def test_jsonable_error(self, mock_gettext):
        dummy_value = "Some other language"
        mock_gettext.return_value = dummy_value

        self.login("hamlet@zulip.com")
        result = self.client.get("/de/accounts/login/jwt/")

        self.assert_json_error_contains(result,
                                        dummy_value,
                                        status_code=400)
