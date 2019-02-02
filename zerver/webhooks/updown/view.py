# Webhooks for external integrations.
import re
from typing import Any, Dict, List

from django.http import HttpRequest, HttpResponse

from zerver.decorator import api_key_only_webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message, \
    UnexpectedWebhookEventType
from zerver.models import UserProfile

TOPIC_TEMPLATE = "{service_url}"

def send_message_for_event(request: HttpRequest, user_profile: UserProfile,
                           event: Dict[str, Any]) -> None:
    event_type = get_event_type(event)
    subject = TOPIC_TEMPLATE.format(service_url=event['check']['url'])
    body = EVENT_TYPE_BODY_MAPPER[event_type](event)
    check_send_webhook_message(request, user_profile, subject, body)

def get_body_for_up_event(event: Dict[str, Any]) -> str:
    body = "Service is `up`"
    event_downtime = event['downtime']
    if event_downtime['started_at']:
        body = "{} again".format(body)
        string_date = get_time_string_based_on_duration(event_downtime['duration'])
        if string_date:
            body = "{} after {}".format(body, string_date)
    return "{}.".format(body)

def get_time_string_based_on_duration(duration: int) -> str:
    days, reminder = divmod(duration, 86400)
    hours, reminder = divmod(reminder, 3600)
    minutes, seconds = divmod(reminder, 60)

    string_date = ''
    string_date += add_time_part_to_string_date_if_needed(days, 'day')
    string_date += add_time_part_to_string_date_if_needed(hours, 'hour')
    string_date += add_time_part_to_string_date_if_needed(minutes, 'minute')
    string_date += add_time_part_to_string_date_if_needed(seconds, 'second')
    return string_date.rstrip()

def add_time_part_to_string_date_if_needed(value: int, text_name: str) -> str:
    if value == 1:
        return "1 {} ".format(text_name)
    if value > 1:
        return "{} {}s ".format(value, text_name)
    return ''

def get_body_for_down_event(event: Dict[str, Any]) -> str:
    return "Service is `down`. It returned a {} error at {}.".format(
        event['downtime']['error'],
        event['downtime']['started_at'].replace('T', ' ').replace('Z', ' UTC'))

@api_key_only_webhook_view('Updown')
@has_request_variables
def api_updown_webhook(
        request: HttpRequest, user_profile: UserProfile,
        payload: List[Dict[str, Any]]=REQ(argument_type='body')
) -> HttpResponse:
    for event in payload:
        send_message_for_event(request, user_profile, event)
    return json_success()

EVENT_TYPE_BODY_MAPPER = {
    'up': get_body_for_up_event,
    'down': get_body_for_down_event
}

def get_event_type(event: Dict[str, Any]) -> str:
    event_type_match = re.match('check.(.*)', event['event'])
    if event_type_match:
        event_type = event_type_match.group(1)
        if event_type in EVENT_TYPE_BODY_MAPPER:
            return event_type
    raise UnexpectedWebhookEventType('Updown', event['event'])
