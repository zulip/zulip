# Webhooks for external integrations.

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import WebhookPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile


@webhook_view("HelloWorld")
@typed_endpoint
def api_helloworld_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: WebhookPayload[WildValue],
) -> HttpResponse:
    # construct the body of the message
    body = "Hello! I am happy to be here! :smile:"

    # try to add the Wikipedia article of the day
    body_template = (
        "\nThe Wikipedia featured article for today is **[{featured_title}]({featured_url})**"
    )
    body += body_template.format(
        featured_title=payload["featured_title"].tame(check_string),
        featured_url=payload["featured_url"].tame(check_string),
    )

    topic = "Hello World"

    # send the message
    check_send_webhook_message(request, user_profile, topic, body)

    return json_success(request)
