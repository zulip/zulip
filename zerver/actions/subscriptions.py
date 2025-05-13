from collections import defaultdict
from collections.abc import Collection, Iterable, Mapping
from typing import Any, TypeAlias

from django.db import transaction
from django.utils.timezone import now as timezone_now

from zerver.lib.message import get_last_message_id
from zerver.lib.queue import queue_event_on_commit
from zerver.lib.stream_color import pick_colors
from zerver.lib.stream_subscription import (
    SubInfo,
    SubscriberPeerInfo,
    bulk_update_subscriber_counts,
    get_bulk_stream_subscriber_info,
    get_used_colors_for_user_ids,
    get_user_ids_for_streams,
    get_users_for_streams,
)
from zerver.lib.stream_traffic import get_streams_traffic
from zerver.lib.streams import (
    check_basic_stream_access,
    get_anonymous_group_membership_dict_for_streams,
    get_users_dict_with_metadata_access_to_streams_via_permission_groups,
    send_stream_creation_event,
    send_stream_deletion_event,
    stream_to_dict,
)
from zerver.lib.subscription_info import bulk_get_subscriber_peer_info
from zerver.lib.types import APISubscriptionDict, UserGroupMembersData
from zerver.lib.users import (
    all_users_accessible_by_everyone_in_realm,
    get_subscribers_of_target_user_subscriptions,
    get_users_involved_in_dms_with_target_users,
)
from zerver.models.realm_audit_logs import AuditLogEventType, RealmAuditLog
from zerver.models.realms import Realm
from zerver.models.recipients import Recipient
from zerver.models.streams import Stream, Subscription
from zerver.models.users import UserProfile, active_non_guest_user_ids, active_user_ids
from zerver.tornado.django_api import send_event_on_commit


def send_subscription_add_events(
    realm: Realm,
    sub_info_list: list[SubInfo],
    subscriber_dict: dict[int, set[int]],
) -> None:
    info_by_user: dict[int, list[SubInfo]] = defaultdict(list)
    for sub_info in sub_info_list:
        info_by_user[sub_info.user.id].append(sub_info)

    stream_ids = {sub_info.stream.id for sub_info in sub_info_list}
    recent_traffic = get_streams_traffic(stream_ids=stream_ids, realm=realm)

    # We generally only have a few streams, so we compute subscriber
    # data in its own loop.
    stream_subscribers_dict: dict[int, list[int]] = {}
    for sub_info in sub_info_list:
        stream = sub_info.stream
        if stream.id not in stream_subscribers_dict:
            if stream.is_in_zephyr_realm and not stream.invite_only:
                subscribers = []
            else:
                subscribers = list(subscriber_dict[stream.id])
            stream_subscribers_dict[stream.id] = subscribers

    streams = [sub_info.stream for sub_info in sub_info_list]
    anonymous_group_membership = get_anonymous_group_membership_dict_for_streams(
        streams)

    for user_id, sub_infos in info_by_user.items():
        sub_dicts: list[APISubscriptionDict] = []
        for sub_info in sub_infos:
            stream = sub_info.stream
            stream_subscribers = stream_subscribers_dict[stream.id]
            subscription = sub_info.sub
            stream_dict = stream_to_dict(
                stream, recent_traffic, anonymous_group_membership)
            # This is verbose as we cannot unpack existing TypedDict
            # to initialize another TypedDict while making mypy happy.
            # https://github.com/python/mypy/issues/5382
            sub_dict = APISubscriptionDict(
                # Fields from Subscription.API_FIELDS
                audible_notifications=subscription.audible_notifications,
                color=subscription.color,
                desktop_notifications=subscription.desktop_notifications,
                email_notifications=subscription.email_notifications,
                is_muted=subscription.is_muted,
                pin_to_top=subscription.pin_to_top,
                push_notifications=subscription.push_notifications,
                wildcard_mentions_notify=subscription.wildcard_mentions_notify,
                # Computed fields not present in Subscription.API_FIELDS
                in_home_view=not subscription.is_muted,
                stream_weekly_traffic=stream_dict["stream_weekly_traffic"],
                subscribers=stream_subscribers,
                # Fields from Stream.API_FIELDS
                is_archived=stream_dict["is_archived"],
                can_add_subscribers_group=stream_dict["can_add_subscribers_group"],
                can_administer_channel_group=stream_dict["can_administer_channel_group"],
                can_send_message_group=stream_dict["can_send_message_group"],
                can_remove_subscribers_group=stream_dict["can_remove_subscribers_group"],
                can_subscribe_group=stream_dict["can_subscribe_group"],
                creator_id=stream_dict["creator_id"],
                date_created=stream_dict["date_created"],
                description=stream_dict["description"],
                first_message_id=stream_dict["first_message_id"],
                is_recently_active=stream_dict["is_recently_active"],
                history_public_to_subscribers=stream_dict["history_public_to_subscribers"],
                invite_only=stream_dict["invite_only"],
                is_web_public=stream_dict["is_web_public"],
                message_retention_days=stream_dict["message_retention_days"],
                name=stream_dict["name"],
                rendered_description=stream_dict["rendered_description"],
                stream_id=stream_dict["stream_id"],
                stream_post_policy=stream_dict["stream_post_policy"],
                # Computed fields not present in Stream.API_FIELDS
                is_announcement_only=stream_dict["is_announcement_only"],
            )

            sub_dicts.append(sub_dict)

        # Send a notification to the user who subscribed.
        event = dict(type="subscription", op="add", subscriptions=sub_dicts)
        send_event_on_commit(realm, event, [user_id])


# This function contains all the database changes as part of
# subscribing users to streams; the transaction ensures that the
# RealmAuditLog entries are created atomically with the Subscription
# object creation (and updates).
@transaction.atomic(savepoint=False)
def bulk_add_subs_to_db_with_logging(
    realm: Realm,
    acting_user: UserProfile | None,
    subs_to_add: list[SubInfo],
    subs_to_activate: list[SubInfo],
) -> None:
    Subscription.objects.bulk_create(info.sub for info in subs_to_add)
    sub_ids = [info.sub.id for info in subs_to_activate]
    Subscription.objects.filter(id__in=sub_ids).update(active=True)

    # Log subscription activities in RealmAuditLog
    event_time = timezone_now()
    event_last_message_id = get_last_message_id()

    all_subscription_logs = [
        RealmAuditLog(
            realm=realm,
            acting_user=acting_user,
            modified_user=sub_info.user,
            modified_stream=sub_info.stream,
            event_last_message_id=event_last_message_id,
            event_type=event_type,
            event_time=event_time,
        )
        for event_type, subs in [
            (AuditLogEventType.SUBSCRIPTION_CREATED, subs_to_add),
            (AuditLogEventType.SUBSCRIPTION_ACTIVATED, subs_to_activate),
        ]
        for sub_info in subs
    ]
    # Now since we have all log objects generated we can do a bulk insert
    RealmAuditLog.objects.bulk_create(all_subscription_logs)


def send_stream_creation_events_for_previously_inaccessible_streams(
    realm: Realm,
    stream_dict: dict[int, Stream],
    altered_user_dict: dict[int, set[int]],
    altered_guests: set[int],
    users_with_metadata_access_via_permission_groups: dict[int,
                                                           set[int]] | None = None,
) -> None:
    stream_ids = set(altered_user_dict.keys())
    recent_traffic = get_streams_traffic(stream_ids, realm)

    streams = [stream_dict[stream_id] for stream_id in stream_ids]
    anonymous_group_membership: dict[int, UserGroupMembersData] | None = None

    for stream_id, stream_users_ids in altered_user_dict.items():
        stream = stream_dict[stream_id]

        notify_user_ids = []
        if not stream.is_public():
            assert users_with_metadata_access_via_permission_groups is not None
            # Users newly added to invite-only streams
            # need a `create` notification.  The former, because
            # they need the stream to exist before
            # they get the "subscribe" notification, and the latter so
            # they can manage the new stream.
            # Realm admins already have all created private streams.
            realm_admin_ids = {
                user.id for user in realm.get_admin_users_and_bots()}
            notify_user_ids = list(
                stream_users_ids
                - realm_admin_ids
                - users_with_metadata_access_via_permission_groups[stream.id]
            )
        elif not stream.is_web_public:
            # Guese users need a `create` notification for
            # public streams as well because they need the stream
            # to exist before they get the "subscribe" notification.
            notify_user_ids = list(stream_users_ids & altered_guests)

        if notify_user_ids:
            if anonymous_group_membership is None:
                anonymous_group_membership = get_anonymous_group_membership_dict_for_streams(
                    streams
                )

            send_stream_creation_event(
                realm, stream, notify_user_ids, recent_traffic, anonymous_group_membership
            )


def send_peer_subscriber_events(
    op: str,
    realm: Realm,
    stream_dict: dict[int, Stream],
    altered_user_dict: dict[int, set[int]],
    subscriber_peer_info: SubscriberPeerInfo,
) -> None:
    # Send peer_add/peer_remove events to other users who are tracking the
    # subscribers lists of streams in their browser; everyone for
    # public streams and only existing subscribers for private streams.

    assert op in ["peer_add", "peer_remove"]

    private_stream_ids = [
        stream_id for stream_id in altered_user_dict if stream_dict[stream_id].invite_only
    ]
    public_stream_ids = [
        stream_id
        for stream_id in altered_user_dict
        if not stream_dict[stream_id].invite_only and not stream_dict[stream_id].is_in_zephyr_realm
    ]
    web_public_stream_ids = [
        stream_id for stream_id in public_stream_ids if stream_dict[stream_id].is_web_public
    ]

    private_peer_dict = subscriber_peer_info.private_peer_dict
    for stream_id in private_stream_ids:
        altered_user_ids = altered_user_dict[stream_id]
        peer_user_ids = private_peer_dict[stream_id] - altered_user_ids

        if peer_user_ids and altered_user_ids:
            event = dict(
                type="subscription",
                op=op,
                stream_ids=[stream_id],
                user_ids=sorted(altered_user_ids),
            )
            send_event_on_commit(realm, event, peer_user_ids)

    if public_stream_ids:
        subscriber_dict = subscriber_peer_info.subscribed_ids
        user_streams: dict[str, set[int]] = defaultdict(set)
        non_guest_user_ids = set(active_non_guest_user_ids(realm.id))

        for stream_id in public_stream_ids:
            altered_user_ids = altered_user_dict[stream_id]
            if altered_user_ids:
                altered_user_id_string = ",".join(
                    map(str, sorted(altered_user_ids)))
                # We will store stream_ids related to each set of
                # unique user ids.
                user_streams[altered_user_id_string].add(stream_id)

        # For each set of unique user ids, we will send one event for
        # web public streams, one event for public streams without a
        # guest user and for each stream apart from that, we will send
        # one event each.
        for altered_user_id_string, stream_ids in user_streams.items():
            altered_user_ids = set(map(int, altered_user_id_string.split(",")))
            # Both of the lists below will have the same list of peer
            # user ids each, so we will send a single event for each of
            # these lists.
            web_public_user_stream_ids = []
            public_user_stream_ids_without_guest_users = []

            for stream_id in stream_ids:
                if stream_id in web_public_stream_ids:
                    web_public_user_stream_ids.append(stream_id)
                else:
                    if (non_guest_user_ids | subscriber_dict[stream_id]) == non_guest_user_ids:
                        public_user_stream_ids_without_guest_users.append(
                            stream_id)
                    else:
                        # This channel likely has a unique set of
                        # peer_user_ids to notify, so we send the event
                        # directly for just this channel.
                        peer_user_ids = (
                            non_guest_user_ids | subscriber_dict[stream_id]
                        ) - altered_user_ids
                        event = dict(
                            type="subscription",
                            op=op,
                            stream_ids=[stream_id],
                            user_ids=list(altered_user_ids),
                        )
                        send_event_on_commit(realm, event, peer_user_ids)

            if len(web_public_user_stream_ids) > 0:
                web_public_peer_ids = set(active_user_ids(realm.id))
                web_public_streams_event = dict(
                    type="subscription",
                    op=op,
                    stream_ids=sorted(web_public_user_stream_ids),
                    user_ids=list(altered_user_ids),
                )
                send_event_on_commit(
                    realm, web_public_streams_event, web_public_peer_ids - altered_user_ids
                )
            if len(public_user_stream_ids_without_guest_users) > 0:
                public_streams_event = dict(
                    type="subscription",
                    op=op,
                    stream_ids=sorted(
                        public_user_stream_ids_without_guest_users),
                    user_ids=list(altered_user_ids),
                )
                send_event_on_commit(
                    realm, public_streams_event, non_guest_user_ids - altered_user_ids
                )


def send_user_creation_events_on_adding_subscriptions(
    realm: Realm,
    altered_user_dict: dict[int, set[int]],
    altered_streams_dict: dict[UserProfile, set[int]],
    subscribers_of_altered_user_subscriptions: dict[int, set[int]],
) -> None:
    altered_users = list(altered_streams_dict.keys())
    non_guest_user_ids = active_non_guest_user_ids(realm.id)

    users_involved_in_dms = get_users_involved_in_dms_with_target_users(
        altered_users, realm)

    altered_stream_ids = altered_user_dict.keys()
    subscribers_dict = get_users_for_streams(set(altered_stream_ids))

    subscribers_user_id_map: dict[int, UserProfile] = {}
    subscriber_ids_dict: dict[int, set[int]] = defaultdict(set)
    for stream_id, subscribers in subscribers_dict.items():
        for user in subscribers:
            subscriber_ids_dict[stream_id].add(user.id)
            subscribers_user_id_map[user.id] = user

    from zerver.actions.create_user import notify_created_user

    for user in altered_users:
        streams_for_user = altered_streams_dict[user]
        subscribers_in_altered_streams: set[int] = set()
        for stream_id in streams_for_user:
            subscribers_in_altered_streams |= subscriber_ids_dict[stream_id]

        users_already_with_access_to_altered_user = (
            set(non_guest_user_ids)
            | subscribers_of_altered_user_subscriptions[user.id]
            | users_involved_in_dms[user.id]
            | {user.id}
        )

        users_to_receive_creation_event = (
            subscribers_in_altered_streams - users_already_with_access_to_altered_user
        )
        if users_to_receive_creation_event:
            notify_created_user(user, list(users_to_receive_creation_event))

        if user.is_guest:
            # If the altered user is a guest, then the user may receive
            # user creation events for subscribers of the new stream.
            users_already_accessible_to_altered_user = (
                subscribers_of_altered_user_subscriptions[user.id]
                | users_involved_in_dms[user.id]
                | {user.id}
            )

            new_accessible_user_ids = (
                subscribers_in_altered_streams - users_already_accessible_to_altered_user
            )
            for accessible_user_id in new_accessible_user_ids:
                accessible_user = subscribers_user_id_map[accessible_user_id]
                notify_created_user(accessible_user, [user.id])


SubT: TypeAlias = tuple[list[SubInfo], list[SubInfo]]


@transaction.atomic(savepoint=False)
def bulk_add_subscriptions(
    realm: Realm,
    streams: Collection[Stream],
    users: Iterable[UserProfile],
    color_map: Mapping[str, str] = {},
    from_user_creation: bool = False,
    *,
    acting_user: UserProfile | None,
) -> SubT:
    users = list(users)
    user_ids = [user.id for user in users]

    # Sanity check out callers
    for stream in streams:
        assert stream.realm_id == realm.id

    for user in users:
        assert user.realm_id == realm.id

    recipient_ids = [stream.recipient_id for stream in streams]
    recipient_id_to_stream = {
        stream.recipient_id: stream for stream in streams}

    recipient_color_map = {}
    recipient_ids_set: set[int] = set()
    for stream in streams:
        assert stream.recipient_id is not None
        recipient_ids_set.add(stream.recipient_id)
        color: str | None = color_map.get(stream.name, None)
        if color is not None:
            recipient_color_map[stream.recipient_id] = color

    used_colors_for_user_ids: dict[int, set[str]
                                   ] = get_used_colors_for_user_ids(user_ids)

    existing_subs = Subscription.objects.filter(
        user_profile_id__in=user_ids,
        recipient__type=Recipient.STREAM,
        recipient_id__in=recipient_ids,
    )

    subs_by_user: dict[int, list[Subscription]] = defaultdict(list)
    for sub in existing_subs:
        subs_by_user[sub.user_profile_id].append(sub)

    already_subscribed: list[SubInfo] = []
    subs_to_activate: list[SubInfo] = []
    subs_to_add: list[SubInfo] = []
    for user_profile in users:
        my_subs = subs_by_user[user_profile.id]

        # Make a fresh set of all new recipient ids, and then we will
        # remove any for which our user already has a subscription
        # (and we'll re-activate any subscriptions as needed).
        new_recipient_ids: set[int] = recipient_ids_set.copy()

        for sub in my_subs:
            if sub.recipient_id in new_recipient_ids:
                new_recipient_ids.remove(sub.recipient_id)
                stream = recipient_id_to_stream[sub.recipient_id]
                sub_info = SubInfo(user_profile, sub, stream)
                if sub.active:
                    already_subscribed.append(sub_info)
                else:
                    subs_to_activate.append(sub_info)

        used_colors = used_colors_for_user_ids.get(user_profile.id, set())
        user_color_map = pick_colors(
            used_colors, recipient_color_map, list(new_recipient_ids))

        for recipient_id in new_recipient_ids:
            stream = recipient_id_to_stream[recipient_id]
            color = user_color_map[recipient_id]

            sub = Subscription(
                user_profile=user_profile,
                is_user_active=user_profile.is_active,
                active=True,
                color=color,
                recipient_id=recipient_id,
            )
            sub_info = SubInfo(user_profile, sub, stream)
            subs_to_add.append(sub_info)

    if len(subs_to_add) == 0 and len(subs_to_activate) == 0:
        # We can return early if users are already subscribed to all the streams.
        return ([], already_subscribed)

    altered_user_dict: dict[int, set[int]] = defaultdict(set)
    altered_guests: set[int] = set()
    altered_streams_dict: dict[UserProfile, set[int]] = defaultdict(set)
    subscriber_count_changes: dict[int, set[int]] = defaultdict(set)
    for sub_info in subs_to_add + subs_to_activate:
        altered_user_dict[sub_info.stream.id].add(sub_info.user.id)
        altered_streams_dict[sub_info.user].add(sub_info.stream.id)
        if sub_info.user.is_active:
            subscriber_count_changes[sub_info.stream.id].add(sub_info.user.id)
        if sub_info.user.is_guest:
            altered_guests.add(sub_info.user.id)

    if not all_users_accessible_by_everyone_in_realm(realm):
        altered_users = list(altered_streams_dict.keys())
        subscribers_of_altered_user_subscriptions = get_subscribers_of_target_user_subscriptions(
            altered_users
        )

    bulk_add_subs_to_db_with_logging(
        realm=realm,
        acting_user=acting_user,
        subs_to_add=subs_to_add,
        subs_to_activate=subs_to_activate,
    )
    bulk_update_subscriber_counts(direction=1, streams=subscriber_count_changes)

    stream_dict = {stream.id: stream for stream in streams}

    new_streams = [stream_dict[stream_id] for stream_id in altered_user_dict]

    private_streams = [
        stream for stream in new_streams if not stream.is_public()]
    users_with_metadata_access_via_permission_groups = None
    if private_streams:
        users_with_metadata_access_via_permission_groups = (
            get_users_dict_with_metadata_access_to_streams_via_permission_groups(
                private_streams, realm.id
            )
        )

    subscriber_peer_info = bulk_get_subscriber_peer_info(
        realm=realm,
        streams=new_streams,
        users_with_metadata_access_via_permission_groups=users_with_metadata_access_via_permission_groups,
    )

    # We now send several types of events to notify browsers.  The
    # first batches of notifications are sent only to the user(s)
    # being subscribed; we can skip these notifications when this is
    # being called from the new user creation flow.
    if not from_user_creation:
        send_stream_creation_events_for_previously_inaccessible_streams(
            realm=realm,
            stream_dict=stream_dict,
            altered_user_dict=altered_user_dict,
            altered_guests=altered_guests,
            users_with_metadata_access_via_permission_groups=users_with_metadata_access_via_permission_groups,
        )

        send_subscription_add_events(
            realm=realm,
            sub_info_list=subs_to_add + subs_to_activate,
            subscriber_dict=subscriber_peer_info.subscribed_ids,
        )

    if not all_users_accessible_by_everyone_in_realm(realm):
        send_user_creation_events_on_adding_subscriptions(
            realm,
            altered_user_dict,
            altered_streams_dict,
            subscribers_of_altered_user_subscriptions,
        )

    send_peer_subscriber_events(
        op="peer_add",
        realm=realm,
        altered_user_dict=altered_user_dict,
        stream_dict=stream_dict,
        subscriber_peer_info=subscriber_peer_info,
    )

    return (
        subs_to_add + subs_to_activate,
        already_subscribed,
    )


def send_peer_remove_events(
    realm: Realm,
    streams: list[Stream],
    altered_user_dict: dict[int, set[int]],
) -> None:
    subscriber_peer_info = bulk_get_subscriber_peer_info(
        realm=realm,
        streams=streams,
    )
    stream_dict = {stream.id: stream for stream in streams}

    send_peer_subscriber_events(
        op="peer_remove",
        realm=realm,
        stream_dict=stream_dict,
        altered_user_dict=altered_user_dict,
        subscriber_peer_info=subscriber_peer_info,
    )


def notify_subscriptions_removed(
    realm: Realm, user_profile: UserProfile, streams: Iterable[Stream]
) -> None:
    payload = [dict(name=stream.name, stream_id=stream.id)
               for stream in streams]
    event = dict(type="subscription", op="remove", subscriptions=payload)
    send_event_on_commit(realm, event, [user_profile.id])


SubAndRemovedT: TypeAlias = tuple[
    list[tuple[UserProfile, Stream]], list[tuple[UserProfile, Stream]]
]


def send_subscription_remove_events(
    realm: Realm,
    users: list[UserProfile],
    streams: list[Stream],
    removed_subs: list[tuple[UserProfile, Stream]],
) -> None:
    altered_user_dict: dict[int, set[int]] = defaultdict(set)
    streams_by_user: dict[int, list[Stream]] = defaultdict(list)
    for user, stream in removed_subs:
        streams_by_user[user.id].append(stream)
        altered_user_dict[stream.id].add(user.id)

    for user_profile in users:
        if len(streams_by_user[user_profile.id]) == 0:
            continue
        notify_subscriptions_removed(
            realm, user_profile, streams_by_user[user_profile.id])

        event = {
            "type": "mark_stream_messages_as_read",
            "user_profile_id": user_profile.id,
            "stream_recipient_ids": [
                stream.recipient_id for stream in streams_by_user[user_profile.id]
            ],
        }
        queue_event_on_commit("deferred_work", event)

        if not user_profile.is_realm_admin:
            inaccessible_streams = [
                stream
                for stream in streams_by_user[user_profile.id]
                if not check_basic_stream_access(
                    user_profile, stream, is_subscribed=False, require_content_access=False
                )
            ]

            if inaccessible_streams:
                send_stream_deletion_event(
                    realm, [user_profile.id], inaccessible_streams)

    send_peer_remove_events(
        realm=realm,
        streams=streams,
        altered_user_dict=altered_user_dict,
    )


def send_user_remove_events_on_removing_subscriptions(
    realm: Realm, altered_user_dict: dict[UserProfile, set[int]]
) -> None:
    altered_stream_ids: set[int] = set()
    altered_users = list(altered_user_dict.keys())
    for stream_ids in altered_user_dict.values():
        altered_stream_ids |= stream_ids

    users_involved_in_dms = get_users_involved_in_dms_with_target_users(
        altered_users, realm)
    subscribers_of_altered_user_subscriptions = get_subscribers_of_target_user_subscriptions(
        altered_users
    )

    non_guest_user_ids = active_non_guest_user_ids(realm.id)

    subscribers_dict = get_user_ids_for_streams(altered_stream_ids)

    for user in altered_users:
        users_in_unsubscribed_streams: set[int] = set()
        for stream_id in altered_user_dict[user]:
            users_in_unsubscribed_streams |= subscribers_dict[stream_id]

        users_who_can_access_altered_user = (
            set(non_guest_user_ids)
            | subscribers_of_altered_user_subscriptions[user.id]
            | users_involved_in_dms[user.id]
            | {user.id}
        )

        subscribers_without_access_to_altered_user = (
            users_in_unsubscribed_streams - users_who_can_access_altered_user
        )

        if subscribers_without_access_to_altered_user:
            event_remove_user = dict(
                type="realm_user",
                op="remove",
                person=dict(user_id=user.id, full_name=str(
                    UserProfile.INACCESSIBLE_USER_NAME)),
            )
            send_event_on_commit(
                realm, event_remove_user, list(
                    subscribers_without_access_to_altered_user)
            )

        if user.is_guest:
            users_inaccessible_to_altered_user = users_in_unsubscribed_streams - (
                subscribers_of_altered_user_subscriptions[user.id]
                | users_involved_in_dms[user.id]
                | {user.id}
            )

            for user_id in users_inaccessible_to_altered_user:
                event_remove_user = dict(
                    type="realm_user",
                    op="remove",
                    person=dict(user_id=user_id, full_name=str(
                        UserProfile.INACCESSIBLE_USER_NAME)),
                )
                send_event_on_commit(realm, event_remove_user, [user.id])


def bulk_remove_subscriptions(
    realm: Realm,
    users: Iterable[UserProfile],
    streams: Iterable[Stream],
    *,
    acting_user: UserProfile | None,
) -> SubAndRemovedT:
    users = list(users)
    streams = list(streams)

    # Sanity check our callers
    for stream in streams:
        assert stream.realm_id == realm.id

    for user in users:
        assert user.realm_id == realm.id

    stream_dict = {stream.id: stream for stream in streams}

    existing_subs_by_user = get_bulk_stream_subscriber_info(users, streams)

    def get_non_subscribed_subs() -> list[tuple[UserProfile, Stream]]:
        stream_ids = {stream.id for stream in streams}

        not_subscribed: list[tuple[UserProfile, Stream]] = []

        for user_profile in users:
            user_sub_stream_info = existing_subs_by_user[user_profile.id]

            subscribed_stream_ids = {
                sub_info.stream.id for sub_info in user_sub_stream_info}
            not_subscribed_stream_ids = stream_ids - subscribed_stream_ids

            not_subscribed.extend(
                (user_profile, stream_dict[stream_id]) for stream_id in not_subscribed_stream_ids
            )

        return not_subscribed

    not_subscribed = get_non_subscribed_subs()

    # This loop just flattens out our data into big lists for
    # bulk operations.
    subs_to_deactivate = [
        sub_info for sub_infos in existing_subs_by_user.values() for sub_info in sub_infos
    ]

    if len(subs_to_deactivate) == 0:
        # We can return early if users are not subscribed to any of the streams.
        return ([], not_subscribed)

    sub_ids_to_deactivate = [
        sub_info.sub.id for sub_info in subs_to_deactivate]

    subscriber_count_changes: dict[int, set[int]] = defaultdict(set)
    for sub_info in subs_to_deactivate:
        if sub_info.user.is_active:
            subscriber_count_changes[sub_info.stream.id].add(sub_info.user.id)

    # We do all the database changes in a transaction to ensure
    # RealmAuditLog entries are atomically created when making changes.
    with transaction.atomic(savepoint=False):
        Subscription.objects.filter(
            id__in=sub_ids_to_deactivate,
        ).update(active=False)
        bulk_update_subscriber_counts(
            direction=-1, streams=subscriber_count_changes)

        # Log subscription activities in RealmAuditLog
        event_time = timezone_now()
        event_last_message_id = get_last_message_id()
        all_subscription_logs = [
            RealmAuditLog(
                realm=sub_info.user.realm,
                acting_user=acting_user,
                modified_user=sub_info.user,
                modified_stream=sub_info.stream,
                event_last_message_id=event_last_message_id,
                event_type=AuditLogEventType.SUBSCRIPTION_DEACTIVATED,
                event_time=event_time,
            )
            for sub_info in subs_to_deactivate
        ]

        # Now since we have all log objects generated we can do a bulk insert
        RealmAuditLog.objects.bulk_create(all_subscription_logs)

    removed_sub_tuples = [(sub_info.user, sub_info.stream)
                          for sub_info in subs_to_deactivate]
    send_subscription_remove_events(realm, users, streams, removed_sub_tuples)

    if not all_users_accessible_by_everyone_in_realm(realm):
        altered_user_dict: dict[UserProfile, set[int]] = defaultdict(set)
        for user, stream in removed_sub_tuples:
            altered_user_dict[user].add(stream.id)
        send_user_remove_events_on_removing_subscriptions(
            realm, altered_user_dict)

    return (
        removed_sub_tuples,
        not_subscribed,
    )


@transaction.atomic(durable=True)
def do_change_subscription_property(
    user_profile: UserProfile,
    sub: Subscription,
    stream: Stream,
    property_name: str,
    value: Any,
    *,
    acting_user: UserProfile | None,
) -> None:
    database_property_name = property_name
    database_value = value

    # For this property, is_muted is used in the database, but
    # in_home_view is still in the API, since we haven't fully
    # migrated to the new name yet.
    if property_name == "in_home_view":
        database_property_name = "is_muted"
        database_value = not value

    old_value = getattr(sub, database_property_name)
    setattr(sub, database_property_name, database_value)
    sub.save(update_fields=[database_property_name])
    event_time = timezone_now()
    RealmAuditLog.objects.create(
        realm=user_profile.realm,
        event_type=AuditLogEventType.SUBSCRIPTION_PROPERTY_CHANGED,
        event_time=event_time,
        modified_user=user_profile,
        acting_user=acting_user,
        modified_stream=stream,
        extra_data={
            RealmAuditLog.OLD_VALUE: old_value,
            RealmAuditLog.NEW_VALUE: database_value,
            "property": database_property_name,
        },
    )

    # This first in_home_view event is deprecated and will be removed
    # once clients are migrated to handle the subscription update event
    # with is_muted as the property name.
    if database_property_name == "is_muted":
        event_value = not database_value
        in_home_view_event = dict(
            type="subscription",
            op="update",
            property="in_home_view",
            value=event_value,
            stream_id=stream.id,
        )

        send_event_on_commit(user_profile.realm,
                             in_home_view_event, [user_profile.id])

    event = dict(
        type="subscription",
        op="update",
        property=database_property_name,
        value=database_value,
        stream_id=stream.id,
    )
    send_event_on_commit(user_profile.realm, event, [user_profile.id])
