#!/usr/bin/env python

from __future__ import absolute_import
from __future__ import print_function

import os
import sys
import unittest

from unittest.mock import MagicMock, patch
from unittest import TestCase

from run import get_lib_module
from bot_lib import StateHandler
from contrib_bots import bot_lib

class BotTestCase(TestCase):

    def mock_test(self, messages, message_handler):
        # type: (List[Dict[str, str]], Function) -> None
        # Mocking BotHandlerApi
        with patch('contrib_bots.bot_lib.BotHandlerApi') as MockClass:
            instance = MockClass.return_value

            for message in messages:
                # Send message to the concerned bot
                message_handler.handle_message(message, MockClass(), StateHandler())

                # Check if BotHandlerApi is sending a reply message.
                # This can later be modified to assert the contents of BotHandlerApi.send_message
                assert instance.send_message.called is True


    def bot_to_run(self, bot_module):
        # type: None -> Function
        lib_module = get_lib_module(bot_module)
        message_handler = lib_module.handler_class()
        return message_handler

    def bot_test(self, messages, bot_module):

        message_handler = self.bot_to_run(bot_module)
        self.mock_test(messages=messages, message_handler=message_handler)
