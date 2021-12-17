# Webhooks for external integrations.
from typing import Any, Dict, Optional, Sequence

from django.http import HttpRequest, HttpResponse

from zerver.decorator import log_exception_to_webhook_logger, webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.lib.webhooks.git import get_push_commits_event_message
from zerver.models import UserProfile


class Helper:
    def __init__(
        self,
        payload: Dict[str, Any],
        include_title: bool,
    ) -> None:
        self.payload = payload
        self.include_title = include_title

    def log_unsupported(self, event: str) -> None:
        summary = f"The '{event}' event isn't currently supported by the RhodeCode webhook"
        log_exception_to_webhook_logger(
            summary=summary,
            unsupported_event=True,
        )


def get_repository_name(payload: Dict[str, Any]) -> str:
    return payload["event"]["repo"]["repo_name"]


def get_sender_name(payload: Dict[str, Any]) -> str:
    return payload["event"]["actor"]["username"]


def get_push_commits_body(helper: Helper) -> str:
    payload = helper.payload
    commits_data = [
        {
            "name": commit.get("author"),
            "sha": commit["short_id"],
            "url": commit["url"],
            "message": commit["message_html"],
        }
        for commit in payload["event"]["push"]["commits"]
    ]
    return get_push_commits_event_message(
        get_sender_name(payload),
        payload["event"]["repo"]["permalink_url"],
        payload["event"]["push"]["branches"][0]["name"],
        commits_data,
    )


EVENT_FUNCTION_MAPPER = {"push_commits": get_push_commits_body}


ALL_EVENT_TYPES = list(EVENT_FUNCTION_MAPPER.keys())


@webhook_view("RhodeCode", all_event_types=ALL_EVENT_TYPES)
@has_request_variables
def api_rhodecode_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    payload: Dict[str, Sequence[Dict[str, Any]]] = REQ(argument_type="body"),
    branches: Optional[str] = REQ(default=None),
    user_specified_topic: Optional[str] = REQ("topic", default=None),
) -> HttpResponse:

    event = "push_commits"

    body_function = EVENT_FUNCTION_MAPPER[event]

    helper = Helper(
        payload=payload,
        include_title=user_specified_topic is not None,
    )
    body = body_function(helper)

    subject = get_repository_name(payload)

    check_send_webhook_message(request, user_profile, subject, body, event)

    return json_success()
