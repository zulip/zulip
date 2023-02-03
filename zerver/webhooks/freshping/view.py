from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventTypeError
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.validator import WildValue, check_int, check_string, to_wild_value
from zerver.lib.webhooks.common import check_send_webhook_message, get_setup_webhook_message
from zerver.models import UserProfile

FRESHPING_TOPIC_TEMPLATE_TEST = "Freshping"
FRESHPING_TOPIC_TEMPLATE = "{check_name}"

FRESHPING_MESSAGE_TEMPLATE_UNREACHABLE = """
{request_url} has just become unreachable.
Error code: {http_status_code}.
""".strip()
FRESHPING_MESSAGE_TEMPLATE_UP = "{request_url} is back up and no longer unreachable."
CHECK_STATE_NAME_TO_EVENT_TYPE = {"Reporting Error": "reporting_error", "Available": "available"}
ALL_EVENT_TYPES = list(CHECK_STATE_NAME_TO_EVENT_TYPE.values())


@webhook_view("Freshping", all_event_types=ALL_EVENT_TYPES)
@has_request_variables
def api_freshping_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    payload: WildValue = REQ(argument_type="body", converter=to_wild_value),
) -> HttpResponse:
    body = get_body_for_http_request(payload)
    subject = get_subject_for_http_request(payload)
    check_state_name = payload["webhook_event_data"]["check_state_name"].tame(check_string)
    if check_state_name not in CHECK_STATE_NAME_TO_EVENT_TYPE:
        raise UnsupportedWebhookEventTypeError(check_state_name)

    check_send_webhook_message(
        request,
        user_profile,
        subject,
        body,
        CHECK_STATE_NAME_TO_EVENT_TYPE[check_state_name],
    )
    return json_success(request)


def get_subject_for_http_request(payload: WildValue) -> str:
    webhook_event_data = payload["webhook_event_data"]
    if webhook_event_data["application_name"].tame(check_string) == "Webhook test":
        subject = FRESHPING_TOPIC_TEMPLATE_TEST
    else:
        subject = FRESHPING_TOPIC_TEMPLATE.format(
            check_name=webhook_event_data["check_name"].tame(check_string)
        )
    return subject


def get_body_for_http_request(payload: WildValue) -> str:
    webhook_event_data = payload["webhook_event_data"]
    if webhook_event_data["check_state_name"].tame(check_string) == "Reporting Error":
        body = FRESHPING_MESSAGE_TEMPLATE_UNREACHABLE.format(
            request_url=webhook_event_data["request_url"].tame(check_string),
            http_status_code=webhook_event_data["http_status_code"].tame(check_int),
        )
    elif webhook_event_data["check_state_name"].tame(check_string) == "Available":
        if webhook_event_data["application_name"].tame(check_string) == "Webhook test":
            body = get_setup_webhook_message("Freshping")
        else:
            body = FRESHPING_MESSAGE_TEMPLATE_UP.format(
                request_url=webhook_event_data["request_url"].tame(check_string)
            )

    return body
