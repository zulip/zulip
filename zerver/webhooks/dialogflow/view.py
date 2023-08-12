# Webhooks for external integrations.
from django.http import HttpRequest, HttpResponse

from zerver.actions.message_send import check_send_private_message
from zerver.decorator import webhook_view
from zerver.lib.request import RequestNotes
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import WebhookPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_int, check_string
from zerver.models import UserProfile, get_user


@webhook_view("Dialogflow")
@typed_endpoint
def api_dialogflow_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: WebhookPayload[WildValue],
    email: str,
) -> HttpResponse:
    status = payload["status"]["code"].tame(check_int)

    if status == 200:
        result = payload["result"]["fulfillment"]["speech"].tame(check_string)
        if not result:
            alternate_result = payload["alternateResult"]["fulfillment"]["speech"].tame(
                check_string
            )
            if not alternate_result:
                body = "Dialogflow couldn't process your query."
            else:
                body = alternate_result
        else:
            body = result
    else:
        error_status = payload["status"]["errorDetails"].tame(check_string)
        body = f"{status} - {error_status}"

    receiving_user = get_user(email, user_profile.realm)
    client = RequestNotes.get_notes(request).client
    assert client is not None
    check_send_private_message(user_profile, client, receiving_user, body)
    return json_success(request)
