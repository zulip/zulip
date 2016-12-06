from __future__ import absolute_import
from __future__ import print_function

from typing import Any, Optional

if False:
    import zerver.tornado.event_queue

descriptors_by_handler_id = {} # type: Dict[int, zerver.tornado.event_queue.ClientDescriptor]

def get_descriptor_by_handler_id(handler_id):
    # type: (int) -> zerver.tornado.event_queue.ClientDescriptor
    return descriptors_by_handler_id.get(handler_id)

def set_descriptor_by_handler_id(handler_id, client_descriptor):
    # type: (int, zerver.tornado.event_queue.ClientDescriptor) -> None
    descriptors_by_handler_id[handler_id] = client_descriptor

def clear_descriptor_by_handler_id(handler_id, client_descriptor):
    # type: (int, Optional[zerver.tornado.event_queue.ClientDescriptor]) -> None
    del descriptors_by_handler_id[handler_id]

