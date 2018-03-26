# -*- coding: utf-8 -*-
from typing import Text
from zerver.lib.test_classes import WebhookTestCase

class FlockHookTests(WebhookTestCase):
    STREAM_NAME = 'test'
    URL_TEMPLATE = u"/api/v1/external/flock?api_key={api_key}&stream={stream}"

    def test_flock_message(self) -> None:
        expected_subject = u"Flock notifications"
        expected_message = u"This is the welcome message!"
        self.send_and_test_stream_message('messages',
                                          expected_subject,
                                          expected_message,
                                          content_type="application/json")

    def test_flock_reply(self) -> None:
        expected_subject = u"Flock notifications"
        expected_message = u"It's interesting how high productivity will go..."
        self.send_and_test_stream_message('reply',
                                          expected_subject,
                                          expected_message,
                                          content_type="application/json")

    def test_flock_note(self) -> None:
        expected_subject = u"Flock notifications"
        expected_message = u"Shared a note"
        self.send_and_test_stream_message('note',
                                          expected_subject,
                                          expected_message,
                                          content_type="application/json")

    def test_flock_reply_note(self) -> None:
        expected_subject = u"Flock notifications"
        expected_message = u"This is reply to Note."
        self.send_and_test_stream_message('reply_note',
                                          expected_subject,
                                          expected_message,
                                          content_type="application/json")

    def test_flock_reply_pinned(self) -> None:
        expected_subject = u"Flock notifications"
        expected_message = u"This is reply to pinned message."
        self.send_and_test_stream_message('reply_pinned',
                                          expected_subject,
                                          expected_message,
                                          content_type="application/json")

    def test_flock_reply_reminder(self) -> None:
        expected_subject = u"Flock notifications"
        expected_message = u"This is a reply to Reminder."
        self.send_and_test_stream_message('reply_reminder',
                                          expected_subject,
                                          expected_message,
                                          content_type="application/json")

    def test_flock_reply_todo(self) -> None:
        expected_subject = u"Flock notifications"
        expected_message = u"This is a reply to Todo notification."
        self.send_and_test_stream_message('reply_todo',
                                          expected_subject,
                                          expected_message,
                                          content_type="application/json")

    def test_flock_pinned(self) -> None:
        expected_subject = u"Flock notifications"
        expected_message = u"Rishabh rawat pinned an item to the conversation"
        self.send_and_test_stream_message('pinned',
                                          expected_subject,
                                          expected_message,
                                          content_type="application/json")

    def test_flock_reminder(self) -> None:
        expected_subject = u"Flock notifications"
        expected_message = u"Rishabh rawat wanted me to remind All"
        self.send_and_test_stream_message('reminder',
                                          expected_subject,
                                          expected_message,
                                          content_type="application/json")

    def test_flock_todo(self) -> None:
        expected_subject = u"Flock notifications"
        expected_message = u"Rishabh rawat added a to-do in New List 1 list"
        self.send_and_test_stream_message('todo',
                                          expected_subject,
                                          expected_message,
                                          content_type="application/json")

    def get_body(self, fixture_name: Text) -> Text:
        return self.fixture_data("flock", fixture_name, file_type="json")
