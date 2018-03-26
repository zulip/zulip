# -*- coding: utf-8 -*-
from typing import Text

from zerver.lib.test_classes import WebhookTestCase

class DropboxHookTests(WebhookTestCase):
    STREAM_NAME = 'test'
    URL_TEMPLATE = "/api/v1/external/dropbox?&api_key={api_key}&stream={stream}"
    FIXTURE_DIR_NAME = 'dropbox'

    def test_file_updated(self) -> None:
        expected_subject = u"Dropbox"
        expected_message = u"File has been updated on Dropbox!"

        self.send_and_test_stream_message('file_updated', expected_subject, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def get_body(self, fixture_name: Text) -> Text:
        return self.fixture_data("dropbox", fixture_name, file_type="json")

    def test_verification_request(self) -> None:
        self.subscribe(self.test_user, self.STREAM_NAME)
        get_params = {'stream_name': self.STREAM_NAME,
                      'challenge': '9B2SVL4orbt5DxLMqJHI6pOTipTqingt2YFMIO0g06E',
                      'api_key': self.test_user.api_key}
        result = self.client_get(self.url, get_params)

        self.assert_in_response('9B2SVL4orbt5DxLMqJHI6pOTipTqingt2YFMIO0g06E', result)
