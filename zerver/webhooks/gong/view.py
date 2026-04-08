# Webhooks for external integrations.

from dataclasses import dataclass
from datetime import datetime, timedelta

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import AnomalousWebhookPayloadError
from zerver.lib.response import json_success
from zerver.lib.timestamp import datetime_to_global_time
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import (
    WildValue,
    check_bool,
    check_int,
    check_iso_datetime,
    check_string,
    check_url,
)
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

GONG_TOPIC_TEMPLATE = "Gong Call: {call_title}"
GONG_MESSAGE_TEMPLATE = """\
:phone: Gong call completed: **[{call_title}]({call_url})**! :phone:

**Call time:** {starttime_string} to {endtime_string} ({formatted_duration})
**Scheduled time**: {scheduled_string}
**Participants**:
{participants}
"""


@dataclass
class GongData:
    call_url: str
    call_title: str
    scheduled: datetime
    started: datetime
    duration: int
    participants: str


def duration_pretty(duration: int) -> str:
    (hours, rest) = divmod(duration, 3600)
    (minutes, seconds) = divmod(rest, 60)
    if seconds >= 30:
        minutes = minutes + 1
    if minutes == 60:
        hours = hours + 1
        minutes = 0
    hour_word = "hour" if hours == 1 else "hours"
    minute_word = "minute" if minutes == 1 else "minutes"
    if hours > 0:
        if minutes == 0:
            return f"{hours} {hour_word}"
        return f"{hours} {hour_word} {minutes} {minute_word}"
    return f"{minutes} {minute_word}"


def format_participant(party_payload: WildValue) -> str:
    name = party_payload["name"].tame(check_string)
    title_part = (
        (": " + party_payload["title"].tame(check_string)) if "title" in party_payload else ""
    )
    if "emailAddress" in party_payload and "phoneNumber" in party_payload:
        contact_part = (
            " ("
            + party_payload["emailAddress"].tame(check_string)
            + ", "
            + party_payload["phoneNumber"].tame(check_string)
            + ")"
        )
    elif "emailAddress" in party_payload:
        contact_part = " (" + party_payload["emailAddress"].tame(check_string) + ")"
    elif "phoneNumber" in party_payload:
        contact_part = " (" + party_payload["phoneNumber"].tame(check_string) + ")"
    else:
        contact_part = ""
    return f"* {name}{title_part}{contact_part}"


def parse_payload(gong_payload: WildValue) -> GongData:
    return GongData(
        call_url=gong_payload["metaData"]["url"].tame(check_url),
        call_title=gong_payload["metaData"]["title"].tame(check_string),
        scheduled=gong_payload["metaData"]["scheduled"].tame(check_iso_datetime),
        started=gong_payload["metaData"]["started"].tame(check_iso_datetime),
        duration=gong_payload["metaData"]["duration"].tame(check_int),
        participants="\n".join(format_participant(party) for party in gong_payload["parties"]),
    )


def create_topic(data: GongData) -> str:
    return GONG_TOPIC_TEMPLATE.format(call_title=data.call_title)


def create_body(data: GongData) -> str:
    return GONG_MESSAGE_TEMPLATE.format(
        call_title=data.call_title,
        call_url=data.call_url,
        scheduled_string=datetime_to_global_time(data.scheduled),
        starttime_string=datetime_to_global_time(data.started),
        endtime_string=datetime_to_global_time(data.started + timedelta(seconds=data.duration)),
        formatted_duration=duration_pretty(data.duration),
        participants=data.participants,
    )


@webhook_view("Gong")
@typed_endpoint
def api_gong_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
) -> HttpResponse:
    if "isTest" not in payload:
        raise AnomalousWebhookPayloadError
    elif payload["isTest"].tame(check_bool):
        topic = "Gong call test"
        body = ":phone: Gong webhook test received! :phone:"
    elif "callData" in payload:
        data = parse_payload(payload["callData"])
        topic = create_topic(data)
        body = create_body(data)
    else:
        raise AnomalousWebhookPayloadError
    check_send_webhook_message(request, user_profile, topic, body)
    return json_success(request)
