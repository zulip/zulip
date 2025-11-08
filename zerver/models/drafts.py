from typing import Any

from django.db import models
from typing_extensions import override

from zerver.lib.display_recipient import get_recipient_ids
from zerver.models.constants import MAX_TOPIC_NAME_LENGTH
from zerver.models.recipients import Recipient
from zerver.models.users import UserProfile


class Draft(models.Model):
    """Server-side storage model for storing drafts so that drafts can be synced across
    multiple clients/devices.
    """

    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    recipient = models.ForeignKey(Recipient, null=True, on_delete=models.SET_NULL)
    topic = models.CharField(max_length=MAX_TOPIC_NAME_LENGTH, db_index=True)
    content = models.TextField()  # Length should not exceed MAX_MESSAGE_LENGTH
    last_edit_time = models.DateTimeField(db_index=True)

    @override
    def __str__(self) -> str:
        return f"{self.user_profile.email} / {self.id} / {self.last_edit_time}"

    def to_dict(self) -> dict[str, Any]:
        to, recipient_type_str = get_recipient_ids(self.recipient, self.user_profile_id)
        return {
            "id": self.id,
            "type": recipient_type_str,
            "to": to,
            "topic": self.topic,
            "content": self.content,
            "timestamp": int(self.last_edit_time.timestamp()),
        }
