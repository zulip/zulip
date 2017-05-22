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

    # Messages to be sent to bot for testing.
    # Eventually more test messages can be added.
    def request_messages(self):
        # type: None -> List[Dict[str, str]]
        messages = []
        message1 = {'content': "foo", 'type': "private", 'sender_email': "foo"}
        message2 = {'content': "cat", 'type': "stream", 'display_recipient': "foo", 'subject': "foo"}
        messages.append(message1)
        messages.append(message2)
        return messages

    # Reply messages from the test bot.
    # Each reply message corresponding to each request message.
    def bot_response_messages(self):
        # type: None -> List[str]
        messages = []
        message1 = "**foo**:\nDefinition not available."
        message2 = ("**cat**:\n\n* (**noun**) a small domesticated carnivorous mammal "
                    "with soft fur, a short snout, and retractile claws. It is widely "
                    "kept as a pet or for catching mice, and many breeds have been "
                    "developed.\n&nbsp;&nbsp;their pet cat\n\n")
        messages.append(message1)
        messages.append(message2)
        return messages

    def test_define(self):
        # type: None -> None
        # Edit bot_module to test different bots, the below code can be looped for all the bots.
        bot_module = "./bots/define/define.py"
        messages = self.request_messages()
        bot_response = self.bot_response_messages()
        test_case = BotTestCase()
        test_case.bot_test(messages=messages, bot_module=bot_module, bot_response=bot_response)
