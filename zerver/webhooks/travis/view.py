# Webhooks for external integrations.

from django.http import HttpRequest, HttpResponse
from pydantic import BaseModel, Json
from typing_extensions import Annotated

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

MESSAGE_TEMPLATE = """\
Author: {}
Build status: {} {}
Details: [changes]({}), [build log]({})"""


class TravisPayload(BaseModel):
    author_name: str
    status_message: str
    compare_url: str
    build_url: str
    type: str


@webhook_view("Travis", all_event_types=ALL_EVENT_TYPES)
@typed_endpoint
def api_travis_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    message: Annotated[Json[TravisPayload], ApiParamConfig("payload")],
    ignore_pull_requests: Json[bool] = True,
) -> HttpResponse:
    event = message.type
    message_status = message.status_message
    if ignore_pull_requests and message.type == "pull_request":
        return json_success(request)

    if message_status in GOOD_STATUSES:
        emoji = ":thumbs_up:"
    elif message_status in BAD_STATUSES:
        emoji = ":thumbs_down:"
    elif message_status in PENDING_STATUSES:
        emoji = ":counterclockwise:"
    else:
        emoji = f"(No emoji specified for status '{message_status}'.)"

    body = MESSAGE_TEMPLATE.format(
        message.author_name,
        message_status,
        emoji,
        message.compare_url,
        message.build_url,
    )
    topic = "builds"

    check_send_webhook_message(request, user_profile, topic, body, event)
    return json_success(request)
