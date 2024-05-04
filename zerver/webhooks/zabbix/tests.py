from zerver.lib.send_email import FromAddress
from zerver.lib.test_classes import WebhookTestCase
from zerver.models import Recipient
from zerver.webhooks.zabbix.view import MISCONFIGURED_PAYLOAD_ERROR_MESSAGE


class ZabbixHookTests(WebhookTestCase):
    CHANNEL_NAME = "zabbix"
    URL_TEMPLATE = "/api/v1/external/zabbix?api_key={api_key}&stream={stream}"
    WEBHOOK_DIR_NAME = "zabbix"

    def test_zabbix_alert_message(self) -> None:
        """
        Tests if zabbix alert is handled correctly
        """
        expected_topic_name = "www.example.com"
        expected_message = "PROBLEM (Average) alert on [www.example.com](https://zabbix.example.com/tr_events.php?triggerid=14032&eventid=10528):\n* Zabbix agent on www.example.com is unreachable for 5 minutes\n* Agent ping is Up (1)"
        self.check_webhook("zabbix_alert", expected_topic_name, expected_message)

    def test_zabbix_invalid_payload_with_missing_data(self) -> None:
        """
        Tests if invalid Zabbix payloads are handled correctly
        """
        self.url = self.build_webhook_url()
        payload = self.get_body("zabbix_invalid_payload_with_missing_data")
        result = self.client_post(self.url, payload, content_type="application/json")
        self.assert_json_error(result, "Invalid payload")

        expected_message = MISCONFIGURED_PAYLOAD_ERROR_MESSAGE.format(
            bot_name=self.test_user.full_name,
            support_email=FromAddress.SUPPORT,
        ).strip()

        msg = self.get_last_message()
        self.assertEqual(msg.content, expected_message)
        self.assertEqual(msg.recipient.type, Recipient.PERSONAL)
