# -*- coding: utf-8 -*-
from typing import Text

from zerver.lib.test_classes import WebhookTestCase

class GoSquaredHookTests(WebhookTestCase):
    STREAM_NAME = 'gosquared'
    URL_TEMPLATE = "/api/v1/external/gosquared?stream={stream}&api_key={api_key}"
    FIXTURE_DIR_NAME = 'gosquared'

    # Note: Include a test function per each distinct message condition your integration supports
    def test_traffic_message(self) -> None:
        expected_subject = "GoSquared - requestb.in"
        expected_message = u"[requestb.in](https://www.gosquared.com/now/GSN-595854-T) has 33 visitors online."

        self.send_and_test_stream_message('traffic_spike', expected_subject, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def get_body(self, fixture_name: Text) -> Text:
        return self.fixture_data("gosquared", fixture_name, file_type="json")
