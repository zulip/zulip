# Webhooks for external integrations.
from __future__ import absolute_import
import re
from datetime import datetime
from typing import Any, Dict
from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _
from zerver.lib.actions import check_send_message
from zerver.lib.response import json_success, json_error
from zerver.lib.request import JsonableError
from zerver.decorator import REQ, has_request_variables, api_key_only_webhook_view
from zerver.models import UserProfile, Client


SUBJECT_TEMPLATE = "{service_url}"


class UnsupportedUpdownEventType(JsonableError):
    pass

def send_message_for_event(event, user_profile, client, stream):
    # type: (Dict[str, Any], UserProfile, Client, str) -> None
    try:
        event_type = get_event_type(event)
        subject = SUBJECT_TEMPLATE.format(service_url=event['check']['url'])
        body = EVENT_TYPE_BODY_MAPPER[event_type](event)
    except KeyError as e:
        return json_error(_("Missing key {} in JSON").format(str(e)))
    check_send_message(user_profile, client, 'stream', [stream], subject, body)

def get_body_for_up_event(event):
    # type: (Dict[str, Any]) -> str
    body = "Service is `up`"
    event_downtime = event['downtime']
    if event_downtime['started_at']:
        body = "{} again".format(body)
        string_date = get_time_string_based_on_duration(event_downtime['duration'])
        if string_date:
            body = "{} after {}".format(body, string_date)
    return "{}.".format(body)

def get_time_string_based_on_duration(duration):
    # type: (int) -> str
    days, reminder = divmod(duration, 86400)
    hours, reminder = divmod(reminder, 3600)
    minutes, seconds = divmod(reminder, 60)

    string_date = ''
    string_date += add_time_part_to_string_date_if_needed(days, 'day')
    string_date += add_time_part_to_string_date_if_needed(hours, 'hour')
    string_date += add_time_part_to_string_date_if_needed(minutes, 'minute')
    string_date += add_time_part_to_string_date_if_needed(seconds, 'second')
    return string_date.rstrip()

def add_time_part_to_string_date_if_needed(value, text_name):
    # type: (int, str) -> str
    if value == 1:
        return "1 {} ".format(text_name)
    if value > 1:
        return "{} {}s ".format(value, text_name)
    return ''

def get_body_for_down_event(event):
    # type: (Dict[str, Any]) -> str
    event_downtime = event['downtime']
    started_at = datetime.strptime(event_downtime['started_at'], "%Y-%m-%dT%H:%M:%SZ")
    return "Service is `down`. It returned \"{}\" error at {}.".format(
        event_downtime['error'],
        started_at.strftime("%d-%m-%Y %H:%M")
    )

@api_key_only_webhook_view('Updown')
@has_request_variables
def api_updown_webhook(request, user_profile, client,
                       payload=REQ(argument_type='body'),
                       stream=REQ(default='updown')):
    # type: (HttpRequest, UserProfile, Client, List[Dict[str, Any]], str) -> HttpResponse
    for event in payload:
        send_message_for_event(event, user_profile, client, stream)
    return json_success()

EVENT_TYPE_BODY_MAPPER = {
    'up': get_body_for_up_event,
    'down': get_body_for_down_event
}

def get_event_type(event):
    # type: (Dict[str, Any]) -> str
    event_type_match = re.match('check.(.*)', event['event'])
    if event_type_match:
        event_type = event_type_match.group(1)
        if event_type in EVENT_TYPE_BODY_MAPPER:
            return event_type
    raise UnsupportedUpdownEventType(event['event'])
