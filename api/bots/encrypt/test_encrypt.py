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

class TestEncryptBot(BotTestCase):
    bot_name = "encrypt"

    def test_bot(self):
        expected = {
            "": "Encrypted/Decrypted text: ",
            "Let\'s Do It": "Encrypted/Decrypted text: Yrg\'f Qb Vg",
            "me&mom together..!!": "Encrypted/Decrypted text: zr&zbz gbtrgure..!!",
            "foo bar": "Encrypted/Decrypted text: sbb one",
            "Please encrypt this": "Encrypted/Decrypted text: Cyrnfr rapelcg guvf",
        }
        self.check_expected_responses(expected)
