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

class TestThesaurusBot(BotTestCase):
    bot_name = "thesaurus"

    def test_bot(self):
        self.assert_bot_output(
            {'content': "synonym good", 'type': "private", 'sender_email': "foo"},
            "great, satisfying, exceptional, positive, acceptable"
        )
        self.assert_bot_output(
            {'content': "synonym nice", 'type': "stream", 'display_recipient': "foo", 'subject': "foo"},
            "cordial, kind, good, okay, fair"
        )
        self.assert_bot_output(
            {'content': "synonym foo", 'type': "stream", 'display_recipient': "foo", 'subject': "foo"},
            "bar, thud, X, baz, corge"
        )
        self.assert_bot_output(
            {'content': "antonym dirty", 'type': "stream", 'display_recipient': "foo", 'subject': "foo"},
            "ordered, sterile, spotless, moral, clean"
        )
        self.assert_bot_output(
            {'content': "antonym bar", 'type': "stream", 'display_recipient': "foo", 'subject': "foo"},
            "loss, whole, advantage, aid, failure"
        )
        self.assert_bot_output(
            {'content': "", 'type': "stream", 'display_recipient': "foo", 'subject': "foo"},
            ("To use this bot, start messages with either "
             "@mention-bot synonym (to get the synonyms of a given word) "
             "or @mention-bot antonym (to get the antonyms of a given word). "
             "Phrases are not accepted so only use single words "
             "to search. For example you could search '@mention-bot synonym hello' "
             "or '@mention-bot antonym goodbye'."),
        )
