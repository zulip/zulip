from zerver.lib.test_classes import WebhookTestCase


class OpenProjectHookTests(WebhookTestCase):
    CHANNEL_NAME = "OpenProjectUpdates"
    URL_TEMPLATE = "/api/v1/external/openproject?api_key={api_key}&stream={stream}"
    WEBHOOK_DIR_NAME = "openproject"
    STREAM_NAME = "OpenProjectUpdates"

    def test_project_with_parent_created(self) -> None:
        expected_topic = "AI Backend"
        expected_message = "Project **AI Backend** was created in project **Demo project**."

        self.check_webhook(
            "project_created__with_parent",
            expected_topic,
            expected_message,
        )

    def test_project_without_parent_created(self) -> None:
        expected_topic = "AI Backend"
        expected_message = "Project **AI Backend** was created."

        self.check_webhook(
            "project_created__without_parent",
            expected_topic,
            expected_message,
        )

    def test_project_updated(self) -> None:
        expected_topic = "AI Backend"
        expected_message = "Project **AI Backend** was updated."
        self.check_webhook(
            "project_updated",
            expected_topic,
            expected_message,
        )

    def test_work_package_created(self) -> None:
        expected_topic = "Demo project"
        expected_message = "**Task** work package **Task1** was created by **Nirved Mishra**."
        self.check_webhook(
            "work_package_created",
            expected_topic,
            expected_message,
        )

    def test_work_package_updated(self) -> None:
        expected_topic = "Demo project"
        expected_message = "**Task** work package **Task1** was updated by **Nirved Mishra**."
        self.check_webhook(
            "work_package_updated",
            expected_topic,
            expected_message,
        )

    def test_time_entry_with_workpackage_created(self) -> None:
        expected_topic = "Project1"
        expected_message = "**Nirved Mishra** created a time entry of **1H** for **kl**."
        self.check_webhook(
            "time_entry_created__with_workpackage",
            expected_topic,
            expected_message,
        )

    def test_time_entry_without_workpackage_created(self) -> None:
        expected_topic = "Project1"
        expected_message = "**Nirved Mishra** created a time entry of **1H**."
        self.check_webhook(
            "time_entry_created__without_workpackage",
            expected_topic,
            expected_message,
        )

    def test_attachment_created(self) -> None:
        expected_topic = "Project 2"
        expected_message = "**Nirved Mishra** uploaded **a.out** in workpackage **task2**."
        self.check_webhook(
            "attachment_created",
            expected_topic,
            expected_message,
        )
