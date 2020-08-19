from typing import Any, Dict, List

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

MESSAGE_TEMPLATE = """
{action} {first_name} {last_name} (ID: {candidate_id}), applying for:
* **Role**: {role}
* **Emails**: {emails}
* **Attachments**: {attachments}
""".strip()

def dict_list_to_string(some_list: List[Any]) -> str:
    internal_template = ''
    for item in some_list:
        item_type = item.get('type', '').title()
        item_value = item.get('value')
        item_url = item.get('url')
        if item_type and item_value:
            internal_template += f"{item_value} ({item_type}), "
        elif item_type and item_url:
            internal_template += f"[{item_type}]({item_url}), "

    internal_template = internal_template[:-2]
    return internal_template

@webhook_view('Greenhouse')
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
    application = payload['payload']['application']

    body = MESSAGE_TEMPLATE.format(
        action=action,
        first_name=candidate['first_name'],
        last_name=candidate['last_name'],
        candidate_id=str(candidate['id']),
        role=application['jobs'][0]['name'],
        emails=dict_list_to_string(application['candidate']['email_addresses']),
        attachments=dict_list_to_string(application['candidate']['attachments']),
    )

    topic = "{} - {}".format(action, str(candidate['id']))

    check_send_webhook_message(request, user_profile, topic, body)
    return json_success()
