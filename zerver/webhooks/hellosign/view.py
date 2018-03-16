from typing import Any, Dict, List

from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _

from zerver.decorator import api_key_only_webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_error, json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

def format_body(signatories: List[Dict[str, Any]], model_payload: Dict[str, Any]) -> str:
    def append_separator(i: int) -> None:
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

def ready_payload(signatories: List[Dict[str, Any]],
                  payload: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    model_payload = {'contract_title': payload['signature_request']['title']}
    for i, signatory in enumerate(signatories):
        model_payload['name_{}'.format(i)] = signatory['signer_name']
        model_payload['status_{}'.format(i)] = signatory['status_code']
    return model_payload

@api_key_only_webhook_view('HelloSign')
@has_request_variables
def api_hellosign_webhook(request: HttpRequest, user_profile: UserProfile,
                          payload: Dict[str, Dict[str, Any]]=REQ(argument_type='body')) -> HttpResponse:
    model_payload = ready_payload(payload['signature_request']['signatures'], payload)
    body = format_body(payload['signature_request']['signatures'], model_payload)
    topic = model_payload['contract_title']
    check_send_webhook_message(request, user_profile, topic, body)
    return json_success()
