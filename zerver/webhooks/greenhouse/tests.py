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
        expected_message = ("Hire Candidate\n>Johnny Smith\nID: 19"
                            "\nApplying for role:\nDeveloper\n**Emails:**"
                            "\nPersonal\npersonal@example.com\nWork\nwork@example.com\n\n\n>"
                            "**Attachments:**\n[Resume](https://prod-heroku.s3.amazonaws.com/...)")

        self.send_and_test_stream_message('candidate_hired',
                                          expected_topic,
                                          expected_message,
                                          content_type=self.CONTENT_TYPE)

    def test_message_candidate_rejected(self) -> None:
        expected_topic = "Reject Candidate - 265788"
        expected_message = ("Reject Candidate\n>Hector Porter\nID: "
                            "265788\nApplying for role:\nDesigner"
                            "\n**Emails:**\nPersonal\n"
                            "hector.porter.265788@example.com\n\n\n>"
                            "**Attachments:**\n[Resume](https://prod-heroku.s3.amazonaws.com/...)")

        self.send_and_test_stream_message('candidate_rejected',
                                          expected_topic,
                                          expected_message,
                                          content_type=self.CONTENT_TYPE)

    def test_message_candidate_stage_change(self) -> None:
        expected_topic = "Candidate Stage Change - 265772"
        expected_message = ("Candidate Stage Change\n>Giuseppe Hurley"
                            "\nID: 265772\nApplying for role:\n"
                            "Designer\n**Emails:**\nPersonal"
                            "\ngiuseppe.hurley@example.com\n\n\n>"
                            "**Attachments:**\n[Resume](https://prod-heroku.s3.amazonaws.com/...)"
                            "\n[Cover_Letter](https://prod-heroku.s3.amazonaws.com/...)"
                            "\n[Attachment](https://prod-heroku.s3.amazonaws.com/...)")

        self.send_and_test_stream_message('candidate_stage_change',
                                          expected_topic,
                                          expected_message,
                                          content_type=self.CONTENT_TYPE)

    def test_message_prospect_created(self) -> None:
        expected_topic = "New Prospect Application - 968190"
        expected_message = ("New Prospect Application\n>Trisha Troy"
                            "\nID: 968190\nApplying for role:\n"
                            "Designer\n**Emails:**\nPersonal"
                            "\nt.troy@example.com\n\n\n>**Attachments:**"
                            "\n[Resume](https://prod-heroku.s3.amazonaws.com/...)")

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
