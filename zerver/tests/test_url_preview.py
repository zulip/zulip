import json
from typing import TYPE_CHECKING, Any

import requests
import responses
from django.test import override_settings
from typing_extensions import override

from zerver.lib.test_classes import ZulipTestCase
from zerver.openapi.openapi import validate_against_openapi_schema

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as TestHttpResponse

GITHUB_API_URL = "https://api.github.com/repos/zulip/zulip/issues/{number}"


class UrlPreviewTest(ZulipTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        self.login("hamlet")

    def add_github_response(self, number: str, json_data: dict[str, Any], status: int = 200) -> str:
        api_url = GITHUB_API_URL.format(number=number)
        responses.add(responses.GET, api_url, json=json_data, status=status)
        return api_url

    def url_preview(
        self, number: str, *, platform: str = "github", owner: str = "zulip", repo: str = "zulip"
    ) -> "TestHttpResponse":
        # The Markdown renderer parses these out of the link and attaches them
        # to the anchor; the client then sends them here (see test_markdown.py
        # for the parsing/tagging side).
        return self.client_get(
            "/json/url_preview",
            {"platform": platform, "owner": owner, "repo": repo, "number": number},
        )

    @responses.activate
    def test_github_issue_preview(self) -> None:
        self.add_github_response(
            "19710",
            {
                "title": "Show titles (previews) of GitHub issues on hover",
                "user": {"login": "alya"},
                "state": "open",
                "state_reason": None,
            },
        )
        data = self.assert_json_success(self.url_preview("19710"))
        self.assertEqual(data["platform"], "github")
        self.assertEqual(data["type"], "issue")
        self.assertEqual(data["owner"], "zulip")
        self.assertEqual(data["repo"], "zulip")
        self.assertEqual(data["number"], "19710")
        self.assertEqual(data["title"], "Show titles (previews) of GitHub issues on hover")
        self.assertEqual(data["author"], "alya")
        self.assertEqual(data["state"], "open")
        self.assertEqual(data["state_reason"], None)
        # Issue responses don't carry pull-request-only fields.
        self.assertNotIn("draft", data)
        self.assertNotIn("merged_at", data)
        validate_against_openapi_schema(data, "/url_preview", "get", "200")

    @responses.activate
    def test_github_closed_issue_with_state_reason(self) -> None:
        self.add_github_response(
            "100",
            {
                "title": "Completed work",
                "user": {"login": "tabbott"},
                "state": "closed",
                "state_reason": "completed",
            },
        )
        data = self.assert_json_success(self.url_preview("100"))
        self.assertEqual(data["state"], "closed")
        self.assertEqual(data["state_reason"], "completed")

    @responses.activate
    def test_github_open_pull_request_preview(self) -> None:
        self.add_github_response(
            "22368",
            {
                "title": "Feat: Show titles of GitHub issues on hover.",
                "user": {"login": "brijsiyag"},
                "state": "open",
                "draft": False,
                "pull_request": {"merged_at": None},
            },
        )
        data = self.assert_json_success(self.url_preview("22368"))
        self.assertEqual(data["type"], "pull_request")
        self.assertEqual(data["state"], "open")
        self.assertEqual(data["draft"], False)
        self.assertEqual(data["merged_at"], None)
        self.assertEqual(data["author"], "brijsiyag")
        # Pull request responses don't carry the issue-only field.
        self.assertNotIn("state_reason", data)
        validate_against_openapi_schema(data, "/url_preview", "get", "200")

    @responses.activate
    def test_github_draft_pull_request(self) -> None:
        self.add_github_response(
            "30001",
            {
                "title": "WIP",
                "user": {"login": "x"},
                "state": "open",
                "draft": True,
                "pull_request": {"merged_at": None},
            },
        )
        data = self.assert_json_success(self.url_preview("30001"))
        self.assertEqual(data["draft"], True)

    @responses.activate
    def test_github_merged_pull_request(self) -> None:
        self.add_github_response(
            "30000",
            {
                "title": "Merged work",
                "user": {"login": "timabbott"},
                "state": "closed",
                "draft": False,
                "pull_request": {"merged_at": "2026-01-01T00:00:00Z"},
            },
        )
        data = self.assert_json_success(self.url_preview("30000"))
        self.assertEqual(data["state"], "closed")
        self.assertEqual(data["merged_at"], "2026-01-01T00:00:00Z")

    @responses.activate
    def test_invalid_params_are_not_previewable(self) -> None:
        # These are rejected before any GitHub request; `responses` is active
        # with no mocks, so a stray outgoing request would fail the test.
        for params in [
            {"number": "1", "platform": "gitlab"},  # unsupported platform
            {"number": "notanumber"},  # non-numeric number
            {"number": "1", "owner": "../etc"},  # owner with illegal characters
            {"number": "1", "repo": "zulip/evil"},  # repo with illegal characters
            {"number": "1", "owner": "-bad"},  # owner can't start with a hyphen
            {"number": "1", "owner": "dotted.owner"},  # owners can't contain dots
            {"number": "1", "repo": "."},  # bare dot-segment repo
            {"number": "1", "repo": ".."},  # repo that would walk the API path
        ]:
            result = self.url_preview(**params)
            self.assert_json_error(result, "URL is not previewable.")
            self.assertEqual(result.json()["code"], "REQUEST_VARIABLE_INVALID")

    @responses.activate
    def test_github_404_returns_invalid_or_expired(self) -> None:
        self.add_github_response("2", {"message": "Not Found"}, status=404)
        self.assert_json_error(self.url_preview("2"), "Invalid or expired URL.")

    @responses.activate
    def test_github_api_error_is_logged(self) -> None:
        api_url = self.add_github_response("3", {"message": "Forbidden"}, status=403)
        with self.assertLogs("zerver.lib.github", level="WARNING") as logs:
            result = self.url_preview("3")
        self.assert_json_error(result, "Unable to fetch data from GitHub.")
        self.assert_length(logs.output, 1)
        self.assertIn(f"Unable to fetch GitHub preview data from {api_url}:", logs.output[0])

    @responses.activate
    def test_github_network_error_is_logged(self) -> None:
        responses.add(
            responses.GET, GITHUB_API_URL.format(number="5"), body=requests.ConnectionError("boom")
        )
        with self.assertLogs("zerver.lib.github", level="WARNING") as logs:
            result = self.url_preview("5")
        self.assert_json_error(result, "Unable to fetch data from GitHub.")
        self.assert_length(logs.output, 1)

    @override_settings(GITHUB_API_AUTH_TOKEN="public-scope-token")
    @responses.activate
    def test_auth_token_is_sent_when_configured(self) -> None:
        def callback(request: requests.PreparedRequest) -> tuple[int, dict[str, str], str]:
            self.assertEqual(request.headers.get("Authorization"), "Bearer public-scope-token")
            return (
                200,
                {},
                json.dumps(
                    {"title": "x", "user": {"login": "y"}, "state": "open", "state_reason": None}
                ),
            )

        responses.add_callback(
            responses.GET,
            GITHUB_API_URL.format(number="7"),
            callback=callback,
            content_type="application/json",
        )
        data = self.assert_json_success(self.url_preview("7"))
        self.assertEqual(data["title"], "x")

    @responses.activate
    def test_results_are_cached(self) -> None:
        # A distinct number keeps this isolated from other tests' cache entries.
        api_url = self.add_github_response(
            "424242",
            {"title": "Cache me", "user": {"login": "z"}, "state": "open", "state_reason": None},
        )
        first = self.assert_json_success(self.url_preview("424242"))
        responses.assert_call_count(api_url, 1)
        second = self.assert_json_success(self.url_preview("424242"))
        # The second hover is served from cache: no additional GitHub request.
        responses.assert_call_count(api_url, 1)
        self.assertEqual(first, second)

    @responses.activate
    def test_nonexistent_issue_or_pr_is_cached(self) -> None:
        # A 404 is a stable negative, so it's cached too: repeatedly hovering a
        # broken link must not keep hitting GitHub and burning the rate limit.
        api_url = self.add_github_response("525252", {"message": "Not Found"}, status=404)
        self.assert_json_error(self.url_preview("525252"), "Invalid or expired URL.")
        responses.assert_call_count(api_url, 1)
        self.assert_json_error(self.url_preview("525252"), "Invalid or expired URL.")
        responses.assert_call_count(api_url, 1)

    @responses.activate
    def test_transient_error_is_not_cached(self) -> None:
        # Rate-limit/5xx/network errors can clear quickly, so they must not be
        # cached as negatives; each hover retries the fetch.
        api_url = self.add_github_response("626262", {"message": "Forbidden"}, status=403)
        with self.assertLogs("zerver.lib.github", level="WARNING"):
            self.assert_json_error(self.url_preview("626262"), "Unable to fetch data from GitHub.")
        responses.assert_call_count(api_url, 1)
        with self.assertLogs("zerver.lib.github", level="WARNING"):
            self.assert_json_error(self.url_preview("626262"), "Unable to fetch data from GitHub.")
        responses.assert_call_count(api_url, 2)

    @responses.activate
    def test_unexpected_response_shape_is_handled(self) -> None:
        # A 200 whose body lacks the fields we read shouldn't 500; it degrades
        # to a normal fetch error.
        self.add_github_response("727272", {"unexpected": "shape"})
        with self.assertLogs("zerver.lib.github", level="WARNING") as logs:
            self.assert_json_error(self.url_preview("727272"), "Unable to fetch data from GitHub.")
        self.assert_length(logs.output, 1)
        self.assertIn("Unexpected GitHub preview response from", logs.output[0])

    def test_requires_login(self) -> None:
        # The endpoint is for logged-in users only; spectators get no preview.
        self.logout()
        result = self.url_preview("1")
        self.assert_json_error(
            result,
            "Not logged in: API authentication or user session required",
            status_code=401,
        )
