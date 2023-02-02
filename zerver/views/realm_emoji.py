from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _

from zerver.actions.realm_emoji import check_add_realm_emoji, do_remove_realm_emoji
from zerver.decorator import require_member_or_admin
from zerver.lib.emoji import check_remove_custom_emoji, check_valid_emoji_name, name_to_codepoint
from zerver.lib.exceptions import JsonableError
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.models import RealmEmoji, UserProfile


def list_emoji(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    # We don't do any checks here because the list of realm
    # emoji is public.
    return json_success(request, data={"emoji": user_profile.realm.get_emoji()})


@require_member_or_admin
@has_request_variables
def upload_emoji(
    request: HttpRequest, user_profile: UserProfile, emoji_name: str = REQ(path_only=True)
) -> HttpResponse:
    emoji_name = emoji_name.strip().replace(" ", "_")
    valid_built_in_emoji = name_to_codepoint.keys()
    check_valid_emoji_name(emoji_name)

    if not user_profile.can_add_custom_emoji():
        raise JsonableError(_("Insufficient permission"))

    if RealmEmoji.objects.filter(
        realm=user_profile.realm, name=emoji_name, deactivated=False
    ).exists():
        raise JsonableError(_("A custom emoji with this name already exists."))
    if len(request.FILES) != 1:
        raise JsonableError(_("You must upload exactly one file."))
    if emoji_name in valid_built_in_emoji:
        if not user_profile.is_realm_admin:
            raise JsonableError(_("Only administrators can override built-in emoji."))
    emoji_file = list(request.FILES.values())[0]
    assert isinstance(emoji_file, UploadedFile)
    assert emoji_file.size is not None
    if (settings.MAX_EMOJI_FILE_SIZE_MIB * 1024 * 1024) < emoji_file.size:
        raise JsonableError(
            _("Uploaded file is larger than the allowed limit of {} MiB").format(
                settings.MAX_EMOJI_FILE_SIZE_MIB,
            )
        )

    check_add_realm_emoji(user_profile.realm, emoji_name, user_profile, emoji_file)
    return json_success(request)


def delete_emoji(request: HttpRequest, user_profile: UserProfile, emoji_name: str) -> HttpResponse:
    if not RealmEmoji.objects.filter(
        realm=user_profile.realm, name=emoji_name, deactivated=False
    ).exists():
        raise JsonableError(_("Emoji '{}' does not exist").format(emoji_name))
    check_remove_custom_emoji(user_profile, emoji_name)
    do_remove_realm_emoji(user_profile.realm, emoji_name, acting_user=user_profile)
    return json_success(request)
