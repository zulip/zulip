from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventTypeError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_int, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile


def get_event_type(payload: WildValue) -> str:
    return payload["action"].tame(check_string)


def get_issue_topic(payload: WildValue) -> str:
    issue_id = payload["issue"]["id"].tame(check_int)
    return f"Issue #{issue_id}"


def handle_issue_updated(payload: WildValue) -> str:
    issue = payload["issue"]
    author = issue["author"]
    url = payload["url"].tame(check_string)
    author_name = (
        f"{author['firstname'].tame(check_string)} {author['lastname'].tame(check_string)}"
    )
    issue_link = f"[#{issue['id'].tame(check_int)} {issue['subject'].tame(check_string)}]({url})"
    message = f"{author_name} updated issue {issue_link}:\n"
    message += f"• **Status:** {issue['status']['name'].tame(check_string)}\n"

    if payload.get("journal"):
        journal = payload["journal"]
        if journal.get("notes"):
            notes = journal["notes"].tame(check_string)
            if notes.strip():
                message += f"• **Notes:** {notes}"

    return message


def handle_issue_opened(payload: WildValue) -> str:
    issue = payload["issue"]
    author = issue["author"]
    url = payload["url"].tame(check_string)
    author_name = (
        f"{author['firstname'].tame(check_string)} {author['lastname'].tame(check_string)}"
    )
    issue_link = f"[#{issue['id'].tame(check_int)} {issue['subject'].tame(check_string)}]({url})"
    message = f"{author_name} created issue {issue_link}:\n"
    details = []
    if issue.get("assignee"):
        assignee = issue["assignee"]
        assignee_name = (
            f"{assignee['firstname'].tame(check_string)} {assignee['lastname'].tame(check_string)}"
        )
        details.append(f"**Assignee:** {assignee_name}")

    details.append(f"**Status:** {issue['status']['name'].tame(check_string)}")
    if issue.get("priority"):
        details.append(f"**Priority:** {issue['priority']['name'].tame(check_string)}")
    if details:
        message += "• " + "\n• ".join(details)

    return message


REDMINE_EVENT_FUNCTION_MAPPER = {
    "opened": handle_issue_opened,
    "updated": handle_issue_updated,
}

ALL_EVENT_TYPES = list(REDMINE_EVENT_FUNCTION_MAPPER.keys())
DESCRIPTION_TRUNCATE_LENGTH = 200


@webhook_view("Redmine", notify_bot_owner_on_invalid_json=True, all_event_types=ALL_EVENT_TYPES)
@typed_endpoint
def api_redmine_webhook(
    request: HttpRequest, user_profile: UserProfile, *, payload: JsonBodyPayload[WildValue]
) -> HttpResponse:
    redmine_payload = payload["payload"]
    event = get_event_type(redmine_payload)

    if event not in REDMINE_EVENT_FUNCTION_MAPPER:
        raise UnsupportedWebhookEventTypeError(event)

    topic_name = get_issue_topic(redmine_payload)
    content_func = REDMINE_EVENT_FUNCTION_MAPPER[event]
    content = content_func(redmine_payload)
    check_send_webhook_message(request, user_profile, topic_name, content)

    return json_success(request)
