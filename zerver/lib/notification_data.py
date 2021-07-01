from dataclasses import dataclass
from typing import Collection, Optional, Set


@dataclass
class UserMessageNotificationsData:
    user_id: int
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
            user_id=user_id,
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

    # For these functions, acting_user_id is the user sent a message
    # (or edited a message) triggering the event for which we need to
    # determine notifiability.
    def is_notifiable(self, private_message: bool, acting_user_id: int, idle: bool) -> bool:
        return self.is_email_notifiable(
            private_message, acting_user_id, idle
        ) or self.is_push_notifiable(private_message, acting_user_id, idle)

    def is_push_notifiable(self, private_message: bool, acting_user_id: int, idle: bool) -> bool:
        return self.get_push_notification_trigger(private_message, acting_user_id, idle) is not None

    def get_push_notification_trigger(
        self, private_message: bool, acting_user_id: int, idle: bool
    ) -> Optional[str]:
        if not idle and not self.online_push_enabled:
            return None

        if self.user_id == acting_user_id:
            return None

        if self.sender_is_muted:
            return None

        if private_message:
            return "private_message"
        elif self.mentioned:
            return "mentioned"
        elif self.wildcard_mention_notify:
            return "wildcard_mentioned"
        elif self.stream_push_notify:
            return "stream_push_notify"
        else:
            return None

    def is_email_notifiable(self, private_message: bool, acting_user_id: int, idle: bool) -> bool:
        return (
            self.get_email_notification_trigger(private_message, acting_user_id, idle) is not None
        )

    def get_email_notification_trigger(
        self, private_message: bool, acting_user_id: int, idle: bool
    ) -> Optional[str]:
        if not idle:
            return None

        if self.user_id == acting_user_id:
            return None

        if self.sender_is_muted:
            return None

        if private_message:
            return "private_message"
        elif self.mentioned:
            return "mentioned"
        elif self.wildcard_mention_notify:
            return "wildcard_mentioned"
        elif self.stream_email_notify:
            return "stream_email_notify"
        else:
            return None
