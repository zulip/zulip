from zerver.lib.test_classes import WebhookTestCase

class RedmineWebhookTests(WebhookTestCase):
    STREAM_NAME = "redmine"
    CHANNEL_NAME = "redmine"
    WEBHOOK_DIR_NAME = "redmine"
    URL_TEMPLATE = "/api/v1/external/redmine?stream={stream}&api_key={api_key}"

    def test_issue_created(self) -> None:
        expected_topic = "Issue #123: Sample issue subject"
        expected_message = (
            "**New issue created in _Sample Project_**\n"
            "**Type:** Bug\n"
            "**Status:** New\n"
            "**Priority:** Normal\n"
            "**Author:** John Smith\n"
            "**Assigned to:** Jane Doe\n"
            "**Description:**\nThis is a sample issue description.\n"
            "[View issue](https://redmine.example.com/issues/123)"
        )
        self.check_webhook("issue_created", expected_topic, expected_message)
         