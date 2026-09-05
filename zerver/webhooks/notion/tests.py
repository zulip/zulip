import copy
from collections.abc import Callable
from functools import wraps
from typing import Any, Concatenate

import orjson
import requests
import responses
from typing_extensions import ParamSpec

from zerver.lib.bot_config import set_bot_config
from zerver.lib.test_classes import WebhookTestCase
from zerver.lib.validator import to_wild_value
from zerver.webhooks.notion.view import (
    extract_page_title,
    extract_property_value,
    get_author_name,
    get_notion_api_headers,
    get_notion_data,
)

ParamT = ParamSpec("ParamT")

USER_NAME = "Sathwik Shetty"
PAGE_TITLE = "Zulip Notion Test"
AUTHOR_ID = "1d6d872b-594c-8129-818d-000250c7f19f"
PAGE_ID = "337e31d6-4eb9-80fa-b299-c93680d85322"

NOTION_USERS_URL = f"https://api.notion.com/v1/users/{AUTHOR_ID}"
NOTION_PAGES_URL = f"https://api.notion.com/v1/pages/{PAGE_ID}"


def mock_notion_api_calls(
    test_func: Callable[Concatenate["NotionWebhookTest", ParamT], None],
) -> Callable[Concatenate["NotionWebhookTest", ParamT], None]:
    @wraps(test_func)
    @responses.activate
    def _wrapped(self: "NotionWebhookTest", /, *args: ParamT.args, **kwargs: ParamT.kwargs) -> None:
        set_bot_config(self.test_user, "notion_token", "test_notion_token")
        responses.add(
            responses.GET,
            NOTION_USERS_URL,
            self.webhook_fixture_data("notion", "notion_user_info_api_response"),
        )
        responses.add(
            responses.GET,
            NOTION_PAGES_URL,
            self.webhook_fixture_data("notion", "notion_page_info_api_response"),
        )
        test_func(self, *args, **kwargs)

    return _wrapped


class NotionWebhookTest(WebhookTestCase):
    def test_verification_request(self) -> None:
        expected_topic = "Verification"
        expected_message = """
Notion webhook has been successfully configured.
Your verification token is: `secret_tMrlL1qK5vuQAh1b6cZGhFChZTSYJlce98V0pYn7yBl`
Please copy this token and paste it into your Notion webhook configuration to complete the setup.
""".strip()
        self.check_webhook("verification", expected_topic, expected_message)

    @mock_notion_api_calls
    def test_page_created(self) -> None:
        expected_topic = f"Page: {PAGE_TITLE}"
        expected_message = f"Page **{PAGE_TITLE}** was created by **{USER_NAME}**."
        self.check_webhook("page_created", expected_topic, expected_message)

    @mock_notion_api_calls
    def test_page_content_updated(self) -> None:
        expected_topic = f"Page: {PAGE_TITLE}"
        expected_message = f"Page **{PAGE_TITLE}**'s content was updated by **{USER_NAME}**."
        self.check_webhook("page_content_updated", expected_topic, expected_message)

    @mock_notion_api_calls
    def test_page_properties_updated(self) -> None:
        expected_topic = f"Page: {PAGE_TITLE}"
        expected_message = (
            f"Page **{PAGE_TITLE}**'s properties were updated by **{USER_NAME}**"
            " with the following:\n"
            "- Status set to In Progress\n"
            "- Priority set to High\n"
            "- Deadline set to 2026-02-01"
        )

        payload_data = orjson.loads(self.webhook_fixture_data("notion", "page_properties_updated"))
        self.check_webhook("page_properties_updated", expected_topic, expected_message)

        modified = copy.deepcopy(payload_data)
        modified["data"]["updated_properties"] = modified["data"]["updated_properties"][:1]

        self.subscribe(self.test_user, self.channel_name)
        msg = self.send_webhook_payload(
            self.test_user,
            self.url,
            orjson.dumps(modified).decode(),
            content_type="application/json",
        )

        self.assert_channel_message(
            message=msg,
            channel_name=self.channel_name,
            topic_name=f"Page: {PAGE_TITLE}",
            content=f"Page **{PAGE_TITLE}**'s property was updated by **{USER_NAME}** with Status set to In Progress.",
        )

    @mock_notion_api_calls
    def test_page_moved(self) -> None:
        expected_topic = f"Page: {PAGE_TITLE}"
        expected_message = f"Page **{PAGE_TITLE}** was moved by **{USER_NAME}**."
        self.check_webhook("page_moved", expected_topic, expected_message)

    @mock_notion_api_calls
    def test_page_deleted(self) -> None:
        expected_topic = f"Page: {PAGE_TITLE}"
        expected_message = f"Page **{PAGE_TITLE}** was moved to trash by **{USER_NAME}**."
        self.check_webhook("page_deleted", expected_topic, expected_message)

    @mock_notion_api_calls
    def test_page_undeleted(self) -> None:
        expected_topic = f"Page: {PAGE_TITLE}"
        expected_message = f"Page **{PAGE_TITLE}** was restored from trash by **{USER_NAME}**."
        self.check_webhook("page_undeleted", expected_topic, expected_message)

    @mock_notion_api_calls
    def test_page_locked(self) -> None:
        expected_topic = f"Page: {PAGE_TITLE}"
        expected_message = f"Page **{PAGE_TITLE}** was locked by **{USER_NAME}**."
        self.check_webhook("page_locked", expected_topic, expected_message)

    @mock_notion_api_calls
    def test_page_unlocked(self) -> None:
        expected_topic = f"Page: {PAGE_TITLE}"
        expected_message = f"Page **{PAGE_TITLE}** was unlocked by **{USER_NAME}**."
        self.check_webhook("page_unlocked", expected_topic, expected_message)

    def test_get_notion_api_headers(self) -> None:
        headers = get_notion_api_headers("test_token")
        self.assertEqual(headers["Authorization"], "Bearer test_token")
        self.assertEqual(headers["Notion-Version"], "2025-09-03")
        self.assertEqual(headers["Content-Type"], "application/json")

    def test_extract_page_title(self) -> None:
        page_data = orjson.loads(
            self.webhook_fixture_data("notion", "notion_page_info_api_response")
        )

        # Test for null title field.
        page_data_with_null_title = copy.deepcopy(page_data)
        page_data_with_null_title["properties"]["title"]["title"] = []
        self.assertEqual(extract_page_title(page_data_with_null_title), "Untitled Page")

        # Test for missing title field.
        page_data_without_title = copy.deepcopy(page_data)
        page_data_without_title["properties"].pop("title")
        self.assertRaises(AssertionError, extract_page_title, page_data_without_title)

    @mock_notion_api_calls
    def test_get_author_name(self) -> None:
        payload_data = orjson.loads(self.webhook_fixture_data("notion", "page_created"))

        # Test for successful retrieval.
        self.assertEqual(
            get_author_name(to_wild_value("payload", orjson.dumps(payload_data).decode()), "token"),
            USER_NAME,
        )

        # Test for empty authors list.
        payload_no_authors = copy.deepcopy(payload_data)
        payload_no_authors["authors"] = []
        self.assertIsNone(
            get_author_name(
                to_wild_value("payload", orjson.dumps(payload_no_authors).decode()), "token"
            )
        )

        # Test for multiple authors.
        payload_multiple = copy.deepcopy(payload_data)
        payload_multiple["authors"].append({"id": "user2", "type": "person"})
        self.assertEqual(
            get_author_name(
                to_wild_value("payload", orjson.dumps(payload_multiple).decode()), "token"
            ),
            f"{USER_NAME} (+1 other)",
        )

        # Test for many authors.
        payload_many = copy.deepcopy(payload_data)
        payload_many["authors"].extend(
            [{"id": "user2", "type": "person"}, {"id": "user3", "type": "person"}]
        )
        self.assertEqual(
            get_author_name(to_wild_value("payload", orjson.dumps(payload_many).decode()), "token"),
            f"{USER_NAME} (+2 others)",
        )

        # Test for failed user API response.
        UNKNOWN_USER_ID = "unknown_user_id"
        NOTION_UNKNOWN_USER_URL = f"https://api.notion.com/v1/users/{UNKNOWN_USER_ID}"
        responses.add(
            responses.GET,
            NOTION_UNKNOWN_USER_URL,
            json={"object": "error", "status": 404, "message": "Not found"},
            status=404,
        )
        payload_failed_author = copy.deepcopy(payload_data)
        payload_failed_author["authors"] = [{"id": UNKNOWN_USER_ID, "type": "person"}]
        with self.assertLogs("zerver.lib.webhooks.common", level="WARNING") as warn_logs:
            self.assertIsNone(
                get_author_name(
                    to_wild_value("payload", orjson.dumps(payload_failed_author).decode()), "token"
                )
            )
        self.assertEqual(
            warn_logs.output,
            [
                f"WARNING:zerver.lib.webhooks.common:Failed to fetch data from {NOTION_UNKNOWN_USER_URL}"
                f" for Notion integration: 404 Client Error: Not Found for url: {NOTION_UNKNOWN_USER_URL}"
            ],
        )

    def test_extract_property_value(self) -> None:
        cases: list[tuple[str, dict[str, Any], str]] = [
            ("None value", {"type": "url", "url": None}, "empty"),
            (
                "rich_text",
                {"type": "rich_text", "rich_text": [{"plain_text": "Test Page"}]},
                "Test Page",
            ),
            ("checkbox", {"type": "checkbox", "checkbox": True}, "true"),
            (
                "multi_select",
                {
                    "type": "multi_select",
                    "multi_select": [{"name": "Option 1"}, {"name": "Option 2"}],
                },
                "Option 1, Option 2",
            ),
            (
                "formula number",
                {"type": "formula", "formula": {"type": "number", "number": 123}},
                "123",
            ),
            (
                "relation",
                {"type": "relation", "relation": [{"id": "123"}, {"id": "456"}]},
                "2 linked page(s)",
            ),
            ("unique_id", {"type": "unique_id", "unique_id": {"number": 123}}, "123"),
        ]
        for label, prop, expected in cases:
            with self.subTest(label):
                self.assertEqual(extract_property_value(prop), expected)

    @responses.activate
    def test_get_notion_data(self) -> None:
        # Test for missing token.
        self.assertIsNone(get_notion_data("", "users", AUTHOR_ID))

        # Test for successful retrieval.
        responses.add(
            responses.GET,
            NOTION_USERS_URL,
            self.webhook_fixture_data("notion", "notion_user_info_api_response"),
        )
        result = get_notion_data("token", "users", AUTHOR_ID)
        assert result is not None
        self.assertEqual(result["name"], USER_NAME)

        # Test for API failure.
        responses.add(
            responses.GET,
            NOTION_PAGES_URL,
            json={"object": "error", "status": 500, "message": "Internal error"},
            status=500,
        )

        with self.assertLogs("zerver.lib.webhooks.common", level="WARNING") as warn_logs:
            self.assertIsNone(get_notion_data("token", "pages", PAGE_ID))
        self.assertEqual(
            warn_logs.output,
            [
                f"WARNING:zerver.lib.webhooks.common:Failed to fetch data from {NOTION_PAGES_URL}"
                f" for Notion integration: 500 Server Error: Internal Server Error for url: {NOTION_PAGES_URL}"
            ],
        )

        # Test for invalid JSON.
        INVALID_URL = "https://api.notion.com/v1/pages/invalid-json"
        responses.add(
            responses.GET,
            INVALID_URL,
            body="invalid json",
            status=200,
        )
        self.assertIsNone(get_notion_data("token", "pages", "invalid-json"))

        # Test for RequestException (network failure).
        EXCEPTION_URL = "https://api.notion.com/v1/pages/network-error"
        responses.add(
            responses.GET,
            EXCEPTION_URL,
            body=requests.RequestException("Connection error"),
        )

        with self.assertLogs("zerver.lib.webhooks.common", level="WARNING") as warn_logs:
            self.assertIsNone(get_notion_data("token", "pages", "network-error"))
        self.assertEqual(
            warn_logs.output,
            [
                f"WARNING:zerver.lib.webhooks.common:Failed to fetch data from {EXCEPTION_URL}"
                " for Notion integration: Connection error"
            ],
        )

    @responses.activate
    def test_event_with_author_retrieval_failure(self) -> None:
        set_bot_config(self.test_user, "notion_token", "test_notion_token")
        responses.add(
            responses.GET,
            NOTION_USERS_URL,
            json={"object": "error", "status": 404, "message": "Not found"},
            status=404,
        )
        responses.add(
            responses.GET,
            NOTION_PAGES_URL,
            self.webhook_fixture_data("notion", "notion_page_info_api_response"),
        )

        expected_topic = f"Page: {PAGE_TITLE}"
        expected_message = f"Page **{PAGE_TITLE}** was created."
        with self.assertLogs("zerver.lib.webhooks.common", level="WARNING") as warn_logs:
            self.check_webhook("page_created", expected_topic, expected_message)
        self.assertEqual(
            warn_logs.output,
            [
                f"WARNING:zerver.lib.webhooks.common:Failed to fetch data from {NOTION_USERS_URL}"
                f" for Notion integration: 404 Client Error: Not Found for url: {NOTION_USERS_URL}"
            ],
        )

    @responses.activate
    def test_event_with_title_retrieval_failure(self) -> None:
        set_bot_config(self.test_user, "notion_token", "test_notion_token")
        responses.add(
            responses.GET,
            NOTION_USERS_URL,
            self.webhook_fixture_data("notion", "notion_user_info_api_response"),
        )
        responses.add(
            responses.GET,
            NOTION_PAGES_URL,
            json={"object": "error", "status": 404, "message": "Not found"},
            status=404,
        )

        expected_topic = "Page"
        expected_message = f"Page was created by **{USER_NAME}**."
        with self.assertLogs("zerver.lib.webhooks.common", level="WARNING") as warn_logs:
            self.check_webhook("page_created", expected_topic, expected_message)
        self.assertEqual(
            warn_logs.output,
            [
                f"WARNING:zerver.lib.webhooks.common:Failed to fetch data from {NOTION_PAGES_URL}"
                f" for Notion integration: 404 Client Error: Not Found for url: {NOTION_PAGES_URL}"
            ],
        )

    @responses.activate
    def test_property_updated_without_page_data(self) -> None:
        set_bot_config(self.test_user, "notion_token", "test_notion_token")
        responses.add(
            responses.GET,
            NOTION_USERS_URL,
            self.webhook_fixture_data("notion", "notion_user_info_api_response"),
        )
        responses.add(
            responses.GET,
            NOTION_PAGES_URL,
            json={"object": "error", "status": 404, "message": "Not found"},
            status=404,
        )

        expected_topic = "Page"
        expected_message = f"Page's properties were updated by **{USER_NAME}**."
        with self.assertLogs("zerver.lib.webhooks.common", level="WARNING") as warn_logs:
            self.check_webhook("page_properties_updated", expected_topic, expected_message)
        self.assertEqual(
            warn_logs.output,
            [
                f"WARNING:zerver.lib.webhooks.common:Failed to fetch data from {NOTION_PAGES_URL}"
                f" for Notion integration: 404 Client Error: Not Found for url: {NOTION_PAGES_URL}"
            ],
        )
