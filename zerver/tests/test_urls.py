import importlib
import os
from typing import List
from unittest import mock

import django.urls.resolvers
from django.test import Client

from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.url_redirects import (
    API_DOCUMENTATION_REDIRECTS,
    HELP_DOCUMENTATION_REDIRECTS,
    LANDING_PAGE_REDIRECTS,
    POLICY_DOCUMENTATION_REDIRECTS,
)
from zerver.models import Stream
from zproject import urls
from zproject.backends import AUTH_BACKEND_NAME_MAP


class PublicURLTest(ZulipTestCase):
    """
    Account creation URLs are accessible even when not logged in. Authenticated
    URLs redirect to a page.
    """

    def fetch(self, method: str, urls: List[str], expected_status: int) -> None:
        for url in urls:
            # e.g. self.client_post(url) if method is "post"
            response = getattr(self, method)(url)
            self.assertEqual(
                response.status_code,
                expected_status,
                msg=f"Expected {expected_status}, received {response.status_code} for {method} to {url}",
            )

    def test_help_pages(self) -> None:
        # Test all files in help documentation directory (except for 'index.md',
        # 'missing.md' and `help/include/` files).

        help_urls = []
        for doc in os.listdir("./help/"):
            if doc.startswith(".") or "~" in doc or "#" in doc:
                continue  # nocoverage -- just here for convenience
            if doc in {"index.md", "include", "missing.md"}:
                continue
            url = "/help/" + os.path.splitext(doc)[0]  # Strip the extension.
            help_urls.append(url)

        # We have lots of help files, so this will be expensive!
        self.assertGreater(len(help_urls), 190)

        expected_tag = """<meta property="og:description" content="This is a help page" />"""

        for url in help_urls:
            with mock.patch(
                "zerver.lib.html_to_text.html_to_text", return_value="This is a help page"
            ) as m:
                response = self.client_get(url)
                m.assert_called_once()
                self.assertIn(expected_tag, response.content.decode())
                self.assertEqual(response.status_code, 200)

    def test_public_urls(self) -> None:
        """
        Test which views are accessible when not logged in.
        """
        # FIXME: We should also test the Tornado URLs -- this codepath
        # can't do so because this Django test mechanism doesn't go
        # through Tornado.
        denmark_stream_id = Stream.objects.get(name="Denmark").id
        get_urls = {
            200: [
                "/accounts/home/",
                "/accounts/login/",
                "/en/accounts/home/",
                "/ru/accounts/home/",
                "/en/accounts/login/",
                "/ru/accounts/login/",
                "/help/",
                # Since web-public streams are enabled in this `zulip`
                # instance, the public access experience is loaded directly.
                "/",
                "/en/",
                "/ru/",
            ],
            400: [
                "/json/messages",
            ],
            401: [
                f"/json/streams/{denmark_stream_id}/members",
                "/api/v1/users/me/subscriptions",
                "/api/v1/messages",
                "/api/v1/streams",
            ],
            404: [
                "/help/api-doc-template",
                "/help/nonexistent",
                "/help/include/admin",
                "/help/" + "z" * 1000,
            ],
        }

        post_urls = {
            200: ["/accounts/login/"],
            302: ["/accounts/logout/"],
            401: [
                "/json/messages",
                "/json/invites",
                "/json/subscriptions/exists",
                "/api/v1/users/me/subscriptions/properties",
                "/json/fetch_api_key",
                "/json/users/me/subscriptions",
                "/api/v1/users/me/subscriptions",
                "/json/export/realm",
            ],
            400: [
                "/api/v1/external/github",
                "/api/v1/fetch_api_key",
            ],
        }
        patch_urls = {
            401: ["/json/settings"],
        }

        for status_code, url_set in get_urls.items():
            self.fetch("client_get", url_set, status_code)
        for status_code, url_set in post_urls.items():
            self.fetch("client_post", url_set, status_code)
        for status_code, url_set in patch_urls.items():
            self.fetch("client_patch", url_set, status_code)

    def test_config_error_endpoints_dev_env(self) -> None:
        """
        The content of these pages is tested separately.
        Here we simply sanity-check that all the URLs load
        correctly.
        """
        auth_types = [auth.lower() for auth in AUTH_BACKEND_NAME_MAP]
        for auth in [
            "azuread",
            "email",
            "remoteuser",
            # The endpoint is generated dynamically based on the configuration of the OIDC backend,
            # so it can't be tested here.
            "openid connect",
        ]:  # We do not have configerror pages for AzureAD and Email.
            auth_types.remove(auth)

        auth_types += [
            "smtp",
            "remoteuser/remote_user_backend_disabled",
            "remoteuser/remote_user_header_missing",
        ]
        urls = [f"/config-error/{auth_type}" for auth_type in auth_types]
        with self.settings(DEVELOPMENT=True):
            for url in urls:
                response = self.client_get(url)
                self.assert_in_success_response(["Configuration error"], response)


class URLResolutionTest(ZulipTestCase):
    def check_function_exists(self, module_name: str, view: str) -> None:
        module = importlib.import_module(module_name)
        self.assertTrue(hasattr(module, view), f"View {module_name}.{view} does not exist")

    # Tests function-based views declared in urls.urlpatterns for
    # whether the function exists.  We at present do not test the
    # class-based views.
    def test_non_api_url_resolution(self) -> None:
        for pattern in urls.urlpatterns:
            if isinstance(pattern, django.urls.resolvers.URLPattern):
                (module_name, base_view) = pattern.lookup_str.rsplit(".", 1)
                self.check_function_exists(module_name, base_view)


class ErrorPageTest(ZulipTestCase):
    def test_bogus_http_host(self) -> None:
        # This tests that we've successfully worked around a certain bug in
        # Django's exception handling.  The enforce_csrf_checks=True,
        # secure=True, and HTTP_REFERER with an `https:` scheme are all
        # there to get us down just the right path for Django to blow up
        # when presented with an HTTP_HOST that's not a valid DNS name.
        client = Client(enforce_csrf_checks=True)
        result = client.post(
            "/json/users", secure=True, HTTP_REFERER="https://somewhere", HTTP_HOST="$nonsense"
        )
        self.assertEqual(result.status_code, 400)


class RedirectURLTest(ZulipTestCase):
    def test_api_redirects(self) -> None:
        for redirect in API_DOCUMENTATION_REDIRECTS:
            result = self.client_get(redirect.old_url, follow=True)
            self.assert_in_success_response(["Zulip homepage", "API documentation home"], result)

    def test_help_redirects(self) -> None:
        for redirect in HELP_DOCUMENTATION_REDIRECTS:
            result = self.client_get(redirect.old_url, follow=True)
            self.assert_in_success_response(["Zulip homepage", "Help center home"], result)

    def test_policy_redirects(self) -> None:
        for redirect in POLICY_DOCUMENTATION_REDIRECTS:
            result = self.client_get(redirect.old_url, follow=True)
            self.assert_in_success_response(["Policies", "Archive"], result)

    def test_landing_page_redirects(self) -> None:
        for redirect in LANDING_PAGE_REDIRECTS:
            result = self.client_get(redirect.old_url, follow=True)
            self.assert_in_success_response(["Download"], result)

            result = self.client_get(redirect.old_url)
            self.assertEqual(result.status_code, 301)
            self.assertIn(redirect.new_url, result["Location"])
