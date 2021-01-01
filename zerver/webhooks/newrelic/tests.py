from zerver.lib.test_classes import WebhookTestCase


class NewRelicHookTests(WebhookTestCase):
    STREAM_NAME = 'newrelic'
    URL_TEMPLATE = "/api/v1/external/newrelic?stream={stream}&api_key={api_key}"
    FIXTURE_DIR_NAME = 'newrelic'

    def test_open(self) -> None:
        expected_topic = "Test policy name (1234)"
        expected_message = """
[Incident](https://alerts.newrelic.com/accounts/2941966/incidents/1234) **opened** for condition: **Server Down** at <time:2020-11-11 22:32:11.151000+00:00>
``` quote
Violation description test.
```
""".strip()

        self.check_webhook(
            "incident_opened",
            expected_topic,
            expected_message,
            content_type="application/json",
        )

    def test_closed(self) -> None:
        expected_topic = "Test policy name (1234)"
        expected_message = """
[Incident](https://alerts.newrelic.com/accounts/2941966/incidents/1234) **closed** for condition: **Server Down**
""".strip()

        self.check_webhook(
            "incident_closed",
            expected_topic,
            expected_message,
            content_type="application/json",
        )

    def test_acknowledged(self) -> None:
        expected_topic = "Test policy name (1234)"
        expected_message = """
[Incident](https://alerts.newrelic.com/accounts/2941966/incidents/1234) **acknowledged** by **Alice** for condition: **Server Down**
""".strip()

        self.check_webhook(
            "incident_acknowledged",
            expected_topic,
            expected_message,
            content_type="application/json",
        )

    def test_not_recognized(self) -> None:
        with self.assertRaises(AssertionError) as e:
            self.check_webhook(
                "incident_state_not_recognized",
                "",
                "",
                content_type="application/json",
            )
        self.assertIn("The newrelic webhook requires current_state be in [open|acknowledged|closed]", e.exception.args[0])

    def test_missing_fields(self) -> None:
        expected_topic = "Unknown Policy (Unknown ID)"
        expected_message = """
[Incident](https://alerts.newrelic.com) **opened** for condition: **Unknown condition** at <time:2020-11-11 22:32:11.151000+00:00>
``` quote
No details.
```
""".strip()

        self.check_webhook(
            "incident_default_fields",
            expected_topic,
            expected_message,
            content_type="application/json",
        )

    def test_missing_current_state(self) -> None:
        with self.assertRaises(AssertionError) as e:
            self.check_webhook(
                "incident_missing_current_state",
                "",
                "",
                content_type="application/json",
            )
        self.assertIn("The newrelic webhook requires current_state be in [open|acknowledged|closed]", e.exception.args[0])

    def test_missing_timestamp(self) -> None:
        with self.assertRaises(AssertionError) as e:
            self.check_webhook(
                "incident_missing_timestamp",
                "",
                "",
                content_type="application/json",
            )
        self.assertIn("The newrelic webhook requires timestamp in milliseconds", e.exception.args[0])

    def test_malformatted_time(self) -> None:
        with self.assertRaises(AssertionError) as e:
            self.check_webhook(
                "incident_malformatted_time",
                "",
                "",
                content_type="application/json",
            )
        self.assertIn("The newrelic webhook expects time in milleseconds.", e.exception.args[0])

    def test_time_too_large(self) -> None:
        with self.assertRaises(AssertionError) as e:
            self.check_webhook(
                "incident_time_too_large",
                "",
                "",
                content_type="application/json",
            )
        self.assertIn("The newrelic webhook expects time in milleseconds.", e.exception.args[0])
