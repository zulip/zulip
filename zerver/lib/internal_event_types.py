# Events as handed to Tornado, for the event types whose payload
# Tornado rewrites before delivery. zerver/lib/event_types.py describes
# what clients receive; the fields added here are consumed by
# zerver/tornado/event_queue.py and never reach a client, so they are
# not part of the documented API.
from zerver.lib.event_types import (
    RealmEmoji,
    RealmEmojiAddEvent,
    RealmEmojiUpdateOneEvent,
    RealmUserAddEvent,
    StreamCreateEvent,
    StreamDeleteEvent,
    UserGroupAddEvent,
    UserGroupUpdateEvent,
)


class InternalRealmEmojiAddEvent(RealmEmojiAddEvent):
    # The full emoji dict, which process_realm_emoji_event sends as a
    # realm_emoji/update event to clients without the
    # individual_emoji_changes capability.
    realm_emoji: dict[str, RealmEmoji]


class InternalRealmEmojiUpdateOneEvent(RealmEmojiUpdateOneEvent):
    realm_emoji: dict[str, RealmEmoji]


class InternalRealmUserAddEvent(RealmUserAddEvent):
    # Lets process_realm_user_add_event skip clients with the
    # user_list_incomplete capability, which do not track users they
    # cannot access.
    inaccessible_user: bool


class InternalStreamCreateEvent(StreamCreateEvent):
    # Lets process_stream_creation_event skip clients that never
    # stopped seeing the channel, because they receive archived
    # channels.
    for_unarchiving: bool


class InternalStreamDeleteEvent(StreamDeleteEvent):
    # Lets process_stream_deletion_event skip clients that keep
    # seeing the channel, because they receive archived channels.
    for_archiving: bool


class InternalUserGroupAddEvent(UserGroupAddEvent):
    # Lets process_user_group_creation_event skip clients that never
    # stopped seeing the group, because they receive deactivated groups.
    for_reactivation: bool


class InternalUserGroupUpdateEvent(UserGroupUpdateEvent):
    # Set only for name updates; when the group is deactivated,
    # process_user_group_name_update_event withholds the event from
    # clients that do not receive deactivated groups.
    deactivated: bool | None = None
