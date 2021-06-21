from dataclasses import dataclass
from typing import Collection


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
