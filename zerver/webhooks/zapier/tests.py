from zerver.lib.test_classes import WebhookTestCase


class ZapierHookTests(WebhookTestCase):
    CHANNEL_NAME = "zapier"
    URL_TEMPLATE = "/api/v1/external/zapier?stream={stream}&api_key={api_key}"
    WEBHOOK_DIR_NAME = "zapier"

    def test_zapier_when_subject_and_body_are_correct(self) -> None:
        expected_topic_name = "New email from zulip@zulip.com"
        expected_message = "Your email content is: \nMy Email content."
        self.check_webhook("correct_subject_and_body", expected_topic_name, expected_message)

    def test_zapier_when_topic_and_body_are_correct(self) -> None:
        expected_topic_name = "New email from zulip@zulip.com"
        expected_message = "Your email content is: \nMy Email content."
        self.check_webhook("correct_topic_and_body", expected_topic_name, expected_message)

    def test_zapier_weather_update(self) -> None:
        expected_topic_name = "Here is your weather update for the day:"
        expected_message = (
            "Foggy in the morning.\nMaximum temperature to be 24.\nMinimum temperature to be 12"
        )
        self.check_webhook("weather_update", expected_topic_name, expected_message)


class ZapierZulipAppTests(WebhookTestCase):
    CHANNEL_NAME = "zapier"
    URL_TEMPLATE = "/api/v1/external/zapier?api_key={api_key}&stream={stream}"
    WEBHOOK_DIR_NAME = "zapier"

    def test_auth(self) -> None:
        payload = self.get_body("zapier_zulip_app_auth")
        result = self.client_post(self.url, payload, content_type="application/json")
        json_result = self.assert_json_success(result)
        self.assertEqual(json_result["full_name"], "Zulip Webhook Bot")
        self.assertEqual(json_result["email"], "webhook-bot@zulip.com")
        self.assertIn("id", json_result)
