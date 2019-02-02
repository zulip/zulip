import re
from typing import Any, Dict

from django.http import HttpRequest, HttpResponse

from zerver.decorator import api_key_only_webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message, \
    UnexpectedWebhookEventType
from zerver.models import UserProfile

from .support_event import SUPPORT_EVENTS

DOCUMENT_TEMPLATE = "{user_name} {verb} the document [{title}]({url})"
QUESTION_TEMPLATE = "{user_name} {verb} the question [{title}]({url})"
QUESTIONS_ANSWER_TEMPLATE = ("{user_name} {verb} the [answer]({answer_url}) " +
                             "of the question [{question_title}]({question_url})")
COMMENT_TEMPLATE = ("{user_name} {verb} the [comment]({answer_url}) "
                    "of the task [{task_title}]({task_url})")
MESSAGE_TEMPLATE = "{user_name} {verb} the message [{title}]({url})"
TODO_LIST_TEMPLATE = "{user_name} {verb} the todo list [{title}]({url})"
TODO_TEMPLATE = "{user_name} {verb} the todo task [{title}]({url})"

@api_key_only_webhook_view('Basecamp')
@has_request_variables
def api_basecamp_webhook(request: HttpRequest, user_profile: UserProfile,
                         payload: Dict[str, Any]=REQ(argument_type='body')) -> HttpResponse:
    event = get_event_type(payload)

    if event not in SUPPORT_EVENTS:
        raise UnexpectedWebhookEventType('Basecamp', event)

    subject = get_project_name(payload)
    if event.startswith('document_'):
        body = get_document_body(event, payload)
    elif event.startswith('question_answer_'):
        body = get_questions_answer_body(event, payload)
    elif event.startswith('question_'):
        body = get_questions_body(event, payload)
    elif event.startswith('message_'):
        body = get_message_body(event, payload)
    elif event.startswith('todolist_'):
        body = get_todo_list_body(event, payload)
    elif event.startswith('todo_'):
        body = get_todo_body(event, payload)
    elif event.startswith('comment_'):
        body = get_comment_body(event, payload)
    else:
        raise UnexpectedWebhookEventType('Basecamp', event)

    check_send_webhook_message(request, user_profile, subject, body)
    return json_success()

def get_project_name(payload: Dict[str, Any]) -> str:
    return payload['recording']['bucket']['name']

def get_event_type(payload: Dict[str, Any]) -> str:
    return payload['kind']

def get_event_creator(payload: Dict[str, Any]) -> str:
    return payload['creator']['name']

def get_subject_url(payload: Dict[str, Any]) -> str:
    return payload['recording']['app_url']

def get_subject_title(payload: Dict[str, Any]) -> str:
    return payload['recording']['title']

def get_verb(event: str, prefix: str) -> str:
    verb = event.replace(prefix, '')
    if verb == 'active':
        return 'activated'

    matched = re.match(r"(?P<subject>[A-z]*)_changed", verb)
    if matched:
        return "changed {} of".format(matched.group('subject'))
    return verb

def get_document_body(event: str, payload: Dict[str, Any]) -> str:
    return get_generic_body(event, payload, 'document_', DOCUMENT_TEMPLATE)

def get_questions_answer_body(event: str, payload: Dict[str, Any]) -> str:
    verb = get_verb(event, 'question_answer_')
    question = payload['recording']['parent']

    return QUESTIONS_ANSWER_TEMPLATE.format(
        user_name=get_event_creator(payload),
        verb=verb,
        answer_url=get_subject_url(payload),
        question_title=question['title'],
        question_url=question['app_url']
    )

def get_comment_body(event: str, payload: Dict[str, Any]) -> str:
    verb = get_verb(event, 'comment_')
    task = payload['recording']['parent']

    return COMMENT_TEMPLATE.format(
        user_name=get_event_creator(payload),
        verb=verb,
        answer_url=get_subject_url(payload),
        task_title=task['title'],
        task_url=task['app_url']
    )

def get_questions_body(event: str, payload: Dict[str, Any]) -> str:
    return get_generic_body(event, payload, 'question_', QUESTION_TEMPLATE)

def get_message_body(event: str, payload: Dict[str, Any]) -> str:
    return get_generic_body(event, payload, 'message_', MESSAGE_TEMPLATE)

def get_todo_list_body(event: str, payload: Dict[str, Any]) -> str:
    return get_generic_body(event, payload, 'todolist_', TODO_LIST_TEMPLATE)

def get_todo_body(event: str, payload: Dict[str, Any]) -> str:
    return get_generic_body(event, payload, 'todo_', TODO_TEMPLATE)

def get_generic_body(event: str, payload: Dict[str, Any], prefix: str, template: str) -> str:
    verb = get_verb(event, prefix)

    return template.format(
        user_name=get_event_creator(payload),
        verb=verb,
        title=get_subject_title(payload),
        url=get_subject_url(payload),
    )
