# Webhooks for external integrations.
from functools import partial
from typing import Any, Callable, Dict, Optional

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventType
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
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

def ticket_started_body(payload: Dict[str, Any]) -> str:
    return TICKET_STARTED_TEMPLATE.format(**payload)

def ticket_assigned_body(payload: Dict[str, Any]) -> Optional[str]:
    state = payload['state']
    kwargs = {
        'state': 'open' if state == 'opened' else state,
        'number': payload['number'],
        'title': payload['title'],
        'app_url': payload['app_url'],
    }

    assignee = payload['assignee']
    assigned_group = payload['assigned_group']

    if assignee or assigned_group:
        if assignee and assigned_group:
            kwargs['assignee_info'] = '{assignee} from {assigned_group}'.format(**payload)
        elif assignee:
            kwargs['assignee_info'] = '{assignee}'.format(**payload)
        elif assigned_group:
            kwargs['assignee_info'] = '{assigned_group}'.format(**payload)

        return TICKET_ASSIGNED_TEMPLATE.format(**kwargs)
    else:
        return None

def replied_body(payload: Dict[str, Any], actor: str, action: str) -> str:
    actor_url = "http://api.groovehq.com/v1/{}/".format(actor + 's')
    actor = payload['links']['author']['href'].split(actor_url)[1]
    number = payload['links']['ticket']['href'].split("http://api.groovehq.com/v1/tickets/")[1]

    body = AGENT_REPLIED_TEMPLATE.format(
        actor=actor,
        action=action,
        number=number,
        app_ticket_url=payload['app_ticket_url'],
        plain_text_body=payload['plain_text_body'],
    )

    return body

def get_event_handler(event: str) -> Callable[..., str]:
    # The main reason for this function existence is because of mypy
    handler: Any = EVENTS_FUNCTION_MAPPER.get(event)
    if handler is None:
        raise UnsupportedWebhookEventType(event)
    return handler

@webhook_view('Groove')
@has_request_variables
def api_groove_webhook(request: HttpRequest, user_profile: UserProfile,
                       payload: Dict[str, Any]=REQ(argument_type='body')) -> HttpResponse:
    event = validate_extract_webhook_http_header(request, 'X_GROOVE_EVENT', 'Groove')
    assert event is not None
    handler = get_event_handler(event)

    body = handler(payload)
    topic = 'notifications'

    if body is not None:
        check_send_webhook_message(request, user_profile, topic, body)

    return json_success()

EVENTS_FUNCTION_MAPPER = {
    'ticket_started': ticket_started_body,
    'ticket_assigned': ticket_assigned_body,
    'agent_replied': partial(replied_body, actor='agent', action='replied to'),
    'customer_replied': partial(replied_body, actor='customer', action='replied to'),
    'note_added': partial(replied_body, actor='agent', action='left a note on'),
}

fixture_to_headers = get_http_headers_from_filename("HTTP_X_GROOVE_EVENT")
