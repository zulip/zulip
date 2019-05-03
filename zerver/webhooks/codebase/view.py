import json
from typing import Any, Dict, Iterable

from django.http import HttpRequest, HttpResponse
from zerver.decorator import api_key_only_webhook_view
from zerver.lib.webhooks.common import check_send_webhook_message, \
    UnexpectedWebhookEventType
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.models import UserProfile

def get_event_type(payload: Dict[str, Any]):
    return (payload['type'])

def get_topic_type(payload: Dict[str, Any]):

    if payload['type'] == "ticket_update":
        payload = payload['payload']
        payload = json.loads(payload)

        return payload['ticket']['summary']
    else:
        payload = payload['payload']
        payload = json.loads(payload)

        return payload['summary']

def ticket_creation(payload: Dict[str, Any], user_profile: UserProfile):

    payload = payload['payload']
    payload = json.loads(payload)

    type = payload['type']['name']
    name = payload['assignee']['name']
    category = payload['category']
    url = payload['url']

    body = "A ticket of **[{}]({})** type and category **{}** has been created by **{}**".format(type, url, category, name)

    return body

def ticket_update(payload: Dict[str, Any], user_profile: UserProfile):
    payload = payload['payload']
    payload = json.loads(payload)

    id = payload['ticket']['id']
    type = payload['ticket']['category']
    name = payload['user']['name']
    url = payload['ticket']['project']['url']

    body = "Ticket with ID **[{}]({})**, category **{}** has been updated by **{}**".format(id, url, type, name)

    return body

CODEBASE_EVENT_MAPPER = {
    "ticket_creation": ticket_creation,
    "ticket_update": ticket_update
}

@api_key_only_webhook_view('CodeBase')
@has_request_variables
def api_codebase_webhook(
        request: HttpRequest, user_profile: UserProfile,
        payload: Dict[str, Iterable[Dict[str, Any]]]=REQ(argument_type='body')
) -> HttpResponse:

    if payload is None:
        return json_success()

    event = get_event_type(payload)
    topic = get_topic_type(payload)

    if event is not None:
        body_func = CODEBASE_EVENT_MAPPER.get(event)

    if body_func is None:
        raise UnexpectedWebhookEventType('Cobdebase', event)

    body = body_func(payload, user_profile)  # type : str

    check_send_webhook_message(request, user_profile, topic, body)

    return json_success()
