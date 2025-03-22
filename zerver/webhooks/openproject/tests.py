from zerver.lib.test_classes import WebhookTestCase


class OpenProjectHookTests(WebhookTestCase):
    CHANNEL_NAME = "OpenProjectUpdates"
    URL_TEMPLATE = "/api/v1/external/openproject?api_key={api_key}&stream={stream}"
    WEBHOOK_DIR_NAME = "openproject"
    STREAM_NAME = "OpenProjectUpdates"

    def test_project_created(self) -> None:
        expected_topic = "Project"
        expected_message = "Project **AI Backend** was created."

        self.check_webhook(
            "project_created",
            expected_topic,
            expected_message,
            content_type="application/json",
        )

    def test_project_updated(self) -> None:
        expected_topic = "Project"
        expected_message = "Project **AI Backend** was updated."
        self.check_webhook(
            "project_updated",
            expected_topic,
            expected_message,
            content_type="application/json",
        )

    def test_work_package_created(self) -> None:
        expected_topic = "Work Package"
        expected_message = "Work Package **Task1** of type **Task** was created."
        self.check_webhook(
            "work_package_created",
            expected_topic,
            expected_message,
            content_type="application/json",
        )

    def test_work_package_updated(self) -> None:
        expected_topic = "Work Package"
        expected_message = "Work Package **Task1** of type **Task** was updated."
        self.check_webhook(
            "work_package_updated",
            expected_topic,
            expected_message,
            content_type="application/json",
        )

    def test_time_entry_created(self) -> None:
        expected_topic = "Time Entry"
        expected_message = "A time entry of **1H** was created for project **Project1**."
        self.check_webhook(
            "time_entry_created",
            expected_topic,
            expected_message,
            content_type="application/json",
        )

    def test_attachment_created(self) -> None:
        expected_topic = "Attachment"
        expected_message = "A file **a.out** was uploaded."
        self.check_webhook(
            "attachment_created",
            expected_topic,
            expected_message,
            content_type="application/json",
        )

    def test_openproject_anomalous_payload(self) -> None:
        result = self.client_post(
            self.url,
            {},
            content_type="application/json",
        )
        self.assert_json_error(
            result, "Unable to parse request: Did OpenProject generate this event?", 400
        )
