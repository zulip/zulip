from dataclasses import dataclass
from typing import List


@dataclass
class UserMessageNotificationsData:
    id: int
    flags: List[str]
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
