from zerver.lib.test_classes import WebhookTestCase
from zerver.lib.validator import WildValue, check_string
from zerver.lib.webhooks.common import get_setup_webhook_message

from .view import NOTION_VERIFICATION_TOKEN_MESSAGE
from .webhook import COMMENT_EVENT_MESSAGES, DATABASE_EVENT_MESSAGES, PAGE_EVENT_MESSAGES


class NotionHookTests(WebhookTestCase):
    WEBHOOK_DIR_NAME = "notion"
    CHANNEL_NAME = "notion"
    URL_TEMPLATE = "/api/v1/external/notion"

    def test_verification_request(self) -> None:
        expected_topic = "Verification"
        payload = WildValue(self.get_payload("verification"))
        verification_token = payload["verification_token"].tame(check_string)
        expected_message = NOTION_VERIFICATION_TOKEN_MESSAGE.format(
            setup_message=get_setup_webhook_message("Notion"),
            token=verification_token,
        )
        self.check_webhook(
            "verification",
            expected_topic,
            expected_message=expected_message,
        )

    def test_all_page_events(self) -> None:
        events = [
            "page_created",
            "page_deleted",
            "page_moved",
            "page_locked",
            "page_unlocked",
            "page_properties_updated",
            "page_content_updated",
            "page_undeleted",
        ]

        for event in events:
            payload = WildValue(self.get_payload(event))
            event_type = payload["type"].tame(check_string)
            workspace = payload["workspace_name"].tame(check_string)
            page_id = payload["entity"]["id"].tame(check_string)
            action = PAGE_EVENT_MESSAGES[event_type]
            expected_message = f"**{action}**\n\nWorkspace: **{workspace}**\nPage ID: `{page_id}`"
            self.check_webhook(event, "Notion Pages", expected_message=expected_message)

    def test_all_database_events(self) -> None:
        events = [
            "database_created",
            "database_deleted",
            "database_moved",
            "database_schema_updated",
            "database_content_updated",
            "database_undeleted",
        ]

        for event in events:
            payload = WildValue(self.get_payload(event))
            event_type = payload["type"].tame(check_string)
            db_id = payload["entity"]["id"].tame(check_string)
            action = DATABASE_EVENT_MESSAGES[event_type]
            expected_message = f"**{action}**\n\nDatabase ID: `{db_id}`"
            self.check_webhook(event, "Notion Databases", expected_message=expected_message)

    def test_all_comment_events(self) -> None:
        events = [
            "comment_created",
            "comment_updated",
            "comment_deleted",
        ]

        for event in events:
            payload = WildValue(self.get_payload(event))
            event_type = payload["type"].tame(check_string)
            action = COMMENT_EVENT_MESSAGES[event_type]
            expected_message = f"**{action}** in Notion."
            self.check_webhook(event, "Notion Comments", expected_message=expected_message)
