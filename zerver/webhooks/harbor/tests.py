from unittest.mock import MagicMock, patch

from zerver.lib.test_classes import WebhookTestCase


class HarborHookTests(WebhookTestCase):
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

    def test_pull_image(self) -> None:
        expected_topic_name = "example/test"
        expected_message = """**admin** pulled image `example/test:latest`"""
        self.check_webhook("pull_image", expected_topic_name, expected_message)

    def test_scanning_stopped(self) -> None:
        expected_topic_name = "library/nginx"
        expected_message = """Image scan stopped for `library/nginx:v1.0`"""
        self.check_webhook("scanning_stopped", expected_topic_name, expected_message)

    def test_scanning_failed(self) -> None:
        expected_topic_name = "library/redis"
        expected_message = """Image scan failed for `library/redis:v2.0`"""
        self.check_webhook("scanning_failed", expected_topic_name, expected_message)

    def test_quota_exceed(self) -> None:
        expected_topic_name = "myproject/app"
        expected_message = """Quota exceeded for repository `myproject/app`: adding 2.1 MiB of storage resource, which when updated to current usage of 97.9 MiB will exceed the configured upper limit of 100.0 MiB"""
        self.check_webhook("quota_exceed", expected_topic_name, expected_message)

    def test_quota_warning(self) -> None:
        expected_topic_name = "production/web_app"
        expected_message = """Quota warning for repository `production/web_app`: current usage is 85.0 MiB of the 100.0 MiB quota limit"""
        self.check_webhook("quota_warning", expected_topic_name, expected_message)

    def test_replication(self) -> None:
        expected_topic_name = "library/alpine"
        expected_message = """Replication to `harbor-backup.example.com` succeeded"""
        self.check_webhook("replication", expected_topic_name, expected_message)

    def test_tag_retention(self) -> None:
        expected_topic_name = "myapp/backend"
        expected_message = (
            """Tag retention completed for `myapp/backend`: 5 retained, 10 deleted (total: 15)"""
        )
        self.check_webhook("tag_retention", expected_topic_name, expected_message)
