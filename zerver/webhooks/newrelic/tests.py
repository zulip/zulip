# -*- coding: utf-8 -*-
from typing import Text

from zerver.lib.test_classes import WebhookTestCase

class NewRelicHookTests(WebhookTestCase):
    STREAM_NAME = 'newrelic'
    URL_TEMPLATE = u"/api/v1/external/newrelic?stream={stream}&api_key={api_key}"

    def test_alert(self) -> None:
        expected_subject = "Apdex score fell below critical level of 0.90"
        expected_message = 'Alert opened on [application name]: \
Apdex score fell below critical level of 0.90\n\
[View alert](https://rpm.newrelc.com/accounts/[account_id]/applications/[application_id]/incidents/[incident_id])'
        self.send_and_test_stream_message('alert', expected_subject, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_deployment(self) -> None:
        expected_subject = 'Test App deploy'
        expected_message = '`1242` deployed by **Zulip Test**\n\
Description sent via curl\n\nChangelog string'
        self.send_and_test_stream_message('deployment', expected_subject, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def get_body(self, fixture_name: Text) -> Text:
        return self.fixture_data("newrelic", fixture_name, file_type="txt")
