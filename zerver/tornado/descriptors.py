from typing import TYPE_CHECKING, Optional

from django.conf import settings

if TYPE_CHECKING:
    from zerver.tornado.event_queue import ClientDescriptor

descriptors_by_handler_id: dict[int, "ClientDescriptor"] = {}


def get_descriptor_by_handler_id(handler_id: int) -> Optional["ClientDescriptor"]:
    return descriptors_by_handler_id.get(handler_id)


def set_descriptor_by_handler_id(handler_id: int, client_descriptor: "ClientDescriptor") -> None:
    descriptors_by_handler_id[handler_id] = client_descriptor


def clear_descriptor_by_handler_id(handler_id: int) -> None:
    del descriptors_by_handler_id[handler_id]


current_port: int | None = None


def is_current_port(port: int) -> int | None:
    return settings.TEST_SUITE or current_port == port


def set_current_port(port: int) -> None:
    global current_port
    current_port = port
