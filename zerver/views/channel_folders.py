from typing import Annotated

from django.http import HttpRequest, HttpResponse
from pydantic import StringConstraints

from zerver.actions.channel_folders import check_add_channel_folder
from zerver.decorator import require_realm_admin
from zerver.lib.channel_folders import check_channel_folder_name
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint
from zerver.models.channel_folders import ChannelFolder
from zerver.models.users import UserProfile


@require_realm_admin
@typed_endpoint
def create_channel_folder(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    name: Annotated[str, StringConstraints(max_length=ChannelFolder.MAX_NAME_LENGTH)],
    description: Annotated[str, StringConstraints(max_length=ChannelFolder.MAX_DESCRIPTION_LENGTH)],
) -> HttpResponse:
    check_channel_folder_name(name, user_profile.realm)
    channel_folder = check_add_channel_folder(name, description, acting_user=user_profile)

    return json_success(request, data={"channel_folder_id": channel_folder.id})
