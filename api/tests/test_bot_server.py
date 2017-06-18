from __future__ import absolute_import
import mock
import unittest
from typing import Any
from .bot_server_test_lib import BotServerTestCase

class BotServerTests(BotServerTestCase):
    class MockMessageHandler(object):
        def handle_message(self, message, bot_handler, state_handler):
            # type: (Any, Any, Any) -> None
            assert message == {'key': "test message"}

    class MockLibModule(object):
        def handler_class(self):
            # type: () -> Any
            return BotServerTests.MockMessageHandler()

    @mock.patch('zulip.bot_server.ExternalBotHandler')
    def test_successful_request(self, mock_ExternalBotHandler):
        # type: (mock.Mock) -> None
        available_bots = ['testbot']
        bots_config = {
            'testbot': {
                'email': 'testbot-bot@zulip.com',
                'key': '123456789qwertyuiop',
                'site': 'http://localhost',
            }
        }
        bots_lib_module = {
            'testbot': BotServerTests.MockLibModule()
        }
        self.assert_bot_server_response(available_bots=available_bots,
                                        bots_config=bots_config,
                                        bots_lib_module=bots_lib_module,
                                        check_success=True)
        assert mock_ExternalBotHandler.called

    def test_bot_not_supported(self):
        # type: () -> None
        available_bots = ['testbot']
        self.assert_bot_server_response(available_bots=available_bots,
                                        payload_url="/bots/not_supported_bot",
                                        check_success=False)

    def test_wrong_bot_credentials(self):
        # type: () -> None
        available_bots = ['testbot']
        bots_config = {
            'testbot': {
                'email': 'testbot-bot@zulip.com',
                'key': '123456789qwertyuiop',
                'site': 'http://localhost',
            }
        }
        self.assert_bot_server_response(available_bots=available_bots,
                                        bots_config=bots_config,
                                        check_success=False)

if __name__ == '__main__':
    unittest.main()
