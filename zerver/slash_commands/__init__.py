from __future__ import absolute_import
from typing import Any, Dict, Text

from zerver.slash_commands.greet import GreetUser

AVAILABLE_SLASH_COMMANDS = {
    "greet": GreetUser,
}   # type: Dict[Text, Any]


def get_slash_command_handler_class(command):
    # type: (Text) -> Any
    if command in AVAILABLE_SLASH_COMMANDS:
        return AVAILABLE_SLASH_COMMANDS[command]
    else:
        raise NotImplementedError("Error: Slash command %s not found." % command,)
