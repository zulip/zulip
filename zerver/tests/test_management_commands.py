import os
import re
import urllib
from datetime import timedelta
from typing import Any, Dict, List, Optional
from unittest import mock, skipUnless
from unittest.mock import MagicMock, call, patch

from django.apps import apps
from django.conf import settings
from django.core.management import call_command, find_commands
from django.core.management.base import CommandError
from django.test import override_settings
from django.utils.timezone import now as timezone_now

from confirmation.models import RealmCreationKey, generate_realm_creation_url
from zerver.actions.create_user import do_create_user
from zerver.actions.reactions import do_add_reaction
from zerver.lib.management import ZulipBaseCommand, check_config
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import most_recent_message, stdout_suppressed
from zerver.models import (
    Message,
    Reaction,
    Realm,
    Recipient,
    UserProfile,
    get_realm,
    get_stream,
    get_user_profile_by_email,
)


class TestCheckConfig(ZulipTestCase):
    def test_check_config(self) -> None:
        check_config()
        with self.settings(REQUIRED_SETTINGS=[("asdf", "not asdf")]):
            with self.assertRaisesRegex(
                CommandError, "Error: You must set asdf in /etc/zulip/settings.py."
            ):
                check_config()

    @override_settings(WARN_NO_EMAIL=True)
    def test_check_send_email(self) -> None:
        with self.assertRaisesRegex(CommandError, "Outgoing email not yet configured, see"):
            call_command("send_test_email", "test@example.com")


class TestZulipBaseCommand(ZulipTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.zulip_realm = get_realm("zulip")
        self.command = ZulipBaseCommand()

    def test_get_client(self) -> None:
        self.assertEqual(self.command.get_client().name, "ZulipServer")

    def test_get_realm(self) -> None:
        self.assertEqual(self.command.get_realm(dict(realm_id="zulip")), self.zulip_realm)
        self.assertEqual(self.command.get_realm(dict(realm_id=None)), None)
        self.assertEqual(
            self.command.get_realm(dict(realm_id=str(self.zulip_realm.id))), self.zulip_realm
        )
        with self.assertRaisesRegex(CommandError, "There is no realm with id"):
            self.command.get_realm(dict(realm_id="17"))
        with self.assertRaisesRegex(CommandError, "There is no realm with id"):
            self.command.get_realm(dict(realm_id="mit"))

    def test_get_user(self) -> None:
        mit_realm = get_realm("zephyr")
        user_profile = self.example_user("hamlet")
        email = user_profile.delivery_email

        self.assertEqual(self.command.get_user(email, self.zulip_realm), user_profile)
        self.assertEqual(self.command.get_user(email, None), user_profile)

        error_message = f"The realm '{mit_realm}' does not contain a user with email"
        with self.assertRaisesRegex(CommandError, error_message):
            self.command.get_user(email, mit_realm)

        with self.assertRaisesRegex(CommandError, "server does not contain a user with email"):
            self.command.get_user("invalid_email@example.com", None)

        do_create_user(email, "password", mit_realm, "full_name", acting_user=None)

        with self.assertRaisesRegex(CommandError, "server contains multiple users with that email"):
            self.command.get_user(email, None)

    def test_get_user_profile_by_email(self) -> None:
        user_profile = self.example_user("hamlet")
        email = user_profile.delivery_email

        self.assertEqual(get_user_profile_by_email(email), user_profile)

    def get_users_sorted(
        self, options: Dict[str, Any], realm: Optional[Realm], **kwargs: Any
    ) -> List[UserProfile]:
        user_profiles = self.command.get_users(options, realm, **kwargs)
        return sorted(user_profiles, key=lambda x: x.email)

    def sorted_users(self, users: List[UserProfile]) -> List[UserProfile]:
        return sorted(users, key=lambda x: x.email)

    def test_get_users(self) -> None:
        expected_user_profiles = self.sorted_users(
            [
                self.example_user("hamlet"),
                self.example_user("iago"),
            ]
        )

        user_emails = ",".join(u.delivery_email for u in expected_user_profiles)
        user_profiles = self.get_users_sorted(dict(users=user_emails), self.zulip_realm)
        self.assertEqual(user_profiles, expected_user_profiles)
        user_profiles = self.get_users_sorted(dict(users=user_emails), None)
        self.assertEqual(user_profiles, expected_user_profiles)

        expected_user_profiles = self.sorted_users(
            [
                self.mit_user("sipbtest"),
                self.example_user("iago"),
            ]
        )
        user_emails = ",".join(u.delivery_email for u in expected_user_profiles)
        user_profiles = self.get_users_sorted(dict(users=user_emails), None)
        self.assertEqual(user_profiles, expected_user_profiles)
        error_message = f"The realm '{self.zulip_realm}' does not contain a user with email"
        with self.assertRaisesRegex(CommandError, error_message):
            self.command.get_users(dict(users=user_emails), self.zulip_realm)

        self.assertEqual(
            list(self.command.get_users(dict(users=self.example_email("iago")), self.zulip_realm)),
            [self.example_user("iago")],
        )

        self.assertEqual(list(self.command.get_users(dict(users=None), None)), [])

    def test_get_users_with_all_users_argument_enabled(self) -> None:
        expected_user_profiles = self.sorted_users(
            [
                self.example_user("hamlet"),
                self.example_user("iago"),
            ]
        )
        user_emails = ",".join(u.delivery_email for u in expected_user_profiles)
        user_profiles = self.get_users_sorted(
            dict(users=user_emails, all_users=False), self.zulip_realm
        )
        self.assertEqual(user_profiles, expected_user_profiles)
        error_message = "You can't use both -u/--users and -a/--all-users."
        with self.assertRaisesRegex(CommandError, error_message):
            self.command.get_users(dict(users=user_emails, all_users=True), None)

        # Test the default mode excluding bots and deactivated users
        expected_user_profiles = sorted(
            UserProfile.objects.filter(realm=self.zulip_realm, is_active=True, is_bot=False),
            key=lambda x: x.email,
        )
        user_profiles = self.get_users_sorted(
            dict(users=None, all_users=True), self.zulip_realm, is_bot=False
        )
        self.assertEqual(user_profiles, expected_user_profiles)

        # Test the default mode excluding bots and deactivated users
        expected_user_profiles = sorted(
            UserProfile.objects.filter(realm=self.zulip_realm, is_active=True),
            key=lambda x: x.email,
        )
        user_profiles = self.get_users_sorted(dict(users=None, all_users=True), self.zulip_realm)
        self.assertEqual(user_profiles, expected_user_profiles)

        # Test include_deactivated
        expected_user_profiles = sorted(
            UserProfile.objects.filter(realm=self.zulip_realm, is_bot=False), key=lambda x: x.email
        )
        user_profiles = self.get_users_sorted(
            dict(users=None, all_users=True),
            self.zulip_realm,
            is_bot=False,
            include_deactivated=True,
        )
        self.assertEqual(user_profiles, expected_user_profiles)

        error_message = "You have to pass either -u/--users or -a/--all-users."
        with self.assertRaisesRegex(CommandError, error_message):
            self.command.get_users(dict(users=None, all_users=False), None)

        error_message = "The --all-users option requires a realm; please pass --realm."
        with self.assertRaisesRegex(CommandError, error_message):
            self.command.get_users(dict(users=None, all_users=True), None)

    def test_get_non_bot_users(self) -> None:
        expected_user_profiles = sorted(
            UserProfile.objects.filter(realm=self.zulip_realm, is_bot=False), key=lambda x: x.email
        )
        user_profiles = self.get_users_sorted(
            dict(users=None, all_users=True), self.zulip_realm, is_bot=False
        )
        self.assertEqual(user_profiles, expected_user_profiles)


class TestCommandsCanStart(ZulipTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.commands = [
            command
            for app_config in apps.get_app_configs()
            if os.path.dirname(os.path.realpath(app_config.path)) == settings.DEPLOY_ROOT
            for command in find_commands(os.path.join(app_config.path, "management"))
        ]
        assert self.commands

    def test_management_commands_show_help(self) -> None:
        with stdout_suppressed():
            for command in self.commands:
                with self.subTest(management_command=command):
                    with self.assertRaises(SystemExit):
                        call_command(command, "--help")
        # zerver/management/commands/runtornado.py sets this to True;
        # we need to reset it here.  See #3685 for details.
        settings.RUNNING_INSIDE_TORNADO = False


class TestSendWebhookFixtureMessage(ZulipTestCase):
    COMMAND_NAME = "send_webhook_fixture_message"

    def setUp(self) -> None:
        super().setUp()
        self.fixture_path = os.path.join("some", "fake", "path.json")
        self.url = "/some/url/with/hook"

    @patch("zerver.management.commands.send_webhook_fixture_message.Command.print_help")
    def test_check_if_command_exits_when_fixture_param_is_empty(
        self, print_help_mock: MagicMock
    ) -> None:
        with self.assertRaises(CommandError):
            call_command(self.COMMAND_NAME, url=self.url)

        print_help_mock.assert_any_call("./manage.py", self.COMMAND_NAME)

    @patch("zerver.management.commands.send_webhook_fixture_message.Command.print_help")
    def test_check_if_command_exits_when_url_param_is_empty(
        self, print_help_mock: MagicMock
    ) -> None:
        with self.assertRaises(CommandError):
            call_command(self.COMMAND_NAME, fixture=self.fixture_path)

        print_help_mock.assert_any_call("./manage.py", self.COMMAND_NAME)

    @patch("zerver.management.commands.send_webhook_fixture_message.os.path.exists")
    def test_check_if_command_exits_when_fixture_path_does_not_exist(
        self, os_path_exists_mock: MagicMock
    ) -> None:
        os_path_exists_mock.return_value = False

        with self.assertRaises(CommandError):
            call_command(self.COMMAND_NAME, fixture=self.fixture_path, url=self.url)

        os_path_exists_mock.assert_any_call(os.path.join(settings.DEPLOY_ROOT, self.fixture_path))

    @patch("zerver.management.commands.send_webhook_fixture_message.os.path.exists")
    @patch("zerver.management.commands.send_webhook_fixture_message.Client")
    @patch("zerver.management.commands.send_webhook_fixture_message.orjson")
    @patch("zerver.management.commands.send_webhook_fixture_message.open", create=True)
    def test_check_if_command_post_request_to_url_with_fixture(
        self,
        open_mock: MagicMock,
        orjson_mock: MagicMock,
        client_mock: MagicMock,
        os_path_exists_mock: MagicMock,
    ) -> None:
        orjson_mock.loads.return_value = {}
        orjson_mock.dumps.return_value = b"{}"
        os_path_exists_mock.return_value = True

        client = client_mock()

        with self.assertRaises(CommandError):
            call_command(self.COMMAND_NAME, fixture=self.fixture_path, url=self.url)
        self.assertTrue(orjson_mock.dumps.called)
        self.assertTrue(orjson_mock.loads.called)
        self.assertTrue(open_mock.called)
        client.post.assert_called_once_with(
            self.url, b"{}", content_type="application/json", HTTP_HOST="zulip.testserver"
        )


class TestGenerateRealmCreationLink(ZulipTestCase):
    COMMAND_NAME = "generate_realm_creation_link"

    @override_settings(OPEN_REALM_CREATION=False)
    def test_generate_link_and_create_realm(self) -> None:
        email = "user1@test.com"
        generated_link = generate_realm_creation_url(by_admin=True)

        # Get realm creation page
        result = self.client_get(generated_link)
        self.assert_in_success_response(["Create a new Zulip organization"], result)

        # Enter email
        with self.assertRaises(Realm.DoesNotExist):
            get_realm("test")
        result = self.client_post(
            generated_link,
            {
                "email": email,
                "realm_name": "Zulip test",
                "realm_type": Realm.ORG_TYPES["business"]["id"],
                "realm_subdomain": "custom-test",
            },
        )
        self.assertEqual(result.status_code, 302)
        self.assertTrue(re.search(r"/accounts/do_confirm/\w+$", result["Location"]))

        # Bypass sending mail for confirmation, go straight to creation form
        result = self.client_get(result["Location"])
        self.assert_in_response('action="/realm/register/"', result)

        # Original link is now dead
        result = self.client_get(generated_link)
        self.assert_in_success_response(["Organization creation link expired or invalid"], result)

    @override_settings(OPEN_REALM_CREATION=False)
    def test_generate_link_confirm_email(self) -> None:
        email = "user1@test.com"
        realm_name = "Zulip test"
        string_id = "custom-test"
        generated_link = generate_realm_creation_url(by_admin=False)

        result = self.client_post(
            generated_link,
            {
                "email": email,
                "realm_name": realm_name,
                "realm_type": Realm.ORG_TYPES["business"]["id"],
                "realm_subdomain": string_id,
            },
        )
        self.assertEqual(result.status_code, 302)
        self.assertEqual(
            f"/accounts/new/send_confirm/?email={urllib.parse.quote(email)}&realm_name={urllib.parse.quote_plus(realm_name)}&realm_type=10&realm_subdomain={string_id}",
            result["Location"],
        )
        result = self.client_get(result["Location"])
        self.assert_in_response("check your email", result)

        # Original link is now dead
        result = self.client_get(generated_link)
        self.assert_in_success_response(["Organization creation link expired or invalid"], result)

    @override_settings(OPEN_REALM_CREATION=False)
    def test_realm_creation_with_random_link(self) -> None:
        # Realm creation attempt with an invalid link should fail
        random_link = "/new/5e89081eb13984e0f3b130bf7a4121d153f1614b"
        result = self.client_get(random_link)
        self.assert_in_success_response(["Organization creation link expired or invalid"], result)

    @override_settings(OPEN_REALM_CREATION=False)
    def test_realm_creation_with_expired_link(self) -> None:
        generated_link = generate_realm_creation_url(by_admin=True)
        key = generated_link[-24:]
        # Manually expire the link by changing the date of creation
        obj = RealmCreationKey.objects.get(creation_key=key)
        obj.date_created = obj.date_created - timedelta(
            days=settings.REALM_CREATION_LINK_VALIDITY_DAYS + 1
        )
        obj.save()

        result = self.client_get(generated_link)
        self.assert_in_success_response(["Organization creation link expired or invalid"], result)


@skipUnless(settings.ZILENCER_ENABLED, "requires zilencer")
class TestCalculateFirstVisibleMessageID(ZulipTestCase):
    COMMAND_NAME = "calculate_first_visible_message_id"

    def test_check_if_command_calls_maybe_update_first_visible_message_id(self) -> None:
        func_name = "zilencer.management.commands.calculate_first_visible_message_id.maybe_update_first_visible_message_id"
        with patch(func_name) as m:
            call_command(self.COMMAND_NAME, "--realm=zulip", "--lookback-hours=30")
        m.assert_called_with(get_realm("zulip"), 30)

        with patch(func_name) as m:
            call_command(self.COMMAND_NAME, "--lookback-hours=35")
        calls = [call(realm, 35) for realm in Realm.objects.all()]
        m.assert_has_calls(calls, any_order=True)


class TestPasswordRestEmail(ZulipTestCase):
    COMMAND_NAME = "send_password_reset_email"

    def test_if_command_sends_password_reset_email(self) -> None:
        call_command(self.COMMAND_NAME, users=self.example_email("iago"))
        from django.core.mail import outbox

        self.assertEqual(self.email_envelope_from(outbox[0]), settings.NOREPLY_EMAIL_ADDRESS)
        self.assertRegex(
            self.email_display_from(outbox[0]),
            rf"^Zulip Account Security <{self.TOKENIZED_NOREPLY_REGEX}>\Z",
        )
        self.assertIn("reset your password", outbox[0].body)


class TestRealmReactivationEmail(ZulipTestCase):
    COMMAND_NAME = "send_realm_reactivation_email"

    def test_if_realm_not_deactivated(self) -> None:
        realm = get_realm("zulip")
        with self.assertRaisesRegex(CommandError, f"The realm {realm.name} is already active."):
            call_command(self.COMMAND_NAME, "--realm=zulip")


class TestSendToEmailMirror(ZulipTestCase):
    COMMAND_NAME = "send_to_email_mirror"

    def test_sending_a_fixture(self) -> None:
        fixture_path = "zerver/tests/fixtures/email/1.txt"
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)
        self.subscribe(user_profile, "Denmark")

        with self.assertLogs("zerver.lib.email_mirror", level="INFO") as info_log:
            call_command(self.COMMAND_NAME, f"--fixture={fixture_path}")
        self.assertEqual(
            info_log.output,
            ["INFO:zerver.lib.email_mirror:Successfully processed email to Denmark (zulip)"],
        )
        message = most_recent_message(user_profile)

        # last message should be equal to the body of the email in 1.txt
        self.assertEqual(message.content, "Email fixture 1.txt body")

    def test_sending_a_json_fixture(self) -> None:
        fixture_path = "zerver/tests/fixtures/email/1.json"
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)
        self.subscribe(user_profile, "Denmark")

        with self.assertLogs("zerver.lib.email_mirror", level="INFO") as info_log:
            call_command(self.COMMAND_NAME, f"--fixture={fixture_path}")
        self.assertEqual(
            info_log.output,
            ["INFO:zerver.lib.email_mirror:Successfully processed email to Denmark (zulip)"],
        )
        message = most_recent_message(user_profile)

        # last message should be equal to the body of the email in 1.json
        self.assertEqual(message.content, "Email fixture 1.json body")

    def test_stream_option(self) -> None:
        fixture_path = "zerver/tests/fixtures/email/1.txt"
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)
        self.subscribe(user_profile, "Denmark2")

        with self.assertLogs("zerver.lib.email_mirror", level="INFO") as info_log:
            call_command(self.COMMAND_NAME, f"--fixture={fixture_path}", "--stream=Denmark2")
        self.assertEqual(
            info_log.output,
            ["INFO:zerver.lib.email_mirror:Successfully processed email to Denmark2 (zulip)"],
        )
        message = most_recent_message(user_profile)

        # last message should be equal to the body of the email in 1.txt
        self.assertEqual(message.content, "Email fixture 1.txt body")

        stream_id = get_stream("Denmark2", get_realm("zulip")).id
        self.assertEqual(message.recipient.type, Recipient.STREAM)
        self.assertEqual(message.recipient.type_id, stream_id)


class TestConvertMattermostData(ZulipTestCase):
    COMMAND_NAME = "convert_mattermost_data"

    def test_if_command_calls_do_convert_data(self) -> None:
        with patch(
            "zerver.management.commands.convert_mattermost_data.do_convert_data"
        ) as m, patch("builtins.print") as mock_print:
            mm_fixtures = self.fixture_file_name("", "mattermost_fixtures")
            output_dir = self.make_import_output_dir("mattermost")
            call_command(self.COMMAND_NAME, mm_fixtures, f"--output={output_dir}")

        m.assert_called_with(
            masking_content=False,
            mattermost_data_dir=os.path.realpath(mm_fixtures),
            output_dir=os.path.realpath(output_dir),
        )
        self.assertEqual(mock_print.mock_calls, [call("Converting data ...")])


@skipUnless(settings.ZILENCER_ENABLED, "requires zilencer")
class TestInvoicePlans(ZulipTestCase):
    COMMAND_NAME = "invoice_plans"

    def test_if_command_calls_invoice_plans_as_needed(self) -> None:
        with patch("zilencer.management.commands.invoice_plans.invoice_plans_as_needed") as m:
            call_command(self.COMMAND_NAME)

        m.assert_called_once()


@skipUnless(settings.ZILENCER_ENABLED, "requires zilencer")
class TestDowngradeSmallRealmsBehindOnPayments(ZulipTestCase):
    COMMAND_NAME = "downgrade_small_realms_behind_on_payments"

    def test_if_command_calls_downgrade_small_realms_behind_on_payments_as_needed(self) -> None:
        with patch(
            "zilencer.management.commands.downgrade_small_realms_behind_on_payments.downgrade_small_realms_behind_on_payments_as_needed"
        ) as m:
            call_command(self.COMMAND_NAME)

        m.assert_called_once()


class TestExport(ZulipTestCase):
    COMMAND_NAME = "export"

    def test_command_with_consented_message_id(self) -> None:
        realm = get_realm("zulip")
        self.send_stream_message(
            self.example_user("othello"),
            "Verona",
            topic_name="Export",
            content="Outbox emoji for export",
        )
        message = Message.objects.last()
        assert message is not None
        do_add_reaction(
            self.example_user("iago"), message, "outbox", "1f4e4", Reaction.UNICODE_EMOJI
        )
        do_add_reaction(
            self.example_user("hamlet"), message, "outbox", "1f4e4", Reaction.UNICODE_EMOJI
        )

        with patch("zerver.management.commands.export.export_realm_wrapper") as m, patch(
            "builtins.print"
        ) as mock_print, patch("builtins.input", return_value="y") as mock_input:
            call_command(self.COMMAND_NAME, "-r=zulip", f"--consent-message-id={message.id}")
            m.assert_called_once_with(
                realm=realm,
                public_only=False,
                consent_message_id=message.id,
                threads=mock.ANY,
                output_dir=mock.ANY,
                percent_callback=mock.ANY,
                upload=False,
                export_as_active=None,
            )
            mock_input.assert_called_once_with("Continue? [y/N] ")

        self.assertEqual(
            mock_print.mock_calls,
            [
                call("\033[94mExporting realm\033[0m: zulip"),
                call("\n\033[94mMessage content:\033[0m\nOutbox emoji for export\n"),
                call(
                    "\033[94mNumber of users that reacted outbox:\033[0m 2 / 9 total non-guest users\n"
                ),
            ],
        )

        with self.assertRaisesRegex(CommandError, "Message with given ID does not"), patch(
            "builtins.print"
        ) as mock_print:
            call_command(self.COMMAND_NAME, "-r=zulip", "--consent-message-id=123456")
        self.assertEqual(
            mock_print.mock_calls,
            [
                call("\033[94mExporting realm\033[0m: zulip"),
            ],
        )

        message.last_edit_time = timezone_now()
        message.save()
        with self.assertRaisesRegex(CommandError, "Message was edited. Aborting..."), patch(
            "builtins.print"
        ) as mock_print:
            call_command(self.COMMAND_NAME, "-r=zulip", f"--consent-message-id={message.id}")
        self.assertEqual(
            mock_print.mock_calls,
            [
                call("\033[94mExporting realm\033[0m: zulip"),
            ],
        )

        message.last_edit_time = None
        message.save()
        do_add_reaction(
            self.mit_user("sipbtest"), message, "outbox", "1f4e4", Reaction.UNICODE_EMOJI
        )
        with self.assertRaisesRegex(
            CommandError, "Users from a different realm reacted to message. Aborting..."
        ), patch("builtins.print") as mock_print:
            call_command(self.COMMAND_NAME, "-r=zulip", f"--consent-message-id={message.id}")

        self.assertEqual(
            mock_print.mock_calls,
            [
                call("\033[94mExporting realm\033[0m: zulip"),
            ],
        )


class TestSendCustomEmail(ZulipTestCase):
    COMMAND_NAME = "send_custom_email"

    def test_custom_email_with_dry_run(self) -> None:
        path = "templates/zerver/tests/markdown/test_nested_code_blocks.md"
        user = self.example_user("hamlet")
        other_user = self.example_user("cordelia")

        with patch("builtins.print") as mock_print:
            call_command(
                self.COMMAND_NAME,
                "-r=zulip",
                f"--path={path}",
                f"-u={user.delivery_email}",
                "--subject=Test email",
                "--from-name=zulip@zulip.example.com",
                "--dry-run",
            )
            self.assertEqual(
                mock_print.mock_calls[1:],
                [
                    call("Would send the above email to:"),
                    call("  hamlet@zulip.com (zulip)"),
                ],
            )

        with patch("builtins.print") as mock_print:
            call_command(
                self.COMMAND_NAME,
                "-r=zulip",
                f"--path={path}",
                f"-u={user.delivery_email},{other_user.delivery_email}",
                "--subject=Test email",
                "--from-name=zulip@zulip.example.com",
                "--dry-run",
            )
            self.assertEqual(
                mock_print.mock_calls[1:],
                [
                    call("Would send the above email to:"),
                    call("  cordelia@zulip.com (zulip)"),
                    call("  hamlet@zulip.com (zulip)"),
                ],
            )
