#!/usr/bin/env python

from __future__ import absolute_import
from __future__ import print_function

from six.moves import zip

from bots_test_lib import BotTestCase

class TestHelpBot(BotTestCase):
    bot_name = "help"

    def test_bot(self):
        txt = "Info on Zulip can be found here:\nhttps://github.com/zulip/zulip"
        messages = ["", "help", "Hi, my name is abc"]
        self.check_expected_responses(dict(list(zip(messages, len(messages)*[txt]))))
