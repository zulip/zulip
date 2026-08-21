import orjson

from zerver.lib.send_email import FromAddress
from zerver.lib.test_classes import WebhookTestCase
from zerver.models import Recipient
from zerver.webhooks.zabbix.view import MISCONFIGURED_PAYLOAD_ERROR_MESSAGE


class ZabbixHookTests(WebhookTestCase):
    def test_zabbix_alert_severities_with_emoji(self) -> None:
        """
        Tests if zabbix alert is handled correctly
        """
        self.url = self.build_webhook_url()
        self.subscribe(self.test_user, self.channel_name)

        a = [
            ("Disaster", ":cross_mark:"),
            ("High", ":rotating_light:"),
            ("Average", ":yellow_circle:"),
            ("Warning", ":warning:"),
            ("Information", ":bulb:"),
            ("Not classified", ":question:"),
        ]

        payload = self.webhook_fixture_data("zabbix", "zabbix_alert")
        data = orjson.loads(payload)

        expected_topic_name = data["hostname"]

        for severity, emoji in a:
            with self.subTest(severity=severity):
                data["severity"] = severity

                expected_message = (
                    f"{emoji} {data['status']} ({severity}) alert on "
                    f"[{data['hostname']}]({data['link']}):\n"
                    f"* {data['trigger']}\n"
                    f"* {data['item']}"
                )

                msg = self.send_webhook_payload(
                    self.test_user,
                    self.url,
                    orjson.dumps(data).decode(),
                    content_type="application/json",
                )

                self.assert_channel_message(
                    message=msg,
                    channel_name=self.channel_name,
                    topic_name=expected_topic_name,
                    content=expected_message,
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
