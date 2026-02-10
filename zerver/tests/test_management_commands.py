import hashlib
import os
import re
from datetime import timedelta
from typing import Any
from unittest import mock, skipUnless
from unittest.mock import MagicMock, call, patch
from urllib.parse import quote, quote_plus

from django.apps import apps
from django.conf import settings
from django.core.management import call_command, find_commands
from django.core.management.base import CommandError
from django.db.models import Q
from django.db.models.functions import Lower
from django.test import override_settings
from typing_extensions import override

from confirmation.models import Confirmation, generate_realm_creation_url
from zerver.actions.create_user import do_create_user
from zerver.actions.user_settings import do_change_user_setting
from zerver.lib.management import ZulipBaseCommand
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import most_recent_message, stdout_suppressed
from zerver.models import Realm, RealmAuditLog, Recipient, UserProfile
from zerver.models.realm_audit_logs import AuditLogEventType
from zerver.models.realms import get_realm
from zerver.models.streams import get_stream
from zerver.models.users import get_user_profile_by_email


class TestWarnNoEmail(ZulipTestCase):
    @override_settings(WARN_NO_EMAIL=True)
    def test_check_send_email(self) -> None:
        with self.assertRaisesRegex(CommandError, "Outgoing email not yet configured, see"):
            call_command("send_test_email", "test@example.com")


class TestZulipBaseCommand(ZulipTestCase):
    @override
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
        self, options: dict[str, Any], realm: Realm | None, **kwargs: Any
    ) -> list[UserProfile]:
        user_profiles = self.command.get_users(options, realm, **kwargs)
        return sorted(user_profiles, key=lambda x: x.email)

    def sorted_users(self, users: list[UserProfile]) -> list[UserProfile]:
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
    @override
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
                with self.subTest(management_command=command), self.assertRaises(SystemExit):
                    call_command(command, "--help")
        # zerver/management/commands/runtornado.py sets this to True;
        # we need to reset it here.  See #3685 for details.
        settings.RUNNING_INSIDE_TORNADO = False


class TestSendWebhookFixtureMessage(ZulipTestCase):
    COMMAND_NAME = "send_webhook_fixture_message"

    @override
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
                "realm_default_language": "en",
                "realm_subdomain": "custom-test",
                "import_from": "none",
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
                "realm_default_language": "en",
                "realm_subdomain": string_id,
                "import_from": "none",
            },
        )
        self.assertEqual(result.status_code, 302)
        self.assertEqual(
            f"/accounts/new/send_confirm/?email={quote(email)}&realm_name={quote_plus(realm_name)}&realm_type=10&realm_default_language=en&realm_subdomain={string_id}",
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
        key = generated_link.split("/")[-1]
        # Manually expire the link by changing the date of expiry.
        confirmation = Confirmation.objects.get(confirmation_key=key)
        assert confirmation.expiry_date is not None

        confirmation.expiry_date -= timedelta(days=settings.CAN_CREATE_REALM_LINK_VALIDITY_DAYS + 1)
        confirmation.save()

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
            rf"^testserver account security <{self.TOKENIZED_NOREPLY_REGEX}>\Z",
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
        with (
            patch("zerver.management.commands.convert_mattermost_data.do_convert_data") as m,
            patch("builtins.print") as mock_print,
        ):
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

    def test_command_to_export_full_with_consent(self) -> None:
        do_change_user_setting(
            self.example_user("iago"), "allow_private_data_export", True, acting_user=None
        )
        do_change_user_setting(
            self.example_user("desdemona"), "allow_private_data_export", True, acting_user=None
        )

        with (
            patch("zerver.management.commands.export.export_realm_wrapper") as m,
            patch("builtins.print") as mock_print,
        ):
            call_command(self.COMMAND_NAME, "-r=zulip", "--export-full-with-consent")
            m.assert_called_once_with(
                export_row=mock.ANY,
                processes=mock.ANY,
                output_dir=mock.ANY,
                percent_callback=mock.ANY,
                upload=False,
                export_as_active=None,
            )

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

        # Verify log entries not created in dry-run
        audit_logs = RealmAuditLog.objects.filter(event_type=AuditLogEventType.CUSTOM_EMAIL_SENT)
        self.assert_length(audit_logs, 0)

    def test_custom_email_duplicate_prevention_by_user(self) -> None:
        path = "zerver/tests/fixtures/email/custom_emails/email_base_headers_custom_test.md"

        # Generate email hash
        with open(path) as f:
            text = f.read()
            email_template_hash = hashlib.sha256(text.encode()).hexdigest()[0:32]

        iago = self.example_user("iago")
        prospero = self.example_user("prospero")
        othello = self.example_user("othello")

        call_command(
            self.COMMAND_NAME,
            f"--path={path}",
            f"-u={iago.delivery_email},{prospero.delivery_email}",
        )

        # Verify RealmAuditLog entries were created
        audit_logs = RealmAuditLog.objects.filter(event_type=AuditLogEventType.CUSTOM_EMAIL_SENT)
        self.assert_length(audit_logs, 2)
        self.assertEqual(email_template_hash, audit_logs[0].extra_data["email_id"])
        self.assertEqual("Test subject", audit_logs[0].extra_data["email_subject"])

        # Second send attempt - should send one email and exclude the two users that already received the email

        with patch("builtins.print") as mock_print:
            call_command(
                self.COMMAND_NAME,
                f"--path={path}",
                f"-u={iago.delivery_email},{prospero.delivery_email},{othello.delivery_email}",
            )

            self.assertEqual(
                mock_print.mock_calls[0:],
                [
                    call("Excluded 2 users who already received this email"),
                ],
            )
        new_audit_logs = RealmAuditLog.objects.filter(
            event_type=AuditLogEventType.CUSTOM_EMAIL_SENT
        )
        self.assert_length(new_audit_logs, 3)
        self.assertEqual(email_template_hash, new_audit_logs[0].extra_data["email_id"])
        self.assertEqual("Test subject", audit_logs[0].extra_data["email_subject"])

        othello_audit_log = RealmAuditLog.objects.filter(
            event_type=AuditLogEventType.CUSTOM_EMAIL_SENT, modified_user=othello
        )
        self.assert_length(othello_audit_log, 1)

    def test_custom_marketing_email_duplicate_prevention_by_email(self) -> None:
        path = "zerver/tests/fixtures/email/custom_emails/email_base_headers_custom_test.md"

        # Ensure that marketing includes two users with two different realms and different roles
        realm1 = get_realm("lear")
        realm2 = get_realm("zephyr")

        shared_email = "DUPLICATE@example.com"

        admin_user = do_create_user(
            email=shared_email,
            password="password",
            realm=realm1,
            full_name="Admin User",
            role=UserProfile.ROLE_REALM_ADMINISTRATOR,
            acting_user=None,
            tos_version=settings.TERMS_OF_SERVICE_VERSION,
        )
        admin_user.save()

        owner_user = do_create_user(
            email=shared_email.lower(),
            password="password",
            realm=realm2,
            full_name="Owner User",
            role=UserProfile.ROLE_REALM_OWNER,
            acting_user=None,
            tos_version=settings.TERMS_OF_SERVICE_VERSION,
        )

        owner_user.save()

        # Get the total number of marketing emails to be sent
        users = UserProfile.objects.filter(
            is_active=True,
            is_bot=False,
            is_mirror_dummy=False,
            realm__deactivated=False,
            enable_marketing_emails=True,
        ).filter(
            Q(long_term_idle=False)
            | Q(
                role__in=[
                    UserProfile.ROLE_REALM_OWNER,
                    UserProfile.ROLE_REALM_ADMINISTRATOR,
                ]
            )
        )

        users = users.annotate(lower_email=Lower("delivery_email")).distinct("lower_email")

        users_count = users.count()
        users_emails = users.values_list("lower_email", flat=True)

        # Get the email hash
        with open(path) as f:
            text = f.read()
            email_template_hash = hashlib.sha256(text.encode()).hexdigest()[0:32]

        call_command(
            self.COMMAND_NAME,
            f"--path={path}",
            "--marketing",
        )

        # Verify RealmAuditLog entries were created
        audit_logs = RealmAuditLog.objects.filter(event_type=AuditLogEventType.CUSTOM_EMAIL_SENT)
        self.assert_length(audit_logs, users_count)

        # Verify the email_id
        self.assertEqual(email_template_hash, audit_logs[0].extra_data["email_id"])

        # Verify modified_user email
        modified_users_email = audit_logs.annotate(
            lower_email=Lower("modified_user__delivery_email")
        ).values_list("lower_email", flat=True)
        self.assertEqual(set(users_emails), set(modified_users_email))

        # Verify only one email was sent (to one of the two users created before)
        audit_logs_duplicate = RealmAuditLog.objects.filter(
            event_type=AuditLogEventType.CUSTOM_EMAIL_SENT,
            modified_user__in=[admin_user, owner_user],
        )
        self.assert_length(audit_logs_duplicate, 1)

        # Verify the email addresses match (case-insensitive)
        assert audit_logs_duplicate[0].modified_user is not None
        self.assertEqual(
            audit_logs_duplicate[0].modified_user.delivery_email.lower(),
            shared_email.lower(),
        )

        # Verify the second call prevents sending duplication emails
        with patch("builtins.print") as mock_print:
            call_command(
                self.COMMAND_NAME,
                f"--path={path}",
                "--marketing",
            )

            self.assertEqual(
                mock_print.mock_calls[0:],
                [
                    call(f"Excluded {users_count} users who already received this email"),
                ],
            )

        # Verify no additional audit logs were created for these users
        audit_logs_after_second_send = RealmAuditLog.objects.filter(
            event_type=AuditLogEventType.CUSTOM_EMAIL_SENT,
            modified_user__in=[admin_user, owner_user],
        )
        self.assert_length(audit_logs_after_second_send, 1)  # Still only 1

    def test_email_sending_failure_does_not_create_audit_log(self) -> None:
        """Test that audit log entries are not created when email sending fails"""
        path = "zerver/tests/fixtures/email/custom_emails/email_base_headers_custom_test.md"
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")

        # Verify no audit logs exist initially
        initial_audit_count = RealmAuditLog.objects.filter(
            event_type=AuditLogEventType.CUSTOM_EMAIL_SENT
        ).count()

        # Mock email sending to raise an exception
        with patch("zerver.lib.send_email.send_immediate_email") as mock_send:
            # Configure mock to raise EmailNotDeliveredError
            from zerver.lib.send_email import EmailNotDeliveredError

            mock_send.side_effect = EmailNotDeliveredError("SMTP connection failed")

            # Attempt to send emails (should fail silently due to suppress() in send_one_email)
            call_command(
                self.COMMAND_NAME,
                f"--path={path}",
                "-r=zulip",
                f"-u={hamlet.delivery_email},{cordelia.delivery_email}",
            )

            # Verify that email sending was attempted
            self.assertEqual(mock_send.call_count, 2)  # Once for each user

        # Verify no audit log entries were created
        final_audit_count = RealmAuditLog.objects.filter(
            event_type=AuditLogEventType.CUSTOM_EMAIL_SENT
        ).count()
        self.assertEqual(final_audit_count, initial_audit_count)


class TestSendZulipUpdateAnnouncements(ZulipTestCase):
    COMMAND_NAME = "send_zulip_update_announcements"

    def test_reset_level(self) -> None:
        realm = get_realm("zulip")
        realm.zulip_update_announcements_level = 9
        realm.save()

        call_command(self.COMMAND_NAME, "--reset-level=5")

        realm.refresh_from_db()
        self.assertEqual(realm.zulip_update_announcements_level, 5)


class TestUserChangeNotifications(ZulipTestCase):
    def test_bulk_change_user_name_sends_notifications(self) -> None:
        hamlet = self.example_user("hamlet")
        bot = self.example_user("default_bot")
        realm = hamlet.realm

        # Count bot messages before changes
        from zerver.models import Message

        bot_messages_before = Message.objects.filter(
            realm_id=realm.id, recipient__type_id=bot.id
        ).count()

        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv") as f:
            f.write(f"{hamlet.delivery_email},New Hamlet Name\n")
            f.write(f"{bot.delivery_email},New Bot Name\n")
            data_file = f.name

        try:
            # Run the bulk_change_user_name command
            with stdout_suppressed():
                call_command("bulk_change_user_name", data_file, f"--realm={realm.string_id}")

            # Verify the name was changed
            hamlet.refresh_from_db()
            self.assertEqual(hamlet.full_name, "New Hamlet Name")

            # Verify a notification was sent (acting_user=None means system change)
            message = most_recent_message(hamlet)
            self.assertIn(
                "The following changes have been made to your account.",
                message.content,
            )
            self.assertIn("**Old full name:** King Hamlet", message.content)
            self.assertIn("**New full name:** New Hamlet Name", message.content)

            # Verify bot's name was changed
            bot.refresh_from_db()
            self.assertEqual(bot.full_name, "New Bot Name")

            # Verify bot did NOT receive a notification
            bot_messages_after = Message.objects.filter(
                realm_id=realm.id, recipient__type_id=bot.id
            ).count()
            self.assertEqual(bot_messages_before, bot_messages_after)
        finally:
            os.unlink(data_file)

    def test_change_user_role_sends_notifications(self) -> None:
        hamlet = self.example_user("hamlet")
        realm = hamlet.realm

        # Hamlet starts as a member
        self.assertEqual(hamlet.role, UserProfile.ROLE_MEMBER)

        # Change hamlet's role to moderator via management command
        with stdout_suppressed():
            call_command(
                "change_user_role", hamlet.delivery_email, "moderator", f"--realm={realm.string_id}"
            )

        # Verify the role was changed
        hamlet.refresh_from_db()
        self.assertEqual(hamlet.role, UserProfile.ROLE_MODERATOR)

        # Verify a notification was sent (acting_user=None means system change)
        message = most_recent_message(hamlet)
        self.assertIn("The following changes have been made to your account", message.content)
        self.assertIn("**Old role:** Member", message.content)
        self.assertIn("**New role:** Moderator", message.content)

        # Change bot's role to moderator via management command
        bot = self.example_user("default_bot")

        # Count bot messages before changes
        from zerver.models import Message

        bot_messages_before = Message.objects.filter(
            realm_id=realm.id, recipient__type_id=bot.id
        ).count()

        with stdout_suppressed():
            call_command(
                "change_user_role", bot.delivery_email, "moderator", f"--realm={realm.string_id}"
            )

        # Verify bot's role was changed
        bot.refresh_from_db()
        self.assertEqual(bot.role, UserProfile.ROLE_MODERATOR)

        # Verify bot did NOT receive a notification
        bot_messages_after = Message.objects.filter(
            realm_id=realm.id, recipient__type_id=bot.id
        ).count()
        self.assertEqual(bot_messages_before, bot_messages_after)
