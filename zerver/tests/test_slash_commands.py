# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import print_function

import mock
from typing import Text, Optional, Sequence

from zerver.models import get_client, get_realm_by_email_domain, UserProfile, Client, Realm
from zerver.lib.test_classes import ZulipTestCase
from zerver.slash_commands.slash_command_handler import SlashCommandHandler

class TestSlashCommandHandler(ZulipTestCase):

    @mock.patch('zerver.slash_commands.slash_command_handler.get_slash_command_owner_bot')
    @mock.patch('zerver.slash_commands.slash_command_handler.check_send_message')
    def test_send_reply(self, mock_check_send_message, mock_get_slash_command_owner_bot):
        # type: (mock.Mock, mock.Mock) -> None

        def check_values_passed(sender, client, message_type_name, message_to, subject_name, message_content,
                                realm=None, forged=False, forged_timestamp=None, forwarder_user_profile=None,
                                local_id=None, sender_queue_id=None):
            # type: (UserProfile, Client, Text, Sequence[Text], Optional[Text], Text, Optional[Realm], bool, Optional[float], Optional[UserProfile], Optional[Text], Optional[Text]) -> int
            self.assertEqual(sender, self.example_user('hamlet'))
            self.assertEqual(client, get_client("SlashCommandResponse"))
            self.assertEqual(message_type_name, recipient_type_name)
            if recipient_type_name == "stream":
                self.assertEqual(message_to, recipients_stream)
            else:
                self.assertEqual(message_to, recipients_private)
            self.assertEqual(subject_name, subject)
            self.assertEqual(message_content, response_message_content)
            self.assertEqual(realm, get_realm_by_email_domain(u'hamlet@zulip.com'))
            self.assertEqual(forwarder_user_profile, self.example_user('hamlet'))

            return 0

        mock_check_send_message.side_effect = check_values_passed
        mock_get_slash_command_owner_bot.return_value = self.example_user('hamlet')
        handler = SlashCommandHandler()

        recipient_type_name = "stream"
        recipient = dict(email=u'hamlet@zulip.com')
        recipients_stream = [recipient]
        recipients_private = [u'hamlet@zulip.com']
        subject = "abcd"
        response_message_content = "stream_message1"

        event = {
            'message': {
                'type': recipient_type_name,
                'sender_email': u'hamlet@zulip.com',
                'display_recipient': recipient,
                'subject': subject
            },
            'command': 'test',
        }
        handler.send_reply(event, response_message_content)

        recipient_type_name = "private"

        event = {
            'message': {
                'type': recipient_type_name,
                'sender_email': u'hamlet@zulip.com',
                'display_recipient': recipients_stream,
                'subject': subject
            },
            'command': 'test',
        }
        handler.send_reply(event, response_message_content)
