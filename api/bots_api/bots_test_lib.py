#!/usr/bin/env python

from __future__ import absolute_import
from __future__ import print_function

import os
import sys

import json
import logging
import mock
import requests
import unittest

from mock import MagicMock, patch

from run import get_lib_module
from bot_lib import StateHandler
from bots_api import bot_lib
from six.moves import zip

from contextlib import contextmanager
from unittest import TestCase

from typing import List, Dict, Any, Optional, Callable
from types import ModuleType

current_dir = os.path.dirname(os.path.abspath(__file__))

class BotTestCase(TestCase):
    bot_name = ''  # type: str

    def get_bot_message_handler(self):
        # type: () -> Any
        # message_handler is of type 'Any', since it can contain any bot's
        # handler class. Eventually, we want bot's handler classes to
        # inherit from a common prototype specifying the handle_message
        # function.
        bot_module_path = os.path.join(
            current_dir, "bots", self.bot_name, self.bot_name + ".py")
        lib_module = get_lib_module(bot_module_path)
        return lib_module.handler_class()

    def setUp(self):
        # type: () -> None
        # Mocking BotHandlerApi
        self.patcher = patch('bots_api.bot_lib.BotHandlerApi')
        self.MockClass = self.patcher.start()
        self.message_handler = self.get_bot_message_handler()

    def tearDown(self):
        # type: () -> None
        self.patcher.stop()

    def initialize_bot(self):
        # type: () -> None
        self.message_handler.initialize(self.MockClass())

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

    def call_request(self, message, expected_method, response):
        # type: (Dict[str, Any], str, Dict[str, Any]) -> None
        # Send message to the concerned bot
        self.message_handler.handle_message(message, self.MockClass(), StateHandler())

        # Check if the bot is sending a message via `send_message` function.
        # Where response is a dictionary here.
        instance = self.MockClass.return_value
        if expected_method == "send_message":
            instance.send_message.assert_called_with(response)
        else:
            instance.send_reply.assert_called_with(message, response['content'])

    @contextmanager
    def mock_config_info(self, config_info):
        # type: (Dict[str, str]) -> Any
        self.MockClass.return_value.get_config_info.return_value = config_info
        yield
        self.MockClass.return_value.get_config_info.return_value = None

    @contextmanager
    def mock_http_conversation(self, test_name):
        # type: (str) -> Any
        """
        Use this context manager to mock and verify a bot's HTTP
        requests to the third-party API (and provide the correct
        third-party API response. This allows us to test things
        that would require the Internet without it).
        """
        assert test_name is not None
        base_path = os.path.realpath(os.path.join(os.path.dirname(
            os.path.abspath(__file__)), '..', 'bots', self.bot_name, 'fixtures'))
        http_request_path = os.path.join(base_path, '{}_request.json'.format(test_name))
        http_response_path = os.path.join(base_path, '{}_response.json'.format(test_name))
        with open(http_request_path, 'r') as http_request_file, \
                open(http_response_path, 'r') as http_response_file:
            http_request = json.load(http_request_file)
            http_response = json.load(http_response_file)
            with patch('requests.get') as mock_get:
                mock_result = mock.MagicMock()
                mock_result.json.return_value = http_response
                mock_result.ok.return_value = True
                mock_get.return_value = mock_result
                yield
                mock_get.assert_called_with(http_request['api_url'],
                                            params=http_request['params'])

    def assert_bot_response(self, message, response, expected_method):
        # type: (Dict[str, Any], Dict[str, Any], str) -> None
        # Strictly speaking, this function is not needed anymore,
        # kept for now for legacy reasons.
        self.call_request(message, expected_method, response)
