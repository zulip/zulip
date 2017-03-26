# -*- coding: utf-8 -*-
from zerver.lib.test_classes import WebhookTestCase

class CrashlyticsHookTests(WebhookTestCase):
    STREAM_NAME = 'crashlytics'
    URL_TEMPLATE = u"/api/v1/external/crashlytics?stream={stream}&api_key={api_key}"
    FIXTURE_DIR_NAME = 'crashlytics'

    def test_crashlytics_verification_message(self):
        # type: () -> None
        last_message_before_request = self.get_last_message()
        payload = self.get_body('verification')
        url = self.build_webhook_url()
        result = self.client_post(url, payload, content_type="application/json")
        last_message_after_request = self.get_last_message()
        self.assert_json_success(result)
        self.assertEqual(last_message_after_request.pk, last_message_before_request.pk)

    def test_crashlytics_build_in_success_status(self):
        # type: () -> None
        expected_subject = u"123: Issue Title"
        expected_message = u"[Issue](http://crashlytics.com/full/url/to/issue) impacts at least 16 device(s)."
        self.send_and_test_stream_message('issue_message', expected_subject, expected_message)
