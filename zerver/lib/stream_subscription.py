import itertools
from collections import defaultdict
from dataclasses import dataclass
from operator import itemgetter
from typing import Any, Dict, List, Optional, Set

from django.db.models.query import QuerySet

from zerver.models import Realm, Recipient, Stream, Subscription, UserProfile


@dataclass
class SubInfo:
    user: UserProfile
    sub: Subscription
    stream: Stream

@dataclass
class SubscriberPeerInfo:
    subscribed_ids: Dict[int, Set[int]]
    private_peer_dict: Dict[int, Set[int]]

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
    users: List[UserProfile],
    streams: List[Stream],
) -> Dict[int, List[SubInfo]]:

    stream_ids = {stream.id for stream in streams}

    subs = Subscription.objects.filter(
        user_profile__in=users,
        recipient__type=Recipient.STREAM,
        recipient__type_id__in=stream_ids,
        active=True,
    ).only('user_profile_id', 'recipient_id')

    stream_map = {stream.recipient_id: stream for stream in streams}
    user_map = {user.id: user for user in users}

    result: Dict[int, List[SubInfo]] = {user.id: [] for user in users}

    for sub in subs:
        user_id = sub.user_profile_id
        user = user_map[user_id]
        recipient_id = sub.recipient_id
        stream = stream_map[recipient_id]
        sub_info = SubInfo(
            user=user,
            sub=sub,
            stream=stream,
        )

        result[user_id].append(sub_info)

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

        private_peer_dict:
            These are the folks that need to know about a new subscriber.
            It's usually a superset of the subscribers.

            Note that we only compute this for PRIVATE streams.  We
            let other code handle peers for public streams, since the
            peers for all public streams are actually the same group
            of users, and downstream code can use that property of
            public streams to avoid extra work.
    """

    subscribed_ids = {}
    private_peer_dict = {}

    private_stream_ids = {stream.id for stream in streams if stream.invite_only}
    public_stream_ids = {stream.id for stream in streams if not stream.invite_only}

    stream_user_ids = get_user_ids_for_streams(private_stream_ids | public_stream_ids)

    if private_stream_ids:
        realm_admin_ids = {user.id for user in realm.get_admin_users_and_bots()}

        for stream_id in private_stream_ids:
            # This is the same business rule as we use in
            # bulk_get_private_peers. Realm admins can see all private stream
            # subscribers.
            subscribed_user_ids = stream_user_ids.get(stream_id, set())
            subscribed_ids[stream_id] = subscribed_user_ids
            private_peer_dict[stream_id] = subscribed_user_ids | realm_admin_ids

    for stream_id in public_stream_ids:
        subscribed_user_ids = stream_user_ids.get(stream_id, set())
        subscribed_ids[stream_id] = subscribed_user_ids

    return SubscriberPeerInfo(
        subscribed_ids=subscribed_ids,
        private_peer_dict=private_peer_dict,
    )

def bulk_get_private_peers(
    realm: Realm,
    private_streams: List[Stream],
) -> Dict[int, Set[int]]:

    if not private_streams:
        return {}

    for stream in private_streams:
        # Our caller should only pass us private streams.
        assert stream.invite_only

    peer_ids: Dict[int, Set[int]] = {}

    realm_admin_ids = {user.id for user in realm.get_admin_users_and_bots()}

    stream_ids = {stream.id for stream in private_streams}
    stream_user_ids = get_user_ids_for_streams(stream_ids)

    for stream in private_streams:
        # This is the same business rule as we use in
        # bulk_get_subscriber_peer_info.  Realm admins can see all private
        # stream subscribers.
        subscribed_user_ids = stream_user_ids.get(stream.id, set())
        peer_ids[stream.id] = subscribed_user_ids | realm_admin_ids

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
