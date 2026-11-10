import orjson
from typing_extensions import override

from zerver.lib.test_classes import ZulipTestCase
from zerver.models import Message
from zerver.models.realms import get_realm


class HoneybadgerHookTests(ZulipTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        self.bot = self.get_user_from_email("webhook-bot@zulip.com", get_realm("zulip"))
        self.subscribe(self.bot, "honeybadger")
        self.url = f"/api/v1/external/honeybadger?stream=honeybadger&api_key={self.bot.api_key}"

    def check_notification(self, fixture: str, topic: str, content: str) -> None:
        message = self.send_webhook_payload(
            self.bot,
            self.url,
            self.webhook_fixture_data("honeybadger", fixture),
            content_type="application/json",
        )
        self.assert_notification(message, topic, content)

    def assert_notification(self, message: Message, topic: str, content: str) -> None:
        self.assert_message_stream_name(message, "honeybadger")
        self.assertEqual(message.topic_name(), topic)
        self.assertEqual(message.content, content)

    def test_error_events(self) -> None:
        messages = {
            "occurred": "[Billing API/production] NoMethodError: undefined method 'total' for nil",
            "rate_exceeded": "[Billing API/production] NoMethodError has occurred 5 time(s) in the past minute",
            "resolved": "[Billing API/production] NoMethodError resolved by Jane Doe",
            "unresolved": "[Billing API/production] NoMethodError unresolved by Jane Doe",
            "assigned": "[Billing API/production] NoMethodError assigned to Jane Doe by Jane Doe",
            "commented": "[Billing API/production] Jane Doe commented on NoMethodError: Looking into this now.",
        }
        for event, message in messages.items():
            with self.subTest(event=event):
                self.check_notification(
                    f"v2_{event}",
                    "Error #26225",
                    message
                    + "\n\n[View error](https://app.honeybadger.io/projects/85736/faults/26225)",
                )

    def test_deployment(self) -> None:
        self.check_notification(
            "v2_deployed",
            "Project #85736",
            "[Billing API/production] deploy-bot deployed Billing API to production\n\n"
            "[View deployment](https://github.com/acme/billing/commit/850510ab072102729e6967cf89f28b740c61311b)",
        )

    def test_volume_spike(self) -> None:
        self.check_notification(
            "v2_volume_spike",
            "Project #85736",
            "[Billing API] Errors are 3.2× your normal rate (412 in the last hour vs ~128/hr typical)\n\n"
            "[View project](https://app.honeybadger.io/projects/85736/faults)",
        )

    def test_uptime_events(self) -> None:
        messages = {
            "down": "[Billing API] Checkout is down.",
            "up": "[Billing API] Checkout is back up after 7m 1s.",
            "cert_will_expire": "[Billing API] SSL certificate for Checkout will expire on 11/4/2026 23:59:59 UTC",
        }
        for event, message in messages.items():
            with self.subTest(event=event):
                self.check_notification(
                    f"v2_{event}",
                    "Uptime 8121ab91-87fd-4e92-ae23-a7b5bf915a2f",
                    message
                    + "\n\n[View uptime monitor](https://app.honeybadger.io/projects/85736/sites/8121ab91-87fd-4e92-ae23-a7b5bf915a2f)",
                )

    def test_check_in_events(self) -> None:
        messages = {
            "check_in_missing": "[Billing API] MISSING: Nightly invoice run hasn't checked in for 1 day",
            "check_in_reporting": "[Billing API] REPORTING: Nightly invoice run is reporting again",
        }
        for event, message in messages.items():
            with self.subTest(event=event):
                self.check_notification(
                    f"v2_{event}",
                    "Check-in b3IAob",
                    message
                    + "\n\n[View check-ins](https://app.honeybadger.io/projects/85736/check_ins)",
                )

    def test_alarm_events(self) -> None:
        messages = {
            "alarm_alert": "[Billing API] ALERT: Checkout errors is in alert status",
            "alarm_ok": "[Billing API] OK: Checkout errors is no longer in alert status",
        }
        for event, message in messages.items():
            with self.subTest(event=event):
                self.check_notification(
                    f"v2_{event}",
                    "Alarm opticon-observer-root-id",
                    message
                    + "\n\n[View alarm](https://app.honeybadger.io/projects/85736/insights/alarms/opticon-observer-root-id)",
                )

    def test_recorded_error(self) -> None:
        self.check_notification(
            "test_error",
            "Error #123",
            "[Zulip Integration/production] TestingException: This is a test error generated by Honeybadger\n\n"
            "[View error](https://app.honeybadger.io/projects/54639/faults/123)",
        )

    def test_alarm_without_id_or_name(self) -> None:
        payload = orjson.loads(self.webhook_fixture_data("honeybadger", "v2_alarm_alert"))
        payload["alarm"]["id"] = None
        payload["alarm"]["name"] = None
        message = self.send_webhook_payload(
            self.bot, self.url, orjson.dumps(payload).decode(), content_type="application/json"
        )
        self.assert_notification(
            message,
            "Alarm opticon-observer-root-id",
            "[Billing API] ALERT: Checkout errors is in alert status\n\n"
            "[View alarm](https://app.honeybadger.io/projects/85736/insights/alarms/opticon-observer-root-id)",
        )

    def test_error_from_inactive_account(self) -> None:
        payload = orjson.loads(self.webhook_fixture_data("honeybadger", "v2_resolved"))
        payload["fault"] = {
            key: payload["fault"][key] for key in ["id", "project_id", "message", "created_at"]
        }
        del payload["actor"]
        message = self.send_webhook_payload(
            self.bot, self.url, orjson.dumps(payload).decode(), content_type="application/json"
        )
        self.assert_notification(
            message,
            "Error #26225",
            "[Billing API/production] NoMethodError resolved by Jane Doe",
        )

    def test_recorded_uptime(self) -> None:
        self.check_notification(
            "uptime",
            "Uptime 59ad71ac-6d2e-4fd0-a04f-b5c916c8f57e",
            "[Zulip Integration] Zulip will now receive uptime alerts.",
        )

    def test_recorded_check_in(self) -> None:
        self.check_notification(
            "checkin",
            "Check-in 15mIYe",
            "[Zulip Integration] MISSING: Zulip hasn't checked in for 6 minutes",
        )

    def test_event_filters(self) -> None:
        self.url += '&only_events=["resolved"]'
        initial_count = Message.objects.count()
        result = self.client_post(
            self.url,
            self.webhook_fixture_data("honeybadger", "v2_occurred"),
            content_type="application/json",
        )
        self.assert_json_success(result)
        self.assertEqual(Message.objects.count(), initial_count)
        self.check_notification(
            "v2_resolved",
            "Error #26225",
            "[Billing API/production] NoMethodError resolved by Jane Doe\n\n"
            "[View error](https://app.honeybadger.io/projects/85736/faults/26225)",
        )

    def test_custom_topic(self) -> None:
        self.url += "&topic=monitoring"
        self.check_notification(
            "v2_resolved",
            "monitoring",
            "[Billing API/production] NoMethodError resolved by Jane Doe\n\n"
            "[View error](https://app.honeybadger.io/projects/85736/faults/26225)",
        )

    def test_unknown_event(self) -> None:
        payload = orjson.loads(self.webhook_fixture_data("honeybadger", "v2_occurred"))
        payload["event"] = "unknown"
        initial_count = Message.objects.count()
        with self.assertLogs("zulip.zerver.webhooks.unsupported", level="ERROR"):
            result = self.client_post(
                self.url, orjson.dumps(payload).decode(), content_type="application/json"
            )
        self.assert_json_success(result)
        self.assertEqual(Message.objects.count(), initial_count)

    def test_invalid_api_key(self) -> None:
        initial_count = Message.objects.count()
        result = self.client_post(
            "/api/v1/external/honeybadger?stream=honeybadger&api_key=00000000000000000000000000000000",
            self.webhook_fixture_data("honeybadger", "v2_occurred"),
            content_type="application/json",
        )
        self.assert_json_error(result, "Invalid API key", status_code=401)
        self.assertEqual(Message.objects.count(), initial_count)

    def test_invalid_error_id(self) -> None:
        payload = orjson.loads(self.webhook_fixture_data("honeybadger", "v2_occurred"))
        payload["fault"]["id"] = "invalid"
        initial_count = Message.objects.count()
        result = self.client_post(
            self.url, orjson.dumps(payload).decode(), content_type="application/json"
        )
        self.assert_json_error(result, "request['fault']['id'] is not an integer")
        self.assertEqual(Message.objects.count(), initial_count)

    def test_missing_message(self) -> None:
        payload = orjson.loads(self.webhook_fixture_data("honeybadger", "v2_occurred"))
        del payload["message"]
        initial_count = Message.objects.count()
        result = self.client_post(
            self.url, orjson.dumps(payload).decode(), content_type="application/json"
        )
        self.assert_json_error(result, "request['message'] is missing")
        self.assertEqual(Message.objects.count(), initial_count)

    def test_invalid_alarm_url(self) -> None:
        payload = orjson.loads(self.webhook_fixture_data("honeybadger", "v2_alarm_alert"))
        payload["alarm"]["url"] = "https://["
        initial_count = Message.objects.count()
        result = self.client_post(
            self.url, orjson.dumps(payload).decode(), content_type="application/json"
        )
        self.assert_json_error(result, "request['alarm']['url'] is not a URL")
        self.assertEqual(Message.objects.count(), initial_count)
