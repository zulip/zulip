from typing import Set

from zerver.models import UserTopic


class StreamTopicTarget:
    """
    This class is designed to help us move to a
    StreamTopic table or something similar.  It isolates
    places where we are are still using `topic_name` as
    a key into tables.
    """

    def __init__(self, stream_id: int, topic_name: str) -> None:
        self.stream_id = stream_id
        self.topic_name = topic_name

    def user_ids_muting_topic(self) -> Set[int]:
        query = UserTopic.objects.filter(
            stream_id=self.stream_id,
            topic_name__iexact=self.topic_name,
            visibility_policy=UserTopic.MUTED,
        ).values(
            "user_profile_id",
        )
        return {row["user_profile_id"] for row in query}
