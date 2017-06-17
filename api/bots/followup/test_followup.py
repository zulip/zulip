#!/usr/bin/env python

from __future__ import absolute_import
from __future__ import print_function

from bots_test_lib import BotTestCase

class TestFollowUpBot(BotTestCase):
    bot_name = "followup"

    def test_bot(self):
        expected_send_reply = {
            "": 'Please specify the message you want to send to followup stream after @mention-bot'
        }
        self.check_expected_responses(expected_send_reply, expected_method='send_reply')

        expected_send_message = {
            "foo": {
                'type': 'stream',
                'to': 'followup',
                'subject': 'foo_sender@zulip.com',
                'content': 'from foo_sender@zulip.com: foo',
            },
            "I have completed my task": {
                'type': 'stream',
                'to': 'followup',
                'subject': 'foo_sender@zulip.com',
                'content': 'from foo_sender@zulip.com: I have completed my task',
            },
        }
        self.check_expected_responses(expected_send_message, expected_method='send_message')
