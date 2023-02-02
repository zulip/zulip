# Webhooks for external integrations.
from typing import Optional

from django.db.models import Q
from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventTypeError
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.validator import WildValue, check_int, check_string, to_wild_value
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import Realm, UserProfile

IGNORED_EVENTS = [
    "DOWNLOAD_CHART",
    "DELETE_CHART",
    "UPLOAD_CHART",
    "PULL_ARTIFACT",
    "DELETE_ARTIFACT",
    "SCANNING_FAILED",
]


def guess_zulip_user_from_harbor(harbor_username: str, realm: Realm) -> Optional[UserProfile]:
    try:
        # Try to find a matching user in Zulip
        # We search a user's full name, short name,
        # and beginning of email address
        user = UserProfile.objects.filter(
            Q(full_name__iexact=harbor_username) | Q(email__istartswith=harbor_username),
            is_active=True,
            realm=realm,
        ).order_by("id")[0]
        return user  # nocoverage
    except IndexError:
        return None


def handle_push_image_event(
    payload: WildValue, user_profile: UserProfile, operator_username: str
) -> str:
    image_name = payload["event_data"]["repository"]["repo_full_name"].tame(check_string)
    image_tag = payload["event_data"]["resources"][0]["tag"].tame(check_string)

    return f"{operator_username} pushed image `{image_name}:{image_tag}`"


SCANNING_COMPLETED_TEMPLATE = """
Image scan completed for `{image_name}:{image_tag}`. Vulnerabilities by severity:

{scan_results}
""".strip()


def handle_scanning_completed_event(
    payload: WildValue, user_profile: UserProfile, operator_username: str
) -> str:
    scan_results = ""
    scan_overview = payload["event_data"]["resources"][0]["scan_overview"]
    if "application/vnd.security.vulnerability.report; version=1.1" not in scan_overview:
        raise UnsupportedWebhookEventTypeError("Unsupported harbor scanning webhook payload")
    scan_summaries = scan_overview["application/vnd.security.vulnerability.report; version=1.1"][
        "summary"
    ]["summary"]
    if len(scan_summaries) > 0:
        for severity, count in scan_summaries.items():
            scan_results += "* {}: **{}**\n".format(severity, count.tame(check_int))
    else:
        scan_results += "None\n"

    return SCANNING_COMPLETED_TEMPLATE.format(
        image_name=payload["event_data"]["repository"]["repo_full_name"].tame(check_string),
        image_tag=payload["event_data"]["resources"][0]["tag"].tame(check_string),
        scan_results=scan_results,
    )


EVENT_FUNCTION_MAPPER = {
    "PUSH_ARTIFACT": handle_push_image_event,
    "SCANNING_COMPLETED": handle_scanning_completed_event,
}

ALL_EVENT_TYPES = list(EVENT_FUNCTION_MAPPER.keys())


@webhook_view("Harbor", all_event_types=ALL_EVENT_TYPES)
@has_request_variables
def api_harbor_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    payload: WildValue = REQ(argument_type="body", converter=to_wild_value),
) -> HttpResponse:
    operator_username = "**{}**".format(payload["operator"].tame(check_string))

    if operator_username != "auto":
        operator_profile = guess_zulip_user_from_harbor(operator_username, user_profile.realm)

    if operator_profile:
        operator_username = f"@**{operator_profile.full_name}**"  # nocoverage

    event = payload["type"].tame(check_string)
    topic = payload["event_data"]["repository"]["repo_full_name"].tame(check_string)

    if event in IGNORED_EVENTS:
        return json_success(request)

    content_func = EVENT_FUNCTION_MAPPER.get(event)

    if content_func is None:
        raise UnsupportedWebhookEventTypeError(event)

    content: str = content_func(payload, user_profile, operator_username)

    check_send_webhook_message(
        request, user_profile, topic, content, event, unquote_url_parameters=True
    )
    return json_success(request)
