from typing import Annotated, Literal

from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _
from pydantic import Json, NonNegativeInt

from zerver.actions.message_edit import validate_user_can_edit_message
from zerver.actions.typing import (
    check_send_typing_notification,
    do_send_direct_message_edit_typing_notification,
    do_send_stream_message_edit_typing_notification,
    do_send_stream_typing_notification,
)
from zerver.lib.exceptions import JsonableError
from zerver.lib.message import access_message
from zerver.lib.response import json_success
from zerver.lib.streams import access_stream_by_id_for_message, access_stream_for_send_message
from zerver.lib.topic import (
    maybe_rename_general_chat_to_empty_topic,
    maybe_rename_no_topic_to_empty_topic,
)
from zerver.lib.typed_endpoint import ApiParamConfig, OptionalTopic, PathOnly, typed_endpoint
from zerver.models import Recipient, UserProfile
from zerver.models.recipients import get_direct_message_group_user_ids


@typed_endpoint
def send_notification_backend(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    notification_to: Annotated[Json[list[int] | None], ApiParamConfig("to")] = None,
    operator: Annotated[Literal["start", "stop"], ApiParamConfig("op")],
    req_type: Annotated[Literal["direct", "stream", "channel"], ApiParamConfig("type")] = "direct",
    stream_id: Json[int | None] = None,
    topic: OptionalTopic = None,
) -> HttpResponse:
    recipient_type_name = req_type
    if recipient_type_name == "channel":
        # For now, use "stream" from Message.API_RECIPIENT_TYPES.
        # TODO: Use "channel" here, as well as in events and
        # message (created, schdeduled, drafts) objects/dicts.
        recipient_type_name = "stream"

    if recipient_type_name == "stream":
        if stream_id is None:
            raise JsonableError(_("Missing '{var_name}' argument").format(var_name="stream_id"))

        if topic is None:
            raise JsonableError(_("Missing topic"))

        if not user_profile.send_stream_typing_notifications:
            raise JsonableError(_("User has disabled typing notifications for channel messages"))

        # Verify that the user has access to the stream and has
        # permission to send messages to it.
        stream = access_stream_by_id_for_message(user_profile, stream_id)[0]
        access_stream_for_send_message(user_profile, stream, forwarder_user_profile=None)
        topic = maybe_rename_general_chat_to_empty_topic(topic)
        topic = maybe_rename_no_topic_to_empty_topic(topic)
        do_send_stream_typing_notification(user_profile, operator, stream, topic)
    else:
        if notification_to is None:
            raise JsonableError(_("Missing 'to' argument"))

        user_ids = notification_to
        to_length = len(user_ids)
        if to_length == 0:
            raise JsonableError(_("Empty 'to' list"))

        if not user_profile.send_private_typing_notifications:
            raise JsonableError(_("User has disabled typing notifications for direct messages"))

        check_send_typing_notification(user_profile, user_ids, operator)

    return json_success(request)


@typed_endpoint
def send_message_edit_notification_backend(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    message_id: PathOnly[NonNegativeInt],
    operator: Annotated[Literal["start", "stop"], ApiParamConfig("op")],
) -> HttpResponse:
    # Technically, this endpoint doesn't modify the message, but we're
    # attempting to send a typing notification that we're editing the
    # message.
    message = access_message(user_profile, message_id, is_modifying_message=True)
    validate_user_can_edit_message(user_profile, message, edit_limit_buffer=0)
    recipient = message.recipient

    if recipient.type == Recipient.STREAM:
        if not user_profile.send_stream_typing_notifications:
            raise JsonableError(_("User has disabled typing notifications for channel messages"))

        channel_id = recipient.type_id
        topic = message.topic_name()
        do_send_stream_message_edit_typing_notification(
            user_profile, channel_id, message_id, operator, topic
        )

    else:
        if not user_profile.send_private_typing_notifications:
            raise JsonableError(_("User has disabled typing notifications for direct messages"))

        if recipient.type == Recipient.PERSONAL:
            recipient_ids = [user_profile.id, recipient.type_id]
        else:
            recipient_ids = list(get_direct_message_group_user_ids(recipient))

        do_send_direct_message_edit_typing_notification(
            user_profile, recipient_ids, message_id, operator
        )

    return json_success(request)
