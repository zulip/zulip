from typing import Dict, Set

from zerver.models import UserTopic


class StreamTopicTarget:
    """
    This class is designed to help us move to a
    StreamTopic table or something similar.  It isolates
    places where we are still using `topic_name` as
    a key into tables.
    """

    def __init__(self, stream_id: int, topic_name: str) -> None:
        self.stream_id = stream_id
        self.topic_name = topic_name

    def user_ids_with_visibility_policy(self, visibility_policy: int) -> Set[int]:
        query = UserTopic.objects.filter(
            stream_id=self.stream_id,
            topic_name__iexact=self.topic_name,
            visibility_policy=visibility_policy,
        ).values(
            "user_profile_id",
        )
        return {row["user_profile_id"] for row in query}

    def user_id_to_visibility_policy_dict(self) -> Dict[int, int]:
        user_id_to_visibility_policy: Dict[int, int] = {}

        query = UserTopic.objects.filter(
            stream_id=self.stream_id, topic_name__iexact=self.topic_name
        ).values(
            "visibility_policy",
            "user_profile_id",
        )
        for row in query:
            user_id_to_visibility_policy[row["user_profile_id"]] = row["visibility_policy"]
        return user_id_to_visibility_policy
