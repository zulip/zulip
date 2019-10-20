# -*- coding: utf-8 -*-

from zerver.lib.test_classes import WebhookTestCase

class HarborHookTests(WebhookTestCase):
    STREAM_NAME = "harbor"
    URL_TEMPLATE = u"/api/v1/external/harbor?api_key={api_key}&stream={stream}"

    def test_push_image(self) -> None:
        expected_topic = "example/test"
        expected_message = """**admin** pushed image `example/test:latest`"""
        self.send_and_test_stream_message(
            "push_image", expected_topic, expected_message)

    def test_scanning_completed(self) -> None:
        expected_topic = "example/test"

        expected_message = """
Image scan completed for `example/test:latest`. Vulnerabilities by severity:

* High: 12
* Medium: 16
* Low: 7
* Unknown: 2
* None: 131
        """.strip()

        self.send_and_test_stream_message(
            "scanning_completed", expected_topic, expected_message)

    def get_body(self, fixture_name: str) -> str:
        return self.webhook_fixture_data("harbor", fixture_name, file_type="json")
