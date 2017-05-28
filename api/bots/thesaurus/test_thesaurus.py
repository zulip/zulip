#!/usr/bin/env python

from __future__ import absolute_import
from __future__ import print_function

import os
import sys

our_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(our_dir)))
# For dev setups, we can find the API in the repo itself.
if os.path.exists(os.path.join(our_dir, '..')):
    sys.path.insert(0, '..')
from bots_test_lib import BotTestCase

class TestThesaurusBot(BotTestCase):
    bot_name = "thesaurus"

    def test_bot(self):
        expected = {
            "synonym good": "great, satisfying, exceptional, positive, acceptable",
            "synonym nice": "cordial, kind, good, okay, fair",
            "synonym foo": "bar, thud, X, baz, corge",
            "antonym dirty": "ordered, sterile, spotless, moral, clean",
            "antonym bar": "loss, whole, advantage, aid, failure",
            "": ("To use this bot, start messages with either "
                 "@mention-bot synonym (to get the synonyms of a given word) "
                 "or @mention-bot antonym (to get the antonyms of a given word). "
                 "Phrases are not accepted so only use single words "
                 "to search. For example you could search '@mention-bot synonym hello' "
                 "or '@mention-bot antonym goodbye'."),
        }
        self.check_expected_responses(expected)
