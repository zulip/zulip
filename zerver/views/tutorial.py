from __future__ import absolute_import

from django.utils.translation import ugettext as _
from django.http import HttpRequest, HttpResponse

from zerver.decorator import authenticated_json_post_view, has_request_variables, REQ
from zerver.lib.actions import internal_send_message
from zerver.lib.response import json_error, json_success
from zerver.lib.validator import check_string
from zerver.models import UserProfile

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
        internal_send_message(sender_name, "stream", recipient, topic, content,
                              realm=user_profile.realm)
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

