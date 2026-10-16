# Events as handed to Tornado, for the event types whose payload
# Tornado rewrites before delivery. zerver/lib/event_types.py describes
# what clients receive; the fields declared only here are consumed by
# zerver/tornado/event_queue.py and never reach a client, so they are
# not part of the documented API.
from typing import Literal

from zerver.lib.event_types import (
    BaseEvent,
    BaseEventModel,
    UpdateMessageOptionalFields,
    UserGroupAddEvent,
    UserGroupUpdateEvent,
)


class InternalMessageNotificationFields(BaseEventModel):
    # The per-recipient inputs process_message_event and
    # process_message_update_event use to decide push and email
    # notifications. update_message events carry them only for content
    # edits, hence optional.
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
    disable_external_notifications: bool | None = None


class InternalMessageEvent(InternalMessageNotificationFields, BaseEvent):
    # Not a subclass of the model clients receive: message is the
    # message id and message_dict the wide dict, from which
    # process_message_event finalizes the payload per client.
    type: Literal["message"] = "message"
    message: int
    message_dict: dict[str, object]
    realm_host: str
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


class InternalUpdateMessageEvent(
    InternalMessageNotificationFields, UpdateMessageOptionalFields, BaseEvent
):
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
    prior_mention_user_ids: list[int] | None = None


class InternalUserGroupAddEvent(UserGroupAddEvent):
    # Lets process_user_group_creation_event skip clients that never
    # stopped seeing the group, because they receive deactivated groups.
    for_reactivation: bool


class InternalUserGroupUpdateEvent(UserGroupUpdateEvent):
    # Set only for name updates; when the group is deactivated,
    # process_user_group_name_update_event withholds the event from
    # clients that do not receive deactivated groups.
    deactivated: bool | None = None
