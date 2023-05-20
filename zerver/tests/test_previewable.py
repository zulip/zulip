import json
from typing import Dict, Tuple

import requests
import responses
from django.test import override_settings

from zerver.lib.test_classes import ZulipTestCase


class TestPreviewable(ZulipTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.login("hamlet")

    def auth_request_callback(
        self, request: requests.PreparedRequest
    ) -> Tuple[int, Dict[str, str], str]:
        response_data = {
            "title": "Feat: Show titles of GitHub issues on hover fixes: #19710.",
            "user": {"login": "brijsiyag"},
            "state": "open",
            "draft": False,
            "pull_request": {
                "merged_at": None,
            },
        }
        if (
            request.headers.get("Authorization", None)
            == "token 3608bca1e44ea6c4d268eb6db02260269892c0"
        ):
            return (200, {}, json.dumps(response_data))
        return (403, {}, json.dumps({}))

    @override_settings(GITHUB_API_AUTH_TOKEN="3608bca1e44ea6c4d268eb6db02260269892c0")
    @responses.activate()
    def test_github_auth(self) -> None:
        responses.add_callback(
            responses.GET,
            "https://api.github.com/repos/zulip/zulip/issues/22368",
            callback=self.auth_request_callback,
            content_type="application/json",
        )
        result = self.client_post(
            "/json/previewable", {"url": "https://github.com/zulip/zulip/pull/22368"}
        )
        self.assertEqual(result.status_code, 200)

    @responses.activate()
    def test_github_without_auth(self) -> None:
        api_url = "https://api.github.com/repos/zulip/zulip/issues/22368"
        responses.add_callback(
            responses.GET,
            api_url,
            callback=self.auth_request_callback,
            content_type="application/json",
        )
        with self.assertLogs("zerver.lib.github", level="WARNING") as error_log:
            result = self.client_post(
                "/json/previewable", {"url": "https://github.com/zulip/zulip/pull/22368"}
            )
            self.assertEqual(result.status_code, 400)
            self.assert_json_error(result, "Unable to fetch data from github.")
            self.assertIn(
                f"WARNING:zerver.lib.github:Unable to fetch data from gitHub: 403 Client Error: Forbidden for url: {api_url}",
                error_log.output[0],
            )

    @responses.activate()
    def test_get_github_issue_data(self) -> None:
        response_data = {
            "title": "Show titles of GitHub issues on hover",
            "user": {"login": "brijsiyag"},
            "state": "closed",
            "state_reason": None,
        }
        responses.add(
            responses.GET,
            "https://api.github.com/repos/zulip/zulip/issues/19710",
            json=response_data,
        )
        result = self.client_post(
            "/json/previewable", {"url": "https://github.com/zulip/zulip/issues/19710"}
        )
        self.assert_json_success(result)
        result = result.json()
        self.assertEqual(result["platform"], "github")
        self.assertEqual(result["type"], "issue")
        self.assertEqual(result["owner"], "zulip")
        self.assertEqual(result["repo"], "zulip")
        self.assertEqual(result["issue_number"], "19710")
        self.assertEqual(result["author"], "brijsiyag")
        self.assertEqual(result["title"], "Show titles of GitHub issues on hover")

    @responses.activate()
    def test_get_github_pull_data(self) -> None:
        response_data = {
            "title": "Feat: Show titles of GitHub issues on hover fixes: #19710.",
            "user": {"login": "brijsiyag"},
            "state": "open",
            "draft": False,
            "pull_request": {
                "merged_at": None,
            },
        }
        responses.add(
            responses.GET,
            "https://api.github.com/repos/zulip/zulip/issues/22368",
            json=response_data,
        )
        result = self.client_post(
            "/json/previewable", {"url": "https://github.com/zulip/zulip/pull/22368"}
        )
        self.assert_json_success(result)
        result = result.json()
        self.assertEqual(result["platform"], "github")
        self.assertEqual(result["type"], "pull_request")
        self.assertEqual(result["owner"], "zulip")
        self.assertEqual(result["repo"], "zulip")
        self.assertEqual(result["issue_number"], "22368")
        self.assertEqual(result["state"], "open")
        self.assertEqual(result["draft"], False)
        self.assertEqual(result["author"], "brijsiyag")
        self.assertEqual(
            result["title"], "Feat: Show titles of GitHub issues on hover fixes: #19710."
        )
        self.assertEqual(result["merged_at"], None)

    def test_not_previewable_url(self) -> None:
        result = self.client_post(
            "/json/previewable", {"url": "https://github.com/zulip/xyz/zulip/issues/3"}
        )
        self.assert_json_error(result, msg="URL is not previewable.")

    def test_not_url(self) -> None:
        result = self.client_post(
            "/json/previewable", {"url": "https://github.com[/zulip/xyz/zulip/issues/3"}
        )
        self.assert_json_error(result, msg="URL is not valid.")

    @responses.activate()
    def test_invalid_previewable_url(self) -> None:
        response_data = {
            "message": "Not Found",
            "documentation_url": "https://docs.github.com/rest/reference/issues#get-an-issue",
        }
        api_url = "https://api.github.com/repos/zulip/zulip/issues/2"
        responses.add(
            responses.GET,
            api_url,
            json=response_data,
            status=404,
        )
        result = self.client_post(
            "/json/previewable", {"url": "https://github.com/zulip/zulip/issues/2"}
        )
        self.assert_json_error(result, msg="Invalid or expired URL.")

    @responses.activate()
    def test_cache(self) -> None:
        response_data = {
            "title": "Feat: Show titles of GitHub issues on hover fixes: #19710.",
            "user": {"login": "brijsiyag"},
            "state": "open",
            "draft": False,
            "pull_request": {
                "merged_at": None,
            },
        }
        api_url = "https://api.github.com/repos/zulip/zulip/issues/19710"
        responses.add(
            responses.GET,
            api_url,
            json=response_data,
        )
        github_url = "https://github.com/zulip/zulip/issues/19710"
        first_response = self.client_post("/json/previewable", {"url": github_url})
        self.assert_json_success(first_response)
        responses.assert_call_count(api_url, 1)

        second_response = self.client_post("/json/previewable", {"url": github_url})
        self.assert_json_success(second_response)
        responses.assert_call_count(api_url, 1)

        self.assertEqual(first_response.json(), second_response.json())
