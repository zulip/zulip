from __future__ import absolute_import
from typing import Dict, Any, Text

from django.utils.translation import ugettext as _
from django.http import HttpRequest, HttpResponse

from zerver.decorator import authenticated_json_post_view, has_request_variables, REQ
from zerver.lib.actions import internal_send_message, get_next_tutorial_pieces, do_update_tutorial_state
from zerver.lib.response import json_error, json_success
from zerver.lib.validator import check_string
from zerver.models import UserProfile
import ujson

@authenticated_json_post_view
@has_request_variables
def json_tutorial_send_message(request, user_profile, type=REQ(validator=check_string),
                               recipient=REQ(validator=check_string), topic=REQ(validator=check_string),
                               content=REQ(validator=check_string)):
    # type: (HttpRequest, UserProfile, str, str, str, str) -> HttpResponse
    """
    This function, used by the onboarding tutorial, causes the Tutorial Bot to
    send you the message you pass in here. (That way, the Tutorial Bot's
    messages to you get rendered by the server and therefore look like any other
    message.)
    """
    sender_name = "welcome-bot@zulip.com"
    if type == 'stream':
        internal_send_message(user_profile.realm, sender_name,
                              "stream", recipient, topic, content)
        return json_success()
    # For now, there are no PM cases.
    return json_error(_('Bad data passed in to tutorial_send_message'))

@authenticated_json_post_view
@has_request_variables
def json_tutorial_status(request, user_profile,
                         status=REQ(validator=check_string)):
    # type: (HttpRequest, UserProfile, str) -> HttpResponse
    if status == 'started':
        user_profile.tutorial_status = UserProfile.TUTORIAL_STARTED
    elif status == 'finished':
        user_profile.tutorial_status = UserProfile.TUTORIAL_FINISHED
    user_profile.save(update_fields=["tutorial_status"])

    return json_success()

@has_request_variables
def next_tutorial_pieces(request, user_profile):
    # type: (HttpRequest, UserProfile) -> HttpResponse
    next_pieces = get_next_tutorial_pieces(user_profile)
    return json_success({"next_pieces": next_pieces})

@has_request_variables
def update_tutorial_state(request, user_profile, update_dict=REQ()):
    # type: (HttpRequest, UserProfile, Any) -> HttpResponse
    ALL_FLAGS = ['welcome', 'streams', 'topics', 'narrowing', 'replying', 'get_started']
    update_dict = ujson.loads(update_dict)
    for tutorial_piece, value in update_dict.items():
        if not isinstance(value, bool) or str(tutorial_piece) not in ALL_FLAGS:
            return json_error(_('Tutorial update flags must be in ALL_FLAGS and have bool values'))
    next_pieces = do_update_tutorial_state(user_profile, update_dict)
    return json_success({"next_pieces": next_pieces})

@has_request_variables
def restart_tutorial(request, user_profile):
    # type: (HttpRequest, UserProfile) -> HttpResponse
    restart_dict = {'welcome': False, 'streams': False, 'topics': False, 'narrowing': False, 'replying': False, 'get_started': False}
    do_update_tutorial_state(user_profile, restart_dict)
    return json_success()
