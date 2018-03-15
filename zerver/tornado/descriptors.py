
from typing import Any, Dict, Optional

if False:
    from zerver.tornado.event_queue import ClientDescriptor

descriptors_by_handler_id = {}  # type: Dict[int, ClientDescriptor]

def get_descriptor_by_handler_id(handler_id: int) -> 'ClientDescriptor':
    return descriptors_by_handler_id.get(handler_id)

def set_descriptor_by_handler_id(handler_id: int,
                                 client_descriptor: 'ClientDescriptor') -> None:
    descriptors_by_handler_id[handler_id] = client_descriptor

def clear_descriptor_by_handler_id(handler_id: int,
                                   client_descriptor: 'ClientDescriptor') -> None:
    del descriptors_by_handler_id[handler_id]
