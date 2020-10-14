# Webhooks for external integrations.
from typing import Any, Dict, Iterable

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile


@webhook_view('Mention')
@has_request_variables
def api_mention_webhook(
        request: HttpRequest, user_profile: UserProfile,
        payload: Dict[str, Iterable[Dict[str, Any]]] = REQ(argument_type='body'),
) -> HttpResponse:
    title = payload["title"]
    source_url = payload["url"]
    description = payload["description"]
    # construct the body of the message
    template = """
**[{title}]({url})**:

``` quote
{description}
```
""".strip()
    body = template.format(title=title, url=source_url,
                           description=description)
    topic = 'news'

    # send the message
    check_send_webhook_message(request, user_profile, topic, body)

    return json_success()
