from __future__ import absolute_import
from zerver.models import UserProfile

from typing import List, Text

from zerver.models import UserProfile

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
