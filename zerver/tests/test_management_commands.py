# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function

import os
import glob
from datetime import timedelta
from mock import MagicMock, patch
from six.moves import map, filter

from django.conf import settings
from django.core.management import call_command
from django.test import TestCase
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import stdout_suppressed
from zerver.models import get_realm
from confirmation.models import RealmCreationKey, generate_realm_creation_url

class TestCommandsCanStart(TestCase):

    def setUp(self):
        # type: () -> None
        self.commands = filter(
            lambda filename: filename != '__init__',
            map(
                lambda file: os.path.basename(file).replace('.py', ''),
                glob.iglob('*/management/commands/*.py')
            )
        )

    def test_management_commands_show_help(self):
        # type: () -> None
        with stdout_suppressed() as stdout:
            for command in self.commands:
                print('Testing management command: {}'.format(command),
                      file=stdout)

                with self.assertRaises(SystemExit):
                    call_command(command, '--help')
        # zerver/management/commands/runtornado.py sets this to True;
        # we need to reset it here.  See #3685 for details.
        settings.RUNNING_INSIDE_TORNADO = False

class TestSendWebhookFixtureMessage(TestCase):
    COMMAND_NAME = 'send_webhook_fixture_message'

    def setUp(self):
        # type: () -> None
        self.fixture_path = os.path.join('some', 'fake', 'path.json')
        self.url = '/some/url/with/hook'

    @patch('zerver.management.commands.send_webhook_fixture_message.Command.print_help')
    def test_check_if_command_exits_when_fixture_param_is_empty(self, print_help_mock):
        # type: (MagicMock) -> None
        with self.assertRaises(SystemExit):
            call_command(self.COMMAND_NAME, url=self.url)

        print_help_mock.assert_any_call('./manage.py', self.COMMAND_NAME)

    @patch('zerver.management.commands.send_webhook_fixture_message.Command.print_help')
    def test_check_if_command_exits_when_url_param_is_empty(self, print_help_mock):
        # type: (MagicMock) -> None
        with self.assertRaises(SystemExit):
            call_command(self.COMMAND_NAME, fixture=self.fixture_path)

        print_help_mock.assert_any_call('./manage.py', self.COMMAND_NAME)

    @patch('zerver.management.commands.send_webhook_fixture_message.os.path.exists')
    def test_check_if_command_exits_when_fixture_path_does_not_exist(self, os_path_exists_mock):
        # type: (MagicMock) -> None
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
        # type: (MagicMock, MagicMock, MagicMock, MagicMock) -> None
        ujson_mock.loads.return_value = '{}'
        ujson_mock.dumps.return_value = {}
        os_path_exists_mock.return_value = True

        client = client_mock()

        call_command(self.COMMAND_NAME, fixture=self.fixture_path, url=self.url)
        self.assertTrue(ujson_mock.dumps.called)
        self.assertTrue(ujson_mock.loads.called)
        self.assertTrue(open_mock.called)
        client.post.assert_called_once_with(self.url, {}, content_type="application/json")

class TestGenerateRealmCreationLink(ZulipTestCase):
    COMMAND_NAME = "generate_realm_creation_link"

    def test_generate_link_and_create_realm(self):
        # type: () -> None
        email = "user1@test.com"
        generated_link = generate_realm_creation_url()

        with self.settings(OPEN_REALM_CREATION=False):
            # Check realm creation page is accessible
            result = self.client_get(generated_link)
            self.assert_in_success_response([u"Create a new Zulip organization"], result)

            # Create Realm with generated link
            self.assertIsNone(get_realm('test'))
            result = self.client_post(generated_link, {'email': email})
            self.assertEqual(result.status_code, 302)
            self.assertTrue(result["Location"].endswith(
                "/accounts/send_confirm/%s" % (email,)))
            result = self.client_get(result["Location"])
            self.assert_in_response("Check your email so we can get started.", result)

            # Generated link used for creating realm
            result = self.client_get(generated_link)
            self.assert_in_success_response(["The organization creation link has expired or is not valid."], result)

    def test_realm_creation_with_random_link(self):
        # type: () -> None
        with self.settings(OPEN_REALM_CREATION=False):
            # Realm creation attempt with an invalid link should fail
            random_link = "/create_realm/5e89081eb13984e0f3b130bf7a4121d153f1614b"
            result = self.client_get(random_link)
            self.assert_in_success_response(["The organization creation link has expired or is not valid."], result)

    def test_realm_creation_with_expired_link(self):
        # type: () -> None
        with self.settings(OPEN_REALM_CREATION=False):
            generated_link = generate_realm_creation_url()
            key = generated_link[-40:]
            # Manually expire the link by changing the date of creation
            obj = RealmCreationKey.objects.get(creation_key=key)
            obj.date_created = obj.date_created - timedelta(days=settings.REALM_CREATION_LINK_VALIDITY_DAYS + 1)
            obj.save()

            result = self.client_get(generated_link)
            self.assert_in_success_response(["The organization creation link has expired or is not valid."], result)
