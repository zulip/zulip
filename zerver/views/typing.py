from typing import List, Optional

from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _

from zerver.actions.typing import check_send_typing_notification, do_send_stream_typing_notification
from zerver.lib.exceptions import JsonableError
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.streams import access_stream_by_id, access_stream_for_send_message
from zerver.lib.validator import check_int, check_list, check_string_in
from zerver.models import Message, UserProfile

VALID_OPERATOR_TYPES = ["start", "stop"]


@has_request_variables
def send_notification_backend(
    request: HttpRequest,
    user_profile: UserProfile,
    req_type: str = REQ(
        "type", str_validator=check_string_in(Message.API_RECIPIENT_TYPES), default="direct"
    ),
    operator: str = REQ("op", str_validator=check_string_in(VALID_OPERATOR_TYPES)),
    notification_to: List[int] = REQ("to", json_validator=check_list(check_int)),
    topic: Optional[str] = REQ("topic", default=None),
) -> HttpResponse:
    to_length = len(notification_to)

    if to_length == 0:
        raise JsonableError(_("Empty 'to' list"))

    recipient_type_name = req_type
    if recipient_type_name == "private":
        # TODO: Use "direct" in typing notification events.
        recipient_type_name = "direct"

    if recipient_type_name == "stream":
        if to_length > 1:
            raise JsonableError(_("Cannot send to multiple streams"))

        if topic is None:
            raise JsonableError(_("Missing topic"))

        if not user_profile.send_stream_typing_notifications:
            raise JsonableError(_("User has disabled typing notifications for stream messages"))

        stream_id = notification_to[0]
        # Verify that the user has access to the stream and has
        # permission to send messages to it.
        stream = access_stream_by_id(user_profile, stream_id)[0]
        access_stream_for_send_message(user_profile, stream, forwarder_user_profile=None)
        do_send_stream_typing_notification(user_profile, operator, stream, topic)
    else:
        if not user_profile.send_private_typing_notifications:
            raise JsonableError(_("User has disabled typing notifications for direct messages"))

        user_ids = notification_to
        check_send_typing_notification(user_profile, user_ids, operator)

    return json_success(request)
