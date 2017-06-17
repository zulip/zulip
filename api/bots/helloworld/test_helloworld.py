#!/usr/bin/env python

from __future__ import absolute_import
from __future__ import print_function

from six.moves import zip

from bots_test_lib import BotTestCase

class TestHelloWorldBot(BotTestCase):
    bot_name = "helloworld"

    def test_bot(self):
        txt = "beep boop"
        messages = ["", "foo", "Hi, my name is abc"]
        self.check_expected_responses(dict(list(zip(messages, len(messages)*[txt]))))
