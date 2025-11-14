from zerver.lib.test_classes import WebhookTestCase


class RedmineHookTests(WebhookTestCase):
    CHANNEL_NAME = "redmine"
    URL_TEMPLATE = "/api/v1/external/redmine?&api_key={api_key}&stream={stream}"
    WEBHOOK_DIR_NAME = "redmine"

    def test_issue_opened(self) -> None:
        expected_topic_name = "Issue #191"
        expected_message = """test user created issue [#191 Found a bug](https://example.com):
• **Assignee:** test user
• **Status:** new
• **Priority:** normal"""

        self.check_webhook(
            "issue_opened",
            expected_topic_name,
            expected_message,
            content_type="application/json",
        )

    def test_issue_updated(self) -> None:
        expected_topic_name = "Issue #191"
        expected_message = """test user updated issue [#191 Found a bug](https://example.com):
• **Status:** in progress
• **Notes:** I've started working on this issue. The problem seems to be in the authentication module."""

        self.check_webhook(
            "issue_updated",
            expected_topic_name,
            expected_message,
            content_type="application/json",
        )
