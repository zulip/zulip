import itertools
from collections import defaultdict
from dataclasses import dataclass
from operator import itemgetter
from typing import Any, Dict, List, Optional, Set, Tuple

from django.db.models.query import QuerySet

from zerver.models import (
    Realm,
    Recipient,
    Stream,
    Subscription,
    UserProfile,
    active_non_guest_user_ids,
)


@dataclass
class SubscriberPeerInfo:
    subscribed_ids: Dict[int, Set[int]]
    peer_ids: Dict[int, Set[int]]

def get_active_subscriptions_for_stream_id(stream_id: int) -> QuerySet:
    # TODO: Change return type to QuerySet[Subscription]
    return Subscription.objects.filter(
        recipient__type=Recipient.STREAM,
        recipient__type_id=stream_id,
        active=True,
    )

def get_active_subscriptions_for_stream_ids(stream_ids: Set[int]) -> QuerySet:
    # TODO: Change return type to QuerySet[Subscription]
    return Subscription.objects.filter(
        recipient__type=Recipient.STREAM,
        recipient__type_id__in=stream_ids,
        active=True,
    )

def get_subscribed_stream_ids_for_user(user_profile: UserProfile) -> QuerySet:
    return Subscription.objects.filter(
        user_profile_id=user_profile,
        recipient__type=Recipient.STREAM,
        active=True,
    ).values_list('recipient__type_id', flat=True)

def get_stream_subscriptions_for_user(user_profile: UserProfile) -> QuerySet:
    # TODO: Change return type to QuerySet[Subscription]
    return Subscription.objects.filter(
        user_profile=user_profile,
        recipient__type=Recipient.STREAM,
    )

def get_stream_subscriptions_for_users(user_profiles: List[UserProfile]) -> QuerySet:
    # TODO: Change return type to QuerySet[Subscription]
    return Subscription.objects.filter(
        user_profile__in=user_profiles,
        recipient__type=Recipient.STREAM,
    )

def get_bulk_stream_subscriber_info(
        user_profiles: List[UserProfile],
        stream_dict: Dict[int, Stream]) -> Dict[int, List[Tuple[Subscription, Stream]]]:

    stream_ids = stream_dict.keys()

    result: Dict[int, List[Tuple[Subscription, Stream]]] = {
        user_profile.id: []
        for user_profile in user_profiles
    }

    subs = Subscription.objects.filter(
        user_profile__in=user_profiles,
        recipient__type=Recipient.STREAM,
        recipient__type_id__in=stream_ids,
        active=True,
    ).select_related('user_profile', 'recipient')

    for sub in subs:
        user_profile_id = sub.user_profile_id
        stream_id = sub.recipient.type_id
        stream = stream_dict[stream_id]
        result[user_profile_id].append((sub, stream))

    return result

def num_subscribers_for_stream_id(stream_id: int) -> int:
    return get_active_subscriptions_for_stream_id(stream_id).filter(
        user_profile__is_active=True,
    ).count()

def get_user_ids_for_streams(stream_ids: Set[int]) -> Dict[int, Set[int]]:
    all_subs = get_active_subscriptions_for_stream_ids(stream_ids).filter(
        user_profile__is_active=True,
    ).values(
        'recipient__type_id',
        'user_profile_id',
    ).order_by(
        'recipient__type_id',
    )

    get_stream_id = itemgetter('recipient__type_id')

    result: Dict[int, Set[int]] = defaultdict(set)
    for stream_id, rows in itertools.groupby(all_subs, get_stream_id):
        user_ids = {row['user_profile_id'] for row in rows}
        result[stream_id] = user_ids

    return result

def bulk_get_subscriber_peer_info(
    realm: Realm,
    streams: List[Stream],
) -> SubscriberPeerInfo:
    """
    Glossary:

        subscribed_ids:
            This shows the users who are actually subscribed to the
            stream, which we generally send to the person subscribing
            to the stream.

        peer_ids:
            These are the folks that need to know about a new subscriber.
            It's usually a superset of the subscribers.
    """

    subscribed_ids = {}
    peer_ids = {}

    private_stream_ids = {stream.id for stream in streams if stream.invite_only}
    public_stream_ids = {stream.id for stream in streams if not stream.invite_only}

    stream_user_ids = get_user_ids_for_streams(private_stream_ids | public_stream_ids)

    if private_stream_ids:
        realm_admin_ids = {user.id for user in realm.get_admin_users_and_bots()}

        for stream_id in private_stream_ids:
            subscribed_user_ids = stream_user_ids.get(stream_id, set())
            subscribed_ids[stream_id] = subscribed_user_ids
            peer_ids[stream_id] = subscribed_user_ids | realm_admin_ids

    if public_stream_ids:
        non_guests = active_non_guest_user_ids(realm.id)
        for stream_id in public_stream_ids:
            subscribed_user_ids = stream_user_ids.get(stream_id, set())
            subscribed_ids[stream_id] = subscribed_user_ids
            peer_ids[stream_id] = set(non_guests)

    return SubscriberPeerInfo(
        subscribed_ids=subscribed_ids,
        peer_ids=peer_ids,
    )

def bulk_get_peers(
    realm: Realm,
    streams: List[Stream],
) -> Dict[int, Set[int]]:
    # This is almost a subset of bulk_get_subscriber_peer_info,
    # with the nuance that we don't have to query subscribers
    # for public streams.  (The other functions tries to save
    # a query hop.)

    peer_ids = {}

    private_stream_ids = {stream.id for stream in streams if stream.invite_only}
    public_stream_ids = {stream.id for stream in streams if not stream.invite_only}

    if private_stream_ids:
        realm_admin_ids = {user.id for user in realm.get_admin_users_and_bots()}
        stream_user_ids = get_user_ids_for_streams(private_stream_ids)

        for stream_id in private_stream_ids:
            subscribed_user_ids = stream_user_ids.get(stream_id, set())
            peer_ids[stream_id] = subscribed_user_ids | realm_admin_ids

    if public_stream_ids:
        non_guests = active_non_guest_user_ids(realm.id)
        for stream_id in public_stream_ids:
            peer_ids[stream_id] = set(non_guests)

    return peer_ids

def handle_stream_notifications_compatibility(user_profile: Optional[UserProfile],
                                              stream_dict: Dict[str, Any],
                                              notification_settings_null: bool) -> None:
    # Old versions of the mobile apps don't support `None` as a
    # value for the stream-level notifications properties, so we
    # have to handle the normally frontend-side defaults for these
    # settings here for those older clients.
    #
    # Note that this situation results in these older mobile apps
    # having a subtle bug where changes to the user-level stream
    # notification defaults will not properly propagate to the
    # mobile app "stream notification settings" UI until the app
    # re-registers.  This is an acceptable level of
    # backwards-compatibility problem in our view.
    assert not notification_settings_null

    for notification_type in ["desktop_notifications", "audible_notifications",
                              "push_notifications", "email_notifications"]:
        # Values of true/false are supported by older clients.
        if stream_dict[notification_type] is not None:
            continue
        target_attr = "enable_stream_" + notification_type
        stream_dict[notification_type] = False if user_profile is None else getattr(user_profile, target_attr)
