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
    """
    File upload questions are in raw_request["temp_upload"].
    So, the other questions are the keys in raw_request starting
    with "q". We exclude any questions with a zero length value,
    because they are not in the "pretty" data of the payload.
    """
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


def format_value(value: str | list[str] | dict[str, str]) -> str:
    if isinstance(value, str):
        return value
    elif isinstance(value, list):
        return " ".join(value)

    return " ".join(value.values())


def get_pretty_fields(pretty: str, values: list[str]) -> list[tuple[str, str]]:
    """
    The format of "pretty" data in the payload is "key1:value1, key2:value2, ..."
    The parameter "values" contains all substrings that appear as values
    in the pretty data. Extracts each key-value pair by locating the position
    of each value in the string and separating the corresponding key and value,
    by tracking the starting position of the next key-value pair.
    This approach is necessary because keys and values may contain colons
    or commas, making it unreliable to simply split the string using ', '.

    Returns a list of (key, value) pairs to preserve order and allow duplicate keys.
    """

    pretty_fields = []
    pair_starting_index = 0

    for value in values:
        value_length = len(value)
        possible_match_index = pretty.find(value + ":", pair_starting_index)

        # If the current pair starts with a key that is equal to the value
        if possible_match_index == pair_starting_index:
            key = value
            val = value

            # 3 characters for colon, comma and space.
            pair_starting_index += 2 * value_length + 3
        else:
            value_occurence_index = pretty.find(value, pair_starting_index)
            value_ending_index = value_occurence_index + value_length

            # -1 for colon, separating key and value
            key = pretty[pair_starting_index : value_occurence_index - 1]
            val = pretty[value_occurence_index:value_ending_index]

            # 2 characters for comma and space, which separate the fields
            pair_starting_index = value_ending_index + 2

        pretty_fields.append((key, val))

    return pretty_fields


@webhook_view("Jotform")
@typed_endpoint_without_parameters
def api_jotform_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
) -> HttpResponse:
    payload = request.POST
    topic_name = payload.get("formTitle")

    raw_request = json.loads(payload.get("rawRequest", "{}"))
    non_file_upload_values_in_pretty_data = [
        format_value(value)
        for field, value in raw_request.items()
        if is_non_file_upload_question_with_response(field, raw_request)
    ]

    url_mappings = {}
    file_values_in_pretty_data = []
    if raw_request.get("temp_upload"):
        upload_keys = raw_request.get("temp_upload").keys()
        file_questions_keys = [key.split("_", 1)[-1] for key in upload_keys]
        file_values_in_pretty_data = [
            " ".join(unquote(url.split("/")[-1]) for url in raw_request.get(key, []))
            for key in file_questions_keys
        ]
        url_mappings = {
            unquote(url.split("/")[-1]): url
            for key in file_questions_keys
            for url in raw_request.get(key, [])
        }

    # Non file values come earlier than file values in the "pretty" data of the payload.
    pretty_values = non_file_upload_values_in_pretty_data + list(file_values_in_pretty_data)
    pretty_fields = get_pretty_fields(payload.get("pretty", ""), pretty_values)

    if not topic_name or not pretty_fields:
        raise JsonableError(_("Unable to handle Jotform payload"))

    form_response = ""
    for index, (label, value) in enumerate(pretty_fields):
        separator = " " if label.endswith("?") else ": "

        # File upload fields are last in the "pretty" payload data.
        if index >= len(non_file_upload_values_in_pretty_data):
            value = format_uploaded_file_links(value, url_mappings)
            # We add a new line so that image files are rendered
            # correctly in the message.
            form_response += "\n"
        form_response += f"* **{label}**{separator}{value}\n"

    message = form_response.strip()

    check_send_webhook_message(request, user_profile, topic_name, message)
    return json_success(request)
