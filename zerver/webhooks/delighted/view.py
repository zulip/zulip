from typing import Any, Dict, Optional

from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _

from zerver.decorator import api_key_only_webhook_view
from zerver.lib.actions import check_send_stream_message
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_error, json_success
from zerver.models import UserProfile

def body_template(score: int) -> str:
    if score >= 7:
        return 'Kudos! You have a new promoter.\n>Score of {score}/10 from {email}\n>{comment}'
    else:
        return 'Great! You have new feedback.\n>Score of {score}/10 from {email}\n>{comment}'

@api_key_only_webhook_view("Delighted")
@has_request_variables
def api_delighted_webhook(request, user_profile,
                          payload=REQ(argument_type='body'),
                          stream=REQ(default='delighted'),
                          topic=REQ(default='Survey Response')):
    # type: (HttpRequest, UserProfile, Dict[str, Dict[str, Any]], str, str) -> HttpResponse
    person = payload['event_data']['person']
    selected_payload = {'email': person['email']}
    selected_payload['score'] = payload['event_data']['score']
    selected_payload['comment'] = payload['event_data']['comment']

    BODY_TEMPLATE = body_template(selected_payload['score'])
    body = BODY_TEMPLATE.format(**selected_payload)

    check_send_stream_message(user_profile, request.client, stream,
                              topic, body)
    return json_success()
