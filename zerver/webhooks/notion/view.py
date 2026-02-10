from collections.abc import Callable

from django.http import HttpRequest
from django.http.response import HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventTypeError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_none_or, check_string
from zerver.lib.webhooks.common import check_send_webhook_message, get_setup_webhook_message
from zerver.models import UserProfile

NOTION_VERIFICATION_TOKEN_MESSAGE = """
{setup_message}
Your verification token is: `{token}`
Please copy this token and paste it into your Notion webhook configuration to complete the setup.
""".strip()


def handle_verification_request(payload: WildValue) -> tuple[str, str]:
    verification_token = payload["verification_token"].tame(check_string)
    setup_message = get_setup_webhook_message("Notion")
    body = NOTION_VERIFICATION_TOKEN_MESSAGE.format(
        setup_message=setup_message, token=verification_token
    )
    return ("Verification", body)


EVENT_TO_FUNCTION_MAPPER: dict[str, Callable[[WildValue], tuple[str, str]]] = {
    "verification": handle_verification_request,
}


def is_verification(payload: WildValue) -> bool:
    return payload.get("verification_token").tame(check_none_or(check_string)) is not None


ALL_EVENT_TYPES = list(EVENT_TO_FUNCTION_MAPPER.keys())


@webhook_view("Notion", all_event_types=ALL_EVENT_TYPES)
@typed_endpoint
def api_notion_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
) -> HttpResponse:
    if is_verification(payload):
        event_type = "verification"
    else:
        event_type = payload.get("type").tame(check_string)  # nocoverage

    handler = EVENT_TO_FUNCTION_MAPPER.get(event_type)
    if handler is None:
        raise UnsupportedWebhookEventTypeError(event_type)
    topic_name, body = handler(payload)

    check_send_webhook_message(request, user_profile, topic_name, body, event_type)
    return json_success(request)
