# zerver/webhooks/github/tests/test_github_issue_rename.py
from zerver.lib.test_classes import WebhookTestCase
from zerver.models import Message, Recipient

class GitHubIssueRenameWebhookTest(WebhookTestCase):
    STREAM_NAME = "GitHub"
    URL_TEMPLATE = "/api/v1/external/github?stream={stream}&api_key={api_key}"
    WEBHOOK_DIR_NAME = "github"  # required for get_body()

    def test_issue_edited_title_triggers_topic_rename(self) -> None:
        # Ensure the test user is subscribed to the target stream so messages are recorded
        self.subscribe(self.test_user, self.STREAM_NAME)

        # Build the webhook URL (uses URL_TEMPLATE above)
        url = self.build_webhook_url(stream=self.STREAM_NAME)

        # Load the fixture payload from zerver/webhooks/github/fixtures/issues__edited_title.json
        payload = self.get_body("issues__edited_title")

        # Send a POST to the webhook endpoint, include the GitHub required header.
        # Note: Django test client expects header names prefixed with "HTTP_".
        result = self.client_post(
            url,
            payload,
            content_type="application/json",
            HTTP_X_GITHUB_EVENT="issues",
        )

        # If this fails, the response content will help debugging.
        self.assert_json_success(result)

        # Now find the most recent stream message and assert the topic was renamed.
        message = (
            Message.objects.filter(recipient__type=Recipient.STREAM)
            .order_by("-id")
            .first()
        )
        assert message is not None, "Webhook did not create any stream message."

        topic = message.topic_name()

        # Adjust this assertion to match the new title present in your fixture.
        # Replace "New title" with the exact new title string in issues__edited_title.json
        self.assertIn("New Title".casefold(), topic.casefold())
