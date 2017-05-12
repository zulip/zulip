from __future__ import absolute_import
from typing import Any, Dict, Text

AVAILABLE_OUTGOING_WEBHOOK_INTERFACES = {}   # type: Dict[Text, Any]

def get_service_interface_class(interface):
    # type: (Text) -> Any
    return AVAILABLE_OUTGOING_WEBHOOK_INTERFACES[interface]
