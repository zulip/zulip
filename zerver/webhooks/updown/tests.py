# -*- coding: utf-8 -*-
from zerver.lib.test_classes import WebhookTestCase

class UpdownHookTests(WebhookTestCase):
    STREAM_NAME = 'updown'
    URL_TEMPLATE = u"/api/v1/external/updown?stream={stream}&api_key={api_key}"
    FIXTURE_DIR_NAME = 'updown'

    def test_updown_check_down_event(self) -> None:
        expected_subject = u"https://updown.io"
        expected_message = u"Service is `down`. It returned a 500 error at 2016-02-07 13:11:43 UTC."
        self.send_and_test_stream_message('check_down_one_event', expected_subject, expected_message)

    def test_updown_check_up_again_event(self) -> None:
        expected_subject = u"https://updown.io"
        expected_message = u"Service is `up` again after 4 minutes 25 seconds."
        self.send_and_test_stream_message('check_up_again_one_event', expected_subject, expected_message)

    def test_updown_check_up_event(self) -> None:
        expected_subject = u"https://updown.io"
        expected_message = u"Service is `up`."
        self.send_and_test_stream_message('check_up_first_time', expected_subject, expected_message)

    def test_updown_check_up_multiple_events(self) -> None:
        first_message_expected_subject = u"https://updown.io"
        first_message_expected_message = u"Service is `up` again after 1 second."

        second_message_expected_subject = u"https://updown.io"
        second_message_expected_message = u"Service is `down`. It returned a 500 error at 2016-02-07 13:11:43 UTC."

        self.send_and_test_stream_message('check_multiple_events')
        last_message = self.get_last_message()
        self.do_test_subject(last_message, first_message_expected_subject)
        self.do_test_message(last_message, first_message_expected_message)

        second_to_last_message = self.get_second_to_last_message()
        self.do_test_subject(second_to_last_message, second_message_expected_subject)
        self.do_test_message(second_to_last_message, second_message_expected_message)
