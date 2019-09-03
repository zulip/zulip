from typing import Any, Dict, Optional

from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _

from zerver.decorator import api_key_only_webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

MATCHES_TEMPLATE = '[Search for "{name}"]({url}) found **{number}** matches:\n'
SEARCH_TEMPLATE = """
{timestamp} - {source} - {query}:
``` quote
{message}
```
""".strip()

def ensure_keys(name: str, data: Any) -> Optional[str]:
    if 'events' in data and 'saved_search' in data:
        saved_search = data['saved_search']
        if 'name' in saved_search and 'html_search_url' in saved_search:
            return None
    return _("Missing expected keys")

@api_key_only_webhook_view('Papertrail')
@has_request_variables
def api_papertrail_webhook(request: HttpRequest, user_profile: UserProfile,
                           payload: Dict[str, Any]=REQ(validator=ensure_keys)) -> HttpResponse:

    matches = MATCHES_TEMPLATE.format(
        name=payload["saved_search"]["name"],
        url=payload["saved_search"]["html_search_url"],
        number=str(len(payload["events"]))
    )
    message = [matches]

    for i, event in enumerate(payload["events"]):
        event_text = SEARCH_TEMPLATE.format(
            timestamp=event["display_received_at"],
            source=event["source_name"],
            query=payload["saved_search"]["query"],
            message=event["message"]
        )

        message.append(event_text)

        if i >= 3:
            message.append('[See more]({})'.format(payload["saved_search"]["html_search_url"]))
            break

    post = '\n'.join(message)
    topic = 'logs'

    check_send_webhook_message(request, user_profile, topic, post)
    return json_success()
