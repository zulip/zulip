from __future__ import absolute_import
from typing import Any, Dict, Text

from zerver.outgoing_webhooks.generic import Generic
from zerver.models import GENERIC_INTERFACE

AVAILABLE_OUTGOING_WEBHOOK_INTERFACES = {
    GENERIC_INTERFACE: Generic
}   # type: Dict[Text, Any]

def get_service_interface_class(interface):
    # type: (Text) -> Any
    if interface is None or interface not in AVAILABLE_OUTGOING_WEBHOOK_INTERFACES:
        return AVAILABLE_OUTGOING_WEBHOOK_INTERFACES[GENERIC_INTERFACE]
    else:
        return AVAILABLE_OUTGOING_WEBHOOK_INTERFACES[interface]
