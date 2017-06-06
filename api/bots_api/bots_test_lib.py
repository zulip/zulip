#!/usr/bin/env python

from __future__ import absolute_import
from __future__ import print_function

import os
import sys
import unittest
import logging
import requests
import mock

from mock import MagicMock, patch

from run import get_lib_module
from bot_lib import StateHandler
from bots_api import bot_lib
from six.moves import zip

from unittest import TestCase

from typing import List, Dict, Any, Optional
from types import ModuleType

current_dir = os.path.dirname(os.path.abspath(__file__))

class BotTestCase(TestCase):
    bot_name = ''  # type: str

    def check_expected_responses(self, expectations, expected_method='send_reply',
                                 email="foo_sender@zulip.com", recipient="foo", subject="foo",
                                 type="all"):
        # type: (Dict[str, Any], str, str, str, str, str) -> None
        # To test send_message, Any would be a Dict type,
        # to test send_reply, Any would be a str type.
        if type not in ["private", "stream", "all"]:
            logging.exception("check_expected_response expects type to be 'private', 'stream' or 'all'")
        for m, r in expectations.items():
            # For calls with send_reply, r is a string (the content of a message),
            # so we need to add it to a Dict as the value of 'content'.
            # For calls with send_message, r is already a Dict.
            response = {'content': r} if expected_method == 'send_reply' else r
            if type != "stream":
                message = {'content': m, 'type': "private", 'display_recipient': recipient,
                           'sender_email': email}
                self.assert_bot_response(message=message, response=response, expected_method=expected_method)
            if type != "private":
                message = {'content': m, 'type': "stream", 'display_recipient': recipient,
                           'subject': subject, 'sender_email': email}
                self.assert_bot_response(message=message, response=response, expected_method=expected_method)

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

    def call_request(self, message_handler, message, expected_method,
                     MockClass, response):
        # type: (Any, Dict[str, Any], str, Any, Dict[str, Any]) -> None
        # Send message to the concerned bot
        message_handler.handle_message(message, MockClass(), StateHandler())

        # Check if the bot is sending a message via `send_message` function.
        # Where response is a dictionary here.
        instance = MockClass.return_value
        if expected_method == "send_message":
            instance.send_message.assert_called_with(response)
        else:
            instance.send_reply.assert_called_with(message, response['content'])

    def assert_bot_response(self, message, response, expected_method,
                            http_request=None, http_response=None):
        # type: (Dict[str, Any], Dict[str, Any], str, Optional[Dict[str, Any]], Optional[Dict[str, Any]]) -> None
        message_handler = self.get_bot_message_handler()
        # Mocking BotHandlerApi
        with patch('bots_api.bot_lib.BotHandlerApi') as MockClass:
            # If not mock http_request/http_response are provided,
            # just call the request normally (potentially using
            # the Internet)
            if http_response is None:
                assert http_request is None
                self.call_request(message_handler, message, expected_method,
                                  MockClass, response)
                return

            # Otherwise, we mock requests, and verify that the bot
            # made the correct HTTP request to the third-party API
            # (and provide the correct third-party API response.
            # This allows us to test things that would require the
            # Internet without it).
            assert http_request is not None
            with patch('requests.get') as mock_get:
                mock_result = mock.MagicMock()
                mock_result.json.return_value = http_response
                mock_result.ok.return_value = True
                mock_get.return_value = mock_result
                self.call_request(message_handler, message, expected_method,
                                  MockClass, response)
                # Check if the bot is sending the correct http_request corresponding
                # to the given http_response.
                if http_request is not None:
                    mock_get.assert_called_with(http_request['api_url'],
                                                params=http_request['params'])

    def bot_to_run(self, bot_module):
        # Returning Any, same argument as in get_bot_message_handler function.
        # type: (str) -> Any
        lib_module = get_lib_module(bot_module)
        message_handler = lib_module.handler_class()
        return message_handler
