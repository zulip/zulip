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
    bot_name = ''  # type: str

    def check_expected_responses(self, expectations, expected_method='send_reply', email="foo_sender@zulip.com", recipient="foo", subject="foo", type="all"):
        # type: (Dict[str, Any], str, str, str, str, str) -> None
        # To test send_message, Any would be a Dict type,
        # to test send_reply, Any would be a str type.
        if type not in ["private", "stream", "all"]:
            logging.exception("check_expected_response expects type to be 'private', 'stream' or 'all'")
        for m, r in expectations.items():
            if type != "stream":
                self.mock_test(
                    {'content': m, 'type': "private", 'display_recipient': recipient,
                     'sender_email': email}, r, expected_method)
            if type != "private":
                self.mock_test(
                    {'content': m, 'type': "stream", 'display_recipient': recipient,
                     'subject': subject, 'sender_email': email}, r, expected_method)

    def mock_test(self, messages, bot_response, expected_method):
        # type: (Dict[str, str], Any, str) -> None
        if expected_method == "send_reply":
            self.mock_test_send_reply(messages, bot_response, expected_method)
        else:
            self.mock_test_send_message(messages, bot_response, expected_method)

    def mock_test_send_message(self, messages, bot_response, expected_method):
        # type: (Dict[str, str], Dict[str, str], str) -> None
        # Since send_message function uses bot_response of type Dict, no
        # further changes required.
        self.assert_bot_output([messages], [bot_response], expected_method)

    def mock_test_send_reply(self, messages, bot_response, expected_method):
        # type: (Dict[str, str], str, str) -> None
        # Since send_reply function uses bot_response of type str, we
        # do convert the str type to a Dict type to have the same assert_bot_output function.
        bot_response_type_dict = {'content': bot_response}
        self.assert_bot_output([messages], [bot_response_type_dict], expected_method)

    def get_bot_message_handler(self):
        # type: () -> Any
        # message_handler is of type 'Any', since it can contain any bot's
        # handler class. Eventually, we want bot's handler classes to
        # inherit from a common prototype specifying the handle_message
        # function.
        bot_module = os.path.join(current_dir, "bots",
                                  self.bot_name, self.bot_name + ".py")
        message_handler = self.bot_to_run(bot_module)
        return message_handler

    def assert_bot_output(self, messages, bot_response, expected_method):
        # type: (List[Dict[str, Any]], List[Dict[str, str]], str) -> None
        message_handler = self.get_bot_message_handler()
        # Mocking BotHandlerApi
        with patch('bots_api.bot_lib.BotHandlerApi') as MockClass:
            instance = MockClass.return_value

            for (message, response) in zip(messages, bot_response):
                # Send message to the concerned bot
                message_handler.handle_message(message, MockClass(), StateHandler())
                # Check if the bot is sending a message via `send_message` function.
                # Where response is a dictionary here.
                if expected_method == "send_message":
                    instance.send_message.assert_called_with(response)
                else:
                    instance.send_reply.assert_called_with(message, response['content'])

    def bot_to_run(self, bot_module):
        # Returning Any, same argument as in get_bot_message_handler function.
        # type: (str) -> Any
        lib_module = get_lib_module(bot_module)
        message_handler = lib_module.handler_class()
        return message_handler
