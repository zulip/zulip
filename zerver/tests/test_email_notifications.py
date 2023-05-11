import random
import re
from datetime import datetime, timedelta, timezone
from email.headerregistry import Address
from typing import List, Optional, Sequence, Union
from unittest import mock
from unittest.mock import patch

import ldap
import lxml.html
import orjson
from django.conf import settings
from django.core import mail
from django.core.mail.message import EmailMultiAlternatives
from django.test import override_settings
from django.utils.timezone import now as timezone_now
from django_auth_ldap.config import LDAPSearch
from django_stubs_ext import StrPromise

from zerver.actions.user_settings import do_change_user_setting
from zerver.actions.users import do_change_user_role
from zerver.lib.email_notifications import (
    enqueue_welcome_emails,
    fix_emojis,
    fix_spoilers_in_html,
    followup_day2_email_delay,
    handle_missedmessage_emails,
    relative_to_full_url,
)
from zerver.lib.send_email import FromAddress, deliver_scheduled_emails, send_custom_email
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.user_groups import create_user_group
from zerver.models import ScheduledEmail, UserMessage, UserProfile, get_realm, get_stream


class TestCustomEmails(ZulipTestCase):
    def test_send_custom_email_argument(self) -> None:
        hamlet = self.example_user("hamlet")
        email_subject = "subject_test"
        reply_to = "reply_to_test"
        from_name = "from_name_test"
        markdown_template_path = "templates/zerver/emails/email_base_default.source.html"
        send_custom_email(
            [hamlet],
            options={
                "markdown_template_path": markdown_template_path,
                "reply_to": reply_to,
                "subject": email_subject,
                "from_name": from_name,
                "dry_run": False,
            },
        )
        self.assert_length(mail.outbox, 1)
        msg = mail.outbox[0]
        self.assertEqual(msg.subject, email_subject)
        self.assert_length(msg.reply_to, 1)
        self.assertEqual(msg.reply_to[0], reply_to)
        self.assertNotIn("{% block content %}", msg.body)

    def test_send_custom_email_remote_server(self) -> None:
        email_subject = "subject_test"
        reply_to = "reply_to_test"
        from_name = "from_name_test"
        contact_email = "zulip-admin@example.com"
        markdown_template_path = "templates/corporate/policies/index.md"
        send_custom_email(
            [],
            target_emails=[contact_email],
            options={
                "markdown_template_path": markdown_template_path,
                "reply_to": reply_to,
                "subject": email_subject,
                "from_name": from_name,
                "dry_run": False,
            },
        )
        self.assert_length(mail.outbox, 1)
        msg = mail.outbox[0]
        self.assertEqual(msg.subject, email_subject)
        self.assertEqual(msg.to, [contact_email])
        self.assert_length(msg.reply_to, 1)
        self.assertEqual(msg.reply_to[0], reply_to)
        self.assertNotIn("{% block content %}", msg.body)
        # Verify that the HTML version contains the footer.
        self.assertIn(
            "You are receiving this email to update you about important changes to Zulip",
            str(msg.message()),
        )

    def test_send_custom_email_headers(self) -> None:
        hamlet = self.example_user("hamlet")
        markdown_template_path = (
            "zerver/tests/fixtures/email/custom_emails/email_base_headers_test.source.html"
        )
        send_custom_email(
            [hamlet],
            options={
                "markdown_template_path": markdown_template_path,
                "dry_run": False,
            },
        )
        self.assert_length(mail.outbox, 1)
        msg = mail.outbox[0]
        self.assertEqual(msg.subject, "Test subject")
        self.assertFalse(msg.reply_to)
        self.assertEqual("Test body", msg.body)

    def test_send_custom_email_no_argument(self) -> None:
        hamlet = self.example_user("hamlet")
        from_name = "from_name_test"
        email_subject = "subject_test"
        markdown_template_path = "zerver/tests/fixtures/email/custom_emails/email_base_headers_no_headers_test.source.html"

        from zerver.lib.send_email import NoEmailArgumentError

        self.assertRaises(
            NoEmailArgumentError,
            send_custom_email,
            [hamlet],
            options={
                "markdown_template_path": markdown_template_path,
                "from_name": from_name,
                "dry_run": False,
            },
        )

        self.assertRaises(
            NoEmailArgumentError,
            send_custom_email,
            [hamlet],
            options={
                "markdown_template_path": markdown_template_path,
                "subject": email_subject,
                "dry_run": False,
            },
        )

    def test_send_custom_email_doubled_arguments(self) -> None:
        hamlet = self.example_user("hamlet")
        from_name = "from_name_test"
        email_subject = "subject_test"
        markdown_template_path = (
            "zerver/tests/fixtures/email/custom_emails/email_base_headers_test.source.html"
        )

        from zerver.lib.send_email import DoubledEmailArgumentError

        self.assertRaises(
            DoubledEmailArgumentError,
            send_custom_email,
            [hamlet],
            options={
                "markdown_template_path": markdown_template_path,
                "subject": email_subject,
                "dry_run": False,
            },
        )

        self.assertRaises(
            DoubledEmailArgumentError,
            send_custom_email,
            [hamlet],
            options={
                "markdown_template_path": markdown_template_path,
                "from_name": from_name,
                "dry_run": False,
            },
        )

    def test_send_custom_email_admins_only(self) -> None:
        admin_user = self.example_user("hamlet")
        do_change_user_role(admin_user, UserProfile.ROLE_REALM_ADMINISTRATOR, acting_user=None)

        non_admin_user = self.example_user("cordelia")

        markdown_template_path = (
            "zerver/tests/fixtures/email/custom_emails/email_base_headers_test.source.html"
        )
        send_custom_email(
            [admin_user, non_admin_user],
            options={
                "markdown_template_path": markdown_template_path,
                "admins_only": True,
                "dry_run": False,
            },
        )
        self.assert_length(mail.outbox, 1)
        self.assertIn(admin_user.delivery_email, mail.outbox[0].to[0])

    def test_send_custom_email_dry_run(self) -> None:
        hamlet = self.example_user("hamlet")
        email_subject = "subject_test"
        reply_to = "reply_to_test"
        from_name = "from_name_test"
        markdown_template_path = "templates/zerver/tests/markdown/test_nested_code_blocks.md"
        with patch("builtins.print") as _:
            send_custom_email(
                [hamlet],
                options={
                    "markdown_template_path": markdown_template_path,
                    "reply_to": reply_to,
                    "subject": email_subject,
                    "from_name": from_name,
                    "dry_run": True,
                },
            )
            self.assert_length(mail.outbox, 0)


class TestFollowupEmails(ZulipTestCase):
    def test_day1_email_context(self) -> None:
        hamlet = self.example_user("hamlet")
        enqueue_welcome_emails(hamlet)
        scheduled_emails = ScheduledEmail.objects.filter(users=hamlet)
        email_data = orjson.loads(scheduled_emails[0].data)
        self.assertEqual(email_data["context"]["email"], self.example_email("hamlet"))
        self.assertEqual(email_data["context"]["is_realm_admin"], False)
        self.assertEqual(email_data["context"]["getting_started_link"], "https://zulip.com")
        self.assertNotIn("ldap_username", email_data["context"])

        ScheduledEmail.objects.all().delete()

        iago = self.example_user("iago")
        enqueue_welcome_emails(iago)
        scheduled_emails = ScheduledEmail.objects.filter(users=iago)
        email_data = orjson.loads(scheduled_emails[0].data)
        self.assertEqual(email_data["context"]["email"], self.example_email("iago"))
        self.assertEqual(email_data["context"]["is_realm_admin"], True)
        self.assertEqual(
            email_data["context"]["getting_started_link"],
            "http://zulip.testserver/help/getting-your-organization-started-with-zulip",
        )
        self.assertNotIn("ldap_username", email_data["context"])

    # See https://zulip.readthedocs.io/en/latest/production/authentication-methods.html#ldap-including-active-directory
    # for case details.
    @override_settings(
        AUTHENTICATION_BACKENDS=(
            "zproject.backends.ZulipLDAPAuthBackend",
            "zproject.backends.ZulipDummyBackend",
        ),
        # configure email search for email address in the uid attribute:
        AUTH_LDAP_REVERSE_EMAIL_SEARCH=LDAPSearch(
            "ou=users,dc=zulip,dc=com", ldap.SCOPE_ONELEVEL, "(uid=%(email)s)"
        ),
    )
    def test_day1_email_ldap_case_a_login_credentials(self) -> None:
        self.init_default_ldap_database()
        ldap_user_attr_map = {"full_name": "cn"}

        with self.settings(AUTH_LDAP_USER_ATTR_MAP=ldap_user_attr_map):
            self.login_with_return(
                "newuser_email_as_uid@zulip.com",
                self.ldap_password("newuser_email_as_uid@zulip.com"),
            )
            user = UserProfile.objects.get(delivery_email="newuser_email_as_uid@zulip.com")
            scheduled_emails = ScheduledEmail.objects.filter(users=user)

            self.assert_length(scheduled_emails, 2)
            email_data = orjson.loads(scheduled_emails[0].data)
            self.assertEqual(email_data["context"]["ldap"], True)
            self.assertEqual(
                email_data["context"]["ldap_username"], "newuser_email_as_uid@zulip.com"
            )

    @override_settings(
        AUTHENTICATION_BACKENDS=(
            "zproject.backends.ZulipLDAPAuthBackend",
            "zproject.backends.ZulipDummyBackend",
        )
    )
    def test_day1_email_ldap_case_b_login_credentials(self) -> None:
        self.init_default_ldap_database()
        ldap_user_attr_map = {"full_name": "cn"}

        with self.settings(
            LDAP_APPEND_DOMAIN="zulip.com",
            AUTH_LDAP_USER_ATTR_MAP=ldap_user_attr_map,
        ):
            self.login_with_return("newuser@zulip.com", self.ldap_password("newuser"))

            user = UserProfile.objects.get(delivery_email="newuser@zulip.com")
            scheduled_emails = ScheduledEmail.objects.filter(users=user)

            self.assert_length(scheduled_emails, 2)
            email_data = orjson.loads(scheduled_emails[0].data)
            self.assertEqual(email_data["context"]["ldap"], True)
            self.assertEqual(email_data["context"]["ldap_username"], "newuser")

    @override_settings(
        AUTHENTICATION_BACKENDS=(
            "zproject.backends.ZulipLDAPAuthBackend",
            "zproject.backends.ZulipDummyBackend",
        )
    )
    def test_day1_email_ldap_case_c_login_credentials(self) -> None:
        self.init_default_ldap_database()
        ldap_user_attr_map = {"full_name": "cn"}

        with self.settings(
            LDAP_EMAIL_ATTR="mail",
            AUTH_LDAP_USER_ATTR_MAP=ldap_user_attr_map,
        ):
            self.login_with_return("newuser_with_email", self.ldap_password("newuser_with_email"))
            user = UserProfile.objects.get(delivery_email="newuser_email@zulip.com")
            scheduled_emails = ScheduledEmail.objects.filter(users=user)

            self.assert_length(scheduled_emails, 2)
            email_data = orjson.loads(scheduled_emails[0].data)
            self.assertEqual(email_data["context"]["ldap"], True)
            self.assertEqual(email_data["context"]["ldap_username"], "newuser_with_email")

    def test_followup_emails_count(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")

        enqueue_welcome_emails(self.example_user("hamlet"))
        # Hamlet has account only in Zulip realm so both day1 and day2 emails should be sent
        scheduled_emails = ScheduledEmail.objects.filter(users=hamlet).order_by(
            "scheduled_timestamp"
        )
        self.assert_length(scheduled_emails, 2)
        self.assertEqual(
            orjson.loads(scheduled_emails[1].data)["template_prefix"], "zerver/emails/followup_day2"
        )
        self.assertEqual(
            orjson.loads(scheduled_emails[0].data)["template_prefix"], "zerver/emails/followup_day1"
        )

        ScheduledEmail.objects.all().delete()

        enqueue_welcome_emails(cordelia)
        scheduled_emails = ScheduledEmail.objects.filter(users=cordelia)
        # Cordelia has account in more than 1 realm so day2 email should not be sent
        self.assert_length(scheduled_emails, 1)
        email_data = orjson.loads(scheduled_emails[0].data)
        self.assertEqual(email_data["template_prefix"], "zerver/emails/followup_day1")

    def test_followup_emails_for_regular_realms(self) -> None:
        cordelia = self.example_user("cordelia")
        enqueue_welcome_emails(self.example_user("cordelia"), realm_creation=True)
        scheduled_email = ScheduledEmail.objects.filter(users=cordelia).last()
        assert scheduled_email is not None
        self.assertEqual(
            orjson.loads(scheduled_email.data)["template_prefix"], "zerver/emails/followup_day1"
        )

        deliver_scheduled_emails(scheduled_email)
        from django.core.mail import outbox

        self.assert_length(outbox, 1)

        message = outbox[0]
        self.assertIn("You've created the new Zulip organization", message.body)
        self.assertNotIn("demo org", message.body)

    def test_followup_emails_for_demo_realms(self) -> None:
        cordelia = self.example_user("cordelia")
        cordelia.realm.demo_organization_scheduled_deletion_date = timezone_now() + timedelta(
            days=30
        )
        cordelia.realm.save()
        enqueue_welcome_emails(self.example_user("cordelia"), realm_creation=True)
        scheduled_email = ScheduledEmail.objects.filter(users=cordelia).last()
        assert scheduled_email is not None
        self.assertEqual(
            orjson.loads(scheduled_email.data)["template_prefix"], "zerver/emails/followup_day1"
        )

        deliver_scheduled_emails(scheduled_email)
        from django.core.mail import outbox

        self.assert_length(outbox, 1)

        message = outbox[0]
        self.assertIn("You've created a demo Zulip organization", message.body)


class TestMissedMessages(ZulipTestCase):
    def test_read_message(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        self.login("cordelia")
        result = self.client_post(
            "/json/messages",
            {
                "type": "private",
                "content": "Test message",
                "to": orjson.dumps([hamlet.email]).decode(),
            },
        )
        self.assert_json_success(result)
        message = self.get_last_message()

        # The message is marked as read for the sender (Cordelia) by the message send codepath.
        # We obviously should not send notifications to someone for messages they sent themselves.
        with mock.patch(
            "zerver.lib.email_notifications.do_send_missedmessage_events_reply_in_zulip"
        ) as m:
            handle_missedmessage_emails(
                cordelia.id, [{"message_id": message.id, "trigger": "private_message"}]
            )
        m.assert_not_called()

        # If the notification is processed before Hamlet reads the message, he should get the email.
        with mock.patch(
            "zerver.lib.email_notifications.do_send_missedmessage_events_reply_in_zulip"
        ) as m:
            handle_missedmessage_emails(
                hamlet.id, [{"message_id": message.id, "trigger": "private_message"}]
            )
        m.assert_called_once()

        # If Hamlet reads the message before receiving the email notification, we should not sent him
        # an email.
        usermessage = UserMessage.objects.get(
            user_profile=hamlet,
            message=message,
        )
        usermessage.flags.read = True
        usermessage.save()
        with mock.patch(
            "zerver.lib.email_notifications.do_send_missedmessage_events_reply_in_zulip"
        ) as m:
            handle_missedmessage_emails(
                hamlet.id, [{"message_id": message.id, "trigger": "private_message"}]
            )
        m.assert_not_called()

    def normalize_string(self, s: Union[str, StrPromise]) -> str:
        s = s.strip()
        return re.sub(r"\s+", " ", s)

    def _get_tokens(self) -> List[str]:
        return ["mm" + str(random.getrandbits(32)) for _ in range(30)]

    def _test_cases(
        self,
        msg_id: int,
        verify_body_include: List[str],
        email_subject: str,
        send_as_user: bool,
        verify_html_body: bool = False,
        show_message_content: bool = True,
        verify_body_does_not_include: Sequence[str] = [],
        trigger: str = "",
        mentioned_user_group_id: Optional[int] = None,
    ) -> None:
        othello = self.example_user("othello")
        hamlet = self.example_user("hamlet")
        tokens = self._get_tokens()
        with patch("zerver.lib.email_mirror.generate_missed_message_token", side_effect=tokens):
            handle_missedmessage_emails(
                hamlet.id,
                [
                    {
                        "message_id": msg_id,
                        "trigger": trigger,
                        "mentioned_user_group_id": mentioned_user_group_id,
                    }
                ],
            )
        if settings.EMAIL_GATEWAY_PATTERN != "":
            reply_to_addresses = [settings.EMAIL_GATEWAY_PATTERN % (t,) for t in tokens]
            reply_to_emails = [
                str(Address(display_name="Zulip", addr_spec=address))
                for address in reply_to_addresses
            ]
        else:
            reply_to_emails = ["noreply@testserver"]
        msg = mail.outbox[0]
        assert isinstance(msg, EmailMultiAlternatives)
        from_email = str(Address(display_name="Zulip notifications", addr_spec=FromAddress.NOREPLY))
        self.assert_length(mail.outbox, 1)
        if send_as_user:
            from_email = f'"{othello.full_name}" <{othello.email}>'
        self.assertEqual(self.email_envelope_from(msg), settings.NOREPLY_EMAIL_ADDRESS)
        self.assertEqual(self.email_display_from(msg), from_email)
        self.assertEqual(msg.subject, email_subject)
        self.assert_length(msg.reply_to, 1)
        self.assertIn(msg.reply_to[0], reply_to_emails)
        if verify_html_body:
            for text in verify_body_include:
                assert isinstance(msg.alternatives[0][0], str)
                self.assertIn(text, self.normalize_string(msg.alternatives[0][0]))
        else:
            for text in verify_body_include:
                self.assertIn(text, self.normalize_string(msg.body))
        for text in verify_body_does_not_include:
            self.assertNotIn(text, self.normalize_string(msg.body))

        self.assertEqual(msg.extra_headers["List-Id"], "Zulip Dev <zulip.testserver>")

    def _realm_name_in_missed_message_email_subject(
        self, realm_name_in_notifications: bool
    ) -> None:
        msg_id = self.send_personal_message(
            self.example_user("othello"),
            self.example_user("hamlet"),
            "Extremely personal message!",
        )
        verify_body_include = ["Extremely personal message!"]
        email_subject = "PMs with Othello, the Moor of Venice"

        if realm_name_in_notifications:
            email_subject = "PMs with Othello, the Moor of Venice [Zulip Dev]"
        self._test_cases(msg_id, verify_body_include, email_subject, False)

    def _extra_context_in_missed_stream_messages_mention(
        self, send_as_user: bool, show_message_content: bool = True
    ) -> None:
        for i in range(0, 11):
            self.send_stream_message(self.example_user("othello"), "Denmark", content=str(i))
        self.send_stream_message(self.example_user("othello"), "Denmark", "11", topic_name="test2")
        msg_id = self.send_stream_message(
            self.example_user("othello"), "denmark", "@**King Hamlet**"
        )

        if show_message_content:
            verify_body_include = [
                "Othello, the Moor of Venice: > 1 > 2 > 3 > 4 > 5 > 6 > 7 > 8 > 9 > 10 > @**King Hamlet** -- ",
                "You are receiving this because you were personally mentioned.",
            ]
            email_subject = "#Denmark > test"
            verify_body_does_not_include: List[str] = []
        else:
            # Test in case if message content in missed email message are disabled.
            verify_body_include = [
                "This email does not include message content because you have disabled message ",
                "http://zulip.testserver/help/pm-mention-alert-notifications ",
                "View or reply in Zulip Dev Zulip",
                " Manage email preferences: http://zulip.testserver/#settings/notifications",
            ]

            email_subject = "New messages"
            verify_body_does_not_include = [
                "Denmark > test",
                "Othello, the Moor of Venice",
                "1 2 3 4 5 6 7 8 9 10 @**King Hamlet**",
                "private",
                "group",
                "Reply to this email directly, or view it in Zulip Dev Zulip",
            ]
        self._test_cases(
            msg_id,
            verify_body_include,
            email_subject,
            send_as_user,
            show_message_content=show_message_content,
            verify_body_does_not_include=verify_body_does_not_include,
            trigger="mentioned",
        )

    def _extra_context_in_missed_stream_messages_wildcard_mention(
        self, send_as_user: bool, show_message_content: bool = True
    ) -> None:
        for i in range(1, 6):
            self.send_stream_message(self.example_user("othello"), "Denmark", content=str(i))
        self.send_stream_message(self.example_user("othello"), "Denmark", "11", topic_name="test2")
        msg_id = self.send_stream_message(self.example_user("othello"), "denmark", "@**all**")

        if show_message_content:
            verify_body_include = [
                "Othello, the Moor of Venice: > 1 > 2 > 3 > 4 > 5 > @**all** -- ",
                "You are receiving this because everyone was mentioned in #Denmark.",
            ]
            email_subject = "#Denmark > test"
            verify_body_does_not_include: List[str] = []
        else:
            # Test in case if message content in missed email message are disabled.
            verify_body_include = [
                "This email does not include message content because you have disabled message ",
                "http://zulip.testserver/help/pm-mention-alert-notifications ",
                "View or reply in Zulip Dev Zulip",
                " Manage email preferences: http://zulip.testserver/#settings/notifications",
            ]
            email_subject = "New messages"
            verify_body_does_not_include = [
                "Denmark > test",
                "Othello, the Moor of Venice",
                "1 2 3 4 5 @**all**",
                "private",
                "group",
                "Reply to this email directly, or view it in Zulip Dev Zulip",
            ]
        self._test_cases(
            msg_id,
            verify_body_include,
            email_subject,
            send_as_user,
            show_message_content=show_message_content,
            verify_body_does_not_include=verify_body_does_not_include,
            trigger="wildcard_mentioned",
        )

    def _extra_context_in_missed_stream_messages_email_notify(self, send_as_user: bool) -> None:
        for i in range(0, 11):
            self.send_stream_message(self.example_user("othello"), "Denmark", content=str(i))
        self.send_stream_message(self.example_user("othello"), "Denmark", "11", topic_name="test2")
        msg_id = self.send_stream_message(self.example_user("othello"), "denmark", "12")
        verify_body_include = [
            "Othello, the Moor of Venice: > 1 > 2 > 3 > 4 > 5 > 6 > 7 > 8 > 9 > 10 > 12 -- ",
            "You are receiving this because you have email notifications enabled for #Denmark.",
        ]
        email_subject = "#Denmark > test"
        self._test_cases(
            msg_id, verify_body_include, email_subject, send_as_user, trigger="stream_email_notify"
        )

    def _extra_context_in_missed_stream_messages_mention_two_senders(
        self, send_as_user: bool
    ) -> None:
        cordelia = self.example_user("cordelia")
        self.subscribe(cordelia, "Denmark")

        for i in range(0, 3):
            self.send_stream_message(cordelia, "Denmark", str(i))
        msg_id = self.send_stream_message(
            self.example_user("othello"), "Denmark", "@**King Hamlet**"
        )
        verify_body_include = [
            "Cordelia, Lear's daughter: > 0 > 1 > 2 Othello, the Moor of Venice: > @**King Hamlet** -- ",
            "You are receiving this because you were personally mentioned.",
        ]
        email_subject = "#Denmark > test"
        self._test_cases(
            msg_id, verify_body_include, email_subject, send_as_user, trigger="mentioned"
        )

    def _extra_context_in_missed_personal_messages(
        self,
        send_as_user: bool,
        show_message_content: bool = True,
        message_content_disabled_by_user: bool = False,
        message_content_disabled_by_realm: bool = False,
    ) -> None:
        msg_id = self.send_personal_message(
            self.example_user("othello"),
            self.example_user("hamlet"),
            "Extremely personal message!",
        )

        if show_message_content:
            verify_body_include = ["> Extremely personal message!"]
            email_subject = "PMs with Othello, the Moor of Venice"
            verify_body_does_not_include: List[str] = []
        else:
            if message_content_disabled_by_realm:
                verify_body_include = [
                    "This email does not include message content because your organization has disabled",
                    "http://zulip.testserver/help/hide-message-content-in-emails",
                    "View or reply in Zulip Dev Zulip",
                    " Manage email preferences: http://zulip.testserver/#settings/notifications",
                ]
            elif message_content_disabled_by_user:
                verify_body_include = [
                    "This email does not include message content because you have disabled message ",
                    "http://zulip.testserver/help/pm-mention-alert-notifications ",
                    "View or reply in Zulip Dev Zulip",
                    " Manage email preferences: http://zulip.testserver/#settings/notifications",
                ]
            email_subject = "New messages"
            verify_body_does_not_include = [
                "Othello, the Moor of Venice",
                "Extremely personal message!",
                "mentioned",
                "group",
                "Reply to this email directly, or view it in Zulip Dev Zulip",
            ]
        self._test_cases(
            msg_id,
            verify_body_include,
            email_subject,
            send_as_user,
            show_message_content=show_message_content,
            verify_body_does_not_include=verify_body_does_not_include,
        )

    def _reply_to_email_in_missed_personal_messages(self, send_as_user: bool) -> None:
        msg_id = self.send_personal_message(
            self.example_user("othello"),
            self.example_user("hamlet"),
            "Extremely personal message!",
        )
        verify_body_include = ["Reply to this email directly, or view it in Zulip Dev Zulip"]
        email_subject = "PMs with Othello, the Moor of Venice"
        self._test_cases(msg_id, verify_body_include, email_subject, send_as_user)

    def _reply_warning_in_missed_personal_messages(self, send_as_user: bool) -> None:
        msg_id = self.send_personal_message(
            self.example_user("othello"),
            self.example_user("hamlet"),
            "Extremely personal message!",
        )
        verify_body_include = ["Do not reply to this email."]
        email_subject = "PMs with Othello, the Moor of Venice"
        self._test_cases(msg_id, verify_body_include, email_subject, send_as_user)

    def _extra_context_in_missed_huddle_messages_two_others(
        self, send_as_user: bool, show_message_content: bool = True
    ) -> None:
        msg_id = self.send_huddle_message(
            self.example_user("othello"),
            [
                self.example_user("hamlet"),
                self.example_user("iago"),
            ],
            "Group personal message!",
        )

        if show_message_content:
            verify_body_include = [
                "Othello, the Moor of Venice: > Group personal message! -- Reply"
            ]
            email_subject = "Group PMs with Iago and Othello, the Moor of Venice"
            verify_body_does_not_include: List[str] = []
        else:
            verify_body_include = [
                "This email does not include message content because you have disabled message ",
                "http://zulip.testserver/help/pm-mention-alert-notifications ",
                "View or reply in Zulip Dev Zulip",
                " Manage email preferences: http://zulip.testserver/#settings/notifications",
            ]
            email_subject = "New messages"
            verify_body_does_not_include = [
                "Iago",
                "Othello, the Moor of Venice Othello, the Moor of Venice",
                "Group personal message!",
                "mentioned",
                "Reply to this email directly, or view it in Zulip Dev Zulip",
            ]
        self._test_cases(
            msg_id,
            verify_body_include,
            email_subject,
            send_as_user,
            show_message_content=show_message_content,
            verify_body_does_not_include=verify_body_does_not_include,
        )

    def _extra_context_in_missed_huddle_messages_three_others(self, send_as_user: bool) -> None:
        msg_id = self.send_huddle_message(
            self.example_user("othello"),
            [
                self.example_user("hamlet"),
                self.example_user("iago"),
                self.example_user("cordelia"),
            ],
            "Group personal message!",
        )

        verify_body_include = ["Othello, the Moor of Venice: > Group personal message! -- Reply"]
        email_subject = (
            "Group PMs with Cordelia, Lear's daughter, Iago, and Othello, the Moor of Venice"
        )
        self._test_cases(msg_id, verify_body_include, email_subject, send_as_user)

    def _extra_context_in_missed_huddle_messages_many_others(self, send_as_user: bool) -> None:
        msg_id = self.send_huddle_message(
            self.example_user("othello"),
            [
                self.example_user("hamlet"),
                self.example_user("iago"),
                self.example_user("cordelia"),
                self.example_user("prospero"),
            ],
            "Group personal message!",
        )

        verify_body_include = ["Othello, the Moor of Venice: > Group personal message! -- Reply"]
        email_subject = "Group PMs with Cordelia, Lear's daughter, Iago, and 2 others"
        self._test_cases(msg_id, verify_body_include, email_subject, send_as_user)

    def _deleted_message_in_missed_stream_messages(self, send_as_user: bool) -> None:
        msg_id = self.send_stream_message(
            self.example_user("othello"), "denmark", "@**King Hamlet** to be deleted"
        )

        hamlet = self.example_user("hamlet")
        self.login("othello")
        result = self.client_patch("/json/messages/" + str(msg_id), {"content": " "})
        self.assert_json_success(result)
        handle_missedmessage_emails(hamlet.id, [{"message_id": msg_id}])
        self.assert_length(mail.outbox, 0)

    def _deleted_message_in_missed_personal_messages(self, send_as_user: bool) -> None:
        msg_id = self.send_personal_message(
            self.example_user("othello"),
            self.example_user("hamlet"),
            "Extremely personal message! to be deleted!",
        )

        hamlet = self.example_user("hamlet")
        self.login("othello")
        result = self.client_patch("/json/messages/" + str(msg_id), {"content": " "})
        self.assert_json_success(result)
        handle_missedmessage_emails(hamlet.id, [{"message_id": msg_id}])
        self.assert_length(mail.outbox, 0)

    def _deleted_message_in_missed_huddle_messages(self, send_as_user: bool) -> None:
        msg_id = self.send_huddle_message(
            self.example_user("othello"),
            [
                self.example_user("hamlet"),
                self.example_user("iago"),
            ],
            "Group personal message!",
        )

        hamlet = self.example_user("hamlet")
        iago = self.example_user("iago")
        self.login("othello")
        result = self.client_patch("/json/messages/" + str(msg_id), {"content": " "})
        self.assert_json_success(result)
        handle_missedmessage_emails(hamlet.id, [{"message_id": msg_id}])
        self.assert_length(mail.outbox, 0)
        handle_missedmessage_emails(iago.id, [{"message_id": msg_id}])
        self.assert_length(mail.outbox, 0)

    def test_smaller_user_group_mention_priority(self) -> None:
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")
        cordelia = self.example_user("cordelia")

        hamlet_only = create_user_group("hamlet_only", [hamlet], get_realm("zulip"))
        hamlet_and_cordelia = create_user_group(
            "hamlet_and_cordelia", [hamlet, cordelia], get_realm("zulip")
        )

        hamlet_only_message_id = self.send_stream_message(othello, "Denmark", "@*hamlet_only*")
        hamlet_and_cordelia_message_id = self.send_stream_message(
            othello, "Denmark", "@*hamlet_and_cordelia*"
        )

        handle_missedmessage_emails(
            hamlet.id,
            [
                {
                    "message_id": hamlet_only_message_id,
                    "trigger": "mentioned",
                    "mentioned_user_group_id": hamlet_only.id,
                },
                {
                    "message_id": hamlet_and_cordelia_message_id,
                    "trigger": "mentioned",
                    "mentioned_user_group_id": hamlet_and_cordelia.id,
                },
            ],
        )

        expected_email_include = [
            "Othello, the Moor of Venice: > @*hamlet_only* > @*hamlet_and_cordelia* -- ",
            "You are receiving this because @hamlet_only was mentioned.",
        ]

        for text in expected_email_include:
            self.assertIn(text, self.normalize_string(mail.outbox[0].body))

    def test_personal_over_user_group_mention_priority(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        othello = self.example_user("othello")

        hamlet_and_cordelia = create_user_group(
            "hamlet_and_cordelia", [hamlet, cordelia], get_realm("zulip")
        )

        user_group_mentioned_message_id = self.send_stream_message(
            othello, "Denmark", "@*hamlet_and_cordelia*"
        )
        personal_mentioned_message_id = self.send_stream_message(
            othello, "Denmark", "@**King Hamlet**"
        )

        handle_missedmessage_emails(
            hamlet.id,
            [
                {
                    "message_id": user_group_mentioned_message_id,
                    "trigger": "mentioned",
                    "mentioned_user_group_id": hamlet_and_cordelia.id,
                },
                {
                    "message_id": personal_mentioned_message_id,
                    "trigger": "mentioned",
                    "mentioned_user_group_id": None,
                },
            ],
        )

        expected_email_include = [
            "Othello, the Moor of Venice: > @*hamlet_and_cordelia* > @**King Hamlet** -- ",
            "You are receiving this because you were personally mentioned.",
        ]

        for text in expected_email_include:
            self.assertIn(text, self.normalize_string(mail.outbox[0].body))

    def test_user_group_over_wildcard_mention_priority(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        othello = self.example_user("othello")

        hamlet_and_cordelia = create_user_group(
            "hamlet_and_cordelia", [hamlet, cordelia], get_realm("zulip")
        )

        wildcard_mentioned_message_id = self.send_stream_message(othello, "Denmark", "@**all**")
        user_group_mentioned_message_id = self.send_stream_message(
            othello, "Denmark", "@*hamlet_and_cordelia*"
        )

        handle_missedmessage_emails(
            hamlet.id,
            [
                {
                    "message_id": wildcard_mentioned_message_id,
                    "trigger": "wildcard_mentioned",
                    "mentioned_user_group_id": None,
                },
                {
                    "message_id": user_group_mentioned_message_id,
                    "trigger": "mentioned",
                    "mentioned_user_group_id": hamlet_and_cordelia.id,
                },
            ],
        )

        expected_email_include = [
            "Othello, the Moor of Venice: > @**all** > @*hamlet_and_cordelia* -- ",
            "You are receiving this because @hamlet_and_cordelia was mentioned.",
        ]

        for text in expected_email_include:
            self.assertIn(text, self.normalize_string(mail.outbox[0].body))

    def test_wildcard_over_stream_mention_priority(self) -> None:
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")

        stream_mentioned_message_id = self.send_stream_message(othello, "Denmark", "1")
        wildcard_mentioned_message_id = self.send_stream_message(othello, "Denmark", "@**all**")

        handle_missedmessage_emails(
            hamlet.id,
            [
                {
                    "message_id": stream_mentioned_message_id,
                    "trigger": "stream_email_notify",
                    "mentioned_user_group_id": None,
                },
                {
                    "message_id": wildcard_mentioned_message_id,
                    "trigger": "wildcard_mentioned",
                    "mentioned_user_group_id": None,
                },
            ],
        )

        expected_email_include = [
            "Othello, the Moor of Venice: > 1 > @**all** -- ",
            "You are receiving this because everyone was mentioned in #Denmark.",
        ]

        for text in expected_email_include:
            self.assertIn(text, self.normalize_string(mail.outbox[0].body))

    def test_realm_name_in_notifications(self) -> None:
        # Test with realm_name_in_notifications for hamlet disabled.
        self._realm_name_in_missed_message_email_subject(False)

        # Enable realm_name_in_notifications for hamlet and test again.
        hamlet = self.example_user("hamlet")
        hamlet.realm_name_in_notifications = True
        hamlet.save(update_fields=["realm_name_in_notifications"])

        # Empty the test outbox
        mail.outbox = []
        self._realm_name_in_missed_message_email_subject(True)

    def test_message_content_disabled_in_missed_message_notifications(self) -> None:
        # Test when user disabled message content in email notifications.
        do_change_user_setting(
            self.example_user("hamlet"),
            "message_content_in_email_notifications",
            False,
            acting_user=None,
        )
        self._extra_context_in_missed_stream_messages_mention(False, show_message_content=False)
        mail.outbox = []
        self._extra_context_in_missed_stream_messages_wildcard_mention(
            False, show_message_content=False
        )
        mail.outbox = []
        self._extra_context_in_missed_personal_messages(
            False, show_message_content=False, message_content_disabled_by_user=True
        )
        mail.outbox = []
        self._extra_context_in_missed_huddle_messages_two_others(False, show_message_content=False)

    @override_settings(SEND_MISSED_MESSAGE_EMAILS_AS_USER=True)
    def test_extra_context_in_missed_stream_messages_as_user(self) -> None:
        self._extra_context_in_missed_stream_messages_mention(True)

    def test_extra_context_in_missed_stream_messages(self) -> None:
        self._extra_context_in_missed_stream_messages_mention(False)

    @override_settings(SEND_MISSED_MESSAGE_EMAILS_AS_USER=True)
    def test_extra_context_in_missed_stream_messages_as_user_wildcard(self) -> None:
        self._extra_context_in_missed_stream_messages_wildcard_mention(True)

    def test_extra_context_in_missed_stream_messages_wildcard(self) -> None:
        self._extra_context_in_missed_stream_messages_wildcard_mention(False)

    @override_settings(SEND_MISSED_MESSAGE_EMAILS_AS_USER=True)
    def test_extra_context_in_missed_stream_messages_as_user_two_senders(self) -> None:
        self._extra_context_in_missed_stream_messages_mention_two_senders(True)

    def test_extra_context_in_missed_stream_messages_two_senders(self) -> None:
        self._extra_context_in_missed_stream_messages_mention_two_senders(False)

    def test_reply_to_email_in_missed_personal_messages(self) -> None:
        self._reply_to_email_in_missed_personal_messages(False)

    @override_settings(SEND_MISSED_MESSAGE_EMAILS_AS_USER=True)
    def test_extra_context_in_missed_stream_messages_email_notify_as_user(self) -> None:
        self._extra_context_in_missed_stream_messages_email_notify(True)

    def test_extra_context_in_missed_stream_messages_email_notify(self) -> None:
        self._extra_context_in_missed_stream_messages_email_notify(False)

    @override_settings(EMAIL_GATEWAY_PATTERN="")
    def test_reply_warning_in_missed_personal_messages(self) -> None:
        self._reply_warning_in_missed_personal_messages(False)

    @override_settings(SEND_MISSED_MESSAGE_EMAILS_AS_USER=True)
    def test_extra_context_in_missed_personal_messages_as_user(self) -> None:
        self._extra_context_in_missed_personal_messages(True)

    def test_extra_context_in_missed_personal_messages(self) -> None:
        self._extra_context_in_missed_personal_messages(False)

    @override_settings(SEND_MISSED_MESSAGE_EMAILS_AS_USER=True)
    def test_extra_context_in_missed_huddle_messages_two_others_as_user(self) -> None:
        self._extra_context_in_missed_huddle_messages_two_others(True)

    def test_extra_context_in_missed_huddle_messages_two_others(self) -> None:
        self._extra_context_in_missed_huddle_messages_two_others(False)

    @override_settings(SEND_MISSED_MESSAGE_EMAILS_AS_USER=True)
    def test_extra_context_in_missed_huddle_messages_three_others_as_user(self) -> None:
        self._extra_context_in_missed_huddle_messages_three_others(True)

    def test_extra_context_in_missed_huddle_messages_three_others(self) -> None:
        self._extra_context_in_missed_huddle_messages_three_others(False)

    @override_settings(SEND_MISSED_MESSAGE_EMAILS_AS_USER=True)
    def test_extra_context_in_missed_huddle_messages_many_others_as_user(self) -> None:
        self._extra_context_in_missed_huddle_messages_many_others(True)

    def test_extra_context_in_missed_huddle_messages_many_others(self) -> None:
        self._extra_context_in_missed_huddle_messages_many_others(False)

    @override_settings(SEND_MISSED_MESSAGE_EMAILS_AS_USER=True)
    def test_deleted_message_in_missed_stream_messages_as_user(self) -> None:
        self._deleted_message_in_missed_stream_messages(True)

    def test_deleted_message_in_missed_stream_messages(self) -> None:
        self._deleted_message_in_missed_stream_messages(False)

    @override_settings(SEND_MISSED_MESSAGE_EMAILS_AS_USER=True)
    def test_deleted_message_in_missed_personal_messages_as_user(self) -> None:
        self._deleted_message_in_missed_personal_messages(True)

    def test_deleted_message_in_missed_personal_messages(self) -> None:
        self._deleted_message_in_missed_personal_messages(False)

    @override_settings(SEND_MISSED_MESSAGE_EMAILS_AS_USER=True)
    def test_deleted_message_in_missed_huddle_messages_as_user(self) -> None:
        self._deleted_message_in_missed_huddle_messages(True)

    def test_deleted_message_in_missed_huddle_messages(self) -> None:
        self._deleted_message_in_missed_huddle_messages(False)

    def test_realm_message_content_allowed_in_email_notifications(self) -> None:
        user = self.example_user("hamlet")

        # When message content is allowed at realm level
        realm = get_realm("zulip")
        realm.message_content_allowed_in_email_notifications = True
        realm.save(update_fields=["message_content_allowed_in_email_notifications"])

        # Emails have missed message content when message content is enabled by the user
        do_change_user_setting(
            user, "message_content_in_email_notifications", True, acting_user=None
        )
        mail.outbox = []
        self._extra_context_in_missed_personal_messages(False, show_message_content=True)

        # Emails don't have missed message content when message content is disabled by the user
        do_change_user_setting(
            user, "message_content_in_email_notifications", False, acting_user=None
        )
        mail.outbox = []
        self._extra_context_in_missed_personal_messages(
            False, show_message_content=False, message_content_disabled_by_user=True
        )

        # When message content is not allowed at realm level
        # Emails don't have message content irrespective of message content setting of the user
        realm = get_realm("zulip")
        realm.message_content_allowed_in_email_notifications = False
        realm.save(update_fields=["message_content_allowed_in_email_notifications"])

        do_change_user_setting(
            user, "message_content_in_email_notifications", True, acting_user=None
        )
        mail.outbox = []
        self._extra_context_in_missed_personal_messages(
            False, show_message_content=False, message_content_disabled_by_realm=True
        )

        do_change_user_setting(
            user, "message_content_in_email_notifications", False, acting_user=None
        )
        mail.outbox = []
        self._extra_context_in_missed_personal_messages(
            False,
            show_message_content=False,
            message_content_disabled_by_user=True,
            message_content_disabled_by_realm=True,
        )

    def test_realm_emoji_in_missed_message(self) -> None:
        realm = get_realm("zulip")

        msg_id = self.send_personal_message(
            self.example_user("othello"),
            self.example_user("hamlet"),
            "Extremely personal message with a realm emoji :green_tick:!",
        )
        realm_emoji_id = realm.get_active_emoji()["green_tick"]["id"]
        realm_emoji_url = (
            f"http://zulip.testserver/user_avatars/{realm.id}/emoji/images/{realm_emoji_id}.png"
        )
        verify_body_include = [
            f'<img alt=":green_tick:" src="{realm_emoji_url}" title="green tick" style="height: 20px;">'
        ]
        email_subject = "PMs with Othello, the Moor of Venice"
        self._test_cases(
            msg_id, verify_body_include, email_subject, send_as_user=False, verify_html_body=True
        )

    def test_emojiset_in_missed_message(self) -> None:
        hamlet = self.example_user("hamlet")
        hamlet.emojiset = "twitter"
        hamlet.save(update_fields=["emojiset"])
        msg_id = self.send_personal_message(
            self.example_user("othello"),
            self.example_user("hamlet"),
            "Extremely personal message with a hamburger :hamburger:!",
        )
        verify_body_include = [
            '<img alt=":hamburger:" src="http://zulip.testserver/static/generated/emoji/images-twitter-64/1f354.png" title="hamburger" style="height: 20px;">'
        ]
        email_subject = "PMs with Othello, the Moor of Venice"
        self._test_cases(
            msg_id, verify_body_include, email_subject, send_as_user=False, verify_html_body=True
        )

    def test_stream_link_in_missed_message(self) -> None:
        msg_id = self.send_personal_message(
            self.example_user("othello"),
            self.example_user("hamlet"),
            "Come and join us in #**Verona**.",
        )
        stream_id = get_stream("Verona", get_realm("zulip")).id
        href = f"http://zulip.testserver/#narrow/stream/{stream_id}-Verona"
        verify_body_include = [
            f'<a class="stream" data-stream-id="{stream_id}" href="{href}">#Verona</a'
        ]
        email_subject = "PMs with Othello, the Moor of Venice"
        self._test_cases(
            msg_id, verify_body_include, email_subject, send_as_user=False, verify_html_body=True
        )

    def test_pm_link_in_missed_message_header(self) -> None:
        cordelia = self.example_user("cordelia")
        msg_id = self.send_personal_message(
            cordelia,
            self.example_user("hamlet"),
            "Let's test PM link in email notifications",
        )

        encoded_name = "Cordelia,-Lear's-daughter"
        verify_body_include = [
            f"view it in Zulip Dev Zulip: http://zulip.testserver/#narrow/pm-with/{cordelia.id}-{encoded_name}"
        ]
        email_subject = "PMs with Cordelia, Lear's daughter"
        self._test_cases(msg_id, verify_body_include, email_subject, send_as_user=False)

    def test_sender_name_in_missed_message(self) -> None:
        hamlet = self.example_user("hamlet")
        msg_id_1 = self.send_stream_message(
            self.example_user("iago"), "Denmark", "@**King Hamlet**"
        )
        msg_id_2 = self.send_stream_message(self.example_user("iago"), "Verona", "* 1\n *2")
        msg_id_3 = self.send_personal_message(self.example_user("iago"), hamlet, "Hello")

        handle_missedmessage_emails(
            hamlet.id,
            [
                {"message_id": msg_id_1, "trigger": "mentioned"},
                {"message_id": msg_id_2, "trigger": "stream_email_notify"},
                {"message_id": msg_id_3},
            ],
        )

        assert isinstance(mail.outbox[0], EmailMultiAlternatives)
        assert isinstance(mail.outbox[0].alternatives[0][0], str)
        self.assertIn("Iago:\n> @**King Hamlet**\n\n--\nYou are", mail.outbox[0].body)
        # If message content starts with <p> tag the sender name is appended inside the <p> tag.
        self.assertIn(
            '<p><b>Iago</b>: <span class="user-mention"', mail.outbox[0].alternatives[0][0]
        )

        assert isinstance(mail.outbox[1], EmailMultiAlternatives)
        assert isinstance(mail.outbox[1].alternatives[0][0], str)
        self.assertIn("Iago:\n> * 1\n>  *2\n\n--\nYou are receiving", mail.outbox[1].body)
        # If message content does not starts with <p> tag sender name is appended before the <p> tag
        self.assertIn(
            "       <b>Iago</b>: <div><ul>\n<li>1<br/>\n *2</li>\n</ul></div>\n",
            mail.outbox[1].alternatives[0][0],
        )

        assert isinstance(mail.outbox[2], EmailMultiAlternatives)
        assert isinstance(mail.outbox[2].alternatives[0][0], str)
        self.assertEqual("> Hello\n\n--\n\nReply", mail.outbox[2].body[:18])
        # Sender name is not appended to message for PM missed messages
        self.assertIn(
            ">\n                    \n                        <div><p>Hello</p></div>\n",
            mail.outbox[2].alternatives[0][0],
        )

    def test_multiple_missed_personal_messages(self) -> None:
        hamlet = self.example_user("hamlet")
        msg_id_1 = self.send_personal_message(
            self.example_user("othello"), hamlet, "Personal Message 1"
        )
        msg_id_2 = self.send_personal_message(
            self.example_user("iago"), hamlet, "Personal Message 2"
        )

        handle_missedmessage_emails(
            hamlet.id,
            [
                {"message_id": msg_id_1},
                {"message_id": msg_id_2},
            ],
        )
        self.assert_length(mail.outbox, 2)
        email_subject = "PMs with Othello, the Moor of Venice"
        self.assertEqual(mail.outbox[0].subject, email_subject)
        email_subject = "PMs with Iago"
        self.assertEqual(mail.outbox[1].subject, email_subject)

    def test_multiple_stream_messages(self) -> None:
        hamlet = self.example_user("hamlet")
        msg_id_1 = self.send_stream_message(self.example_user("othello"), "Denmark", "Message1")
        msg_id_2 = self.send_stream_message(self.example_user("iago"), "Denmark", "Message2")

        handle_missedmessage_emails(
            hamlet.id,
            [
                {"message_id": msg_id_1, "trigger": "stream_email_notify"},
                {"message_id": msg_id_2, "trigger": "stream_email_notify"},
            ],
        )
        self.assert_length(mail.outbox, 1)
        email_subject = "#Denmark > test"
        self.assertEqual(mail.outbox[0].subject, email_subject)

    def test_multiple_stream_messages_and_mentions(self) -> None:
        """Subject should be stream name and topic as usual."""
        hamlet = self.example_user("hamlet")
        msg_id_1 = self.send_stream_message(self.example_user("iago"), "Denmark", "Regular message")
        msg_id_2 = self.send_stream_message(
            self.example_user("othello"), "Denmark", "@**King Hamlet**"
        )

        handle_missedmessage_emails(
            hamlet.id,
            [
                {"message_id": msg_id_1, "trigger": "stream_email_notify"},
                {"message_id": msg_id_2, "trigger": "mentioned"},
            ],
        )
        self.assert_length(mail.outbox, 1)
        email_subject = "#Denmark > test"
        self.assertEqual(mail.outbox[0].subject, email_subject)

    def test_message_access_in_emails(self) -> None:
        # Messages sent to a protected history-private stream shouldn't be
        # accessible/available in emails before subscribing
        stream_name = "private_stream"
        self.make_stream(stream_name, invite_only=True, history_public_to_subscribers=False)
        user = self.example_user("iago")
        self.subscribe(user, stream_name)
        late_subscribed_user = self.example_user("hamlet")

        self.send_stream_message(user, stream_name, "Before subscribing")

        self.subscribe(late_subscribed_user, stream_name)

        self.send_stream_message(user, stream_name, "After subscribing")

        mention_msg_id = self.send_stream_message(user, stream_name, "@**King Hamlet**")

        handle_missedmessage_emails(
            late_subscribed_user.id,
            [
                {"message_id": mention_msg_id, "trigger": "mentioned"},
            ],
        )

        self.assert_length(mail.outbox, 1)
        self.assertEqual(mail.outbox[0].subject, "#private_stream > test")  # email subject
        email_text = mail.outbox[0].message().as_string()
        self.assertNotIn("Before subscribing", email_text)
        self.assertIn("After subscribing", email_text)
        self.assertIn("@**King Hamlet**", email_text)

    def test_stream_mentions_multiple_people(self) -> None:
        """Subject should be stream name and topic as usual."""
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")

        self.subscribe(cordelia, "Denmark")

        msg_id_1 = self.send_stream_message(
            self.example_user("iago"), "Denmark", "@**King Hamlet**"
        )
        msg_id_2 = self.send_stream_message(
            self.example_user("othello"), "Denmark", "@**King Hamlet**"
        )
        msg_id_3 = self.send_stream_message(cordelia, "Denmark", "Regular message")

        handle_missedmessage_emails(
            hamlet.id,
            [
                {"message_id": msg_id_1, "trigger": "mentioned"},
                {"message_id": msg_id_2, "trigger": "mentioned"},
                {"message_id": msg_id_3, "trigger": "stream_email_notify"},
            ],
        )
        self.assert_length(mail.outbox, 1)
        email_subject = "#Denmark > test"
        self.assertEqual(mail.outbox[0].subject, email_subject)

    def test_multiple_stream_messages_different_topics(self) -> None:
        """Should receive separate emails for each topic within a stream."""
        hamlet = self.example_user("hamlet")
        msg_id_1 = self.send_stream_message(self.example_user("othello"), "Denmark", "Message1")
        msg_id_2 = self.send_stream_message(
            self.example_user("iago"), "Denmark", "Message2", topic_name="test2"
        )

        handle_missedmessage_emails(
            hamlet.id,
            [
                {"message_id": msg_id_1, "trigger": "stream_email_notify"},
                {"message_id": msg_id_2, "trigger": "stream_email_notify"},
            ],
        )
        self.assert_length(mail.outbox, 2)
        email_subjects = {mail.outbox[0].subject, mail.outbox[1].subject}
        valid_email_subjects = {"#Denmark > test", "#Denmark > test2"}
        self.assertEqual(email_subjects, valid_email_subjects)

    def test_relative_to_full_url(self) -> None:
        def convert(test_data: str) -> str:
            fragment = lxml.html.fragment_fromstring(test_data, create_parent=True)
            relative_to_full_url(fragment, "http://example.com")
            return lxml.html.tostring(fragment, encoding="unicode")

        zulip_realm = get_realm("zulip")
        zephyr_realm = get_realm("zephyr")
        # Run `relative_to_full_url()` function over test fixtures present in
        # 'markdown_test_cases.json' and check that it converts all the relative
        # URLs to absolute URLs.
        fixtures = orjson.loads(self.fixture_data("markdown_test_cases.json"))
        test_fixtures = {}
        for test in fixtures["regular_tests"]:
            test_fixtures[test["name"]] = test
        for test_name in test_fixtures:
            test_data = test_fixtures[test_name]["expected_output"]
            output_data = convert(test_data)
            if re.search(r"""(?<=\=['"])/(?=[^<]+>)""", output_data) is not None:
                raise AssertionError(
                    "Relative URL present in email: "
                    + output_data
                    + "\nFailed test case's name is: "
                    + test_name
                    + "\nIt is present in markdown_test_cases.json"
                )

        # Specific test cases.

        # A path similar to our emoji path, but not in a link:
        test_data = "<p>Check out the file at: '/static/generated/emoji/images/emoji/'</p>"
        actual_output = convert(test_data)
        expected_output = (
            "<div><p>Check out the file at: '/static/generated/emoji/images/emoji/'</p></div>"
        )
        self.assertEqual(actual_output, expected_output)

        # An uploaded file
        test_data = '<a href="/user_uploads/{realm_id}/1f/some_random_value">/user_uploads/{realm_id}/1f/some_random_value</a>'
        test_data = test_data.format(realm_id=zephyr_realm.id)
        actual_output = convert(test_data)
        expected_output = (
            '<div><a href="http://example.com/user_uploads/{realm_id}/1f/some_random_value">'
            + "/user_uploads/{realm_id}/1f/some_random_value</a></div>"
        )
        expected_output = expected_output.format(realm_id=zephyr_realm.id)
        self.assertEqual(actual_output, expected_output)

        # A profile picture like syntax, but not actually in an HTML tag
        test_data = '<p>Set src="/avatar/username@example.com?s=30"</p>'
        actual_output = convert(test_data)
        expected_output = '<div><p>Set src="/avatar/username@example.com?s=30"</p></div>'
        self.assertEqual(actual_output, expected_output)

        # A narrow URL which begins with a '#'.
        test_data = (
            '<p><a href="#narrow/stream/test/topic/test.20topic/near/142"'
            + 'title="#narrow/stream/test/topic/test.20topic/near/142">Conversation</a></p>'
        )
        actual_output = convert(test_data)
        expected_output = (
            '<div><p><a href="http://example.com/#narrow/stream/test/topic/test.20topic/near/142" '
            + 'title="http://example.com/#narrow/stream/test/topic/test.20topic/near/142">Conversation</a></p></div>'
        )
        self.assertEqual(actual_output, expected_output)

        # Scrub inline images.
        test_data = (
            '<p>See this <a href="/user_uploads/{realm_id}/52/fG7GM9e3afz_qsiUcSce2tl_/avatar_103.jpeg" target="_blank" '
            + 'title="avatar_103.jpeg">avatar_103.jpeg</a>.</p>'
            + '<div class="message_inline_image"><a href="/user_uploads/{realm_id}/52/fG7GM9e3afz_qsiUcSce2tl_/avatar_103.jpeg" '
            + 'target="_blank" title="avatar_103.jpeg"><img src="/user_uploads/{realm_id}/52/fG7GM9e3afz_qsiUcSce2tl_/avatar_103.jpeg"></a></div>'
        )
        test_data = test_data.format(realm_id=zulip_realm.id)
        actual_output = convert(test_data)
        expected_output = (
            '<div><p>See this <a href="http://example.com/user_uploads/{realm_id}/52/fG7GM9e3afz_qsiUcSce2tl_/avatar_103.jpeg" target="_blank" '
            + 'title="avatar_103.jpeg">avatar_103.jpeg</a>.</p></div>'
        )
        expected_output = expected_output.format(realm_id=zulip_realm.id)
        self.assertEqual(actual_output, expected_output)

        # A message containing only an inline image URL preview, we do
        # somewhat more extensive surgery.
        test_data = (
            '<div class="message_inline_image"><a href="https://www.google.com/images/srpr/logo4w.png" '
            + 'target="_blank" title="https://www.google.com/images/srpr/logo4w.png">'
            + '<img data-src-fullsize="/thumbnail/https%3A//www.google.com/images/srpr/logo4w.png?size=0x0" '
            + 'src="/thumbnail/https%3A//www.google.com/images/srpr/logo4w.png?size=0x100"></a></div>'
        )
        actual_output = convert(test_data)
        expected_output = (
            '<div><p><a href="https://www.google.com/images/srpr/logo4w.png" '
            + 'target="_blank" title="https://www.google.com/images/srpr/logo4w.png">'
            + "https://www.google.com/images/srpr/logo4w.png</a></p></div>"
        )
        self.assertEqual(actual_output, expected_output)

    def test_spoilers_in_html_emails(self) -> None:
        test_data = '<div class="spoiler-block"><div class="spoiler-header">\n\n<p><a>header</a> text</p>\n</div><div class="spoiler-content" aria-hidden="true">\n\n<p>content</p>\n</div></div>\n\n<p>outside spoiler</p>'
        fragment = lxml.html.fromstring(test_data)
        fix_spoilers_in_html(fragment, "en")
        actual_output = lxml.html.tostring(fragment, encoding="unicode")
        expected_output = '<div><div class="spoiler-block">\n\n<p><a>header</a> text <span class="spoiler-title" title="Open Zulip to see the spoiler content">(Open Zulip to see the spoiler content)</span></p>\n</div>\n\n<p>outside spoiler</p></div>'
        self.assertEqual(actual_output, expected_output)

        # test against our markdown_test_cases so these features do not get out of sync.
        fixtures = orjson.loads(self.fixture_data("markdown_test_cases.json"))
        test_fixtures = {}
        for test in fixtures["regular_tests"]:
            if "spoiler" in test["name"]:
                test_fixtures[test["name"]] = test
        for test_name in test_fixtures:
            fragment = lxml.html.fromstring(test_fixtures[test_name]["expected_output"])
            fix_spoilers_in_html(fragment, "en")
            output_data = lxml.html.tostring(fragment, encoding="unicode")
            assert "spoiler-header" not in output_data
            assert "spoiler-content" not in output_data
            assert "spoiler-block" in output_data
            assert "spoiler-title" in output_data

    def test_spoilers_in_text_emails(self) -> None:
        content = "@**King Hamlet**\n\n```spoiler header text\nsecret-text\n```"
        msg_id = self.send_stream_message(self.example_user("othello"), "Denmark", content)
        verify_body_include = ["header text", "Open Zulip to see the spoiler content"]
        verify_body_does_not_include = ["secret-text"]
        email_subject = "#Denmark > test"
        send_as_user = False
        self._test_cases(
            msg_id,
            verify_body_include,
            email_subject,
            send_as_user,
            trigger="mentioned",
            verify_body_does_not_include=verify_body_does_not_include,
        )

    def test_fix_emoji(self) -> None:
        # An emoji.
        test_data = (
            '<p>See <span aria-label="cloud with lightning and rain" class="emoji emoji-26c8" role="img" title="cloud with lightning and rain">'
            + ":cloud_with_lightning_and_rain:</span>.</p>"
        )
        fragment = lxml.html.fromstring(test_data)
        fix_emojis(fragment, "http://example.com", "google")
        actual_output = lxml.html.tostring(fragment, encoding="unicode")
        expected_output = (
            '<p>See <img alt=":cloud_with_lightning_and_rain:" src="http://example.com/static/generated/emoji/images-google-64/26c8.png" '
            + 'title="cloud with lightning and rain" style="height: 20px;">.</p>'
        )
        self.assertEqual(actual_output, expected_output)

    def test_empty_backticks_in_missed_message(self) -> None:
        msg_id = self.send_personal_message(
            self.example_user("othello"),
            self.example_user("hamlet"),
            "```\n```",
        )
        verify_body_include = ["view it in Zulip Dev Zulip"]
        email_subject = "PMs with Othello, the Moor of Venice"
        self._test_cases(
            msg_id, verify_body_include, email_subject, send_as_user=False, verify_html_body=True
        )

    def test_long_term_idle_user_missed_message(self) -> None:
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")
        cordelia = self.example_user("cordelia")
        large_user_group = create_user_group(
            "large_user_group", [hamlet, othello, cordelia], get_realm("zulip")
        )

        # Do note that the event dicts for the missed messages are constructed by hand
        # The part of testing the consumption of missed messages by the worker is left to
        # test_queue_worker.test_missed_message_worker

        # Personal mention in a stream message should soft reactivate the user
        with self.soft_deactivate_and_check_long_term_idle(hamlet, expected=False):
            mention = f"@**{hamlet.full_name}**"
            stream_mentioned_message_id = self.send_stream_message(othello, "Denmark", mention)
            handle_missedmessage_emails(
                hamlet.id,
                [{"message_id": stream_mentioned_message_id, "trigger": "mentioned"}],
            )

        # Private message should soft reactivate the user
        with self.soft_deactivate_and_check_long_term_idle(hamlet, expected=False):
            # Soft reactivate the user by sending a personal message
            personal_message_id = self.send_personal_message(othello, hamlet, "Message")
            handle_missedmessage_emails(
                hamlet.id,
                [{"message_id": personal_message_id, "trigger": "private_message"}],
            )

        # Wild card mention should NOT soft reactivate the user
        with self.soft_deactivate_and_check_long_term_idle(hamlet, expected=True):
            # Soft reactivate the user by sending a personal message
            mention = "@**all**"
            stream_mentioned_message_id = self.send_stream_message(othello, "Denmark", mention)
            handle_missedmessage_emails(
                hamlet.id,
                [{"message_id": stream_mentioned_message_id, "trigger": "wildcard_mentioned"}],
            )

        # Group mention should NOT soft reactivate the user
        with self.soft_deactivate_and_check_long_term_idle(hamlet, expected=True):
            # Soft reactivate the user by sending a personal message
            mention = "@*large_user_group*"
            stream_mentioned_message_id = self.send_stream_message(othello, "Denmark", mention)
            handle_missedmessage_emails(
                hamlet.id,
                [
                    {
                        "message_id": stream_mentioned_message_id,
                        "trigger": "mentioned",
                        "mentioned_user_group_id": large_user_group.id,
                    }
                ],
            )


class TestFollowupEmailDelay(ZulipTestCase):
    def test_followup_day2_email_delay(self) -> None:
        user_profile = self.example_user("hamlet")
        # Test date_joined == Thursday
        user_profile.date_joined = datetime(2018, 1, 4, 1, 0, 0, 0, tzinfo=timezone.utc)
        self.assertEqual(followup_day2_email_delay(user_profile), timedelta(days=1, hours=-1))
        # Test date_joined == Friday
        user_profile.date_joined = datetime(2018, 1, 5, 1, 0, 0, 0, tzinfo=timezone.utc)
        self.assertEqual(followup_day2_email_delay(user_profile), timedelta(days=3, hours=-1))


class TestCustomEmailSender(ZulipTestCase):
    def test_custom_email_sender(self) -> None:
        name = "Nonreg Email"
        email = self.nonreg_email("test")
        with override_settings(
            WELCOME_EMAIL_SENDER={
                "name": name,
                "email": email,
            }
        ):
            hamlet = self.example_user("hamlet")
            enqueue_welcome_emails(hamlet)
            scheduled_emails = ScheduledEmail.objects.filter(users=hamlet)
            email_data = orjson.loads(scheduled_emails[0].data)
            self.assertEqual(email_data["context"]["email"], self.example_email("hamlet"))
            self.assertEqual(email_data["from_name"], name)
            self.assertEqual(email_data["from_address"], email)
