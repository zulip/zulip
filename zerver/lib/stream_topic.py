from typing import (Dict, List, Text, Set)

from zerver.models import MutedTopic

class StreamTopicTarget(object):
    '''
    This class is designed to help us move to a
    StreamTopic table or something similar.  It isolates
    places where we are are still using `subject` or
    `topic_name` as a key into tables.
    '''
    def __init__(self, stream_id, topic_name):
        # type: (int, Text) -> None
        self.stream_id = stream_id
        self.topic_name = topic_name

    def user_ids_muting_topic(self):
        # type: () -> Set[int]
        query = MutedTopic.objects.filter(
            stream_id=self.stream_id,
            topic_name__iexact=self.topic_name,
        ).values(
            'user_profile_id',
        )
        return {
            row['user_profile_id']
            for row in query
        }
