from zerver.lib.test_classes import WebhookTestCase


class OpenCollectiveHookTests(WebhookTestCase):
    CHANNEL_NAME = "test"
    URL_TEMPLATE = "/api/v1/external/opencollective?&api_key={api_key}&stream={stream}"
    WEBHOOK_DIR_NAME = "opencollective"

    # Note: Include a test function per each distinct message condition your integration supports
    def test_one_time_donation(self) -> None:  # test one time donation
        expected_topic_name = "New Member"
        expected_message = "@_**Λευτέρης Κυριαζάνος** donated **€1.00**! :tada:"

        self.check_webhook(
            "one_time_donation",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_one_time_incognito_donation(self) -> None:  # test one time incognito donation
        expected_topic_name = "New Member"
        expected_message = "An **Incognito** member donated **$1.00**! :tada:"

        # use fixture named helloworld_hello
        self.check_webhook(
            "one_time_incognito_donation",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )
