from zerver.lib.test_classes import WebhookTestCase


class NewRelicHookTests(WebhookTestCase):
    STREAM_NAME = 'newrelic'
    URL_TEMPLATE = "/api/v1/external/newrelic?stream={stream}&api_key={api_key}"

    def test_alert(self) -> None:
        expected_topic = "Apdex score fell below critical level of 0.90"
        expected_message = 'Alert opened on [application name]: Apdex score fell below critical level of 0.90 ([view alert](https://rpm.newrelc.com/accounts/[account_id]/applications/[application_id]/incidents/[incident_id])).'

        self.check_webhook(
            "alert",
            expected_topic,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_deployment(self) -> None:
        expected_topic = 'Test App deploy'
        expected_message = """
**1242** deployed by **Zulip Test**:

``` quote
Description sent via curl
```

Changelog:

``` quote
Changelog string
```
""".strip()

        self.check_webhook(
            "deployment",
            expected_topic,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def get_body(self, fixture_name: str) -> str:
        return self.webhook_fixture_data("newrelic", fixture_name, file_type="txt")
