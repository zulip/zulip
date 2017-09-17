from __future__ import absolute_import
from zerver.models import UserProfile

from typing import Any, Callable, Dict, List, Optional, Text

from zerver.models import (
    bulk_get_recipients,
    bulk_get_streams,
    get_recipient,
    get_stream,
    get_recipient,
    get_stream,
    MutedTopic,
    Recipient,
    Stream,
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

import six
import ujson

def get_topic_mutes(user_profile):
    # type: (UserProfile) -> List[List[Text]]
    rows = MutedTopic.objects.filter(
        user_profile=user_profile,
    ).values(
        'stream__name',
        'topic_name'
    )
    return [
        [row['stream__name'], row['topic_name']]
        for row in rows
    ]

def set_topic_mutes(user_profile, muted_topics):
    # type: (UserProfile, List[List[Text]]) -> None

    '''
    This is only used in tests.
    '''

    MutedTopic.objects.filter(
        user_profile=user_profile,
    ).delete()

    for stream_name, topic_name in muted_topics:
        stream = get_stream(stream_name, user_profile.realm)
        recipient = get_recipient(Recipient.STREAM, stream.id)

        add_topic_mute(
            user_profile=user_profile,
            stream_id=stream.id,
            recipient_id=recipient.id,
            topic_name=topic_name,
        )

def add_topic_mute(user_profile, stream_id, recipient_id, topic_name):
    # type: (UserProfile, int, int, str) -> None
    MutedTopic.objects.create(
        user_profile=user_profile,
        stream_id=stream_id,
        recipient_id=recipient_id,
        topic_name=topic_name,
    )

def remove_topic_mute(user_profile, stream_id, topic_name):
    # type: (UserProfile, int, str) -> None
    row = MutedTopic.objects.get(
        user_profile=user_profile,
        stream_id=stream_id,
        topic_name__iexact=topic_name
    )
    row.delete()

def topic_is_muted(user_profile, stream, topic_name):
    # type: (UserProfile, Stream, Text) -> bool
    is_muted = MutedTopic.objects.filter(
        user_profile=user_profile,
        stream_id=stream.id,
        topic_name__iexact=topic_name,
    ).exists()
    return is_muted

def exclude_topic_mutes(conditions, user_profile, stream_id):
    # type: (List[Selectable], UserProfile, Optional[int]) -> List[Selectable]
    query = MutedTopic.objects.filter(
        user_profile=user_profile,
    )

    if stream_id is not None:
        # If we are narrowed to a stream, we can optimize the query
        # by not considering topic mutes outside the stream.
        query = query.filter(stream_id=stream_id)

    query = query.values(
        'recipient_id',
        'topic_name'
    )
    rows = list(query)

    if not rows:
        return conditions

    def mute_cond(row):
        # type: (Dict[str, Any]) -> Selectable
        recipient_id = row['recipient_id']
        topic_name = row['topic_name']
        stream_cond = column("recipient_id") == recipient_id
        topic_cond = func.upper(column("subject")) == func.upper(topic_name)
        return and_(stream_cond, topic_cond)

    condition = not_(or_(*list(map(mute_cond, rows))))
    return conditions + [condition]

def build_topic_mute_checker(user_profile):
    # type: (UserProfile) -> Callable[[int, Text], bool]
    rows = MutedTopic.objects.filter(
        user_profile=user_profile,
    ).values(
        'recipient_id',
        'topic_name'
    )
    rows = list(rows)

    tups = set()
    for row in rows:
        recipient_id = row['recipient_id']
        topic_name = row['topic_name']
        tups.add((recipient_id, topic_name.lower()))

    def is_muted(recipient_id, topic):
        # type: (int, Text) -> bool
        return (recipient_id, topic.lower()) in tups

    return is_muted
