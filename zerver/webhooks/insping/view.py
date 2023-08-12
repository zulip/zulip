import time

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import WebhookPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_int, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

MESSAGE_TEMPLATE = """
State changed to **{state}**:
* **URL**: {url}
* **Response time**: {response_time} ms
* **Timestamp**: {timestamp}
""".strip()


@webhook_view("Insping")
@typed_endpoint
def api_insping_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: WebhookPayload[WildValue],
) -> HttpResponse:
    data = payload["webhook_event_data"]

    state_name = data["check_state_name"].tame(check_string)
    url_tested = data["request_url"].tame(check_string)
    response_time = data["response_time"].tame(check_int)
    timestamp = data["request_start_time"].tame(check_string)

    time_formatted = time.strftime("%c", time.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.%f+00:00"))

    body = MESSAGE_TEMPLATE.format(
        state=state_name,
        url=url_tested,
        response_time=response_time,
        timestamp=time_formatted,
    )

    topic = "insping"

    check_send_webhook_message(request, user_profile, topic, body)

    return json_success(request)
