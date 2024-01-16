from typing import List, Optional

from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _

from zerver.actions.message_edit import validate_user_can_edit_message
from zerver.actions.typing import (
    check_send_typing_notification,
    do_send_direct_message_edit_typing_notification,
    do_send_stream_message_edit_typing_notification,
    do_send_stream_typing_notification,
)
from zerver.lib.exceptions import JsonableError
from zerver.lib.message import access_message
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.streams import access_stream_by_id, access_stream_for_send_message
from zerver.lib.validator import check_int, check_list, check_string_in
from zerver.models import Recipient, UserProfile
from zerver.models.recipients import get_huddle_user_ids

VALID_OPERATOR_TYPES = ["start", "stop"]
VALID_RECIPIENT_TYPES = ["direct", "stream", "channel"]


@has_request_variables
def send_notification_backend(
    request: HttpRequest,
    user_profile: UserProfile,
    req_type: str = REQ(
        "type", str_validator=check_string_in(VALID_RECIPIENT_TYPES), default="direct"
    ),
    operator: str = REQ("op", str_validator=check_string_in(VALID_OPERATOR_TYPES)),
    notification_to: Optional[List[int]] = REQ(
        "to", json_validator=check_list(check_int), default=None
    ),
    stream_id: Optional[int] = REQ(json_validator=check_int, default=None),
    topic: Optional[str] = REQ("topic", default=None),
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
        stream = access_stream_by_id(user_profile, stream_id)[0]
        access_stream_for_send_message(user_profile, stream, forwarder_user_profile=None)
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


@has_request_variables
def send_message_edit_notification_backend(
    request: HttpRequest,
    user_profile: UserProfile,
    operator: str = REQ("op", str_validator=check_string_in(VALID_OPERATOR_TYPES)),
    message_id: int = REQ(json_validator=check_int),
) -> HttpResponse:
    message = access_message(user_profile, message_id)
    recipient = message.recipient

    validate_user_can_edit_message(user_profile, message, 0)

    if recipient.type == Recipient.STREAM:
        if not user_profile.send_stream_typing_notifications:
            raise JsonableError(_("User has disabled typing notifications for stream messages"))

        channel_id = recipient.type_id
        do_send_stream_message_edit_typing_notification(
            user_profile, channel_id, message_id, operator
        )

    else:
        if not user_profile.send_private_typing_notifications:
            raise JsonableError(_("User has disabled typing notifications for direct messages"))

        if recipient.type == Recipient.PERSONAL:
            recipient_ids = [recipient.type_id]
        else:
            recipient_ids = list(get_huddle_user_ids(recipient))

        do_send_direct_message_edit_typing_notification(
            user_profile, recipient_ids, message_id, operator
        )

    return json_success(request)
