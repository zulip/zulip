#!/usr/bin/env python

from __future__ import absolute_import
from __future__ import print_function

import os
import sys
import json

our_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(our_dir)))
# For dev setups, we can find the API in the repo itself.
if os.path.exists(os.path.join(our_dir, '..')):
    sys.path.insert(0, '..')
from bots_test_lib import BotTestCase

class TestGiphyBot(BotTestCase):
    bot_name = "giphy"

    def test_bot(self):
        bot_response = '[Click to enlarge]' \
                       '(https://media4.giphy.com/media/3o6ZtpxSZbQRRnwCKQ/giphy.gif)' \
                       '[](/static/images/interactive-bot/giphy/powered-by-giphy.png)'
        # This message calls the `send_reply` function of BotHandlerApi
        with self.mock_http_conversation('test_1'):
            self.assert_bot_response(
                message = {'content': 'Hello'},
                response = {'content': bot_response},
                expected_method='send_reply'
            )
