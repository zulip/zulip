#!/usr/bin/env python

from __future__ import absolute_import
from __future__ import print_function

from bots_test_lib import BotTestCase

class TestWikipediaBot(BotTestCase):
    bot_name = "wikipedia"

    def test_bot(self):
        expected = {
            "": 'Please enter your message after @mention-bot',
            "sssssss kkkkk": ('I am sorry. The search term you provided '
                              'is not found :slightly_frowning_face:'),
            "foo": ('For search term "foo", '
                    'https://en.wikipedia.org/wiki/Foobar'),
            "123": ('For search term "123", '
                    'https://en.wikipedia.org/wiki/123'),
            "laugh": ('For search term "laugh", '
                      'https://en.wikipedia.org/wiki/Laughter'),
        }
        self.check_expected_responses(expected)
