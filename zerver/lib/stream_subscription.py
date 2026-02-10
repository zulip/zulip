import itertools
from collections import defaultdict
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from operator import itemgetter
from typing import Any, Literal

from django.db import connection, transaction
from django.db.models import F, Q, QuerySet
from psycopg2 import sql
from psycopg2.extras import execute_values

from zerver.models import AlertWord, Recipient, Stream, Subscription, UserProfile, UserTopic


@dataclass
class SubInfo:
    user: UserProfile
    sub: Subscription
    stream: Stream


@dataclass
class SubscriberPeerInfo:
    subscribed_ids: dict[int, set[int]]
    private_peer_dict: dict[int, set[int]]


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


def get_active_subscriptions_for_stream_ids(stream_ids: set[int]) -> QuerySet[Subscription]:
    return Subscription.objects.filter(
        recipient__type=Recipient.STREAM,
        recipient__type_id__in=stream_ids,
        active=True,
        is_user_active=True,
    )


def get_subscribed_stream_ids_for_user(
    user_profile: UserProfile,
) -> QuerySet[Subscription, int]:
    return Subscription.objects.filter(
        user_profile_id=user_profile,
        recipient__type=Recipient.STREAM,
        active=True,
    ).values_list("recipient__type_id", flat=True)


def get_subscribed_stream_recipient_ids_for_user(
    user_profile: UserProfile,
) -> QuerySet[Subscription, int]:
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


def get_user_subscribed_streams(user_profile: UserProfile) -> QuerySet[Stream]:
    return Stream.objects.filter(
        recipient_id__in=get_subscribed_stream_recipient_ids_for_user(user_profile)
    )


def get_used_colors_for_user_ids(user_ids: list[int]) -> dict[int, set[str]]:
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

    result: dict[int, set[str]] = defaultdict(set)

    for row in query:
        assert row["color"] is not None
        result[row["user_profile_id"]].add(row["color"])

    return result


def get_bulk_stream_subscriber_info(
    users: list[UserProfile],
    streams: list[Stream],
) -> dict[int, list[SubInfo]]:
    stream_ids = {stream.id for stream in streams}

    subs = Subscription.objects.filter(
        user_profile__in=users,
        recipient__type=Recipient.STREAM,
        recipient__type_id__in=stream_ids,
        active=True,
    ).only("user_profile_id", "recipient_id")

    stream_map = {stream.recipient_id: stream for stream in streams}
    user_map = {user.id: user for user in users}

    result: dict[int, list[SubInfo]] = {user.id: [] for user in users}

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


def get_user_ids_for_stream_query(
    query: QuerySet[Subscription, Subscription],
) -> dict[int, set[int]]:
    all_subs = query.values(
        "recipient__type_id",
        "user_profile_id",
    ).order_by(
        "recipient__type_id",
    )

    get_stream_id = itemgetter("recipient__type_id")

    result: dict[int, set[int]] = defaultdict(set)
    for stream_id, rows in itertools.groupby(all_subs, get_stream_id):
        user_ids = {row["user_profile_id"] for row in rows}
        result[stream_id] = user_ids

    return result


def get_user_ids_for_streams(stream_ids: set[int]) -> dict[int, set[int]]:
    return get_user_ids_for_stream_query(get_active_subscriptions_for_stream_ids(stream_ids))


def get_guest_user_ids_for_streams(stream_ids: set[int]) -> dict[int, set[int]]:
    return get_user_ids_for_stream_query(
        get_active_subscriptions_for_stream_ids(stream_ids).filter(
            user_profile__role=UserProfile.ROLE_GUEST
        )
    )


def get_users_for_streams(stream_ids: set[int]) -> dict[int, set[UserProfile]]:
    all_subs = (
        get_active_subscriptions_for_stream_ids(stream_ids)
        .select_related("user_profile", "recipient")
        .order_by("recipient__type_id")
    )

    result: dict[int, set[UserProfile]] = defaultdict(set)
    for stream_id, rows in itertools.groupby(all_subs, key=lambda obj: obj.recipient.type_id):
        users = {row.user_profile for row in rows}
        result[stream_id] = users

    return result


def handle_stream_notifications_compatibility(
    user_profile: UserProfile | None,
    stream_dict: dict[str, Any],
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


def subscriber_ids_with_stream_history_access(stream: Stream) -> set[int]:
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


def update_all_subscriber_counts_for_user(
    user_profile: UserProfile, direction: Literal[1, -1]
) -> None:
    """
    Increment/Decrement number of stream subscribers by 1, when reactivating/deactivating user.

    direction -> 1=increment, -1=decrement
    """
    get_user_subscribed_streams(user_profile).update(
        subscriber_count=F("subscriber_count") + direction
    )


def bulk_update_subscriber_counts(
    direction: Literal[1, -1],
    streams: dict[int, set[int]],
) -> None:
    """Increment/Decrement number of stream subscribers for multiple users.

    direction -> 1=increment, -1=decrement
    """
    if len(streams) == 0:
        return

    # list of tuples (stream_id, delta_subscribers) used as the
    # columns of the temporary table delta_table.
    stream_delta_values = [
        (stream_id, len(subscribers) * direction) for stream_id, subscribers in streams.items()
    ]

    # The goal here is to update subscriber_count in a bulk efficient way,
    # letting the database handle the deltas to avoid some race conditions.
    #
    # But unlike update_all_subscriber_counts_for_user which uses F()
    # for a single delta value, we can't use F() to apply different
    # deltas per row in a single update using ORM, so we use a raw
    # SQL query.
    query = sql.SQL(
        """UPDATE {stream_table}
            SET subscriber_count = {stream_table}.subscriber_count + delta_table.delta
            FROM (VALUES %s) AS delta_table(id, delta)
            WHERE {stream_table}.id = delta_table.id;
        """
    ).format(stream_table=sql.Identifier(Stream._meta.db_table))

    cursor = connection.cursor()
    execute_values(cursor.cursor, query, stream_delta_values)


@transaction.atomic(savepoint=False)
def create_stream_subscription(
    user_profile: UserProfile,
    recipient: Recipient,
    stream: Stream,
    color: str = Subscription.DEFAULT_STREAM_COLOR,
) -> None:
    """
    Creates a single stream Subscription object, incrementing
    stream.subscriber_count by 1 if user is active, in the same
    transaction.
    """

    # We only create a stream subscription in this function
    assert recipient.type == Recipient.STREAM

    Subscription.objects.create(
        recipient=recipient,
        user_profile=user_profile,
        is_user_active=user_profile.is_active,
        color=color,
    )

    if user_profile.is_active:
        Stream.objects.filter(id=stream.id).update(subscriber_count=F("subscriber_count") + 1)


@transaction.atomic(savepoint=False)
def bulk_create_stream_subscriptions(  # nocoverage
    subs: list[Subscription], streams: dict[int, set[int]]
) -> None:
    """
    Bulk create subscripions for streams, incrementing
    stream.subscriber_count in the same transaction.

    Currently only used in populate_db.
    """
    Subscription.objects.bulk_create(subs)
    bulk_update_subscriber_counts(direction=1, streams=streams)
