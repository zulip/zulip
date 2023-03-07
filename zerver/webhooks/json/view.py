import json
from typing import Any, Dict

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

JSON_MESSAGE_TEMPLATE = """
```json
{webhook_payload}
```
""".strip()


@webhook_view("JSON")
@has_request_variables
def api_json_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    payload: Dict[str, Any] = REQ(argument_type="body"),
) -> HttpResponse:
    body = get_body_for_http_request(payload)
    subject = get_subject_for_http_request(payload)

    check_send_webhook_message(request, user_profile, subject, body)
    return json_success(request)


def get_subject_for_http_request(payload: Dict[str, Any]) -> str:
    return "JSON"


def get_body_for_http_request(payload: Dict[str, Any]) -> str:
    prettypayload = json.dumps(payload, indent=2)
    return JSON_MESSAGE_TEMPLATE.format(webhook_payload=prettypayload, sort_keys=True)
