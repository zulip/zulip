from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import WebhookPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

LINK_TEMPLATE = "[See in Wekan]({url})"
MESSAGE_TEMPLATE = "{body}\n\n{footer}"


def get_url(text: str) -> str:
    return text.split("\n")[-1]


def get_hyperlinked_url(text: str) -> str:
    url = get_url(text)
    return LINK_TEMPLATE.format(url=url)


def clean_payload_text(text: str) -> str:
    url = get_url(text)
    return text.replace(url, "").replace("\n", "")


def get_message_body(payload: WildValue) -> str:
    footer = get_hyperlinked_url(payload["text"].tame(check_string))
    body = process_message_data(payload)
    return MESSAGE_TEMPLATE.format(body=body, footer=footer)


def process_message_data(payload: WildValue) -> str:
    text = clean_payload_text(payload["text"].tame(check_string))
    return f"{text}."


@webhook_view("Wekan")
@typed_endpoint
def api_wekan_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: WebhookPayload[WildValue],
) -> HttpResponse:
    topic = "Wekan Notification"
    body = get_message_body(payload)
    check_send_webhook_message(request, user_profile, topic, body)
    return json_success(request)
