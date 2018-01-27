from typing import Any, Callable, Dict, List, Optional, Text

from zerver.models import (
    get_stream_recipient,
    get_stream,
    LockedTopic,
    UserProfile
)
from sqlalchemy.sql import (
    and_,
    column,
    func,
    not_,
    or_,
    Selectable
)

def add_locked_topic(stream_id: int, topic_name: str) -> None:
    LockedTopic.objects.create(
        stream_id=stream_id,
        topic_name=topic_name,
    )

def remove_locked_topic(stream_id: int, topic_name: str) -> None:
    row = LockedTopic.objects.get(
        stream_id=stream_id,
        topic_name=topic_name,
    )
    row.delete()

def topic_is_locked(stream_id: int, topic_name: Text) -> bool:
    is_locked = LockedTopic.objects.filter(
        stream_id=stream_id,
        topic_name__iexact=topic_name,
    ).exists()
    return is_locked

def get_locked_topics() -> List[List[Text]]:
    rows = LockedTopic.objects.values(
        'stream__name',
        'topic_name'
    )
    return [
        [row['stream__name'], row['topic_name']]
        for row in rows
    ]
