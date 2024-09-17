from zerver.lib.test_classes import WebhookTestCase


class PabblyHookTests(WebhookTestCase):
    CHANNEL_NAME = "pabbly"
    URL_TEMPLATE = "/api/v1/external/pabbly?stream={stream}&api_key={api_key}"
    WEBHOOK_DIR_NAME = "pabbly"
    EXPECTED_TOPIC = "Pabbly notification"

    def test_pabbly_workflow_event(self) -> None:
        expected_topic_name = self.EXPECTED_TOPIC
        expected_message = """New event from your Pabbly workflow! :notifications:
* **Customer name**: User
* **Vehicle year**: 2007
* **Vehicle make**: Chevrolet
* **Fee**: 129.32
* **id**: 93
* **Ready for QC**: True
* **Checked**: None"""
        self.check_webhook("pabbly_workflow_event", expected_topic_name, expected_message)
