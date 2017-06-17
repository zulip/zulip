#!/usr/bin/env python

from __future__ import absolute_import
from __future__ import print_function

import json

from bots_test_lib import BotTestCase

class TestGiphyBot(BotTestCase):
    bot_name = "giphy"

    def test_bot(self):
        bot_response = '[Click to enlarge]' \
                       '(https://media4.giphy.com/media/3o6ZtpxSZbQRRnwCKQ/giphy.gif)' \
                       '[](/static/images/interactive-bot/giphy/powered-by-giphy.png)'
        # This message calls the `send_reply` function of BotHandlerApi
        with self.mock_config_info({'key': '12345678'}), \
                self.mock_http_conversation('test_1'):
            self.initialize_bot()
            self.assert_bot_response(
                message = {'content': 'Hello'},
                response = {'content': bot_response},
                expected_method='send_reply'
            )
