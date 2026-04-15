# Webhooks for external integrations.

from typing import Annotated

from django.http import HttpRequest, HttpResponse
from pydantic import BaseModel, Json

from zerver.decorator import webhook_view
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import ApiParamConfig, typed_endpoint
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.lib.webhooks.git import TOPIC_WITH_BRANCH_TEMPLATE, TOPIC_WITH_PR_OR_ISSUE_INFO_TEMPLATE
from zerver.models import UserProfile

ALL_EVENT_TYPES = [
    "push",
    "pull_request",
]

STATUS_MAP = {
    "Passed": ("passed", ":check:"),
    "Fixed": ("was fixed", ":check:"),
    "Failed": ("failed", ":warning:"),
    "Broken": ("is broken", ":warning:"),
    "Still Failing": ("is still failing", ":warning:"),
    "Canceled": ("was canceled", ":no_entry:"),
    "Errored": ("errored", ":rotating_light:"),
    "Pending": ("is in progress", ":time_ticking:"),
}

MESSAGE_TEMPLATE = """
{emoji} Build [#{build_number}]({build_url}) **{status}** \
for commit [{commit_message}]({compare_url}) by {author}.
""".strip()


class Repository(BaseModel):
    name: str


class TravisPayload(BaseModel):
    author_name: str
    status_message: str
    compare_url: str
    build_url: str
    type: str
    message: str | None = None
    number: str
    branch: str
    repository: Repository
    pull_request_number: int | None = None
    pull_request_title: str | None = None


def get_message_body(payload: TravisPayload) -> str:
    # Extract only the first line of the commit message
    # for multi-line commit messages.
    commit_message = (
        payload.message.strip().splitlines()[0] if payload.message else "(no commit message)"
    )
    status_message, emoji = STATUS_MAP[payload.status_message]
    body = MESSAGE_TEMPLATE.format(
        build_number=payload.number,
        build_url=payload.build_url,
        status=status_message,
        commit_message=commit_message,
        author=payload.author_name,
        emoji=emoji,
        compare_url=payload.compare_url,
    )

    return body


def get_topic(payload: TravisPayload, event: str) -> str:

    if event == "pull_request":
        topic = TOPIC_WITH_PR_OR_ISSUE_INFO_TEMPLATE.format(
            repo=payload.repository.name,
            type="PR",
            id=payload.pull_request_number,
            title=payload.pull_request_title,
        )
    else:
        topic = TOPIC_WITH_BRANCH_TEMPLATE.format(
            repo=payload.repository.name,
            branch=payload.branch,
        )

    return topic


@webhook_view("Travis", all_event_types=ALL_EVENT_TYPES)
@typed_endpoint
def api_travis_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    message: Annotated[Json[TravisPayload], ApiParamConfig("payload")],
) -> HttpResponse:
    event = message.type

    body = get_message_body(message)
    topic_name = get_topic(message, event)

    check_send_webhook_message(request, user_profile, topic_name, body, event)
    return json_success(request)
