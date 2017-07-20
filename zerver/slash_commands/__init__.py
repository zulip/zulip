from __future__ import absolute_import
from typing import Any, Dict, Text

AVAILABLE_SLASH_COMMANDS = {
}   # type: Dict[Text, Any]


def get_slash_command_handler_class(command):
    # type: (Text) -> Any
    if command in AVAILABLE_SLASH_COMMANDS:
        return AVAILABLE_SLASH_COMMANDS[command]
    else:
        raise NotImplementedError("Error: Slash command %s not found." % command,)
