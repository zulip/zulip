from typing import Iterable, List, Sequence

from zerver.lib.user_groups import (
    access_user_group_by_id_for_stream_creation,
    get_user_group_members,
)
from zerver.models import Stream, StreamUserGroupAccess, UserGroup, UserProfile
from zerver.tornado.django_api import send_event


def send_stream_user_group_access_creation_event(
    acting_user: UserProfile, access_object: StreamUserGroupAccess
) -> None:
    stream_user_group_access_object = dict(
        id=access_object.id,
        stream_id=access_object.stream.id,
        group_id=access_object.user_group.id,
    )
    event = dict(
        type="stream_user_group_access",
        op="create",
        stream_user_group_access_object=stream_user_group_access_object,
    )
    active_users = acting_user.realm.get_active_users()
    stream_creators = [user.id for user in active_users if user.can_create_streams()]
    group_members = get_user_group_members(access_object.user_group)
    user_ids: Iterable[int] = list(set([*group_members, *stream_creators, acting_user.id]))
    send_event(acting_user.realm, event, user_ids)


def send_stream_user_group_access_delete_event(
    acting_user: UserProfile, id: int, group: UserGroup
) -> None:
    event = dict(
        type="stream_user_group_access",
        op="delete",
        access_object_id=id,
    )
    active_users = acting_user.realm.get_active_users()
    stream_creators = [user.id for user in active_users if user.can_create_streams()]
    group_members = get_user_group_members(group)
    user_ids: Iterable[int] = list(set([*group_members, *stream_creators, acting_user.id]))
    send_event(acting_user.realm, event, user_ids)


def update_stream_user_group_access_for_post(
    stream: Stream, add: Sequence[int], remove: Sequence[int], user_profile: UserProfile
) -> None:
    # We first check all the group ids to be valid and then proceed for creation/deletion.
    # If any of the provided group id is invalid request is completly failed  for all the
    # group ids.

    valid_groups_for_add: List[UserGroup] = []
    valid_groups_for_remove: List[UserGroup] = []
    for group_id in add:
        group = access_user_group_by_id_for_stream_creation(group_id, user_profile)
        valid_groups_for_add.append(group)

    for group_id in remove:
        group = access_user_group_by_id_for_stream_creation(group_id, user_profile)
        valid_groups_for_remove.append(group)

    for group in valid_groups_for_add:
        # This avoids creation of duplicate StreamUserGroupAccess objects.
        # Not sure if bulk create should be used here.
        obj, created = StreamUserGroupAccess.objects.get_or_create(
            stream=stream, user_group=group, realm=user_profile.realm
        )
        if created:
            send_stream_user_group_access_creation_event(user_profile, obj)

    # Handle deletion
    access_qs = StreamUserGroupAccess.objects.filter(
        stream=stream, user_group__in=valid_groups_for_remove
    )
    access_objects_ids = [item.id for item in access_qs]  # store ids to send event after deletion.
    access_qs.delete()

    StreamUserGroupAccess.objects.filter(
        stream=stream, user_group__in=valid_groups_for_remove, realm=user_profile.realm
    ).delete()
    for id in access_objects_ids:
        send_stream_user_group_access_delete_event(user_profile, id, group)


def get_stream_user_group_access_objects(user_profile: UserProfile) -> List[StreamUserGroupAccess]:
    if user_profile.can_create_streams():
        access_objs = list(StreamUserGroupAccess.objects.filter(realm=user_profile.realm))
    else:
        access_objs = list(
            StreamUserGroupAccess.objects.filter(
                realm=user_profile.realm, user_group__members=user_profile
            )
        )
    access_objs = [
        dict(id=obj.id, stream_id=obj.stream.id, group_id=obj.user_group.id) for obj in access_objs
    ]
    return access_objs
