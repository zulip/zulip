from __future__ import absolute_import

from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _
from typing import Text

from zerver.decorator import authenticated_json_post_view,\
    has_request_variables, REQ, to_non_negative_int
from zerver.lib.actions import do_add_reaction, do_remove_reaction
from zerver.lib.emoji import check_valid_emoji
from zerver.lib.message import access_message
from zerver.lib.request import JsonableError
from zerver.lib.response import json_success
from zerver.models import Reaction, UserMessage, UserProfile

@has_request_variables
def add_reaction_backend(request, user_profile, message_id, emoji_name):
    # type: (HttpRequest, UserProfile, int, Text) -> HttpResponse

    # access_message will throw a JsonableError exception if the user
    # cannot see the message (e.g. for messages to private streams).
    message, user_message = access_message(user_profile, message_id)

    check_valid_emoji(message.sender.realm, emoji_name)

    # We could probably just make this check be a try/except for the
    # IntegrityError from it already existing, but this is a bit cleaner.
    if Reaction.objects.filter(user_profile=user_profile,
                               message=message,
                               emoji_name=emoji_name).exists():
        raise JsonableError(_("Reaction already exists"))

    if user_message is None:
        # Users can see and react to messages sent to streams they
        # were not a subscriber to; in order to receive events for
        # those, we give the user a `historical` UserMessage objects
        # for the message.  This is the same trick we use for starring
        # messages.
        UserMessage.objects.create(user_profile=user_profile,
                                   message=message,
                                   flags=UserMessage.flags.historical | UserMessage.flags.read)

    do_add_reaction(user_profile, message, emoji_name)

    return json_success()

@has_request_variables
def remove_reaction_backend(request, user_profile, message_id, emoji_name):
    # type: (HttpRequest, UserProfile, int, Text) -> HttpResponse

    # access_message will throw a JsonableError exception if the user
    # cannot see the message (e.g. for messages to private streams).
    message = access_message(user_profile, message_id)[0]

    check_valid_emoji(message.sender.realm, emoji_name)

    # We could probably just make this check be a try/except for the
    # IntegrityError from it already existing, but this is a bit cleaner.
    if not Reaction.objects.filter(user_profile=user_profile,
                                   message=message,
                                   emoji_name=emoji_name).exists():
        raise JsonableError(_("Reaction does not exist"))

    do_remove_reaction(user_profile, message, emoji_name)

    return json_success()
