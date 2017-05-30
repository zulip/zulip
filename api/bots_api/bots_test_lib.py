#!/usr/bin/env python

from __future__ import absolute_import
from __future__ import print_function

import os
import sys
import unittest
import logging

from mock import MagicMock, patch

from run import get_lib_module
from bot_lib import StateHandler
from bots_api import bot_lib
from six.moves import zip

from unittest import TestCase

from typing import List, Dict, Any
from types import ModuleType

current_dir = os.path.dirname(os.path.abspath(__file__))

class BotTestCase(TestCase):
    bot_name = '' # type: str

    def assert_bot_output(self, request, response):
        # type: (Dict[str, Any], str) -> None
        bot_module = os.path.normpath(os.path.join(current_dir, "../bots", self.bot_name, self.bot_name + ".py"))
        self.bot_test(messages=[request], bot_module=bot_module,
                      bot_response=[response])

    def check_expected_responses(self, expectations, email="foo", recipient="foo", subject="foo", type="all"):
        # type: (Dict[str, str], str, str, str, str) -> None
        if type not in ["private", "stream", "all"]:
            logging.exception("check_expected_response expects type to be 'private', 'stream' or 'all'")
        for m, r in expectations.items():
            if type != "stream":
                self.assert_bot_output(
                    {'content': m, 'type': "private", 'sender_email': email}, r)
            if type != "private":
                self.assert_bot_output(
                    {'content': m, 'type': "stream", 'display_recipient': recipient,
                     'subject': subject}, r)

    def mock_test(self, messages, message_handler, bot_response):
        # message_handler is of type Any, since it can contain any bot's
        # handler class. Eventually, we want bot's handler classes to
        # inherit from a common prototype specifying the handle_message
        # function.
        # type: (List[Dict[str, Any]], Any, List[str]) -> None
        # Mocking BotHandlerApi
        with patch('bots_api.bot_lib.BotHandlerApi') as MockClass:
            instance = MockClass.return_value

            for (message, response) in zip(messages, bot_response):
                # Send message to the concerned bot
                message_handler.handle_message(message, MockClass(), StateHandler())

                # Check if BotHandlerApi is sending a reply message.
                # This can later be modified to assert the contents of BotHandlerApi.send_message
                instance.send_reply.assert_called_with(message, response)

    def bot_to_run(self, bot_module):
        # Returning Any, same argument as in mock_test function.
        # type: (str) -> Any
        lib_module = get_lib_module(bot_module)
        message_handler = lib_module.handler_class()
        return message_handler

    def bot_test(self, messages, bot_module, bot_response):
        # type: (List[Dict[str, Any]], str, List[str]) -> None
        message_handler = self.bot_to_run(bot_module)
        self.mock_test(messages=messages, message_handler=message_handler, bot_response=bot_response)
