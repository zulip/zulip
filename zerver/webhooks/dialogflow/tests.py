from zerver.lib.test_classes import WebhookTestCase


class DialogflowHookTests(WebhookTestCase):
    URL_TEMPLATE = "/api/v1/external/dialogflow?api_key={api_key}&email=AARON@zulip.com"
    WEBHOOK_DIR_NAME = "dialogflow"

    def test_dialogflow_default(self) -> None:
        email = self.example_user("aaron").email
        self.url = self.build_webhook_url(
            email=email,
            username="aaron",
            user_ip="127.0.0.1",
        )
        expected_message = "The weather sure looks great !"
        self.send_and_test_private_message("default", expected_message)

    def test_dialogflow_alternate_result(self) -> None:
        email = self.example_user("aaron").email
        self.url = self.build_webhook_url(
            email=email,
            username="aaron",
            user_ip="127.0.0.1",
        )
        expected_message = "Weather in New Delhi is nice!"
        self.send_and_test_private_message("alternate_result", expected_message)

    def test_dialogflow_error_status(self) -> None:
        email = self.example_user("aaron").email
        self.url = self.build_webhook_url(
            email=email,
            username="aaron",
            user_ip="127.0.0.1",
        )
        expected_message = "403 - Access Denied"
        self.send_and_test_private_message("error_status", expected_message)

    def test_dialogflow_exception(self) -> None:
        email = self.example_user("aaron").email
        self.url = self.build_webhook_url(
            email=email,
            username="aaron",
            user_ip="127.0.0.1",
        )
        expected_message = "Dialogflow couldn't process your query."
        self.send_and_test_private_message("exception", expected_message)
