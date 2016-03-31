# -*- coding: utf-8 -*-
from __future__ import absolute_import

from django.test import TestCase
from django.conf import settings
from http.cookies import SimpleCookie


class TranslationTestCase(TestCase):
    """
    Tranlations strings should change with locale. URLs should be locale
    aware.
    """

    def fetch(self, method, url, expected_status, **kwargs):
        # e.g. self.client.post(url) if method is "post"
        response = getattr(self.client, method)(url, **kwargs)
        self.assertEqual(response.status_code, expected_status,
                         msg="Expected %d, received %d for %s to %s" % (
                expected_status, response.status_code, method, url))
        return response

    def test_accept_language_header(self):
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
        languages = [('en', 'Register'),
                     ('de', 'Registrieren'),
                     ('sr', 'Региструј се'),
                     ('zh-cn', '注册'),
                     ]

        for lang, word in languages:
            response = self.fetch('get', '/{}/integrations/'.format(lang), 200)
            self.assertTrue(word in response.content)
