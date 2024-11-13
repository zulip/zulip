from datetime import datetime

from django.db import transaction

from zerver.lib.timestamp import datetime_to_timestamp
from zerver.lib.types import TopicSettingsDict
from zerver.models import UserProfile
from zerver.models.topic_settings import TopicSettings


def get_topic_settings(
    user_profile: UserProfile,
) -> list[TopicSettingsDict]:
    """
    Fetches TopicSettings objects associated with the target user.
    """
    query = TopicSettings.objects.filter(realm_id=user_profile.realm.id)
    rows = query.values("stream_id", "topic_name", "last_updated", "is_locked")

    result = []
    for row in rows:
        topic_settings_dict: TopicSettingsDict = {
            "stream_id": row["stream_id"],
            "topic_name": row["topic_name"],
            "is_locked": row["is_locked"],
            "last_updated": datetime_to_timestamp(row["last_updated"]),
        }

        result.append(topic_settings_dict)

    return result


def get_topic_lock_status(user_profile: UserProfile, topic_name: str, stream_id: int) -> bool:
    topic = TopicSettings.objects.filter(
        realm_id=user_profile.realm.id,
        stream_id=stream_id,
        topic_name=topic_name.lower(),
    ).first()
    if topic:
        return topic.is_locked
    return False


@transaction.atomic(savepoint=False)
def set_topic_settings_in_database(
    user_profile_id: int,
    realm_id: int,
    stream_id: int,
    topic_name: str,
    is_topic_locked: bool,
    last_updated: datetime,
) -> None:
    """
    Sets the topic settings in the database. If the topic already exists in the TopicSettings table,
    updates the existing entry. Otherwise, creates a new entry.
    """
    TopicSettings.objects.update_or_create(
        user_profile_id=user_profile_id,
        realm_id=realm_id,
        stream_id=stream_id,
        topic_name=topic_name.lower(),
        defaults={
            "is_locked": is_topic_locked,
            "last_updated": last_updated,
        },
    )
