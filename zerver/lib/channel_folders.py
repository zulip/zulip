from typing import TypedDict

from django.utils.translation import gettext as _

from zerver.lib.exceptions import JsonableError
from zerver.lib.markdown import markdown_convert
from zerver.lib.streams import get_web_public_streams_queryset
from zerver.lib.string_validation import check_string_is_printable
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.models import ChannelFolder, Realm, Stream, UserProfile


class ChannelFolderDict(TypedDict):
    id: int
    name: str
    description: str
    rendered_description: str
    creator_id: int | None
    date_created: int
    is_archived: bool


def check_channel_folder_name(name: str, realm: Realm) -> None:
    if name.strip() == "":
        raise JsonableError(_("Channel folder name can't be empty."))

    invalid_character_pos = check_string_is_printable(name)
    if invalid_character_pos is not None:
        raise JsonableError(
            _("Invalid character in channel folder name, at position {position}.").format(
                position=invalid_character_pos
            )
        )

    if ChannelFolder.objects.filter(name__iexact=name, realm=realm).exists():
        raise JsonableError(_("Channel folder name already in use"))


def render_channel_folder_description(text: str, realm: Realm, *, acting_user: UserProfile) -> str:
    return markdown_convert(
        text, message_realm=realm, no_previews=True, acting_user=acting_user
    ).rendered_content


def get_channel_folder_dict(channel_folder: ChannelFolder) -> ChannelFolderDict:
    date_created = datetime_to_timestamp(channel_folder.date_created)
    return ChannelFolderDict(
        id=channel_folder.id,
        name=channel_folder.name,
        description=channel_folder.description,
        rendered_description=channel_folder.rendered_description,
        date_created=date_created,
        creator_id=channel_folder.creator_id,
        is_archived=channel_folder.is_archived,
    )


def get_channel_folders_in_realm(
    realm: Realm, include_archived: bool = False
) -> list[ChannelFolderDict]:
    folders = ChannelFolder.objects.filter(realm=realm)
    if not include_archived:
        folders = folders.exclude(is_archived=True)

    channel_folders = [get_channel_folder_dict(channel_folder) for channel_folder in folders]
    return sorted(channel_folders, key=lambda folder: folder["id"])


def get_channel_folder_by_id(channel_folder_id: int, realm: Realm) -> ChannelFolder:
    try:
        channel_folder = ChannelFolder.objects.get(id=channel_folder_id, realm=realm)
        return channel_folder
    except ChannelFolder.DoesNotExist:
        raise JsonableError(_("Invalid channel folder ID"))


def get_channel_folders_for_spectators(realm: Realm) -> list[ChannelFolderDict]:
    folder_ids_for_web_public_streams = set(
        get_web_public_streams_queryset(realm).values_list("folder_id", flat=True)
    )
    folders = ChannelFolder.objects.filter(id__in=folder_ids_for_web_public_streams)
    channel_folders = [get_channel_folder_dict(channel_folder) for channel_folder in folders]
    return sorted(channel_folders, key=lambda folder: folder["id"])


def check_channel_folder_in_use(channel_folder: ChannelFolder) -> bool:
    if Stream.objects.filter(folder=channel_folder).exists():
        return True
    return False
