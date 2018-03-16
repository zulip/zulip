# -*- coding: utf-8 -*-
from typing import Any, Dict, Optional, Text

from zerver.lib.test_classes import WebhookTestCase

class ZenDeskHookTests(WebhookTestCase):
    STREAM_NAME = 'zendesk'
    URL_TEMPLATE = u"/api/v1/external/zendesk?stream={stream}"

    DEFAULT_TICKET_TITLE = 'User can\'t login'
    TICKET_TITLE = DEFAULT_TICKET_TITLE

    DEFAULT_TICKET_ID = 54
    TICKET_ID = DEFAULT_TICKET_ID

    DEFAULT_MESSAGE = 'Message'
    MESSAGE = DEFAULT_MESSAGE

    def get_body(self, fixture_name: Text) -> Dict[str, Any]:
        return {
            'ticket_title': self.TICKET_TITLE,
            'ticket_id': self.TICKET_ID,
            'message': self.MESSAGE,
            'stream': self.STREAM_NAME,
        }

    def do_test(self, expected_subject: Optional[Text]=None, expected_message: Optional[Text]=None) -> None:
        self.api_stream_message(self.TEST_USER_EMAIL, "", expected_subject, expected_message,
                                content_type=None)
        self.TICKET_TITLE = self.DEFAULT_TICKET_TITLE
        self.TICKET_ID = self.DEFAULT_TICKET_ID
        self.MESSAGE = self.DEFAULT_MESSAGE

    def test_subject(self) -> None:
        self.TICKET_ID = 4
        self.TICKET_TITLE = "Test ticket"
        self.do_test(expected_subject='#4: Test ticket')

    def test_long_subject(self) -> None:
        self.TICKET_ID = 4
        self.TICKET_TITLE = "Test ticket" + '!' * 80
        self.do_test(expected_subject='#4: Test ticket' + '!' * 42 + '...')

    def test_content(self) -> None:
        self.MESSAGE = 'New comment:\n> It is better\n* here'
        self.do_test(expected_message='New comment:\n> It is better\n* here')
