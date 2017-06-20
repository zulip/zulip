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

from typing import List, Dict, Any, Optional, Callable, Tuple
from types import ModuleType

current_dir = os.path.dirname(os.path.abspath(__file__))

class ExpectedContentException(Exception):
    pass

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

    message_template = {
        'private': {
            'type': 'private',
            'display_recipient': "[foo_sender@zulip.com]",
            'sender_email': "foo_sender@zulip.com",
            'sender_id': 0,
            'sender_full_name': "Foo bar",
        },
        'stream': {
            'type': 'stream',
            'display_recipient': 'foo',  # stream name
            'subject': 'foo',            # topic name
            'sender_email': "foo_sender@zulip.com",
            'sender_id': 0,
            'sender_full_name': "Foo Bar",
        },
    }
    response_template = {
        'private': {
            'type': 'private',
            'to': "foo_receiver@zulip.com",
        },
        'stream': {
            'type': 'stream',
            'to': 'foo',
            'subject': 'foo',
        },
    }

    def check_expected_responses(self, content_expectations,
                                 message_templates=list(message_template.values()),
                                 default_method='send_reply',
                                 default_response_template={},
                                 default_result={'result': 'success', 'id': 5}):
        # type: (List[Tuple[str, Any]], List[Dict], str, Dict, Dict) -> None
        # To use defaults, Any would be a str type.
        # To use non-defaults, Any would be a tuple.
        for mt in message_templates:
            for ce in content_expectations:
                (m, r) = ce
                resp = r if isinstance(r, list) else [r]
                # Expand message content to have current message template
                message = dict(mt, content = m)
                # Check entries in content_expectations have the correct form, given args
                for i in resp:
                    err = None
                    if isinstance(i, tuple):
                        li = len(i)
                        if li not in (3, 2):
                            err = "tuple must be length 2 or 3 (or just content)"
                        elif li == 3 and i[1] != 'send_message':
                            err = "length 3 tuple should find: ('<resp>','send_message',<response_template>)"
                        elif li == 2 and i[1] != 'send_reply':
                            err = "length 2 tuple should find: ('<resp>','send_reply')"
                    else:
                        if default_method == 'send_message' and default_response_template == {}:
                            err = "if specifying send_message as default method, you must also specify default_response_template"
                    if err is not None:
                        raise ExpectedContentException("{}\n\t(with response: {})".format(err, resp))
                # Expand each response to use default template, unless specified in entry
                # Result is a list of (response, method, result) pairs
                # FIXME Small change, but cannot specialise result to be not a success in table
                responses = []
                for i in resp:
                    if isinstance(i, tuple):
                        if len(i) == 3:
                            responses.append((dict(i[2], content = i[0]), i[1], default_result))
                        elif len(i) == 2:
                            responses.append((i[0], i[1], default_result))
                    else:
                        responses.append((dict(default_response_template, content = i),
                                          default_method, default_result))
                self.assert_bot_response(message, responses)

    def call_request(self, message, responses):
        # type: (Dict[str, Any], List[Tuple[Any, str, Dict[str, str]]]) -> None
        # Mock 'client'; get instance
        client = self.MockClass()
        instance = self.MockClass.return_value
        # Set return values for each set of calls
        instance.send_message.side_effect = [r[2] for r in responses if r[1] == 'send_message']
        instance.send_reply.side_effect = [r[2] for r in responses if r[1] == 'send_reply']
        # Send message to the bot
        self.message_handler.handle_message(message, client, StateHandler())
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
                err = ("Numbers of {} called do not match those expected" +
                       fail_template).format(fn[0], message, fn[1].call_args_list, fn[2])
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

    def assert_bot_response(self, message, responses):
        # type: (Dict[str, Any], List[Tuple[Any, str, Dict[str, str]]]) -> None
        # Strictly speaking, this function is not needed anymore,
        # kept for now for legacy reasons.
        # FIXME Would like to add support for optionally printing this:
        if 0:
            print(message)
            print("->")
            print(responses)
            print(70*'-')
        self.call_request(message, responses)
