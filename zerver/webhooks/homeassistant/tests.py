from zerver.lib.test_classes import WebhookTestCase


class HomeAssistantHookTests(WebhookTestCase):
    def test_simplereq(self) -> None:
        expected_topic_name = "homeassistant"
        expected_message = "The sun will be shining today!"

        self.check_webhook(
            "simplereq",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_req_with_title(self) -> None:
        expected_topic_name = "Weather forecast"
        expected_message = "It will be 30 degrees Celsius out there today!"

        self.check_webhook(
            "reqwithtitle",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )
