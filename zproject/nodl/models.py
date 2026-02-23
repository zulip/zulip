from datetime import timedelta

from django.db import models
from django.utils import timezone

from zerver.models import UserProfile

INVITE_EXPIRY_DAYS = 7


class NodlRegistrationPin(models.Model):
    """Stores bcrypt-hashed Registration Lock PINs for SIM swap protection.

    Each Zulip user can have at most one PIN. The PIN is required when
    authenticating on a new device (is_new_device=True in auth bridge response).
    """

    user = models.OneToOneField(
        UserProfile,
        on_delete=models.CASCADE,
        related_name="nodl_registration_pin",
    )
    pin_hash = models.CharField(max_length=255)
    failed_attempts = models.IntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "nodl_registration_pin"

    def is_locked(self) -> bool:
        """Check if the account is currently locked due to failed attempts."""
        if self.locked_until is None:
            return False
        return timezone.now() < self.locked_until

    def remaining_lockout_seconds(self) -> int:
        """Return seconds remaining in lockout, or 0 if not locked."""
        if not self.is_locked():
            return 0
        delta = self.locked_until - timezone.now()  # type: ignore[operator]
        return max(0, int(delta.total_seconds()))


class NodlInvite(models.Model):
    """Tracks phone invitations sent by users.

    Status is computed at read time from ``expires_at`` and ``invited_user``:
    - invited_user is set -> "registered"
    - expires_at < now and no invited_user -> "expired"
    - otherwise -> "sent"
    """

    inviter = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        related_name="sent_invites",
    )
    invited_phone_hash = models.CharField(max_length=64, db_index=True)
    invited_phone_display = models.CharField(max_length=8)
    invited_user = models.ForeignKey(
        UserProfile,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="received_invites",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField()

    class Meta:
        db_table = "nodl_invite"
        ordering = ["-created_at"]

    def save(self, *args: object, **kwargs: object) -> None:
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=INVITE_EXPIRY_DAYS)
        super().save(*args, **kwargs)

    @property
    def computed_status(self) -> str:
        if self.invited_user_id is not None:
            return "registered"
        if self.expires_at < timezone.now():
            return "expired"
        return "sent"

    def to_api_dict(self) -> dict:
        return {
            "id": self.pk,
            "phone_display": self.invited_phone_display,
            "status": self.computed_status,
            "invited_name": (self.invited_user.full_name if self.invited_user else None),
            "invited_user_id": self.invited_user_id,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
        }
