#!/usr/bin/env python

from __future__ import absolute_import
from __future__ import print_function

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
