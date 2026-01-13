from zerver.lib.test_classes import WebhookTestCase


class IntercomWebHookTests(WebhookTestCase):
    CHANNEL_NAME = "intercom"
    URL_TEMPLATE = "/api/v1/external/intercom?stream={stream}&api_key={api_key}&separate_topics_for_each_entity=true"
    WEBHOOK_DIR_NAME = "intercom"

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
        expected_message = "Admin **John Doe** added to workspace."
        self.check_webhook("admin_added_to_workspace", expected_topic_name, expected_message)

    def test_admin_away_mode_updated(self) -> None:
        expected_topic_name = "Admin: John Doe"
        expected_message = "Admin **John Doe** updated away mode to enabled."
        self.check_webhook("admin_away_mode_updated", expected_topic_name, expected_message)

    def test_admin_logged_in(self) -> None:
        expected_topic_name = "Admin: John Doe"
        expected_message = "Admin **John Doe** logged in."
        self.check_webhook("admin_logged_in", expected_topic_name, expected_message)

    def test_admin_logged_out(self) -> None:
        expected_topic_name = "Admin: John Doe"
        expected_message = "Admin **John Doe** logged out."
        self.check_webhook("admin_logged_out", expected_topic_name, expected_message)

    def test_admin_removed_from_workspace(self) -> None:
        expected_topic_name = "Admin: John Doe"
        expected_message = "Admin **John Doe** removed from workspace."
        self.check_webhook("admin_removed_from_workspace", expected_topic_name, expected_message)

    def test_admin_generic_topic(self) -> None:
        expected_topic_name = "Admin"
        expected_message = "Admin **John Doe** added to workspace."
        self.url = (
            f"/api/v1/external/intercom?stream={self.CHANNEL_NAME}&api_key={self.test_user.api_key}"
        )
        self.check_webhook(
            "admin_added_to_workspace",
            expected_topic_name,
            expected_message,
        )
