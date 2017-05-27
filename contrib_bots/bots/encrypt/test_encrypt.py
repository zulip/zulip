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

class TestEncryptBot(BotTestCase):
    bot_name = "encrypt"

    def test_bot(self):
        self.assert_bot_output(
            {'content': "Please encrypt this", 'type': "private", 'sender_email': "foo@gmail.com"},
            "Encrypted/Decrypted text: Cyrnfr rapelcg guvf"
        )
        self.assert_bot_output(
            {'content': "Let\'s Do It", 'type': "stream", 'display_recipient': "foo", 'subject': "foo"},
            "Encrypted/Decrypted text: Yrg\'f Qb Vg"
        )
        self.assert_bot_output(
            {'content': "", 'type': "stream", 'display_recipient': "foo", 'subject': "foo"},
            "Encrypted/Decrypted text: "
        )
        self.assert_bot_output(
            {'content': "me&mom together..!!", 'type': "stream", 'display_recipient': "foo", 'subject': "foo"},
            "Encrypted/Decrypted text: zr&zbz gbtrgure..!!"
        )
        self.assert_bot_output(
            {'content': "foo bar", 'type': "stream", 'display_recipient': "foo", 'subject': "foo"},
            "Encrypted/Decrypted text: sbb one"
        )
