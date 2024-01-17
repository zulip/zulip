# Webhooks for external integrations.

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile


@webhook_view("Jotform")
@typed_endpoint
def api_jotform_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
) -> HttpResponse:
    topic_name = payload["formTitle"].tame(check_string)
    submission_id = payload["submissionID"].tame(check_string)
    fields = payload["pretty"].tame(check_string).split(", ")

    form_response = f"A new submission (ID {submission_id}) was received:\n"
    for field in fields:
        form_response += f"* {field}\n"

    message = form_response.strip()

    check_send_webhook_message(request, user_profile, topic_name, message)
    return json_success(request)
