from typing import Optional, Sequence, Union

from django.http import HttpRequest, HttpResponse
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _

from zerver.actions.message_send import extract_private_recipients
from zerver.actions.scheduled_messages import (
    check_schedule_message,
    delete_scheduled_message,
)
from zerver.lib.exceptions import JsonableError
from zerver.lib.request import REQ, RequestNotes, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.scheduled_messages import get_undelivered_scheduled_messages
from zerver.lib.timestamp import timestamp_to_datetime
from zerver.lib.topic import REQ_topic
from zerver.lib.validator import check_int, check_string_in
from zerver.models import Message, UserProfile


@has_request_variables
def fetch_scheduled_messages(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    return json_success(
        request, data={"scheduled_messages": get_undelivered_scheduled_messages(user_profile)}
    )


@has_request_variables
def delete_scheduled_messages(
    request: HttpRequest, user_profile: UserProfile, scheduled_message_id: int
) -> HttpResponse:
    delete_scheduled_message(user_profile, scheduled_message_id)
    return json_success(request)


@has_request_variables
def scheduled_messages_backend(
    request: HttpRequest,
    user_profile: UserProfile,
    req_type: str = REQ("type", str_validator=check_string_in(Message.API_RECIPIENT_TYPES)),
    req_to: str = REQ("to"),
    topic_name: Optional[str] = REQ_topic(),
    message_content: str = REQ("content"),
    scheduled_message_id: Optional[int] = REQ(default=None, json_validator=check_int),
    scheduled_delivery_timestamp: int = REQ(json_validator=check_int),
) -> HttpResponse:
    recipient_type_name = req_type
    if recipient_type_name == "direct":
        # For now, use "private" from Message.API_RECIPIENT_TYPES.
        # TODO: Use "direct" here, as well as in events and
        # scheduled message objects/dicts.
        recipient_type_name = "private"

    deliver_at = timestamp_to_datetime(scheduled_delivery_timestamp)
    if deliver_at <= timezone_now():
        raise JsonableError(_("Scheduled delivery time must be in the future."))

    sender = user_profile
    client = RequestNotes.get_notes(request).client
    assert client is not None

    if recipient_type_name == "stream":
        # req_to is ID of the recipient stream.
        message_to: Union[Sequence[str], Sequence[int]] = [int(req_to)]
    else:
        message_to = extract_private_recipients(req_to)

    scheduled_message_id = check_schedule_message(
        sender,
        client,
        recipient_type_name,
        message_to,
        topic_name,
        message_content,
        scheduled_message_id,
        deliver_at,
        realm=user_profile.realm,
        forwarder_user_profile=user_profile,
    )
    return json_success(request, data={"scheduled_message_id": scheduled_message_id})
