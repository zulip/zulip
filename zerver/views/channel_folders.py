from typing import Annotated

from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _
from pydantic import Json, StringConstraints

from zerver.actions.channel_folders import (
    check_add_channel_folder,
    do_archive_channel_folder,
    do_change_channel_folder_description,
    do_change_channel_folder_name,
    do_unarchive_channel_folder,
)
from zerver.decorator import require_realm_admin
from zerver.lib.channel_folders import (
    check_channel_folder_in_use,
    check_channel_folder_name,
    get_channel_folder_by_id,
    get_channel_folders_in_realm,
)
from zerver.lib.exceptions import JsonableError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import PathOnly, typed_endpoint
from zerver.models.channel_folders import ChannelFolder
from zerver.models.users import UserProfile


@require_realm_admin
@typed_endpoint
def create_channel_folder(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    description: Annotated[str, StringConstraints(max_length=ChannelFolder.MAX_DESCRIPTION_LENGTH)],
    name: Annotated[str, StringConstraints(max_length=ChannelFolder.MAX_NAME_LENGTH)],
) -> HttpResponse:
    realm = user_profile.realm
    check_channel_folder_name(name, realm)
    channel_folder = check_add_channel_folder(realm, name, description, acting_user=user_profile)

    return json_success(request, data={"channel_folder_id": channel_folder.id})


@typed_endpoint
def get_channel_folders(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    include_archived: Json[bool] = False,
) -> HttpResponse:
    channel_folders = get_channel_folders_in_realm(user_profile.realm, include_archived)
    return json_success(request, data={"channel_folders": channel_folders})


@require_realm_admin
@typed_endpoint
def update_channel_folder(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    channel_folder_id: PathOnly[int],
    description: str | None = None,
    is_archived: Json[bool] | None = None,
    name: str | None = None,
) -> HttpResponse:
    channel_folder = get_channel_folder_by_id(channel_folder_id, user_profile.realm)

    if name is not None and channel_folder.name != name:
        check_channel_folder_name(name, user_profile.realm)
        do_change_channel_folder_name(channel_folder, name, acting_user=user_profile)

    if description is not None and channel_folder.description != description:
        do_change_channel_folder_description(channel_folder, description, acting_user=user_profile)

    if is_archived is not None and channel_folder.is_archived != is_archived:
        if is_archived:
            if check_channel_folder_in_use(channel_folder):
                raise JsonableError(
                    _("You need to remove all the channels from this folder to archive it.")
                )

            do_archive_channel_folder(channel_folder, acting_user=user_profile)
        else:
            do_unarchive_channel_folder(channel_folder, acting_user=user_profile)

    return json_success(request)
