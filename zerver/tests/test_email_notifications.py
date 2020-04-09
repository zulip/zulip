import ldap
import random
import re
import ujson

from django.conf import settings
from django.core import mail
from django.test import override_settings
from django_auth_ldap.config import LDAPSearch
from email.utils import formataddr
from mock import patch
from typing import List, Optional

from zerver.lib.email_notifications import fix_emojis, handle_missedmessage_emails, \
    enqueue_welcome_emails, relative_to_full_url
from zerver.lib.actions import do_change_notification_settings
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.send_email import FromAddress, send_custom_email
from zerver.models import (
    get_realm,
    get_stream,
    UserProfile,
    ScheduledEmail
)

class TestCustomEmails(ZulipTestCase):
    def test_send_custom_email_argument(self) -> None:
        hamlet = self.example_user('hamlet')
        email_subject = 'subject_test'
        reply_to = 'reply_to_test'
        from_name = "from_name_test"
        markdown_template_path = "templates/zerver/emails/email_base_default.source.html"
        send_custom_email([hamlet], {
            "markdown_template_path": markdown_template_path,
            "reply_to": reply_to,
            "subject": email_subject,
            "from_name": from_name
        })
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertEqual(msg.subject, email_subject)
        self.assertEqual(len(msg.reply_to), 1)
        self.assertEqual(msg.reply_to[0], reply_to)
        self.assertNotIn("{% block content %}", msg.body)

    def test_send_custom_email_headers(self) -> None:
        hamlet = self.example_user('hamlet')
        markdown_template_path = "zerver/tests/fixtures/email/custom_emails/email_base_headers_test.source.html"
        send_custom_email([hamlet], {
            "markdown_template_path": markdown_template_path,
        })
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertEqual(msg.subject, "Test Subject")
        self.assertFalse(msg.reply_to)
        self.assertEqual('Test body', msg.body)

    def test_send_custom_email_no_argument(self) -> None:
        hamlet = self.example_user('hamlet')
        from_name = "from_name_test"
        email_subject = 'subject_test'
        markdown_template_path = "zerver/tests/fixtures/email/custom_emails/email_base_headers_no_headers_test.source.html"

        from zerver.lib.send_email import NoEmailArgumentException
        self.assertRaises(NoEmailArgumentException, send_custom_email, [hamlet], {
            "markdown_template_path": markdown_template_path,
            "from_name": from_name
        })

        self.assertRaises(NoEmailArgumentException, send_custom_email, [hamlet], {
            "markdown_template_path": markdown_template_path,
            "subject": email_subject
        })

    def test_send_custom_email_doubled_arguments(self) -> None:
        hamlet = self.example_user('hamlet')
        from_name = "from_name_test"
        email_subject = 'subject_test'
        markdown_template_path = "zerver/tests/fixtures/email/custom_emails/email_base_headers_test.source.html"

        from zerver.lib.send_email import DoubledEmailArgumentException
        self.assertRaises(DoubledEmailArgumentException, send_custom_email, [hamlet], {
            "markdown_template_path": markdown_template_path,
            "subject": email_subject,
        })

        self.assertRaises(DoubledEmailArgumentException, send_custom_email, [hamlet], {
            "markdown_template_path": markdown_template_path,
            "from_name": from_name,
        })


class TestFollowupEmails(ZulipTestCase):
    def test_day1_email_context(self) -> None:
        hamlet = self.example_user("hamlet")
        enqueue_welcome_emails(hamlet)
        scheduled_emails = ScheduledEmail.objects.filter(users=hamlet)
        email_data = ujson.loads(scheduled_emails[0].data)
        self.assertEqual(email_data["context"]["email"], self.example_email("hamlet"))
        self.assertEqual(email_data["context"]["is_realm_admin"], False)
        self.assertEqual(email_data["context"]["getting_started_link"], "https://zulipchat.com")
        self.assertNotIn("ldap_username", email_data["context"])

        ScheduledEmail.objects.all().delete()

        iago = self.example_user("iago")
        enqueue_welcome_emails(iago)
        scheduled_emails = ScheduledEmail.objects.filter(users=iago)
        email_data = ujson.loads(scheduled_emails[0].data)
        self.assertEqual(email_data["context"]["email"], self.example_email("iago"))
        self.assertEqual(email_data["context"]["is_realm_admin"], True)
        self.assertEqual(email_data["context"]["getting_started_link"],
                         "http://zulip.testserver/help/getting-your-organization-started-with-zulip")
        self.assertNotIn("ldap_username", email_data["context"])

    # See https://zulip.readthedocs.io/en/latest/production/authentication-methods.html#ldap-including-active-directory
    # for case details.
    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',
                                                'zproject.backends.ZulipDummyBackend'),
                       # configure email search for email address in the uid attribute:
                       AUTH_LDAP_REVERSE_EMAIL_SEARCH=LDAPSearch("ou=users,dc=zulip,dc=com",
                                                                 ldap.SCOPE_ONELEVEL,
                                                                 "(uid=%(email)s)"))
    def test_day1_email_ldap_case_a_login_credentials(self) -> None:
        self.init_default_ldap_database()
        ldap_user_attr_map = {'full_name': 'cn', 'short_name': 'sn'}

        with self.settings(AUTH_LDAP_USER_ATTR_MAP=ldap_user_attr_map):
            self.login_with_return("newuser_email_as_uid@zulip.com",
                                   self.ldap_password("newuser_email_as_uid@zulip.com"))
            user = UserProfile.objects.get(delivery_email="newuser_email_as_uid@zulip.com")
            scheduled_emails = ScheduledEmail.objects.filter(users=user)

            self.assertEqual(len(scheduled_emails), 2)
            email_data = ujson.loads(scheduled_emails[0].data)
            self.assertEqual(email_data["context"]["ldap"], True)
            self.assertEqual(email_data["context"]["ldap_username"], "newuser_email_as_uid@zulip.com")

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',
                                                'zproject.backends.ZulipDummyBackend'))
    def test_day1_email_ldap_case_b_login_credentials(self) -> None:
        self.init_default_ldap_database()
        ldap_user_attr_map = {'full_name': 'cn', 'short_name': 'sn'}

        with self.settings(
                LDAP_APPEND_DOMAIN='zulip.com',
                AUTH_LDAP_USER_ATTR_MAP=ldap_user_attr_map,
        ):
            self.login_with_return("newuser@zulip.com", self.ldap_password("newuser"))

            user = UserProfile.objects.get(delivery_email="newuser@zulip.com")
            scheduled_emails = ScheduledEmail.objects.filter(users=user)

            self.assertEqual(len(scheduled_emails), 2)
            email_data = ujson.loads(scheduled_emails[0].data)
            self.assertEqual(email_data["context"]["ldap"], True)
            self.assertEqual(email_data["context"]["ldap_username"], "newuser")

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',
                                                'zproject.backends.ZulipDummyBackend'))
    def test_day1_email_ldap_case_c_login_credentials(self) -> None:
        self.init_default_ldap_database()
        ldap_user_attr_map = {'full_name': 'cn', 'short_name': 'sn'}

        with self.settings(
                LDAP_EMAIL_ATTR='mail',
                AUTH_LDAP_USER_ATTR_MAP=ldap_user_attr_map,
        ):
            self.login_with_return("newuser_with_email", self.ldap_password("newuser_with_email"))
            user = UserProfile.objects.get(delivery_email="newuser_email@zulip.com")
            scheduled_emails = ScheduledEmail.objects.filter(users=user)

            self.assertEqual(len(scheduled_emails), 2)
            email_data = ujson.loads(scheduled_emails[0].data)
            self.assertEqual(email_data["context"]["ldap"], True)
            self.assertEqual(email_data["context"]["ldap_username"], "newuser_with_email")

    def test_followup_emails_count(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")

        enqueue_welcome_emails(self.example_user("hamlet"))
        # Hamlet has account only in Zulip realm so both day1 and day2 emails should be sent
        scheduled_emails = ScheduledEmail.objects.filter(users=hamlet).order_by(
            "scheduled_timestamp")
        self.assertEqual(2, len(scheduled_emails))
        self.assertEqual(ujson.loads(scheduled_emails[1].data)["template_prefix"], 'zerver/emails/followup_day2')
        self.assertEqual(ujson.loads(scheduled_emails[0].data)["template_prefix"], 'zerver/emails/followup_day1')

        ScheduledEmail.objects.all().delete()

        enqueue_welcome_emails(cordelia)
        scheduled_emails = ScheduledEmail.objects.filter(users=cordelia)
        # Cordelia has account in more than 1 realm so day2 email should not be sent
        self.assertEqual(len(scheduled_emails), 1)
        email_data = ujson.loads(scheduled_emails[0].data)
        self.assertEqual(email_data["template_prefix"], 'zerver/emails/followup_day1')

class TestMissedMessages(ZulipTestCase):
    def normalize_string(self, s: str) -> str:
        s = s.strip()
        return re.sub(r'\s+', ' ', s)

    def _get_tokens(self) -> List[str]:
        return ['mm' + str(random.getrandbits(32)) for _ in range(30)]

    def _test_cases(self, msg_id: int, verify_body_include: List[str], email_subject: str,
                    send_as_user: bool, verify_html_body: bool=False,
                    show_message_content: bool=True,
                    verify_body_does_not_include: Optional[List[str]]=None,
                    trigger: str='') -> None:
        othello = self.example_user('othello')
        hamlet = self.example_user('hamlet')
        tokens = self._get_tokens()
        with patch('zerver.lib.email_mirror.generate_missed_message_token', side_effect=tokens):
            handle_missedmessage_emails(hamlet.id, [{'message_id': msg_id, 'trigger': trigger}])
        if settings.EMAIL_GATEWAY_PATTERN != "":
            reply_to_addresses = [settings.EMAIL_GATEWAY_PATTERN % (t,) for t in tokens]
            reply_to_emails = [formataddr(("Zulip", address)) for address in reply_to_addresses]
        else:
            reply_to_emails = ["noreply@testserver"]
        msg = mail.outbox[0]
        from_email = formataddr(("Zulip missed messages", FromAddress.NOREPLY))
        self.assertEqual(len(mail.outbox), 1)
        if send_as_user:
            from_email = '"%s" <%s>' % (othello.full_name, othello.email)
        self.assertEqual(msg.from_email, from_email)
        self.assertEqual(msg.subject, email_subject)
        self.assertEqual(len(msg.reply_to), 1)
        self.assertIn(msg.reply_to[0], reply_to_emails)
        if verify_html_body:
            for text in verify_body_include:
                self.assertIn(text, self.normalize_string(msg.alternatives[0][0]))
        else:
            for text in verify_body_include:
                self.assertIn(text, self.normalize_string(msg.body))
        if verify_body_does_not_include is not None:
            for text in verify_body_does_not_include:
                self.assertNotIn(text, self.normalize_string(msg.body))

    def _realm_name_in_missed_message_email_subject(self, realm_name_in_notifications: bool) -> None:
        msg_id = self.send_personal_message(
            self.example_user('othello'),
            self.example_user('hamlet'),
            'Extremely personal message!',
        )
        verify_body_include = ['Extremely personal message!']
        email_subject = 'PMs with Othello, the Moor of Venice'

        if realm_name_in_notifications:
            email_subject = 'PMs with Othello, the Moor of Venice [Zulip Dev]'
        self._test_cases(msg_id, verify_body_include, email_subject, False)

    def _extra_context_in_missed_stream_messages_mention(self, send_as_user: bool,
                                                         show_message_content: bool=True) -> None:
        for i in range(0, 11):
            self.send_stream_message(self.example_user('othello'), "Denmark", content=str(i))
        self.send_stream_message(
            self.example_user('othello'), "Denmark",
            '11', topic_name='test2')
        msg_id = self.send_stream_message(
            self.example_user('othello'), "denmark",
            '@**King Hamlet**')

        if show_message_content:
            verify_body_include = [
                "Othello, the Moor of Venice: 1 2 3 4 5 6 7 8 9 10 @**King Hamlet** -- ",
                "You are receiving this because you were mentioned in Zulip Dev."
            ]
            email_subject = '#Denmark > test'
            verify_body_does_not_include = []  # type: List[str]
        else:
            # Test in case if message content in missed email message are disabled.
            verify_body_include = [
                "This email does not include message content because you have disabled message ",
                "http://zulip.testserver/help/pm-mention-alert-notifications ",
                "View or reply in Zulip",
                " Manage email preferences: http://zulip.testserver/#settings/notifications"
            ]

            email_subject = 'New missed messages'
            verify_body_does_not_include = ['Denmark > test', 'Othello, the Moor of Venice',
                                            '1 2 3 4 5 6 7 8 9 10 @**King Hamlet**', 'private', 'group',
                                            'Reply to this email directly, or view it in Zulip']
        self._test_cases(msg_id, verify_body_include, email_subject, send_as_user,
                         show_message_content=show_message_content,
                         verify_body_does_not_include=verify_body_does_not_include,
                         trigger='mentioned')

    def _extra_context_in_missed_stream_messages_wildcard_mention(self, send_as_user: bool,
                                                                  show_message_content: bool=True) -> None:
        for i in range(1, 6):
            self.send_stream_message(self.example_user('othello'), "Denmark", content=str(i))
        self.send_stream_message(
            self.example_user('othello'), "Denmark",
            '11', topic_name='test2')
        msg_id = self.send_stream_message(
            self.example_user('othello'), "denmark",
            '@**all**')

        if show_message_content:
            verify_body_include = [
                "Othello, the Moor of Venice: 1 2 3 4 5 @**all** -- ",
                "You are receiving this because you were mentioned in Zulip Dev."
            ]
            email_subject = '#Denmark > test'
            verify_body_does_not_include = []  # type: List[str]
        else:
            # Test in case if message content in missed email message are disabled.
            verify_body_include = [
                "This email does not include message content because you have disabled message ",
                "http://zulip.testserver/help/pm-mention-alert-notifications ",
                "View or reply in Zulip",
                " Manage email preferences: http://zulip.testserver/#settings/notifications"
            ]
            email_subject = 'New missed messages'
            verify_body_does_not_include = ['Denmark > test', 'Othello, the Moor of Venice',
                                            '1 2 3 4 5 @**all**', 'private', 'group',
                                            'Reply to this email directly, or view it in Zulip']
        self._test_cases(msg_id, verify_body_include, email_subject, send_as_user,
                         show_message_content=show_message_content,
                         verify_body_does_not_include=verify_body_does_not_include,
                         trigger='wildcard_mentioned')

    def _extra_context_in_missed_stream_messages_email_notify(self, send_as_user: bool) -> None:
        for i in range(0, 11):
            self.send_stream_message(self.example_user('othello'), "Denmark", content=str(i))
        self.send_stream_message(
            self.example_user('othello'), "Denmark",
            '11', topic_name='test2')
        msg_id = self.send_stream_message(
            self.example_user('othello'), "denmark",
            '12')
        verify_body_include = [
            "Othello, the Moor of Venice: 1 2 3 4 5 6 7 8 9 10 12 -- ",
            "You are receiving this because you have email notifications enabled for this stream."
        ]
        email_subject = '#Denmark > test'
        self._test_cases(msg_id, verify_body_include, email_subject, send_as_user, trigger='stream_email_notify')

    def _extra_context_in_missed_stream_messages_mention_two_senders(self, send_as_user: bool) -> None:
        for i in range(0, 3):
            self.send_stream_message(self.example_user('cordelia'), "Denmark", str(i))
        msg_id = self.send_stream_message(
            self.example_user('othello'), "Denmark",
            '@**King Hamlet**')
        verify_body_include = [
            "Cordelia Lear: 0 1 2 Othello, the Moor of Venice: @**King Hamlet** -- ",
            "You are receiving this because you were mentioned in Zulip Dev."
        ]
        email_subject = '#Denmark > test'
        self._test_cases(msg_id, verify_body_include, email_subject, send_as_user, trigger='mentioned')

    def _extra_context_in_personal_missed_stream_messages(self, send_as_user: bool,
                                                          show_message_content: bool=True,
                                                          message_content_disabled_by_user: bool=False,
                                                          message_content_disabled_by_realm: bool=False) -> None:
        msg_id = self.send_personal_message(
            self.example_user('othello'),
            self.example_user('hamlet'),
            'Extremely personal message!',
        )

        if show_message_content:
            verify_body_include = ['Extremely personal message!']
            email_subject = 'PMs with Othello, the Moor of Venice'
            verify_body_does_not_include = []  # type: List[str]
        else:
            if message_content_disabled_by_realm:
                verify_body_include = [
                    "This email does not include message content because your organization has disabled",
                    "http://zulip.testserver/help/hide-message-content-in-emails",
                    "View or reply in Zulip",
                    " Manage email preferences: http://zulip.testserver/#settings/notifications"
                ]
            elif message_content_disabled_by_user:
                verify_body_include = [
                    "This email does not include message content because you have disabled message ",
                    "http://zulip.testserver/help/pm-mention-alert-notifications ",
                    "View or reply in Zulip",
                    " Manage email preferences: http://zulip.testserver/#settings/notifications"
                ]
            email_subject = 'New missed messages'
            verify_body_does_not_include = ['Othello, the Moor of Venice', 'Extremely personal message!',
                                            'mentioned', 'group', 'Reply to this email directly, or view it in Zulip']
        self._test_cases(msg_id, verify_body_include, email_subject, send_as_user,
                         show_message_content=show_message_content,
                         verify_body_does_not_include=verify_body_does_not_include)

    def _reply_to_email_in_personal_missed_stream_messages(self, send_as_user: bool) -> None:
        msg_id = self.send_personal_message(
            self.example_user('othello'),
            self.example_user('hamlet'),
            'Extremely personal message!',
        )
        verify_body_include = ['Reply to this email directly, or view it in Zulip']
        email_subject = 'PMs with Othello, the Moor of Venice'
        self._test_cases(msg_id, verify_body_include, email_subject, send_as_user)

    def _reply_warning_in_personal_missed_stream_messages(self, send_as_user: bool) -> None:
        msg_id = self.send_personal_message(
            self.example_user('othello'),
            self.example_user('hamlet'),
            'Extremely personal message!',
        )
        verify_body_include = ['Do not reply to this email.']
        email_subject = 'PMs with Othello, the Moor of Venice'
        self._test_cases(msg_id, verify_body_include, email_subject, send_as_user)

    def _extra_context_in_huddle_missed_stream_messages_two_others(self, send_as_user: bool,
                                                                   show_message_content: bool=True) -> None:
        msg_id = self.send_huddle_message(
            self.example_user('othello'),
            [
                self.example_user('hamlet'),
                self.example_user('iago'),
            ],
            'Group personal message!',
        )

        if show_message_content:
            verify_body_include = ['Othello, the Moor of Venice: Group personal message! -- Reply']
            email_subject = 'Group PMs with Iago and Othello, the Moor of Venice'
            verify_body_does_not_include = []  # type: List[str]
        else:
            verify_body_include = [
                "This email does not include message content because you have disabled message ",
                "http://zulip.testserver/help/pm-mention-alert-notifications ",
                "View or reply in Zulip",
                " Manage email preferences: http://zulip.testserver/#settings/notifications"
            ]
            email_subject = 'New missed messages'
            verify_body_does_not_include = ['Iago', 'Othello, the Moor of Venice Othello, the Moor of Venice',
                                            'Group personal message!', 'mentioned',
                                            'Reply to this email directly, or view it in Zulip']
        self._test_cases(msg_id, verify_body_include, email_subject, send_as_user,
                         show_message_content=show_message_content,
                         verify_body_does_not_include=verify_body_does_not_include)

    def _extra_context_in_huddle_missed_stream_messages_three_others(self, send_as_user: bool) -> None:
        msg_id = self.send_huddle_message(
            self.example_user('othello'),
            [
                self.example_user('hamlet'),
                self.example_user('iago'),
                self.example_user('cordelia'),
            ],
            'Group personal message!',
        )

        verify_body_include = ['Othello, the Moor of Venice: Group personal message! -- Reply']
        email_subject = 'Group PMs with Cordelia Lear, Iago, and Othello, the Moor of Venice'
        self._test_cases(msg_id, verify_body_include, email_subject, send_as_user)

    def _extra_context_in_huddle_missed_stream_messages_many_others(self, send_as_user: bool) -> None:
        msg_id = self.send_huddle_message(self.example_user('othello'),
                                          [self.example_user('hamlet'),
                                           self.example_user('iago'),
                                           self.example_user('cordelia'),
                                           self.example_user('prospero')],
                                          'Group personal message!')

        verify_body_include = ['Othello, the Moor of Venice: Group personal message! -- Reply']
        email_subject = 'Group PMs with Cordelia Lear, Iago, and 2 others'
        self._test_cases(msg_id, verify_body_include, email_subject, send_as_user)

    def _deleted_message_in_missed_stream_messages(self, send_as_user: bool) -> None:
        msg_id = self.send_stream_message(
            self.example_user('othello'), "denmark",
            '@**King Hamlet** to be deleted')

        hamlet = self.example_user('hamlet')
        self.login('othello')
        result = self.client_patch('/json/messages/' + str(msg_id),
                                   {'message_id': msg_id, 'content': ' '})
        self.assert_json_success(result)
        handle_missedmessage_emails(hamlet.id, [{'message_id': msg_id}])
        self.assertEqual(len(mail.outbox), 0)

    def _deleted_message_in_personal_missed_stream_messages(self, send_as_user: bool) -> None:
        msg_id = self.send_personal_message(self.example_user('othello'),
                                            self.example_user('hamlet'),
                                            'Extremely personal message! to be deleted!')

        hamlet = self.example_user('hamlet')
        self.login('othello')
        result = self.client_patch('/json/messages/' + str(msg_id),
                                   {'message_id': msg_id, 'content': ' '})
        self.assert_json_success(result)
        handle_missedmessage_emails(hamlet.id, [{'message_id': msg_id}])
        self.assertEqual(len(mail.outbox), 0)

    def _deleted_message_in_huddle_missed_stream_messages(self, send_as_user: bool) -> None:
        msg_id = self.send_huddle_message(
            self.example_user('othello'),
            [
                self.example_user('hamlet'),
                self.example_user('iago'),
            ],
            'Group personal message!',
        )

        hamlet = self.example_user('hamlet')
        iago = self.example_user('iago')
        self.login('othello')
        result = self.client_patch('/json/messages/' + str(msg_id),
                                   {'message_id': msg_id, 'content': ' '})
        self.assert_json_success(result)
        handle_missedmessage_emails(hamlet.id, [{'message_id': msg_id}])
        self.assertEqual(len(mail.outbox), 0)
        handle_missedmessage_emails(iago.id, [{'message_id': msg_id}])
        self.assertEqual(len(mail.outbox), 0)

    def test_realm_name_in_notifications(self) -> None:
        # Test with realm_name_in_notifications for hamlet disabled.
        self._realm_name_in_missed_message_email_subject(False)

        # Enable realm_name_in_notifications for hamlet and test again.
        hamlet = self.example_user('hamlet')
        hamlet.realm_name_in_notifications = True
        hamlet.save(update_fields=['realm_name_in_notifications'])

        # Empty the test outbox
        mail.outbox = []
        self._realm_name_in_missed_message_email_subject(True)

    def test_message_content_disabled_in_missed_message_notifications(self) -> None:
        # Test when user disabled message content in email notifications.
        do_change_notification_settings(self.example_user("hamlet"),
                                        "message_content_in_email_notifications", False)
        self._extra_context_in_missed_stream_messages_mention(False, show_message_content=False)
        mail.outbox = []
        self._extra_context_in_missed_stream_messages_wildcard_mention(False, show_message_content=False)
        mail.outbox = []
        self._extra_context_in_personal_missed_stream_messages(False, show_message_content=False,
                                                               message_content_disabled_by_user=True)
        mail.outbox = []
        self._extra_context_in_huddle_missed_stream_messages_two_others(False, show_message_content=False)

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

    def test_reply_to_email_in_personal_missed_stream_messages(self) -> None:
        self._reply_to_email_in_personal_missed_stream_messages(False)

    @override_settings(SEND_MISSED_MESSAGE_EMAILS_AS_USER=True)
    def test_extra_context_in_missed_stream_messages_email_notify_as_user(self) -> None:
        self._extra_context_in_missed_stream_messages_email_notify(True)

    def test_extra_context_in_missed_stream_messages_email_notify(self) -> None:
        self._extra_context_in_missed_stream_messages_email_notify(False)

    @override_settings(EMAIL_GATEWAY_PATTERN="")
    def test_reply_warning_in_personal_missed_stream_messages(self) -> None:
        self._reply_warning_in_personal_missed_stream_messages(False)

    @override_settings(SEND_MISSED_MESSAGE_EMAILS_AS_USER=True)
    def test_extra_context_in_personal_missed_stream_messages_as_user(self) -> None:
        self._extra_context_in_personal_missed_stream_messages(True)

    def test_extra_context_in_personal_missed_stream_messages(self) -> None:
        self._extra_context_in_personal_missed_stream_messages(False)

    @override_settings(SEND_MISSED_MESSAGE_EMAILS_AS_USER=True)
    def test_extra_context_in_huddle_missed_stream_messages_two_others_as_user(self) -> None:
        self._extra_context_in_huddle_missed_stream_messages_two_others(True)

    def test_extra_context_in_huddle_missed_stream_messages_two_others(self) -> None:
        self._extra_context_in_huddle_missed_stream_messages_two_others(False)

    @override_settings(SEND_MISSED_MESSAGE_EMAILS_AS_USER=True)
    def test_extra_context_in_huddle_missed_stream_messages_three_others_as_user(self) -> None:
        self._extra_context_in_huddle_missed_stream_messages_three_others(True)

    def test_extra_context_in_huddle_missed_stream_messages_three_others(self) -> None:
        self._extra_context_in_huddle_missed_stream_messages_three_others(False)

    @override_settings(SEND_MISSED_MESSAGE_EMAILS_AS_USER=True)
    def test_extra_context_in_huddle_missed_stream_messages_many_others_as_user(self) -> None:
        self._extra_context_in_huddle_missed_stream_messages_many_others(True)

    def test_extra_context_in_huddle_missed_stream_messages_many_others(self) -> None:
        self._extra_context_in_huddle_missed_stream_messages_many_others(False)

    @override_settings(SEND_MISSED_MESSAGE_EMAILS_AS_USER=True)
    def test_deleted_message_in_missed_stream_messages_as_user(self) -> None:
        self._deleted_message_in_missed_stream_messages(True)

    def test_deleted_message_in_missed_stream_messages(self) -> None:
        self._deleted_message_in_missed_stream_messages(False)

    @override_settings(SEND_MISSED_MESSAGE_EMAILS_AS_USER=True)
    def test_deleted_message_in_personal_missed_stream_messages_as_user(self) -> None:
        self._deleted_message_in_personal_missed_stream_messages(True)

    def test_deleted_message_in_personal_missed_stream_messages(self) -> None:
        self._deleted_message_in_personal_missed_stream_messages(False)

    @override_settings(SEND_MISSED_MESSAGE_EMAILS_AS_USER=True)
    def test_deleted_message_in_huddle_missed_stream_messages_as_user(self) -> None:
        self._deleted_message_in_huddle_missed_stream_messages(True)

    def test_deleted_message_in_huddle_missed_stream_messages(self) -> None:
        self._deleted_message_in_huddle_missed_stream_messages(False)

    def test_realm_message_content_allowed_in_email_notifications(self) -> None:
        user = self.example_user("hamlet")

        # When message content is allowed at realm level
        realm = get_realm("zulip")
        realm.message_content_allowed_in_email_notifications = True
        realm.save(update_fields=['message_content_allowed_in_email_notifications'])

        # Emails have missed message content when message content is enabled by the user
        do_change_notification_settings(user, "message_content_in_email_notifications", True)
        mail.outbox = []
        self._extra_context_in_personal_missed_stream_messages(False, show_message_content=True)

        # Emails don't have missed message content when message content is disabled by the user
        do_change_notification_settings(user, "message_content_in_email_notifications", False)
        mail.outbox = []
        self._extra_context_in_personal_missed_stream_messages(False, show_message_content=False,
                                                               message_content_disabled_by_user=True)

        # When message content is not allowed at realm level
        # Emails don't have missed message irrespective of message content setting of the user
        realm = get_realm("zulip")
        realm.message_content_allowed_in_email_notifications = False
        realm.save(update_fields=['message_content_allowed_in_email_notifications'])

        do_change_notification_settings(user, "message_content_in_email_notifications", True)
        mail.outbox = []
        self._extra_context_in_personal_missed_stream_messages(False, show_message_content=False,
                                                               message_content_disabled_by_realm=True)

        do_change_notification_settings(user, "message_content_in_email_notifications", False)
        mail.outbox = []
        self._extra_context_in_personal_missed_stream_messages(False, show_message_content=False,
                                                               message_content_disabled_by_user=True,
                                                               message_content_disabled_by_realm=True)

    def test_realm_emoji_in_missed_message(self) -> None:
        realm = get_realm("zulip")

        msg_id = self.send_personal_message(
            self.example_user('othello'), self.example_user('hamlet'),
            'Extremely personal message with a realm emoji :green_tick:!')
        realm_emoji_id = realm.get_active_emoji()['green_tick']['id']
        realm_emoji_url = "http://zulip.testserver/user_avatars/%s/emoji/images/%s.png" % (
            realm.id, realm_emoji_id,)
        verify_body_include = ['<img alt=":green_tick:" src="%s" title="green tick" style="height: 20px;">' % (realm_emoji_url,)]
        email_subject = 'PMs with Othello, the Moor of Venice'
        self._test_cases(msg_id, verify_body_include, email_subject, send_as_user=False, verify_html_body=True)

    def test_emojiset_in_missed_message(self) -> None:
        hamlet = self.example_user('hamlet')
        hamlet.emojiset = 'twitter'
        hamlet.save(update_fields=['emojiset'])
        msg_id = self.send_personal_message(
            self.example_user('othello'), self.example_user('hamlet'),
            'Extremely personal message with a hamburger :hamburger:!')
        verify_body_include = ['<img alt=":hamburger:" src="http://zulip.testserver/static/generated/emoji/images-twitter-64/1f354.png" title="hamburger" style="height: 20px;">']
        email_subject = 'PMs with Othello, the Moor of Venice'
        self._test_cases(msg_id, verify_body_include, email_subject, send_as_user=False, verify_html_body=True)

    def test_stream_link_in_missed_message(self) -> None:
        msg_id = self.send_personal_message(
            self.example_user('othello'), self.example_user('hamlet'),
            'Come and join us in #**Verona**.')
        stream_id = get_stream('Verona', get_realm('zulip')).id
        href = "http://zulip.testserver/#narrow/stream/{stream_id}-Verona".format(stream_id=stream_id)
        verify_body_include = ['<a class="stream" data-stream-id="5" href="{href}">#Verona</a'.format(href=href)]
        email_subject = 'PMs with Othello, the Moor of Venice'
        self._test_cases(msg_id, verify_body_include, email_subject, send_as_user=False, verify_html_body=True)

    def test_sender_name_in_missed_message(self) -> None:
        hamlet = self.example_user('hamlet')
        msg_id_1 = self.send_stream_message(self.example_user('iago'),
                                            "Denmark",
                                            '@**King Hamlet**')
        msg_id_2 = self.send_stream_message(self.example_user('iago'),
                                            "Verona",
                                            '* 1\n *2')
        msg_id_3 = self.send_personal_message(self.example_user('iago'),
                                              hamlet,
                                              'Hello')

        handle_missedmessage_emails(hamlet.id, [
            {'message_id': msg_id_1, "trigger": "mentioned"},
            {'message_id': msg_id_2, "trigger": "stream_email_notify"},
            {'message_id': msg_id_3},
        ])

        self.assertIn('Iago: @**King Hamlet**\n\n--\nYou are', mail.outbox[0].body)
        # If message content starts with <p> tag the sender name is appended inside the <p> tag.
        self.assertIn('<p><b>Iago</b>: <span class="user-mention"', mail.outbox[0].alternatives[0][0])

        self.assertIn('Iago: * 1\n *2\n\n--\nYou are receiving', mail.outbox[1].body)
        # If message content does not starts with <p> tag sender name is appended before the <p> tag
        self.assertIn('       <b>Iago</b>: <ul>\n<li>1<br/>\n *2</li>\n</ul>\n',
                      mail.outbox[1].alternatives[0][0])

        self.assertEqual('Hello\n\n--\n\nReply', mail.outbox[2].body[:16])
        # Sender name is not appended to message for PM missed messages
        self.assertIn('>\n                    \n                        <p>Hello</p>\n',
                      mail.outbox[2].alternatives[0][0])

    def test_multiple_missed_personal_messages(self) -> None:
        hamlet = self.example_user('hamlet')
        msg_id_1 = self.send_personal_message(self.example_user('othello'),
                                              hamlet,
                                              'Personal Message 1')
        msg_id_2 = self.send_personal_message(self.example_user('iago'),
                                              hamlet,
                                              'Personal Message 2')

        handle_missedmessage_emails(hamlet.id, [
            {'message_id': msg_id_1},
            {'message_id': msg_id_2},
        ])
        self.assertEqual(len(mail.outbox), 2)
        email_subject = 'PMs with Othello, the Moor of Venice'
        self.assertEqual(mail.outbox[0].subject, email_subject)
        email_subject = 'PMs with Iago'
        self.assertEqual(mail.outbox[1].subject, email_subject)

    def test_multiple_stream_messages(self) -> None:
        hamlet = self.example_user('hamlet')
        msg_id_1 = self.send_stream_message(self.example_user('othello'),
                                            "Denmark",
                                            'Message1')
        msg_id_2 = self.send_stream_message(self.example_user('iago'),
                                            "Denmark",
                                            'Message2')

        handle_missedmessage_emails(hamlet.id, [
            {'message_id': msg_id_1, "trigger": "stream_email_notify"},
            {'message_id': msg_id_2, "trigger": "stream_email_notify"},
        ])
        self.assertEqual(len(mail.outbox), 1)
        email_subject = '#Denmark > test'
        self.assertEqual(mail.outbox[0].subject, email_subject)

    def test_multiple_stream_messages_and_mentions(self) -> None:
        """Subject should be stream name and topic as usual."""
        hamlet = self.example_user('hamlet')
        msg_id_1 = self.send_stream_message(self.example_user('iago'),
                                            "Denmark",
                                            'Regular message')
        msg_id_2 = self.send_stream_message(self.example_user('othello'),
                                            "Denmark",
                                            '@**King Hamlet**')

        handle_missedmessage_emails(hamlet.id, [
            {'message_id': msg_id_1, "trigger": "stream_email_notify"},
            {'message_id': msg_id_2, "trigger": "mentioned"},
        ])
        self.assertEqual(len(mail.outbox), 1)
        email_subject = '#Denmark > test'
        self.assertEqual(mail.outbox[0].subject, email_subject)

    def test_message_access_in_emails(self) -> None:
        # Messages sent to a protected history-private stream shouldn't be
        # accessible/available in emails before subscribing
        stream_name = "private_stream"
        self.make_stream(stream_name, invite_only=True,
                         history_public_to_subscribers=False)
        user = self.example_user('iago')
        self.subscribe(user, stream_name)
        late_subscribed_user = self.example_user('hamlet')

        self.send_stream_message(user,
                                 stream_name,
                                 'Before subscribing')

        self.subscribe(late_subscribed_user, stream_name)

        self.send_stream_message(user,
                                 stream_name,
                                 "After subscribing")

        mention_msg_id = self.send_stream_message(user,
                                                  stream_name,
                                                  '@**King Hamlet**')

        handle_missedmessage_emails(late_subscribed_user.id, [
            {'message_id': mention_msg_id, "trigger": "mentioned"},
        ])

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, '#private_stream > test')  # email subject
        email_text = mail.outbox[0].message().as_string()
        self.assertNotIn('Before subscribing', email_text)
        self.assertIn('After subscribing', email_text)
        self.assertIn('@**King Hamlet**', email_text)

    def test_stream_mentions_multiple_people(self) -> None:
        """Subject should be stream name and topic as usual."""
        hamlet = self.example_user('hamlet')
        msg_id_1 = self.send_stream_message(self.example_user('iago'),
                                            "Denmark",
                                            '@**King Hamlet**')
        msg_id_2 = self.send_stream_message(self.example_user('othello'),
                                            "Denmark",
                                            '@**King Hamlet**')
        msg_id_3 = self.send_stream_message(self.example_user('cordelia'),
                                            "Denmark",
                                            'Regular message')

        handle_missedmessage_emails(hamlet.id, [
            {'message_id': msg_id_1, "trigger": "mentioned"},
            {'message_id': msg_id_2, "trigger": "mentioned"},
            {'message_id': msg_id_3, "trigger": "stream_email_notify"},
        ])
        self.assertEqual(len(mail.outbox), 1)
        email_subject = '#Denmark > test'
        self.assertEqual(mail.outbox[0].subject, email_subject)

    def test_multiple_stream_messages_different_topics(self) -> None:
        """Should receive separate emails for each topic within a stream."""
        hamlet = self.example_user('hamlet')
        msg_id_1 = self.send_stream_message(self.example_user('othello'),
                                            "Denmark",
                                            'Message1')
        msg_id_2 = self.send_stream_message(self.example_user('iago'),
                                            "Denmark",
                                            'Message2',
                                            topic_name="test2")

        handle_missedmessage_emails(hamlet.id, [
            {'message_id': msg_id_1, "trigger": "stream_email_notify"},
            {'message_id': msg_id_2, "trigger": "stream_email_notify"},
        ])
        self.assertEqual(len(mail.outbox), 2)
        email_subjects = {mail.outbox[0].subject, mail.outbox[1].subject}
        valid_email_subjects = {'#Denmark > test', '#Denmark > test2'}
        self.assertEqual(email_subjects, valid_email_subjects)

    def test_relative_to_full_url(self) -> None:
        zulip_realm = get_realm("zulip")
        zephyr_realm = get_realm("zephyr")
        # Run `relative_to_full_url()` function over test fixtures present in
        # 'markdown_test_cases.json' and check that it converts all the relative
        # URLs to absolute URLs.
        fixtures = ujson.loads(self.fixture_data("markdown_test_cases.json"))
        test_fixtures = {}
        for test in fixtures['regular_tests']:
            test_fixtures[test['name']] = test
        for test_name in test_fixtures:
            test_data = test_fixtures[test_name]["expected_output"]
            output_data = relative_to_full_url("http://example.com", test_data)
            if re.search(r"""(?<=\=['"])/(?=[^<]+>)""", output_data) is not None:
                raise AssertionError("Relative URL present in email: " + output_data +
                                     "\nFailed test case's name is: " + test_name +
                                     "\nIt is present in markdown_test_cases.json")

        # Specific test cases.

        # A path similar to our emoji path, but not in a link:
        test_data = "<p>Check out the file at: '/static/generated/emoji/images/emoji/'</p>"
        actual_output = relative_to_full_url("http://example.com", test_data)
        expected_output = "<p>Check out the file at: '/static/generated/emoji/images/emoji/'</p>"
        self.assertEqual(actual_output, expected_output)

        # An uploaded file
        test_data = '<a href="/user_uploads/{realm_id}/1f/some_random_value">/user_uploads/{realm_id}/1f/some_random_value</a>'
        test_data = test_data.format(realm_id=zephyr_realm.id)
        actual_output = relative_to_full_url("http://example.com", test_data)
        expected_output = '<a href="http://example.com/user_uploads/{realm_id}/1f/some_random_value">' + \
            '/user_uploads/{realm_id}/1f/some_random_value</a>'
        expected_output = expected_output.format(realm_id=zephyr_realm.id)
        self.assertEqual(actual_output, expected_output)

        # A profile picture like syntax, but not actually in an HTML tag
        test_data = '<p>Set src="/avatar/username@example.com?s=30"</p>'
        actual_output = relative_to_full_url("http://example.com", test_data)
        expected_output = '<p>Set src="/avatar/username@example.com?s=30"</p>'
        self.assertEqual(actual_output, expected_output)

        # A narrow URL which begins with a '#'.
        test_data = '<p><a href="#narrow/stream/test/topic/test.20topic/near/142"' +  \
                    'title="#narrow/stream/test/topic/test.20topic/near/142">Conversation</a></p>'
        actual_output = relative_to_full_url("http://example.com", test_data)
        expected_output = '<p><a href="http://example.com/#narrow/stream/test/topic/test.20topic/near/142" ' + \
                          'title="http://example.com/#narrow/stream/test/topic/test.20topic/near/142">Conversation</a></p>'
        self.assertEqual(actual_output, expected_output)

        # Scrub inline images.
        test_data = '<p>See this <a href="/user_uploads/{realm_id}/52/fG7GM9e3afz_qsiUcSce2tl_/avatar_103.jpeg" target="_blank" ' +   \
                    'title="avatar_103.jpeg">avatar_103.jpeg</a>.</p>' +    \
                    '<div class="message_inline_image"><a href="/user_uploads/{realm_id}/52/fG7GM9e3afz_qsiUcSce2tl_/avatar_103.jpeg" ' +    \
                    'target="_blank" title="avatar_103.jpeg"><img src="/user_uploads/{realm_id}/52/fG7GM9e3afz_qsiUcSce2tl_/avatar_103.jpeg"></a></div>'
        test_data = test_data.format(realm_id=zulip_realm.id)
        actual_output = relative_to_full_url("http://example.com", test_data)
        expected_output = '<div><p>See this <a href="http://example.com/user_uploads/{realm_id}/52/fG7GM9e3afz_qsiUcSce2tl_/avatar_103.jpeg" target="_blank" ' +  \
                          'title="avatar_103.jpeg">avatar_103.jpeg</a>.</p></div>'
        expected_output = expected_output.format(realm_id=zulip_realm.id)
        self.assertEqual(actual_output, expected_output)

        # A message containing only an inline image URL preview, we do
        # somewhat more extensive surgery.
        test_data = '<div class="message_inline_image"><a href="https://www.google.com/images/srpr/logo4w.png" ' + \
                    'target="_blank" title="https://www.google.com/images/srpr/logo4w.png">' + \
                    '<img data-src-fullsize="/thumbnail/https%3A//www.google.com/images/srpr/logo4w.png?size=0x0" ' + \
                    'src="/thumbnail/https%3A//www.google.com/images/srpr/logo4w.png?size=0x100"></a></div>'
        actual_output = relative_to_full_url("http://example.com", test_data)
        expected_output = '<p><a href="https://www.google.com/images/srpr/logo4w.png" ' + \
                          'target="_blank" title="https://www.google.com/images/srpr/logo4w.png">' + \
                          'https://www.google.com/images/srpr/logo4w.png</a></p>'
        self.assertEqual(actual_output, expected_output)

    def test_fix_emoji(self) -> None:
        # An emoji.
        test_data = '<p>See <span aria-label="cloud with lightning and rain" class="emoji emoji-26c8" role="img" title="cloud with lightning and rain">' + \
                    ':cloud_with_lightning_and_rain:</span>.</p>'
        actual_output = fix_emojis(test_data, "http://example.com", "google")
        expected_output = '<p>See <img alt=":cloud_with_lightning_and_rain:" src="http://example.com/static/generated/emoji/images-google-64/26c8.png" ' + \
                          'title="cloud with lightning and rain" style="height: 20px;">.</p>'
        self.assertEqual(actual_output, expected_output)
