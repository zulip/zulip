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

class TestConverterBot(BotTestCase):
    bot_name = "converter"

    def test_bot(self):
        self.assert_bot_output(
            {'content': "2 m cm", 'type': "private", 'sender_email': "foo@gmail.com"},
            "2.0 m = 200.0 cm\n"
        )
        self.assert_bot_output(
            {'content': "12 celsius fahrenheit", 'type': "stream", 'display_recipient': "foo", 'subject': "foo"},
            "12.0 celsius = 53.600054 fahrenheit\n"
        )
        self.assert_bot_output(
            {'content': "0.002 kilometer millimile", 'type': "stream", 'display_recipient': "foo", 'subject': "foo"},
            "0.002 kilometer = 1.2427424 millimile\n"
        )
        self.assert_bot_output(
            {'content': "3 megabyte kilobit", 'type': "stream", 'display_recipient': "foo", 'subject': "foo"},
            "3.0 megabyte = 24576.0 kilobit\n"
        )
        self.assert_bot_output(
            {'content': "foo bar", 'type': "stream", 'display_recipient': "foo", 'subject': "foo"},
            ('Too few arguments given. Enter `@convert help` '
             'for help on using the converter.\n')
        )
