
from django.conf import settings
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _
from typing import Text

from zerver.models import RealmEmoji, UserProfile
from zerver.lib.emoji import check_emoji_admin, check_valid_emoji_name, check_valid_emoji
from zerver.lib.request import JsonableError, REQ, has_request_variables
from zerver.lib.response import json_success, json_error
from zerver.lib.actions import check_add_realm_emoji, do_remove_realm_emoji


def list_emoji(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:

    # We don't call check_emoji_admin here because the list of realm
    # emoji is public.
    return json_success({'emoji': user_profile.realm.get_emoji()})


@has_request_variables
def upload_emoji(request: HttpRequest, user_profile: UserProfile,
                 emoji_name: Text=REQ()) -> HttpResponse:
    check_valid_emoji_name(emoji_name)
    check_emoji_admin(user_profile)
    if RealmEmoji.objects.filter(realm=user_profile.realm,
                                 name=emoji_name,
                                 deactivated=False).exists():
        return json_error(_("A custom emoji with this name already exists."))
    if len(request.FILES) != 1:
        return json_error(_("You must upload exactly one file."))
    emoji_file = list(request.FILES.values())[0]
    if (settings.MAX_EMOJI_FILE_SIZE * 1024 * 1024) < emoji_file.size:
        return json_error(_("Uploaded file is larger than the allowed limit of %s MB") % (
            settings.MAX_EMOJI_FILE_SIZE))

    realm_emoji = check_add_realm_emoji(user_profile.realm,
                                        emoji_name,
                                        user_profile,
                                        emoji_file)
    if realm_emoji is None:
        return json_error(_("Image file upload failed."))
    return json_success()


def delete_emoji(request: HttpRequest, user_profile: UserProfile,
                 emoji_name: str) -> HttpResponse:
    if not RealmEmoji.objects.filter(realm=user_profile.realm,
                                     name=emoji_name,
                                     deactivated=False).exists():
        raise JsonableError(_("Emoji '%s' does not exist" % (emoji_name,)))
    check_emoji_admin(user_profile, emoji_name)
    do_remove_realm_emoji(user_profile.realm, emoji_name)
    return json_success()
