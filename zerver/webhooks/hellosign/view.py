from __future__ import absolute_import
from django.utils.translation import ugettext as _
from zerver.lib.actions import check_send_message
from zerver.lib.response import json_success, json_error
from zerver.decorator import REQ, has_request_variables, api_key_only_webhook_view

from zerver.models import UserProfile

from django.http import HttpRequest, HttpResponse
from six import text_type
from typing import Any, Dict, List

def format_body(signatories, model_payload):
    # type: (List[Dict[str, Any]], Dict[str, Any]) -> str
    def append_separator(i):
        # type: (int) -> None
        if i + 1 == len(signatories):
            result.append('.')
        elif i + 2 == len(signatories):
            result.append(' and')
        elif i + 3 != len(signatories):
            result.append(',')

    result = ["The {}".format(model_payload['contract_title'])]  # type: Any
    for i, signatory in enumerate(signatories):
        name = model_payload['name_{}'.format(i)]
        if signatory['status_code'] == 'awaiting_signature':
            result.append(" is awaiting the signature of {}".format(name))
        elif signatory['status_code'] in ['signed', 'declined']:
            status = model_payload['status_{}'.format(i)]
            result.append(" was just {} by {}".format(status, name))

        append_separator(i)
    return ''.join(result)

def ready_payload(signatories, payload):
    # type: (List[Dict[str, Any]], Dict[str, Dict[str, Any]]) -> Dict[str, Any]
    model_payload = {'contract_title': payload['signature_request']['title']}
    for i, signatory in enumerate(signatories):
        model_payload['name_{}'.format(i)] = signatory['signer_name']
        model_payload['status_{}'.format(i)] = signatory['status_code']
    return model_payload

@api_key_only_webhook_view('HelloSign')
@has_request_variables
def api_hellosign_webhook(request, user_profile,
                          payload=REQ(argument_type='body'),
                          stream=REQ(default='hellosign'),
                          topic=REQ(default=None)):
    # type: (HttpRequest, UserProfile, Dict[str, Dict[str, Any]], text_type, text_type) -> HttpResponse
    try:
        model_payload = ready_payload(payload['signature_request']['signatures'],
                                      payload)
    except KeyError as e:
        return json_error(_("Missing key {} in JSON").format(str(e)))

    body = format_body(payload['signature_request']['signatures'], model_payload)
    topic = topic or model_payload['contract_title']
    check_send_message(user_profile, request.client, 'stream', [stream],
                       topic, body)
    return json_success()
