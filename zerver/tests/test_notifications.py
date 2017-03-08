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
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import get_user_profile_by_email, Recipient

class TestMissedMessages(ZulipTestCase):
    def normalize_string(self, s):
        # type: (Text) -> Text
        s = s.strip()
        return re.sub(r'\s+', ' ', s)

    def _get_tokens(self):
        # type: () -> List[str]
        return [str(random.getrandbits(32)) for _ in range(30)]

    def _test_cases(self, tokens, msg_id, body, send_as_user):
        # type: (List[str], int, str, bool) -> None
        othello = get_user_profile_by_email('othello@zulip.com')
        hamlet = get_user_profile_by_email('hamlet@zulip.com')
        handle_missedmessage_emails(hamlet.id, [{'message_id': msg_id}])
        reply_to_addresses = [settings.EMAIL_GATEWAY_PATTERN % (u'mm' + t) for t in tokens]
        msg = mail.outbox[0]
        sender = 'Zulip <{}>'.format(settings.NOREPLY_EMAIL_ADDRESS)
        from_email = sender
        self.assertEqual(len(mail.outbox), 1)
        if send_as_user:
            from_email = '"%s" <%s>' % (othello.full_name, othello.email)
            self.assertEqual(msg.extra_headers['Sender'], sender)
        else:
            self.assertNotIn("Sender", msg.extra_headers)
        self.assertEqual(msg.from_email, from_email)
        self.assertIn(msg.extra_headers['Reply-To'], reply_to_addresses)
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
        self._test_cases(tokens, msg_id, body, send_as_user)

    @patch('zerver.lib.email_mirror.generate_random_token')
    def _extra_context_in_personal_missed_stream_messages(self, send_as_user, mock_random_token):
        # type: (bool, MagicMock) -> None
        tokens = self._get_tokens()
        mock_random_token.side_effect = tokens

        msg_id = self.send_message("othello@zulip.com", "hamlet@zulip.com",
                                   Recipient.PERSONAL,
                                   'Extremely personal message!')
        body = 'You and Othello, the Moor of Venice Extremely personal message!'
        self._test_cases(tokens, msg_id, body, send_as_user)

    @patch('zerver.lib.email_mirror.generate_random_token')
    def _extra_context_in_huddle_missed_stream_messages(self, send_as_user, mock_random_token):
        # type: (bool, MagicMock) -> None
        tokens = self._get_tokens()
        mock_random_token.side_effect = tokens

        msg_id = self.send_message("othello@zulip.com",
                                   ["hamlet@zulip.com", "iago@zulip.com"],
                                   Recipient.PERSONAL,
                                   'Group personal message!')

        body = ('You and Iago, Othello, the Moor of Venice Othello,'
                ' the Moor of Venice Group personal message')
        self._test_cases(tokens, msg_id, body, send_as_user)

    @override_settings(SEND_MISSED_MESSAGE_EMAILS_AS_USER=True)
    def test_extra_context_in_missed_stream_messages_as_user(self):
        # type: () -> None
        self._extra_context_in_missed_stream_messages(True)

    def test_extra_context_in_missed_stream_messages(self):
        # type: () -> None
        self._extra_context_in_missed_stream_messages(False)

    @override_settings(SEND_MISSED_MESSAGE_EMAILS_AS_USER=True)
    def test_extra_context_in_personal_missed_stream_messages_as_user(self):
        # type: () -> None
        self._extra_context_in_personal_missed_stream_messages(True)

    def test_extra_context_in_personal_missed_stream_messages(self):
        # type: () -> None
        self._extra_context_in_personal_missed_stream_messages(False)

    @override_settings(SEND_MISSED_MESSAGE_EMAILS_AS_USER=True)
    def test_extra_context_in_huddle_missed_stream_messages_as_user(self):
        # type: () -> None
        self._extra_context_in_huddle_missed_stream_messages(True)

    def test_extra_context_in_huddle_missed_stream_messages(self):
        # type: () -> None
        self._extra_context_in_huddle_missed_stream_messages(False)
