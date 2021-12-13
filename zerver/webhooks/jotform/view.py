# Webhooks for external integrations.
from typing import Dict

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.validator import check_dict, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile


@webhook_view("Jotform")
@has_request_variables
def api_jotform_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    payload: Dict[str, object] = REQ(argument_type="body", json_validator=check_dict()),
) -> HttpResponse:
    topic = check_string("formTitle", payload.get("formTitle"))
    submission_id = check_string("submissionID", payload.get("submissionID"))
    fields_dict = check_string("pretty", payload.get("pretty")).split(", ")

    form_response = f"A new submission (ID {submission_id}) was received:\n"
    for field in fields_dict:
        form_response += f"* {field}\n"

    message = form_response.strip()

    check_send_webhook_message(request, user_profile, topic, message)
    return json_success()
