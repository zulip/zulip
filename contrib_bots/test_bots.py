#!/usr/bin/env python3

import os
import sys
import unittest

from unittest.mock import MagicMock, patch
from unittest import TestCase

from run import get_lib_module
from bot_lib import BotHandlerApi, StateHandler

class BotTestCase(TestCase):

    bot_module = './bots/define/define.py'

    def mock_test(self, messages, message_handler):
        # type: (List[Dict[str, str]], Function) -> None
        # Mocking BotHandlerApi
        with patch('__main__.BotHandlerApi') as MockClass:
            instance = MockClass.return_value

            for message in messages:
                # Send message to the concerned bot
                message_handler.handle_message(message, MockClass(), StateHandler())

                # Check if BotHandlerApi is sending a reply message.
                # This can later be modified to assert the contents of BotHandlerApi.send_message
                assert instance.send_message.called is True

    # Messages to be sent to bot for testing.
    # Eventually more test messages can be added.
    def test_messages(self):
        # type: None -> List[Dict[str, str]]
        messages = []
        message1 = {'content': "foo", 'type': "private", 'sender_email': "foo"}
        message2 = {'content': "foo", 'type': "stream", 'display_recipient': "foo", 'subject': "foo"}
        messages.append(message1)
        messages.append(message2)
        return messages

    def bot_to_run(self):
        # type: None -> Function
        lib_module = get_lib_module(self.bot_module)
        message_handler = lib_module.handler_class()
        return message_handler

    def test(self):
        # type: None -> None
        # Edit bot_module to test different bots, the below code can be looped for all the bots.

        #bot_module = "./bots/help/help.py"

        messages = self.test_messages()
        message_handler = self.bot_to_run()

        self.mock_test(messages=messages, message_handler=message_handler)

if __name__ == '__main__':
    if len(sys.argv) == 1:
        print("{} <bot module>".format(__file__))
        sys.exit()
    BotTestCase.bot_module = sys.argv.pop()
    unittest.main()
