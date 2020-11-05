from typing import Optional

from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _

from zerver.decorator import REQ, has_request_variables
from zerver.lib.actions import check_add_reaction, do_remove_reaction
from zerver.lib.emoji import emoji_name_to_emoji_code
from zerver.lib.message import access_message
from zerver.lib.request import JsonableError
from zerver.lib.response import json_success
from zerver.models import Reaction, UserProfile


@has_request_variables
def add_reaction(
    request: HttpRequest,
    user_profile: UserProfile,
    message_id: int,
    emoji_name: str = REQ(),
    emoji_code: Optional[str] = REQ(default=None),
    reaction_type: Optional[str] = REQ(default=None),
) -> HttpResponse:
    check_add_reaction(user_profile, message_id, emoji_name, emoji_code, reaction_type)

    return json_success()


@has_request_variables
def remove_reaction(
    request: HttpRequest,
    user_profile: UserProfile,
    message_id: int,
    emoji_name: Optional[str] = REQ(default=None),
    emoji_code: Optional[str] = REQ(default=None),
    reaction_type: str = REQ(default="unicode_emoji"),
) -> HttpResponse:
    message, user_message = access_message(
        user_profile, message_id, lock_message=False, lock_usermessage=False
    )

    if emoji_code is None:
        if emoji_name is None:
            raise JsonableError(
                _(
                    "At least one of the following arguments "
                    "must be present: emoji_name, emoji_code"
                )
            )
        # A correct full Zulip client implementation should always
        # pass an emoji_code, because of the corner cases discussed in
        # the long block comments elsewhere in this file.  However, to
        # make it easy for simple API clients to use the reactions API
        # without needing the mapping between emoji names and codes,
        # we allow instead passing the emoji_name and looking up the
        # corresponding code using the current data.
        emoji_code = emoji_name_to_emoji_code(message.sender.realm, emoji_name)[0]

    if not Reaction.objects.filter(
        user_profile=user_profile,
        message=message,
        emoji_code=emoji_code,
        reaction_type=reaction_type,
    ).exists():
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
