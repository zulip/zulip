# Events as handed to Tornado, for the event types whose payload
# Tornado rewrites before delivery. zerver/lib/event_types.py describes
# what clients receive; the fields declared only here are consumed by
# zerver/tornado/event_queue.py and never reach a client, so they are
# not part of the documented API.
from typing import Literal

from zerver.lib.event_types import (
    BaseEvent,
    DeleteMessageEvent,
    LegacyPresence,
    ModernPresence,
    UserGroupAddEvent,
    UserGroupUpdateEvent,
)


class InternalDeleteMessageEvent(DeleteMessageEvent):
    # Always the bulk form; process_deletion_event expands it into one
    # message_id event per message for clients without the
    # bulk_message_deletion capability.
    message_ids: list[int]


class InternalPresenceEvent(BaseEvent):
    # Not a subclass of the model clients receive: process_presence_event
    # builds the legacy, slim and modern presence events from this,
    # picking per client capability.
    type: Literal["presence"] = "presence"
    user_id: int
    email: str
    server_timestamp: float
    legacy_presence: dict[str, LegacyPresence]
    modern_presence: ModernPresence


class InternalUserGroupAddEvent(UserGroupAddEvent):
    # Lets process_user_group_creation_event skip clients that never
    # stopped seeing the group, because they receive deactivated groups.
    for_reactivation: bool


class InternalUserGroupUpdateEvent(UserGroupUpdateEvent):
    # Set only for name updates; when the group is deactivated,
    # process_user_group_name_update_event withholds the event from
    # clients that do not receive deactivated groups.
    deactivated: bool | None = None
