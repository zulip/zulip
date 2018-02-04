# -*- coding: utf-8 -*-
from zerver.lib.test_classes import WebhookTestCase

class PingdomHookTests(WebhookTestCase):
    STREAM_NAME = 'pingdom'
    URL_TEMPLATE = u"/api/v1/external/pingdom?stream={stream}&api_key={api_key}"
    FIXTURE_DIR_NAME = 'pingdom'

    def test_pingdom_from_up_to_down_http_check_message(self) -> None:
        """
        Tests if pingdom http check from up to down is handled correctly
        """
        expected_message = u"Service someurl.com changed its HTTP status from UP to DOWN.\nDescription: Non-recoverable failure in name resolution."
        self.send_and_test_stream_message('http_up_to_down', u"Test check status.", expected_message)

    def test_pingdom_from_up_to_down_smtp_check_message(self) -> None:
        """
        Tests if pingdom smtp check from up to down is handled correctly
        """
        expected_message = u"Service smtp.someurl.com changed its SMTP status from UP to DOWN.\nDescription: Connection refused."
        self.send_and_test_stream_message('smtp_up_to_down', u"SMTP check status.", expected_message)

    def test_pingdom_from_up_to_down_imap_check_message(self) -> None:
        """
        Tests if pingdom imap check from up to down is handled correctly
        """
        expected_message = u"Service imap.someurl.com changed its IMAP status from UP to DOWN.\nDescription: Invalid hostname, address or socket."
        self.send_and_test_stream_message('imap_up_to_down', u"IMAP check status.", expected_message)

    def test_pingdom_from_down_to_up_imap_check_message(self) -> None:
        """
        Tests if pingdom imap check from down to up is handled correctly
        """
        expected_message = u"Service imap.someurl.com changed its IMAP status from DOWN to UP."
        self.send_and_test_stream_message('imap_down_to_up', u"IMAP check status.", expected_message)
