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
    def messages(self):
        # type: None -> List[Dict[str, str]]
        messages = []
        message1 = {'content': "foo", 'type': "private", 'sender_email': "foo"}
        message2 = {'content': "foo", 'type': "stream", 'display_recipient': "foo", 'subject': "foo"}
        messages.append(message1)
        messages.append(message2)
        return messages

    def test_define(self):
        # type: None -> None
        # Edit bot_module to test different bots, the below code can be looped for all the bots.
        bot_module = "./bots/define/define.py"
        messages = self.messages()
        test_case = BotTestCase()
        test_case.bot_test(messages=messages, bot_module=bot_module)
