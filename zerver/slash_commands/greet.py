from __future__ import absolute_import
from zerver.slash_commands.slash_command_handler import SlashCommandHandler
from typing import Mapping, Any

class GreetUser(SlashCommandHandler):

    def handle_event(self, event):
        # type: (Mapping[str, Any]) -> None
        user_full_name = event['message']['sender_full_name']
        response_message_content = "Hello %s! Welcome to Zulip!" % (user_full_name,)
        self.send_reply(event, response_message_content)
