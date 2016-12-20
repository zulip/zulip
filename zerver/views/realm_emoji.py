from __future__ import absolute_import
from django.http import HttpRequest, HttpResponse
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext as _
from typing import Text

from zerver.models import UserProfile
from zerver.lib.request import JsonableError
from zerver.lib.response import json_success, json_error
from zerver.lib.actions import check_add_realm_emoji, do_remove_realm_emoji

def check_emoji_admin(user_profile):
    # type: (UserProfile) -> None
    if user_profile.realm.add_emoji_by_admins_only and not user_profile.is_realm_admin:
        raise JsonableError(_("Must be a realm administrator"))

def list_emoji(request, user_profile):
    # type: (HttpRequest, UserProfile) -> HttpResponse

    # We don't call check_emoji_admin here because the list of realm
    # emoji is public.
    return json_success({'emoji': user_profile.realm.get_emoji()})

def upload_emoji(request, user_profile):
    # type: (HttpRequest, UserProfile) -> HttpResponse
    check_emoji_admin(user_profile)
    emoji_name = request.POST.get('name', None)
    emoji_url = request.POST.get('url', None)
    try:
        check_add_realm_emoji(user_profile.realm, emoji_name, emoji_url, author=user_profile)
    except ValidationError as e:
        return json_error(e.messages[0])
    return json_success()

def delete_emoji(request, user_profile, emoji_name):
    # type: (HttpRequest, UserProfile, Text) -> HttpResponse
    check_emoji_admin(user_profile)
    do_remove_realm_emoji(user_profile.realm, emoji_name)
    return json_success()
