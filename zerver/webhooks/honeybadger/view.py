from pathlib import PurePosixPath
from urllib.parse import urlsplit

from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import JsonableError, UnsupportedWebhookEventTypeError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_int, check_string, check_url
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

ERROR_EVENT_TYPES = ["occurred", "rate_exceeded", "resolved", "unresolved", "assigned", "commented"]
ALL_EVENT_TYPES = [
    *ERROR_EVENT_TYPES,
    "deployed",
    "volume_spike",
    "down",
    "up",
    "cert_will_expire",
    "check_in_missing",
    "check_in_reporting",
    "alarm_alert",
    "alarm_ok",
]


def get_honeybadger_message(payload: WildValue) -> tuple[str, str, str]:
    event = payload["event"].tame(check_string)
    url: str | None = None

    if event in ERROR_EVENT_TYPES:
        error_id = payload["fault"]["id"].tame(check_int)
        topic = f"Error #{error_id}"
        if "url" in payload["fault"]:
            url = payload["fault"]["url"].tame(check_url)
        label = "error"
    elif event in ["deployed", "volume_spike"]:
        project_id = payload["project"]["id"].tame(check_int)
        topic = f"Project #{project_id}"
        if event == "deployed":
            url = payload["deploy"]["url"].tame(check_url)
            label = "deployment"
        else:
            url = payload["project"]["url"].tame(check_url)
            label = "project"
    elif event in ["down", "up", "cert_will_expire"]:
        site_id = payload["site"]["id"].tame(check_string)
        topic = f"Uptime {site_id}"
        if "details_url" in payload["site"]:
            url = payload["site"]["details_url"].tame(check_url)
        label = "uptime monitor"
    elif event in ["check_in_missing", "check_in_reporting"]:
        check_in_id = payload["check_in"]["id"].tame(check_string)
        topic = f"Check-in {check_in_id}"
        if "details_url" in payload["check_in"]:
            url = payload["check_in"]["details_url"].tame(check_url)
        label = "check-ins"
    elif event in ["alarm_alert", "alarm_ok"]:
        url = payload["alarm"]["url"].tame(check_url)
        alarm_id = PurePosixPath(urlsplit(url).path).name
        topic = f"Alarm {alarm_id}"
        label = "alarm"
    else:
        raise UnsupportedWebhookEventTypeError(event)

    message = payload["message"].tame(check_string)
    body = message
    if url is not None:
        body += f"\n\n[View {label}]({url})"
    return event, topic, body


@webhook_view("Honeybadger", all_event_types=ALL_EVENT_TYPES)
@typed_endpoint
def api_honeybadger_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
) -> HttpResponse:
    try:
        event, topic, body = get_honeybadger_message(payload)
    except ValidationError as error:
        raise JsonableError(error.message) from error

    check_send_webhook_message(request, user_profile, topic, body, event)
    return json_success(request)
