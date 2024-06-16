import itertools
from collections import defaultdict
from dataclasses import dataclass
from operator import itemgetter
from typing import AbstractSet, Any, Collection, Dict, List, Optional, Set

from django.db.models import Q, QuerySet
from django_stubs_ext import ValuesQuerySet

from zerver.models import AlertWord, Realm, Recipient, Stream, Subscription, UserProfile, UserTopic


@dataclass
class SubInfo:
    user: UserProfile
    sub: Subscription
    stream: Stream


@dataclass
class SubscriberPeerInfo:
    subscribed_ids: Dict[int, Set[int]]
    private_peer_dict: Dict[int, Set[int]]


def get_active_subscriptions_for_stream_id(
    stream_id: int, *, include_deactivated_users: bool
) -> QuerySet[Subscription]:
    query = Subscription.objects.filter(
        recipient__type=Recipient.STREAM,
        recipient__type_id=stream_id,
        active=True,
    )
    if not include_deactivated_users:
        # Note that non-active users may still have "active" subscriptions, because we
        # want to be able to easily reactivate them with their old subscriptions.  This
        # is why the query here has to look at the is_user_active flag.
        query = query.filter(is_user_active=True)

    return query


def get_active_subscriptions_for_stream_ids(stream_ids: Set[int]) -> QuerySet[Subscription]:
    return Subscription.objects.filter(
        recipient__type=Recipient.STREAM,
        recipient__type_id__in=stream_ids,
        active=True,
        is_user_active=True,
    )


def get_subscribed_stream_ids_for_user(
    user_profile: UserProfile,
) -> ValuesQuerySet[Subscription, int]:
    return Subscription.objects.filter(
        user_profile_id=user_profile,
        recipient__type=Recipient.STREAM,
        active=True,
    ).values_list("recipient__type_id", flat=True)


def get_subscribed_stream_recipient_ids_for_user(
    user_profile: UserProfile,
) -> ValuesQuerySet[Subscription, int]:
    return Subscription.objects.filter(
        user_profile_id=user_profile,
        recipient__type=Recipient.STREAM,
        active=True,
    ).values_list("recipient_id", flat=True)


def get_stream_subscriptions_for_user(user_profile: UserProfile) -> QuerySet[Subscription]:
    return Subscription.objects.filter(
        user_profile=user_profile,
        recipient__type=Recipient.STREAM,
    )


def get_used_colors_for_user_ids(user_ids: List[int]) -> Dict[int, Set[str]]:
    """Fetch which stream colors have already been used for each user in
    user_ids. Uses an optimized query designed to support picking
    colors when bulk-adding users to streams, which requires
    inspecting all Subscription objects for the users, which can often
    end up being all Subscription objects in the realm.
    """
    query = (
        Subscription.objects.filter(
            user_profile_id__in=user_ids,
            recipient__type=Recipient.STREAM,
        )
        .values("user_profile_id", "color")
        .distinct()
    )

    result: Dict[int, Set[str]] = defaultdict(set)

    for row in query:
        assert row["color"] is not None
        result[row["user_profile_id"]].add(row["color"])

    return result


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
    ).only("user_profile_id", "recipient_id")

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
    return get_active_subscriptions_for_stream_id(
        stream_id, include_deactivated_users=False
    ).count()


def get_user_ids_for_streams(stream_ids: Set[int]) -> Dict[int, Set[int]]:
    all_subs = (
        get_active_subscriptions_for_stream_ids(stream_ids)
        .values(
            "recipient__type_id",
            "user_profile_id",
        )
        .order_by(
            "recipient__type_id",
        )
    )

    get_stream_id = itemgetter("recipient__type_id")

    result: Dict[int, Set[int]] = defaultdict(set)
    for stream_id, rows in itertools.groupby(all_subs, get_stream_id):
        user_ids = {row["user_profile_id"] for row in rows}
        result[stream_id] = user_ids

    return result


def get_users_for_streams(stream_ids: Set[int]) -> Dict[int, Set[UserProfile]]:
    all_subs = (
        get_active_subscriptions_for_stream_ids(stream_ids)
        .select_related("user_profile", "recipient")
        .order_by("recipient__type_id")
    )

    result: Dict[int, Set[UserProfile]] = defaultdict(set)
    for stream_id, rows in itertools.groupby(all_subs, key=lambda obj: obj.recipient.type_id):
        users = {row.user_profile for row in rows}
        result[stream_id] = users

    return result


def bulk_get_subscriber_peer_info(
    realm: Realm,
    streams: Collection[Stream] | QuerySet[Stream],
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
            # Realm admins can see all private stream
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


def handle_stream_notifications_compatibility(
    user_profile: Optional[UserProfile],
    stream_dict: Dict[str, Any],
    notification_settings_null: bool,
) -> None:
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

    for notification_type in [
        "desktop_notifications",
        "audible_notifications",
        "push_notifications",
        "email_notifications",
    ]:
        # Values of true/false are supported by older clients.
        if stream_dict[notification_type] is not None:
            continue
        target_attr = "enable_stream_" + notification_type
        stream_dict[notification_type] = (
            False if user_profile is None else getattr(user_profile, target_attr)
        )


def subscriber_ids_with_stream_history_access(stream: Stream) -> Set[int]:
    """Returns the set of active user IDs who can access any message
    history on this stream (regardless of whether they have a
    UserMessage) based on the stream's configuration.

    1. if !history_public_to_subscribers:
          History is not available to anyone
    2. if history_public_to_subscribers:
          All subscribers can access the history including guests

    The results of this function need to be kept consistent with
    what can_access_stream_history would dictate.

    """

    if not stream.is_history_public_to_subscribers():
        return set()

    return set(
        get_active_subscriptions_for_stream_id(
            stream.id, include_deactivated_users=False
        ).values_list("user_profile_id", flat=True)
    )


def get_subscriptions_for_send_message(
    *,
    realm_id: int,
    stream_id: int,
    topic_name: str,
    possible_stream_wildcard_mention: bool,
    topic_participant_user_ids: AbstractSet[int],
    possibly_mentioned_user_ids: AbstractSet[int],
) -> QuerySet[Subscription]:
    """This function optimizes an important use case for large
    streams. Open realms often have many long_term_idle users, which
    can result in 10,000s of long_term_idle recipients in default
    streams. do_send_messages has an optimization to avoid doing work
    for long_term_idle unless message flags or notifications should be
    generated.

    However, it's expensive even to fetch and process them all in
    Python at all. This function returns all recipients of a stream
    message that could possibly require action in the send-message
    codepath.

    Basically, it returns all subscribers, excluding all long-term
    idle users who it can prove will not receive a UserMessage row or
    notification for the message (i.e. no alert words, mentions, or
    email/push notifications are configured) and thus are not needed
    for processing the message send.

    Critically, this function is called before the Markdown
    processor. As a result, it returns all subscribers who have ANY
    configured alert words, even if their alert words aren't present
    in the message. Similarly, it returns all subscribers who match
    the "possible mention" parameters.

    Downstream logic, which runs after the Markdown processor has
    parsed the message, will do the precise determination.
    """

    query = get_active_subscriptions_for_stream_id(
        stream_id,
        include_deactivated_users=False,
    )

    if possible_stream_wildcard_mention:
        return query

    query = query.filter(
        Q(user_profile__long_term_idle=False)
        | Q(push_notifications=True)
        | (Q(push_notifications=None) & Q(user_profile__enable_stream_push_notifications=True))
        | Q(email_notifications=True)
        | (Q(email_notifications=None) & Q(user_profile__enable_stream_email_notifications=True))
        | Q(user_profile_id__in=possibly_mentioned_user_ids)
        | Q(user_profile_id__in=topic_participant_user_ids)
        | Q(
            user_profile_id__in=AlertWord.objects.filter(realm_id=realm_id).values_list(
                "user_profile_id"
            )
        )
        | Q(
            user_profile_id__in=UserTopic.objects.filter(
                stream_id=stream_id,
                topic_name__iexact=topic_name,
                visibility_policy=UserTopic.VisibilityPolicy.FOLLOWED,
            ).values_list("user_profile_id")
        )
    )
    return query
