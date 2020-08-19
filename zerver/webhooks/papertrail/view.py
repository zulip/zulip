from typing import Any, Dict

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.validator import check_dict, check_list, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

MATCHES_TEMPLATE = '[Search for "{name}"]({url}) found **{number}** matches:\n'
SEARCH_TEMPLATE = """
{timestamp} - {source} - {query}:
``` quote
{message}
```
""".strip()

@webhook_view('Papertrail')
@has_request_variables
def api_papertrail_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    payload: Dict[str, Any] = REQ(validator=check_dict([
        ("events", check_list(check_dict([]))),
        ("saved_search", check_dict([
            ("name", check_string),
            ("html_search_url", check_string),
        ])),
    ])),
) -> HttpResponse:

    matches = MATCHES_TEMPLATE.format(
        name=payload["saved_search"]["name"],
        url=payload["saved_search"]["html_search_url"],
        number=str(len(payload["events"])),
    )
    message = [matches]

    for i, event in enumerate(payload["events"]):
        event_text = SEARCH_TEMPLATE.format(
            timestamp=event["display_received_at"],
            source=event["source_name"],
            query=payload["saved_search"]["query"],
            message=event["message"],
        )

        message.append(event_text)

        if i >= 3:
            message.append('[See more]({})'.format(payload["saved_search"]["html_search_url"]))
            break

    post = '\n'.join(message)
    topic = 'logs'

    check_send_webhook_message(request, user_profile, topic, post)
    return json_success()
