from __future__ import absolute_import
from typing import Any, Dict
from six import text_type

AVAILABLE_OUTGOING_WEBHOOKS = {}   # type: Dict[text_type, Any]

def get_bot_instance_class(bot_name):
    # type: (text_type) -> Any
    return AVAILABLE_OUTGOING_WEBHOOKS[bot_name]
