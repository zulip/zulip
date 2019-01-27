import os

from zerver.lib.request import JsonableError
from zerver.lib.topic import (
    get_topic_from_message_info,
)
from django.conf import settings
from django.utils.translation import ugettext as _

from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence

stop_words_list = None  # type: Optional[List[str]]
def read_stop_words() -> List[str]:
    global stop_words_list
    if stop_words_list is None:
        file_path = os.path.join(settings.DEPLOY_ROOT, "puppet/zulip/files/postgresql/zulip_english.stop")
        with open(file_path, 'r') as f:
            stop_words_list = f.read().splitlines()

    return stop_words_list

def check_supported_events_narrow_filter(narrow: Iterable[Sequence[str]]) -> None:
    for element in narrow:
        operator = element[0]
        if operator not in ["stream", "topic", "sender", "is"]:
            raise JsonableError(_("Operator %s not supported.") % (operator,))

def is_web_public_compatible(narrow: Iterable[Dict[str, str]]) -> bool:
    for element in narrow:
        operator = element['operator']
        if 'operand' not in element:
            return False
        if operator not in ["stream", "topic", "sender", "has", "search", "near", "id"]:
            return False
    return True

def build_narrow_filter(narrow: Iterable[Sequence[str]]) -> Callable[[Mapping[str, Any]], bool]:
    """Changes to this function should come with corresponding changes to
    BuildNarrowFilterTest."""
    check_supported_events_narrow_filter(narrow)

    def narrow_filter(event: Mapping[str, Any]) -> bool:
        message = event["message"]
        flags = event["flags"]
        for element in narrow:
            operator = element[0]
            operand = element[1]
            if operator == "stream":
                if message["type"] != "stream":
                    return False
                if operand.lower() != message["display_recipient"].lower():
                    return False
            elif operator == "topic":
                if message["type"] != "stream":
                    return False
                topic_name = get_topic_from_message_info(message)
                if operand.lower() != topic_name.lower():
                    return False
            elif operator == "sender":
                if operand.lower() != message["sender_email"].lower():
                    return False
            elif operator == "is" and operand == "private":
                if message["type"] != "private":
                    return False
            elif operator == "is" and operand in ["starred"]:
                if operand not in flags:
                    return False
            elif operator == "is" and operand == "unread":
                if "read" in flags:
                    return False
            elif operator == "is" and operand in ["alerted", "mentioned"]:
                if "mentioned" not in flags:
                    return False

        return True
    return narrow_filter
