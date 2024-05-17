from unittest.mock import MagicMock, patch

from zerver.lib.test_classes import WebhookTestCase


class HarborHookTests(WebhookTestCase):
    CHANNEL_NAME = "harbor"
    URL_TEMPLATE = "/api/v1/external/harbor?api_key={api_key}&stream={stream}"
    WEBHOOK_DIR_NAME = "harbor"

    def test_push_image(self) -> None:
        expected_topic_name = "example/test"
        expected_message = """**admin** pushed image `example/test:latest`"""
        self.check_webhook("push_image", expected_topic_name, expected_message)

    @patch("zerver.lib.webhooks.common.check_send_webhook_message")
    def test_delete_image_ignored(self, check_send_webhook_message_mock: MagicMock) -> None:
        self.url = self.build_webhook_url()
        payload = self.get_body("delete_image")
        result = self.client_post(self.url, payload, content_type="application/json")
        self.assertFalse(check_send_webhook_message_mock.called)
        self.assert_json_success(result)

    def test_scanning_completed(self) -> None:
        expected_topic_name = "test/alpine/helm"

        expected_message = """
Image scan completed for `test/alpine/helm:3.8.1`. Vulnerabilities by severity:

* High: **4**
* Unknown: **1**
        """.strip()

        self.check_webhook("scanning_completed", expected_topic_name, expected_message)

    def test_scanning_completed_no_vulnerability(self) -> None:
        expected_topic_name = "test123/test-image"

        expected_message = """
Image scan completed for `test123/test-image:latest`. Vulnerabilities by severity:

None
        """.strip()

        self.check_webhook(
            "scanning_completed_no_vulnerability", expected_topic_name, expected_message
        )

    def test_scanning_completed_no_tag(self) -> None:
        expected_topic_name = "test/alpine/helm"

        expected_message = """
Image scan completed for `test/alpine/helm@sha256:b50334049354ed01330403212605dce2f4676a4e787ed113506861d9cf3c5424`. Vulnerabilities by severity:

* High: **4**
* Unknown: **1**
        """.strip()

        self.check_webhook("scanning_completed_no_tag", expected_topic_name, expected_message)
