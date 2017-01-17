from __future__ import absolute_import
from typing import Any, Dict, Optional

from six import text_type

from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _

from zerver.decorator import (REQ, api_key_only_webhook_view,
                              has_request_variables)
from zerver.lib.actions import check_send_message
from zerver.lib.response import json_error, json_success
from zerver.models import Client, UserProfile


def body_template(score):
    # type: (int) -> str
    if score >= 7:
        return 'Kudos! You have a new promoter.\n>Score of {score}/10 from {email}\n>{comment}'
    else:
        return 'Great! You have new feedback.\n>Score of {score}/10 from {email}\n>{comment}'

@api_key_only_webhook_view("Delighted")
@has_request_variables
def api_delighted_webhook(request, user_profile, client,
                          payload=REQ(argument_type='body'),
                          stream=REQ(default='delighted'),
                          topic=REQ(default='Survey Response')):
    # type: (HttpRequest, UserProfile, Client, Dict[str, Dict[str, Any]], text_type, text_type) -> HttpResponse
    try:
        person = payload['event_data']['person']
        selected_payload = {'email': person['email']}
        selected_payload['score'] = payload['event_data']['score']
        selected_payload['comment'] = payload['event_data']['comment']
    except KeyError as e:
        return json_error(_("Missing key {} in JSON").format(str(e)))

    BODY_TEMPLATE = body_template(selected_payload['score'])
    body = BODY_TEMPLATE.format(**selected_payload)

    check_send_message(user_profile, client, 'stream', [stream],
                       topic, body)
    return json_success()
