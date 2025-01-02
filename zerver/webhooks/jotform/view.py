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
    pretty_field = payload.get("pretty", "")

    if not topic_name or not pretty_field:
        raise JsonableError(_("Unable to handle Jotform payload"))

    # List of known values that can appear in the `pretty` field (can be dynamic based on your case)
    known_values = ["Student's Name", "Type of Tutoring", "Subject for Tutoring", "Grade"]
    form_response = []

    # Split the pretty field by commas and loop through to process each key-value pair
    for field in pretty_field.split(", "):
        label, value = field.split(":", 1)
        # Check if the label matches any of the known values
        if any(known_value in label for known_value in known_values):
            form_response.append(f"* **{label}**: {value.strip()}")

    message = "\n".join(form_response)


    check_send_webhook_message(request, user_profile, topic_name, message)
    return json_success(request)