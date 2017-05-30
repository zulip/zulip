from __future__ import absolute_import

from django.conf import settings
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _
from typing import Text

from zerver.lib.upload import upload_emoji_image
from zerver.models import UserProfile
from zerver.lib.emoji import check_emoji_admin, check_valid_emoji_name, check_valid_emoji, \
    get_emoji_file_name
from zerver.lib.request import JsonableError, REQ, has_request_variables
from zerver.lib.response import json_success, json_error
from zerver.lib.actions import check_add_realm_emoji, do_remove_realm_emoji


def list_emoji(request, user_profile):
    # type: (HttpRequest, UserProfile) -> HttpResponse

    # We don't call check_emoji_admin here because the list of realm
    # emoji is public.
    return json_success({'emoji': user_profile.realm.get_emoji()})


@has_request_variables
def upload_emoji(request, user_profile, emoji_name=REQ()):
    # type: (HttpRequest, UserProfile, Text) -> HttpResponse
    check_valid_emoji_name(emoji_name)
    check_emoji_admin(user_profile)
    if len(request.FILES) != 1:
        return json_error(_("You must upload exactly one file."))
    emoji_file = list(request.FILES.values())[0]
    if (settings.MAX_EMOJI_FILE_SIZE * 1024 * 1024) < emoji_file.size:
        return json_error(_("Uploaded file is larger than the allowed limit of %s MB") % (
            settings.MAX_EMOJI_FILE_SIZE))
    emoji_file_name = get_emoji_file_name(emoji_file.name, emoji_name)
    upload_emoji_image(emoji_file, emoji_file_name, user_profile)
    try:
        check_add_realm_emoji(user_profile.realm, emoji_name, emoji_file_name, author=user_profile)
    except ValidationError as e:
        return json_error(e.messages[0])
    return json_success()


def delete_emoji(request, user_profile, emoji_name):
    # type: (HttpRequest, UserProfile, Text) -> HttpResponse
    check_valid_emoji(user_profile.realm, emoji_name)
    check_emoji_admin(user_profile, emoji_name)
    do_remove_realm_emoji(user_profile.realm, emoji_name)
    return json_success()
