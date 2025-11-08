# Webhooks for external integrations.
import re

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventTypeError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_int, check_none_or, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

TOPIC_TEMPLATE = "{service_url}"


def send_message_for_event(
    request: HttpRequest, user_profile: UserProfile, event: WildValue
) -> None:
    event_type = get_event_type(event)
    topic_name = TOPIC_TEMPLATE.format(service_url=event["check"]["url"].tame(check_string))
    body = EVENT_TYPE_BODY_MAPPER[event_type](event)
    check_send_webhook_message(request, user_profile, topic_name, body, event_type)


def get_body_for_up_event(event: WildValue) -> str:
    body = "Service is `up`"
    event_downtime = event["downtime"]
    if event_downtime["started_at"].tame(check_none_or(check_string)):
        body = f"{body} again"
        duration = event_downtime["duration"].tame(check_none_or(check_int))
        if duration:
            string_date = get_time_string_based_on_duration(duration)
            if string_date:
                body = f"{body} after {string_date}"
    return f"{body}."


def get_time_string_based_on_duration(duration: int) -> str:
    days, reminder = divmod(duration, 86400)
    hours, reminder = divmod(reminder, 3600)
    minutes, seconds = divmod(reminder, 60)

    string_date = ""
    string_date += add_time_part_to_string_date_if_needed(days, "day")
    string_date += add_time_part_to_string_date_if_needed(hours, "hour")
    string_date += add_time_part_to_string_date_if_needed(minutes, "minute")
    string_date += add_time_part_to_string_date_if_needed(seconds, "second")
    return string_date.rstrip()


def add_time_part_to_string_date_if_needed(value: int, text_name: str) -> str:
    if value == 1:
        return f"1 {text_name} "
    if value > 1:
        return f"{value} {text_name}s "
    return ""


def get_body_for_down_event(event: WildValue) -> str:
    return "Service is `down`. It returned a {} error at {}.".format(
        event["downtime"]["error"].tame(check_none_or(check_string)),
        event["downtime"]["started_at"]
        .tame(check_string)  # started_at is not None in a "down" event.
        .replace("T", " ")
        .replace("Z", " UTC"),
    )


EVENT_TYPE_BODY_MAPPER = {
    "up": get_body_for_up_event,
    "down": get_body_for_down_event,
}
ALL_EVENT_TYPES = list(EVENT_TYPE_BODY_MAPPER.keys())


@webhook_view("Updown", all_event_types=ALL_EVENT_TYPES)
@typed_endpoint
def api_updown_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
) -> HttpResponse:
    for event in payload:
        send_message_for_event(request, user_profile, event)
    return json_success(request)


def get_event_type(event: WildValue) -> str:
    event_type_match = re.match(r"check.(.*)", event["event"].tame(check_string))
    if event_type_match:
        event_type = event_type_match.group(1)
        if event_type in EVENT_TYPE_BODY_MAPPER:
            return event_type
    raise UnsupportedWebhookEventTypeError(event["event"].tame(check_string))
