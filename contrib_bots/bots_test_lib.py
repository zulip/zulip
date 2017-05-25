#!/usr/bin/env python

from __future__ import absolute_import
from __future__ import print_function

import os
import sys
import unittest

from mock import MagicMock, patch

from run import get_lib_module
from bot_lib import StateHandler
from contrib_bots import bot_lib
from six.moves import zip

from unittest import TestCase

current_dir = os.path.dirname(os.path.abspath(__file__))

class BotTestCase(TestCase):
    bot_name = None

    def assert_bot_output(self, request, response):
        # type: (str, str) -> None
        bot_module = os.path.join(current_dir, "bots",
                                  self.bot_name, self.bot_name + ".py")
        self.bot_test(messages=[request], bot_module=bot_module,
                      bot_response=[response])

    def mock_test(self, messages, message_handler, bot_response):
        # type: (List[Dict[str, str]], Function) -> None
        # Mocking BotHandlerApi
        with patch('contrib_bots.bot_lib.BotHandlerApi') as MockClass:
            instance = MockClass.return_value

            for (message, response) in zip(messages, bot_response):
                # Send message to the concerned bot
                message_handler.handle_message(message, MockClass(), StateHandler())

                # Check if BotHandlerApi is sending a reply message.
                # This can later be modified to assert the contents of BotHandlerApi.send_message
                instance.send_reply.assert_called_with(message, response)

    def bot_to_run(self, bot_module):
        # type: None -> Function
        lib_module = get_lib_module(bot_module)
        message_handler = lib_module.handler_class()
        return message_handler

    def bot_test(self, messages, bot_module, bot_response):
        message_handler = self.bot_to_run(bot_module)
        self.mock_test(messages=messages, message_handler=message_handler, bot_response=bot_response)
