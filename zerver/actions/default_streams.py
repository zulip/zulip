from typing import Any, Dict, Iterable, List

from django.db import transaction
from django.utils.translation import gettext as _

from zerver.lib.default_streams import (
    get_default_stream_ids_for_realm,
    get_default_streams_for_realm_as_dicts,
)
from zerver.lib.exceptions import JsonableError
from zerver.models import DefaultStream, DefaultStreamGroup, Realm, Stream
from zerver.models.streams import get_default_stream_groups
from zerver.models.users import active_non_guest_user_ids
from zerver.tornado.django_api import send_event_on_commit


def check_default_stream_group_name(group_name: str) -> None:
    if group_name.strip() == "":
        raise JsonableError(
            _("Invalid default channel group name '{group_name}'").format(group_name=group_name)
        )
    if len(group_name) > DefaultStreamGroup.MAX_NAME_LENGTH:
        raise JsonableError(
            _("Default channel group name too long (limit: {max_length} characters)").format(
                max_length=DefaultStreamGroup.MAX_NAME_LENGTH,
            )
        )
    for i in group_name:
        if ord(i) == 0:
            raise JsonableError(
                _(
                    "Default channel group name '{group_name}' contains NULL (0x00) characters."
                ).format(
                    group_name=group_name,
                )
            )


def lookup_default_stream_groups(
    default_stream_group_names: List[str], realm: Realm
) -> List[DefaultStreamGroup]:
    default_stream_groups = []
    for group_name in default_stream_group_names:
        try:
            default_stream_group = DefaultStreamGroup.objects.get(name=group_name, realm=realm)
        except DefaultStreamGroup.DoesNotExist:
            raise JsonableError(
                _("Invalid default channel group {group_name}").format(group_name=group_name)
            )
        default_stream_groups.append(default_stream_group)
    return default_stream_groups


def notify_default_streams(realm: Realm) -> None:
    event = dict(
        type="default_streams",
        default_streams=get_default_streams_for_realm_as_dicts(realm.id),
    )
    send_event_on_commit(realm, event, active_non_guest_user_ids(realm.id))


def notify_default_stream_groups(realm: Realm) -> None:
    event = dict(
        type="default_stream_groups",
        default_stream_groups=default_stream_groups_to_dicts_sorted(
            get_default_stream_groups(realm)
        ),
    )
    send_event_on_commit(realm, event, active_non_guest_user_ids(realm.id))


def do_add_default_stream(stream: Stream) -> None:
    realm_id = stream.realm_id
    stream_id = stream.id
    if not DefaultStream.objects.filter(realm_id=realm_id, stream_id=stream_id).exists():
        DefaultStream.objects.create(realm_id=realm_id, stream_id=stream_id)
        notify_default_streams(stream.realm)


@transaction.atomic(savepoint=False)
def do_remove_default_stream(stream: Stream) -> None:
    realm_id = stream.realm_id
    stream_id = stream.id
    DefaultStream.objects.filter(realm_id=realm_id, stream_id=stream_id).delete()
    notify_default_streams(stream.realm)


def do_create_default_stream_group(
    realm: Realm, group_name: str, description: str, streams: List[Stream]
) -> None:
    default_stream_ids = get_default_stream_ids_for_realm(realm.id)
    for stream in streams:
        if stream.id in default_stream_ids:
            raise JsonableError(
                _(
                    "'{channel_name}' is a default channel and cannot be added to '{group_name}'",
                ).format(channel_name=stream.name, group_name=group_name)
            )

    check_default_stream_group_name(group_name)
    (group, created) = DefaultStreamGroup.objects.get_or_create(
        name=group_name, realm=realm, description=description
    )
    if not created:
        raise JsonableError(
            _(
                "Default channel group '{group_name}' already exists",
            ).format(group_name=group_name)
        )

    group.streams.set(streams)
    notify_default_stream_groups(realm)


def do_add_streams_to_default_stream_group(
    realm: Realm, group: DefaultStreamGroup, streams: List[Stream]
) -> None:
    default_stream_ids = get_default_stream_ids_for_realm(realm.id)
    for stream in streams:
        if stream.id in default_stream_ids:
            raise JsonableError(
                _(
                    "'{channel_name}' is a default channel and cannot be added to '{group_name}'",
                ).format(channel_name=stream.name, group_name=group.name)
            )
        if stream in group.streams.all():
            raise JsonableError(
                _(
                    "Channel '{channel_name}' is already present in default channel group '{group_name}'",
                ).format(channel_name=stream.name, group_name=group.name)
            )
        group.streams.add(stream)

    group.save()
    notify_default_stream_groups(realm)


def do_remove_streams_from_default_stream_group(
    realm: Realm, group: DefaultStreamGroup, streams: List[Stream]
) -> None:
    group_stream_ids = {stream.id for stream in group.streams.all()}
    for stream in streams:
        if stream.id not in group_stream_ids:
            raise JsonableError(
                _(
                    "Channel '{channel_name}' is not present in default channel group '{group_name}'",
                ).format(channel_name=stream.name, group_name=group.name)
            )

    delete_stream_ids = {stream.id for stream in streams}

    group.streams.remove(*delete_stream_ids)
    notify_default_stream_groups(realm)


def do_change_default_stream_group_name(
    realm: Realm, group: DefaultStreamGroup, new_group_name: str
) -> None:
    if group.name == new_group_name:
        raise JsonableError(
            _("This default channel group is already named '{group_name}'").format(
                group_name=new_group_name
            )
        )

    if DefaultStreamGroup.objects.filter(name=new_group_name, realm=realm).exists():
        raise JsonableError(
            _("Default channel group '{group_name}' already exists").format(
                group_name=new_group_name
            )
        )

    group.name = new_group_name
    group.save()
    notify_default_stream_groups(realm)


def do_change_default_stream_group_description(
    realm: Realm, group: DefaultStreamGroup, new_description: str
) -> None:
    group.description = new_description
    group.save()
    notify_default_stream_groups(realm)


def do_remove_default_stream_group(realm: Realm, group: DefaultStreamGroup) -> None:
    group.delete()
    notify_default_stream_groups(realm)


def default_stream_groups_to_dicts_sorted(
    groups: Iterable[DefaultStreamGroup],
) -> List[Dict[str, Any]]:
    return sorted((group.to_dict() for group in groups), key=lambda elt: elt["name"])
