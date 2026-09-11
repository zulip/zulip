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

        payload = orjson.loads(self.webhook_fixture_data("intercom", "admin_away_mode_updated"))
        payload["data"]["item"]["away_status_reason"] = "😜 On a vacation"
        self.subscribe(self.test_user, self.channel_name)
        msg = self.send_webhook_payload(
            self.test_user,
            self.url,
            orjson.dumps(payload).decode(),
            content_type="application/json",
        )
        self.assert_channel_message(
            message=msg,
            channel_name=self.channel_name,
            topic_name=expected_topic_name,
            content=f"{BO_NAME} is away (😜 On a vacation).",
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
            topic_name=f"Admin: {BO_NAME}",
            content=f"{BO_NAME} is now available.",
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

    def test_company_created(self) -> None:
        expected_topic_name = "Company: 6961d175205cf6a4438f0c22-qualification-company"
        expected_message = "6961d175205cf6a4438f0c22-qualification-company was created."
        self.check_webhook("company_created", expected_topic_name, expected_message)

    def test_company_created_with_name(self) -> None:
        expected_topic_name = "Company: Acme Enterprises"
        expected_message = "Acme Enterprises was created."
        self.check_webhook("company_created_with_name", expected_topic_name, expected_message)

    def test_company_deleted(self) -> None:
        expected_topic_name = "Company: 6961d38729675009a437c3bf"
        expected_message = "6961d38729675009a437c3bf was deleted."
        self.check_webhook("company_deleted", expected_topic_name, expected_message)

    def test_company_updated(self) -> None:
        expected_topic_name = "Company: Acme Enterprises"
        expected_message = "Acme Enterprises was updated."
        self.check_webhook("company_updated", expected_topic_name, expected_message)

    def test_company_contact_attached(self) -> None:
        expected_topic_name = "Lead: Jane Lead (6961d162fb0ef1f1ac90ce8c)"
        expected_message = "**Jane Lead** was attached to company **6961d175205cf6a4438f0c22-qualification-company**."
        self.check_webhook("company_contact_attached", expected_topic_name, expected_message)

    def test_company_contact_detached(self) -> None:
        expected_topic_name = "User: Jane Smith (6961cf78fb9d13be07871c78)"
        expected_message = "**Jane Smith** was detached from company **Acme Corp**."
        self.check_webhook("company_contact_detached", expected_topic_name, expected_message)
