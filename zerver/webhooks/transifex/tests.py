# -*- coding: utf-8 -*-
from typing import Any, Dict, Text

from zerver.lib.test_classes import WebhookTestCase

class TransifexHookTests(WebhookTestCase):
    STREAM_NAME = 'transifex'
    URL_TEMPLATE = u"/api/v1/external/transifex?stream={stream}&api_key={api_key}"
    URL_REVIEWED_METHOD_TEMPLATE = "reviewed=100"
    URL_TRANSLATED_METHOD_TEMPLATE = "translated=100"
    FIXTURE_DIR_NAME = 'transifex'

    PROJECT = 'project-title'
    LANGUAGE = 'en'
    RESOURCE = 'file'
    REVIEWED = True

    def test_transifex_reviewed_message(self) -> None:
        self.REVIEWED = True
        expected_subject = "{} in {}".format(self.PROJECT, self.LANGUAGE)
        expected_message = "Resource {} fully reviewed.".format(self.RESOURCE)
        self.url = self.build_webhook_url(
            self.URL_REVIEWED_METHOD_TEMPLATE,
            project=self.PROJECT,
            language=self.LANGUAGE,
            resource=self.RESOURCE,
        )
        self.send_and_test_stream_message("", expected_subject, expected_message)

    def test_transifex_translated_message(self) -> None:
        self.REVIEWED = False
        expected_subject = "{} in {}".format(self.PROJECT, self.LANGUAGE)
        expected_message = "Resource {} fully translated.".format(self.RESOURCE)
        self.url = self.build_webhook_url(
            self.URL_TRANSLATED_METHOD_TEMPLATE,
            project=self.PROJECT,
            language=self.LANGUAGE,
            resource=self.RESOURCE,
        )
        self.send_and_test_stream_message("", expected_subject, expected_message)

    def get_body(self, fixture_name: Text) -> Dict[str, Any]:
        return {}
