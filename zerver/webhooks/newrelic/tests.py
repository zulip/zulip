from zerver.lib.test_classes import WebhookTestCase


class NewRelicHookTests(WebhookTestCase):
    CHANNEL_NAME = "newrelic"
    URL_TEMPLATE = "/api/v1/external/newrelic?stream={stream}&api_key={api_key}"
    WEBHOOK_DIR_NAME = "newrelic"

    # The following 9 unit tests are for the old format
    # corresponding json fixtures were renamed to have the "_old" trailing
    # These tests and fixtures are to be deleted when old notifications EOLed

    def test_open_old(self) -> None:
        expected_topic_name = "Test policy name (1234)"
        expected_message = """
[Incident](https://alerts.newrelic.com/accounts/2941966/incidents/1234) **opened** for condition: **Server Down** at <time:2020-11-11 22:32:11.151000+00:00>
``` quote
Violation description test.
```
""".strip()

        self.check_webhook(
            "incident_opened_old",
            expected_topic_name,
            expected_message,
            content_type="application/json",
        )

    def test_closed_old(self) -> None:
        expected_topic_name = "Test policy name (1234)"
        expected_message = """
[Incident](https://alerts.newrelic.com/accounts/2941966/incidents/1234) **closed** for condition: **Server Down**
""".strip()

        self.check_webhook(
            "incident_closed_old",
            expected_topic_name,
            expected_message,
            content_type="application/json",
        )

    def test_acknowledged_old(self) -> None:
        expected_topic_name = "Test policy name (1234)"
        expected_message = """
[Incident](https://alerts.newrelic.com/accounts/2941966/incidents/1234) **acknowledged** by **Alice** for condition: **Server Down**
""".strip()

        self.check_webhook(
            "incident_acknowledged_old",
            expected_topic_name,
            expected_message,
            content_type="application/json",
        )

    def test_not_recognized_old(self) -> None:
        with self.assertRaises(AssertionError) as e:
            self.check_webhook(
                "incident_state_not_recognized_old",
                "",
                "",
                content_type="application/json",
            )
        self.assertIn(
            "The newrelic webhook requires current_state be in [open|acknowledged|closed]",
            e.exception.args[0],
        )

    def test_missing_fields_old(self) -> None:
        expected_topic_name = "Unknown Policy (Unknown ID)"
        expected_message = """
[Incident](https://alerts.newrelic.com) **opened** for condition: **Unknown condition** at <time:2020-11-11 22:32:11.151000+00:00>
``` quote
No details.
```
""".strip()

        self.check_webhook(
            "incident_default_fields_old",
            expected_topic_name,
            expected_message,
            content_type="application/json",
        )

    def test_missing_current_state_old(self) -> None:
        with self.assertRaises(AssertionError) as e:
            self.check_webhook(
                "incident_missing_current_state_old",
                "",
                "",
                content_type="application/json",
            )
        self.assertIn(
            "The newrelic webhook requires current_state be in [open|acknowledged|closed]",
            e.exception.args[0],
        )

    def test_missing_timestamp_old(self) -> None:
        with self.assertRaises(AssertionError) as e:
            self.check_webhook(
                "incident_missing_timestamp_old",
                "",
                "",
                content_type="application/json",
            )
        self.assertIn(
            "The newrelic webhook requires timestamp in milliseconds", e.exception.args[0]
        )

    def test_malformatted_time_old(self) -> None:
        with self.assertRaises(AssertionError) as e:
            self.check_webhook(
                "incident_malformatted_time_old",
                "",
                "",
                content_type="application/json",
            )
        self.assertIn("The newrelic webhook expects time in milliseconds.", e.exception.args[0])

    def test_time_too_large_old(self) -> None:
        with self.assertRaises(AssertionError) as e:
            self.check_webhook(
                "incident_time_too_large_old",
                "",
                "",
                content_type="application/json",
            )
        self.assertIn("The newrelic webhook expects time in milliseconds.", e.exception.args[0])

    # The following 10 unit tests are for the new format
    # One more test than the old format as we have 4 states instead of 3 in the old
    # corresponding json fixtures have "_new" trailing in the name

    def test_activated_new(self) -> None:
        expected_topic_name = "Test policy name (8ceed342-f305-4bfa-adb8-97ba93f5dd26)"
        expected_message = """
[Incident](https://alerts.newrelic.com/accounts/2941966/incidents/1234) **active** for condition: **Server Down** at <time:2020-11-11 22:32:11.151000+00:00>
``` quote
Violation description test.
```
""".strip()

        self.check_webhook(
            "incident_active_new",
            expected_topic_name,
            expected_message,
            content_type="application/json",
        )

    def test_created_new(self) -> None:
        expected_topic_name = "Test policy name (8114ada3-572e-4550-a310-12375371669e)"
        expected_message = """
[Incident](https://alerts.newrelic.com/accounts/2941966/incidents/1234) **created** for condition: **Server Down**
""".strip()

        self.check_webhook(
            "incident_created_new",
            expected_topic_name,
            expected_message,
            content_type="application/json",
        )

    def test_closed_new(self) -> None:
        expected_topic_name = "Test policy name (f0d98b28-bf9d-49e7-b9d0-ac7cbb52e73a)"
        expected_message = """
[Incident](https://alerts.newrelic.com/accounts/2941966/incidents/1234) **closed** for condition: **Server Down**
""".strip()

        self.check_webhook(
            "incident_closed_new",
            expected_topic_name,
            expected_message,
            content_type="application/json",
        )

    def test_acknowledged_new(self) -> None:
        expected_topic_name = "Test policy name (3576f543-dc3c-4d97-9f16-5c81f35195cb)"
        expected_message = """
[Incident](https://alerts.newrelic.com/accounts/2941966/incidents/1234) **acknowledged** by **Alice** for condition: **Server Down**
""".strip()

        self.check_webhook(
            "incident_acknowledged_new",
            expected_topic_name,
            expected_message,
            content_type="application/json",
        )

    def test_not_recognized_new(self) -> None:
        with self.assertRaises(AssertionError) as e:
            self.check_webhook(
                "incident_state_not_recognized_new",
                "",
                "",
                content_type="application/json",
            )
        self.assertIn(
            "The newrelic webhook requires state be in [created|activated|acknowledged|closed]",
            e.exception.args[0],
        )

    def test_missing_fields_new(self) -> None:
        expected_topic_name = "Unknown Policy (e04156e4-4cac-4f39-9d27-75d361e40a6d)"
        expected_message = """
[Incident](https://alerts.newrelic.com) **active** for condition: **Unknown condition** at <time:2020-11-11 22:32:11.151000+00:00>
``` quote
No details.
```
""".strip()

        self.check_webhook(
            "incident_default_fields_new",
            expected_topic_name,
            expected_message,
            content_type="application/json",
        )

    def test_missing_state_new(self) -> None:
        with self.assertRaises(AssertionError) as e:
            self.check_webhook(
                "incident_missing_state_new",
                "",
                "",
                content_type="application/json",
            )
        self.assertIn(
            "The newrelic webhook requires state be in [created|activated|acknowledged|closed]",
            e.exception.args[0],
        )

    def test_missing_timestamp_new(self) -> None:
        with self.assertRaises(AssertionError) as e:
            self.check_webhook(
                "incident_missing_timestamp_new",
                "",
                "",
                content_type="application/json",
            )
        self.assertIn(
            "The newrelic webhook requires timestamp in milliseconds", e.exception.args[0]
        )

    def test_malformatted_time_new(self) -> None:
        with self.assertRaises(AssertionError) as e:
            self.check_webhook(
                "incident_malformatted_time_new",
                "",
                "",
                content_type="application/json",
            )
        self.assertIn("The newrelic webhook expects time in milliseconds.", e.exception.args[0])

    def test_time_too_large_new(self) -> None:
        with self.assertRaises(AssertionError) as e:
            self.check_webhook(
                "incident_time_too_large_new",
                "",
                "",
                content_type="application/json",
            )
        self.assertIn("The newrelic webhook expects time in milliseconds.", e.exception.args[0])
