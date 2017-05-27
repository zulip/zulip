#!/usr/bin/env python

from __future__ import absolute_import
from __future__ import print_function

import mock
import os
import sys

our_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(our_dir)))
# For dev setups, we can find the API in the repo itself.
if os.path.exists(os.path.join(our_dir, '..')):
    sys.path.insert(0, '..')
from bots_test_lib import BotTestCase

class TestXkcdBot(BotTestCase):
    bot_name = "xkcd"

    @mock.patch('logging.exception')
    def test_bot(self, mock_logging_exception):
        help_txt = "xkcd bot supports these commands:"
        err_txt  = "xkcd bot only supports these commands:"
        commands = '''
* `@xkcd help` to show this help message.
* `@xkcd latest` to fetch the latest comic strip from xkcd.
* `@xkcd random` to fetch a random comic strip from xkcd.
* `@xkcd <comic id>` to fetch a comic strip based on `<comic id>` e.g `@xkcd 1234`.'''
        invalid_id_txt = "Sorry, there is likely no xkcd comic strip with id: #"
        expected = {
            "": err_txt+commands,
            "help": help_txt+commands,
            "x": err_txt+commands,
            "0": invalid_id_txt + "0",
            "1": ("#1: **Barrel - Part 1**\n[Don't we all.]"
                  "(https://imgs.xkcd.com/comics/barrel_cropped_(1).jpg)"),
            "1800": ("#1800: **Chess Notation**\n"
                     "[I've decided to score all my conversations "
                     "using chess win-loss notation. (??)]"
                     "(https://imgs.xkcd.com/comics/chess_notation.png)"),
            "999999999": invalid_id_txt + "999999999",
        }
        self.check_expected_responses(expected)
