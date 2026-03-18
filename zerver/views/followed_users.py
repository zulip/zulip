from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _

from zerver.actions.followed_users import do_follow_user, do_unfollow_user
from zerver.lib.exceptions import JsonableError
from zerver.lib.followed_users import get_follow_object
from zerver.lib.response import json_success
from zerver.lib.users import access_user_by_id
from zerver.models import UserProfile


def follow_user(
    request: HttpRequest,
    user_profile: UserProfile,
    followed_user_id: int,
) -> HttpResponse:
    if user_profile.id == followed_user_id:
        raise JsonableError(_("You cannot follow yourself."))

    followed_user = access_user_by_id(
        user_profile, followed_user_id, allow_deactivated=True, allow_bots=True, for_admin=False
    )
    if get_follow_object(user_profile, followed_user):
        raise JsonableError(_("User is already followed."))

    do_follow_user(user_profile, followed_user)
    return json_success(request)


def unfollow_user(
    request: HttpRequest,
    user_profile: UserProfile,
    followed_user_id: int,
) -> HttpResponse:
    followed_user = access_user_by_id(
        user_profile, followed_user_id, allow_deactivated=True, allow_bots=True, for_admin=False
    )

    if not get_follow_object(user_profile, followed_user):
        raise JsonableError(_("User is not followed."))

    do_unfollow_user(user_profile, followed_user)
    return json_success(request)
