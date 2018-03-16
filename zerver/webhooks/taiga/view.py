"""Taiga integration for Zulip.

Tips for notification output:

*Emojis*: most of the events have specific emojis e.g.
- :notebook: - change of subject/name/description
- :chart_with_upwards_trend: - change of status
etc. If no there's no meaningful emoji for certain event, the defaults are used:
- :thought_balloon: - event connected to commenting
- :busts_in_silhouette: - event connected to a certain user
- :package: - all other events connected to user story
- :calendar: - all other events connected to milestones
- :clipboard: - all other events connected to tasks
- :bulb: - all other events connected to issues

*Text formatting*: if there has been a change of a property, the new
value should always be in bold; otherwise the subject of US/task
should be in bold.
"""

from typing import Any, Dict, List, Mapping, Optional, Text, Tuple

import ujson
from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _

from zerver.decorator import api_key_only_webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_error, json_success
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
        'create': u':package: %(user)s created epic **%(subject)s**',
        'set_assigned_to': u':busts_in_silhouette: %(user)s assigned epic **%(subject)s** to %(new)s.',
        'unset_assigned_to': u':busts_in_silhouette: %(user)s unassigned epic **%(subject)s**',
        'changed_assigned_to': u':busts_in_silhouette: %(user)s reassigned epic **%(subject)s**'
        ' from %(old)s to %(new)s.',
        'blocked': u':lock: %(user)s blocked epic **%(subject)s**',
        'unblocked': u':unlock: %(user)s unblocked epic **%(subject)s**',
        'changed_status': u':chart_increasing: %(user)s changed status of epic **%(subject)s**'
        ' from %(old)s to %(new)s.',
        'renamed': u':notebook: %(user)s renamed epic from **%(old)s** to **%(new)s**',
        'description_diff': u':notebook: %(user)s updated description of epic **%(subject)s**',
        'commented': u':thought_balloon: %(user)s commented on epic **%(subject)s**',
        'delete': u':cross_mark: %(user)s deleted epic **%(subject)s**',
    },
    'relateduserstory': {
        'create': (u':package: %(user)s added a related user story '
                   u'**%(userstory_subject)s** to the epic **%(epic_subject)s**'),
        'delete': (u':cross_mark: %(user)s removed a related user story ' +
                   u'**%(userstory_subject)s** from the epic **%(epic_subject)s**'),
    },
    'userstory': {
        'create': u':package: %(user)s created user story **%(subject)s**.',
        'set_assigned_to': u':busts_in_silhouette: %(user)s assigned user story **%(subject)s** to %(new)s.',
        'unset_assigned_to': u':busts_in_silhouette: %(user)s unassigned user story **%(subject)s**.',
        'changed_assigned_to': u':busts_in_silhouette: %(user)s reassigned user story **%(subject)s**'
        ' from %(old)s to %(new)s.',
        'points': u':game_die: %(user)s changed estimation of user story **%(subject)s**.',
        'blocked': u':lock: %(user)s blocked user story **%(subject)s**.',
        'unblocked': u':unlock: %(user)s unblocked user story **%(subject)s**.',
        'set_milestone': u':calendar: %(user)s added user story **%(subject)s** to sprint %(new)s.',
        'unset_milestone': u':calendar: %(user)s removed user story **%(subject)s** from sprint %(old)s.',
        'changed_milestone': u':calendar: %(user)s changed sprint of user story **%(subject)s** from %(old)s'
        ' to %(new)s.',
        'changed_status': u':chart_with_upwards_trend: %(user)s changed status of user story **%(subject)s**'
        ' from %(old)s to %(new)s.',
        'closed': u':checkered_flag: %(user)s closed user story **%(subject)s**.',
        'reopened': u':package: %(user)s reopened user story **%(subject)s**.',
        'renamed': u':notebook: %(user)s renamed user story from %(old)s to **%(new)s**.',
        'description_diff': u':notebook: %(user)s updated description of user story **%(subject)s**.',
        'commented': u':thought_balloon: %(user)s commented on user story **%(subject)s**.',
        'delete': u':x: %(user)s deleted user story **%(subject)s**.'
    },
    'milestone': {
        'create': u':calendar: %(user)s created sprint **%(subject)s**.',
        'renamed': u':notebook: %(user)s renamed sprint from %(old)s to **%(new)s**.',
        'estimated_start': u':calendar: %(user)s changed estimated start of sprint **%(subject)s**'
        ' from %(old)s to %(new)s.',
        'estimated_finish': u':calendar: %(user)s changed estimated finish of sprint **%(subject)s**'
        ' from %(old)s to %(new)s.',
        'delete': u':x: %(user)s deleted sprint **%(subject)s**.'
    },
    'task': {
        'create': u':clipboard: %(user)s created task **%(subject)s**.',
        'set_assigned_to': u':busts_in_silhouette: %(user)s assigned task **%(subject)s** to %(new)s.',
        'unset_assigned_to': u':busts_in_silhouette: %(user)s unassigned task **%(subject)s**.',
        'changed_assigned_to': u':busts_in_silhouette: %(user)s reassigned task **%(subject)s**'
        ' from %(old)s to %(new)s.',
        'blocked': u':lock: %(user)s blocked task **%(subject)s**.',
        'unblocked': u':unlock: %(user)s unblocked task **%(subject)s**.',
        'set_milestone': u':calendar: %(user)s added task **%(subject)s** to sprint %(new)s.',
        'changed_milestone': u':calendar: %(user)s changed sprint of task '
                             '**%(subject)s** from %(old)s to %(new)s.',
        'changed_status': u':chart_with_upwards_trend: %(user)s changed status of task **%(subject)s**'
        ' from %(old)s to %(new)s.',
        'renamed': u':notebook: %(user)s renamed task %(old)s to **%(new)s**.',
        'description_diff': u':notebook: %(user)s updated description of task **%(subject)s**.',
        'commented': u':thought_balloon: %(user)s commented on task **%(subject)s**.',
        'delete': u':x: %(user)s deleted task **%(subject)s**.',
        'changed_us': u':clipboard: %(user)s moved task **%(subject)s** from user story %(old)s to %(new)s.'
    },
    'issue': {
        'create': u':bulb: %(user)s created issue **%(subject)s**.',
        'set_assigned_to': u':busts_in_silhouette: %(user)s assigned issue **%(subject)s** to %(new)s.',
        'unset_assigned_to': u':busts_in_silhouette: %(user)s unassigned issue **%(subject)s**.',
        'changed_assigned_to': u':busts_in_silhouette: %(user)s reassigned issue **%(subject)s**'
        ' from %(old)s to %(new)s.',
        'changed_priority': u':rocket: %(user)s changed priority of issue '
                            '**%(subject)s** from %(old)s to %(new)s.',
        'changed_severity': u':warning: %(user)s changed severity of issue '
                            '**%(subject)s** from %(old)s to %(new)s.',
        'changed_status': u':chart_with_upwards_trend: %(user)s changed status of issue **%(subject)s**'
                           ' from %(old)s to %(new)s.',
        'changed_type': u':bulb: %(user)s changed type of issue **%(subject)s** from %(old)s to %(new)s.',
        'renamed': u':notebook: %(user)s renamed issue %(old)s to **%(new)s**.',
        'description_diff': u':notebook: %(user)s updated description of issue **%(subject)s**.',
        'commented': u':thought_balloon: %(user)s commented on issue **%(subject)s**.',
        'delete': u':x: %(user)s deleted issue **%(subject)s**.'
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

    try:
        old = message["change"]["diff"][change_type]["from"]
    except KeyError:
        old = None

    try:
        new = message["change"]["diff"][change_type]["to"]
    except KeyError:
        new = None

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

    return events

def generate_content(data: Mapping[str, Any]) -> str:
    """ Gets the template string and formats it with parsed data. """
    return templates[data['type']][data['event']] % data['values']

def get_owner_name(message: Mapping[str, Any]) -> str:
    return message["by"]["full_name"]

def get_subject(message: Mapping[str, Any]) -> str:
    data = message["data"]
    return data.get("subject", data.get("name"))
