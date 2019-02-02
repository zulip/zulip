from typing import Any, Dict, List

from django.http import HttpRequest, HttpResponse

from zerver.decorator import api_key_only_webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile


IS_AWAITING_SIGNATURE = "is awaiting the signature of {awaiting_recipients}"
WAS_JUST_SIGNED_BY = "was just signed by {signed_recipients}"
BODY = "The `{contract_title}` document {actions}."

def get_message_body(payload: Dict[str, Dict[str, Any]]) -> str:
    contract_title = payload['signature_request']['title']
    recipients = {}  # type: Dict[str, List[str]]
    signatures = payload['signature_request']['signatures']

    for signature in signatures:
        recipients.setdefault(signature['status_code'], [])
        recipients[signature['status_code']].append(signature['signer_name'])

    recipients_text = ""
    if recipients.get('awaiting_signature'):
        recipients_text += IS_AWAITING_SIGNATURE.format(
            awaiting_recipients=get_recipients_text(recipients['awaiting_signature'])
        )

    if recipients.get('signed'):
        text = WAS_JUST_SIGNED_BY.format(
            signed_recipients=get_recipients_text(recipients['signed'])
        )

        if recipients_text:
            recipients_text = "{}, and {}".format(recipients_text, text)
        else:
            recipients_text = text

    return BODY.format(contract_title=contract_title,
                       actions=recipients_text).strip()

def get_recipients_text(recipients: List[str]) -> str:
    recipients_text = ""
    if len(recipients) == 1:
        recipients_text = "{}".format(*recipients)
    else:
        for recipient in recipients[:-1]:
            recipients_text += "{}, ".format(recipient)
        recipients_text += "and {}".format(recipients[-1])

    return recipients_text

@api_key_only_webhook_view('HelloSign')
@has_request_variables
def api_hellosign_webhook(request: HttpRequest, user_profile: UserProfile,
                          payload: Dict[str, Dict[str, Any]]=REQ(argument_type='body')) -> HttpResponse:
    body = get_message_body(payload)
    topic = payload['signature_request']['title']
    check_send_webhook_message(request, user_profile, topic, body)
    return json_success()
