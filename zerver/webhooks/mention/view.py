# Webhooks for external integrations.
from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import WebhookPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile


@webhook_view("Mention")
@typed_endpoint
def api_mention_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: WebhookPayload[WildValue],
) -> HttpResponse:
    title = payload["title"].tame(check_string)
    source_url = payload["url"].tame(check_string)
    description = payload["description"].tame(check_string)
    # construct the body of the message
    template = """
**[{title}]({url})**:

``` quote
{description}
```
""".strip()
    body = template.format(title=title, url=source_url, description=description)
    topic = "news"

    # send the message
    check_send_webhook_message(request, user_profile, topic, body)

    return json_success(request)
