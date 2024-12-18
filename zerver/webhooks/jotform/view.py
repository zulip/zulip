# Webhooks for external integrations.

import json

from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _

from zerver.decorator import webhook_view
from zerver.lib.exceptions import JsonableError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint_without_parameters
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile


def replace_with_url_markdowns(file_question_value: str, file_url_mappings: dict[str, str]) -> str:
    words = file_question_value.split()
    url_markdown_list = []
    current_file_name_words = []
    for word in words:
        current_file_name_words.append(word)
        if "." in word:
            # The word having extension will be the last word in a file name.
            current_file_name = " ".join(current_file_name_words)
            file_url = file_url_mappings.get(current_file_name)
            url_markdown_list.append(f"[{current_file_name}]({file_url})")
            current_file_name_words = []

    return ", ".join(url_markdown_list)


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
            url.split("/")[-1].replace("%20", " "): url
            for key in file_questions_keys
            for url in raw_request.get(key, [])
        }

    # Jotform sends all the file questions in raw_request["temp_ipload"]
    # So, the fields in raw_request starting with q are non files
    num_non_file_questions = len([question for question in raw_request if question[0] == "q"])
    form_response = ""
    for index, field in enumerate(fields):
        label, value = field.split(":", 1)
        separator = " " if label.endswith("?") else ": "

        # Jotforms sends file fields at last in the "pretty" field
        if index >= num_non_file_questions:
            value = replace_with_url_markdowns(value, url_mappings)
            # To render image files correctly
            form_response += "\n"
        form_response += f"* **{label}**{separator}{value}\n"

    message = form_response.strip()

    check_send_webhook_message(request, user_profile, topic_name, message)
    return json_success(request)
