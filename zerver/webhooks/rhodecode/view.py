from typing import Any, Dict, Sequence, Optional

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventType
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

def get_push_event_body(payload: Dict[str, Any]) -> str:
    username = get_username(payload)
    commits_count = get_commits_count(payload.get("push"))
    branch_name = get_branch_name(payload.get("push"))
    # TODO: use zerver.lib.webhooks.git instead
    # WIP Fix this for 1 commit vs multipls commits remove/add s after commit accordingly
    return f"{username} pushed {commits_count} commits in {branch_name} branch"

EVENT_FUNCTION_MAPPER = {
    "repo-push": get_push_event_body
}

ALL_EVENT_TYPES = list(EVENT_FUNCTION_MAPPER.keys())

@webhook_view("RhodeCode", all_event_types=ALL_EVENT_TYPES)
@has_request_variables
def api_rhodecode_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    payload: Dict[str, Sequence[Dict[str, Any]]] = REQ(argument_type="body"),
) -> HttpResponse:
    event = get_event(payload.get("event"))

    event_body_function = get_body_based_on_event(event)
    message = event_body_function(payload.get("event"))

    subject = "WIP"
    check_send_webhook_message(request, user_profile, subject, message)
    return json_success()

def get_body_based_on_event(event: str) -> Any:
    return EVENT_FUNCTION_MAPPER[event]

def get_branch_name(payload: Dict[str, Any]) -> str:
    return payload.get("branches")[0].get("name")

def get_commits_count(payload: Dict[str, Any]) -> str:
    return len(payload.get("commits"))

def get_event(
    payload: Dict[str, Any]
) -> Optional[str]:
    event_type = payload.get("name")

    if event_type in list(EVENT_FUNCTION_MAPPER.keys()):
        return event_type

    raise UnsupportedWebhookEventType(event_type)

def get_username(payload: Dict[str, Any]) -> str:
    return payload.get("actor").get("username")