from typing import Any, Dict, Iterable

from django.http import HttpRequest, HttpResponse

from zerver.decorator import api_key_only_webhook_view
from zerver.lib.webhooks.common import check_send_webhook_message, \
    validate_extract_webhook_http_header, UnexpectedWebhookEventType
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.models import UserProfile

EVENTS = ['deploy_failed', 'deploy_locked', 'deploy_unlocked', 'deploy_building', 'deploy_created']

@api_key_only_webhook_view('Netlify')
@has_request_variables
def api_netlify_webhook(
        request: HttpRequest, user_profile: UserProfile,
        payload: Dict[str, Iterable[Dict[str, Any]]]=REQ(argument_type='body')
) -> HttpResponse:

    message_template = get_template(request, payload)

    body = message_template.format(build_name=payload['name'],
                                   build_url=payload['url'],
                                   branch_name=payload['branch'],
                                   state=payload['state'])

    topic = "{topic}".format(topic=payload['branch'])

    check_send_webhook_message(request, user_profile, topic, body)

    return json_success()

def get_template(request: HttpRequest, payload: Dict[str, Any]) -> str:

    message_template = u'The build [{build_name}]({build_url}) on branch {branch_name} '
    event = validate_extract_webhook_http_header(request, 'X_NETLIFY_EVENT', 'Netlify')

    if event == 'deploy_failed':
        return message_template + payload['error_message']
    elif event == 'deploy_locked':
        return message_template + 'is now locked.'
    elif event == 'deploy_unlocked':
        return message_template + 'is now unlocked.'
    elif event in EVENTS:
        return message_template + 'is now {state}.'.format(state=payload['state'])
    else:
        raise UnexpectedWebhookEventType('Netlify', event)
