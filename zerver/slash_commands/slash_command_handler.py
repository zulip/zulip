from __future__ import absolute_import
from typing import Mapping, Any

from zerver.models import get_realm_by_email_domain, get_slash_command_owner_bot, get_client
from zerver.lib.actions import check_send_message


class SlashCommandHandler(object):

    def send_reply(self, event, response_message_content):
        # type: (Mapping[str, Any], str) -> None
        message = event['message']
        recipient_type_name = message['type']
        realm = get_realm_by_email_domain(message['sender_email'])
        command = event['command']
        command_owner_bot = get_slash_command_owner_bot(command)

        if recipient_type_name == 'stream':
            recipients = [message['display_recipient']]
            check_send_message(command_owner_bot, get_client("SlashCommandResponse"), recipient_type_name,
                               recipients, message['subject'], response_message_content, realm,
                               forwarder_user_profile=command_owner_bot)
        else:
            # Private message; only send if the bot is there in the recipients
            recipients = [recipient['email'] for recipient in message['display_recipient']]
            if command_owner_bot.email in recipients:
                check_send_message(command_owner_bot, get_client("SlashCommandResponse"), recipient_type_name,
                                   recipients, message['subject'], response_message_content, realm,
                                   forwarder_user_profile=command_owner_bot)

    def handle_event(self, event):
        # type: (Mapping[str, Any]) -> None
        raise NotImplementedError()
