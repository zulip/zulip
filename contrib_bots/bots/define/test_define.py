#!/usr/bin/env python

from __future__ import absolute_import
from __future__ import print_function

import os
import sys
import unittest
from unittest import TestCase

our_dir = os.path.dirname(os.path.abspath(__file__))

# For dev setups, we can find the API in the repo itself.
if os.path.exists(os.path.join(our_dir, '..')):
    sys.path.insert(0, '..')
from bots_test_lib import BotTestCase

class TestDefineBot(TestCase):
    def setUp(self):
        # Messages to be sent to bot for testing.
        self.request_messages = [
            {'content': "foo", 'type': "private", 'sender_email': "foo"},
            {'content': "cat", 'type': "stream", 'display_recipient': "foo", 'subject': "foo"},
        ]
        # Reply messages from the test bot.
        self.bot_response_messages = [
            "**foo**:\nDefinition not available.",
            ("**cat**:\n\n* (**noun**) a small domesticated carnivorous mammal "
                    "with soft fur, a short snout, and retractile claws. It is widely "
                    "kept as a pet or for catching mice, and many breeds have been "
                    "developed.\n&nbsp;&nbsp;their pet cat\n\n"),
        ]

    def runTest(self):
        # type: None -> None
        # Edit bot_module to test different bots, the below code can be looped for all the bots.
        bot_module = os.path.join(our_dir, "define.py")
        test_case = BotTestCase()
        test_case.bot_test(messages=self.request_messages, bot_module=bot_module,
            bot_response=self.bot_response_messages)
