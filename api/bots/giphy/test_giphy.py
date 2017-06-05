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
from bots.giphy import giphy

def get_http_response_json(gif_url):
    response_json = {
        'meta': {
            'status': 200
        },
        'data': {
            'images': {
                'original': {
                    'url': gif_url
                }
            }
        }
    }
    return response_json

def get_bot_response(gif_url):
    return ('[Click to enlarge](%s)'
            '[](/static/images/interactive-bot/giphy/powered-by-giphy.png)'
            % (gif_url))

def get_http_request(keyword):
    return {
        'api_url': giphy.GIPHY_TRANSLATE_API,
        'params': {
            's': keyword,
            'api_key': giphy.get_giphy_api_key_from_config()
        }
    }

class TestGiphyBot(BotTestCase):
    bot_name = "giphy"

    def test_bot(self):
        # This message calls `send_reply` function of BotHandlerApi
        keyword = "Hello"
        gif_url = "https://media4.giphy.com/media/3o6ZtpxSZbQRRnwCKQ/giphy.gif"
        expectations = {
            keyword: get_bot_response(gif_url)
        }
        self.check_expected_responses(
            expectations=expectations,
            http_request=get_http_request(keyword),
            http_response=get_http_response_json(gif_url)
        )
