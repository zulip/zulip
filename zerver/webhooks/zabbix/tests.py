# -*- coding: utf-8 -*-
from zerver.lib.test_classes import WebhookTestCase

from zerver.models import Recipient
from zerver.lib.send_email import FromAddress
from zerver.webhooks.zabbix.view import MISCONFIGURED_PAYLOAD_ERROR_MESSAGE

class ZabbixHookTests(WebhookTestCase):
    STREAM_NAME = 'zabbix'
    URL_TEMPLATE = u"/api/v1/external/zabbix?api_key={api_key}&stream={stream}"
    FIXTURE_DIR_NAME = 'zabbix'

    def test_zabbix_alert_message(self) -> None:
        """
        Tests if zabbix alert is handled correctly
        """
        expected_topic = u"www.example.com"
        expected_message = u"PROBLEM (Average) alert on [www.example.com](https://zabbix.example.com/tr_events.php?triggerid=14032&eventid=10528).\nZabbix agent on www.example.com is unreachable for 5 minutes\nAgent ping is Up (1)"
        self.send_and_test_stream_message('zabbix_alert', expected_topic, expected_message)

    def test_zabbix_invalid_payload_with_missing_data(self) -> None:
        """
        Tests if invalid Zabbix payloads are handled correctly
        """
        self.url = self.build_webhook_url()
        payload = self.get_body('zabbix_invalid_payload_with_missing_data')
        result = self.client_post(self.url, payload, content_type='application/json')
        self.assert_json_error(result, "Invalid payload")

        expected_message = MISCONFIGURED_PAYLOAD_ERROR_MESSAGE.format(
            bot_name=self.test_user.full_name,
            support_email=FromAddress.SUPPORT
        ).strip()

        msg = self.get_last_message()
        self.assertEqual(msg.content, expected_message)
        self.assertEqual(msg.recipient.type, Recipient.PERSONAL)

    def get_body(self, fixture_name: str) -> str:
        return self.webhook_fixture_data("zabbix", fixture_name, file_type="json")
