# Webhooks for external integrations.
from typing import Dict, List

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import WebhookPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_int, check_none_or, check_string, check_union
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

subject_types: Dict[str, List[List[str]]] = {
    "app": [  # Object type name
        ["name"],  # Title
        ["html_url"],  # Automatically put into title
        ["language"],  # Other properties.
        ["framework"],
    ],
    "base": [
        ["title"],
        ["html_url"],
        ["#summary"],
        ["subject"],
    ],
    "comment": [
        [""],
        ["subject"],
    ],
    "errorgroup": [
        ["E#{}", "number"],
        ["html_url"],
        ["last_occurrence:error"],
    ],
    "error": [
        [""],
        ['">**Most recent Occurrence**'],
        ["in {}", "extra/pathname"],
        ["!message"],
    ],
}


def get_value(_obj: WildValue, key: str) -> str:
    for _key in key.lstrip("!").split("/"):
        if _key in _obj:
            _obj = _obj[_key]
        else:
            return ""
    return str(_obj.tame(check_union([check_string, check_int])))


def format_object(
    obj: WildValue,
    subject_type: str,
    message: str,
) -> str:
    if subject_type not in subject_types:
        return message
    keys: List[List[str]] = subject_types[subject_type][1:]
    title = subject_types[subject_type][0]
    if title[0] != "":
        title_str = ""
        if len(title) > 1:
            title_str = title[0].format(get_value(obj, title[1]))
        else:
            title_str = obj[title[0]].tame(check_string)

        url = obj["html_url"].tame(check_none_or(check_string))
        if url is not None:
            if "opbeat.com" not in url:
                url = "https://opbeat.com/" + url.lstrip("/")
            message += f"\n**[{title_str}]({url})**"
        else:
            message += f"\n**{title_str}**"
    for key_list in keys:
        if len(key_list) > 1:
            value = key_list[0].format(get_value(obj, key_list[1]))
            message += f"\n>{value}"
        else:
            key = key_list[0]
            key_raw = key.lstrip("!").lstrip("#").lstrip('"')
            if key_raw != "html_url" and key_raw != "subject" and ":" not in key_raw:
                value = get_value(obj, key_raw)
                if key.startswith("!"):
                    message += f"\n>{value}"
                elif key.startswith("#"):
                    message += f"\n{value}"
                elif key.startswith('"'):
                    message += f"\n{key_raw}"
                else:
                    message += f"\n>{key}: {value}"
            if key == "subject":
                message = format_object(
                    obj["subject"], obj["subject_type"].tame(check_string), message + "\n"
                )
            if ":" in key:
                value, value_type = key.split(":")
                message = format_object(obj[value], value_type, message + "\n")
    return message


@webhook_view("Opbeat")
@typed_endpoint
def api_opbeat_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: WebhookPayload[WildValue],
) -> HttpResponse:
    """
    This uses the subject name from opbeat to make the topic,
    and the summary from Opbeat as the message body, with
    details about the object mentioned.
    """

    topic = payload["title"].tame(check_string)

    message = format_object(payload, "base", "")

    check_send_webhook_message(request, user_profile, topic, message)
    return json_success(request)
