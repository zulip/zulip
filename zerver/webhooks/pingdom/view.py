# Webhooks for external integrations.
from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventTypeError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import WebhookPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

PINGDOM_TOPIC_TEMPLATE = "{name} status."

MESSAGE_TEMPLATE = """
Service {service_url} changed its {type} status from {previous_state} to {current_state}:
""".strip()

DESC_TEMPLATE = """

``` quote
{description}
```
""".rstrip()

SUPPORTED_CHECK_TYPES = (
    "HTTP",
    "HTTP_CUSTOM",
    "HTTPS",
    "SMTP",
    "POP3",
    "IMAP",
    "PING",
    "DNS",
    "UDP",
    "PORT_TCP",
)

ALL_EVENT_TYPES = list(SUPPORTED_CHECK_TYPES)


@webhook_view("Pingdom", all_event_types=ALL_EVENT_TYPES)
@typed_endpoint
def api_pingdom_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: WebhookPayload[WildValue],
) -> HttpResponse:
    check_type = get_check_type(payload)

    if check_type in SUPPORTED_CHECK_TYPES:
        topic = get_topic_for_http_request(payload)
        body = get_body_for_http_request(payload)
    else:
        raise UnsupportedWebhookEventTypeError(check_type)

    check_send_webhook_message(request, user_profile, topic, body, check_type)
    return json_success(request)


def get_topic_for_http_request(payload: WildValue) -> str:
    return PINGDOM_TOPIC_TEMPLATE.format(name=payload["check_name"].tame(check_string))


def get_body_for_http_request(payload: WildValue) -> str:
    current_state = payload["current_state"].tame(check_string)
    previous_state = payload["previous_state"].tame(check_string)

    data = {
        "service_url": payload["check_params"]["hostname"].tame(check_string),
        "previous_state": previous_state,
        "current_state": current_state,
        "type": get_check_type(payload),
    }
    body = MESSAGE_TEMPLATE.format(**data)
    if current_state == "DOWN" and previous_state == "UP":
        description = DESC_TEMPLATE.format(
            description=payload["long_description"].tame(check_string)
        )
        body += description
    else:
        body = f"{body[:-1]}."

    return body


def get_check_type(payload: WildValue) -> str:
    return payload["check_type"].tame(check_string)
