import logging
from collections import defaultdict
from collections.abc import Callable
from datetime import datetime
from typing import TypedDict

from django.db import connection, transaction
from django.db.models import QuerySet
from django.utils.timezone import now as timezone_now
from psycopg2.sql import SQL, Literal
from sqlalchemy.sql import ClauseElement, and_, column, not_, or_
from sqlalchemy.types import Integer

from zerver.lib.timestamp import datetime_to_timestamp
from zerver.lib.topic_sqlalchemy import topic_match_sa
from zerver.lib.types import UserTopicDict
from zerver.models import Recipient, Subscription, UserProfile, UserTopic
from zerver.models.streams import get_stream


def get_user_topics(
    user_profile: UserProfile,
    include_deactivated: bool = False,
    include_stream_name: bool = False,
    visibility_policy: int | None = None,
) -> list[UserTopicDict]:
    """
    Fetches UserTopic objects associated with the target user.
    * include_deactivated: Whether to include those associated with
      deactivated streams.
    * include_stream_name: Whether to include stream names in the
      returned dictionaries.
    * visibility_policy: If specified, returns only UserTopic objects
      with the specified visibility_policy value.
    """
    query = UserTopic.objects.filter(user_profile=user_profile)

    if visibility_policy is not None:
        query = query.filter(visibility_policy=visibility_policy)

    # Exclude user topics that are part of deactivated streams unless
    # explicitly requested.
    if not include_deactivated:
        query = query.filter(stream__deactivated=False)

    rows = query.values(
        "stream_id", "stream__name", "topic_name", "last_updated", "visibility_policy"
    )

    result = []
    for row in rows:
        user_topic_dict: UserTopicDict = {
            "stream_id": row["stream_id"],
            "topic_name": row["topic_name"],
            "visibility_policy": row["visibility_policy"],
            "last_updated": datetime_to_timestamp(row["last_updated"]),
        }

        if include_stream_name:
            user_topic_dict["stream__name"] = row["stream__name"]

        result.append(user_topic_dict)

    return result


def get_topic_mutes(
    user_profile: UserProfile, include_deactivated: bool = False
) -> list[list[str | int]]:
    user_topics = get_user_topics(
        user_profile=user_profile,
        include_deactivated=include_deactivated,
        include_stream_name=True,
        visibility_policy=UserTopic.VisibilityPolicy.MUTED,
    )

    return [
        [user_topic["stream__name"], user_topic["topic_name"], user_topic["last_updated"]]
        for user_topic in user_topics
    ]


@transaction.atomic(savepoint=False)
def set_topic_visibility_policy(
    user_profile: UserProfile,
    topics: list[list[str]],
    visibility_policy: int,
    last_updated: datetime | None = None,
) -> None:
    """
    This is only used in tests.
    """

    UserTopic.objects.filter(
        user_profile=user_profile,
        visibility_policy=visibility_policy,
    ).delete()

    if last_updated is None:
        last_updated = timezone_now()
    for stream_name, topic_name in topics:
        stream = get_stream(stream_name, user_profile.realm)
        recipient_id = stream.recipient_id
        assert recipient_id is not None

        bulk_set_user_topic_visibility_policy_in_database(
            user_profiles=[user_profile],
            stream_id=stream.id,
            recipient_id=recipient_id,
            topic_name=topic_name,
            visibility_policy=visibility_policy,
            last_updated=last_updated,
        )


def get_topic_visibility_policy(
    user_profile: UserProfile,
    stream_id: int,
    topic_name: str,
) -> int:
    try:
        user_topic = UserTopic.objects.get(
            user_profile=user_profile, stream_id=stream_id, topic_name__iexact=topic_name
        )
        visibility_policy = user_topic.visibility_policy
    except UserTopic.DoesNotExist:
        visibility_policy = UserTopic.VisibilityPolicy.INHERIT
    return visibility_policy


@transaction.atomic(savepoint=False)
def bulk_set_user_topic_visibility_policy_in_database(
    user_profiles: list[UserProfile],
    stream_id: int,
    topic_name: str,
    *,
    visibility_policy: int,
    recipient_id: int | None = None,
    last_updated: datetime | None = None,
) -> list[UserProfile]:
    # returns the list of user_profiles whose user_topic row
    # is either deleted, updated, or created.
    rows = UserTopic.objects.filter(
        user_profile__in=user_profiles,
        stream_id=stream_id,
        topic_name__iexact=topic_name,
    ).select_related("user_profile", "user_profile__realm")

    user_profiles_with_visibility_policy = [row.user_profile for row in rows]
    user_profiles_without_visibility_policy = list(
        set(user_profiles) - set(user_profiles_with_visibility_policy)
    )

    if visibility_policy == UserTopic.VisibilityPolicy.INHERIT:
        for user_profile in user_profiles_without_visibility_policy:
            # The user doesn't already have a visibility_policy for this topic.
            logging.info(
                "User %s tried to remove visibility_policy, which actually doesn't exist",
                user_profile.id,
            )
        rows.delete()
        return user_profiles_with_visibility_policy

    assert last_updated is not None
    assert recipient_id is not None

    user_profiles_seeking_user_topic_update_or_create: list[UserProfile] = (
        user_profiles_without_visibility_policy
    )
    for row in rows:
        if row.visibility_policy == visibility_policy:
            logging.info(
                "User %s tried to set visibility_policy to its current value of %s",
                row.user_profile_id,
                visibility_policy,
            )
            continue
        # The request is to just 'update' the visibility policy of a topic
        user_profiles_seeking_user_topic_update_or_create.append(row.user_profile)

    if user_profiles_seeking_user_topic_update_or_create:
        user_profile_ids_array = SQL("ARRAY[{}]").format(
            SQL(", ").join(
                [
                    Literal(user_profile.id)
                    for user_profile in user_profiles_seeking_user_topic_update_or_create
                ]
            )
        )

        query = SQL("""
            INSERT INTO zerver_usertopic(user_profile_id, stream_id, recipient_id, topic_name, last_updated, visibility_policy)
            SELECT * FROM UNNEST({user_profile_ids_array}) AS user_profile(user_profile_id)
            CROSS JOIN (VALUES ({stream_id}, {recipient_id}, {topic_name}, {last_updated}, {visibility_policy}))
            AS other_values(stream_id, recipient_id, topic_name, last_updated, visibility_policy)
            ON CONFLICT (user_profile_id, stream_id, lower(topic_name)) DO UPDATE SET
            last_updated = EXCLUDED.last_updated,
            visibility_policy = EXCLUDED.visibility_policy;
        """).format(
            user_profile_ids_array=user_profile_ids_array,
            stream_id=Literal(stream_id),
            recipient_id=Literal(recipient_id),
            topic_name=Literal(topic_name),
            last_updated=Literal(last_updated),
            visibility_policy=Literal(visibility_policy),
        )

        with connection.cursor() as cursor:
            cursor.execute(query)

    return user_profiles_seeking_user_topic_update_or_create


def topic_has_visibility_policy(
    user_profile: UserProfile, stream_id: int, topic_name: str, visibility_policy: int
) -> bool:
    if visibility_policy == UserTopic.VisibilityPolicy.INHERIT:
        has_user_topic_row = UserTopic.objects.filter(
            user_profile=user_profile, stream_id=stream_id, topic_name__iexact=topic_name
        ).exists()
        return not has_user_topic_row
    has_visibility_policy = UserTopic.objects.filter(
        user_profile=user_profile,
        stream_id=stream_id,
        topic_name__iexact=topic_name,
        visibility_policy=visibility_policy,
    ).exists()
    return has_visibility_policy


def exclude_stream_and_topic_mutes(
    conditions: list[ClauseElement], user_profile: UserProfile, stream_id: int | None
) -> list[ClauseElement]:
    # Note: Unlike get_topic_mutes, here we always want to
    # consider topics in deactivated streams, so they are
    # never filtered from the query in this method.
    query = UserTopic.objects.filter(
        user_profile=user_profile,
        visibility_policy=UserTopic.VisibilityPolicy.MUTED,
    )

    if stream_id is not None:
        # If we are narrowed to a stream, we can optimize the query
        # by not considering topic mutes outside the stream.
        query = query.filter(stream_id=stream_id)

    excluded_topic_rows = query.values(
        "recipient_id",
        "topic_name",
    )

    class RecipientTopicDict(TypedDict):
        recipient_id: int
        topic_name: str

    def topic_cond(row: RecipientTopicDict) -> ClauseElement:
        recipient_id = row["recipient_id"]
        topic_name = row["topic_name"]
        stream_cond = column("recipient_id", Integer) == recipient_id
        topic_cond = topic_match_sa(topic_name)
        return and_(stream_cond, topic_cond)

    # Add this query later to reduce the number of messages it has to run on.
    if excluded_topic_rows:
        exclude_muted_topics_condition = not_(or_(*map(topic_cond, excluded_topic_rows)))
        conditions = [*conditions, exclude_muted_topics_condition]

    # Channel-level muting only applies when looking at views that
    # include multiple channels, since we do want users to be able to
    # browser messages within a muted channel.
    if stream_id is None:
        rows = Subscription.objects.filter(
            user_profile=user_profile,
            active=True,
            is_muted=True,
            recipient__type=Recipient.STREAM,
        ).values("recipient_id")
        muted_recipient_ids = [row["recipient_id"] for row in rows]

        if len(muted_recipient_ids) == 0:
            return conditions

        # Add entries with visibility_policy FOLLOWED or UNMUTED in muted_recipient_ids
        query = UserTopic.objects.filter(
            user_profile=user_profile,
            recipient_id__in=muted_recipient_ids,
            visibility_policy__in=[
                UserTopic.VisibilityPolicy.FOLLOWED,
                UserTopic.VisibilityPolicy.UNMUTED,
            ],
        )

        included_topic_rows = query.values(
            "recipient_id",
            "topic_name",
        )

        # Exclude muted_recipient_ids unless they match include_followed_or_unmuted_topics_condition
        muted_stream_condition = column("recipient_id", Integer).in_(muted_recipient_ids)

        if included_topic_rows:
            include_followed_or_unmuted_topics_condition = or_(
                *map(topic_cond, included_topic_rows)
            )

            exclude_muted_streams_condition = not_(
                and_(
                    muted_stream_condition,
                    not_(include_followed_or_unmuted_topics_condition),
                )
            )
        else:
            # If no included topics, exclude all muted streams
            exclude_muted_streams_condition = not_(muted_stream_condition)

        conditions = [*conditions, exclude_muted_streams_condition]

    return conditions


def build_get_topic_visibility_policy(
    user_profile: UserProfile,
) -> Callable[[int, str], int]:
    """Prefetch the visibility policies the user has configured for
    various topics.

    The prefetching helps to avoid the db queries later in the loop
    to determine the user's visibility policy for a topic.
    """
    rows = UserTopic.objects.filter(user_profile=user_profile).values(
        "recipient_id",
        "topic_name",
        "visibility_policy",
    )

    topic_to_visibility_policy: dict[tuple[int, str], int] = defaultdict(int)
    for row in rows:
        recipient_id = row["recipient_id"]
        topic_name = row["topic_name"]
        visibility_policy = row["visibility_policy"]
        topic_to_visibility_policy[(recipient_id, topic_name)] = visibility_policy

    def get_topic_visibility_policy(recipient_id: int, topic_name: str) -> int:
        return topic_to_visibility_policy[(recipient_id, topic_name.lower())]

    return get_topic_visibility_policy


def get_users_with_user_topic_visibility_policy(
    stream_id: int, topic_name: str
) -> QuerySet[UserTopic]:
    return UserTopic.objects.filter(
        stream_id=stream_id, topic_name__iexact=topic_name
    ).select_related("user_profile", "user_profile__realm")
