import uuid

from django.db import models

from zerver.models import UserProfile


class DeviceVoipToken(models.Model):
    """Stores VoIP push tokens (iOS PushKit) and FCM tokens (Android) per device.

    Used by call_push_service to dispatch incoming call notifications.
    UNIQUE(user_id, device_id) ensures one token per device per user.
    """

    PLATFORM_CHOICES = [
        ("ios", "iOS"),
        ("android", "Android"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        related_name="voip_tokens",
    )
    platform = models.CharField(max_length=10, choices=PLATFORM_CHOICES)
    fcm_token = models.TextField(null=True, blank=True)
    voip_token = models.TextField(null=True, blank=True)
    device_id = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "device_voip_tokens"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "device_id"],
                name="unique_user_device",
            ),
        ]

    def __str__(self) -> str:
        return f"VoipToken {self.device_id} ({self.platform}) for user {self.user_id}"
