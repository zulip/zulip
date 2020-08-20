from unittest.mock import MagicMock, patch

from zerver.lib.test_classes import WebhookTestCase


class HarborHookTests(WebhookTestCase):
    STREAM_NAME = "harbor"
    URL_TEMPLATE = "/api/v1/external/harbor?api_key={api_key}&stream={stream}"
    FIXTURE_DIR_NAME = "harbor"

    def test_push_image(self) -> None:
        expected_topic = "example/test"
        expected_message = """**admin** pushed image `example/test:latest`"""
        self.check_webhook("push_image", expected_topic, expected_message)

    @patch('zerver.lib.webhooks.common.check_send_webhook_message')
    def test_delete_image_ignored(
            self, check_send_webhook_message_mock: MagicMock) -> None:
        self.url = self.build_webhook_url()
        payload = self.get_body('delete_image')
        result = self.client_post(self.url, payload, content_type="application/json")
        self.assertFalse(check_send_webhook_message_mock.called)
        self.assert_json_success(result)

    def test_scanning_completed(self) -> None:
        expected_topic = "example/test"

        expected_message = """
Image scan completed for `example/test:latest`. Vulnerabilities by severity:

* High: **12**
* Medium: **16**
* Low: **7**
* Unknown: **2**
* None: **131**
        """.strip()

        self.check_webhook("scanning_completed", expected_topic, expected_message)
