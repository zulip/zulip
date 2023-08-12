from typing import Callable, Dict, Optional

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventTypeError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import WebhookPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_int, check_string
from zerver.lib.webhooks.common import OptionalUserSpecifiedTopicStr, check_send_webhook_message
from zerver.models import UserProfile

CONTENT_MESSAGE_TEMPLATE = "\n~~~ quote\n{message}\n~~~\n"

ISSUE_CREATE_OR_UPDATE_TEMPLATE = (
    "{type} [#{number} {title}]({url}) was {action} in team {team_name}"
)

ISSUE_REMOVE_TEMPLATE = "{type} **#{number} {title}** has been removed from team {team_name}."
COMMENT_CREATE_OR_UPDATE_TEMPLATE = "{user} [{action}]({url}) on issue **{issue_title}**:"
COMMENT_REMOVE_TEMPLATE = "{user} has removed a comment."


def get_issue_created_or_updated_message(event: str, payload: WildValue, action: str) -> str:
    message = ISSUE_CREATE_OR_UPDATE_TEMPLATE.format(
        type="Issue" if event == "issue" else "Sub-Issue",
        number=payload["data"]["number"].tame(check_int),
        title=payload["data"]["title"].tame(check_string),
        url=payload["url"].tame(check_string),
        action=action,
        team_name=payload["data"]["team"]["name"].tame(check_string),
    )

    has_description = "description" in payload["data"]
    if has_description:
        message += f":{CONTENT_MESSAGE_TEMPLATE.format(message=payload['data']['description'].tame(check_string))}"
    else:
        message += "."

    to_add = []

    priority_label = payload["data"]["priorityLabel"].tame(check_string)
    if priority_label != "No priority":
        to_add.append(f"Priority: {priority_label}")

    has_assignee = "assignee" in payload["data"]
    if has_assignee:
        to_add.append(f"Assignee: {payload['data']['assignee']['name'].tame(check_string)}")

    status = payload["data"]["state"]["name"].tame(check_string)
    to_add.append(f"Status: {status}")

    message += f"\n{', '.join(to_add)}."

    return message


def get_issue_remove_body(payload: WildValue, event: str) -> str:
    return ISSUE_REMOVE_TEMPLATE.format(
        type="Issue" if event == "issue" else "Sub-Issue",
        number=payload["data"]["number"].tame(check_int),
        title=payload["data"]["title"].tame(check_string),
        team_name=payload["data"]["team"]["name"].tame(check_string),
    )


def get_comment_create_or_update_body(payload: WildValue, event: str, action: str) -> str:
    message = COMMENT_CREATE_OR_UPDATE_TEMPLATE.format(
        user=payload["data"]["user"]["name"].tame(check_string),
        action=action,
        url=payload["url"].tame(check_string),
        issue_title=payload["data"]["issue"]["title"].tame(check_string),
    )
    message += CONTENT_MESSAGE_TEMPLATE.format(message=payload["data"]["body"].tame(check_string))
    return message


def get_comment_remove_body(payload: WildValue, event: str) -> str:
    return COMMENT_REMOVE_TEMPLATE.format(user=payload["data"]["user"]["name"].tame(check_string))


def get_issue_or_sub_issue_message(payload: WildValue, event: str) -> str:
    action = payload["action"].tame(check_string)
    if action == "remove":
        return get_issue_remove_body(payload, event)

    return get_issue_created_or_updated_message(
        event, payload, action="created" if action == "create" else "updated"
    )


def get_comment_message(payload: WildValue, event: str) -> str:
    action = payload["action"].tame(check_string)
    if action == "remove":
        return get_comment_remove_body(payload, event)

    return get_comment_create_or_update_body(
        payload, event, "commented" if action == "create" else "updated comment"
    )


EVENT_FUNCTION_MAPPER: Dict[str, Callable[[WildValue, str], str]] = {
    "issue": get_issue_or_sub_issue_message,
    "sub_issue": get_issue_or_sub_issue_message,
    "comment": get_comment_message,
}

IGNORED_EVENTS = ["IssueLabel", "Project", "ProjectUpdate", "Cycle", "Reaction"]

ALL_EVENT_TYPES = list(EVENT_FUNCTION_MAPPER.keys())


@webhook_view("Linear", notify_bot_owner_on_invalid_json=True, all_event_types=ALL_EVENT_TYPES)
@typed_endpoint
def api_linear_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: WebhookPayload[WildValue],
    user_specified_topic: OptionalUserSpecifiedTopicStr = None,
) -> HttpResponse:
    event_type = get_event_type(payload)
    if event_type is None:
        return json_success(request)

    topic = get_topic(user_specified_topic, event_type, payload)

    body_function = EVENT_FUNCTION_MAPPER[event_type]
    body = body_function(payload, event_type)

    check_send_webhook_message(request, user_profile, topic, body)

    return json_success(request)


def get_topic(user_specified_topic: Optional[str], event: str, payload: WildValue) -> str:
    if user_specified_topic is not None:
        return user_specified_topic
    elif event == "comment":
        issue_id = payload["data"]["issueId"].tame(check_string)
        return issue_id
    elif event == "sub_issue":
        parent = payload["data"]["parentId"].tame(check_string)
        return parent
    elif event == "issue":
        issue_id = payload["data"]["id"].tame(check_string)
        return issue_id

    raise UnsupportedWebhookEventTypeError("unknown event type")


def get_event_type(payload: WildValue) -> Optional[str]:
    event_type = payload["type"].tame(check_string)

    if event_type == "Issue":
        has_parent_id = "parentId" in payload["data"]
        return "issue" if not has_parent_id else "sub_issue"
    elif event_type == "Comment":
        return "comment"
    elif event_type in IGNORED_EVENTS:
        return None

    # This happens when a new event type is added to Linear and we
    # haven't updated the integration yet.
    complete_event = "{}:{}".format(
        event_type, payload.get("action", "???").tame(check_string)
    )  # nocoverage

    raise UnsupportedWebhookEventTypeError(complete_event)
