from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import WebhookPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_int, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

ALL_EVENT_TYPES = ["new", "finished"]


@webhook_view("Buildbot", all_event_types=ALL_EVENT_TYPES)
@typed_endpoint
def api_buildbot_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: WebhookPayload[WildValue],
) -> HttpResponse:
    topic = payload["project"].tame(check_string)
    if not topic:
        topic = "general"
    body = get_message(payload)
    check_send_webhook_message(
        request, user_profile, topic, body, payload["event"].tame(check_string)
    )
    return json_success(request)


def get_message(payload: WildValue) -> str:
    if "results" in payload:
        # See http://docs.buildbot.net/latest/developer/results.html
        results = ("success", "warnings", "failure", "skipped", "exception", "retry", "cancelled")
        status = results[payload["results"].tame(check_int)]

    event = payload["event"].tame(check_string)
    if event == "new":
        body = "Build [#{id}]({url}) for **{name}** started.".format(
            id=payload["buildid"].tame(check_int),
            name=payload["buildername"].tame(check_string),
            url=payload["url"].tame(check_string),
        )
    elif event == "finished":
        body = "Build [#{id}]({url}) (result: {status}) for **{name}** finished.".format(
            id=payload["buildid"].tame(check_int),
            name=payload["buildername"].tame(check_string),
            url=payload["url"].tame(check_string),
            status=status,
        )

    return body
