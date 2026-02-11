import orjson

from zerver.lib.test_classes import WebhookTestCase


class IntercomWebHookTests(WebhookTestCase):
    def test_ping(self) -> None:
        expected_topic_name = "Intercom"
        expected_message = "Intercom webhook has been successfully configured."
        self.check_webhook("ping", expected_topic_name, expected_message)

    def test_admin_activity_log_event_created(self) -> None:
        expected_topic_name = "Admin"
        expected_message = "John Doe disabled the AI inbox translation settings."
        self.check_webhook(
            "admin_activity_log_event_created", expected_topic_name, expected_message
        )

    def test_admin_added_to_workspace(self) -> None:
        expected_topic_name = "Admin: John Doe"
        expected_message = "John Doe is now an admin."
        self.check_webhook("admin_added_to_workspace", expected_topic_name, expected_message)

    def test_admin_away_mode_enabled(self) -> None:
        expected_topic_name = "Admin: John Doe"
        expected_message = "John Doe is away."
        self.check_webhook("admin_away_mode_updated", expected_topic_name, expected_message)

    def test_admin_away_mode_enabled_with_reason(self) -> None:
        self.subscribe(self.test_user, self.channel_name)
        payload = self.webhook_fixture_data(self.webhook_dir_name, "admin_away_mode_updated")
        data = orjson.loads(payload)
        data["data"]["item"]["away_status_reason"] = "On vacation."
        msg = self.send_webhook_payload(
            self.test_user, self.url, orjson.dumps(data).decode(), content_type="application/json"
        )
        self.assert_channel_message(
            message=msg,
            channel_name=self.channel_name,
            topic_name="Admin: John Doe",
            content="John Doe is away. Reason: On vacation.",
        )

    def test_admin_away_mode_disabled(self) -> None:
        self.subscribe(self.test_user, self.channel_name)
        payload = self.webhook_fixture_data(self.webhook_dir_name, "admin_away_mode_updated")
        data = orjson.loads(payload)
        data["data"]["item"]["away_mode_enabled"] = False
        msg = self.send_webhook_payload(
            self.test_user, self.url, orjson.dumps(data).decode(), content_type="application/json"
        )
        self.assert_channel_message(
            message=msg,
            channel_name=self.channel_name,
            topic_name="Admin: John Doe",
            content="John Doe is available.",
        )

    def test_admin_logged_in(self) -> None:
        expected_topic_name = "Admin: John Doe"
        expected_message = "John Doe logged in."
        self.check_webhook("admin_logged_in", expected_topic_name, expected_message)

    def test_admin_logged_out(self) -> None:
        expected_topic_name = "Admin: John Doe"
        expected_message = "John Doe logged out."
        self.check_webhook("admin_logged_out", expected_topic_name, expected_message)

    def test_admin_removed_from_workspace(self) -> None:
        expected_topic_name = "Admin: John Doe"
        expected_message = "John Doe is no longer an admin."
        self.check_webhook("admin_removed_from_workspace", expected_topic_name, expected_message)
