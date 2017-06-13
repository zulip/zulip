#!/usr/bin/env python

from __future__ import absolute_import
from __future__ import print_function

import os
import sys
import json

our_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(our_dir)))
# For dev setups, we can find the API in the repo itself.
if os.path.exists(os.path.join(our_dir, '..')):
    sys.path.insert(0, '..')
from bots_test_lib import BotTestCase

class TestGithubDetailBot(BotTestCase):
    bot_name = "github_detail"

    def test_issue(self):
        bot_response = '**[zulip/zulip#5365](https://github.com/zulip/zulip/issues/5365)'\
                       ' - frontend: Enable hot-reloading of CSS in development**\n'\
                       'Created by **[timabbott](https://github.com/timabbott)**\n'\
                       'Status - **Open**\n'\
                       '```quote\n'\
                       'There\'s strong interest among folks working on the frontend in being '\
                       'able to use the hot-reloading feature of webpack for managing our CSS.\r\n\r\n'\
                       'In order to do this, step 1 is to move our CSS minification pipeline '\
                       'from django-pipeline to Webpack.  \n```'
        # This message calls the `send_reply` function of BotHandlerApi
        with self.mock_http_conversation('test_issue'):
            self.assert_bot_response(
                message = {'content': 'zulip/zulip#5365'},
                response = {'content': bot_response},
                expected_method='send_reply'
            )

    def test_pull_request(self):
        bot_response = '**[zulip/zulip#5345](https://github.com/zulip/zulip/pull/5345)'\
                       ' - [WIP] modal: Replace bootstrap modal with custom modal class**\n'\
                       'Created by **[jackrzhang](https://github.com/jackrzhang)**\n'\
                       'Status - **Open**\n```quote\nAn interaction bug (#4811)  '\
                       'between our settings UI and the bootstrap modals breaks hotkey '\
                       'support for `Esc` when multiple modals are open.\r\n\r\ntodo:\r\n[x]'\
                       ' Create `Modal` class in `modal.js` (drafted by @brockwhittaker)\r\n[x]'\
                       ' Reimplement change_email_modal utilizing `Modal` class\r\n[] Dump '\
                       'using bootstrap for the account settings modal and all other modals,'\
                       ' replace with `Modal` class\r\n[] Add hotkey support for closing the'\
                       ' top modal for `Esc`\r\n\r\nThis should also be a helpful step in removing dependencies from Bootstrap.\n```'
        # This message calls the `send_reply` function of BotHandlerApi
        with self.mock_http_conversation('test_pull'):
            self.assert_bot_response(
                message = {'content': 'zulip/zulip#5345'},
                response = {'content': bot_response},
                expected_method='send_reply'
            )

    def test_404(self):
        bot_response = 'Failed to find issue/pr: zulip/zulip#0'
        # This message calls the `send_reply` function of BotHandlerApi
        with self.mock_http_conversation('test_404'):
            self.assert_bot_response(
                message = {'content': 'zulip/zulip#0'},
                response = {'content': bot_response},
                expected_method='send_reply'
            )

    def test_random_text(self):
        bot_response = 'Failed to find any issue or PR.'
        # This message calls the `send_reply` function of BotHandlerApi
        self.assert_bot_response(
            message = {'content': 'some random text'},
            response = {'content': bot_response},
            expected_method='send_reply'
        )

    def test_help_text(self):
        bot_response = 'This plugin displays details on github issues and pull requests. '\
                       'To reference an issue or pull request usename mention the bot then '\
                       'anytime in the message type its id, for example:\n@**Github detail** '\
                       '#3212 zulip#3212 zulip/zulip#3212\nThe default owner is zulip and '\
                       'the default repo is zulip.'
        # This message calls the `send_reply` function of BotHandlerApi

        mock_config = {'owner': 'zulip', 'repo': 'zulip'}
        with self.mock_config_info(mock_config):
            self.initialize_bot()
            self.assert_bot_response(
                message = {'content': 'help'},
                response = {'content': bot_response},
                expected_method='send_reply'
            )
