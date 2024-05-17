from typing import Optional

from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _

from zerver.actions.reactions import check_add_reaction, do_remove_reaction
from zerver.lib.emoji import get_emoji_data
from zerver.lib.exceptions import JsonableError, ReactionDoesNotExistError
from zerver.lib.message import access_message
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint
from zerver.models import Reaction, UserProfile


# transaction.atomic is required since we use FOR UPDATE queries in access_message
@transaction.atomic
@typed_endpoint
def add_reaction(
    request: HttpRequest,
    user_profile: UserProfile,
    message_id: int,
    *,
    emoji_name: str,
    emoji_code: Optional[str] = None,
    reaction_type: Optional[str] = None,
) -> HttpResponse:
    check_add_reaction(user_profile, message_id, emoji_name, emoji_code, reaction_type)

    return json_success(request)


# transaction.atomic is required since we use FOR UPDATE queries in access_message
@transaction.atomic
@typed_endpoint
def remove_reaction(
    request: HttpRequest,
    user_profile: UserProfile,
    message_id: int,
    *,
    emoji_name: Optional[str] = None,
    emoji_code: Optional[str] = None,
    reaction_type: str = "unicode_emoji",
) -> HttpResponse:
    message = access_message(user_profile, message_id, lock_message=True)

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
        emoji_code = get_emoji_data(message.realm_id, emoji_name).emoji_code

    if not Reaction.objects.filter(
        user_profile=user_profile,
        message=message,
        emoji_code=emoji_code,
        reaction_type=reaction_type,
    ).exists():
        raise ReactionDoesNotExistError

    # Unlike adding reactions, while deleting a reaction, we don't
    # check whether the provided (emoji_type, emoji_code) pair is
    # valid in this realm.  Since there's a row in the database, we
    # know it was valid when the user added their reaction in the
    # first place, so it is safe to just remove the reaction if it
    # exists.  And the (reaction_type, emoji_code) pair may no longer be
    # valid in legitimate situations (e.g. if a realm emoji was
    # deactivated by an administrator in the meantime).
    do_remove_reaction(user_profile, message, emoji_code, reaction_type)

    return json_success(request)
