from zerver.lib.test_classes import WebhookTestCase


class NotionHookTests(WebhookTestCase):
    WEBHOOK_DIR_NAME = "notion"
    CHANNEL_NAME = "notion"
    URL_TEMPLATE = "/api/v1/external/notion"

    def test_verification_request(self) -> None:
        expected_topic = "Verification"
        self.check_webhook(
            "verification",
            expected_topic,
            expected_message_containing="Your verification token is",
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
            self.check_webhook(event, "Notion Pages")

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
            self.check_webhook(event, "Notion Databases")

    def test_all_comment_events(self) -> None:
        events = [
            "comment_created",
            "comment_updated",
            "comment_deleted",
        ]

        for event in events:
            self.check_webhook(event, "Notion Comments")
