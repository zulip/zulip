# Webhooks for external integrations.
from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import WebhookPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import MAX_TOPIC_NAME_LENGTH, UserProfile

MESSAGE_TEMPLATE = """
Splunk alert from saved search:
* **Search**: [{search}]({link})
* **Host**: {host}
* **Source**: `{source}`
* **Raw**: `{raw}`
""".strip()


@webhook_view("Splunk")
@typed_endpoint
def api_splunk_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: WebhookPayload[WildValue],
) -> HttpResponse:
    # use default values if expected data is not provided
    search_name = payload.get("search_name", "Missing search_name").tame(check_string)
    results_link = payload.get("results_link", "Missing results_link").tame(check_string)
    host = payload.get("result", {}).get("host", "Missing host").tame(check_string)
    source = payload.get("result", {}).get("source", "Missing source").tame(check_string)
    raw = payload.get("result", {}).get("_raw", "Missing _raw").tame(check_string)

    # for the default topic, use search name but truncate if too long
    if len(search_name) >= MAX_TOPIC_NAME_LENGTH:
        topic = f"{search_name[:(MAX_TOPIC_NAME_LENGTH - 3)]}..."
    else:
        topic = search_name

    # construct the message body
    body = MESSAGE_TEMPLATE.format(
        search=search_name,
        link=results_link,
        host=host,
        source=source,
        raw=raw,
    )

    # send the message
    check_send_webhook_message(request, user_profile, topic, body)

    return json_success(request)
