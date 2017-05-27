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

class TestConverterBot(BotTestCase):
    bot_name = "converter"

    def test_bot(self):
        expected = {
            "": ('Too few arguments given. Enter `@convert help` '
                 'for help on using the converter.\n'),
            "foo bar": ('Too few arguments given. Enter `@convert help` '
                        'for help on using the converter.\n'),
            "2 m cm": "2.0 m = 200.0 cm\n",
            "12.0 celsius fahrenheit": "12.0 celsius = 53.600054 fahrenheit\n",
            "0.002 kilometer millimile": "0.002 kilometer = 1.2427424 millimile\n",
            "3 megabyte kilobit": "3.0 megabyte = 24576.0 kilobit\n",
        }
        self.check_expected_responses(expected)
