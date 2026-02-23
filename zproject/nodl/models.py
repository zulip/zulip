from django.db import models
from django.utils import timezone

from zerver.models import UserProfile


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
