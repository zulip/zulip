#!/usr/bin/env python

from __future__ import absolute_import
from __future__ import print_function

from bots_test_lib import BotTestCase

class TestFollowUpBot(BotTestCase):
    bot_name = "followup"

    def test_bot(self):
        followup_response = dict(self.response_template['stream'],
                                 to = 'followup', subject = 'foo_sender@zulip.com')
        expected = [
            ("", ('Please specify the message you want to send to followup stream after @mention-bot',
                  'send_reply')),
            ("foo", 'from foo_sender@zulip.com: foo'),
            ("I have completed my task", 'from foo_sender@zulip.com: I have completed my task'),
        ]
        self.check_expected_responses(expected, default_method='send_message',
                                      default_response_template=followup_response)
