# -*- coding: utf-8 -*-
from zerver.lib.test_classes import WebhookTestCase

class CrashlyticsHookTests(WebhookTestCase):
    STREAM_NAME = 'crashlytics'
    URL_TEMPLATE = u"/api/v1/external/crashlytics?stream={stream}&api_key={api_key}"
    FIXTURE_DIR_NAME = 'crashlytics'

    def test_crashlytics_verification_message(self) -> None:
        expected_topic = u"Setup"
        expected_message = u"Webhook has been successfully configured."
        self.send_and_test_stream_message('verification', expected_topic, expected_message)

    def test_crashlytics_build_in_success_status(self) -> None:
        expected_topic = u"123: Issue Title"
        expected_message = u"[Issue](http://crashlytics.com/full/url/to/issue) impacts at least 16 device(s)."
        self.send_and_test_stream_message('issue_message', expected_topic, expected_message)
