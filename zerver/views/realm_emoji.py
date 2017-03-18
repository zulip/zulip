from __future__ import absolute_import

from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _
from typing import Text

from zerver.models import UserProfile
from zerver.lib.emoji import check_emoji_admin, check_valid_emoji_name, check_valid_emoji
from zerver.lib.request import JsonableError, REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.actions import check_add_realm_emoji, do_remove_realm_emoji

def list_emoji(request, user_profile):
    # type: (HttpRequest, UserProfile) -> HttpResponse

    # We don't call check_emoji_admin here because the list of realm
    # emoji is public.
    return json_success({'emoji': user_profile.realm.get_emoji()})

@has_request_variables
def upload_emoji(request, user_profile, emoji_name, url=REQ()):
    # type: (HttpRequest, UserProfile, Text, Text) -> HttpResponse
    check_valid_emoji_name(emoji_name)
    check_emoji_admin(user_profile)
    check_add_realm_emoji(user_profile.realm, emoji_name, url, author=user_profile)
    return json_success()

def delete_emoji(request, user_profile, emoji_name):
    # type: (HttpRequest, UserProfile, Text) -> HttpResponse
    check_emoji_admin(user_profile)
    check_valid_emoji(user_profile.realm, emoji_name)
    do_remove_realm_emoji(user_profile.realm, emoji_name)
    return json_success()
