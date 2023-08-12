from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _

from zerver.actions.message_send import send_rate_limited_pm_notification_to_bot_owner
from zerver.decorator import webhook_view
from zerver.lib.exceptions import JsonableError
from zerver.lib.response import json_success
from zerver.lib.send_email import FromAddress
from zerver.lib.typed_endpoint import WebhookPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

MISCONFIGURED_PAYLOAD_ERROR_MESSAGE = """
Hi there! Your bot {bot_name} just received a UptimeRobot payload that is missing
some data that Zulip requires. This usually indicates a configuration issue
in your UptimeRobot webhook settings. Please make sure that you set the required parameters
when configuring the UptimeRobot webhook. Contact {support_email} if you
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
@typed_endpoint
def api_uptimerobot_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: WebhookPayload[WildValue],
) -> HttpResponse:
    event_type = payload["alert_type_friendly_name"].tame(check_string)
    if event_type == "Up":
        event = "up"
    elif event_type == "Down":
        event = "down"

    try:
        body = get_body_for_http_request(payload, event_type)
        topic = get_topic_for_http_request(payload)
    except ValidationError:
        message = MISCONFIGURED_PAYLOAD_ERROR_MESSAGE.format(
            bot_name=user_profile.full_name,
            support_email=FromAddress.SUPPORT,
        ).strip()
        send_rate_limited_pm_notification_to_bot_owner(user_profile, user_profile.realm, message)

        raise JsonableError(_("Invalid payload"))

    check_send_webhook_message(request, user_profile, topic, body, event)
    return json_success(request)


def get_topic_for_http_request(payload: WildValue) -> str:
    return UPTIMEROBOT_TOPIC_TEMPLATE.format(
        monitor_friendly_name=payload["monitor_friendly_name"].tame(check_string)
    )


def get_body_for_http_request(payload: WildValue, event_type: str) -> str:
    if event_type == "Up":
        monitor_friendly_name = payload["monitor_friendly_name"].tame(check_string)
        monitor_url = payload["monitor_url"].tame(check_string)
        alert_details = payload["alert_details"].tame(check_string)
        alert_friendly_duration = payload["alert_friendly_duration"].tame(check_string)
        body = UPTIMEROBOT_MESSAGE_UP_TEMPLATE.format(
            monitor_friendly_name=monitor_friendly_name,
            monitor_url=monitor_url,
            alert_details=alert_details,
            alert_friendly_duration=alert_friendly_duration,
        )
    elif event_type == "Down":
        monitor_friendly_name = payload["monitor_friendly_name"].tame(check_string)
        monitor_url = payload["monitor_url"].tame(check_string)
        alert_details = payload["alert_details"].tame(check_string)
        body = UPTIMEROBOT_MESSAGE_DOWN_TEMPLATE.format(
            monitor_friendly_name=monitor_friendly_name,
            monitor_url=monitor_url,
            alert_details=alert_details,
        )

    return body
