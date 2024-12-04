# Webhooks for external integrations.

from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _

from zerver.decorator import webhook_view
from zerver.lib.exceptions import JsonableError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint_without_parameters
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile


@webhook_view("Jotform")
@typed_endpoint_without_parameters
def api_jotform_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
) -> HttpResponse:
    payload = request.POST
    topic_name = payload.get("formTitle")
    fields = payload.get("pretty", "").split(", ")

    if not topic_name or not fields:
        raise JsonableError(_("Unable to handle Jotform payload"))

    form_response = ""
    for field in fields:
        label, value = field.split(":", 1)
        # TODO: Add fixtures and tests for question-like fields and files
        separator = " " if label.endswith("?") else ": "
        form_response += f"* **{label}**{separator}{value}\n"
    message = form_response.strip()

    check_send_webhook_message(request, user_profile, topic_name, message)
    return json_success(request)
