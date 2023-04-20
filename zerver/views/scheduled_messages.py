import sys
from typing import Optional, Sequence, Union

from dateutil.parser import parse as dateparser
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
from zerver.lib.scheduled_messages import get_all_scheduled_messages
from zerver.lib.timestamp import convert_to_UTC
from zerver.lib.topic import REQ_topic
from zerver.lib.validator import check_int
from zerver.models import UserProfile

if sys.version_info < (3, 9):  # nocoverage
    from backports import zoneinfo
else:  # nocoverage
    import zoneinfo


@has_request_variables
def fetch_scheduled_messages(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    return json_success(
        request, data={"scheduled_messages": get_all_scheduled_messages(user_profile)}
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
    recipient_type_name: str = REQ("type"),
    req_to: str = REQ("to"),
    topic_name: Optional[str] = REQ_topic(),
    message_content: str = REQ("content"),
    scheduled_message_id: Optional[int] = REQ(default=None, json_validator=check_int),
    defer_until: str = REQ("deliver_at"),
    tz_guess: Optional[str] = REQ("tz_guess"),
) -> HttpResponse:
    local_tz = "UTC"
    if tz_guess:
        local_tz = tz_guess
    elif user_profile.timezone:
        local_tz = user_profile.timezone

    try:
        deliver_at = dateparser(defer_until)
    except ValueError:
        raise JsonableError(_("Invalid time format"))

    deliver_at_usertz = deliver_at
    if deliver_at_usertz.tzinfo is None:
        user_tz = zoneinfo.ZoneInfo(local_tz)
        deliver_at_usertz = deliver_at.replace(tzinfo=user_tz)
    deliver_at = convert_to_UTC(deliver_at_usertz)

    if deliver_at <= timezone_now():
        raise JsonableError(_("Time must be in the future."))

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
        "send_later",
        deliver_at,
        realm=user_profile.realm,
        forwarder_user_profile=user_profile,
    )
    return json_success(request, data={"scheduled_message_id": scheduled_message_id})
