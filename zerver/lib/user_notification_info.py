from dataclasses import dataclass
from typing import List, Optional, Set

from zerver.models import UserProfile, query_for_ids


@dataclass
class UserNotificationInfo:
    id: int
    enable_online_push_notifications: bool
    enable_offline_push_notifications: bool
    enable_offline_email_notifications: bool
    is_bot: bool
    bot_type: Optional[int]
    long_term_idle: bool


class UserNotificationInfoBackend:
    def __init__(self, user_ids: Set[int]) -> None:
        self.user_ids = user_ids

        query = UserProfile.objects.filter(is_active=True).values(
            "id",
            "enable_online_push_notifications",
            "enable_offline_push_notifications",
            "enable_offline_email_notifications",
            "is_bot",
            "bot_type",
            "long_term_idle",
        )

        # query_for_ids is fast highly optimized for large queries, and we
        # need this codepath to be fast (it's part of sending messages)
        query = query_for_ids(
            query=query,
            user_ids=sorted(user_ids),
            field="id",
        )

        self.cache = {
            row["id"]: UserNotificationInfo(
                id=row["id"],
                enable_online_push_notifications=row["enable_online_push_notifications"],
                enable_offline_push_notifications=row["enable_offline_push_notifications"],
                enable_offline_email_notifications=row["enable_offline_email_notifications"],
                is_bot=row["is_bot"],
                bot_type=row["bot_type"],
                long_term_idle=row["long_term_idle"],
            )
            for row in query
        }

    def get_user_notification_info(self, user_ids: Set[int]) -> List[UserNotificationInfo]:
        assert user_ids.issubset(self.user_ids)
        result = [self.cache[user_id] for user_id in user_ids if user_id in self.cache]
        return result
