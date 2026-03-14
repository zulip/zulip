from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventTypeError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_int, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

ISSUE_OPENED_MESSAGE_TEMPLATE = (
    "**{author_name}** opened {issue_link}{assignee_info}.{issue_description}"
)

ISSUE_UPDATED_MESSAGE_TEMPLATE = "**{author_name}** updated {issue_link}.{journal_notes}"

CONTENT_MESSAGE_TEMPLATE = "\n\n~~~ quote\n{message}\n~~~"


def _extract_issue_label(issue: WildValue) -> str:
    id = issue["id"].tame(check_int)
    subject = issue["subject"].tame(check_string)
    return f"#{id} {subject}"


def get_issue_topic(payload: WildValue) -> str:
    issue_label = _extract_issue_label(payload["issue"])
    return f"Issue {issue_label}"


def _get_issue_link(payload: WildValue) -> str:
    url = payload["url"].tame(check_string)
    issue = payload["issue"]
    issue_label = _extract_issue_label(issue)
    return f"[{issue_label}]({url})"


def _get_user_name(user: WildValue) -> str:
    return f"{user['firstname'].tame(check_string)} {user['lastname'].tame(check_string)}"


def _get_assignee_string(issue: WildValue) -> str:
    if assignee := issue.get("assignee"):
        assignee_name = _get_user_name(assignee)
        return f" for **{assignee_name}**"
    return ""


def handle_issue_opened(payload: WildValue) -> str:
    issue = payload["issue"]
    author_name = _get_user_name(issue["author"])
    issue_link = _get_issue_link(payload)
    assignee_info = _get_assignee_string(issue)

    issue_description = ""
    if issue.get("description") and (
        description := issue["description"].tame(check_string).strip()
    ):
        issue_description = CONTENT_MESSAGE_TEMPLATE.format(message=description)

    return ISSUE_OPENED_MESSAGE_TEMPLATE.format(
        author_name=author_name,
        issue_link=issue_link,
        assignee_info=assignee_info,
        issue_description=issue_description,
    )


def handle_issue_updated(payload: WildValue) -> str:
    issue = payload["issue"]
    author_name = _get_user_name(issue["author"])
    issue_link = _get_issue_link(payload)

    journal_notes = ""
    if (
        (journal := payload.get("journal"))
        and (notes := journal.get("notes"))
        and (tamed_notes := notes.tame(check_string).strip())
    ):
        journal_notes = CONTENT_MESSAGE_TEMPLATE.format(message=tamed_notes)

    return ISSUE_UPDATED_MESSAGE_TEMPLATE.format(
        author_name=author_name,
        issue_link=issue_link,
        journal_notes=journal_notes,
    )


REDMINE_EVENT_FUNCTION_MAPPER = {
    "opened": handle_issue_opened,
    "updated": handle_issue_updated,
}

ALL_EVENT_TYPES = list(REDMINE_EVENT_FUNCTION_MAPPER.keys())


@webhook_view("Redmine", notify_bot_owner_on_invalid_json=True, all_event_types=ALL_EVENT_TYPES)
@typed_endpoint
def api_redmine_webhook(
    request: HttpRequest, user_profile: UserProfile, *, payload: JsonBodyPayload[WildValue]
) -> HttpResponse:
    redmine_payload = payload["payload"]
    event = redmine_payload["action"].tame(check_string)

    if event not in REDMINE_EVENT_FUNCTION_MAPPER:
        raise UnsupportedWebhookEventTypeError(event)

    topic_name = get_issue_topic(redmine_payload)
    content_func = REDMINE_EVENT_FUNCTION_MAPPER[event]
    content = content_func(redmine_payload)
    check_send_webhook_message(request, user_profile, topic_name, content)

    return json_success(request)
