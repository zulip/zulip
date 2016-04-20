# -*- coding: utf-8 -*-
import os
from mock import patch
from django.test import TestCase
from django.conf import settings
from django.core.management import call_command


class TestSendWebhookFixtureMessage(TestCase):
    COMMAND_NAME = 'send_webhook_fixture_message'

    def setUp(self):
        self.fixture_path = os.path.join('some', 'fake', 'path.json')
        self.url = '/some/url/with/hook'

    @patch('zerver.management.commands.send_webhook_fixture_message.Command.print_help')
    def test_check_if_command_exits_when_fixture_param_is_empty(self, print_help_mock):
        with self.assertRaises(SystemExit):
            call_command(self.COMMAND_NAME, url=self.url)

        print_help_mock.assert_any_call('python manage.py', self.COMMAND_NAME)

    @patch('zerver.management.commands.send_webhook_fixture_message.Command.print_help')
    def test_check_if_command_exits_when_url_param_is_empty(self, print_help_mock):
        with self.assertRaises(SystemExit):
            call_command(self.COMMAND_NAME, fixture=self.fixture_path)

        print_help_mock.assert_any_call('python manage.py', self.COMMAND_NAME)

    @patch('zerver.management.commands.send_webhook_fixture_message.os.path.exists')
    def test_check_if_command_exits_when_fixture_path_does_not_exist(self, os_path_exists_mock):
        os_path_exists_mock.return_value = False

        with self.assertRaises(SystemExit):
            call_command(self.COMMAND_NAME, fixture=self.fixture_path, url=self.url)

        os_path_exists_mock.assert_any_call(os.path.join(settings.DEPLOY_ROOT, self.fixture_path))

    @patch('zerver.management.commands.send_webhook_fixture_message.os.path.exists')
    @patch('zerver.management.commands.send_webhook_fixture_message.Client')
    @patch('zerver.management.commands.send_webhook_fixture_message.ujson')
    @patch("zerver.management.commands.send_webhook_fixture_message.open", create=True)
    def test_check_if_command_post_request_to_url_with_fixture(self,
                                                               open_mock,
                                                               ujson_mock,
                                                               client_mock,
                                                               os_path_exists_mock):
        ujson_mock.loads.return_value = '{}'
        ujson_mock.dumps.return_value = {}
        os_path_exists_mock.return_value = True

        client = client_mock()

        call_command(self.COMMAND_NAME, fixture=self.fixture_path, url=self.url)
        self.assertTrue(ujson_mock.dumps.called)
        self.assertTrue(ujson_mock.loads.called)
        self.assertTrue(open_mock.called)
        client.post.assert_called_once_with(self.url, {}, content_type="application/json")
