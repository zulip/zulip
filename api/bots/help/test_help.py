#!/usr/bin/env python

from __future__ import absolute_import
from __future__ import print_function

import os
import sys
from six.moves import zip

our_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(our_dir)))
# For dev setups, we can find the API in the repo itself.
if os.path.exists(os.path.join(our_dir, '..')):
    sys.path.insert(0, '..')
from bots_test_lib import BotTestCase

class TestHelpBot(BotTestCase):
    bot_name = "help"

    def test_bot(self):
        txt = "Info on Zulip can be found here:\nhttps://github.com/zulip/zulip"
        messages = ["", "help", "Hi, my name is abc"]
        self.check_expected_responses(dict(list(zip(messages, len(messages)*[txt]))))
