from zerver.lib.test_classes import WebhookTestCase


class RedmineHookTests(WebhookTestCase):
    CHANNEL_NAME = "redmine"
    URL_TEMPLATE = "/api/v1/external/redmine?api_key={api_key}&stream={stream}"
    WEBHOOK_DIR_NAME = "redmine"

    def test_issue_created(self) -> None:
        expected_topic = "Test Project - Issue"
        expected_message = """**New issue created:** Test issue
**Author:** John Doe"""

        self.check_webhook("issue_created", expected_topic, expected_message)

    def test_issue_opened_with_id(self) -> None:
        expected_topic = "Test Project - Issue #123"
        expected_message = """**New issue created:** Test issue with ID
**Author:** John Doe
**Description:** This is a test description"""

        self.check_webhook("issue_opened", expected_topic, expected_message)

    def test_issue_updated(self) -> None:
        expected_topic = "Test Project - Issue #123"
        expected_message = """**Issue updated:** Updated test issue
**Updated by:** Jane Smith"""

        self.check_webhook("issue_updated", expected_topic, expected_message)
