from typing import Dict

from zerver.lib.test_classes import WebhookTestCase


class TransifexHookTests(WebhookTestCase):
    STREAM_NAME = 'transifex'
    URL_TEMPLATE = "/api/v1/external/transifex?stream={stream}&api_key={api_key}"
    URL_REVIEWED_METHOD_TEMPLATE = "reviewed=100"
    URL_TRANSLATED_METHOD_TEMPLATE = "translated=100"
    FIXTURE_DIR_NAME = 'transifex'

    PROJECT = 'project-title'
    LANGUAGE = 'en'
    RESOURCE = 'file'
    REVIEWED = True

    def test_transifex_reviewed_message(self) -> None:
        self.REVIEWED = True
        expected_topic = f"{self.PROJECT} in {self.LANGUAGE}"
        expected_message = f"Resource {self.RESOURCE} fully reviewed."
        self.url = self.build_webhook_url(
            self.URL_REVIEWED_METHOD_TEMPLATE,
            project=self.PROJECT,
            language=self.LANGUAGE,
            resource=self.RESOURCE,
        )
        self.check_webhook("", expected_topic, expected_message)

    def test_transifex_translated_message(self) -> None:
        self.REVIEWED = False
        expected_topic = f"{self.PROJECT} in {self.LANGUAGE}"
        expected_message = f"Resource {self.RESOURCE} fully translated."
        self.url = self.build_webhook_url(
            self.URL_TRANSLATED_METHOD_TEMPLATE,
            project=self.PROJECT,
            language=self.LANGUAGE,
            resource=self.RESOURCE,
        )
        self.check_webhook("", expected_topic, expected_message)

    def get_payload(self, fixture_name: str) -> Dict[str, str]:
        return {}
