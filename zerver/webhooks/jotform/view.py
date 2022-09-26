# Webhooks for external integrations.
from typing import Any, Dict

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile


@webhook_view("Jotform")
@has_request_variables
def api_jotform_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    payload: Dict[str, Any] = REQ(argument_type="body"),
) -> HttpResponse:
    topic = payload["formTitle"]
    submission_id = payload["submissionID"]
    fields_dict = list(payload["pretty"].split(", "))

    form_response = f"A new submission (ID {submission_id}) was received:\n"
    for field in fields_dict:
        form_response += f"* {field}\n"

    message = form_response.strip()

    check_send_webhook_message(request, user_profile, topic, message)
    return json_success(request)
