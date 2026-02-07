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
    get_entity_topic_name,
    get_notion_api_headers,
    get_page_data,
    get_user_name,
)


class NotionWebhookTest(WebhookTestCase):
    CHANNEL_NAME = "notion"
    URL_TEMPLATE = "/api/v1/external/notion?stream={stream}&api_key={api_key}&map_pages_and_datasources_to_topics=true&notion_token=test_token"
    WEBHOOK_DIR_NAME = "notion"

    @override
    def setUp(self) -> None:
        super().setUp()
        self.user_patcher = patch("zerver.webhooks.notion.view.get_user_name", return_value="Casey")
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
                    "Title": {
                        "id": "SeR#",
                        "type": "title",
                        "title": [{"plain_text": "Project Plan"}],
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
This is a webhook configuration test message from Notion.

Your verification token is: `secret_tMrlL1qK5vuQAh1b6cZGhFChZTSYJlce98V0pYn7yBl`

Please copy this token and paste it into your Notion webhook configuration to complete the setup.
""".strip()
        self.check_webhook(
            "verification", expected_topic, expected_message, content_type="application/json"
        )

    def test_page_created(self) -> None:
        expected_topic = "Page: Project Plan"
        expected_message = "Page **Project Plan** was created by **Casey**"
        self.check_webhook("page_created", expected_topic, expected_message)

    def test_page_content_updated(self) -> None:
        expected_topic = "Page: Project Plan"
        expected_message = "**Casey** updated Page **Project Plan's** content"
        self.check_webhook("page_content_updated", expected_topic, expected_message)

    def test_page_properties_updated(self) -> None:
        expected_topic = "Page: Project Plan"
        expected_message = "**Casey** updated Page **Project Plan**'s properties:\n- Status to In Progress\n- Priority to High\n- Deadline to 2026-02-01"
        self.check_webhook("page_properties_updated", expected_topic, expected_message)

    def test_page_moved(self) -> None:
        expected_topic = "Page: Project Plan"
        expected_message = "Page **Project Plan** was moved by **Casey**"
        self.check_webhook("page_moved", expected_topic, expected_message)

    def test_page_deleted(self) -> None:
        expected_topic = "Page: Project Plan"
        expected_message = "Page **Project Plan** was moved to trash by **Casey**"
        self.check_webhook("page_deleted", expected_topic, expected_message)

    def test_page_undeleted(self) -> None:
        expected_topic = "Page: Project Plan"
        expected_message = "Page **Project Plan** was restored from trash by **Casey**"
        self.check_webhook("page_undeleted", expected_topic, expected_message)

    def test_page_locked(self) -> None:
        expected_topic = "Page: Project Plan"
        expected_message = "Page **Project Plan** was locked by **Casey**"
        self.check_webhook("page_locked", expected_topic, expected_message)

    def test_page_unlocked(self) -> None:
        expected_topic = "Page: Project Plan"
        expected_message = "Page **Project Plan** was unlocked by **Casey**"
        self.check_webhook("page_unlocked", expected_topic, expected_message)

    def test_page_created_without_author(self) -> None:
        self.mock_user.return_value = None
        expected_topic = "Page: Project Plan"
        expected_message = "Page **Project Plan** was created"
        self.check_webhook("page_created", expected_topic, expected_message)

    def test_page_created_without_title(self) -> None:
        self.mock_page_data.return_value = None
        expected_topic = "Page"
        expected_message = "Page was created by **Casey**"
        self.check_webhook("page_created", expected_topic, expected_message)

    def test_page_created_without_topic_mapping(self) -> None:
        self.url = f"/api/v1/external/notion?stream={self.CHANNEL_NAME}&api_key={self.test_user.api_key}&map_pages_and_datasources_to_topics=false"
        expected_topic = "Page"
        expected_message = "Page **Project Plan** was created by **Casey**"
        self.check_webhook("page_created", expected_topic, expected_message)


class NotionHelperFunctionTest(WebhookTestCase):
    CHANNEL_NAME = "notion"
    URL_TEMPLATE = "/api/v1/external/notion?stream={stream}&api_key={api_key}"
    WEBHOOK_DIR_NAME = "notion"

    def test_get_notion_api_headers(self) -> None:
        headers = get_notion_api_headers("test_token")
        self.assertEqual(headers["Authorization"], "Bearer test_token")
        self.assertEqual(headers["Notion-Version"], "2025-09-03")
        self.assertEqual(headers["Content-Type"], "application/json")

    def test_get_page_data_without_token(self) -> None:
        result = get_page_data("", "page_id")
        self.assertIsNone(result)

    @patch("zerver.webhooks.notion.view.requests.get")
    def test_get_page_data_with_api_success(self, mock_get: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "properties": {"title": {"type": "title", "title": [{"plain_text": "Test Page"}]}}
        }
        mock_get.return_value = mock_response

        result = get_page_data("token", "page_id")
        self.assertEqual(
            result,
            {"properties": {"title": {"type": "title", "title": [{"plain_text": "Test Page"}]}}},
        )

    @patch("zerver.webhooks.notion.view.requests.get")
    def test_get_page_data_with_api_failure(self, mock_get: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        result = get_page_data("token", "page_id")
        self.assertIsNone(result)

    @patch("zerver.webhooks.notion.view.requests.get")
    def test_get_page_data_with_exception(self, mock_get: MagicMock) -> None:
        mock_get.side_effect = Exception("Network error")
        result = get_page_data("token", "page_id")
        self.assertIsNone(result)

    def test_get_user_name_without_token(self) -> None:
        result = get_user_name("", "user_id")
        self.assertIsNone(result)

    @patch("zerver.webhooks.notion.view.requests.get")
    def test_get_user_name_with_api_success(self, mock_get: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "object": "user",
            "id": "1d6d872b-594c-8129-818d-000250c7f19f",
            "name": "47-Sathwik Suresh Shetty",
            "avatar_url": None,
            "type": "person",
            "person": {"email": "sathwikshetty@gmail.com"},
            "request_id": "ff8254fe-f60e-459f-bc16-3eb0ee949f80",
        }
        mock_get.return_value = mock_response

        result = get_user_name("token", "user_id")
        self.assertEqual(result, "47-Sathwik Suresh Shetty")

    @patch("zerver.webhooks.notion.view.requests.get")
    def test_get_user_name_with_api_failure(self, mock_get: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_get.return_value = mock_response

        result = get_user_name("token", "user_id")
        self.assertIsNone(result)

    @patch("zerver.webhooks.notion.view.requests.get")
    def test_get_user_name_with_exception(self, mock_get: MagicMock) -> None:
        mock_get.side_effect = Exception("Network error")
        result = get_user_name("token", "user_id")
        self.assertIsNone(result)

    @patch("zerver.webhooks.notion.view.get_user_name", return_value="Casey")
    def test_get_author_name_with_multiple_authors(self, mock_user: object) -> None:
        payload = to_wild_value(
            "payload",
            '{"authors": [{"id": "user1", "type": "person"}, {"id": "user2", "type": "person"}]}',
        )
        result = get_author_name(payload, "token")
        self.assertEqual(result, "Casey (+1 other)")

    @patch("zerver.webhooks.notion.view.get_user_name", return_value="Casey")
    def test_get_author_name_with_many_authors(self, mock_user: object) -> None:
        payload = to_wild_value(
            "payload",
            '{"authors": [{"id": "user1", "type": "person"}, {"id": "user2", "type": "person"}, {"id": "user3", "type": "person"}]}',
        )
        result = get_author_name(payload, "token")
        self.assertEqual(result, "Casey (+2 others)")

    def test_extract_page_title_untitled(self) -> None:
        page_data = {"properties": {"Name": {"id": "title", "type": "title", "title": []}}}
        self.assertEqual(extract_page_title(page_data), "Untitled Page")

    def test_format_action_message_with_entity_and_author(self) -> None:
        result = format_action_message("Page", "Test Page", "created", "Casey")
        self.assertEqual(result, "Page **Test Page** was created by **Casey**")

    def test_format_action_message_with_entity_only(self) -> None:
        result = format_action_message("Page", "Test Page", "created", None)
        self.assertEqual(result, "Page **Test Page** was created")

    def test_format_action_message_with_author_only(self) -> None:
        result = format_action_message("Page", None, "created", "Casey")
        self.assertEqual(result, "Page was created by **Casey**")

    def test_format_action_message_without_entity_or_author(self) -> None:
        result = format_action_message("Page", None, "created", None)
        self.assertEqual(result, "Page was created")

    def test_format_update_message_with_entity_and_author(self) -> None:
        result = format_update_message("Page", "Test Page", "content", "Casey")
        self.assertEqual(result, "**Casey** updated Page **Test Page's** content")

    def test_format_update_message_with_entity_only(self) -> None:
        result = format_update_message("Page", "Test Page", "content", None)
        self.assertEqual(result, "Page **Test Page's** content was updated")

    def test_format_update_message_with_author_only(self) -> None:
        result = format_update_message("Page", None, "content", "Casey")
        self.assertEqual(result, "**Casey** updated Page's content")

    def test_format_update_message_without_entity_or_author(self) -> None:
        result = format_update_message("Page", None, "content", None)
        self.assertEqual(result, "Page's content was updated")

    def test_format_properties_message_with_entity_and_author(self) -> None:
        result = format_properties_message("Page", "Test Page", "- Status: Done", "Casey")
        self.assertEqual(
            result, "**Casey** updated Page **Test Page**'s properties:\n- Status: Done"
        )

    def test_format_properties_message_with_entity_only(self) -> None:
        result = format_properties_message("Page", "Test Page", "- Status: Done", None)
        self.assertEqual(result, "Page **Test Page**'s properties were updated:\n- Status: Done")

    def test_format_properties_message_with_author_only(self) -> None:
        result = format_properties_message("Page", None, "- Status: Done", "Casey")
        self.assertEqual(result, "**Casey** updated Page's properties:\n- Status: Done")

    def test_format_properties_message_without_entity_or_author(self) -> None:
        result = format_properties_message("Page", None, "- Status: Done", None)
        self.assertEqual(result, "Page's properties were updated:\n- Status: Done")

    def test_get_entity_topic_name_with_name(self) -> None:
        result = get_entity_topic_name("page", "My Page")
        self.assertEqual(result, "Page: My Page")

    def test_get_entity_topic_name_without_name(self) -> None:
        result = get_entity_topic_name("page", None)
        self.assertEqual(result, "Page")

    def test_extract_property_value_relation(self) -> None:
        prop = {
            "id": "i~t%40",
            "type": "relation",
            "relation": [
                {"id": "2fbe31d6-4eb9-808d-8aa8-cadea1410745"},
                {"id": "2f1e31d6-4eb9-80c7-8250-f8a76132adc2"},
                {"id": "2f1e31d6-4eb9-804b-9b6a-d74281e27cf9"},
            ],
            "has_more": False,
        }
        self.assertEqual(extract_property_value(prop), "3 linked page(s)")

        prop_empty = {
            "id": "i~t%40",
            "type": "relation",
            "relation": [],
            "has_more": False,
        }
        self.assertEqual(extract_property_value(prop_empty), "empty")

    def test_extract_property_value_person(self) -> None:
        prop = {
            "id": "%3DU_%60",
            "type": "people",
            "people": [
                {
                    "object": "user",
                    "id": "1d6d872b-594c-8129-818d-000250c7f19f",
                    "name": "47-Sathwik Suresh Shetty",
                    "avatar_url": None,
                    "type": "person",
                    "person": {"email": "sathwikshetty@gmail.com"},
                }
            ],
        }
        self.assertEqual(extract_property_value(prop), "47-Sathwik Suresh Shetty")

    def test_extract_property_value_created_time(self) -> None:
        prop = {
            "id": "%3FRTJ",
            "type": "created_time",
            "created_time": "2026-02-02T14:26:00.000Z",
        }
        self.assertEqual(extract_property_value(prop), "2026-02-02T14:26:00.000Z")

    def test_extract_property_value_files(self) -> None:
        prop = {
            "id": "y%3D%40%5D",
            "type": "files",
            "files": [
                {
                    "name": "ping.json",
                    "type": "file",
                    "file": {
                        "url": "https://prod-files-secure.s3.us-west-2.amazonaws.com/092e31d6-4eb9-81d9-9417-00033da9b30d/b864625c-1f45-4653-89a3-f0980706b038/ping.json?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Content-Sha256=UNSIGNED-PAYLOAD&X-Amz-Credential=ASIAZI2LB466TXITY3B2%2F20260203%2Fus-west-2%2Fs3%2Faws4_request&X-Amz-Date=20260203T112320Z&X-Amz-Expires=3600&X-Amz-Security-Token=IQoJb3JpZ2luX2VjEDMaCXVzLXdlc3QtMiJIMEYCIQDpRvfLkoHRW0OCHXbzwzxZQ6e7zZd2QFX0tYGZLhM6%2BwIhAOJdUTieWSm74YYgtFROicXLRm2wOmJG0aJRsmU0PcvrKogECPv%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FwEQABoMNjM3NDIzMTgzODA1IgwaLqaislGuvppdLYoq3AMS%2F3cDKFM5RNwVxfYm0w%2BZ69mY3njV%2FN45oA1CX9Gvp0nEUQX1MYAUZoiQJTFWeSj9IJbTdxPsVU6CbHn8SZekgfo9VGsS68Mw7nfxSRfbmbwdS%2FuTXG9UAKnM84578%2FfZ9C10dndKGo3n8JpQ5nv9TPBr14Xt0nHoL9%2FbQFnPyfaIMeAhQsp8P8DUFp8SbpUFdFLVE2AfMN4H45WVbn%2FKapWrwhhet3o7cMZzDshMrZ%2B0uWLeNDJoMf2J4o%2FjMUDKT48arN1emUKEXNl9ZsE%2B3CMXzeRmyiHDiFsFT34x5CVoNnXtOv5NObP%2Be0VQ0ZSgfdzn6%2BR1Z1qDFkBhpU%2FiBQSddVsEH67eyOBgQMX9Ezv4b3EUarU8%2FA%2BzydFVYcr2sOLCc860pjaaypelouhVjy3hOIP2F3V1ab%2BhHLiFKHc5rwBXAZJWaTCE84d4yBCp9L8Lkx9tbEuZBW1fgENPk1BtWlUJlwHgeUAzNjjeMdAOkd8tHpi2XQelf%2BK2oEZFLI%2Bziu8f%2FizFUyriJ30gz87dYAPGkNRyYfMzK9jFoOBBtUrPqlQ2QmriRFrEQBUgh8QqH4HZ89q0%2BO1B%2Fzpdgro3vPYvlYSoD7y9BZ4hL53gPreaB3c%2Ft1Dl9DDImIfMBjqkATbwXQK3KJGklSSq8Utrp2mqfVzFPQCSqCzhzasd2SgjlpVSQEBD554Ng8crEem%2BABT27VwDXJCJrkh17%2F3jzqR9G1x6uMGDoqD1AMUFYdxhz%2BWmPv%2BGSXPgbyDE4%2Ffv63WAp5W4kJwyaOx%2BAjf4ZmZFcRlFjRviIDAQMcs61HtGh439k4NQG3uXg%2BiM5xF649z%2F5kHHPhdu180kXndSbLSqCUOg&X-Amz-Signature=ed51447e89823aa8d4362e1d7a7a3a6c8fee170a0fda3df35836cc9ae66954ef&X-Amz-SignedHeaders=host&x-amz-checksum-mode=ENABLED&x-id=GetObject",
                        "expiry_time": "2026-02-03T12:23:20.561Z",
                    },
                }
            ],
        }
        self.assertEqual(extract_property_value(prop), "ping.json")

    def test_extract_property_value_ID(self) -> None:
        prop = {"id": "BTvQ", "type": "unique_id", "unique_id": {"prefix": None, "number": 23}}
        self.assertEqual(extract_property_value(prop), "23")

    def test_extract_property_value_title(self) -> None:
        prop = {
            "id": "title",
            "type": "title",
            "title": [
                {
                    "type": "text",
                    "text": {"content": "Zulip Webhook Test", "link": None},
                    "annotations": {
                        "bold": False,
                        "italic": False,
                        "strikethrough": False,
                        "underline": False,
                        "code": False,
                        "color": "default",
                    },
                    "plain_text": "Zulip Webhook Test",
                    "href": None,
                }
            ],
        }
        self.assertEqual(extract_property_value(prop), "Zulip Webhook Test")

    def test_extract_property_value_rich_text(self) -> None:
        prop = {
            "id": "eQ%3Ce",
            "type": "rich_text",
            "rich_text": [
                {
                    "type": "text",
                    "text": {"content": "test", "link": None},
                    "annotations": {
                        "bold": False,
                        "italic": False,
                        "strikethrough": False,
                        "underline": False,
                        "code": False,
                        "color": "default",
                    },
                    "plain_text": "test",
                    "href": None,
                }
            ],
        }
        self.assertEqual(extract_property_value(prop), "test")

    def test_extract_property_value_multi_select(self) -> None:
        prop = {
            "id": "%40ab_",
            "type": "multi_select",
            "multi_select": [
                {
                    "id": "bf4f7b5d-f080-46cc-b14f-5bd41f506bce",
                    "name": "Option Test",
                    "color": "purple",
                },
                {
                    "id": "0d387211-4a8a-488f-ac45-b9b049873999",
                    "name": "new",
                    "color": "gray",
                },
            ],
        }
        self.assertEqual(extract_property_value(prop), "Option Test, new")

    def test_extract_property_value_status(self) -> None:
        prop = {
            "id": "Jhor",
            "type": "status",
            "status": {
                "id": "51d18fb1-975a-40cf-8634-9b6b4a9ea0f2",
                "name": "In progress",
                "color": "blue",
            },
        }
        self.assertEqual(extract_property_value(prop), "In progress")

    def test_extract_property_value_checkbox(self) -> None:
        prop = {"id": "MR%60%3F", "type": "checkbox", "checkbox": True}
        self.assertEqual(extract_property_value(prop), "true")

    def test_extract_property_value_place(self) -> None:
        prop = {
            "id": "NU%60W",
            "type": "place",
            "place": {
                "lat": 12.96617,
                "lon": 77.58692,
                "name": "Bengaluru, Karnataka, India",
                "address": "Bengaluru, Karnataka, India",
                "aws_place_id": "AQAAADgA8EUcFGOz_zzEBKf4mhNu3jmxd1jObUuhde4JiAj9WPvBmA2qq3L9wZDJLXLC22-WUD8Rn2u_9XPdIFHSVnU3AUYT7Og7bq4-Mz3yoirab32_xI5KWEGAfA",
                "google_place_id": None,
            },
        }
        self.assertEqual(extract_property_value(prop), "Bengaluru, Karnataka, India")

    def test_extract_property_value_url(self) -> None:
        prop = {
            "id": "R%5Ezt",
            "type": "url",
            "url": "https://www.notion.so/profile/",
        }
        self.assertEqual(extract_property_value(prop), "https://www.notion.so/profile/")

    def test_extract_property_value_date(self) -> None:
        prop = {
            "id": "XDG%3C",
            "type": "date",
            "date": {"start": "2026-02-25", "end": None, "time_zone": None},
        }
        self.assertEqual(extract_property_value(prop), "2026-02-25")

    def test_extract_property_value_email(self) -> None:
        prop = {"id": "ae%5EO", "type": "email", "email": "sathwik@gmail.com"}
        self.assertEqual(extract_property_value(prop), "sathwik@gmail.com")

    def test_extract_property_value_number(self) -> None:
        prop = {"id": "y%5DbM", "type": "number", "number": 88}
        self.assertEqual(extract_property_value(prop), "88")

    def test_extract_property_value_formula(self) -> None:
        prop = {
            "id": "zNas",
            "type": "formula",
            "formula": {
                "type": "date",
                "date": {
                    "start": "2026-02-23T14:26:00.000+00:00",
                    "end": None,
                    "time_zone": None,
                },
            },
        }
        self.assertEqual(extract_property_value(prop), "2026-02-23T14:26:00.000+00:00")

    def test_extract_property_value_rollup(self) -> None:
        prop = {
            "id": "%7Ccl%3F",
            "type": "rollup",
            "rollup": {"type": "number", "number": 0, "function": "checked"},
        }
        self.assertEqual(extract_property_value(prop), "0")

    def test_extract_property_value_with_empty_value(self) -> None:
        prop = {"id": "ae%5EO", "type": "email", "email": None}
        self.assertEqual(extract_property_value(prop), "empty")
