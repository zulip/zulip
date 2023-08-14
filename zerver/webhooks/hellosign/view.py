from typing import Dict, List

from django.http import HttpRequest, HttpResponse
from pydantic import Json
from typing_extensions import Annotated

from zerver.decorator import webhook_view
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import ApiParamConfig, typed_endpoint
from zerver.lib.validator import WildValue, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

IS_AWAITING_SIGNATURE = "is awaiting the signature of {awaiting_recipients}"
WAS_JUST_SIGNED_BY = "was just signed by {signed_recipients}"
BODY = "The `{contract_title}` document {actions}."


def get_message_body(payload: WildValue) -> str:
    contract_title = payload["signature_request"]["title"].tame(check_string)
    recipients: Dict[str, List[str]] = {}
    signatures = payload["signature_request"]["signatures"]

    for signature in signatures:
        status_code = signature["status_code"].tame(check_string)
        recipients.setdefault(status_code, [])
        recipients[status_code].append(signature["signer_name"].tame(check_string))

    recipients_text = ""
    if recipients.get("awaiting_signature"):
        recipients_text += IS_AWAITING_SIGNATURE.format(
            awaiting_recipients=get_recipients_text(recipients["awaiting_signature"]),
        )

    if recipients.get("signed"):
        text = WAS_JUST_SIGNED_BY.format(
            signed_recipients=get_recipients_text(recipients["signed"]),
        )

        if recipients_text:
            recipients_text = f"{recipients_text}, and {text}"
        else:
            recipients_text = text

    return BODY.format(contract_title=contract_title, actions=recipients_text).strip()


def get_recipients_text(recipients: List[str]) -> str:
    recipients_text = ""
    if len(recipients) == 1:
        recipients_text = "{}".format(*recipients)
    else:
        for recipient in recipients[:-1]:
            recipients_text += f"{recipient}, "
        recipients_text += f"and {recipients[-1]}"

    return recipients_text


@webhook_view("HelloSign")
@typed_endpoint
def api_hellosign_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: Annotated[Json[WildValue], ApiParamConfig("json")],
) -> HttpResponse:
    if "signature_request" in payload:
        body = get_message_body(payload)
        topic = payload["signature_request"]["title"].tame(check_string)
        check_send_webhook_message(request, user_profile, topic, body)

    return json_success(request, data={"msg": "Hello API Event Received"})
