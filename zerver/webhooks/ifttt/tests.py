from zerver.lib.test_classes import WebhookTestCase


class IFTTTHookTests(WebhookTestCase):
    CHANNEL_NAME = "ifttt"
    URL_TEMPLATE = "/api/v1/external/ifttt?stream={stream}&api_key={api_key}"
    WEBHOOK_DIR_NAME = "ifttt"
    VIEW_FUNCTION_NAME = "api_iftt_app_webhook"

    def test_ifttt_when_subject_and_body_are_correct(self) -> None:
        expected_topic_name = "Email sent from email@email.com"
        expected_message = "Email subject: Subject"
        self.check_webhook("correct_subject_and_body", expected_topic_name, expected_message)

    def test_ifttt_when_topic_and_body_are_correct(self) -> None:
        expected_topic_name = "Email sent from email@email.com"
        expected_message = "Email subject: Subject"
        self.check_webhook("correct_topic_and_body", expected_topic_name, expected_message)

    def test_ifttt_when_topic_is_missing(self) -> None:
        self.url = self.build_webhook_url()
        payload = self.get_body("invalid_payload_with_missing_topic")
        result = self.client_post(self.url, payload, content_type="application/json")
        self.assert_json_error(result, "Topic can't be empty")

    def test_ifttt_when_content_is_missing(self) -> None:
        self.url = self.build_webhook_url()
        payload = self.get_body("invalid_payload_with_missing_content")
        result = self.client_post(self.url, payload, content_type="application/json")
        self.assert_json_error(result, "Content can't be empty")

    def test_ifttt_when_topic_is_dict(self) -> None:
        self.url = self.build_webhook_url()
        payload = self.get_body("invalid_payload_with_dict_topic")
        result = self.client_post(self.url, payload, content_type="application/json")
        self.assert_json_error(result, "Malformed payload")

    def test_ifttt_when_content_is_dict(self) -> None:
        self.url = self.build_webhook_url()
        payload = self.get_body("invalid_payload_with_dict_content")
        result = self.client_post(self.url, payload, content_type="application/json")
        self.assert_json_error(result, "Malformed payload")
