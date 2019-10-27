"""Taiga integration for Zulip.

Tips for notification output:

*Text formatting*: if there has been a change of a property, the new
value should always be in bold; otherwise the subject of US/task
should be in bold.
"""

from typing import Any, Dict, List, Mapping, Optional, Tuple
import string

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

    check_send_webhook_message(request, user_profile, topic, content)

    return json_success()

templates = {
    'epic': {
        'create': u'{user} created epic **{subject}**.',
        'set_assigned_to': u'{user} assigned epic **{subject}** to {new}.',
        'unset_assigned_to': u'{user} unassigned epic **{subject}**.',
        'changed_assigned_to': u'{user} reassigned epic **{subject}**'
        ' from {old} to {new}.',
        'blocked': u'{user} blocked epic **{subject}**.',
        'unblocked': u'{user} unblocked epic **{subject}**.',
        'changed_status': u'{user} changed status of epic **{subject}**'
        ' from {old} to {new}.',
        'renamed': u'{user} renamed epic from **{old}** to **{new}**.',
        'description_diff': u'{user} updated description of epic **{subject}**.',
        'commented': u'{user} commented on epic **{subject}**.',
        'delete': u'{user} deleted epic **{subject}**.',
    },
    'relateduserstory': {
        'create': (u'{user} added a related user story '
                   u'**{userstory_subject}** to the epic **{epic_subject}**.'),
        'delete': (u'{user} removed a related user story ' +
                   u'**{userstory_subject}** from the epic **{epic_subject}**.'),
    },
    'userstory': {
        'create': u'{user} created user story **{subject}**.',
        'set_assigned_to': u'{user} assigned user story **{subject}** to {new}.',
        'unset_assigned_to': u'{user} unassigned user story **{subject}**.',
        'changed_assigned_to': u'{user} reassigned user story **{subject}**'
        ' from {old} to {new}.',
        'points': u'{user} changed estimation of user story **{subject}**.',
        'blocked': u'{user} blocked user story **{subject}**.',
        'unblocked': u'{user} unblocked user story **{subject}**.',
        'set_milestone': u'{user} added user story **{subject}** to sprint {new}.',
        'unset_milestone': u'{user} removed user story **{subject}** from sprint {old}.',
        'changed_milestone': u'{user} changed sprint of user story **{subject}** from {old}'
        ' to {new}.',
        'changed_status': u'{user} changed status of user story **{subject}**'
        ' from {old} to {new}.',
        'closed': u'{user} closed user story **{subject}**.',
        'reopened': u'{user} reopened user story **{subject}**.',
        'renamed': u'{user} renamed user story from {old} to **{new}**.',
        'description_diff': u'{user} updated description of user story **{subject}**.',
        'commented': u'{user} commented on user story **{subject}**.',
        'delete': u'{user} deleted user story **{subject}**.'
    },
    'milestone': {
        'create': u'{user} created sprint **{subject}**.',
        'renamed': u'{user} renamed sprint from {old} to **{new}**.',
        'estimated_start': u'{user} changed estimated start of sprint **{subject}**'
        ' from {old} to {new}.',
        'estimated_finish': u'{user} changed estimated finish of sprint **{subject}**'
        ' from {old} to {new}.',
        'delete': u'{user} deleted sprint **{subject}**.'
    },
    'task': {
        'create': u'{user} created task **{subject}**.',
        'set_assigned_to': u'{user} assigned task **{subject}** to {new}.',
        'unset_assigned_to': u'{user} unassigned task **{subject}**.',
        'changed_assigned_to': u'{user} reassigned task **{subject}**'
        ' from {old} to {new}.',
        'blocked': u'{user} blocked task **{subject}**.',
        'unblocked': u'{user} unblocked task **{subject}**.',
        'set_milestone': u'{user} added task **{subject}** to sprint {new}.',
        'changed_milestone': u'{user} changed sprint of task '
                             '**{subject}** from {old} to {new}.',
        'changed_status': u'{user} changed status of task **{subject}**'
        ' from {old} to {new}.',
        'renamed': u'{user} renamed task {old} to **{new}**.',
        'description_diff': u'{user} updated description of task **{subject}**.',
        'commented': u'{user} commented on task **{subject}**.',
        'delete': u'{user} deleted task **{subject}**.',
        'changed_us': u'{user} moved task **{subject}** from user story {old} to {new}.'
    },
    'issue': {
        'create': u'{user} created issue **{subject}**.',
        'set_assigned_to': u'{user} assigned issue **{subject}** to {new}.',
        'unset_assigned_to': u'{user} unassigned issue **{subject}**.',
        'changed_assigned_to': u'{user} reassigned issue **{subject}**'
        ' from {old} to {new}.',
        'changed_priority': u'{user} changed priority of issue '
                            '**{subject}** from {old} to {new}.',
        'changed_severity': u'{user} changed severity of issue '
                            '**{subject}** from {old} to {new}.',
        'changed_status': u'{user} changed status of issue **{subject}**'
                           ' from {old} to {new}.',
        'changed_type': u'{user} changed type of issue **{subject}** from {old} to {new}.',
        'renamed': u'{user} renamed issue {old} to **{new}**.',
        'description_diff': u'{user} updated description of issue **{subject}**.',
        'commented': u'{user} commented on issue **{subject}**.',
        'delete': u'{user} deleted issue **{subject}**.'
    },
    'webhook_test': {
        'test': u'{user} triggered a test of the Taiga integration.'
    },
}


return_type = Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]
def get_old_and_new_values(change_type: str,
                           message: Mapping[str, Any]) -> return_type:
    """ Parses the payload and finds previous and current value of change_type."""
    if change_type in ['subject', 'name', 'estimated_finish', 'estimated_start']:
        old = message["change"]["diff"][change_type]["from"]
        new = message["change"]["diff"][change_type]["to"]
        return old, new

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
            'subject': get_subject(message)
        }
    }

def parse_create_or_delete(message: Mapping[str, Any]) -> Dict[str, Any]:
    """ Parses create or delete event. """
    if message["type"] == 'relateduserstory':
        return {
            'type': message["type"],
            'event': message["action"],
            'values': {
                'user': get_owner_name(message),
                'epic_subject': message['data']['epic']['subject'],
                'userstory_subject': message['data']['user_story']['subject'],
            }
        }

    return {
        'type': message["type"],
        'event': message["action"],
        'values': {
            'user': get_owner_name(message),
            'subject': get_subject(message)
        }
    }


def parse_change_event(change_type: str, message: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    """ Parses change event. """
    evt = {}  # type: Dict[str, Any]
    values = {
        'user': get_owner_name(message),
        'subject': get_subject(message)
    }  # type: Dict[str, Any]

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
            values.update({'old': old, 'new': new})

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
        values.update({'old': old, 'new': new})

    elif change_type in ["subject", 'name']:
        event_type = 'renamed'
        old, new = get_old_and_new_values(change_type, message)
        values.update({'old': old, 'new': new})

    elif change_type in ["estimated_finish", "estimated_start"]:
        old, new = get_old_and_new_values(change_type, message)
        if not old == new:
            event_type = change_type
            values.update({'old': old, 'new': new})
        else:
            # date hasn't changed
            return None

    elif change_type in ["priority", "severity", "type", "status"]:
        event_type = 'changed_' + change_type
        old, new = get_old_and_new_values(change_type, message)
        values.update({'old': old, 'new': new})

    else:
        # we are not supporting this type of event
        return None

    evt.update({"type": message["type"], "event": event_type, "values": values})
    return evt

def parse_webhook_test(message: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "type": "webhook_test",
        "event": "test",
        "values": {
            "user": get_owner_name(message),
            "end_type": "test"
        }
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
    end_type = 'end_type'
    if template.endswith('{subject}**.'):
        end_type = 'subject'
    elif template.endswith('{epic_subject}**.'):
        end_type = 'epic_subject'
    elif template.endswith('{new}.') or template.endswith('{new}**.'):
        end_type = 'new'
    elif template.endswith('{old}.') or template.endswith('{old}**.'):
        end_type = 'old'
    end = data['values'].get(end_type)

    if end[-1] in string.punctuation:
        content = content[:-1]

    return content

def get_owner_name(message: Mapping[str, Any]) -> str:
    return message["by"]["full_name"]

def get_subject(message: Mapping[str, Any]) -> str:
    data = message["data"]
    return data.get("subject", data.get("name"))
