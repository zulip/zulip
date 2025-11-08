from zerver.lib.test_classes import WebhookTestCase


class CanarytokensHookTests(WebhookTestCase):
    CHANNEL_NAME = "canarytoken"
    URL_TEMPLATE = "/api/v1/external/canarytoken?stream={stream}&api_key={api_key}"
    WEBHOOK_DIR_NAME = "canarytoken"

    def test_canarytoken_new(self) -> None:
        expected_message = (
            "**:alert: Canarytoken has been triggered on 2020-06-09 14:04:39!**\n\n"
            "Congrats! The newly saved webhook works \n\n"
            "[Manage this canarytoken](http://example.com/test/url/for/webhook)"
        )

        self.check_webhook(
            "canarytoken_new",
            "canarytoken alert",
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_canarytoken_real(self) -> None:
        expected_message = (
            "**:alert: Canarytoken has been triggered on 2020-06-09 14:04:47 "
            "(UTC)!**\n\n"
            "Canarytoken example \n\n"
            "[Manage this canarytoken]"
            "(https://canarytokens.org/manage?token=foo&auth=bar)"
        )

        self.check_webhook(
            "canarytoken_real",
            "canarytoken alert",
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_canarytoken_with_specific_topic(self) -> None:
        self.url = self.build_webhook_url(topic="foo")
        expected_message = (
            "**:alert: Canarytoken has been triggered on 2020-06-09 14:04:47 "
            "(UTC)!**\n\n"
            "Canarytoken example \n\n"
            "[Manage this canarytoken]"
            "(https://canarytokens.org/manage?token=foo&auth=bar)"
        )

        self.check_webhook(
            "canarytoken_real",
            "foo",
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )
