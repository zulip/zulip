from django.db import models
from django.db.models import CASCADE

from zerver.models.streams import Stream
from zerver.models.users import UserProfile


class Meeting(models.Model):
    class Status(models.TextChoices):
        PROPOSED = "proposed"
        DEADLINE_PASSED = "deadline_passed"
        CONFIRMED = "confirmed"

    owner = models.ForeignKey(UserProfile, on_delete=CASCADE, related_name="owned_meetings")
    stream = models.ForeignKey(Stream, on_delete=CASCADE, related_name="meetings")
    topic = models.CharField(max_length=60)
    deadline = models.DateTimeField()
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PROPOSED, db_index=True
    )
    # Set when the owner picks a winning slot after the deadline passes.
    confirmed_slot = models.OneToOneField(
        "MeetingSlot",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="confirmed_for_meeting",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["stream", "status"]),
        ]


class MeetingSlot(models.Model):
    meeting = models.ForeignKey(Meeting, on_delete=CASCADE, related_name="slots")
    start_time = models.DateTimeField()
    # end_time is optional; a slot may represent a point in time rather than a range.
    end_time = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["start_time"]


class MeetingResponse(models.Model):
    slot = models.ForeignKey(MeetingSlot, on_delete=CASCADE, related_name="responses")
    user = models.ForeignKey(UserProfile, on_delete=CASCADE, related_name="meeting_responses")
    available = models.BooleanField()

    class Meta:
        # Each user may have at most one response per slot.
        unique_together = [("slot", "user")]
