# -*- coding: utf-8 -*-

import glob
import os
import re
from datetime import timedelta
from email.utils import parseaddr
from mock import MagicMock, patch, call
from typing import List, Dict, Any, Optional

from django.conf import settings
from django.core.management import call_command
from django.test import TestCase, override_settings
from zerver.lib.actions import do_create_user
from zerver.lib.management import ZulipBaseCommand, CommandError, check_config
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import stdout_suppressed
from zerver.lib.test_runner import slow
from zerver.models import Recipient, get_user_profile_by_email, get_stream

from zerver.lib.test_helpers import most_recent_message
from zerver.models import get_realm, UserProfile, Realm
from confirmation.models import RealmCreationKey, generate_realm_creation_url

class TestCheckConfig(ZulipTestCase):
    def test_check_config(self) -> None:
        with self.assertRaisesRegex(CommandError, "Error: You must set ZULIP_ADMINISTRATOR in /etc/zulip/settings.py."):
            check_config()
        with self.settings(REQUIRED_SETTINGS=[('asdf', 'not asdf')]):
            with self.assertRaisesRegex(CommandError, "Error: You must set asdf in /etc/zulip/settings.py."):
                check_config()

    @override_settings(WARN_NO_EMAIL=True)
    def test_check_send_email(self) -> None:
        with self.assertRaisesRegex(CommandError, "Outgoing email not yet configured, see"):
            call_command("send_test_email", 'test@example.com')

class TestZulipBaseCommand(ZulipTestCase):
    def setUp(self) -> None:
        self.zulip_realm = get_realm("zulip")
        self.command = ZulipBaseCommand()

    def test_get_client(self) -> None:
        self.assertEqual(self.command.get_client().name, "ZulipServer")

    def test_get_realm(self) -> None:
        self.assertEqual(self.command.get_realm(dict(realm_id='zulip')), self.zulip_realm)
        self.assertEqual(self.command.get_realm(dict(realm_id=None)), None)
        self.assertEqual(self.command.get_realm(dict(realm_id='1')), self.zulip_realm)
        with self.assertRaisesRegex(CommandError, "There is no realm with id"):
            self.command.get_realm(dict(realm_id='17'))
        with self.assertRaisesRegex(CommandError, "There is no realm with id"):
            self.command.get_realm(dict(realm_id='mit'))

    def test_get_user(self) -> None:
        mit_realm = get_realm("zephyr")
        user_profile = self.example_user("hamlet")
        email = user_profile.email

        self.assertEqual(self.command.get_user(email, self.zulip_realm), user_profile)
        self.assertEqual(self.command.get_user(email, None), user_profile)

        error_message = "The realm '<Realm: zephyr 2>' does not contain a user with email"
        with self.assertRaisesRegex(CommandError, error_message):
            self.command.get_user(email, mit_realm)

        with self.assertRaisesRegex(CommandError, "server does not contain a user with email"):
            self.command.get_user('invalid_email@example.com', None)

        do_create_user(email, 'password', mit_realm, 'full_name', 'short_name')

        with self.assertRaisesRegex(CommandError, "server contains multiple users with that email"):
            self.command.get_user(email, None)

    def test_get_user_profile_by_email(self) -> None:
        user_profile = self.example_user("hamlet")
        email = user_profile.email

        self.assertEqual(get_user_profile_by_email(email), user_profile)

    def get_users_sorted(self, options: Dict[str, Any], realm: Optional[Realm],
                         is_bot: Optional[bool]=None) -> List[UserProfile]:
        user_profiles = self.command.get_users(options, realm, is_bot=is_bot)
        return sorted(user_profiles, key = lambda x: x.email)

    def test_get_users(self) -> None:
        user_emails = self.example_email("hamlet") + "," + self.example_email("iago")
        expected_user_profiles = [self.example_user("hamlet"), self.example_user("iago")]
        user_profiles = self.get_users_sorted(dict(users=user_emails), self.zulip_realm)
        self.assertEqual(user_profiles, expected_user_profiles)
        user_profiles = self.get_users_sorted(dict(users=user_emails), None)
        self.assertEqual(user_profiles, expected_user_profiles)

        user_emails = self.example_email("iago") + "," + self.mit_email("sipbtest")
        expected_user_profiles = [self.example_user("iago"), self.mit_user("sipbtest")]
        user_profiles = self.get_users_sorted(dict(users=user_emails), None)
        self.assertEqual(user_profiles, expected_user_profiles)
        error_message = "The realm '<Realm: zulip 1>' does not contain a user with email"
        with self.assertRaisesRegex(CommandError, error_message):
            self.command.get_users(dict(users=user_emails), self.zulip_realm)

        self.assertEqual(self.command.get_users(dict(users=self.example_email("iago")), self.zulip_realm),
                         [self.example_user("iago")])

        self.assertEqual(self.command.get_users(dict(users=None), None), [])

    def test_get_users_with_all_users_argument_enabled(self) -> None:
        user_emails = self.example_email("hamlet") + "," + self.example_email("iago")
        expected_user_profiles = [self.example_user("hamlet"), self.example_user("iago")]
        user_profiles = self.get_users_sorted(dict(users=user_emails, all_users=False), self.zulip_realm)
        self.assertEqual(user_profiles, expected_user_profiles)
        error_message = "You can't use both -u/--users and -a/--all-users."
        with self.assertRaisesRegex(CommandError, error_message):
            self.command.get_users(dict(users=user_emails, all_users=True), None)

        expected_user_profiles = sorted(UserProfile.objects.filter(realm=self.zulip_realm),
                                        key = lambda x: x.email)
        user_profiles = self.get_users_sorted(dict(users=None, all_users=True), self.zulip_realm)
        self.assertEqual(user_profiles, expected_user_profiles)

        error_message = "You have to pass either -u/--users or -a/--all-users."
        with self.assertRaisesRegex(CommandError, error_message):
            self.command.get_users(dict(users=None, all_users=False), None)

        error_message = "The --all-users option requires a realm; please pass --realm."
        with self.assertRaisesRegex(CommandError, error_message):
            self.command.get_users(dict(users=None, all_users=True), None)

    def test_get_non_bot_users(self) -> None:
        expected_user_profiles = sorted(UserProfile.objects.filter(realm=self.zulip_realm,
                                                                   is_bot=False),
                                        key = lambda x: x.email)
        user_profiles = self.get_users_sorted(dict(users=None, all_users=True),
                                              self.zulip_realm,
                                              is_bot=False)
        self.assertEqual(user_profiles, expected_user_profiles)

class TestCommandsCanStart(TestCase):

    def setUp(self) -> None:
        self.commands = filter(
            lambda filename: filename != '__init__',
            map(
                lambda file: os.path.basename(file).replace('.py', ''),
                glob.iglob('*/management/commands/*.py')
            )
        )

    @slow("Aggregate of runs dozens of individual --help tests")
    def test_management_commands_show_help(self) -> None:
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

    def setUp(self) -> None:
        self.fixture_path = os.path.join('some', 'fake', 'path.json')
        self.url = '/some/url/with/hook'

    @patch('zerver.management.commands.send_webhook_fixture_message.Command.print_help')
    def test_check_if_command_exits_when_fixture_param_is_empty(self, print_help_mock: MagicMock) -> None:
        with self.assertRaises(SystemExit):
            call_command(self.COMMAND_NAME, url=self.url)

        print_help_mock.assert_any_call('./manage.py', self.COMMAND_NAME)

    @patch('zerver.management.commands.send_webhook_fixture_message.Command.print_help')
    def test_check_if_command_exits_when_url_param_is_empty(self, print_help_mock: MagicMock) -> None:
        with self.assertRaises(SystemExit):
            call_command(self.COMMAND_NAME, fixture=self.fixture_path)

        print_help_mock.assert_any_call('./manage.py', self.COMMAND_NAME)

    @patch('zerver.management.commands.send_webhook_fixture_message.os.path.exists')
    def test_check_if_command_exits_when_fixture_path_does_not_exist(
            self, os_path_exists_mock: MagicMock) -> None:
        os_path_exists_mock.return_value = False

        with self.assertRaises(SystemExit):
            call_command(self.COMMAND_NAME, fixture=self.fixture_path, url=self.url)

        os_path_exists_mock.assert_any_call(os.path.join(settings.DEPLOY_ROOT, self.fixture_path))

    @patch('zerver.management.commands.send_webhook_fixture_message.os.path.exists')
    @patch('zerver.management.commands.send_webhook_fixture_message.Client')
    @patch('zerver.management.commands.send_webhook_fixture_message.ujson')
    @patch("zerver.management.commands.send_webhook_fixture_message.open", create=True)
    def test_check_if_command_post_request_to_url_with_fixture(self,
                                                               open_mock: MagicMock,
                                                               ujson_mock: MagicMock,
                                                               client_mock: MagicMock,
                                                               os_path_exists_mock: MagicMock) -> None:
        ujson_mock.loads.return_value = '{}'
        ujson_mock.dumps.return_value = {}
        os_path_exists_mock.return_value = True

        client = client_mock()

        with self.assertRaises(SystemExit):
            call_command(self.COMMAND_NAME, fixture=self.fixture_path, url=self.url)
        self.assertTrue(ujson_mock.dumps.called)
        self.assertTrue(ujson_mock.loads.called)
        self.assertTrue(open_mock.called)
        client.post.assert_called_once_with(self.url, {}, content_type="application/json",
                                            HTTP_HOST="zulip.testserver")

class TestGenerateRealmCreationLink(ZulipTestCase):
    COMMAND_NAME = "generate_realm_creation_link"

    @override_settings(OPEN_REALM_CREATION=False)
    def test_generate_link_and_create_realm(self) -> None:
        email = "user1@test.com"
        generated_link = generate_realm_creation_url(by_admin=True)

        # Get realm creation page
        result = self.client_get(generated_link)
        self.assert_in_success_response([u"Create a new Zulip organization"], result)

        # Enter email
        self.assertIsNone(get_realm('test'))
        result = self.client_post(generated_link, {'email': email})
        self.assertEqual(result.status_code, 302)
        self.assertTrue(re.search(r'/accounts/do_confirm/\w+$', result["Location"]))

        # Bypass sending mail for confirmation, go straight to creation form
        result = self.client_get(result["Location"])
        self.assert_in_response('action="/accounts/register/"', result)

        # Original link is now dead
        result = self.client_get(generated_link)
        self.assert_in_success_response(["The organization creation link has expired or is not valid."], result)

    @override_settings(OPEN_REALM_CREATION=False)
    def test_generate_link_confirm_email(self) -> None:
        email = "user1@test.com"
        generated_link = generate_realm_creation_url(by_admin=False)

        result = self.client_post(generated_link, {'email': email})
        self.assertEqual(result.status_code, 302)
        self.assertTrue(re.search('/accounts/new/send_confirm/{}$'.format(email),
                                  result["Location"]))
        result = self.client_get(result["Location"])
        self.assert_in_response("Check your email so we can get started", result)

        # Original link is now dead
        result = self.client_get(generated_link)
        self.assert_in_success_response(["The organization creation link has expired or is not valid."], result)

    @override_settings(OPEN_REALM_CREATION=False)
    def test_realm_creation_with_random_link(self) -> None:
        # Realm creation attempt with an invalid link should fail
        random_link = "/new/5e89081eb13984e0f3b130bf7a4121d153f1614b"
        result = self.client_get(random_link)
        self.assert_in_success_response(["The organization creation link has expired or is not valid."], result)

    @override_settings(OPEN_REALM_CREATION=False)
    def test_realm_creation_with_expired_link(self) -> None:
        generated_link = generate_realm_creation_url(by_admin=True)
        key = generated_link[-24:]
        # Manually expire the link by changing the date of creation
        obj = RealmCreationKey.objects.get(creation_key=key)
        obj.date_created = obj.date_created - timedelta(days=settings.REALM_CREATION_LINK_VALIDITY_DAYS + 1)
        obj.save()

        result = self.client_get(generated_link)
        self.assert_in_success_response(["The organization creation link has expired or is not valid."], result)

class TestCalculateFirstVisibleMessageID(ZulipTestCase):
    COMMAND_NAME = 'calculate_first_visible_message_id'

    def test_check_if_command_calls_maybe_update_first_visible_message_id(self) -> None:
        with patch('zerver.lib.message.maybe_update_first_visible_message_id') as m:
            call_command(self.COMMAND_NAME, "--realm=zulip", "--lookback-hours=30")
        m.assert_called_with(get_realm("zulip"), 30)

        with patch('zerver.lib.message.maybe_update_first_visible_message_id') as m:
            call_command(self.COMMAND_NAME, "--lookback-hours=35")
        calls = [call(realm, 35) for realm in Realm.objects.all()]
        m.has_calls(calls, any_order=True)

class TestPasswordRestEmail(ZulipTestCase):
    COMMAND_NAME = "send_password_reset_email"

    def test_if_command_sends_password_reset_email(self) -> None:
        call_command(self.COMMAND_NAME, users=self.example_email("iago"))
        from django.core.mail import outbox
        from_email = outbox[0].from_email
        self.assertIn("Zulip Account Security", from_email)
        tokenized_no_reply_email = parseaddr(from_email)[1]
        self.assertTrue(re.search(self.TOKENIZED_NOREPLY_REGEX, tokenized_no_reply_email))
        self.assertIn("reset your password", outbox[0].body)

class TestRealmReactivationEmail(ZulipTestCase):
    COMMAND_NAME = "send_realm_reactivation_email"

    def test_if_realm_not_deactivated(self) -> None:
        realm = get_realm('zulip')
        with self.assertRaisesRegex(CommandError, "The realm %s is already active." % (realm.name,)):
            call_command(self.COMMAND_NAME, "--realm=zulip")

class TestSendToEmailMirror(ZulipTestCase):
    COMMAND_NAME = "send_to_email_mirror"

    def test_sending_a_fixture(self) -> None:
        fixture_path = "zerver/tests/fixtures/email/1.txt"
        user_profile = self.example_user('hamlet')
        self.login(user_profile.email)
        self.subscribe(user_profile, "Denmark")

        call_command(self.COMMAND_NAME, "--fixture={}".format(fixture_path))
        message = most_recent_message(user_profile)

        # last message should be equal to the body of the email in 1.txt
        self.assertEqual(message.content, "Email fixture 1.txt body")

    def test_sending_a_json_fixture(self) -> None:
        fixture_path = "zerver/tests/fixtures/email/1.json"
        user_profile = self.example_user('hamlet')
        self.login(user_profile.email)
        self.subscribe(user_profile, "Denmark")

        call_command(self.COMMAND_NAME, "--fixture={}".format(fixture_path))
        message = most_recent_message(user_profile)

        # last message should be equal to the body of the email in 1.json
        self.assertEqual(message.content, "Email fixture 1.json body")

    def test_stream_option(self) -> None:
        fixture_path = "zerver/tests/fixtures/email/1.txt"
        user_profile = self.example_user('hamlet')
        self.login(user_profile.email)
        self.subscribe(user_profile, "Denmark2")

        call_command(self.COMMAND_NAME, "--fixture={}".format(fixture_path), "--stream=Denmark2")
        message = most_recent_message(user_profile)

        # last message should be equal to the body of the email in 1.txt
        self.assertEqual(message.content, "Email fixture 1.txt body")

        stream_id = get_stream("Denmark2", message.sender.realm).id
        self.assertEqual(message.recipient.type, Recipient.STREAM)
        self.assertEqual(message.recipient.type_id, stream_id)
