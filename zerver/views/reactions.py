from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _
from six import text_type

from zerver.decorator import authenticated_json_post_view,\
    has_request_variables, REQ, to_non_negative_int
from zerver.lib.actions import do_add_reaction, do_remove_reaction
from zerver.lib.bugdown import emoji_list
from zerver.lib.message import access_message
from zerver.lib.request import JsonableError
from zerver.lib.response import json_success
from zerver.models import Reaction, UserProfile

@has_request_variables
def add_reaction_backend(request, user_profile, emoji_name=REQ('emoji'),
                         message_id = REQ('message_id', converter=to_non_negative_int)):
    # type: (HttpRequest, UserProfile, text_type, int) -> HttpResponse

    # access_message will throw a JsonableError exception if the user
    # cannot see the message (e.g. for messages to private streams).
    message = access_message(user_profile, message_id)[0]

    existing_emojis = set(message.sender.realm.get_emoji().keys()) or set(emoji_list)
    if emoji_name not in existing_emojis:
        raise JsonableError(_("Emoji '%s' does not exist" % (emoji_name,)))

    # We could probably just make this check be a try/except for the
    # IntegrityError from it already existing, but this is a bit cleaner.
    if Reaction.objects.filter(user_profile=user_profile,
                               message=message,
                               emoji_name=emoji_name).exists():
        raise JsonableError(_("Reaction already exists"))

    do_add_reaction(user_profile, message, emoji_name)

    return json_success()

@has_request_variables
def remove_reaction_backend(request, user_profile, emoji_name=REQ('emoji'),
                            message_id = REQ('message_id', converter=to_non_negative_int)):
    # type: (HttpRequest, UserProfile, text_type, int) -> HttpResponse

    # access_message will throw a JsonableError exception if the user
    # cannot see the message (e.g. for messages to private streams).
    message = access_message(user_profile, message_id)[0]

    existing_emojis = set(message.sender.realm.get_emoji().keys()) or set(emoji_list)
    if emoji_name not in existing_emojis:
        raise JsonableError(_("Emoji '%s' does not exist" % (emoji_name,)))

    # We could probably just make this check be a try/except for the
    # IntegrityError from it already existing, but this is a bit cleaner.
    if not Reaction.objects.filter(user_profile=user_profile,
                                   message=message,
                                   emoji_name=emoji_name).exists():
        raise JsonableError(_("Reaction does not exist"))

    do_remove_reaction(user_profile, message, emoji_name)

    return json_success()
