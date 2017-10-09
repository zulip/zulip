# -*- coding: utf-8 -*-
from typing import Optional, Text

from zerver.lib.test_classes import WebhookTestCase


class GoogleCodeInTests(WebhookTestCase):
    STREAM_NAME = 'gci'
    URL_TEMPLATE = "/api/v1/external/gci?&api_key={api_key}&stream={stream}"
    FIXTURE_DIR_NAME = 'gci'

    def test_abandon_event_message(self):
        # type: () -> None
        expected_subject = u'Task: Sails unspread it stopped at kearney'
        expected_message = u'**student-yqqtag** abandoned task [Sails unspread it stopped at kearney](https://0.0.0.0:8000/dashboard/tasks/6694926301528064/).'
        self.send_and_test_stream_message('task_abandoned_by_student',
                                          expected_subject, expected_message)
