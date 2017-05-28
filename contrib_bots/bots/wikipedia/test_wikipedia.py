#!/usr/bin/env python

from __future__ import absolute_import
from __future__ import print_function

import os
import sys

our_dir = os.path.dirname(os.path.abspath(__file__))
# For dev setups, we can find the API in the repo itself.
if os.path.exists(os.path.join(our_dir, '..')):
    sys.path.insert(0, '..')
from bots_test_lib import BotTestCase

class TestWikipediaBot(BotTestCase):
    bot_name = "wikipedia"

    def test_bot(self):
        self.assert_bot_output(
            {'content': "foo", 'type': "private", 'sender_email': "foo"},
            'For search term "foo", https://en.wikipedia.org/wiki/Foobar'
        )
        self.assert_bot_output(
            {'content': "", 'type': "stream", 'display_recipient': "foo", 'subject': "foo"},
            'Please enter your message after @mention-bot'
        )
        self.assert_bot_output(
            {'content': "sssssss kkkkk", 'type': "stream", 'display_recipient': "foo", 'subject': "foo"},
            'I am sorry. The search term you provided is not found :slightly_frowning_face:'
        )
        self.assert_bot_output(
            {'content': "123", 'type': "stream", 'display_recipient': "foo", 'subject': "foo"},
            'For search term "123", https://en.wikipedia.org/wiki/123'
        )
