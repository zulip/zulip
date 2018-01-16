# -*- coding: utf-8 -*-
from typing import Text

from zerver.lib.test_classes import WebhookTestCase

class HerokuHookTests(WebhookTestCase):
    STREAM_NAME = 'heroku'
    URL_TEMPLATE = u"/api/v1/external/heroku?stream={stream}&api_key={api_key}"

    def test_deployment(self) -> None:
        expected_subject = "sample-project"
        expected_message = u"""user@example.com deployed version 3eb5f44 of \
[sample-project](http://sample-project.herokuapp.com)
>   * Example User: Test commit for Deploy Hook 2"""
        self.send_and_test_stream_message('deploy', expected_subject, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def get_body(self, fixture_name: Text) -> Text:
        return self.fixture_data("heroku", fixture_name, file_type="txt")
