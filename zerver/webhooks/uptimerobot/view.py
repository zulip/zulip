from typing import Any, Dict

from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _

from zerver.decorator import webhook_view
from zerver.lib.actions import send_rate_limited_pm_notification_to_bot_owner
from zerver.lib.exceptions import JsonableError
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.send_email import FromAddress
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

MISCONFIGURED_PAYLOAD_ERROR_MESSAGE = """
Hi there! Your bot {bot_name} just received a Uptime Robot payload that is missing
some data that Zulip requires. This usually indicates a configuration issue
in your Uptime Robot webhook settings. Please make sure that you set the required parameters
when configuring the Uptime Robot webhook. Contact {support_email} if you
need further help!
"""

UPTIMEROBOT_TOPIC_TEMPLATE = "{monitor_friendly_name}"
UPTIMEROBOT_MESSAGE_UP_TEMPLATE = """
{monitor_friendly_name} ({monitor_url}) is back UP ({alert_details}).
It was down for {alert_friendly_duration}.
""".strip()
UPTIMEROBOT_MESSAGE_DOWN_TEMPLATE = (
    "{monitor_friendly_name} ({monitor_url}) is DOWN ({alert_details})."
)
ALL_EVENT_TYPES = ["up", "down"]


@webhook_view("UptimeRobot", all_event_types=ALL_EVENT_TYPES)
@has_request_variables
def api_uptimerobot_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    payload: Dict[str, Any] = REQ(argument_type="body"),
) -> HttpResponse:
    if payload["alert_type_friendly_name"] == "Up":
        event = "up"
    elif payload["alert_type_friendly_name"] == "Down":
        event = "down"

    try:
        body = get_body_for_http_request(payload)
        subject = get_subject_for_http_request(payload)
    except KeyError:
        message = MISCONFIGURED_PAYLOAD_ERROR_MESSAGE.format(
            bot_name=user_profile.full_name,
            support_email=FromAddress.SUPPORT,
        ).strip()
        send_rate_limited_pm_notification_to_bot_owner(user_profile, user_profile.realm, message)

        raise JsonableError(_("Invalid payload"))

    check_send_webhook_message(request, user_profile, subject, body, event)
    return json_success()


def get_subject_for_http_request(payload: Dict[str, Any]) -> str:
    return UPTIMEROBOT_TOPIC_TEMPLATE.format(monitor_friendly_name=payload["monitor_friendly_name"])


def get_body_for_http_request(payload: Dict[str, Any]) -> str:
    if payload["alert_type_friendly_name"] == "Up":
        body = UPTIMEROBOT_MESSAGE_UP_TEMPLATE.format(**payload)
    elif payload["alert_type_friendly_name"] == "Down":
        body = UPTIMEROBOT_MESSAGE_DOWN_TEMPLATE.format(**payload)

    return body
