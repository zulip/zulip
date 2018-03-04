from typing import List, Text, Dict, Any

from zerver.models import (
    LockedTopic,
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

def get_locked_topics() -> List[Dict[Text, Any]]:
    rows = LockedTopic.objects.values(
        'stream_id',
        'topic_name'
    )
    return [
        {'stream_id': row['stream_id'], 'topic': row['topic_name']}
        for row in rows
    ]
