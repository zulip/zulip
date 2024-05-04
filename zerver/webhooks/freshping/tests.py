from zerver.lib.test_classes import WebhookTestCase


class FreshpingHookTests(WebhookTestCase):
    CHANNEL_NAME = "freshping"
    URL_TEMPLATE = "/api/v1/external/freshping?api_key={api_key}&stream={stream}"
    WEBHOOK_DIR_NAME = "freshping"

    def test_freshping_check_test(self) -> None:
        """
        Tests if freshping check test is handled correctly
        """
        expected_topic_name = "Freshping"
        expected_message = "Freshping webhook has been successfully configured."
        self.check_webhook("freshping_check_test", expected_topic_name, expected_message)

    def test_freshping_check_unreachable(self) -> None:
        """
        Tests if freshping check unreachable is handled correctly
        """
        expected_topic_name = "Test Check"
        expected_message = """
https://example.com has just become unreachable.
Error code: 521.
""".strip()
        self.check_webhook("freshping_check_unreachable", expected_topic_name, expected_message)

    def test_freshping_check_reachable(self) -> None:
        """
        Tests if freshping check reachable is handled correctly
        """
        expected_topic_name = "Test Check"
        expected_message = "https://example.com is back up and no longer unreachable."
        self.check_webhook("freshping_check_reachable", expected_topic_name, expected_message)
