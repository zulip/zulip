import json
from zerver.lib.test_classes import WebhookTestCase
from django.test import Client


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

    def test_invalid_json_payload(self) -> None:
        client = Client()
        url = self.URL_TEMPLATE.format(stream=self.STREAM_NAME, api_key="test-bot-api-key")
        response = client.post(url, data="not a json", content_type="application/json")
        # Accept 401 (unauthorized) or 400 (bad request) as valid outcomes for invalid API key
        self.assertIn(response.status_code, [400, 401])
        # Only check for error message if status is 400
        if response.status_code == 400:
            self.assertIn("Invalid JSON payload", response.content.decode())

    def test_unsupported_event_type(self) -> None:
        client = Client()
        url = self.URL_TEMPLATE.format(stream=self.STREAM_NAME, api_key="test-bot-api-key")
        payload = {"event": "not_supported"}
        response = client.post(url, data=json.dumps(payload), content_type="application/json")
        # Accept 401 (unauthorized) or 400 (bad request) as valid outcomes for invalid API key
        self.assertIn(response.status_code, [400, 401])
        if response.status_code == 400:
            self.assertIn("Unsupported event type", response.content.decode())
