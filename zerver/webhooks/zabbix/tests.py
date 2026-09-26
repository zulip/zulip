import orjson

from zerver.lib.send_email import FromAddress
from zerver.lib.test_classes import WebhookTestCase
from zerver.models import Recipient
from zerver.webhooks.zabbix.view import MISCONFIGURED_PAYLOAD_ERROR_MESSAGE, ZABBIX_SEVERITY_EMOJI


class ZabbixHookTests(WebhookTestCase):
    def test_zabbix_alert_severities_with_emoji(self) -> None:
        """
        Tests if zabbix alert is handled correctly
        """
        expected_message_template = "{emoji} PROBLEM ({severity}) alert on [www.example.com](https://zabbix.example.com/tr_events.php?triggerid=14032&eventid=10528):\n* Zabbix agent on www.example.com is unreachable for 5 minutes\n* Agent ping is Up (1)"
        payload = orjson.loads(self.get_body("zabbix_alert"))

        for severity, emoji in ZABBIX_SEVERITY_EMOJI.items():
            with self.subTest(severity=severity):
                payload["severity"] = severity
                self.check_webhook(
                    "zabbix_alert",
                    "www.example.com",
                    expected_message_template.format(emoji=emoji, severity=severity),
                    custom_payload=payload,
                )

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
        self.assertEqual(msg.recipient.type, Recipient.DIRECT_MESSAGE_GROUP)
