# Webhooks for external integrations.

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.validator import WildValue, check_string, to_wild_value
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile


@webhook_view("Jotform")
@has_request_variables
def api_jotform_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    payload: WildValue = REQ(argument_type="body", converter=to_wild_value),
) -> HttpResponse:
    topic = payload["formTitle"].tame(check_string)
    submission_id = payload["submissionID"].tame(check_string)
    fields_dict = list(payload["pretty"].tame(check_string).split(", "))

    form_response = f"A new submission (ID {submission_id}) was received:\n"
    for field in fields_dict:
        form_response += f"* {field}\n"

    message = form_response.strip()

    check_send_webhook_message(request, user_profile, topic, message)
    return json_success(request)
