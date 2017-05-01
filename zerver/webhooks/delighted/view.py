from __future__ import absolute_import
from django.utils.translation import ugettext as _
from zerver.lib.actions import check_send_message
from zerver.lib.response import json_success, json_error
from zerver.decorator import REQ, has_request_variables, api_key_only_webhook_view

from zerver.models import UserProfile

from django.http import HttpRequest, HttpResponse
from six import text_type
from typing import Dict, Any, Optional

def body_template(score):
    # type: (int) -> str
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
    # type: (HttpRequest, UserProfile, Dict[str, Dict[str, Any]], text_type, text_type) -> HttpResponse
    try:
        person = payload['event_data']['person']
        selected_payload = {'email': person['email']}
        selected_payload['score'] = payload['event_data']['score']
        selected_payload['comment'] = payload['event_data']['comment']
    except KeyError as e:
        return json_error(_("Missing key {} in JSON").format(str(e)))

    BODY_TEMPLATE = body_template(selected_payload['score'])
    body = BODY_TEMPLATE.format(**selected_payload)

    check_send_message(user_profile, request.client, 'stream', [stream],
                       topic, body)
    return json_success()
