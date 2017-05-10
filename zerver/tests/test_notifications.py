from __future__ import absolute_import
from __future__ import print_function

import random
import re
import ujson

from django.conf import settings
from django.core import mail
from django.http import HttpResponse
from django.test import override_settings
from mock import patch, MagicMock
from six.moves import range
from typing import Any, Dict, List, Text

from zerver.lib.notifications import handle_missedmessage_emails
from zerver.lib.actions import render_incoming_message, do_update_message
from zerver.lib.message import access_message
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import (
    Recipient,
    UserMessage,
    UserProfile,
)

class TestMissedMessages(ZulipTestCase):
    def normalize_string(self, s):
        # type: (Text) -> Text
        s = s.strip()
        return re.sub(r'\s+', ' ', s)

    def _get_tokens(self):
        # type: () -> List[str]
        return [str(random.getrandbits(32)) for _ in range(30)]

    def _test_cases(self, tokens, msg_id, body, subject, send_as_user):
<<<<<<< HEAD
        # type: (List[str], int, str, str, bool) -> None
=======
        # type: (List[str], int, str, bool) -> None
>>>>>>> 8147209bd82d8dc1e9a3669d58e8139f18cf1173
        othello = get_user_profile_by_email('othello@zulip.com')
        hamlet = get_user_profile_by_email('hamlet@zulip.com')
        handle_missedmessage_emails(hamlet.id, [{'message_id': msg_id}])
        if settings.EMAIL_GATEWAY_PATTERN != "":
            reply_to_addresses = [settings.EMAIL_GATEWAY_PATTERN % (u'mm' + t) for t in tokens]
        else:
            reply_to_addresses = ["Zulip <noreply@example.com>"]
        msg = mail.outbox[0]
<<<<<<< HEAD
        sender = settings.NOREPLY_EMAIL_ADDRESS
=======
        sender = 'Zulip Missed Messages <{}>'.format(settings.NOREPLY_EMAIL_ADDRESS)
>>>>>>> 8147209bd82d8dc1e9a3669d58e8139f18cf1173
        from_email = sender
        self.assertEqual(len(mail.outbox), 1)
        if send_as_user:
            from_email = '"%s" <%s>' % (othello.full_name, othello.email)
        self.assertEqual(msg.from_email, from_email)
        self.assertIn(msg.extra_headers['Reply-To'], reply_to_addresses)
        self.assertEqual(msg.subject, subject)
        self.assertIn(body, self.normalize_string(msg.body))

    @patch('zerver.lib.email_mirror.generate_random_token')
    def _extra_context_in_missed_stream_messages(self, send_as_user, mock_random_token):
        # type: (bool, MagicMock) -> None
        tokens = self._get_tokens()
        mock_random_token.side_effect = tokens

        for i in range(0, 11):
            self.send_message("othello@zulip.com", "Denmark", Recipient.STREAM, str(i))
        self.send_message("othello@zulip.com", "Denmark", Recipient.STREAM, '11', subject='test2')
        msg_id = self.send_message("othello@zulip.com", "denmark", Recipient.STREAM, '@**hamlet**')
        body = 'Denmark > test Othello, the Moor of Venice 1 2 3 4 5 6 7 8 9 10 @**hamlet**'
<<<<<<< HEAD
        subject = 'Othello, the Moor of Venice @-mentioned you in Zulip Dev'
=======
        subject = 'Othello, the Moor of Venice @-mentioned you in zulip'
>>>>>>> 8147209bd82d8dc1e9a3669d58e8139f18cf1173
        self._test_cases(tokens, msg_id, body, subject, send_as_user)

    @patch('zerver.lib.email_mirror.generate_random_token')
    def _extra_context_in_personal_missed_stream_messages(self, send_as_user, mock_random_token):
        # type: (bool, MagicMock) -> None
        tokens = self._get_tokens()
        mock_random_token.side_effect = tokens

        msg_id = self.send_message("othello@zulip.com", "hamlet@zulip.com",
                                   Recipient.PERSONAL,
                                   'Extremely personal message!')
        body = 'You and Othello, the Moor of Venice Extremely personal message!'
<<<<<<< HEAD
        subject = 'Othello, the Moor of Venice sent you a message in Zulip Dev'
=======
        subject = 'Othello, the Moor of Venice sent you a message in zulip'
>>>>>>> 8147209bd82d8dc1e9a3669d58e8139f18cf1173
        self._test_cases(tokens, msg_id, body, subject, send_as_user)

    @patch('zerver.lib.email_mirror.generate_random_token')
    def _reply_to_email_in_personal_missed_stream_messages(self, send_as_user, mock_random_token):
        # type: (bool, MagicMock) -> None
        tokens = self._get_tokens()
        mock_random_token.side_effect = tokens

        msg_id = self.send_message("othello@zulip.com", "hamlet@zulip.com",
                                   Recipient.PERSONAL,
                                   'Extremely personal message!')
        body = 'Or just reply to this email.'
<<<<<<< HEAD
        subject = 'Othello, the Moor of Venice sent you a message in Zulip Dev'
=======
        subject = 'Othello, the Moor of Venice sent you a message in zulip'
>>>>>>> 8147209bd82d8dc1e9a3669d58e8139f18cf1173
        self._test_cases(tokens, msg_id, body, subject, send_as_user)

    @patch('zerver.lib.email_mirror.generate_random_token')
    def _reply_warning_in_personal_missed_stream_messages(self, send_as_user, mock_random_token):
        # type: (bool, MagicMock) -> None
        tokens = self._get_tokens()
        mock_random_token.side_effect = tokens

        msg_id = self.send_message("othello@zulip.com", "hamlet@zulip.com",
                                   Recipient.PERSONAL,
                                   'Extremely personal message!')
        body = 'Please do not reply to this automated message.'
<<<<<<< HEAD
        subject = 'Othello, the Moor of Venice sent you a message in Zulip Dev'
        self._test_cases(tokens, msg_id, body, subject, send_as_user)

    @patch('zerver.lib.email_mirror.generate_random_token')
    def _extra_context_in_huddle_missed_stream_messages_two_others(self, send_as_user, mock_random_token):
=======
        subject = 'Othello, the Moor of Venice sent you a message in zulip'
        self._test_cases(tokens, msg_id, body, subject, send_as_user)

    @patch('zerver.lib.email_mirror.generate_random_token')
    def _extra_context_in_huddle_missed_stream_messages_three_members(self, send_as_user, mock_random_token):
>>>>>>> 8147209bd82d8dc1e9a3669d58e8139f18cf1173
        # type: (bool, MagicMock) -> None
        tokens = self._get_tokens()
        mock_random_token.side_effect = tokens

        msg_id = self.send_message("othello@zulip.com",
                                   ["hamlet@zulip.com", "iago@zulip.com"],
                                   Recipient.HUDDLE,
                                   'Group personal message!')

        body = ('You and Iago, Othello, the Moor of Venice Othello,'
                ' the Moor of Venice Group personal message')
<<<<<<< HEAD
        subject = 'Group PMs with Iago and Othello, the Moor of Venice in Zulip Dev'
        self._test_cases(tokens, msg_id, body, subject, send_as_user)

    @patch('zerver.lib.email_mirror.generate_random_token')
    def _extra_context_in_huddle_missed_stream_messages_three_others(self, send_as_user, mock_random_token):
=======
        subject = 'Group PM with Iago and Othello, the Moor of Venice in zulip'
        self._test_cases(tokens, msg_id, body, subject, send_as_user)

    @patch('zerver.lib.email_mirror.generate_random_token')
    def _extra_context_in_huddle_missed_stream_messages_four_members(self, send_as_user, mock_random_token):
>>>>>>> 8147209bd82d8dc1e9a3669d58e8139f18cf1173
        # type: (bool, MagicMock) -> None
        tokens = self._get_tokens()
        mock_random_token.side_effect = tokens

        msg_id = self.send_message("othello@zulip.com",
                                   ["hamlet@zulip.com", "iago@zulip.com", "cordelia@zulip.com"],
                                   Recipient.HUDDLE,
                                   'Group personal message!')

        body = ('You and Cordelia Lear, Iago, Othello, the Moor of Venice Othello,'
                ' the Moor of Venice Group personal message')
<<<<<<< HEAD
        subject = 'Group PMs with Cordelia Lear, Iago, and Othello, the Moor of Venice in Zulip Dev'
        self._test_cases(tokens, msg_id, body, subject, send_as_user)

    @patch('zerver.lib.email_mirror.generate_random_token')
    def _extra_context_in_huddle_missed_stream_messages_many_others(self, send_as_user, mock_random_token):
=======
        subject = 'Group PM with Cordelia Lear, Iago, and Othello, the Moor of Venice in zulip'
        self._test_cases(tokens, msg_id, body, subject, send_as_user)

    @patch('zerver.lib.email_mirror.generate_random_token')
    def _extra_context_in_huddle_missed_stream_messages_five_members(self, send_as_user, mock_random_token):
>>>>>>> 8147209bd82d8dc1e9a3669d58e8139f18cf1173
        # type: (bool, MagicMock) -> None
        tokens = self._get_tokens()
        mock_random_token.side_effect = tokens

        msg_id = self.send_message("othello@zulip.com",
                                   ["hamlet@zulip.com", "iago@zulip.com", "cordelia@zulip.com", "prospero@zulip.com"],
                                   Recipient.HUDDLE,
                                   'Group personal message!')

        body = ('You and Cordelia Lear, Iago, Othello, the Moor of Venice, Prospero from The Tempest'
                ' Othello, the Moor of Venice Group personal message')
<<<<<<< HEAD
        subject = 'Group PMs with Cordelia Lear, Iago, and 2 others in Zulip Dev'
=======
        subject = 'Group PM with Cordelia Lear, Iago, and others in zulip'
>>>>>>> 8147209bd82d8dc1e9a3669d58e8139f18cf1173
        self._test_cases(tokens, msg_id, body, subject, send_as_user)

    @patch('zerver.lib.email_mirror.generate_random_token')
    def _deleted_message_in_missed_stream_messages(self, send_as_user, mock_random_token):
        # type: (bool, MagicMock) -> None
        tokens = self._get_tokens()
        mock_random_token.side_effect = tokens

        msg_id = self.send_message("othello@zulip.com", "denmark", Recipient.STREAM,
                                   '@**hamlet** to be deleted')

        hamlet = self.example_user('hamlet')
        self.login("othello@zulip.com")
        result = self.client_patch('/json/messages/' + str(msg_id),
                                   {'message_id': msg_id, 'content': ' '})
        self.assert_json_success(result)
        handle_missedmessage_emails(hamlet.id, [{'message_id': msg_id}])
        self.assertEqual(len(mail.outbox), 0)

    @patch('zerver.lib.email_mirror.generate_random_token')
    def _deleted_message_in_personal_missed_stream_messages(self, send_as_user, mock_random_token):
        # type: (bool, MagicMock) -> None
        tokens = self._get_tokens()
        mock_random_token.side_effect = tokens

        msg_id = self.send_message("othello@zulip.com", "hamlet@zulip.com", Recipient.PERSONAL,
                                   'Extremely personal message! to be deleted!')

        hamlet = self.example_user('hamlet')
        self.login("othello@zulip.com")
        result = self.client_patch('/json/messages/' + str(msg_id),
                                   {'message_id': msg_id, 'content': ' '})
        self.assert_json_success(result)
        handle_missedmessage_emails(hamlet.id, [{'message_id': msg_id}])
        self.assertEqual(len(mail.outbox), 0)

    @patch('zerver.lib.email_mirror.generate_random_token')
    def _deleted_message_in_huddle_missed_stream_messages(self, send_as_user, mock_random_token):
        # type: (bool, MagicMock) -> None
        tokens = self._get_tokens()
        mock_random_token.side_effect = tokens

        msg_id = self.send_message("othello@zulip.com", ["hamlet@zulip.com", "iago@zulip.com"],
                                   Recipient.PERSONAL, 'Group personal message!')

        hamlet = self.example_user('hamlet')
        iago = self.example_user('iago')
        self.login("othello@zulip.com")
        result = self.client_patch('/json/messages/' + str(msg_id),
                                   {'message_id': msg_id, 'content': ' '})
        self.assert_json_success(result)
        handle_missedmessage_emails(hamlet.id, [{'message_id': msg_id}])
        self.assertEqual(len(mail.outbox), 0)
        handle_missedmessage_emails(iago.id, [{'message_id': msg_id}])
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(SEND_MISSED_MESSAGE_EMAILS_AS_USER=True)
    def test_extra_context_in_missed_stream_messages_as_user(self):
        # type: () -> None
        self._extra_context_in_missed_stream_messages(True)

    def test_extra_context_in_missed_stream_messages(self):
        # type: () -> None
        self._extra_context_in_missed_stream_messages(False)

    def test_reply_to_email_in_personal_missed_stream_messages(self):
        # type: () -> None
        self._reply_to_email_in_personal_missed_stream_messages(False)

    @override_settings(EMAIL_GATEWAY_PATTERN="")
    def test_reply_warning_in_personal_missed_stream_messages(self):
        # type: () -> None
        self._reply_warning_in_personal_missed_stream_messages(False)

    @override_settings(SEND_MISSED_MESSAGE_EMAILS_AS_USER=True)
    def test_extra_context_in_personal_missed_stream_messages_as_user(self):
        # type: () -> None
        self._extra_context_in_personal_missed_stream_messages(True)

    def test_extra_context_in_personal_missed_stream_messages(self):
        # type: () -> None
        self._extra_context_in_personal_missed_stream_messages(False)

    @override_settings(SEND_MISSED_MESSAGE_EMAILS_AS_USER=True)
<<<<<<< HEAD
    def test_extra_context_in_huddle_missed_stream_messages_two_others_as_user(self):
        # type: () -> None
        self._extra_context_in_huddle_missed_stream_messages_two_others(True)

    def test_extra_context_in_huddle_missed_stream_messages_two_others(self):
        # type: () -> None
        self._extra_context_in_huddle_missed_stream_messages_two_others(False)

    @override_settings(SEND_MISSED_MESSAGE_EMAILS_AS_USER=True)
    def test_extra_context_in_huddle_missed_stream_messages_three_others_as_user(self):
        # type: () -> None
        self._extra_context_in_huddle_missed_stream_messages_three_others(True)

    def test_extra_context_in_huddle_missed_stream_messages_three_others(self):
        # type: () -> None
        self._extra_context_in_huddle_missed_stream_messages_three_others(False)

    @override_settings(SEND_MISSED_MESSAGE_EMAILS_AS_USER=True)
    def test_extra_context_in_huddle_missed_stream_messages_many_others_as_user(self):
        # type: () -> None
        self._extra_context_in_huddle_missed_stream_messages_many_others(True)

    def test_extra_context_in_huddle_missed_stream_messages_many_others(self):
        # type: () -> None
        self._extra_context_in_huddle_missed_stream_messages_many_others(False)
=======
    def test_extra_context_in_huddle_missed_stream_messages_three_members_as_user(self):
        # type: () -> None
        self._extra_context_in_huddle_missed_stream_messages_three_members(True)

    def test_extra_context_in_huddle_missed_stream_messages_three_members(self):
        # type: () -> None
        self._extra_context_in_huddle_missed_stream_messages_three_members(False)

    @override_settings(SEND_MISSED_MESSAGE_EMAILS_AS_USER=True)
    def test_extra_context_in_huddle_missed_stream_messages_four_members_as_user(self):
        # type: () -> None
        self._extra_context_in_huddle_missed_stream_messages_four_members(True)

    def test_extra_context_in_huddle_missed_stream_messages_four_members(self):
        # type: () -> None
        self._extra_context_in_huddle_missed_stream_messages_four_members(False)

    @override_settings(SEND_MISSED_MESSAGE_EMAILS_AS_USER=True)
    def test_extra_context_in_huddle_missed_stream_messages_five_members_as_user(self):
        # type: () -> None
        self._extra_context_in_huddle_missed_stream_messages_five_members(True)

    def test_extra_context_in_huddle_missed_stream_messages_five_members(self):
        # type: () -> None
        self._extra_context_in_huddle_missed_stream_messages_five_members(False)
>>>>>>> 8147209bd82d8dc1e9a3669d58e8139f18cf1173

    @override_settings(SEND_MISSED_MESSAGE_EMAILS_AS_USER=True)
    def test_deleted_message_in_missed_stream_messages_as_user(self):
        # type: () -> None
        self._deleted_message_in_missed_stream_messages(True)

    def test_deleted_message_in_missed_stream_messages(self):
        # type: () -> None
        self._deleted_message_in_missed_stream_messages(False)

    @override_settings(SEND_MISSED_MESSAGE_EMAILS_AS_USER=True)
    def test_deleted_message_in_personal_missed_stream_messages_as_user(self):
        # type: () -> None
        self._deleted_message_in_personal_missed_stream_messages(True)

    def test_deleted_message_in_personal_missed_stream_messages(self):
        # type: () -> None
        self._deleted_message_in_personal_missed_stream_messages(False)

    @override_settings(SEND_MISSED_MESSAGE_EMAILS_AS_USER=True)
    def test_deleted_message_in_huddle_missed_stream_messages_as_user(self):
        # type: () -> None
        self._deleted_message_in_huddle_missed_stream_messages(True)

    def test_deleted_message_in_huddle_missed_stream_messages(self):
        # type: () -> None
        self._deleted_message_in_huddle_missed_stream_messages(False)
