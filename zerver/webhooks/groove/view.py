# Webhooks for external integrations.
from functools import partial
from typing import Callable, Dict, Optional

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventType
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.validator import (
    WildValue,
    check_int,
    check_none_or,
    check_string,
    check_url,
    to_wild_value,
)
from zerver.lib.webhooks.common import (
    check_send_webhook_message,
    get_http_headers_from_filename,
    validate_extract_webhook_http_header,
)
from zerver.models import UserProfile

TICKET_STARTED_TEMPLATE = """
{customer_name} submitted new ticket [#{number}: {title}]({app_url}):

``` quote
{summary}
```
""".strip()

TICKET_ASSIGNED_TEMPLATE = "[#{number}: {title}]({app_url}) ({state}) assigned to {assignee_info}."

AGENT_REPLIED_TEMPLATE = """
{actor} {action} [ticket #{number}]({app_ticket_url}):

``` quote
{plain_text_body}
```
""".strip()


def ticket_started_body(payload: WildValue) -> str:
    return TICKET_STARTED_TEMPLATE.format(
        customer_name=payload["customer_name"].tame(check_string),
        number=payload["number"].tame(check_int),
        title=payload["title"].tame(check_string),
        app_url=payload["app_url"].tame(check_url),
        summary=payload["summary"].tame(check_string),
    )


def ticket_assigned_body(payload: WildValue) -> Optional[str]:
    state = payload["state"].tame(check_string)
    kwargs = {
        "state": "open" if state == "opened" else state,
        "number": payload["number"].tame(check_int),
        "title": payload["title"].tame(check_string),
        "app_url": payload["app_url"].tame(check_url),
    }

    assignee = payload["assignee"].tame(check_none_or(check_string))
    assigned_group = payload["assigned_group"].tame(check_none_or(check_string))

    if assignee or assigned_group:
        if assignee and assigned_group:
            kwargs["assignee_info"] = "{assignee} from {assigned_group}".format(
                assignee=assignee, assigned_group=assigned_group
            )
        elif assignee:
            kwargs["assignee_info"] = "{assignee}".format(assignee=assignee)
        elif assigned_group:
            kwargs["assignee_info"] = "{assigned_group}".format(assigned_group=assigned_group)

        return TICKET_ASSIGNED_TEMPLATE.format(**kwargs)
    else:
        return None


def replied_body(payload: WildValue, actor: str, action: str) -> str:
    actor_url = "http://api.groovehq.com/v1/{}/".format(actor + "s")
    actor = payload["links"]["author"]["href"].tame(check_url).split(actor_url)[1]
    number = (
        payload["links"]["ticket"]["href"]
        .tame(check_url)
        .split("http://api.groovehq.com/v1/tickets/")[1]
    )

    body = AGENT_REPLIED_TEMPLATE.format(
        actor=actor,
        action=action,
        number=number,
        app_ticket_url=payload["app_ticket_url"].tame(check_url),
        plain_text_body=payload["plain_text_body"].tame(check_string),
    )

    return body


EVENTS_FUNCTION_MAPPER: Dict[str, Callable[[WildValue], Optional[str]]] = {
    "ticket_started": ticket_started_body,
    "ticket_assigned": ticket_assigned_body,
    "agent_replied": partial(replied_body, actor="agent", action="replied to"),
    "customer_replied": partial(replied_body, actor="customer", action="replied to"),
    "note_added": partial(replied_body, actor="agent", action="left a note on"),
}

ALL_EVENT_TYPES = list(EVENTS_FUNCTION_MAPPER.keys())


@webhook_view("Groove", all_event_types=ALL_EVENT_TYPES)
@has_request_variables
def api_groove_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    payload: WildValue = REQ(argument_type="body", converter=to_wild_value),
) -> HttpResponse:
    event = validate_extract_webhook_http_header(request, "X-Groove-Event", "Groove")
    assert event is not None
    handler = EVENTS_FUNCTION_MAPPER.get(event)
    if handler is None:
        raise UnsupportedWebhookEventType(event)

    body = handler(payload)
    topic = "notifications"

    if body is not None:
        check_send_webhook_message(request, user_profile, topic, body, event)

    return json_success(request)


fixture_to_headers = get_http_headers_from_filename("HTTP_X_GROOVE_EVENT")
