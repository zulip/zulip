#!/usr/bin/env python

from __future__ import absolute_import
from __future__ import print_function

from bots_test_lib import BotTestCase

class TestFollowUpBot(BotTestCase):
    bot_name = "followup"

    def test_bot(self):
        messages = [  # Template for message inputs to test, absent of message content
            {
                'type': 'stream',
                'display_recipient': 'some stream',
                'subject': 'some subject',
                'sender_email': 'foo_sender@zulip.com',
            },
            {
                'type': 'private',
                'sender_email': 'foo_sender@zulip.com',
            },
        ]
        stream_response = {  # Template for the stream response, absent of response content
            'type': 'stream',
            'to': 'followup',  # Always outputs to followup
            'subject': 'foo_sender@zulip.com',
        }
        expected_send_reply = [
            ("", 'Please specify the message you want to send to followup stream after @mention-bot')
        ]
        expected_send_message = [
            ("foo", 'from foo_sender@zulip.com: foo'),
            ("I have completed my task", 'from foo_sender@zulip.com: I have completed my task'),
        ]
        for m in messages:
            for sr in expected_send_reply:
                self.assert_bot_response(dict(m, content=sr[0]),
                                         (sr[1], 'send_reply'))
            for sm in expected_send_message:
                self.assert_bot_response(dict(m, content=sm[0]),
                                         (dict(stream_response, content=sm[1]), 'send_message'))
