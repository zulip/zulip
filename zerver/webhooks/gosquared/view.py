from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventTypeError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import WebhookPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_bool, check_int, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

TRAFFIC_SPIKE_TEMPLATE = "[{website_name}]({website_url}) has {user_num} visitors online."
CHAT_MESSAGE_TEMPLATE = """
The {status} **{name}** messaged:

``` quote
{content}
```
""".strip()


ALL_EVENT_TYPES = ["chat_message", "traffic_spike"]


@webhook_view("GoSquared", all_event_types=ALL_EVENT_TYPES)
@typed_endpoint
def api_gosquared_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: WebhookPayload[WildValue],
) -> HttpResponse:
    body = ""
    topic = ""

    # Unfortunately, there is no other way to infer the event type
    # than just inferring it from the payload's attributes
    # Traffic spike/dip event
    if "concurrents" in payload and "siteDetails" in payload:
        domain_name = payload["siteDetails"]["domain"].tame(check_string)
        user_num = payload["concurrents"].tame(check_int)
        user_acc = payload["siteDetails"]["acct"].tame(check_string)
        acc_url = "https://www.gosquared.com/now/" + user_acc
        body = TRAFFIC_SPIKE_TEMPLATE.format(
            website_name=domain_name, website_url=acc_url, user_num=user_num
        )
        topic = f"GoSquared - {domain_name}"
        check_send_webhook_message(request, user_profile, topic, body, "traffic_spike")

    # Live chat message event
    elif payload.get("message") is not None and payload.get("person") is not None:
        # Only support non-direct messages
        if not payload["message"]["private"].tame(check_bool):
            session_title = payload["message"]["session"]["title"].tame(check_string)
            topic = f"Live chat session - {session_title}"
            body = CHAT_MESSAGE_TEMPLATE.format(
                status=payload["person"]["status"].tame(check_string),
                name=payload["person"]["_anon"]["name"].tame(check_string),
                content=payload["message"]["content"].tame(check_string),
            )
            check_send_webhook_message(request, user_profile, topic, body, "chat_message")
    else:
        raise UnsupportedWebhookEventTypeError("unknown_event")

    return json_success(request)
