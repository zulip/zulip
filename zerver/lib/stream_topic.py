from typing import (Dict, List, Text, Set)
from django.db.models.query import QuerySet

from zerver.lib.stream_subscription import (
    get_active_subscriptions_for_stream_id,
)

from zerver.models import (
    MutedTopic,
)

class StreamTopicTarget:
    '''
    This class is designed to help us move to a
    StreamTopic table or something similar.  It isolates
    places where we are are still using `subject` or
    `topic_name` as a key into tables.
    '''
    def __init__(self, stream_id: int, topic_name: Text) -> None:
        self.stream_id = stream_id
        self.topic_name = topic_name

    def user_ids_muting_topic(self) -> Set[int]:
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

    def get_active_subscriptions(self) -> QuerySet:
        return get_active_subscriptions_for_stream_id(self.stream_id)
