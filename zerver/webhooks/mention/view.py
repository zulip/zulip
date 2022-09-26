# Webhooks for external integrations.
from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.validator import WildValue, check_string, to_wild_value
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile


@webhook_view("Mention")
@has_request_variables
def api_mention_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    payload: WildValue = REQ(argument_type="body", converter=to_wild_value),
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
