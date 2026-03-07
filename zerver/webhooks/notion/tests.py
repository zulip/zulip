from copy import deepcopy
from unittest.mock import MagicMock, patch

from typing_extensions import override

from zerver.lib.test_classes import WebhookTestCase
from zerver.lib.validator import to_wild_value
from zerver.webhooks.notion.view import (
    extract_page_title,
    extract_property_value,
    format_action_message,
    format_properties_message,
    format_update_message,
    get_author_name,
    get_notion_api_headers,
    get_page_data,
    get_user_name,
)


class NotionWebhookTest(WebhookTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        self.user_patcher = patch(
            "zerver.webhooks.notion.view.get_user_name", return_value="Test User"
        )
        self.page_data_patcher = patch(
            "zerver.webhooks.notion.view.get_page_data",
            return_value={
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
            },
        )
        self.mock_user = self.user_patcher.start()
        self.mock_page_data = self.page_data_patcher.start()

    @override
    def tearDown(self) -> None:
        self.user_patcher.stop()
        self.page_data_patcher.stop()
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
        expected_message = "Page **Project Plan** was created by **Test User**"
        self.check_webhook("page_created", expected_topic, expected_message)

    def test_page_content_updated(self) -> None:
        expected_topic = "Page: Project Plan"
        expected_message = "**Test User** updated Page **Project Plan's** content"
        self.check_webhook("page_content_updated", expected_topic, expected_message)

    def test_page_properties_updated(self) -> None:
        expected_topic = "Page: Project Plan"
        expected_message = "**Test User** updated Page **Project Plan**'s properties:\n- Status to In Progress\n- Priority to High\n- Deadline to 2026-02-01"
        self.check_webhook("page_properties_updated", expected_topic, expected_message)

    def test_page_moved(self) -> None:
        expected_topic = "Page: Project Plan"
        expected_message = "Page **Project Plan** was moved by **Test User**"
        self.check_webhook("page_moved", expected_topic, expected_message)

    def test_page_deleted(self) -> None:
        expected_topic = "Page: Project Plan"
        expected_message = "Page **Project Plan** was moved to trash by **Test User**"
        self.check_webhook("page_deleted", expected_topic, expected_message)

    def test_page_undeleted(self) -> None:
        expected_topic = "Page: Project Plan"
        expected_message = "Page **Project Plan** was restored from trash by **Test User**"
        self.check_webhook("page_undeleted", expected_topic, expected_message)

    def test_page_locked(self) -> None:
        expected_topic = "Page: Project Plan"
        expected_message = "Page **Project Plan** was locked by **Test User**"
        self.check_webhook("page_locked", expected_topic, expected_message)

    def test_page_unlocked(self) -> None:
        expected_topic = "Page: Project Plan"
        expected_message = "Page **Project Plan** was unlocked by **Test User**"
        self.check_webhook("page_unlocked", expected_topic, expected_message)

    def test_page_created_without_author(self) -> None:
        self.mock_user.return_value = None
        expected_topic = "Page: Project Plan"
        expected_message = "Page **Project Plan** was created"
        self.check_webhook("page_created", expected_topic, expected_message)

    def test_page_created_without_title(self) -> None:
        self.mock_page_data.return_value = None
        expected_topic = "Page"
        expected_message = "Page was created by **Test User**"
        self.check_webhook("page_created", expected_topic, expected_message)

    def test_get_notion_api_headers(self) -> None:
        headers = get_notion_api_headers("test_token")
        self.assertEqual(headers["Authorization"], "Bearer test_token")
        self.assertEqual(headers["Notion-Version"], "2025-09-03")
        self.assertEqual(headers["Content-Type"], "application/json")

    def test_extract_page_title_with_page_data_without_title_field(self) -> None:
        page_data = deepcopy(self.mock_page_data.return_value)
        page_data["properties"].pop("title")
        self.assertRaises(AssertionError, extract_page_title, page_data)

    def test_extract_page_title_with_page_data_without_title(self) -> None:
        page_data = deepcopy(self.mock_page_data.return_value)
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

    def test_get_page_data_without_token(self) -> None:
        result = get_page_data("", "page_id")
        self.assertIsNone(result)

    @patch("zerver.webhooks.notion.view.fetch_api_data")
    def test_get_page_data_with_api_success(self, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = self.mock_page_data.return_value

        result = get_page_data("token", "page_id")
        self.assertEqual(result, self.mock_page_data.return_value)

    @patch("zerver.webhooks.notion.view.fetch_api_data")
    def test_get_page_data_with_api_failure(self, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = None

        result = get_page_data("token", "page_id")
        self.assertIsNone(result)

    def test_get_user_name_without_token(self) -> None:
        result = get_user_name("", "user_id")
        self.assertIsNone(result)

    @patch("zerver.webhooks.notion.view.fetch_api_data")
    def test_get_user_name_with_api_success(self, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = {
            "object": "user",
            "id": "1d6d872b-594c-8129-818d-000250c7f19f",
            "name": "47-Sathwik Suresh Shetty",
            "avatar_url": None,
            "type": "person",
            "person": {"email": "sathwikshetty@gmail.com"},
            "request_id": "ff8254fe-f60e-459f-bc16-3eb0ee949f80",
        }

        result = get_user_name("token", "user_id")
        self.assertEqual(result, "47-Sathwik Suresh Shetty")

    @patch("zerver.webhooks.notion.view.fetch_api_data")
    def test_get_user_name_with_api_failure(self, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = None

        result = get_user_name("token", "user_id")
        self.assertIsNone(result)

    @patch("zerver.webhooks.notion.view.get_user_name", return_value="Test User")
    def test_get_author_name_with_multiple_authors(self, mock_user: object) -> None:
        payload = to_wild_value(
            "payload",
            '{"authors": [{"id": "user1", "type": "person"}, {"id": "user2", "type": "person"}]}',
        )

        result = get_author_name(payload, "token")
        self.assertEqual(result, "Test User (+1 other)")

    @patch("zerver.webhooks.notion.view.get_user_name", return_value="Test User")
    def test_get_author_name_with_many_authors(self, mock_user: object) -> None:
        payload = to_wild_value(
            "payload",
            '{"authors": [{"id": "user1", "type": "person"}, {"id": "user2", "type": "person"}, {"id": "user3", "type": "person"}]}',
        )

        result = get_author_name(payload, "token")
        self.assertEqual(result, "Test User (+2 others)")

    def test_format_action_message(self) -> None:
        msg = format_action_message("Page", "Project Plan", "created", "Test User")
        self.assertEqual(msg, "Page **Project Plan** was created by **Test User**")

        msg = format_action_message("Page", "Project Plan", "created", None)
        self.assertEqual(msg, "Page **Project Plan** was created")

        msg = format_action_message("Page", None, "created", "Test User")
        self.assertEqual(msg, "Page was created by **Test User**")

        msg = format_action_message("Page", None, "created", None)
        self.assertEqual(msg, "Page was created")

    def test_format_update_message(self) -> None:
        msg = format_update_message("Page", "Project Plan", "content", "Test User")
        self.assertEqual(msg, "**Test User** updated Page **Project Plan's** content")

        msg = format_update_message("Page", "Project Plan", "content", None)
        self.assertEqual(msg, "Page **Project Plan's** content was updated")

        msg = format_update_message("Page", None, "content", "Test User")
        self.assertEqual(msg, "**Test User** updated Page's content")

        msg = format_update_message("Page", None, "content", None)
        self.assertEqual(msg, "Page's content was updated")

    def test_format_properties_message(self) -> None:
        properties = "- Status to Done\n- Priority to High"

        msg = format_properties_message("Page", "Project Plan", properties, "Test User")
        self.assertEqual(
            msg,
            "**Test User** updated Page **Project Plan**'s properties:\n- Status to Done\n- Priority to High",
        )

        msg = format_properties_message("Page", "Project Plan", properties, None)
        self.assertEqual(
            msg,
            "Page **Project Plan**'s properties were updated:\n- Status to Done\n- Priority to High",
        )

        msg = format_properties_message("Page", None, properties, "Test User")
        self.assertEqual(
            msg, "**Test User** updated Page's properties:\n- Status to Done\n- Priority to High"
        )

        msg = format_properties_message("Page", None, properties, None)
        self.assertEqual(
            msg, "Page's properties were updated:\n- Status to Done\n- Priority to High"
        )
