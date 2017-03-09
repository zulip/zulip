# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import print_function

import importlib
import os
import six
import ujson

import django.core.urlresolvers
from django.test import TestCase
from typing import List, Optional

from zerver.lib.test_classes import ZulipTestCase
from zerver.models import Stream
from zproject import urls

class PublicURLTest(ZulipTestCase):
    """
    Account creation URLs are accessible even when not logged in. Authenticated
    URLs redirect to a page.
    """

    def fetch(self, method, urls, expected_status):
        # type: (str, List[str], int) -> None
        for url in urls:
            # e.g. self.client_post(url) if method is "post"
            response = getattr(self, method)(url)
            self.assertEqual(response.status_code, expected_status,
                             msg="Expected %d, received %d for %s to %s" % (
                                 expected_status, response.status_code, method, url))

    def test_public_urls(self):
        # type: () -> None
        """
        Test which views are accessible when not logged in.
        """
        # FIXME: We should also test the Tornado URLs -- this codepath
        # can't do so because this Django test mechanism doesn't go
        # through Tornado.
        denmark_stream_id = Stream.objects.get(name='Denmark').id
        get_urls = {200: ["/accounts/home/", "/accounts/login/"
                          "/en/accounts/home/", "/ru/accounts/home/",
                          "/en/accounts/login/", "/ru/accounts/login/",
                          "/help/"],
                    302: ["/", "/en/", "/ru/"],
                    401: ["/json/streams/%d/members" % (denmark_stream_id,),
                          "/api/v1/users/me/subscriptions",
                          "/api/v1/messages",
                          "/json/messages",
                          "/api/v1/streams",
                          ],
                    404: ["/help/nonexistent"],
                    }

        # Add all files in 'templates/zerver/help' directory (except for 'main.html' and
        # 'index.md') to `get_urls['200']` list.
        for doc in os.listdir('./templates/zerver/help'):
            if doc.startswith(".") or '~' in doc or '#' in doc:
                continue  # nocoverage -- just here for convenience
            if doc not in {'main.html', 'index.md', 'include'}:
                get_urls[200].append('/help/' + os.path.splitext(doc)[0]) # Strip the extension.

        post_urls = {200: ["/accounts/login/"],
                     302: ["/accounts/logout/"],
                     401: ["/json/messages",
                           "/json/invite_users",
                           "/json/settings/change",
                           "/json/subscriptions/exists",
                           "/json/subscriptions/property",
                           "/json/fetch_api_key",
                           "/json/users/me/pointer",
                           "/json/users/me/subscriptions",
                           "/api/v1/users/me/subscriptions",
                           ],
                     400: ["/api/v1/external/github",
                           "/api/v1/fetch_api_key",
                           ],
                     }
        put_urls = {401: ["/json/users/me/pointer"],
                    }
        for status_code, url_set in six.iteritems(get_urls):
            self.fetch("client_get", url_set, status_code)
        for status_code, url_set in six.iteritems(post_urls):
            self.fetch("client_post", url_set, status_code)
        for status_code, url_set in six.iteritems(put_urls):
            self.fetch("client_put", url_set, status_code)

    def test_get_gcid_when_not_configured(self):
        # type: () -> None
        with self.settings(GOOGLE_CLIENT_ID=None):
            resp = self.client_get("/api/v1/fetch_google_client_id")
            self.assertEqual(400, resp.status_code,
                             msg="Expected 400, received %d for GET /api/v1/fetch_google_client_id" % (
                                 resp.status_code,))
            data = ujson.loads(resp.content)
            self.assertEqual('error', data['result'])

    def test_get_gcid_when_configured(self):
        # type: () -> None
        with self.settings(GOOGLE_CLIENT_ID="ABCD"):
            resp = self.client_get("/api/v1/fetch_google_client_id")
            self.assertEqual(200, resp.status_code,
                             msg="Expected 200, received %d for GET /api/v1/fetch_google_client_id" % (
                                 resp.status_code,))
            data = ujson.loads(resp.content)
            self.assertEqual('success', data['result'])
            self.assertEqual('ABCD', data['google_client_id'])

class URLResolutionTest(TestCase):
    def get_callback_string(self, pattern):
        # type: (django.core.urlresolvers.RegexURLPattern) -> Optional[str]
        callback_str = hasattr(pattern, 'lookup_str') and 'lookup_str'
        callback_str = callback_str or '_callback_str'
        return getattr(pattern, callback_str, None)

    def check_function_exists(self, module_name, view):
        # type: (str, str) -> None
        module = importlib.import_module(module_name)
        self.assertTrue(hasattr(module, view), "View %s.%s does not exist" % (module_name, view))

    # Tests that all views in urls.v1_api_and_json_patterns exist
    def test_rest_api_url_resolution(self):
        # type: () -> None
        for pattern in urls.v1_api_and_json_patterns:
            callback_str = self.get_callback_string(pattern)
            if callback_str and hasattr(pattern, "default_args"):
                for func_string in pattern.default_args.values():
                    module_name, view = func_string.rsplit('.', 1)
                    self.check_function_exists(module_name, view)

    # Tests function-based views declared in urls.urlpatterns for
    # whether the function exists.  We at present do not test the
    # class-based views.
    def test_non_api_url_resolution(self):
        # type: () -> None
        for pattern in urls.urlpatterns:
            callback_str = self.get_callback_string(pattern)
            if callback_str:
                (module_name, base_view) = callback_str.rsplit(".", 1)
                self.check_function_exists(module_name, base_view)
