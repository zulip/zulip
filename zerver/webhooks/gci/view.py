from typing import Any, Dict, Optional, Text

from django.http import HttpRequest, HttpResponse

from zerver.decorator import api_key_only_webhook_view
from zerver.lib.actions import check_send_stream_message
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.models import UserProfile

GCI_MESSAGE_TEMPLATE = u'**{actor}** {action} the task [{task_name}]({task_url}).'
GCI_SUBJECT_TEMPLATE = u'{student_name}'


def build_instance_url(instance_id: str) -> str:
    return "https://codein.withgoogle.com/dashboard/task-instances/{}/".format(instance_id)

class UnknownEventType(Exception):
    pass

def get_abandon_event_body(payload: Dict[Text, Any]) -> Text:
    return GCI_MESSAGE_TEMPLATE.format(
        actor=payload['task_claimed_by'],
        action='{}ed'.format(payload['event_type']),
        task_name=payload['task_definition_name'],
        task_url=build_instance_url(payload['task_instance']),
    )

def get_submit_event_body(payload: Dict[Text, Any]) -> Text:
    return GCI_MESSAGE_TEMPLATE.format(
        actor=payload['task_claimed_by'],
        action='{}ted'.format(payload['event_type']),
        task_name=payload['task_definition_name'],
        task_url=build_instance_url(payload['task_instance']),
    )

def get_comment_event_body(payload: Dict[Text, Any]) -> Text:
    return GCI_MESSAGE_TEMPLATE.format(
        actor=payload['author'],
        action='{}ed on'.format(payload['event_type']),
        task_name=payload['task_definition_name'],
        task_url=build_instance_url(payload['task_instance']),
    )

def get_claim_event_body(payload: Dict[Text, Any]) -> Text:
    return GCI_MESSAGE_TEMPLATE.format(
        actor=payload['task_claimed_by'],
        action='{}ed'.format(payload['event_type']),
        task_name=payload['task_definition_name'],
        task_url=build_instance_url(payload['task_instance']),
    )

def get_approve_event_body(payload: Dict[Text, Any]) -> Text:
    return GCI_MESSAGE_TEMPLATE.format(
        actor=payload['author'],
        action='{}d'.format(payload['event_type']),
        task_name=payload['task_definition_name'],
        task_url=build_instance_url(payload['task_instance']),
    )

def get_needswork_event_body(payload: Dict[Text, Any]) -> Text:
    template = "{} for more work.".format(GCI_MESSAGE_TEMPLATE.rstrip('.'))
    return template.format(
        actor=payload['author'],
        action='submitted',
        task_name=payload['task_definition_name'],
        task_url=build_instance_url(payload['task_instance']),
    )

@api_key_only_webhook_view("Google-Code-In")
@has_request_variables
def api_gci_webhook(request, user_profile, stream=REQ(default='gci'),
                    payload=REQ(argument_type='body')):
    # type: (HttpRequest, UserProfile, Text, Dict[Text, Any]) -> HttpResponse
    event = get_event(payload)
    if event is not None:
        body = get_body_based_on_event(event)(payload)
        subject = GCI_SUBJECT_TEMPLATE.format(
            student_name=payload['task_claimed_by']
        )
        check_send_stream_message(user_profile, request.client,
                                  stream, subject, body)

    return json_success()

EVENTS_FUNCTION_MAPPER = {
    'abandon': get_abandon_event_body,
    'approve': get_approve_event_body,
    'claim': get_claim_event_body,
    'comment': get_comment_event_body,
    'needswork': get_needswork_event_body,
    'submit': get_submit_event_body,
}

def get_event(payload: Dict[Text, Any]) -> Optional[Text]:
    event = payload['event_type']
    if event in EVENTS_FUNCTION_MAPPER:
        return event

    raise UnknownEventType(u"Event '{}' is unknown and cannot be handled".format(event))  # nocoverage

def get_body_based_on_event(event: Text) -> Any:
    return EVENTS_FUNCTION_MAPPER[event]
