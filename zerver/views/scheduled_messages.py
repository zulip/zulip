from typing import Optional

from django.http import HttpRequest, HttpResponse
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _

from zerver.actions.scheduled_messages import (
    check_schedule_message,
    delete_scheduled_message,
    edit_scheduled_message,
)
from zerver.lib.exceptions import JsonableError
from zerver.lib.recipient_parsing import extract_direct_message_recipient_ids, extract_stream_id
from zerver.lib.request import REQ, RequestNotes, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.scheduled_messages import get_undelivered_scheduled_messages
from zerver.lib.timestamp import timestamp_to_datetime
from zerver.lib.topic import REQ_topic
from zerver.lib.validator import check_bool, check_int, check_string_in, to_non_negative_int
from zerver.models import Message, UserProfile


@has_request_variables
def fetch_scheduled_messages(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    return json_success(
        request, data={"scheduled_messages": get_undelivered_scheduled_messages(user_profile)}
    )


@has_request_variables
def delete_scheduled_messages(
    request: HttpRequest,
    user_profile: UserProfile,
    scheduled_message_id: int = REQ(converter=to_non_negative_int, path_only=True),
) -> HttpResponse:
    delete_scheduled_message(user_profile, scheduled_message_id)
    return json_success(request)


@has_request_variables
def update_scheduled_message_backend(
    request: HttpRequest,
    user_profile: UserProfile,
    scheduled_message_id: int = REQ(converter=to_non_negative_int, path_only=True),
    req_type: Optional[str] = REQ(
        "type", str_validator=check_string_in(Message.API_RECIPIENT_TYPES), default=None
    ),
    req_to: Optional[str] = REQ("to", default=None),
    topic_name: Optional[str] = REQ_topic(),
    message_content: Optional[str] = REQ("content", default=None),
    scheduled_delivery_timestamp: Optional[int] = REQ(json_validator=check_int, default=None),
) -> HttpResponse:
    if (
        req_type is None
        and req_to is None
        and topic_name is None
        and message_content is None
        and scheduled_delivery_timestamp is None
    ):
        raise JsonableError(_("Nothing to change"))

    recipient_type_name = None
    if req_type:
        if req_to is None:
            raise JsonableError(_("Recipient required when updating type of scheduled message."))
        else:
            recipient_type_name = req_type

    if recipient_type_name is not None and recipient_type_name == "channel":
        # For now, use "stream" from Message.API_RECIPIENT_TYPES.
        # TODO: Use "channel" here, as well as in events and
        # message (created, schdeduled, drafts) objects/dicts.
        recipient_type_name = "stream"

    if recipient_type_name is not None and recipient_type_name == "stream" and topic_name is None:
        raise JsonableError(_("Topic required when updating scheduled message type to channel."))

    if recipient_type_name is not None and recipient_type_name == "direct":
        # For now, use "private" from Message.API_RECIPIENT_TYPES.
        # TODO: Use "direct" here, as well as in events and
        # scheduled message objects/dicts.
        recipient_type_name = "private"

    message_to = None
    if req_to is not None:
        # Because the recipient_type_name may not be updated/changed,
        # we extract these updated recipient IDs in edit_scheduled_message.
        message_to = req_to

    deliver_at = None
    if scheduled_delivery_timestamp is not None:
        deliver_at = timestamp_to_datetime(scheduled_delivery_timestamp)
        if deliver_at <= timezone_now():
            raise JsonableError(_("Scheduled delivery time must be in the future."))

    sender = user_profile
    client = RequestNotes.get_notes(request).client
    assert client is not None

    edit_scheduled_message(
        sender,
        client,
        scheduled_message_id,
        recipient_type_name,
        message_to,
        topic_name,
        message_content,
        deliver_at,
        realm=user_profile.realm,
    )

    return json_success(request)


@has_request_variables
def create_scheduled_message_backend(
    request: HttpRequest,
    user_profile: UserProfile,
    req_type: str = REQ("type", str_validator=check_string_in(Message.API_RECIPIENT_TYPES)),
    req_to: str = REQ("to"),
    topic_name: Optional[str] = REQ_topic(),
    message_content: str = REQ("content"),
    scheduled_delivery_timestamp: int = REQ(json_validator=check_int),
    read_by_sender: Optional[bool] = REQ(json_validator=check_bool, default=None),
) -> HttpResponse:
    recipient_type_name = req_type
    if recipient_type_name == "direct":
        # For now, use "private" from Message.API_RECIPIENT_TYPES.
        # TODO: Use "direct" here, as well as in events and
        # scheduled message objects/dicts.
        recipient_type_name = "private"
    elif recipient_type_name == "channel":
        # For now, use "stream" from Message.API_RECIPIENT_TYPES.
        # TODO: Use "channel" here, as well as in events and
        # message (created, schdeduled, drafts) objects/dicts.
        recipient_type_name = "stream"

    deliver_at = timestamp_to_datetime(scheduled_delivery_timestamp)
    if deliver_at <= timezone_now():
        raise JsonableError(_("Scheduled delivery time must be in the future."))

    sender = user_profile
    client = RequestNotes.get_notes(request).client
    assert client is not None

    if recipient_type_name == "stream":
        stream_id = extract_stream_id(req_to)
        message_to = [stream_id]
    else:
        message_to = extract_direct_message_recipient_ids(req_to)

    scheduled_message_id = check_schedule_message(
        sender,
        client,
        recipient_type_name,
        message_to,
        topic_name,
        message_content,
        deliver_at,
        realm=user_profile.realm,
        forwarder_user_profile=user_profile,
        read_by_sender=read_by_sender,
    )
    return json_success(request, data={"scheduled_message_id": scheduled_message_id})
