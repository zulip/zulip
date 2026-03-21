# Webhooks for external integrations.

from typing import Annotated

from django.http import HttpRequest, HttpResponse
from pydantic import BaseModel, Json

from zerver.decorator import webhook_view
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import ApiParamConfig, typed_endpoint
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

GOOD_STATUSES = ["Passed", "Fixed"]
BAD_STATUSES = ["Failed", "Broken", "Still Failing", "Errored", "Canceled"]
PENDING_STATUSES = ["Pending"]
ALL_EVENT_TYPES = [
    "push",
    "pull_request",
]

STATUS_MAP = {
    "Passed": "**passed**",
    "Fixed": "was **fixed**",
    "Failed": "**failed**",
    "Broken": "is **broken**",
    "Still Failing": "is **still failing**",
    "Canceled": "was **canceled**",
    "Errored": "**errored**",
    "Pending": "is **being built**",
}

MESSAGE_TEMPLATE = """
**Build [#{build_number}]({build_url})** {status} {emoji} \
for commit: [{commit_message}]({compare_url}) by {author}.
""".strip()


class TravisPayload(BaseModel):
    author_name: str
    status_message: str
    compare_url: str
    build_url: str
    type: str
    message: str | None = None
    number: str


def get_message(payload: TravisPayload) -> str:
    commit_message = (
        payload.message.strip().splitlines()[0] if payload.message else "(no commit message)"
    )
    status_message = payload.status_message

    if status_message in GOOD_STATUSES:
        emoji = ":thumbs_up:"
    elif status_message in BAD_STATUSES:
        emoji = ":thumbs_down:"
    elif status_message in PENDING_STATUSES:
        emoji = ":counterclockwise:"
    else:
        emoji = f"(No emoji specified for status '{status_message}'.)"

    body = MESSAGE_TEMPLATE.format(
        build_number=payload.number,
        build_url=payload.build_url,
        status=STATUS_MAP[status_message],
        commit_message=commit_message,
        author=payload.author_name,
        emoji=emoji,
        compare_url=payload.compare_url,
    )

    return body


@webhook_view("Travis", all_event_types=ALL_EVENT_TYPES)
@typed_endpoint
def api_travis_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    message: Annotated[Json[TravisPayload], ApiParamConfig("payload")],
) -> HttpResponse:
    event = message.type
    body = get_message(message)
    topic_name = "builds"
    check_send_webhook_message(request, user_profile, topic_name, body, event)
    return json_success(request)
