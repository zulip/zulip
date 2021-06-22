from dataclasses import dataclass
from typing import Collection, Set


@dataclass
class UserMessageNotificationsData:
    id: int
    flags: Collection[str]
    mentioned: bool
    online_push_enabled: bool
    stream_push_notify: bool
    stream_email_notify: bool
    wildcard_mention_notify: bool
    sender_is_muted: bool

    def __post_init__(self) -> None:
        if self.mentioned:
            assert "mentioned" in self.flags
        if self.wildcard_mention_notify:
            assert "wildcard_mentioned" in self.flags

    @classmethod
    def from_user_id_sets(
        cls,
        user_id: int,
        flags: Collection[str],
        online_push_user_ids: Set[int],
        stream_push_user_ids: Set[int],
        stream_email_user_ids: Set[int],
        wildcard_mention_user_ids: Set[int],
        muted_sender_user_ids: Set[int],
    ) -> "UserMessageNotificationsData":
        wildcard_mention_notify = (
            user_id in wildcard_mention_user_ids and "wildcard_mentioned" in flags
        )
        return cls(
            id=user_id,
            flags=flags,
            mentioned=("mentioned" in flags),
            online_push_enabled=(user_id in online_push_user_ids),
            stream_push_notify=(user_id in stream_push_user_ids),
            stream_email_notify=(user_id in stream_email_user_ids),
            wildcard_mention_notify=wildcard_mention_notify,
            sender_is_muted=(user_id in muted_sender_user_ids),
        )

    # TODO: The following functions should also look at the `enable_offline_push_notifications` and
    # `enable_offline_email_notifications` settings (for PMs and mentions), but currently they
    # don't.

    def is_notifiable(self, private_message: bool, sender_id: int, idle: bool) -> bool:
        return self.is_email_notifiable(
            private_message, sender_id, idle
        ) or self.is_push_notifiable(private_message, sender_id, idle)

    def is_push_notifiable(self, private_message: bool, sender_id: int, idle: bool) -> bool:
        if not idle and not self.online_push_enabled:
            return False

        if self.id == sender_id:
            return False

        if self.sender_is_muted:
            return False

        return (
            private_message
            or self.mentioned
            or self.wildcard_mention_notify
            or self.stream_push_notify
        )

    def is_email_notifiable(self, private_message: bool, sender_id: int, idle: bool) -> bool:
        if not idle:
            return False

        if self.id == sender_id:
            return False

        if self.sender_is_muted:
            return False

        return (
            private_message
            or self.mentioned
            or self.wildcard_mention_notify
            or self.stream_email_notify
        )
