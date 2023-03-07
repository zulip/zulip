from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _

from zerver.decorator import webhook_view
from zerver.lib.exceptions import JsonableError
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.validator import WildValue, check_string, to_wild_value
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

MATCHES_TEMPLATE = '[Search for "{name}"]({url}) found **{number}** matches:\n'
SEARCH_TEMPLATE = """
{timestamp} - {source} - {query}:
``` quote
{message}
```
""".strip()


@webhook_view("Papertrail")
@has_request_variables
def api_papertrail_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    payload: WildValue = REQ(converter=to_wild_value),
) -> HttpResponse:
    if "events" not in payload:
        raise JsonableError(_("Events key is missing from payload"))

    matches = MATCHES_TEMPLATE.format(
        name=payload["saved_search"]["name"].tame(check_string),
        url=payload["saved_search"]["html_search_url"].tame(check_string),
        number=str(len(payload["events"])),
    )
    message = [matches]

    for i, event in enumerate(payload["events"]):
        event_text = SEARCH_TEMPLATE.format(
            timestamp=event["display_received_at"].tame(check_string),
            source=event["source_name"].tame(check_string),
            query=payload["saved_search"]["query"].tame(check_string),
            message=event["message"].tame(check_string),
        )

        message.append(event_text)

        if i >= 3:
            message.append(
                "[See more]({})".format(
                    payload["saved_search"]["html_search_url"].tame(check_string)
                )
            )
            break

    post = "\n".join(message)
    topic = "logs"

    check_send_webhook_message(request, user_profile, topic, post)
    return json_success(request)
