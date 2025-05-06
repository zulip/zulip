from zerver.lib.test_classes import WebhookTestCase


class OpenProjectHookTests(WebhookTestCase):
    CHANNEL_NAME = "OpenProjectUpdates"
    URL_TEMPLATE = "/api/v1/external/openproject?api_key={api_key}&stream={stream}"
    WEBHOOK_DIR_NAME = "openproject"
    STREAM_NAME = "OpenProjectUpdates"

    def test_project_with_parent_created(self) -> None:
        expected_topic = "AI Backend"
        expected_message = (
            "Project **AI Backend** was created as a sub-project of **Demo project**."
        )

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
        expected_message = "**Task1** (work package **Task**) was created by **Nirved Mishra**."
        self.check_webhook(
            "work_package_created",
            expected_topic,
            expected_message,
        )

    def test_work_package_updated(self) -> None:
        expected_topic = "Demo project"
        expected_message = "**Task1** (work package **Task**) was updated by **Nirved Mishra**."
        self.check_webhook(
            "work_package_updated",
            expected_topic,
            expected_message,
        )

    def test_time_entry_with_workpackage_created(self) -> None:
        expected_topic = "Project1"
        expected_message = "**Nirved Mishra** logged **1 hour** on **kl**."
        self.check_webhook(
            "time_entry_created__with_workpackage",
            expected_topic,
            expected_message,
        )

    def test_time_entry_without_workpackage_created(self) -> None:
        expected_topic = "Project1"
        expected_message = "**Nirved Mishra** logged **1 hour** on **Project1**."
        self.check_webhook(
            "time_entry_created__without_workpackage",
            expected_topic,
            expected_message,
        )

    def test_time_entry_with_iso_hm(self) -> None:
        expected_topic = "Project1"
        expected_message = "**Nirved Mishra** logged **7 hours and 42 minutes** on **kl**."
        self.check_webhook(
            "time_entry_created__with_iso_hm",
            expected_topic,
            expected_message,
        )

    def test_time_entry_with_invalid_iso(self) -> None:
        expected_topic = "Project1"
        expected_message = "**Nirved Mishra** logged a time entry on **kl**."
        self.check_webhook(
            "time_entry_created__with_invalid_iso",
            expected_topic,
            expected_message,
        )

    def test_attachment_created(self) -> None:
        expected_topic = "Project 2"
        expected_message = "**Nirved Mishra** uploaded **a.out** in **task2**."
        self.check_webhook(
            "attachment_created",
            expected_topic,
            expected_message,
        )
