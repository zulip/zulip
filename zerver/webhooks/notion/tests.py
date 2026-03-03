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
            expected_message="Your verification token is",
        )

    def test_all_page_events(self) -> None:
        events = [
            ("page_created", "Page created:"),
            ("page_deleted", "Page deleted:"),
            ("page_moved", "Page moved:"),
            ("page_locked", "Page locked:"),
            ("page_unlocked", "Page unlocked:"),
            ("page_properties_updated", "Page properties updated:"),
            ("page_content_updated", "Page content updated:"),
            ("page_undeleted", "Page restored:"),
        ]

        for event, expected_substring in events:
            self.check_webhook(
                event,
                "Notion Pages",
                expected_message_containing=expected_substring,
            )

    def test_all_database_events(self) -> None:
        events = [
            ("database_created", "Database created:"),
            ("database_deleted", "Database deleted:"),
            ("database_moved", "Database moved:"),
            ("database_schema_updated", "Database schema updated:"),
            ("database_content_updated", "Database content updated:"),
            ("database_undeleted", "Database restored:"),
        ]

        for event, expected_substring in events:
            self.check_webhook(
                event,
                "Notion Databases",
                expected_message_containing=expected_substring,
            )

    def test_all_comment_events(self) -> None:
        events = [
            ("comment_created", "Comment created:"),
            ("comment_updated", "Comment updated:"),
            ("comment_deleted", "Comment deleted:"),
        ]

        for event, expected_substring in events:
            self.check_webhook(
                event,
                "Notion Comments",
                expected_message_containing=expected_substring,
            )
