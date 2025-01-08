import logging
from zerver.lib.test_classes import WebhookTestCase

class OpenProjectHookTests(WebhookTestCase):
    CHANNEL_NAME = "OpenProjectUpdates"
    URL_TEMPLATE = "/api/v1/external/openproject?api_key={api_key}&stream={stream}"
    WEBHOOK_DIR_NAME = "openproject"
    STREAM_NAME = "OpenProjectUpdates"

    def test_project_created(self) -> None:
        expected_topic = "Project"
        expected_message = "**Project** Project1 got created"
        
        self.check_webhook(
            "project_created",
            expected_topic,
            expected_message,
            content_type="application/json",
        )



    
    def test_project_updated(self) -> None:
        expected_topic = "Project"
        expected_message = "**Project** Project1 got updated"
        self.check_webhook(
            "project_updated",
            expected_topic,
            expected_message,
            content_type="application/json",
        )
    
    def test_work_package_created(self) -> None:
        expected_topic = "Work Package"
        expected_message = "**Work Package** Task1 of type WorkPackage got created"
        self.check_webhook(
            "work_package_created",
            expected_topic,
            expected_message,
            content_type="application/json",
        )
    
    def test_work_package_updated(self) -> None:
        expected_topic = "Work Package"
        expected_message = "**Work Package** Task1 of type WorkPackage got updated"
        self.check_webhook(
            "work_package_updated",
            expected_topic,
            expected_message,
            content_type="application/json",
        )

    def test_time_entry_created(self) -> None:
        expected_topic = "Time Entry"
        expected_message = "**Time Entry** of 1H got created"
        self.check_webhook(
            "time_entry_created",
            expected_topic,
            expected_message,
            content_type="application/json",

        )

    def test_attachment_created(self) -> None:
        expected_topic = "File Uploaded"
        expected_message = "**File Uploaded** of name a.out"
        self.check_webhook(
            "attachment_created",
            expected_topic,
            expected_message,
            content_type="application/json",
        )