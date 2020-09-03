"""Taiga integration for Zulip.

Tips for notification output:

*Text formatting*: if there has been a change of a property, the new
value should always be in bold; otherwise the subject of US/task
should be in bold.
"""
from typing import Any, Dict, List, Mapping, Optional, Tuple

from django.http import HttpRequest, HttpResponse

from zerver.decorator import api_key_only_webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile


@api_key_only_webhook_view('Taiga')
@has_request_variables
def api_taiga_webhook(request: HttpRequest, user_profile: UserProfile,
                      message: Dict[str, Any]=REQ(argument_type='body')) -> HttpResponse:
    parsed_events = parse_message(message)
    content_lines = []
    for event in parsed_events:
        content_lines.append(generate_content(event) + '\n')
    content = "".join(sorted(content_lines))
    topic = 'General'
    if message["data"].get("milestone") is not None:
        if message["data"]["milestone"].get("name") is not None:
            topic = message["data"]["milestone"]["name"]
    check_send_webhook_message(request, user_profile, topic, content)

    return json_success()

templates = {
    'epic': {
        'create': '[{user}]({user_link}) created epic {subject}.',
        'set_assigned_to': '[{user}]({user_link}) assigned epic {subject} to {new}.',
        'unset_assigned_to': '[{user}]({user_link}) unassigned epic {subject}.',
        'changed_assigned_to': '[{user}]({user_link}) reassigned epic {subject}'
        ' from {old} to {new}.',
        'blocked': '[{user}]({user_link}) blocked epic {subject}.',
        'unblocked': '[{user}]({user_link}) unblocked epic {subject}.',
        'changed_status': '[{user}]({user_link}) changed status of epic {subject}'
        ' from {old} to {new}.',
        'renamed': '[{user}]({user_link}) renamed epic from **{old}** to **{new}**.',
        'description_diff': '[{user}]({user_link}) updated description of epic {subject}.',
        'commented': '[{user}]({user_link}) commented on epic {subject}.',
        'delete': '[{user}]({user_link}) deleted epic {subject}.',
    },
    'relateduserstory': {
        'create': ('[{user}]({user_link}) added a related user story '
                   '{userstory_subject} to the epic {epic_subject}.'),
        'delete': ('[{user}]({user_link}) removed a related user story ' +
                   '{userstory_subject} from the epic {epic_subject}.'),
    },
    'userstory': {
        'create': '[{user}]({user_link}) created user story {subject}.',
        'set_assigned_to': '[{user}]({user_link}) assigned user story {subject} to {new}.',
        'unset_assigned_to': '[{user}]({user_link}) unassigned user story {subject}.',
        'changed_assigned_to': '[{user}]({user_link}) reassigned user story {subject}'
        ' from {old} to {new}.',
        'points': '[{user}]({user_link}) changed estimation of user story {subject}.',
        'blocked': '[{user}]({user_link}) blocked user story {subject}.',
        'unblocked': '[{user}]({user_link}) unblocked user story {subject}.',
        'set_milestone': '[{user}]({user_link}) added user story {subject} to sprint {new}.',
        'unset_milestone': '[{user}]({user_link}) removed user story {subject} from sprint {old}.',
        'changed_milestone': '[{user}]({user_link}) changed sprint of user story {subject} from {old}'
        ' to {new}.',
        'changed_status': '[{user}]({user_link}) changed status of user story {subject}'
        ' from {old} to {new}.',
        'closed': '[{user}]({user_link}) closed user story {subject}.',
        'reopened': '[{user}]({user_link}) reopened user story {subject}.',
        'renamed': '[{user}]({user_link}) renamed user story from {old} to **{new}**.',
        'description_diff': '[{user}]({user_link}) updated description of user story {subject}.',
        'commented': '[{user}]({user_link}) commented on user story {subject}.',
        'delete': '[{user}]({user_link}) deleted user story {subject}.',
        'due_date': '[{user}]({user_link}) changed due date of user story {subject}'
        ' from {old} to {new}.',
        'set_due_date': '[{user}]({user_link}) set due date of user story {subject}'
        ' to {new}.',
    },
    'milestone': {
        'create': '[{user}]({user_link}) created sprint {subject}.',
        'renamed': '[{user}]({user_link}) renamed sprint from {old} to **{new}**.',
        'estimated_start': '[{user}]({user_link}) changed estimated start of sprint {subject}'
        ' from {old} to {new}.',
        'estimated_finish': '[{user}]({user_link}) changed estimated finish of sprint {subject}'
        ' from {old} to {new}.',
        'set_estimated_start': '[{user}]({user_link}) changed estimated start of sprint {subject}'
        ' to {new}.',
        'set_estimated_finish': '[{user}]({user_link}) set estimated finish of sprint {subject}'
        ' to {new}.',
        'delete': '[{user}]({user_link}) deleted sprint {subject}.',
    },
    'task': {
        'create': '[{user}]({user_link}) created task {subject}.',
        'set_assigned_to': '[{user}]({user_link}) assigned task {subject} to {new}.',
        'unset_assigned_to': '[{user}]({user_link}) unassigned task {subject}.',
        'changed_assigned_to': '[{user}]({user_link}) reassigned task {subject}'
        ' from {old} to {new}.',
        'blocked': '[{user}]({user_link}) blocked task {subject}.',
        'unblocked': '[{user}]({user_link}) unblocked task {subject}.',
        'changed_status': '[{user}]({user_link}) changed status of task {subject}'
        ' from {old} to {new}.',
        'renamed': '[{user}]({user_link}) renamed task {old} to **{new}**.',
        'description_diff': '[{user}]({user_link}) updated description of task {subject}.',
        'set_milestone': '[{user}]({user_link}) added task {subject} to sprint {new}.',
        'commented': '[{user}]({user_link}) commented on task {subject}.',
        'delete': '[{user}]({user_link}) deleted task {subject}.',
        'changed_us': '[{user}]({user_link}) moved task {subject} from user story {old} to {new}.',
        'due_date': '[{user}]({user_link}) changed due date of task {subject}'
        ' from {old} to {new}.',
        'set_due_date': '[{user}]({user_link}) set due date of task {subject}'
        ' to {new}.',
    },
    'issue': {
        'create': '[{user}]({user_link}) created issue {subject}.',
        'set_assigned_to': '[{user}]({user_link}) assigned issue {subject} to {new}.',
        'unset_assigned_to': '[{user}]({user_link}) unassigned issue {subject}.',
        'changed_assigned_to': '[{user}]({user_link}) reassigned issue {subject}'
        ' from {old} to {new}.',
        'set_milestone': '[{user}]({user_link}) added issue {subject} to sprint {new}.',
        'unset_milestone': '[{user}]({user_link}) detached issue {subject} from sprint {old}.',
        'changed_priority': '[{user}]({user_link}) changed priority of issue '
                            '{subject} from {old} to {new}.',
        'changed_severity': '[{user}]({user_link}) changed severity of issue '
                            '{subject} from {old} to {new}.',
        'changed_status': '[{user}]({user_link}) changed status of issue {subject}'
                           ' from {old} to {new}.',
        'changed_type': '[{user}]({user_link}) changed type of issue {subject} from {old} to {new}.',
        'renamed': '[{user}]({user_link}) renamed issue {old} to **{new}**.',
        'description_diff': '[{user}]({user_link}) updated description of issue {subject}.',
        'commented': '[{user}]({user_link}) commented on issue {subject}.',
        'delete': '[{user}]({user_link}) deleted issue {subject}.',
        'due_date': '[{user}]({user_link}) changed due date of issue {subject}'
        ' from {old} to {new}.',
        'set_due_date': '[{user}]({user_link}) set due date of issue {subject}'
        ' to {new}.',
        'blocked': '[{user}]({user_link}) blocked issue {subject}.',
        'unblocked': '[{user}]({user_link}) unblocked issue {subject}.',
    },
    'webhook_test': {
        'test': '[{user}]({user_link}) triggered a test of the Taiga integration.',
    },
}


return_type = Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]
def get_old_and_new_values(change_type: str,
                           message: Mapping[str, Any]) -> return_type:
    """ Parses the payload and finds previous and current value of change_type."""
    old = message["change"]["diff"][change_type].get("from")
    new = message["change"]["diff"][change_type].get("to")
    return old, new


def parse_comment(message: Mapping[str, Any]) -> Dict[str, Any]:
    """ Parses the comment to issue, task or US. """
    return {
        'event': 'commented',
        'type': message["type"],
        'values': {
            'user': get_owner_name(message),
            'user_link': get_owner_link(message),
            'subject': get_subject(message),
        },
    }

def parse_create_or_delete(message: Mapping[str, Any]) -> Dict[str, Any]:
    """ Parses create or delete event. """
    if message["type"] == 'relateduserstory':
        return {
            'type': message["type"],
            'event': message["action"],
            'values': {
                'user': get_owner_name(message),
                'user_link': get_owner_link(message),
                'epic_subject': get_epic_subject(message),
                'userstory_subject': get_userstory_subject(message),
            },
        }

    return {
        'type': message["type"],
        'event': message["action"],
        'values': {
            'user': get_owner_name(message),
            'user_link': get_owner_link(message),
            'subject': get_subject(message),
        },
    }


def parse_change_event(change_type: str, message: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    """ Parses change event. """
    evt: Dict[str, Any] = {}
    values: Dict[str, Any] = {
        'user': get_owner_name(message),
        'user_link': get_owner_link(message),
        'subject': get_subject(message),
    }

    if change_type in ["description_diff", "points"]:
        event_type = change_type

    elif change_type in ["milestone", "assigned_to"]:
        old, new = get_old_and_new_values(change_type, message)
        if not old:
            event_type = "set_" + change_type
            values["new"] = new
        elif not new:
            event_type = "unset_" + change_type
            values["old"] = old
        else:
            event_type = "changed_" + change_type
            values.update(old=old, new=new)

    elif change_type == "is_blocked":
        if message["change"]["diff"]["is_blocked"]["to"]:
            event_type = "blocked"
        else:
            event_type = "unblocked"

    elif change_type == "is_closed":
        if message["change"]["diff"]["is_closed"]["to"]:
            event_type = "closed"
        else:
            event_type = "reopened"

    elif change_type == "user_story":
        old, new = get_old_and_new_values(change_type, message)
        event_type = "changed_us"
        values.update(old=old, new=new)

    elif change_type in ["subject", 'name']:
        event_type = 'renamed'
        old, new = get_old_and_new_values(change_type, message)
        values.update(old=old, new=new)

    elif change_type in ["estimated_finish", "estimated_start", "due_date"]:
        old, new = get_old_and_new_values(change_type, message)
        if not old:
            event_type = "set_" + change_type
            values["new"] = new
        elif not old == new:
            event_type = change_type
            values.update(old=old, new=new)
        else:
            # date hasn't changed
            return None

    elif change_type in ["priority", "severity", "type", "status"]:
        event_type = 'changed_' + change_type
        old, new = get_old_and_new_values(change_type, message)
        values.update(old=old, new=new)

    else:
        # we are not supporting this type of event
        return None

    evt.update(type=message["type"], event=event_type, values=values)
    return evt

def parse_webhook_test(message: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "type": "webhook_test",
        "event": "test",
        "values": {
            "user": get_owner_name(message),
            "user_link": get_owner_link(message),
            "end_type": "test",
        },
    }


def parse_message(message: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """ Parses the payload by delegating to specialized functions. """
    events = []
    if message["action"] in ['create', 'delete']:
        events.append(parse_create_or_delete(message))
    elif message["action"] == 'change':
        if message["change"]["diff"]:
            for value in message["change"]["diff"]:
                parsed_event = parse_change_event(value, message)
                if parsed_event:
                    events.append(parsed_event)
        if message["change"]["comment"]:
            events.append(parse_comment(message))
    elif message["action"] == "test":
        events.append(parse_webhook_test(message))

    return events

def generate_content(data: Mapping[str, Any]) -> str:
    """ Gets the template string and formats it with parsed data. """
    template = templates[data['type']][data['event']]
    content = template.format(**data['values'])
    return content

def get_owner_name(message: Mapping[str, Any]) -> str:
    return message["by"]["full_name"]

def get_owner_link(message: Mapping[str, Any]) -> str:
    return message['by']['permalink']

def get_subject(message: Mapping[str, Any]) -> str:
    data = message["data"]
    if 'permalink' in data:
        return '[' + data.get('subject', data.get('name')) + ']' + '(' + data['permalink'] + ')'
    return '**' + data.get('subject', data.get('name')) + '**'

def get_epic_subject(message: Mapping[str, Any]) -> str:
    if 'permalink' in message['data']['epic']:
        return ('[' + message['data']['epic']['subject'] + ']' +
                '(' + message['data']['epic']['permalink'] + ')')
    return '**' + message['data']['epic']['subject'] + '**'

def get_userstory_subject(message: Mapping[str, Any]) -> str:
    if 'permalink' in message['data']['user_story']:
        us_data = message['data']['user_story']
        return '[' + us_data['subject'] + ']' + '(' + us_data['permalink'] + ')'
    return '**' + message['data']['user_story']['subject'] + '**'
