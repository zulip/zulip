import datetime
from typing import Callable, List, Optional, Tuple, TypedDict

from django.db.models import QuerySet
from django.utils.timezone import now as timezone_now
from sqlalchemy.sql import ClauseElement, and_, column, not_, or_
from sqlalchemy.types import Integer

from zerver.lib.timestamp import datetime_to_timestamp
from zerver.lib.topic import topic_match_sa
from zerver.lib.types import UserTopicDict
from zerver.models import UserProfile, UserTopic, get_stream


def get_user_topics(
    user_profile: UserProfile,
    include_deactivated: bool = False,
    include_stream_name: bool = False,
    visibility_policy: Optional[int] = None,
) -> List[UserTopicDict]:
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
) -> List[Tuple[str, str, int]]:
    user_topics = get_user_topics(
        user_profile=user_profile,
        include_deactivated=include_deactivated,
        include_stream_name=True,
        visibility_policy=UserTopic.MUTED,
    )

    return [
        (user_topic["stream__name"], user_topic["topic_name"], user_topic["last_updated"])
        for user_topic in user_topics
    ]


def set_topic_mutes(
    user_profile: UserProfile,
    muted_topics: List[List[str]],
    date_muted: Optional[datetime.datetime] = None,
) -> None:
    """
    This is only used in tests.
    """

    UserTopic.objects.filter(
        user_profile=user_profile,
        visibility_policy=UserTopic.MUTED,
    ).delete()

    if date_muted is None:
        date_muted = timezone_now()
    for stream_name, topic_name in muted_topics:
        stream = get_stream(stream_name, user_profile.realm)
        recipient_id = stream.recipient_id
        assert recipient_id is not None

        add_topic_mute(
            user_profile=user_profile,
            stream_id=stream.id,
            recipient_id=recipient_id,
            topic_name=topic_name,
            date_muted=date_muted,
        )


def add_topic_mute(
    user_profile: UserProfile,
    stream_id: int,
    recipient_id: int,
    topic_name: str,
    date_muted: Optional[datetime.datetime] = None,
    ignore_duplicate: bool = False,
) -> None:
    if date_muted is None:
        date_muted = timezone_now()
    UserTopic.objects.bulk_create(
        [
            UserTopic(
                user_profile=user_profile,
                stream_id=stream_id,
                recipient_id=recipient_id,
                topic_name=topic_name,
                last_updated=date_muted,
                visibility_policy=UserTopic.MUTED,
            ),
        ],
        ignore_conflicts=ignore_duplicate,
    )


def remove_topic_mute(user_profile: UserProfile, stream_id: int, topic_name: str) -> None:
    row = UserTopic.objects.get(
        user_profile=user_profile,
        stream_id=stream_id,
        topic_name__iexact=topic_name,
        visibility_policy=UserTopic.MUTED,
    )
    row.delete()


def topic_is_muted(user_profile: UserProfile, stream_id: int, topic_name: str) -> bool:
    is_muted = UserTopic.objects.filter(
        user_profile=user_profile,
        stream_id=stream_id,
        topic_name__iexact=topic_name,
        visibility_policy=UserTopic.MUTED,
    ).exists()
    return is_muted


def exclude_topic_mutes(
    conditions: List[ClauseElement], user_profile: UserProfile, stream_id: Optional[int]
) -> List[ClauseElement]:
    # Note: Unlike get_topic_mutes, here we always want to
    # consider topics in deactivated streams, so they are
    # never filtered from the query in this method.
    query = UserTopic.objects.filter(
        user_profile=user_profile,
        visibility_policy=UserTopic.MUTED,
    )

    if stream_id is not None:
        # If we are narrowed to a stream, we can optimize the query
        # by not considering topic mutes outside the stream.
        query = query.filter(stream_id=stream_id)

    rows = query.values(
        "recipient_id",
        "topic_name",
    )

    if not rows:
        return conditions

    class RecipientTopicDict(TypedDict):
        recipient_id: int
        topic_name: str

    def mute_cond(row: RecipientTopicDict) -> ClauseElement:
        recipient_id = row["recipient_id"]
        topic_name = row["topic_name"]
        stream_cond = column("recipient_id", Integer) == recipient_id
        topic_cond = topic_match_sa(topic_name)
        return and_(stream_cond, topic_cond)

    condition = not_(or_(*list(map(mute_cond, rows))))
    return [*conditions, condition]


def build_topic_mute_checker(user_profile: UserProfile) -> Callable[[int, str], bool]:
    rows = UserTopic.objects.filter(
        user_profile=user_profile, visibility_policy=UserTopic.MUTED
    ).values(
        "recipient_id",
        "topic_name",
    )

    tups = set()
    for row in rows:
        recipient_id = row["recipient_id"]
        topic_name = row["topic_name"]
        tups.add((recipient_id, topic_name.lower()))

    def is_muted(recipient_id: int, topic: str) -> bool:
        return (recipient_id, topic.lower()) in tups

    return is_muted


def get_users_muting_topic(stream_id: int, topic_name: str) -> QuerySet[UserProfile]:
    return UserProfile.objects.select_related("realm").filter(
        id__in=UserTopic.objects.filter(
            stream_id=stream_id,
            visibility_policy=UserTopic.MUTED,
            topic_name__iexact=topic_name,
        ).values("user_profile_id")
    )
