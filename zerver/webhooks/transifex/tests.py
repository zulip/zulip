# -*- coding: utf-8 -*-
from typing import Any, Dict, Text
from zerver.lib.test_classes import WebhookTestCase

class TransifexHookTests(WebhookTestCase):
    STREAM_NAME = 'transifex'
    URL_TEMPLATE = u"/api/v1/external/transifex?stream={stream}&api_key={api_key}&{data_template}"
    URL_DATA_TEMPLATE = "project={project}&language={language}&resource={resource}&{method}"
    URL_REVIEWED_METHOD_TEMPLATE = "reviewed=100"
    URL_TRANSLATED_METHOD_TEMPLATE = "translated=100"
    FIXTURE_DIR_NAME = 'transifex'

    PROJECT = 'project-title'
    LANGUAGE = 'en'
    RESOURCE = 'file'
    REVIEWED = True

    def test_transifex_reviewed_message(self):
        # type: () -> None
        self.REVIEWED = True
        expected_subject = "{} in {}".format(self.PROJECT, self.LANGUAGE)
        expected_message = "Resource {} fully reviewed.".format(self.RESOURCE)
        self.url = self.build_webhook_url()
        self.send_and_test_stream_message(None, expected_subject, expected_message)

    def test_transifex_translated_message(self):
        # type: () -> None
        self.REVIEWED = False
        expected_subject = "{} in {}".format(self.PROJECT, self.LANGUAGE)
        expected_message = "Resource {} fully translated.".format(self.RESOURCE)
        self.url = self.build_webhook_url()
        self.send_and_test_stream_message(None, expected_subject, expected_message)
        self.REVIEWED = True

    def build_webhook_url(self):
        # type: () -> Text
        url_data = self.URL_DATA_TEMPLATE.format(
            project=self.PROJECT,
            language=self.LANGUAGE,
            resource=self.RESOURCE,
            method=self.URL_REVIEWED_METHOD_TEMPLATE if self.REVIEWED else self.URL_TRANSLATED_METHOD_TEMPLATE
        )
        api_key = self.get_api_key(self.TEST_USER_EMAIL)
        return self.URL_TEMPLATE.format(api_key=api_key, stream=self.STREAM_NAME, data_template=url_data)

    def get_body(self, fixture_name):
        # type: (Text) -> Dict[str, Any]
        return {}
