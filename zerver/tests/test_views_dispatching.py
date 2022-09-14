import uuid
from contextlib import contextmanager
from typing import TYPE_CHECKING, Iterator
from unittest import mock, skipUnless

from django.conf import settings
from django.test.client import Client as TestClient
from django.utils.crypto import get_random_string

from zerver.decorator import authenticated_json_view, authenticated_rest_api_view, public_json_view
from zerver.lib.test_classes import ZulipTestCase

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as TestHttpResponse


class CsrfTestCase(ZulipTestCase):
    """
    Regular test suites are insufficient to verify if CSRF is correctly enabled or
    exempted for endpoints that use csrf_exempt or csrf_protect to override CSRF settings,
    since CSRF is disabled by default for the test client.
    """

    # Django by default disables csrf checks for the test client
    # For the purposes of testing it, we need to override client_class
    # to re-enable this feature
    client_class = lambda _: TestClient(enforce_csrf_checks=True)

    def assert_csrf_error(self, response: "TestHttpResponse") -> None:
        # "CSRF cookie not set" is the first error that Django raises in case CSRF is enabled when
        # the request does not carry the appropriate token. We test for this output to ensure that
        # CSRF is enforced.
        self.assert_json_error(response, "CSRF error: CSRF cookie not set.", status_code=403)

    @contextmanager
    def assert_csrf_logs(self) -> Iterator[None]:
        # See the comments above to see why we are capturing this particular log message.
        with self.assertLogs("django.security.csrf", level="WARN") as m:
            yield
        self.assertIn("WARNING:django.security.csrf:Forbidden (CSRF cookie not set.)", m.output[0])


class RestCsrfTests(CsrfTestCase):
    def test_exempt_from_csrf_authenticated_rest_api_view(self) -> None:
        with mock.patch(
            "zerver.lib.rest.authenticated_rest_api_view", wraps=authenticated_rest_api_view
        ) as m:
            result = self.api_post(
                self.example_user("othello"),
                "/api/v1/messages/render",
                dict(content="foo"),
            )
        m.assert_called_once()
        self.assert_json_success(result)

    def test_enforce_csrf_authenticated_json_view(self) -> None:
        # The test client has to be authenticated so that
        # csrf_protect applies to the tested view.
        self.login("hamlet")
        with self.assert_csrf_logs(), mock.patch(
            "zerver.lib.rest.authenticated_json_view", wraps=authenticated_json_view
        ) as m:
            result = self.client_post(
                "/json/messages/render",
                dict(content="foo"),
            )
        m.assert_called_once()
        self.assert_csrf_error(result)

    def test_enforce_csrf_public_json_view(self) -> None:
        with self.assert_csrf_logs(), mock.patch(
            "zerver.views.events_register.do_events_register", return_value={}
        ), mock.patch("zerver.lib.rest.public_json_view", wraps=public_json_view) as m:
            result = self.client_post("/json/register")
        m.assert_called_once()
        self.assert_csrf_error(result)


@skipUnless(settings.ZILENCER_ENABLED, "requires zilencer")
class RemoteServerCsrfTests(CsrfTestCase):
    def test_exempt_from_csrf_remote_server_view(self) -> None:
        self.login("hamlet")
        result = self.client_patch("/json/remotes/push/register")
        self.assertEqual(result.status_code, 405)
        self.assert_in_response("Method Not Allowed", result)

    def test_exempt_from_csrf_server_register_view(self) -> None:
        # We special case this particular view because it has csrf_exempt
        # applied directly on its view function
        zulip_org_id = str(uuid.uuid4())
        zulip_org_key = get_random_string(64)
        request = dict(
            zulip_org_id=zulip_org_id,
            zulip_org_key=zulip_org_key,
            hostname="example.com",
            contact_email="server-admin@example.com",
        )
        result = self.client_post("/api/v1/remotes/server/register", request)
        self.assert_json_success(result)


@skipUnless(settings.ZILENCER_ENABLED, "requires zilencer")
class RemoteServerViewTests(ZulipTestCase):
    def test_never_cache_responses(self) -> None:
        # We verify that default_never_cache_responses has been correctly applied to views
        # wrapped by remote_server_dispatch
        result = self.client_patch("/json/remotes/push/register")
        self.assertIn("Cache-Control", result)
        self.assertIn("no-cache", result["Cache-Control"])

    def test_exempt_default_cache_policy_server_register_view(self) -> None:
        zulip_org_id = str(uuid.uuid4())
        zulip_org_key = get_random_string(64)
        request = dict(
            zulip_org_id=zulip_org_id,
            zulip_org_key=zulip_org_key,
            hostname="example.com",
            contact_email="server-admin@example.com",
        )
        result = self.client_post("/api/v1/remotes/server/register", request)
        self.assertNotIn("Cache-Control", result)
        self.assert_json_success(result)
