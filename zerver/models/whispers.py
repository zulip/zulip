import hashlib
from typing import Any

from django.db import models
from django.db.models import CASCADE
from django.utils.timezone import now as timezone_now
from typing_extensions import override

from zerver.models.realms import Realm
from zerver.models.recipients import Recipient
from zerver.models.users import UserProfile


class WhisperConversation(models.Model):
    """Represents an active whisper conversation within a parent conversation"""
    
    id = models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")
    parent_recipient = models.ForeignKey(
        Recipient, 
        on_delete=CASCADE, 
        related_name='whisper_conversations'
    )
    realm = models.ForeignKey(Realm, on_delete=CASCADE)
    created_by = models.ForeignKey(UserProfile, on_delete=CASCADE)
    created_at = models.DateTimeField(default=timezone_now, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    
    # Hash of participant user IDs for efficient lookups
    participants_hash = models.CharField(max_length=40, db_index=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["realm", "parent_recipient", "is_active"],
                name="zerver_whisperconversation_realm_parent_active",
            ),
            models.Index(
                fields=["participants_hash", "is_active"],
                name="zerver_whisperconversation_hash_active",
            ),
        ]

    @override
    def __str__(self) -> str:
        return f"WhisperConversation(id={self.id}, parent={self.parent_recipient_id}, participants_hash={self.participants_hash})"

    def get_participant_ids(self) -> list[int]:
        """Get list of participant user IDs from the participants_hash"""
        return WhisperParticipant.objects.filter(
            whisper_conversation=self,
            is_active=True
        ).values_list('user_profile_id', flat=True)


class WhisperRequest(models.Model):
    """Represents a pending whisper invitation"""
    
    id = models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")
    requester = models.ForeignKey(
        UserProfile, 
        on_delete=CASCADE, 
        related_name='sent_whisper_requests'
    )
    recipient = models.ForeignKey(
        UserProfile, 
        on_delete=CASCADE, 
        related_name='received_whisper_requests'
    )
    parent_recipient = models.ForeignKey(Recipient, on_delete=CASCADE)
    realm = models.ForeignKey(Realm, on_delete=CASCADE)
    created_at = models.DateTimeField(default=timezone_now, db_index=True)
    
    class Status(models.IntegerChoices):
        PENDING = 1
        ACCEPTED = 2
        DECLINED = 3
        EXPIRED = 4
    
    status = models.PositiveSmallIntegerField(
        choices=Status.choices, 
        default=Status.PENDING,
        db_index=True
    )
    
    # Reference to the whisper conversation if request is accepted
    whisper_conversation = models.ForeignKey(
        WhisperConversation,
        null=True,
        blank=True,
        on_delete=CASCADE
    )

    class Meta:
        indexes = [
            models.Index(
                fields=["recipient", "status"],
                name="zerver_whisperrequest_recipient_status",
            ),
            models.Index(
                fields=["requester", "status"],
                name="zerver_whisperrequest_requester_status",
            ),
            models.Index(
                fields=["realm", "created_at"],
                name="zerver_whisperrequest_realm_created",
            ),
        ]
        unique_together = [
            ("requester", "recipient", "parent_recipient", "whisper_conversation")
        ]

    @override
    def __str__(self) -> str:
        return f"WhisperRequest(id={self.id}, requester={self.requester.email}, recipient={self.recipient.email}, status={self.get_status_display()})"


class WhisperParticipant(models.Model):
    """Tracks participants in whisper conversations"""
    
    id = models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")
    whisper_conversation = models.ForeignKey(WhisperConversation, on_delete=CASCADE)
    user_profile = models.ForeignKey(UserProfile, on_delete=CASCADE)
    joined_at = models.DateTimeField(default=timezone_now)
    left_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["whisper_conversation", "is_active"],
                name="zerver_whisperparticipant_conversation_active",
            ),
            models.Index(
                fields=["user_profile", "is_active"],
                name="zerver_whisperparticipant_user_active",
            ),
        ]
        unique_together = [("whisper_conversation", "user_profile")]

    @override
    def __str__(self) -> str:
        return f"WhisperParticipant(conversation={self.whisper_conversation_id}, user={self.user_profile.email}, active={self.is_active})"


def get_whisper_participants_hash(user_ids: list[int]) -> str:
    """Generate a hash for a list of user IDs to identify whisper conversations"""
    sorted_ids = sorted(set(user_ids))
    hash_key = ",".join(str(user_id) for user_id in sorted_ids)
    return hashlib.sha1(hash_key.encode()).hexdigest()


def get_active_whisper_conversation(parent_recipient: Recipient, user_ids: list[int]) -> WhisperConversation | None:
    """Get an active whisper conversation for the given participants in the parent conversation"""
    participants_hash = get_whisper_participants_hash(user_ids)
    try:
        return WhisperConversation.objects.get(
            parent_recipient=parent_recipient,
            participants_hash=participants_hash,
            is_active=True
        )
    except WhisperConversation.DoesNotExist:
        return None