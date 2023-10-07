from typing import Optional

from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _

from zerver.actions.typing import check_send_typing_notification, do_send_stream_typing_notification
from zerver.lib.exceptions import JsonableError
from zerver.lib.recipient_parsing import extract_direct_message_recipient_ids, extract_stream_id
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.streams import access_stream_by_id, access_stream_for_send_message
from zerver.lib.validator import check_string_in
from zerver.models import UserProfile

VALID_OPERATOR_TYPES = ["start", "stop"]
VALID_RECIPIENT_TYPES = ["direct", "stream"]


@has_request_variables
def send_notification_backend(
    request: HttpRequest,
    user_profile: UserProfile,
    req_type: str = REQ(
        "type", str_validator=check_string_in(VALID_RECIPIENT_TYPES), default="direct"
    ),
    operator: str = REQ("op", str_validator=check_string_in(VALID_OPERATOR_TYPES)),
    notification_to: str = REQ("to"),
    topic: Optional[str] = REQ("topic", default=None),
) -> HttpResponse:
    recipient_type_name = req_type
    if recipient_type_name == "stream":
        stream_id = extract_stream_id(notification_to)
        if topic is None:
            raise JsonableError(_("Missing topic"))

        if not user_profile.send_stream_typing_notifications:
            raise JsonableError(_("User has disabled typing notifications for stream messages"))

        # Verify that the user has access to the stream and has
        # permission to send messages to it.
        stream = access_stream_by_id(user_profile, stream_id)[0]
        access_stream_for_send_message(user_profile, stream, forwarder_user_profile=None)
        do_send_stream_typing_notification(user_profile, operator, stream, topic)
    else:
        user_ids = extract_direct_message_recipient_ids(notification_to)
        to_length = len(user_ids)
        if to_length == 0:
            raise JsonableError(_("Empty 'to' list"))

        if not user_profile.send_private_typing_notifications:
            raise JsonableError(_("User has disabled typing notifications for direct messages"))

        check_send_typing_notification(user_profile, user_ids, operator)

    return json_success(request)
