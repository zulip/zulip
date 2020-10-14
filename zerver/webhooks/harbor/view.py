# Webhooks for external integrations.
from typing import Any, Dict, Optional

from django.db.models import Q
from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventType
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import Realm, UserProfile

IGNORED_EVENTS = [
    "downloadChart",
    "deleteChart",
    "uploadChart",
    "pullImage",
    "deleteImage",
    "scanningFailed",
]


def guess_zulip_user_from_harbor(harbor_username: str, realm: Realm) -> Optional[UserProfile]:
    try:
        # Try to find a matching user in Zulip
        # We search a user's full name, short name,
        # and beginning of email address
        user = UserProfile.objects.filter(
            Q(full_name__iexact=harbor_username) |
            Q(email__istartswith=harbor_username),
            is_active=True,
            realm=realm).order_by("id")[0]
        return user  # nocoverage
    except IndexError:
        return None


def handle_push_image_event(payload: Dict[str, Any],
                            user_profile: UserProfile,
                            operator_username: str) -> str:
    image_name = payload["event_data"]["repository"]["repo_full_name"]
    image_tag = payload["event_data"]["resources"][0]["tag"]

    return f"{operator_username} pushed image `{image_name}:{image_tag}`"


VULNERABILITY_SEVERITY_NAME_MAP = {
    1: "None",
    2: "Unknown",
    3: "Low",
    4: "Medium",
    5: "High",
}

SCANNING_COMPLETED_TEMPLATE = """
Image scan completed for `{image_name}:{image_tag}`. Vulnerabilities by severity:

{scan_results}
""".strip()


def handle_scanning_completed_event(payload: Dict[str, Any],
                                    user_profile: UserProfile,
                                    operator_username: str) -> str:
    scan_results = ""
    scan_summaries = payload["event_data"]["resources"][0]["scan_overview"]["components"]["summary"]
    summaries_sorted = sorted(
        scan_summaries, key=lambda x: x["severity"], reverse=True)
    for scan_summary in summaries_sorted:
        scan_results += "* {}: **{}**\n".format(
            VULNERABILITY_SEVERITY_NAME_MAP[scan_summary["severity"]], scan_summary["count"])

    return SCANNING_COMPLETED_TEMPLATE.format(
        image_name=payload["event_data"]["repository"]["repo_full_name"],
        image_tag=payload["event_data"]["resources"][0]["tag"],
        scan_results=scan_results,
    )


EVENT_FUNCTION_MAPPER = {
    "pushImage": handle_push_image_event,
    "scanningCompleted": handle_scanning_completed_event,
}


@webhook_view("Harbor")
@has_request_variables
def api_harbor_webhook(request: HttpRequest, user_profile: UserProfile,
                       payload: Dict[str, Any] = REQ(argument_type='body')) -> HttpResponse:

    operator_username = "**{}**".format(payload["operator"])

    if operator_username != "auto":
        operator_profile = guess_zulip_user_from_harbor(
            operator_username, user_profile.realm)

    if operator_profile:
        operator_username = f"@**{operator_profile.full_name}**"  # nocoverage

    event = payload["type"]
    topic = payload["event_data"]["repository"]["repo_full_name"]

    if event in IGNORED_EVENTS:
        return json_success()

    content_func = EVENT_FUNCTION_MAPPER.get(event)

    if content_func is None:
        raise UnsupportedWebhookEventType(event)

    content: str = content_func(payload, user_profile, operator_username)

    check_send_webhook_message(request, user_profile,
                               topic, content,
                               unquote_url_parameters=True)
    return json_success()
