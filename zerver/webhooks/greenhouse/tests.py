# -*- coding: utf-8 -*-

from mock import MagicMock, patch

from zerver.lib.test_classes import WebhookTestCase

class GreenhouseHookTests(WebhookTestCase):
    STREAM_NAME = 'greenhouse'
    URL_TEMPLATE = "/api/v1/external/greenhouse?stream={stream}&api_key={api_key}"
    FIXTURE_DIR_NAME = 'greenhouse'
    CONTENT_TYPE = "application/x-www-form-urlencoded"

    def test_message_candidate_hired(self) -> None:
        expected_topic = "Hire Candidate - 19"
        expected_message = """
Hire Candidate Johnny Smith (ID: 19), applying for:
* **Role**: Developer
* **Emails**: personal@example.com (Personal), work@example.com (Work)
* **Attachments**: [Resume](https://prod-heroku.s3.amazonaws.com/...)
""".strip()

        self.send_and_test_stream_message('candidate_hired',
                                          expected_topic,
                                          expected_message,
                                          content_type=self.CONTENT_TYPE)

    def test_message_candidate_rejected(self) -> None:
        expected_topic = "Reject Candidate - 265788"
        expected_message = """
Reject Candidate Hector Porter (ID: 265788), applying for:
* **Role**: Designer
* **Emails**: hector.porter.265788@example.com (Personal)
* **Attachments**: [Resume](https://prod-heroku.s3.amazonaws.com/...)
""".strip()

        self.send_and_test_stream_message('candidate_rejected',
                                          expected_topic,
                                          expected_message,
                                          content_type=self.CONTENT_TYPE)

    def test_message_candidate_stage_change(self) -> None:
        expected_topic = "Candidate Stage Change - 265772"
        expected_message = """
Candidate Stage Change Giuseppe Hurley (ID: 265772), applying for:
* **Role**: Designer
* **Emails**: giuseppe.hurley@example.com (Personal)
* **Attachments**: [Resume](https://prod-heroku.s3.amazonaws.com/...), [Cover_Letter](https://prod-heroku.s3.amazonaws.com/...), [Attachment](https://prod-heroku.s3.amazonaws.com/...)
""".strip()

        self.send_and_test_stream_message('candidate_stage_change',
                                          expected_topic,
                                          expected_message,
                                          content_type=self.CONTENT_TYPE)

    def test_message_prospect_created(self) -> None:
        expected_topic = "New Prospect Application - 968190"
        expected_message = """
New Prospect Application Trisha Troy (ID: 968190), applying for:
* **Role**: Designer
* **Emails**: t.troy@example.com (Personal)
* **Attachments**: [Resume](https://prod-heroku.s3.amazonaws.com/...)
""".strip()

        self.send_and_test_stream_message('prospect_created',
                                          expected_topic,
                                          expected_message,
                                          content_type=self.CONTENT_TYPE)

    @patch('zerver.webhooks.greenhouse.view.check_send_webhook_message')
    def test_ping_message_ignore(
            self, check_send_webhook_message_mock: MagicMock) -> None:
        self.url = self.build_webhook_url()
        payload = self.get_body('ping_event')
        result = self.client_post(self.url, payload, content_type=self.CONTENT_TYPE)
        self.assertFalse(check_send_webhook_message_mock.called)
        self.assert_json_success(result)

    def get_body(self, fixture_name: str) -> str:
        return self.webhook_fixture_data("greenhouse", fixture_name, file_type="json")
