from typing import Any, Dict

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

ERRBIT_TOPIC_TEMPLATE = '{project_name}'
ERRBIT_MESSAGE_TEMPLATE = '[{error_class}]({error_url}): "{error_message}" occurred.'

@webhook_view('Errbit')
@has_request_variables
def api_errbit_webhook(request: HttpRequest, user_profile: UserProfile,
                       payload: Dict[str, Any]=REQ(argument_type='body')) -> HttpResponse:
    subject = get_subject(payload)
    body = get_body(payload)
    check_send_webhook_message(request, user_profile, subject, body)
    return json_success()

def get_subject(payload: Dict[str, Any]) -> str:
    project = payload['problem']['app_name'] + ' / ' + payload['problem']['environment']
    return ERRBIT_TOPIC_TEMPLATE.format(project_name=project)

def get_body(payload: Dict[str, Any]) -> str:
    data = {
        'error_url': payload['problem']['url'],
        'error_class': payload['problem']['error_class'],
        'error_message': payload['problem']['message'],
    }
    return ERRBIT_MESSAGE_TEMPLATE.format(**data)
