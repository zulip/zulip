from __future__ import absolute_import

from django.utils.translation import ugettext as _
from django.http import HttpRequest, HttpResponse
from typing import Any, Dict, List

from zerver.lib.actions import check_send_message
from zerver.lib.response import json_success, json_error
from zerver.decorator import REQ, has_request_variables, api_key_only_webhook_view
from zerver.models import UserProfile

import ujson

MESSAGE_TEMPLATE = "Applying for role:\n{}\n**Emails:**\n{}\n\n>**Attachments:**\n{}"

def dict_list_to_string(some_list):
    # type: (List[Any]) -> str
    internal_template = ''
    for item in some_list:
        item_type = item.get('type', '').title()
        item_value = item.get('value')
        item_url = item.get('url')
        if item_type and item_value:
            internal_template += "{}\n{}\n".format(item_type, item_value)
        elif item_type and item_url:
            internal_template += "[{}]({})\n".format(item_type, item_url)
    return internal_template

def message_creator(action, application):
    # type: (str, Dict[str, Any]) -> str
    message = MESSAGE_TEMPLATE.format(
        application['jobs'][0]['name'],
        dict_list_to_string(application['candidate']['email_addresses']),
        dict_list_to_string(application['candidate']['attachments']))
    return message

@api_key_only_webhook_view('Greenhouse')
@has_request_variables
def api_greenhouse_webhook(request, user_profile,
                           payload=REQ(argument_type='body'),
                           stream=REQ(default='greenhouse'), topic=REQ(default=None)):
    # type: (HttpRequest, UserProfile, Dict[str, Any], str, str) -> HttpResponse
    try:
        if payload['action'] == 'update_candidate':
            candidate = payload['payload']['candidate']
        else:
            candidate = payload['payload']['application']['candidate']
        action = payload['action'].replace('_', ' ').title()
        body = "{}\n>{} {}\nID: {}\n{}".format(
            action,
            candidate['first_name'],
            candidate['last_name'],
            str(candidate['id']),
            message_creator(payload['action'],
                            payload['payload']['application']))

        if topic is None:
            topic = "{} - {}".format(action, str(candidate['id']))

    except KeyError as e:
        return json_error(_("Missing key {} in JSON").format(str(e)))

    check_send_message(user_profile, request.client, 'stream', [stream], topic, body)
    return json_success()
