import orjson

from zerver.lib.test_classes import WebhookTestCase
from zerver.webhooks.fixtureless_integrations import BO_NAME


class IntercomWebHookTests(WebhookTestCase):
    def test_ping(self) -> None:
        expected_topic_name = "Intercom"
        expected_message = "Intercom webhook has been successfully configured."
        self.check_webhook("ping", expected_topic_name, expected_message)

    def test_admin_activity_log_event_created(self) -> None:
        expected_topic_name = "Admin activity log"
        expected_message = f"{BO_NAME} disabled the AI inbox translation settings."
        self.check_webhook(
            "admin_activity_log_event_created", expected_topic_name, expected_message
        )

    def test_admin_added_to_workspace(self) -> None:
        expected_topic_name = f"Admin: {BO_NAME}"
        expected_message = f"{BO_NAME} is now an admin."
        self.check_webhook("admin_added_to_workspace", expected_topic_name, expected_message)

    def test_admin_away_mode_enabled(self) -> None:
        expected_topic_name = f"Admin: {BO_NAME}"
        expected_message = f"{BO_NAME} is away."
        self.check_webhook("admin_away_mode_updated", expected_topic_name, expected_message)

        payload = orjson.loads(self.get_body("admin_away_mode_updated"))
        payload["data"]["item"]["away_status_reason"] = "😜 On a vacation"
        self.check_webhook(
            "admin_away_mode_updated",
            expected_topic_name,
            f"{BO_NAME} is away (😜 On a vacation).",
            custom_payload=payload,
        )

    def test_admin_away_mode_disabled(self) -> None:
        payload = orjson.loads(self.get_body("admin_away_mode_updated"))
        payload["data"]["item"]["away_mode_enabled"] = False
        self.check_webhook(
            "admin_away_mode_updated",
            f"Admin: {BO_NAME}",
            f"{BO_NAME} is now available.",
            custom_payload=payload,
        )

    def test_admin_logged_in(self) -> None:
        expected_topic_name = f"Admin: {BO_NAME}"
        expected_message = f"{BO_NAME} logged in."
        self.check_webhook("admin_logged_in", expected_topic_name, expected_message)

    def test_admin_logged_out(self) -> None:
        expected_topic_name = f"Admin: {BO_NAME}"
        expected_message = f"{BO_NAME} logged out."
        self.check_webhook("admin_logged_out", expected_topic_name, expected_message)

    def test_admin_removed_from_workspace(self) -> None:
        expected_topic_name = f"Admin: {BO_NAME}"
        expected_message = f"{BO_NAME} is no longer an admin."
        self.check_webhook("admin_removed_from_workspace", expected_topic_name, expected_message)
