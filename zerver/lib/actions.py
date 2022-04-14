from typing import List

from zerver.lib.topic import filter_by_topic_name_via_message
from zerver.models import Message, Stream, UserMessage, UserProfile


def get_topic_messages(user_profile: UserProfile, stream: Stream, topic_name: str) -> List[Message]:
    query = UserMessage.objects.filter(
        user_profile=user_profile,
        message__recipient=stream.recipient,
    ).order_by("id")
    return [um.message for um in filter_by_topic_name_via_message(query, topic_name)]
