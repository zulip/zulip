from zerver.lib.test_classes import WebhookTestCase


class SlackIncomingHookTests(WebhookTestCase):
    STREAM_NAME = "slack_incoming"
    URL_TEMPLATE = "/api/v1/external/slack_incoming?&api_key={api_key}&stream={stream}"
    FIXTURE_DIR_NAME = "slack_incoming"

    def test_message(self) -> None:
        expected_topic = "(no topic)"
        expected_message = """
Hello, world.
""".strip()

        self.check_webhook(
            "text",
            expected_topic,
            expected_message,
        )

    def test_message_as_www_urlencoded(self) -> None:
        expected_topic = "devops"
        expected_message = """
:zap: chris has started deploying project tag v0.0.2rc10 to staging
""".strip()

        self.check_webhook(
            "urlencoded_text",
            expected_topic,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_message_with_actions(self) -> None:
        expected_topic = "C1H9RESGL"
        expected_message = """
Danny Torrence left the following review for your property:

[Overlook Hotel](https://google.com) \n :star: \n Doors had too many axe holes, guest in room 237 was far too rowdy, whole place felt stuck in the 1920s.
[Haunted hotel image](https://is5-ssl.mzstatic.com/image/thumb/Purple3/v4/d3/72/5c/d3725c8f-c642-5d69-1904-aa36e4297885/source/256x256bb.jpg)
""".strip()

        self.check_webhook(
            "actions",
            expected_topic,
            expected_message,
        )

    def test_message_with_blocks(self) -> None:
        expected_topic = "(no topic)"
        expected_message = """
Danny Torrence left the following review for your property:

[Overlook Hotel](https://example.com) \n :star: \n Doors had too many axe holes, guest in room 237 was far too rowdy, whole place felt stuck in the 1920s.
[Haunted hotel image](https://is5-ssl.mzstatic.com/image/thumb/Purple3/v4/d3/72/5c/d3725c8f-c642-5d69-1904-aa36e4297885/source/256x256bb.jpg)
""".strip()

        self.check_webhook(
            "blocks",
            expected_topic,
            expected_message,
        )

    def test_message_with_attachment(self) -> None:
        expected_topic = "prometheus-alerts"
        expected_message = """
[[FIRING:2] InstanceDown for api-server (env="prod", severity="critical")](https://alertmanager.local//#/alerts?receiver=default)
:chart_with_upwards_trend: **[Graph](http://generator.local/1)**   :notebook: **[Runbook](https://runbook.local/1)**

**Alert details**:
**Alert:** api-server down - `critical`
**Description:** api-server at 1.2.3.4:8080 couldn't be scraped **Details:**
   • **alertname:** `InstanceDown`
   • **env:** `prod`
   • **instance:** `1.2.3.4:8080`
   • **job:** `api-server`
   • **severity:** `critical`

**Alert:** api-server down - `critical`
**Description:** api-server at 1.2.3.4:8081 couldn't be scraped **Details:**
   • **alertname:** `InstanceDown`
   • **env:** `prod`
   • **instance:** `1.2.3.4:8081`
   • **job:** `api-server`
   • **severity:** `critical`
""".strip()

        self.check_webhook(
            "attachment",
            expected_topic,
            expected_message,
        )

    def get_body(self, fixture_name: str) -> str:
        if "urlencoded" in fixture_name:
            file_type = "txt"
        else:
            file_type = "json"
        return self.webhook_fixture_data("slack_incoming", fixture_name, file_type=file_type)
