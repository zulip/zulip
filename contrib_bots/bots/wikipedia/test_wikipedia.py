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
        expected = { 
            "":       'Please enter your message after @mention-bot',
            "test":   ('For search term "test", '
                       'https://en.wikipedia.org/wiki/Test'),
            "cheese": ('For search term "cheese", '
                       'https://en.wikipedia.org/wiki/Cheese'),
            "laugh":  ('For search term "laugh", '
                       'https://en.wikipedia.org/wiki/Laughter'),
                   }
        for m, r in expected.items():
            self.assert_bot_output(
                {'content': m, 'type': "private", 'sender_email': "foo"}, r)
            self.assert_bot_output(
                {'content': m, 'type': "stream", 'sender_email': "foo"}, r)
