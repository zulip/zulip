from django.db import IntegrityError
from django.http import HttpRequest, HttpResponse
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _

from zerver.actions.muted_users import do_mute_user, do_unmute_user
from zerver.lib.exceptions import JsonableError
from zerver.lib.muted_users import get_mute_object
from zerver.lib.response import json_success
from zerver.lib.users import access_user_by_id
from zerver.models import UserProfile


def mute_user(request: HttpRequest, user_profile: UserProfile, muted_user_id: int) -> HttpResponse:
    if user_profile.id == muted_user_id:
        raise JsonableError(_("Cannot mute self"))

    muted_user = access_user_by_id(
        user_profile, muted_user_id, allow_bots=True, allow_deactivated=True, for_admin=False
    )
    date_muted = timezone_now()

    try:
        do_mute_user(user_profile, muted_user, date_muted)
    except IntegrityError:
        raise JsonableError(_("User already muted"))

    return json_success(request)


def unmute_user(
    request: HttpRequest, user_profile: UserProfile, muted_user_id: int
) -> HttpResponse:
    muted_user = access_user_by_id(
        user_profile, muted_user_id, allow_bots=True, allow_deactivated=True, for_admin=False
    )
    mute_object = get_mute_object(user_profile, muted_user)

    if mute_object is None:
        raise JsonableError(_("User is not muted"))

    do_unmute_user(mute_object)
    return json_success(request)
