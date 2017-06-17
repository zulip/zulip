#!/usr/bin/env python

from __future__ import absolute_import
from __future__ import print_function

from bots_test_lib import BotTestCase

class TestDefineBot(BotTestCase):
    bot_name = "define"

    def test_bot(self):
        expected = {
            "": 'Please enter a word to define.',
            "foo": "**foo**:\nDefinition not available.",
            "cat": ("**cat**:\n\n* (**noun**) a small domesticated carnivorous mammal "
                    "with soft fur, a short snout, and retractile claws. It is widely "
                    "kept as a pet or for catching mice, and many breeds have been "
                    "developed.\n&nbsp;&nbsp;their pet cat\n\n"),
        }
        self.check_expected_responses(expected)
