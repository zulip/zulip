import random
import re
import ujson
import ldap

from django.conf import settings
from django.core import mail
from django.test import override_settings
from django_auth_ldap.config import LDAPSearch
from email.utils import formataddr
from mock import patch, MagicMock
from typing import List, Optional

from zerver.lib.notifications import fix_emojis, handle_missedmessage_emails, \
    enqueue_welcome_emails, relative_to_full_url
from zerver.lib.actions import do_change_notification_settings
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.send_email import FromAddress
from zerver.lib.test_helpers import MockLDAP
from zerver.models import (
    get_realm,
    get_stream,
    UserProfile,
    ScheduledEmail
)

class TestFollowupEmails(ZulipTestCase):
    def test_day1_email_context(self) -> None:
        hamlet = self.example_user("hamlet")
        enqueue_welcome_emails(hamlet)
        scheduled_emails = ScheduledEmail.objects.filter(user=hamlet)
        email_data = ujson.loads(scheduled_emails[0].data)
        self.assertEqual(email_data["context"]["email"], self.example_email("hamlet"))
        self.assertEqual(email_data["context"]["is_realm_admin"], False)
        self.assertEqual(email_data["context"]["getting_started_link"], "https://zulipchat.com")
        self.assertNotIn("ldap_username", email_data["context"])

        ScheduledEmail.objects.all().delete()

        iago = self.example_user("iago")
        enqueue_welcome_emails(iago)
        scheduled_emails = ScheduledEmail.objects.filter(user=iago)
        email_data = ujson.loads(scheduled_emails[0].data)
        self.assertEqual(email_data["context"]["email"], self.example_email("iago"))
        self.assertEqual(email_data["context"]["is_realm_admin"], True)
        self.assertEqual(email_data["context"]["getting_started_link"],
                         "http://zulip.testserver/help/getting-your-organization-started-with-zulip")
        self.assertNotIn("ldap_username", email_data["context"])

    # See https://zulip.readthedocs.io/en/latest/production/authentication-methods.html#ldap-including-active-directory
    # for case details.
    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',
                                                'zproject.backends.ZulipDummyBackend'))
    def test_day1_email_ldap_case_a_login_credentials(self) -> None:
        ldap_user_attr_map = {'full_name': 'fn', 'short_name': 'sn'}

        ldap_patcher = patch('django_auth_ldap.config.ldap.initialize')
        mock_initialize = ldap_patcher.start()
        mock_ldap = MockLDAP()
        mock_initialize.return_value = mock_ldap

        mock_ldap.directory = {
            "uid=newuser@zulip.com,ou=users,dc=zulip,dc=com": {
                'userPassword': ['testing', ],
                'fn': ['full_name'],
                'sn': ['shortname'],
            }
        }

        ldap_search = LDAPSearch("ou=users,dc=zulip,dc=com", ldap.SCOPE_SUBTREE, "(email=%(user)s)")
        with self.settings(
                AUTH_LDAP_USER_ATTR_MAP=ldap_user_attr_map,
                AUTH_LDAP_USER_DN_TEMPLATE='uid=%(user)s,ou=users,dc=zulip,dc=com',
                AUTH_LDAP_USER_SEARCH=ldap_search):
            self.login_with_return("newuser@zulip.com", "testing")
            user = UserProfile.objects.get(email="newuser@zulip.com")
            scheduled_emails = ScheduledEmail.objects.filter(user=user)

            self.assertEqual(len(scheduled_emails), 2)
            email_data = ujson.loads(scheduled_emails[0].data)
            self.assertEqual(email_data["context"]["ldap"], True)
            self.assertEqual(email_data["context"]["ldap_username"], "newuser@zulip.com")

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',
                                                'zproject.backends.ZulipDummyBackend'))
    def test_day1_email_ldap_case_b_login_credentials(self) -> None:
        ldap_user_attr_map = {'full_name': 'fn', 'short_name': 'sn'}

        ldap_patcher = patch('django_auth_ldap.config.ldap.initialize')
        mock_initialize = ldap_patcher.start()
        mock_ldap = MockLDAP()
        mock_initialize.return_value = mock_ldap

        mock_ldap.directory = {
            'uid=newuser,ou=users,dc=zulip,dc=com': {
                'userPassword': ['testing', ],
                'fn': ['full_name'],
                'sn': ['shortname'],
            }
        }

        with self.settings(
                LDAP_APPEND_DOMAIN='zulip.com',
                AUTH_LDAP_USER_ATTR_MAP=ldap_user_attr_map,
                AUTH_LDAP_USER_DN_TEMPLATE='uid=%(user)s,ou=users,dc=zulip,dc=com'):

            self.login_with_return("newuser@zulip.com", "testing")

            user = UserProfile.objects.get(email="newuser@zulip.com")
            scheduled_emails = ScheduledEmail.objects.filter(user=user)

            self.assertEqual(len(scheduled_emails), 2)
            email_data = ujson.loads(scheduled_emails[0].data)
            self.assertEqual(email_data["context"]["ldap"], True)
            self.assertEqual(email_data["context"]["ldap_username"], "newuser")

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',
                                                'zproject.backends.ZulipDummyBackend'))
    def test_day1_email_ldap_case_c_login_credentials(self) -> None:
        ldap_user_attr_map = {'full_name': 'fn', 'short_name': 'sn'}

        ldap_patcher = patch('django_auth_ldap.config.ldap.initialize')
        mock_initialize = ldap_patcher.start()
        mock_ldap = MockLDAP()
        mock_initialize.return_value = mock_ldap

        mock_ldap.directory = {
            'uid=newuser,ou=users,dc=zulip,dc=com': {
                'userPassword': ['testing', ],
                'fn': ['full_name'],
                'sn': ['shortname'],
                'email': ['newuser_email@zulip.com'],
            }
        }

        with self.settings(
                LDAP_EMAIL_ATTR='email',
                AUTH_LDAP_USER_ATTR_MAP=ldap_user_attr_map,
                AUTH_LDAP_USER_DN_TEMPLATE='uid=%(user)s,ou=users,dc=zulip,dc=com'):
            self.login_with_return("newuser", "testing")
            user = UserProfile.objects.get(email="newuser_email@zulip.com")
            scheduled_emails = ScheduledEmail.objects.filter(user=user)

            self.assertEqual(len(scheduled_emails), 2)
            email_data = ujson.loads(scheduled_emails[0].data)
            self.assertEqual(email_data["context"]["ldap"], True)
            self.assertNotIn("ldap_username", email_data["context"])

    def test_followup_emails_count(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")

        enqueue_welcome_emails(self.example_user("hamlet"))
        # Hamlet has account only in Zulip realm so both day1 and day2 emails should be sent
        scheduled_emails = ScheduledEmail.objects.filter(user=hamlet)
        self.assertEqual(2, len(scheduled_emails))
        self.assertEqual(ujson.loads(scheduled_emails[0].data)["template_prefix"], 'zerver/emails/followup_day2')
        self.assertEqual(ujson.loads(scheduled_emails[1].data)["template_prefix"], 'zerver/emails/followup_day1')

        ScheduledEmail.objects.all().delete()

        enqueue_welcome_emails(cordelia)
        scheduled_emails = ScheduledEmail.objects.filter(user=cordelia)
        # Cordelia has account in more than 1 realm so day2 email should not be sent
        self.assertEqual(len(scheduled_emails), 1)
        email_data = ujson.loads(scheduled_emails[0].data)
        self.assertEqual(email_data["template_prefix"], 'zerver/emails/followup_day1')

class TestMissedMessages(ZulipTestCase):
    def normalize_string(self, s: str) -> str:
        s = s.strip()
        return re.sub(r'\s+', ' ', s)

    def _get_tokens(self) -> List[str]:
        return [str(random.getrandbits(32)) for _ in range(30)]

    def _test_cases(self, tokens: List[str], msg_id: int, body: str, email_subject: str,
                    send_as_user: bool, verify_html_body: bool=False,
                    show_message_content: bool=True,
                    verify_body_does_not_include: Optional[List[str]]=None,
                    trigger: str='') -> None:
        othello = self.example_user('othello')
        hamlet = self.example_user('hamlet')
        handle_missedmessage_emails(hamlet.id, [{'message_id': msg_id, 'trigger': trigger}])
        if settings.EMAIL_GATEWAY_PATTERN != "":
            reply_to_addresses = [settings.EMAIL_GATEWAY_PATTERN % (u'mm' + t) for t in tokens]
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
            self.assertIn(body, self.normalize_string(msg.alternatives[0][0]))
        else:
            self.assertIn(body, self.normalize_string(msg.body))
        if verify_body_does_not_include is not None:
            for text in verify_body_does_not_include:
                self.assertNotIn(text, self.normalize_string(msg.body))

    @patch('zerver.lib.email_mirror.generate_random_token')
    def _realm_name_in_missed_message_email_subject(self,
                                                    realm_name_in_notifications: bool,
                                                    mock_random_token: MagicMock) -> None:
        tokens = self._get_tokens()
        mock_random_token.side_effect = tokens

        msg_id = self.send_personal_message(
            self.example_email('othello'),
            self.example_email('hamlet'),
            'Extremely personal message!',
        )
        body = 'You and Othello, the Moor of Venice Extremely personal message!'
        email_subject = 'Othello, the Moor of Venice sent you a message'

        if realm_name_in_notifications:
            email_subject = 'Othello, the Moor of Venice sent you a message in Zulip Dev'
        self._test_cases(tokens, msg_id, body, email_subject, False)

    @patch('zerver.lib.email_mirror.generate_random_token')
    def _extra_context_in_missed_stream_messages_mention(self, send_as_user: bool,
                                                         mock_random_token: MagicMock,
                                                         show_message_content: bool=True) -> None:
        tokens = self._get_tokens()
        mock_random_token.side_effect = tokens

        for i in range(0, 11):
            self.send_stream_message(self.example_email('othello'), "Denmark", content=str(i))
        self.send_stream_message(
            self.example_email('othello'), "Denmark",
            '11', topic_name='test2')
        msg_id = self.send_stream_message(
            self.example_email('othello'), "denmark",
            '@**King Hamlet**')

        if show_message_content:
            body = 'Denmark > test Othello, the Moor of Venice 1 2 3 4 5 6 7 8 9 10 @**King Hamlet**'
            email_subject = 'Othello, the Moor of Venice mentioned you'
            verify_body_does_not_include = []  # type: List[str]
        else:
            # Test in case if message content in missed email message are disabled.
            body = 'While you were away you received 1 new message in which you were mentioned!'
            email_subject = 'New missed message'
            verify_body_does_not_include = ['Denmark > test', 'Othello, the Moor of Venice',
                                            '1 2 3 4 5 6 7 8 9 10 @**King Hamlet**', 'private', 'group',
                                            'Or just reply to this email.']
        self._test_cases(tokens, msg_id, body, email_subject, send_as_user,
                         show_message_content=show_message_content,
                         verify_body_does_not_include=verify_body_does_not_include,
                         trigger='mentioned')

    @patch('zerver.lib.email_mirror.generate_random_token')
    def _extra_context_in_missed_stream_messages_email_notify(self, send_as_user: bool,
                                                              mock_random_token: MagicMock) -> None:
        tokens = self._get_tokens()
        mock_random_token.side_effect = tokens

        for i in range(0, 11):
            self.send_stream_message(self.example_email('othello'), "Denmark", content=str(i))
        self.send_stream_message(
            self.example_email('othello'), "Denmark",
            '11', topic_name='test2')
        msg_id = self.send_stream_message(
            self.example_email('othello'), "denmark",
            '12')
        body = 'Denmark > test Othello, the Moor of Venice 1 2 3 4 5 6 7 8 9 10 12'
        email_subject = 'New messages in Denmark > test'
        self._test_cases(tokens, msg_id, body, email_subject, send_as_user, trigger='stream_email_notify')

    @patch('zerver.lib.email_mirror.generate_random_token')
    def _extra_context_in_missed_stream_messages_mention_two_senders(
            self, send_as_user: bool, mock_random_token: MagicMock) -> None:
        tokens = self._get_tokens()
        mock_random_token.side_effect = tokens

        for i in range(0, 3):
            self.send_stream_message(self.example_email('cordelia'), "Denmark", str(i))
        msg_id = self.send_stream_message(
            self.example_email('othello'), "Denmark",
            '@**King Hamlet**')
        body = 'Denmark > test Cordelia Lear 0 1 2 Othello, the Moor of Venice @**King Hamlet**'
        email_subject = 'Othello, the Moor of Venice mentioned you'
        self._test_cases(tokens, msg_id, body, email_subject, send_as_user, trigger='mentioned')

    @patch('zerver.lib.email_mirror.generate_random_token')
    def _extra_context_in_personal_missed_stream_messages(self, send_as_user: bool,
                                                          mock_random_token: MagicMock,
                                                          show_message_content: bool=True) -> None:
        tokens = self._get_tokens()
        mock_random_token.side_effect = tokens

        msg_id = self.send_personal_message(
            self.example_email('othello'),
            self.example_email('hamlet'),
            'Extremely personal message!',
        )

        if show_message_content:
            body = 'You and Othello, the Moor of Venice Extremely personal message!'
            email_subject = 'Othello, the Moor of Venice sent you a message'
            verify_body_does_not_include = []  # type: List[str]
        else:
            body = 'While you were away you received 1 new private message!'
            email_subject = 'New missed message'
            verify_body_does_not_include = ['Othello, the Moor of Venice', 'Extremely personal message!',
                                            'mentioned', 'group', 'Or just reply to this email.']
        self._test_cases(tokens, msg_id, body, email_subject, send_as_user,
                         show_message_content=show_message_content,
                         verify_body_does_not_include=verify_body_does_not_include)

    @patch('zerver.lib.email_mirror.generate_random_token')
    def _reply_to_email_in_personal_missed_stream_messages(self, send_as_user: bool,
                                                           mock_random_token: MagicMock) -> None:
        tokens = self._get_tokens()
        mock_random_token.side_effect = tokens

        msg_id = self.send_personal_message(
            self.example_email('othello'),
            self.example_email('hamlet'),
            'Extremely personal message!',
        )
        body = 'Or just reply to this email.'
        email_subject = 'Othello, the Moor of Venice sent you a message'
        self._test_cases(tokens, msg_id, body, email_subject, send_as_user)

    @patch('zerver.lib.email_mirror.generate_random_token')
    def _reply_warning_in_personal_missed_stream_messages(self, send_as_user: bool,
                                                          mock_random_token: MagicMock) -> None:
        tokens = self._get_tokens()
        mock_random_token.side_effect = tokens

        msg_id = self.send_personal_message(
            self.example_email('othello'),
            self.example_email('hamlet'),
            'Extremely personal message!',
        )
        body = 'Please do not reply to this automated message.'
        email_subject = 'Othello, the Moor of Venice sent you a message'
        self._test_cases(tokens, msg_id, body, email_subject, send_as_user)

    @patch('zerver.lib.email_mirror.generate_random_token')
    def _extra_context_in_huddle_missed_stream_messages_two_others(self, send_as_user: bool,
                                                                   mock_random_token: MagicMock,
                                                                   show_message_content: bool=True) -> None:
        tokens = self._get_tokens()
        mock_random_token.side_effect = tokens

        msg_id = self.send_huddle_message(
            self.example_email('othello'),
            [
                self.example_email('hamlet'),
                self.example_email('iago'),
            ],
            'Group personal message!',
        )

        if show_message_content:
            body = ('You and Iago, Othello, the Moor of Venice Othello,'
                    ' the Moor of Venice Group personal message')
            email_subject = 'Group PMs with Iago and Othello, the Moor of Venice'
            verify_body_does_not_include = []  # type: List[str]
        else:
            body = 'While you were away you received 1 new group private message!'
            email_subject = 'New missed message'
            verify_body_does_not_include = ['Iago', 'Othello, the Moor of Venice Othello, the Moor of Venice',
                                            'Group personal message!', 'mentioned',
                                            'Or just reply to this email.']
        self._test_cases(tokens, msg_id, body, email_subject, send_as_user,
                         show_message_content=show_message_content,
                         verify_body_does_not_include=verify_body_does_not_include)

    @patch('zerver.lib.email_mirror.generate_random_token')
    def _extra_context_in_huddle_missed_stream_messages_three_others(self, send_as_user: bool,
                                                                     mock_random_token: MagicMock) -> None:
        tokens = self._get_tokens()
        mock_random_token.side_effect = tokens

        msg_id = self.send_huddle_message(
            self.example_email('othello'),
            [
                self.example_email('hamlet'),
                self.example_email('iago'),
                self.example_email('cordelia'),
            ],
            'Group personal message!',
        )

        body = ('You and Cordelia Lear, Iago, Othello, the Moor of Venice Othello,'
                ' the Moor of Venice Group personal message')
        email_subject = 'Group PMs with Cordelia Lear, Iago, and Othello, the Moor of Venice'
        self._test_cases(tokens, msg_id, body, email_subject, send_as_user)

    @patch('zerver.lib.email_mirror.generate_random_token')
    def _extra_context_in_huddle_missed_stream_messages_many_others(self, send_as_user: bool,
                                                                    mock_random_token: MagicMock) -> None:
        tokens = self._get_tokens()
        mock_random_token.side_effect = tokens

        msg_id = self.send_huddle_message(self.example_email('othello'),
                                          [self.example_email('hamlet'),
                                           self.example_email('iago'),
                                           self.example_email('cordelia'),
                                           self.example_email('prospero')],
                                          'Group personal message!')

        body = ('You and Cordelia Lear, Iago, Othello, the Moor of Venice, Prospero from The Tempest'
                ' Othello, the Moor of Venice Group personal message')
        email_subject = 'Group PMs with Cordelia Lear, Iago, and 2 others'
        self._test_cases(tokens, msg_id, body, email_subject, send_as_user)

    @patch('zerver.lib.email_mirror.generate_random_token')
    def _deleted_message_in_missed_stream_messages(self, send_as_user: bool,
                                                   mock_random_token: MagicMock) -> None:
        tokens = self._get_tokens()
        mock_random_token.side_effect = tokens

        msg_id = self.send_stream_message(
            self.example_email('othello'), "denmark",
            '@**King Hamlet** to be deleted')

        hamlet = self.example_user('hamlet')
        email = self.example_email('othello')
        self.login(email)
        result = self.client_patch('/json/messages/' + str(msg_id),
                                   {'message_id': msg_id, 'content': ' '})
        self.assert_json_success(result)
        handle_missedmessage_emails(hamlet.id, [{'message_id': msg_id}])
        self.assertEqual(len(mail.outbox), 0)

    @patch('zerver.lib.email_mirror.generate_random_token')
    def _deleted_message_in_personal_missed_stream_messages(self, send_as_user: bool,
                                                            mock_random_token: MagicMock) -> None:
        tokens = self._get_tokens()
        mock_random_token.side_effect = tokens

        msg_id = self.send_personal_message(self.example_email('othello'),
                                            self.example_email('hamlet'),
                                            'Extremely personal message! to be deleted!')

        hamlet = self.example_user('hamlet')
        email = self.example_email('othello')
        self.login(email)
        result = self.client_patch('/json/messages/' + str(msg_id),
                                   {'message_id': msg_id, 'content': ' '})
        self.assert_json_success(result)
        handle_missedmessage_emails(hamlet.id, [{'message_id': msg_id}])
        self.assertEqual(len(mail.outbox), 0)

    @patch('zerver.lib.email_mirror.generate_random_token')
    def _deleted_message_in_huddle_missed_stream_messages(self, send_as_user: bool,
                                                          mock_random_token: MagicMock) -> None:
        tokens = self._get_tokens()
        mock_random_token.side_effect = tokens

        msg_id = self.send_huddle_message(
            self.example_email('othello'),
            [
                self.example_email('hamlet'),
                self.example_email('iago'),
            ],
            'Group personal message!',
        )

        hamlet = self.example_user('hamlet')
        iago = self.example_user('iago')
        email = self.example_email('othello')
        self.login(email)
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
        self._extra_context_in_personal_missed_stream_messages(False, show_message_content=False)
        mail.outbox = []
        self._extra_context_in_huddle_missed_stream_messages_two_others(False, show_message_content=False)

    @override_settings(SEND_MISSED_MESSAGE_EMAILS_AS_USER=True)
    def test_extra_context_in_missed_stream_messages_as_user(self) -> None:
        self._extra_context_in_missed_stream_messages_mention(True)

    def test_extra_context_in_missed_stream_messages(self) -> None:
        self._extra_context_in_missed_stream_messages_mention(False)

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
        self._extra_context_in_personal_missed_stream_messages(False, show_message_content=False)

        # When message content is not allowed at realm level
        # Emails don't have missed message irrespective of message content setting of the user
        realm = get_realm("zulip")
        realm.message_content_allowed_in_email_notifications = False
        realm.save(update_fields=['message_content_allowed_in_email_notifications'])

        do_change_notification_settings(user, "message_content_in_email_notifications", True)
        mail.outbox = []
        self._extra_context_in_personal_missed_stream_messages(False, show_message_content=False)

        do_change_notification_settings(user, "message_content_in_email_notifications", False)
        mail.outbox = []
        self._extra_context_in_personal_missed_stream_messages(False, show_message_content=False)

    @patch('zerver.lib.email_mirror.generate_random_token')
    def test_realm_emoji_in_missed_message(self, mock_random_token: MagicMock) -> None:
        tokens = self._get_tokens()
        mock_random_token.side_effect = tokens

        msg_id = self.send_personal_message(
            self.example_email('othello'), self.example_email('hamlet'),
            'Extremely personal message with a realm emoji :green_tick:!')
        realm_emoji_id = get_realm('zulip').get_active_emoji()['green_tick']['id']
        realm_emoji_url = "http://zulip.testserver/user_avatars/1/emoji/images/%s.png" % (realm_emoji_id,)
        body = '<img alt=":green_tick:" src="%s" title="green tick" style="height: 20px;">' % (realm_emoji_url,)
        email_subject = 'Othello, the Moor of Venice sent you a message'
        self._test_cases(tokens, msg_id, body, email_subject, send_as_user=False, verify_html_body=True)

    @patch('zerver.lib.email_mirror.generate_random_token')
    def test_emojiset_in_missed_message(self, mock_random_token: MagicMock) -> None:
        tokens = self._get_tokens()
        mock_random_token.side_effect = tokens

        hamlet = self.example_user('hamlet')
        hamlet.emojiset = 'apple'
        hamlet.save(update_fields=['emojiset'])
        msg_id = self.send_personal_message(
            self.example_email('othello'), self.example_email('hamlet'),
            'Extremely personal message with a hamburger :hamburger:!')
        body = '<img alt=":hamburger:" src="http://zulip.testserver/static/generated/emoji/images-apple-64/1f354.png" title="hamburger" style="height: 20px;">'
        email_subject = 'Othello, the Moor of Venice sent you a message'
        self._test_cases(tokens, msg_id, body, email_subject, send_as_user=False, verify_html_body=True)

    @patch('zerver.lib.email_mirror.generate_random_token')
    def test_stream_link_in_missed_message(self, mock_random_token: MagicMock) -> None:
        tokens = self._get_tokens()
        mock_random_token.side_effect = tokens

        msg_id = self.send_personal_message(
            self.example_email('othello'), self.example_email('hamlet'),
            'Come and join us in #**Verona**.')
        stream_id = get_stream('Verona', get_realm('zulip')).id
        href = "http://zulip.testserver/#narrow/stream/{stream_id}-Verona".format(stream_id=stream_id)
        body = '<a class="stream" data-stream-id="5" href="{href}">#Verona</a'.format(href=href)
        email_subject = 'Othello, the Moor of Venice sent you a message'
        self._test_cases(tokens, msg_id, body, email_subject, send_as_user=False, verify_html_body=True)

    @patch('zerver.lib.email_mirror.generate_random_token')
    def test_multiple_missed_personal_messages(self, mock_random_token: MagicMock) -> None:
        tokens = self._get_tokens()
        mock_random_token.side_effect = tokens

        hamlet = self.example_user('hamlet')
        msg_id_1 = self.send_personal_message(self.example_email('othello'),
                                              hamlet.email,
                                              'Personal Message 1')
        msg_id_2 = self.send_personal_message(self.example_email('iago'),
                                              hamlet.email,
                                              'Personal Message 2')

        handle_missedmessage_emails(hamlet.id, [
            {'message_id': msg_id_1},
            {'message_id': msg_id_2},
        ])
        self.assertEqual(len(mail.outbox), 2)
        email_subject = 'Othello, the Moor of Venice sent you a message'
        self.assertEqual(mail.outbox[0].subject, email_subject)
        email_subject = 'Iago sent you a message'
        self.assertEqual(mail.outbox[1].subject, email_subject)

    @patch('zerver.lib.email_mirror.generate_random_token')
    def test_multiple_stream_messages(self, mock_random_token: MagicMock) -> None:
        tokens = self._get_tokens()
        mock_random_token.side_effect = tokens

        hamlet = self.example_user('hamlet')
        msg_id_1 = self.send_stream_message(self.example_email('othello'),
                                            "Denmark",
                                            'Message1')
        msg_id_2 = self.send_stream_message(self.example_email('iago'),
                                            "Denmark",
                                            'Message2')

        handle_missedmessage_emails(hamlet.id, [
            {'message_id': msg_id_1, "trigger": "stream_email_notify"},
            {'message_id': msg_id_2, "trigger": "stream_email_notify"},
        ])
        self.assertEqual(len(mail.outbox), 1)
        email_subject = 'New messages in Denmark > test'
        self.assertEqual(mail.outbox[0].subject, email_subject)

    @patch('zerver.lib.email_mirror.generate_random_token')
    def test_multiple_stream_messages_and_mentions(self, mock_random_token: MagicMock) -> None:
        """A mention should take precedence over regular stream messages for email subjects."""
        tokens = self._get_tokens()
        mock_random_token.side_effect = tokens

        hamlet = self.example_user('hamlet')
        msg_id_1 = self.send_stream_message(self.example_email('iago'),
                                            "Denmark",
                                            'Regular message')
        msg_id_2 = self.send_stream_message(self.example_email('othello'),
                                            "Denmark",
                                            '@**King Hamlet**')

        handle_missedmessage_emails(hamlet.id, [
            {'message_id': msg_id_1, "trigger": "stream_email_notify"},
            {'message_id': msg_id_2, "trigger": "mentioned"},
        ])
        self.assertEqual(len(mail.outbox), 1)
        email_subject = 'Othello, the Moor of Venice mentioned you'
        self.assertEqual(mail.outbox[0].subject, email_subject)

    @patch('zerver.lib.email_mirror.generate_random_token')
    def test_message_access_in_emails(self, mock_random_token: MagicMock) -> None:
        # Messages sent to a protected history-private stream shouldn't be
        # accessible/available in emails before subscribing
        tokens = self._get_tokens()
        mock_random_token.side_effect = tokens

        stream_name = "private_stream"
        self.make_stream(stream_name, invite_only=True,
                         history_public_to_subscribers=False)
        user = self.example_user('iago')
        self.subscribe(user, stream_name)
        late_subscribed_user = self.example_user('hamlet')

        self.send_stream_message(user.email,
                                 stream_name,
                                 'Before subscribing')

        self.subscribe(late_subscribed_user, stream_name)

        self.send_stream_message(user.email,
                                 stream_name,
                                 "After subscribing")

        mention_msg_id = self.send_stream_message(user.email,
                                                  stream_name,
                                                  '@**King Hamlet**')

        handle_missedmessage_emails(late_subscribed_user.id, [
            {'message_id': mention_msg_id, "trigger": "mentioned"},
        ])

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, 'Iago mentioned you')  # email subject
        email_text = mail.outbox[0].message().as_string()
        self.assertNotIn('Before subscribing', email_text)
        self.assertIn('After subscribing', email_text)
        self.assertIn('@**King Hamlet**', email_text)

    @patch('zerver.lib.email_mirror.generate_random_token')
    def test_stream_mentions_multiple_people(self, mock_random_token: MagicMock) -> None:
        """A mention should take precedence over regular stream messages for email subjects.

        Each sender who has mentioned a user should appear in the email subject line.
        """
        tokens = self._get_tokens()
        mock_random_token.side_effect = tokens

        hamlet = self.example_user('hamlet')
        msg_id_1 = self.send_stream_message(self.example_email('iago'),
                                            "Denmark",
                                            '@**King Hamlet**')
        msg_id_2 = self.send_stream_message(self.example_email('othello'),
                                            "Denmark",
                                            '@**King Hamlet**')
        msg_id_3 = self.send_stream_message(self.example_email('cordelia'),
                                            "Denmark",
                                            'Regular message')

        handle_missedmessage_emails(hamlet.id, [
            {'message_id': msg_id_1, "trigger": "mentioned"},
            {'message_id': msg_id_2, "trigger": "mentioned"},
            {'message_id': msg_id_3, "trigger": "stream_email_notify"},
        ])
        self.assertEqual(len(mail.outbox), 1)
        email_subject = 'Iago, Othello, the Moor of Venice mentioned you'
        self.assertEqual(mail.outbox[0].subject, email_subject)

    @patch('zerver.lib.email_mirror.generate_random_token')
    def test_multiple_stream_messages_different_topics(self, mock_random_token: MagicMock) -> None:
        """Should receive separate emails for each topic within a stream."""
        tokens = self._get_tokens()
        mock_random_token.side_effect = tokens

        hamlet = self.example_user('hamlet')
        msg_id_1 = self.send_stream_message(self.example_email('othello'),
                                            "Denmark",
                                            'Message1')
        msg_id_2 = self.send_stream_message(self.example_email('iago'),
                                            "Denmark",
                                            'Message2',
                                            topic_name="test2")

        handle_missedmessage_emails(hamlet.id, [
            {'message_id': msg_id_1, "trigger": "stream_email_notify"},
            {'message_id': msg_id_2, "trigger": "stream_email_notify"},
        ])
        self.assertEqual(len(mail.outbox), 2)
        email_subjects = {mail.outbox[0].subject, mail.outbox[1].subject}
        valid_email_subjects = {'New messages in Denmark > test', 'New messages in Denmark > test2'}
        self.assertEqual(email_subjects, valid_email_subjects)

    def test_relative_to_full_url(self) -> None:
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
        test_data = '<a href="/user_uploads/2/1f/some_random_value">/user_uploads/2/1f/some_random_value</a>'
        actual_output = relative_to_full_url("http://example.com", test_data)
        expected_output = '<a href="http://example.com/user_uploads/2/1f/some_random_value">' + \
            '/user_uploads/2/1f/some_random_value</a>'
        self.assertEqual(actual_output, expected_output)

        # A user avatar like syntax, but not actually in an HTML tag
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
        test_data = '<p>See this <a href="/user_uploads/1/52/fG7GM9e3afz_qsiUcSce2tl_/avatar_103.jpeg" target="_blank" ' +   \
                    'title="avatar_103.jpeg">avatar_103.jpeg</a>.</p>' +    \
                    '<div class="message_inline_image"><a href="/user_uploads/1/52/fG7GM9e3afz_qsiUcSce2tl_/avatar_103.jpeg" ' +    \
                    'target="_blank" title="avatar_103.jpeg"><img src="/user_uploads/1/52/fG7GM9e3afz_qsiUcSce2tl_/avatar_103.jpeg"></a></div>'
        actual_output = relative_to_full_url("http://example.com", test_data)
        expected_output = '<div><p>See this <a href="http://example.com/user_uploads/1/52/fG7GM9e3afz_qsiUcSce2tl_/avatar_103.jpeg" target="_blank" ' +  \
                          'title="avatar_103.jpeg">avatar_103.jpeg</a>.</p></div>'
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
