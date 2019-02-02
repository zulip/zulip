from typing import Any, Dict, List

from django.http import HttpRequest, HttpResponse

from zerver.decorator import api_key_only_webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

MESSAGE_TEMPLATE = "Applying for role:\n{}\n**Emails:**\n{}\n\n>**Attachments:**\n{}"

def dict_list_to_string(some_list: List[Any]) -> str:
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

def message_creator(action: str, application: Dict[str, Any]) -> str:
    message = MESSAGE_TEMPLATE.format(
        application['jobs'][0]['name'],
        dict_list_to_string(application['candidate']['email_addresses']),
        dict_list_to_string(application['candidate']['attachments']))
    return message

@api_key_only_webhook_view('Greenhouse')
@has_request_variables
def api_greenhouse_webhook(request: HttpRequest, user_profile: UserProfile,
                           payload: Dict[str, Any]=REQ(argument_type='body')) -> HttpResponse:
    if payload['action'] == 'ping':
        return json_success()

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

    topic = "{} - {}".format(action, str(candidate['id']))

    check_send_webhook_message(request, user_profile, topic, body)
    return json_success()
