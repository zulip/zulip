from __future__ import absolute_import
from zerver.models import UserProfile

from typing import Callable, List, Text

from zerver.models import (
    bulk_get_recipients,
    bulk_get_streams,
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

# Our current model for storing topic mutes, as of August 2017,
# is still based on early experimental code from 2014.  All of
# our topic mutes are stored as a single JSON blob on UserProfile.
#
# The blob is a list of 2-element lists of (stream_name, topic_name).
#
# This sounds janky, and it is, but the JSON part of the implemenation
# has some minor performance benefits.  What's not great about the
# current model is that we use stream names instead of ids, and we
# don't even have the option to use topic ids yet (no Topics table).
#
# This module hopefully encapsulates the original database design
# well enough that most people don't need to look at the strange
# database representation.

def get_topic_mutes(user_profile):
    # type: (UserProfile) -> List[List[Text]]
    muted_topics = ujson.loads(user_profile.muted_topics)
    return muted_topics

def set_topic_mutes(user_profile, muted_topics):
    # type: (UserProfile, List[List[Text]]) -> None
    user_profile.muted_topics = ujson.dumps(muted_topics)
    user_profile.save(update_fields=['muted_topics'])

def add_topic_mute(user_profile, stream, topic):
    # type: (UserProfile, str, str) -> None
    muted_topics = get_topic_mutes(user_profile)
    muted_topics.append([stream, topic])
    set_topic_mutes(user_profile, muted_topics)

def remove_topic_mute(user_profile, stream, topic):
    # type: (UserProfile, str, str) -> None
    muted_topics = get_topic_mutes(user_profile)
    muted_topics.remove([stream, topic])
    set_topic_mutes(user_profile, muted_topics)

def topic_is_muted(user_profile, stream_name, topic_name):
    # type: (UserProfile, Text, Text) -> bool
    muted_topics = get_topic_mutes(user_profile)
    is_muted = [stream_name, topic_name] in muted_topics
    return is_muted

def exclude_topic_mutes(conditions, user_profile, stream_name):
    # type: (List[Selectable], UserProfile, Text) -> List[Selectable]
    muted_topics = get_topic_mutes(user_profile)
    if not muted_topics:
        return conditions

    if stream_name is not None:
        muted_topics = [m for m in muted_topics if m[0].lower() == stream_name]
        if not muted_topics:
            return conditions

    muted_streams = bulk_get_streams(user_profile.realm,
                                     [muted[0] for muted in muted_topics])
    muted_recipients = bulk_get_recipients(Recipient.STREAM,
                                           [stream.id for stream in six.itervalues(muted_streams)])
    recipient_map = dict((s.name.lower(), muted_recipients[s.id].id)
                         for s in six.itervalues(muted_streams))

    muted_topics = [m for m in muted_topics if m[0].lower() in recipient_map]

    if not muted_topics:
        return conditions

    def mute_cond(muted):
        # type: (List[str]) -> Selectable
        stream_cond = column("recipient_id") == recipient_map[muted[0].lower()]
        topic_cond = func.upper(column("subject")) == func.upper(muted[1])
        return and_(stream_cond, topic_cond)

    condition = not_(or_(*list(map(mute_cond, muted_topics))))
    return conditions + [condition]

def build_topic_mute_checker(user_profile):
    # type: (UserProfile) -> Callable[[int, Text], bool]
    rows = ujson.loads(user_profile.muted_topics)
    stream_names = {row[0] for row in rows}
    stream_dict = dict()
    for name in stream_names:
        try:
            stream_id = Stream.objects.get(
                name__iexact=name.strip(),
                realm_id=user_profile.realm_id,
            ).id
            stream_dict[name.lower()] = stream_id
        except Stream.DoesNotExist:
            # If the stream doesn't exist, this is just a stale entry
            # in the muted_topics structure.
            continue
    tups = set()
    for row in rows:
        stream_name = row[0].lower()
        topic = row[1]
        if stream_name not in stream_dict:
            # No such stream
            continue
        stream_id = stream_dict[stream_name]
        tups.add((stream_id, topic.lower()))

    def is_muted(stream_id, topic):
        # type: (int, Text) -> bool
        return (stream_id, topic.lower()) in tups

    return is_muted
