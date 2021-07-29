from typing import Any, Dict

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message, get_setup_webhook_message
from zerver.models import UserProfile

FRESHPING_TOPIC_TEMPLATE_TEST = "Freshping"
FRESHPING_TOPIC_TEMPLATE = "{check_name}"

FRESHPING_MESSAGE_TEMPLATE_UNREACHABLE = """
{request_url} has just become unreachable.
Error code: {http_status_code}.
""".strip()
FRESHPING_MESSAGE_TEMPLATE_UP = "{request_url} is back up and no longer unreachable."
ALL_EVENT_TYPES = ["Reporting Error", "Available"]


@webhook_view("Freshping", all_event_types=ALL_EVENT_TYPES)
@has_request_variables
def api_freshping_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    payload: Dict[str, Any] = REQ(argument_type="body"),
) -> HttpResponse:

    body = get_body_for_http_request(payload)
    subject = get_subject_for_http_request(payload)

    check_send_webhook_message(
        request, user_profile, subject, body, payload["webhook_event_data"]["check_state_name"]
    )
    return json_success()


def get_subject_for_http_request(payload: Dict[str, Any]) -> str:
    webhook_event_data = payload["webhook_event_data"]
    if webhook_event_data["application_name"] == "Webhook test":
        subject = FRESHPING_TOPIC_TEMPLATE_TEST
    else:
        subject = FRESHPING_TOPIC_TEMPLATE.format(check_name=webhook_event_data["check_name"])

    return subject


def get_body_for_http_request(payload: Dict[str, Any]) -> str:
    webhook_event_data = payload["webhook_event_data"]
    if webhook_event_data["check_state_name"] == "Reporting Error":
        body = FRESHPING_MESSAGE_TEMPLATE_UNREACHABLE.format(**webhook_event_data)
    elif webhook_event_data["check_state_name"] == "Available":
        if webhook_event_data["application_name"] == "Webhook test":
            body = get_setup_webhook_message("Freshping")
        else:
            body = FRESHPING_MESSAGE_TEMPLATE_UP.format(**webhook_event_data)

    return body
