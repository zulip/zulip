from typing import Any
from unittest.mock import MagicMock, patch

import requests
from typing_extensions import override

from zerver.lib.test_classes import WebhookTestCase
from zerver.lib.validator import to_wild_value
from zerver.webhooks.notion.view import (
    extract_page_title,
    extract_property_value,
    get_author_name,
    get_notion_api_headers,
    get_notion_data,
)


class NotionWebhookTest(WebhookTestCase):
    @staticmethod
    def mock_get_notion_data(token: str, entity_type: str, entity_id: str) -> dict[str, Any]:

        if entity_type == "users":
            return {"name": "Test User"}
        else:
            return {
                "properties": {
                    "title": {
                        "id": "SeR#",
                        "type": "title",
                        "title": [{"plain_text": "Project Plan"}],
                    },
                    "Status": {"id": "XGe%40", "type": "select", "select": {"name": "In Progress"}},
                    "Priority": {"id": "bDf%5B", "type": "select", "select": {"name": "High"}},
                    "Deadline": {
                        "id": "DbAu",
                        "type": "formula",
                        "formula": {"type": "date", "date": {"start": "2026-02-01"}},
                    },
                }
            }

    @override
    def setUp(self) -> None:
        super().setUp()
        self.notion_patcher = patch(
            "zerver.webhooks.notion.view.get_notion_data",
            side_effect=self.mock_get_notion_data,
        )
        self.mock_notion = self.notion_patcher.start()

    @override
    def tearDown(self) -> None:
        self.notion_patcher.stop()
        super().tearDown()

    def test_verification_request(self) -> None:
        expected_topic = "Verification"
        expected_message = """
Notion webhook has been successfully configured.
Your verification token is: `secret_tMrlL1qK5vuQAh1b6cZGhFChZTSYJlce98V0pYn7yBl`
Please copy this token and paste it into your Notion webhook configuration to complete the setup.
""".strip()
        self.check_webhook("verification", expected_topic, expected_message)

    def test_page_created(self) -> None:
        expected_topic = "Page: Project Plan"
        expected_message = "Page **Project Plan** was created by **Test User**."
        self.check_webhook("page_created", expected_topic, expected_message)

    def test_page_content_updated(self) -> None:
        expected_topic = "Page: Project Plan"
        expected_message = "Page **Project Plan**'s content was updated by **Test User**."
        self.check_webhook("page_content_updated", expected_topic, expected_message)

    def test_page_properties_updated(self) -> None:
        expected_topic = "Page: Project Plan"
        expected_message = (
            "Page **Project Plan**'s properties was updated by **Test User** with the following:\n"
            "- Status to In Progress\n"
            "- Priority to High\n"
            "- Deadline to 2026-02-01"
        )
        self.check_webhook("page_properties_updated", expected_topic, expected_message)

    def test_property_updated_without_page_data(self) -> None:
        self.mock_notion.side_effect = lambda token, entity_type, entity_id: (
            None
            if entity_type == "pages"
            else self.mock_get_notion_data(token, entity_type, entity_id)
        )

        expected_topic = "Page"
        expected_message = "Page's properties was updated by **Test User**."
        self.check_webhook("page_properties_updated", expected_topic, expected_message)

    def test_page_moved(self) -> None:
        expected_topic = "Page: Project Plan"
        expected_message = "Page **Project Plan** was moved by **Test User**."
        self.check_webhook("page_moved", expected_topic, expected_message)

    def test_page_deleted(self) -> None:
        expected_topic = "Page: Project Plan"
        expected_message = "Page **Project Plan** was moved to trash by **Test User**."
        self.check_webhook("page_deleted", expected_topic, expected_message)

    def test_page_undeleted(self) -> None:
        expected_topic = "Page: Project Plan"
        expected_message = "Page **Project Plan** was restored from trash by **Test User**."
        self.check_webhook("page_undeleted", expected_topic, expected_message)

    def test_page_locked(self) -> None:
        expected_topic = "Page: Project Plan"
        expected_message = "Page **Project Plan** was locked by **Test User**."
        self.check_webhook("page_locked", expected_topic, expected_message)

    def test_page_unlocked(self) -> None:
        expected_topic = "Page: Project Plan"
        expected_message = "Page **Project Plan** was unlocked by **Test User**."
        self.check_webhook("page_unlocked", expected_topic, expected_message)

    def test_event_with_author_retrieval_failure(self) -> None:
        self.mock_notion.side_effect = lambda token, entity_type, entity_id: (
            None
            if entity_type == "users"
            else self.mock_get_notion_data(token, entity_type, entity_id)
        )

        expected_topic = "Page: Project Plan"
        expected_message = "Page **Project Plan** was created."
        self.check_webhook("page_created", expected_topic, expected_message)

    def test_event_without_title_retrieval_failure(self) -> None:
        self.mock_notion.side_effect = lambda token, entity_type, entity_id: (
            None
            if entity_type == "pages"
            else self.mock_get_notion_data(token, entity_type, entity_id)
        )

        expected_topic = "Page"
        expected_message = "Page was created by **Test User**."
        self.check_webhook("page_created", expected_topic, expected_message)

    def test_get_notion_api_headers(self) -> None:
        headers = get_notion_api_headers("test_token")
        self.assertEqual(headers["Authorization"], "Bearer test_token")
        self.assertEqual(headers["Notion-Version"], "2025-09-03")
        self.assertEqual(headers["Content-Type"], "application/json")

    def test_extract_page_title_without_title_field(self) -> None:
        page_data = self.mock_get_notion_data("token", "pages", "id")
        page_data["properties"].pop("title")
        self.assertRaises(AssertionError, extract_page_title, page_data)

    def test_extract_page_title_with_null_title_field(self) -> None:
        page_data = self.mock_get_notion_data("token", "pages", "id")
        page_data["properties"]["title"]["title"] = []
        self.assertEqual(extract_page_title(page_data), "Untitled Page")

    def test_extract_property_value(self) -> None:
        data_with_value_none = {
            "link": {
                "type": "url",
                "url": None,
            }
        }
        self.assertEqual(extract_property_value(data_with_value_none["link"]), "empty")

        data_with_rich_text = {
            "name": {
                "type": "rich_text",
                "rich_text": [{"plain_text": "Test Page"}],
            }
        }
        self.assertEqual(extract_property_value(data_with_rich_text["name"]), "Test Page")

        data_with_check_box = {
            "name": {
                "type": "checkbox",
                "checkbox": True,
            }
        }
        self.assertEqual(extract_property_value(data_with_check_box["name"]), "true")

        data_with_multi_select = {
            "name": {
                "type": "multi_select",
                "multi_select": [{"name": "Option 1"}, {"name": "Option 2"}],
            },
        }
        self.assertEqual(
            extract_property_value(data_with_multi_select["name"]), "Option 1, Option 2"
        )

        data_with_formula = {
            "name": {
                "type": "formula",
                "formula": {"type": "number", "number": 123},
            }
        }
        self.assertEqual(extract_property_value(data_with_formula["name"]), "123")

        data_with_relation = {
            "name": {
                "type": "relation",
                "relation": [{"id": "123"}, {"id": "456"}],
            }
        }
        self.assertEqual(extract_property_value(data_with_relation["name"]), "2 linked page(s)")

        data_with_unique_id = {
            "name": {
                "type": "unique_id",
                "unique_id": {
                    "number": 123,
                },
            }
        }
        self.assertEqual(extract_property_value(data_with_unique_id["name"]), "123")

    def test_get_notion_data_without_token(self) -> None:
        result = get_notion_data("", "entity_type", "entity_id")
        self.assertIsNone(result)

    @patch("zerver.webhooks.notion.view.get_service_api_data")
    def test_get_notion_data_with_api_success(self, mock_fetch: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = self.mock_get_notion_data("token", "users", "user_id")
        mock_fetch.return_value = mock_response

        result = get_notion_data("token", "users", "user_id")
        self.assertEqual(result, self.mock_get_notion_data("token", "users", "user_id"))

    @patch("zerver.webhooks.notion.view.get_service_api_data")
    def test_get_notion_data_with_api_failure(self, mock_fetch: MagicMock) -> None:
        mock_fetch.side_effect = requests.RequestException("API error")

        result = get_notion_data("token", "pages", "page_id")
        self.assertIsNone(result)

    def test_get_author_name_with_multiple_authors(self) -> None:
        payload = to_wild_value(
            "payload",
            '{"authors": [{"id": "user1", "type": "person"}, {"id": "user2", "type": "person"}]}',
        )

        result = get_author_name(payload, "token")
        self.assertEqual(result, "Test User (+1 other)")

    def test_get_author_name_with_many_authors(self) -> None:
        payload = to_wild_value(
            "payload",
            '{"authors": [{"id": "user1", "type": "person"}, {"id": "user2", "type": "person"}, {"id": "user3", "type": "person"}]}',
        )

        result = get_author_name(payload, "token")
        self.assertEqual(result, "Test User (+2 others)")
