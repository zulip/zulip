from typing import Any, Dict, Iterable
from django.http import HttpRequest, HttpResponse
from zerver.decorator import api_key_only_webhook_view
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.models import UserProfile

@api_key_only_webhook_view('Grafana')
@has_request_variables
def api_grafana_webhook(
        request: HttpRequest, user_profile: UserProfile,
        payload: Dict[str, Iterable[Dict[str, Any]]]=REQ(argument_type='body')
) -> HttpResponse:

    # construct body
    body_template = '\n{ruleName}\n{message}\nFor more information, visit the [dashboard]({ruleUrl})'
    body = body_template.format(**payload)

    # construct topic
    topic_template = '[{state}]{title}'
    topic = topic_template.format(**payload)

    # send the message
    check_send_webhook_message(request, user_profile, topic, body)

    return json_success()
