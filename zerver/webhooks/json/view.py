import json
from typing import Any

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

JSON_MESSAGE_TEMPLATE = """
```json
{webhook_payload}
```
""".strip()


@webhook_view("JSON")
@typed_endpoint
def api_json_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[dict[str, Any]],
) -> HttpResponse:
    body = get_body_for_http_request(payload)
    topic_name = get_topic_for_http_request(payload)

    check_send_webhook_message(request, user_profile, topic_name, body)
    return json_success(request)


def get_topic_for_http_request(payload: dict[str, Any]) -> str:
    return "JSON"


def get_body_for_http_request(payload: dict[str, Any]) -> str:
    prettypayload = json.dumps(payload, indent=2)
    return JSON_MESSAGE_TEMPLATE.format(webhook_payload=prettypayload, sort_keys=True)
