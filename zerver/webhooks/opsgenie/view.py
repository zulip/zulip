from __future__ import absolute_import
from django.utils.translation import ugettext as _
from zerver.lib.actions import check_send_message
from zerver.lib.response import json_success, json_error
from zerver.decorator import REQ, has_request_variables, api_key_only_webhook_view
from zerver.lib.validator import check_dict, check_string
from zerver.models import UserProfile

from django.http import HttpRequest, HttpResponse
from typing import Dict, Any, Iterable, Optional, Text

@api_key_only_webhook_view('OpsGenie')
@has_request_variables
def api_opsgenie_webhook(request, user_profile,
                         payload=REQ(argument_type='body'),
                         stream=REQ(default='opsgenie')):
    # type: (HttpRequest, UserProfile, Dict[str, Any], Text) -> HttpResponse

    # construct the body of the message
    info = {"additional_info": '',
            "alert_type": payload['action'],
            "alert_id": payload['alert']['alertId'],
            "integration_name": payload['integrationName'],
            "tags": ' '.join(['`' + tag + '`' for tag in payload['alert'].get('tags', [])]),
            }
    topic = info['integration_name']
    if 'note' in payload['alert']:
        info['additional_info'] += "Note: *{}*\n".format(payload['alert']['note'])
    if 'recipient' in payload['alert']:
        info['additional_info'] += "Recipient: *{}*\n".format(payload['alert']['recipient'])
    if 'addedTags' in payload['alert']:
        info['additional_info'] += "Added tags: *{}*\n".format(payload['alert']['addedTags'])
    if 'team' in payload['alert']:
        info['additional_info'] += "Added team: *{}*\n".format(payload['alert']['team'])
    if 'owner' in payload['alert']:
        info['additional_info'] += "Assigned owner: *{}*\n".format(payload['alert']['owner'])
    if 'escalationName' in payload:
        info['additional_info'] += "Escalation: *{}*\n".format(payload['escalationName'])
    if 'removedTags' in payload['alert']:
        info['additional_info'] += "Removed tags: *{}*\n".format(payload['alert']['removedTags'])
    if 'message' in payload['alert']:
        info['additional_info'] += "Message: *{}*\n".format(payload['alert']['message'])
    body = ''
    body_template = "**OpsGenie: [Alert for {integration_name}.](https://app.opsgenie.com/alert/V2#/show/{alert_id})**\n" \
                    "Type: *{alert_type}*\n" \
                    "{additional_info}" \
                    "{tags}"
    body += body_template.format(**info)
    # send the message
    check_send_message(user_profile, request.client, 'stream', [stream], topic, body)

    return json_success()
