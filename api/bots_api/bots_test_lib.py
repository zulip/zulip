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

from mock import MagicMock, patch, call

from run import get_lib_module
from bot_lib import StateHandler
from bots_api import bot_lib
from six.moves import zip

from contextlib import contextmanager
from unittest import TestCase

from typing import List, Dict, Any, Optional, Callable, Tuple, Union
from types import ModuleType

from itertools import chain, repeat

current_dir = os.path.dirname(os.path.abspath(__file__))

class BotTestCase(TestCase):
    bot_name = ''  # type: str

    def get_bot_message_handler(self):
        # type: () -> Any
        # message_handler is of type 'Any', since it can contain any bot's
        # handler class. Eventually, we want bot's handler classes to
        # inherit from a common prototype specifying the handle_message
        # function.
        bot_module_path = os.path.normpath(os.path.join(
            current_dir, '..', 'bots', self.bot_name, self.bot_name + '.py'))
        lib_module = get_lib_module(bot_module_path)
        return lib_module.handler_class()

    def setUp(self):
        # type: () -> None
        # Mocking ExternalBotHandler
        self.patcher = patch('bots_api.bot_lib.ExternalBotHandler')
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
                                 sender_id=0, sender_full_name="Foo Bar", type="all"):
        # type: (Dict[str, Any], str, str, str, str, int, str, str) -> None
        # To test send_message, Any would be a Dict type,
        # to test send_reply, Any would be a str type.
        if type not in ["private", "stream", "all"]:
            logging.exception("check_expected_response expects type to be 'private', 'stream' or 'all'")
        for m, r in expectations.items():
            if type != "stream":
                message = {'content': m, 'type': "private", 'display_recipient': recipient,
                           'sender_email': email, 'sender_id': sender_id,
                           'sender_full_name': sender_full_name}
                self.assert_bot_response(message, (r, expected_method))
            if type != "private":
                message = {'content': m, 'type': "stream", 'display_recipient': recipient,
                           'subject': subject, 'sender_email': email, 'sender_id': sender_id,
                           'sender_full_name': sender_full_name}
                self.assert_bot_response(message, (r, expected_method))

    def call_request(self, message, result, *response_list):
        # type: (Dict[str, Any], Dict[str, Any], *Union[Tuple[Dict[str, Any], str], Tuple[Dict[str, Any], str, Dict[str, Any]]]) -> None
        # Expand response_list into responses, where each element has 3 entries
        responses = [(x[0], x[1], (x[2] if len(x) > 2 else result)) for x in response_list]
        # Mock 'client'; get instance
        bot_handler = self.MockClass()
        instance = self.MockClass.return_value
        # Set requested return values for each set of calls, followed by infinitely more
        instance.send_message.side_effect = chain(
            [r[2] for r in responses if r[1] == 'send_message'], repeat(result))
        instance.send_reply.side_effect = chain(
            [r[2] for r in responses if r[1] == 'send_reply'], repeat(result))
        # Send message to the bot
        try:
            self.message_handler.handle_message(message, bot_handler, StateHandler())
        except KeyError as key_err:
            raise Exception("Message tested likely requires key {} to be added".format(key_err))
        # Determine which messaging functions are expected
        send_messages = [call(r[0]) for r in responses if r[1] == 'send_message']
        send_replies = [call(message, r[0]) for r in responses if r[1] == 'send_reply']
        # Test that calls are of correct numbers and that they match
        fail_template = "\nMESSAGE:\n{}\nACTUAL CALLS:\n{}\nEXPECTED:\n{}\n"
        functions_to_test = [['send_message', instance.send_message, send_messages],
                             ['send_reply', instance.send_reply, send_replies]]
        for fn in functions_to_test:
            err = None
            try:
                assert(len(fn[2]) == fn[1].call_count)
            except AssertionError:
                err = ("Numbers of {} called do not match those expected ({} calls, {} expected)" +
                       fail_template).format(fn[0], fn[1].call_count, len(fn[2]), message, fn[1].call_args_list, fn[2])
            else:
                try:
                    if len(fn[2]) > 0:
                        fn[1].assert_has_calls(fn[2])  # any_order = True FIXME
                except AssertionError:
                    err = ("Calls to {} do not match those expected" +
                           fail_template).format(fn[0], message, fn[1].call_args_list, fn[2])
            if err is not None:
                raise AssertionError(err)
            fn[1].reset_mock()  # Ensure the call details are reset

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
        http_data_path = os.path.join(base_path, '{}.json'.format(test_name))
        with open(http_data_path, 'r') as http_data_file:
            http_data = json.load(http_data_file)
            http_request = http_data.get('request')
            http_response = http_data.get('response')
            http_headers = http_data.get('response-headers')
            with patch('requests.get') as mock_get:
                mock_result = mock.MagicMock()
                mock_result.json.return_value = http_response
                mock_result.status_code = http_headers.get('status', 200)
                mock_result.ok.return_value = http_headers.get('ok', True)
                mock_get.return_value = mock_result
                yield
                params = http_request.get('params', None)
                if params is None:
                    mock_get.assert_called_with(http_request['api_url'])
                else:
                    mock_get.assert_called_with(http_request['api_url'], params=params)

    def assert_bot_response(self, message, *response_list, **kwargs):
        # type: (Dict[str, Any], *Union[Tuple[Dict[str, Any], str], Tuple[Dict[str, Any], str, Dict[str, Any]]], **Dict[str, Any]) -> None
        # Strictly speaking, this function is not needed anymore,
        # kept for now for legacy reasons.
        result = kwargs.pop('result', {'result': 'success', 'id': 5})
        self.call_request(message, result, *response_list)
