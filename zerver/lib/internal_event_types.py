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
    RealmEmoji,
    RealmEmojiAddEvent,
    RealmEmojiUpdateOneEvent,
    RealmUserAddEvent,
    StreamCreateEvent,
    StreamDeleteEvent,
    UpdateMessageOptionalFields,
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


class InternalMessageEvent(BaseEvent):
    # Not a subclass of the model clients receive: message is the
    # message id and message_dict the wide dict, from which
    # process_message_event finalizes the payload per client.
    type: Literal["message"] = "message"
    message: int
    message_dict: dict[str, object]
    realm_host: str
    # The per-recipient inputs process_message_event uses to decide
    # push and email notifications.
    presence_idle_user_ids: list[int]
    online_push_user_ids: list[int]
    dm_mention_push_disabled_user_ids: list[int]
    dm_mention_email_disabled_user_ids: list[int]
    stream_push_user_ids: list[int]
    stream_email_user_ids: list[int]
    topic_wildcard_mention_user_ids: list[int]
    stream_wildcard_mention_user_ids: list[int]
    followed_topic_push_user_ids: list[int]
    followed_topic_email_user_ids: list[int]
    topic_wildcard_mention_in_followed_topic_user_ids: list[int]
    stream_wildcard_mention_in_followed_topic_user_ids: list[int]
    muted_sender_user_ids: list[int]
    all_bot_user_ids: list[int]
    push_device_registered_user_ids: list[int]
    disable_external_notifications: bool
    # Set for channel messages, to route to clients registered for all
    # public channels and to withhold the sender from users who cannot
    # access them.
    realm_id: int | None = None
    stream_name: str | None = None
    realm_guest_user_ids: list[int] | None = None
    invite_only: bool | None = None
    is_web_public: bool | None = None
    user_ids_without_access_to_sender: list[int] | None = None
    # Echoed back to the sending client only.
    local_id: str | None = None
    sender_queue_id: str | None = None


class InternalUpdateMessageEvent(UpdateMessageOptionalFields, BaseEvent):
    # The required fields of UpdateMessageEvent, except flags, which
    # process_message_update_event adds per recipient, and message_ids,
    # which do_update_message only knows once the edit has been applied
    # to every affected message.
    type: Literal["update_message"] = "update_message"
    user_id: int | None
    edit_timestamp: int
    message_id: int
    rendering_only: bool
    message_ids: list[int] | None = None
    # The per-recipient inputs process_message_update_event uses to
    # decide push and email notifications, set only for content edits.
    prior_mention_user_ids: list[int] | None = None
    presence_idle_user_ids: list[int] | None = None
    online_push_user_ids: list[int] | None = None
    dm_mention_push_disabled_user_ids: list[int] | None = None
    dm_mention_email_disabled_user_ids: list[int] | None = None
    stream_push_user_ids: list[int] | None = None
    stream_email_user_ids: list[int] | None = None
    topic_wildcard_mention_user_ids: list[int] | None = None
    stream_wildcard_mention_user_ids: list[int] | None = None
    followed_topic_push_user_ids: list[int] | None = None
    followed_topic_email_user_ids: list[int] | None = None
    topic_wildcard_mention_in_followed_topic_user_ids: list[int] | None = None
    stream_wildcard_mention_in_followed_topic_user_ids: list[int] | None = None
    muted_sender_user_ids: list[int] | None = None
    all_bot_user_ids: list[int] | None = None
    push_device_registered_user_ids: list[int] | None = None


class InternalUserGroupAddEvent(UserGroupAddEvent):
    # Lets process_user_group_creation_event skip clients that never
    # stopped seeing the group, because they receive deactivated groups.
    for_reactivation: bool


class InternalUserGroupUpdateEvent(UserGroupUpdateEvent):
    # Set only for name updates; when the group is deactivated,
    # process_user_group_name_update_event withholds the event from
    # clients that do not receive deactivated groups.
    deactivated: bool | None = None
