from zerver.lib.test_classes import WebhookTestCase


class PingdomHookTests(WebhookTestCase):
    CHANNEL_NAME = "pingdom"
    URL_TEMPLATE = "/api/v1/external/pingdom?stream={stream}&api_key={api_key}"
    WEBHOOK_DIR_NAME = "pingdom"

    def test_pingdom_from_up_to_down_http_check_message(self) -> None:
        """
        Tests if pingdom http check from up to down is handled correctly
        """
        expected_message = "Service someurl.com changed its HTTP status from UP to DOWN:\n\n``` quote\nNon-recoverable failure in name resolution\n```"
        self.check_webhook("http_up_to_down", "Test check status.", expected_message)

    def test_pingdom_from_up_to_down_smtp_check_message(self) -> None:
        """
        Tests if pingdom smtp check from up to down is handled correctly
        """
        expected_message = "Service smtp.someurl.com changed its SMTP status from UP to DOWN:\n\n``` quote\nConnection refused\n```"
        self.check_webhook("smtp_up_to_down", "SMTP check status.", expected_message)

    def test_pingdom_from_up_to_down_imap_check_message(self) -> None:
        """
        Tests if pingdom imap check from up to down is handled correctly
        """
        expected_message = "Service imap.someurl.com changed its IMAP status from UP to DOWN:\n\n``` quote\nInvalid hostname, address or socket\n```"
        self.check_webhook("imap_up_to_down", "IMAP check status.", expected_message)

    def test_pingdom_from_down_to_up_imap_check_message(self) -> None:
        """
        Tests if pingdom imap check from down to up is handled correctly
        """
        expected_message = "Service imap.someurl.com changed its IMAP status from DOWN to UP."
        self.check_webhook("imap_down_to_up", "IMAP check status.", expected_message)
