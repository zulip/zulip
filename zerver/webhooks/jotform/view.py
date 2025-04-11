# Webhooks for external integrations.

import json
from typing import Any
from urllib.parse import unquote

from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _

from zerver.decorator import webhook_view
from zerver.lib.exceptions import JsonableError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint_without_parameters
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile


def format_uploaded_file_links(file_question_value: str, file_url_mappings: dict[str, str]) -> str:
    words = file_question_value.split()
    url_markdown_list = []
    current_file_name_words = []
    for word in words:
        current_file_name_words.append(word)

        # Greedy approach to find the filenames in file_url_mappings.
        potential_file_name = " ".join(current_file_name_words)
        if potential_file_name in file_url_mappings:
            file_url = file_url_mappings.get(potential_file_name)
            url_markdown_list.append(f"[{potential_file_name}]({file_url})")
            current_file_name_words = []

    return ", ".join(url_markdown_list)


def is_non_file_upload_question_with_response(field: str, raw_request: dict[str, Any]) -> bool:
    field_value = raw_request.get(field)
    return bool(
        field
        and field[0] == "q"
        and field_value
        and (
            isinstance(field_value, str)
            or (
                isinstance(field_value, dict)
                # Non-empty Appointment, Date fields
                and "" not in field_value.values()
                # Non-empty Input Table field
                and not (
                    len(field_value) == 2 and "colIds" in field_value and "rowIds" in field_value
                )
            )
            # Multiple choice questions
            or isinstance(field_value, list)
        )
    )


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

    raw_request = json.loads(payload.get("rawRequest", "{}"))
    url_mappings = {}
    if raw_request.get("temp_upload"):
        upload_keys = raw_request.get("temp_upload").keys()
        file_questions_keys = [key.split("_", 1)[-1] for key in upload_keys]
        url_mappings = {
            unquote(url.split("/")[-1]): url
            for key in file_questions_keys
            for url in raw_request.get(key, [])
        }

    # File upload questions are in raw_request["temp_upload"].
    # So, the other questions are the keys in raw_request starting
    # with "q". We exclude any questions with a zero length value,
    # because they are not in the "pretty" data of the payload.
    count_non_file_upload_questions = len(
        [
            field
            for field in raw_request
            if is_non_file_upload_question_with_response(field, raw_request)
        ]
    )

    form_response = ""
    for index, field in enumerate(fields):
        label, value = field.split(":", 1)
        separator = " " if label.endswith("?") else ": "

        # File upload fields are last in the "pretty" payload data.
        if index >= count_non_file_upload_questions:
            value = format_uploaded_file_links(value, url_mappings)
            # We add a new line so that image files are rendered
            # correctly in the message.
            form_response += "\n"
        form_response += f"* **{label}**{separator}{value}\n"

    message = form_response.strip()

    check_send_webhook_message(request, user_profile, topic_name, message)
    return json_success(request)
