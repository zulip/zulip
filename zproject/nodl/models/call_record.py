import uuid

from django.db import models
from django.utils import timezone

from zerver.models import UserProfile


class CallRecord(models.Model):
    """Tracks voice call lifecycle — CDR (Call Detail Record).

    Status transitions:
        ringing → connected → ended
        ringing → declined
        ringing → cancelled
        ringing → missed
    """

    STATUS_CHOICES = [
        ("ringing", "Ringing"),
        ("connected", "Connected"),
        ("ended", "Ended"),
        ("missed", "Missed"),
        ("declined", "Declined"),
        ("cancelled", "Cancelled"),
    ]

    END_REASON_CHOICES = [
        ("caller_hangup", "Caller Hangup"),
        ("callee_hangup", "Callee Hangup"),
        ("callee_declined", "Callee Declined"),
        ("caller_cancelled", "Caller Cancelled"),
        ("timeout", "Timeout"),
        ("error", "Error"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room_name = models.CharField(max_length=255)
    caller = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        related_name="outgoing_calls",
    )
    callee = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        related_name="incoming_calls",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ringing")
    initiated_at = models.DateTimeField(default=timezone.now)
    answered_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.IntegerField(null=True, blank=True)
    end_reason = models.CharField(
        max_length=30, choices=END_REASON_CHOICES, null=True, blank=True
    )

    class Meta:
        db_table = "call_records"
        ordering = ["-initiated_at"]

    def __str__(self) -> str:
        return f"Call {self.id} ({self.caller_id} → {self.callee_id}): {self.status}"
