from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _

from zerver.decorator import \
    has_request_variables, REQ
from zerver.lib.actions import do_add_reaction, do_add_reaction_legacy, \
    do_remove_reaction, do_remove_reaction_legacy
from zerver.lib.emoji import check_emoji_request, check_valid_emoji, \
    emoji_name_to_emoji_code
from zerver.lib.message import access_message
from zerver.lib.request import JsonableError
from zerver.lib.response import json_success
from zerver.models import Message, Reaction, UserMessage, UserProfile

from typing import Optional

def create_historical_message(user_profile: UserProfile, message: Message) -> None:
    # Users can see and react to messages sent to streams they
    # were not a subscriber to; in order to receive events for
    # those, we give the user a `historical` UserMessage objects
    # for the message.  This is the same trick we use for starring
    # messages.
    UserMessage.objects.create(user_profile=user_profile,
                               message=message,
                               flags=UserMessage.flags.historical | UserMessage.flags.read)

@has_request_variables
def add_reaction(request: HttpRequest, user_profile: UserProfile, message_id: int,
                 emoji_name: str=REQ(),
                 emoji_code: Optional[str]=REQ(default=None),
                 reaction_type: str=REQ(default="unicode_emoji")) -> HttpResponse:
    message, user_message = access_message(user_profile, message_id)

    if emoji_code is None:
        # The emoji_code argument is only required for rare corner
        # cases discussed in the long block comment below.  For simple
        # API clients, we allow specifying just the name, and just
        # look up the code using the current name->code mapping.
        emoji_code = emoji_name_to_emoji_code(message.sender.realm,
                                              emoji_name)[0]

    if Reaction.objects.filter(user_profile=user_profile,
                               message=message,
                               emoji_code=emoji_code,
                               reaction_type=reaction_type).exists():
        raise JsonableError(_("Reaction already exists."))

    query = Reaction.objects.filter(message=message,
                                    emoji_code=emoji_code,
                                    reaction_type=reaction_type)
    if query.exists():
        # If another user has already reacted to this message with
        # same emoji code, we treat the new reaction as a vote for the
        # existing reaction.  So the emoji name used by that earlier
        # reaction takes precendence over whatever was passed in this
        # request.  This is necessary to avoid a message having 2
        # "different" emoji reactions with the same emoji code (and
        # thus same image) on the same message, which looks ugly.
        #
        # In this "voting for an existing reaction" case, we shouldn't
        # check whether the emoji code and emoji name match, since
        # it's possible that the (emoji_type, emoji_name, emoji_code)
        # triple for this existing rection xmay not pass validation
        # now (e.g. because it is for a realm emoji that has been
        # since deactivated).  We still want to allow users to add a
        # vote any old reaction they see in the UI even if that is a
        # deactivated custom emoji, so we just use the emoji name from
        # the existing reaction with no further validation.
        emoji_name = query.first().emoji_name
    else:
        # Otherwise, use the name provided in this request, but verify
        # it is valid in the user's realm (e.g. not a deactivated
        # realm emoji).
        check_emoji_request(message.sender.realm, emoji_name,
                            emoji_code, reaction_type)

    if user_message is None:
        create_historical_message(user_profile, message)

    do_add_reaction(user_profile, message, emoji_name, emoji_code, reaction_type)

    return json_success()

@has_request_variables
def remove_reaction(request: HttpRequest, user_profile: UserProfile, message_id: int,
                    emoji_name: Optional[str]=REQ(default=None),
                    emoji_code: Optional[str]=REQ(default=None),
                    reaction_type: str=REQ(default="unicode_emoji")) -> HttpResponse:
    message, user_message = access_message(user_profile, message_id)

    if emoji_code is None:
        if emoji_name is None:
            raise JsonableError(_('At least one of the following arguments '
                                  'must be present: emoji_name, emoji_code'))
        # A correct full Zulip client implementation should always
        # pass an emoji_code, because of the corner cases discussed in
        # the long block comments elsewhere in this file.  However, to
        # make it easy for simple API clients to use the reactions API
        # without needing the mapping between emoji names and codes,
        # we allow instead passing the emoji_name and looking up the
        # corresponding code using the current data.
        emoji_code = emoji_name_to_emoji_code(message.sender.realm, emoji_name)[0]

    if not Reaction.objects.filter(user_profile=user_profile,
                                   message=message,
                                   emoji_code=emoji_code,
                                   reaction_type=reaction_type).exists():
        raise JsonableError(_("Reaction doesn't exist."))

    # Unlike adding reactions, while deleting a reaction, we don't
    # check whether the provided (emoji_type, emoji_code) pair is
    # valid in this realm.  Since there's a row in the database, we
    # know it was valid when the user added their reaction in the
    # first place, so it is safe to just remove the reaction if it
    # exists.  And the (reaction_type, emoji_code) pair may no longer be
    # valid in legitimate situations (e.g. if a realm emoji was
    # deactivated by an administrator in the meantime).
    do_remove_reaction(user_profile, message, emoji_code, reaction_type)

    return json_success()

@has_request_variables
def add_reaction_legacy(request: HttpRequest, user_profile: UserProfile,
                        message_id: int, emoji_name: str) -> HttpResponse:

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
        create_historical_message(user_profile, message)

    do_add_reaction_legacy(user_profile, message, emoji_name)

    return json_success()

@has_request_variables
def remove_reaction_legacy(request: HttpRequest, user_profile: UserProfile,
                           message_id: int, emoji_name: str) -> HttpResponse:

    # access_message will throw a JsonableError exception if the user
    # cannot see the message (e.g. for messages to private streams).
    message = access_message(user_profile, message_id)[0]

    # We could probably just make this check be a try/except for the
    # IntegrityError from it already existing, but this is a bit cleaner.
    if not Reaction.objects.filter(user_profile=user_profile,
                                   message=message,
                                   emoji_name=emoji_name).exists():
        raise JsonableError(_("Reaction does not exist"))

    do_remove_reaction_legacy(user_profile, message, emoji_name)

    return json_success()
