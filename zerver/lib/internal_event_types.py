# Events as handed to Tornado, for the event types whose payload
# Tornado rewrites before delivery. zerver/lib/event_types.py describes
# what clients receive; the fields added here are consumed by
# zerver/tornado/event_queue.py and never reach a client, so they are
# not part of the documented API.
from zerver.lib.event_types import UserGroupAddEvent, UserGroupUpdateEvent


class InternalUserGroupAddEvent(UserGroupAddEvent):
    # Lets process_user_group_creation_event skip clients that never
    # stopped seeing the group, because they receive deactivated groups.
    for_reactivation: bool


class InternalUserGroupUpdateEvent(UserGroupUpdateEvent):
    # Set only for name updates, which
    # process_user_group_name_update_event withholds from clients that
    # do not receive deactivated groups.
    deactivated: bool | None = None
