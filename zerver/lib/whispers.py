"""
Library for managing whisper conversations in Zulip.

This module provides functions for creating, managing, and validating
whisper conversations and their participants.
"""

import hashlib
from datetime import timedelta
from typing import Any, Dict, List, Optional, Set

from django.db import transaction
from django.utils.timezone import now as timezone_now

from zerver.lib.exceptions import JsonableError
from zerver.lib.user_groups import access_user_group_by_id
from zerver.models import (
    Realm,
    Recipient,
    Stream,
    Subscription,
    UserProfile,
    WhisperConversation,
    WhisperParticipant,
    WhisperRequest,
)
from zerver.models.recipients import get_direct_message_group_user_ids


class WhisperError(JsonableError):
    """Base exception for whisper-related errors"""
    pass


class WhisperPermissionError(WhisperError):
    """Exception for whisper permission violations"""
    code = "WHISPER_PERMISSION_DENIED"


class WhisperValidationError(WhisperError):
    """Exception for whisper validation failures"""
    code = "WHISPER_VALIDATION_ERROR"


class WhisperConversationError(WhisperError):
    """Exception for whisper conversation management errors"""
    code = "WHISPER_CONVERSATION_ERROR"


def validate_whisper_participants(
    requesting_user: UserProfile,
    participant_user_ids: List[int],
    parent_recipient: Recipient
) -> List[UserProfile]:
    """
    Validate that whisper participants are valid and have appropriate permissions.
    
    Args:
        requesting_user: User requesting to create the whisper
        participant_user_ids: List of user IDs to include in whisper
        parent_recipient: The parent conversation recipient
        
    Returns:
        List of validated UserProfile objects
        
    Raises:
        WhisperPermissionError: If user lacks permission
        WhisperValidationError: If participants are invalid
    """
    if not participant_user_ids:
        raise WhisperValidationError("Whisper must have at least one participant")
    
    if len(participant_user_ids) > 50:  # Reasonable limit
        raise WhisperValidationError("Too many participants in whisper conversation")
    
    # Remove duplicates and requesting user (they're automatically included)
    unique_participant_ids = list(set(participant_user_ids))
    if requesting_user.id in unique_participant_ids:
        unique_participant_ids.remove(requesting_user.id)
    
    if not unique_participant_ids:
        raise WhisperValidationError("Cannot create whisper with only yourself")
    
    # Validate all participants exist and are active
    participants = UserProfile.objects.filter(
        id__in=unique_participant_ids,
        is_active=True,
        realm=requesting_user.realm
    )
    
    if len(participants) != len(unique_participant_ids):
        raise WhisperValidationError("Some participants are invalid or inactive")
    
    # Check if requesting user has access to parent conversation
    if not has_access_to_recipient(requesting_user, parent_recipient):
        raise WhisperPermissionError("You don't have access to this conversation")
    
    # Check if all participants have access to parent conversation
    for participant in participants:
        if not has_access_to_recipient(participant, parent_recipient):
            raise WhisperPermissionError(
                f"User {participant.email} doesn't have access to this conversation"
            )
    
    # Check for blocked users (simplified - in real implementation would check MutedUser)
    # This is a placeholder for more sophisticated permission checking
    
    return list(participants)


def has_access_to_recipient(user: UserProfile, recipient: Recipient) -> bool:
    """
    Check if a user has access to a recipient (stream or direct message group).
    
    Args:
        user: User to check access for
        recipient: Recipient to check access to
        
    Returns:
        True if user has access, False otherwise
    """
    if recipient.type == Recipient.STREAM:
        # Check if user is subscribed to the stream
        return Subscription.objects.filter(
            user_profile=user,
            recipient=recipient,
            is_user_active=True
        ).exists()
    
    elif recipient.type == Recipient.DIRECT_MESSAGE_GROUP:
        # Check if user is part of the direct message group
        group_user_ids = get_direct_message_group_user_ids(recipient)
        return user.id in group_user_ids
    
    elif recipient.type == Recipient.PERSONAL:
        # For 1:1 DMs, check if user is either sender or recipient
        return recipient.type_id == user.id
    
    return False


def create_whisper_conversation(
    requesting_user: UserProfile,
    participant_user_ids: List[int],
    parent_recipient: Recipient
) -> WhisperConversation:
    """
    Create a new whisper conversation with the specified participants.
    
    Args:
        requesting_user: User creating the whisper
        participant_user_ids: List of user IDs to include
        parent_recipient: Parent conversation recipient
        
    Returns:
        Created WhisperConversation object
        
    Raises:
        WhisperPermissionError: If user lacks permission
        WhisperValidationError: If request is invalid
        WhisperConversationError: If conversation creation fails
    """
    # Validate participants
    participants = validate_whisper_participants(
        requesting_user, participant_user_ids, parent_recipient
    )
    
    # Include requesting user in participants
    all_participants = [requesting_user] + participants
    all_participant_ids = [user.id for user in all_participants]
    
    # Generate participants hash
    participants_hash = get_whisper_participants_hash(all_participant_ids)
    
    # Check if conversation already exists
    existing_conversation = get_active_whisper_conversation(
        parent_recipient, all_participant_ids
    )
    if existing_conversation:
        return existing_conversation
    
    # Create conversation and participants atomically
    with transaction.atomic():
        whisper_conversation = WhisperConversation.objects.create(
            parent_recipient=parent_recipient,
            realm=requesting_user.realm,
            created_by=requesting_user,
            participants_hash=participants_hash
        )
        
        # Create participant records
        participant_objects = []
        for participant in all_participants:
            participant_objects.append(
                WhisperParticipant(
                    whisper_conversation=whisper_conversation,
                    user_profile=participant
                )
            )
        
        WhisperParticipant.objects.bulk_create(participant_objects)
    
    return whisper_conversation


def add_participant_to_whisper(
    whisper_conversation: WhisperConversation,
    requesting_user: UserProfile,
    new_participant: UserProfile
) -> WhisperParticipant:
    """
    Add a new participant to an existing whisper conversation.
    
    Args:
        whisper_conversation: Whisper conversation to add participant to
        requesting_user: User requesting to add participant
        new_participant: User to add to conversation
        
    Returns:
        Created WhisperParticipant object
        
    Raises:
        WhisperPermissionError: If user lacks permission
        WhisperValidationError: If request is invalid
    """
    # Check if requesting user is a participant
    if not is_whisper_participant(whisper_conversation, requesting_user):
        raise WhisperPermissionError("You are not a participant in this whisper")
    
    # Check if new participant has access to parent conversation
    if not has_access_to_recipient(new_participant, whisper_conversation.parent_recipient):
        raise WhisperPermissionError(
            "New participant doesn't have access to the parent conversation"
        )
    
    # Check if already a participant
    if is_whisper_participant(whisper_conversation, new_participant):
        raise WhisperValidationError("User is already a participant in this whisper")
    
    # Add participant
    participant = WhisperParticipant.objects.create(
        whisper_conversation=whisper_conversation,
        user_profile=new_participant
    )
    
    # Update participants hash
    update_whisper_participants_hash(whisper_conversation)
    
    return participant


def remove_participant_from_whisper(
    whisper_conversation: WhisperConversation,
    requesting_user: UserProfile,
    participant_to_remove: Optional[UserProfile] = None
) -> bool:
    """
    Remove a participant from a whisper conversation.
    
    Args:
        whisper_conversation: Whisper conversation to remove participant from
        requesting_user: User requesting the removal
        participant_to_remove: User to remove (None means requesting user leaves)
        
    Returns:
        True if conversation is still active, False if it was closed
        
    Raises:
        WhisperPermissionError: If user lacks permission
        WhisperValidationError: If request is invalid
    """
    if participant_to_remove is None:
        participant_to_remove = requesting_user
    
    # Check if requesting user can remove the participant
    if participant_to_remove != requesting_user:
        # Only conversation creator can remove others (simplified rule)
        if whisper_conversation.created_by != requesting_user:
            raise WhisperPermissionError("Only conversation creator can remove other participants")
    
    # Find and deactivate participant
    try:
        participant = WhisperParticipant.objects.get(
            whisper_conversation=whisper_conversation,
            user_profile=participant_to_remove,
            is_active=True
        )
    except WhisperParticipant.DoesNotExist:
        raise WhisperValidationError("User is not an active participant in this whisper")
    
    participant.is_active = False
    participant.left_at = timezone_now()
    participant.save()
    
    # Check if conversation should be closed
    active_participants = WhisperParticipant.objects.filter(
        whisper_conversation=whisper_conversation,
        is_active=True
    ).count()
    
    if active_participants <= 1:
        # Close conversation if only one or no participants left
        whisper_conversation.is_active = False
        whisper_conversation.save()
        return False
    
    # Update participants hash
    update_whisper_participants_hash(whisper_conversation)
    return True


def is_whisper_participant(
    whisper_conversation: WhisperConversation,
    user: UserProfile
) -> bool:
    """
    Check if a user is an active participant in a whisper conversation.
    
    Args:
        whisper_conversation: Whisper conversation to check
        user: User to check
        
    Returns:
        True if user is an active participant
    """
    return WhisperParticipant.objects.filter(
        whisper_conversation=whisper_conversation,
        user_profile=user,
        is_active=True
    ).exists()


def get_whisper_participants_hash(user_ids: List[int]) -> str:
    """
    Generate a hash for a list of user IDs to identify whisper conversations.
    
    Args:
        user_ids: List of user IDs
        
    Returns:
        SHA1 hash string
    """
    sorted_ids = sorted(set(user_ids))
    hash_key = ",".join(str(user_id) for user_id in sorted_ids)
    return hashlib.sha1(hash_key.encode()).hexdigest()


def get_active_whisper_conversation(
    parent_recipient: Recipient,
    user_ids: List[int]
) -> Optional[WhisperConversation]:
    """
    Get an active whisper conversation for the given participants in the parent conversation.
    
    Args:
        parent_recipient: Parent conversation recipient
        user_ids: List of user IDs in the whisper
        
    Returns:
        WhisperConversation if found, None otherwise
    """
    participants_hash = get_whisper_participants_hash(user_ids)
    try:
        return WhisperConversation.objects.get(
            parent_recipient=parent_recipient,
            participants_hash=participants_hash,
            is_active=True
        )
    except WhisperConversation.DoesNotExist:
        return None


def update_whisper_participants_hash(whisper_conversation: WhisperConversation) -> None:
    """
    Update the participants hash for a whisper conversation based on current active participants.
    
    Args:
        whisper_conversation: Whisper conversation to update
    """
    active_participant_ids = list(
        WhisperParticipant.objects.filter(
            whisper_conversation=whisper_conversation,
            is_active=True
        ).values_list('user_profile_id', flat=True)
    )
    
    new_hash = get_whisper_participants_hash(active_participant_ids)
    whisper_conversation.participants_hash = new_hash
    whisper_conversation.save(update_fields=['participants_hash'])


def cleanup_expired_whisper_requests(realm: Realm, hours: int = 24) -> int:
    """
    Clean up expired whisper requests.
    
    Args:
        realm: Realm to clean up requests for
        hours: Number of hours after which requests expire
        
    Returns:
        Number of requests cleaned up
    """
    expiry_time = timezone_now() - timedelta(hours=hours)
    
    expired_requests = WhisperRequest.objects.filter(
        realm=realm,
        status=WhisperRequest.Status.PENDING,
        created_at__lt=expiry_time
    )
    
    count = expired_requests.count()
    expired_requests.update(status=WhisperRequest.Status.EXPIRED)
    
    return count


def cleanup_inactive_whisper_conversations(realm: Realm, days: int = 7) -> int:
    """
    Clean up whisper conversations that have been inactive.
    
    Args:
        realm: Realm to clean up conversations for
        days: Number of days of inactivity before cleanup
        
    Returns:
        Number of conversations cleaned up
    """
    cutoff_time = timezone_now() - timedelta(days=days)
    
    # Find conversations with no recent messages (simplified - would need to check Message table)
    inactive_conversations = WhisperConversation.objects.filter(
        realm=realm,
        is_active=True,
        created_at__lt=cutoff_time
    )
    
    count = inactive_conversations.count()
    inactive_conversations.update(is_active=False)
    
    return count


def get_user_whisper_conversations(
    user: UserProfile,
    parent_recipient: Optional[Recipient] = None
) -> List[WhisperConversation]:
    """
    Get all active whisper conversations for a user.
    
    Args:
        user: User to get conversations for
        parent_recipient: Optional filter by parent recipient
        
    Returns:
        List of WhisperConversation objects
    """
    participant_filter = WhisperParticipant.objects.filter(
        user_profile=user,
        is_active=True
    ).values_list('whisper_conversation_id', flat=True)
    
    conversations_query = WhisperConversation.objects.filter(
        id__in=participant_filter,
        is_active=True
    )
    
    if parent_recipient:
        conversations_query = conversations_query.filter(parent_recipient=parent_recipient)
    
    return list(conversations_query.select_related('parent_recipient', 'created_by'))


def get_whisper_conversation_participants(
    whisper_conversation: WhisperConversation
) -> List[UserProfile]:
    """
    Get all active participants in a whisper conversation.
    
    Args:
        whisper_conversation: Whisper conversation to get participants for
        
    Returns:
        List of UserProfile objects
    """
    return list(
        UserProfile.objects.filter(
            whisperparticipant__whisper_conversation=whisper_conversation,
            whisperparticipant__is_active=True
        ).select_related()
    )


# Whisper Request Management Functions

def create_whisper_request(
    requester: UserProfile,
    recipient: UserProfile,
    parent_recipient: Recipient,
    proposed_participants: List[int]
) -> WhisperRequest:
    """
    Create a whisper request to invite someone to a whisper conversation.
    
    Args:
        requester: User sending the whisper request
        recipient: User receiving the whisper request
        parent_recipient: Parent conversation recipient
        proposed_participants: List of all proposed participant IDs (including requester and recipient)
        
    Returns:
        Created WhisperRequest object
        
    Raises:
        WhisperPermissionError: If user lacks permission
        WhisperValidationError: If request is invalid
    """
    # Validate that both users have access to parent conversation
    if not has_access_to_recipient(requester, parent_recipient):
        raise WhisperPermissionError("You don't have access to this conversation")
    
    if not has_access_to_recipient(recipient, parent_recipient):
        raise WhisperPermissionError("Recipient doesn't have access to this conversation")
    
    # Check if there's already a pending request between these users for this conversation
    existing_request = WhisperRequest.objects.filter(
        requester=requester,
        recipient=recipient,
        parent_recipient=parent_recipient,
        status=WhisperRequest.Status.PENDING
    ).first()
    
    if existing_request:
        raise WhisperValidationError("A whisper request is already pending for this user")
    
    # Check if they're already in a whisper conversation together
    if proposed_participants:
        existing_conversation = get_active_whisper_conversation(parent_recipient, proposed_participants)
        if existing_conversation and is_whisper_participant(existing_conversation, recipient):
            raise WhisperValidationError("User is already in a whisper conversation with you")
    
    # Create the request
    whisper_request = WhisperRequest.objects.create(
        requester=requester,
        recipient=recipient,
        parent_recipient=parent_recipient,
        realm=requester.realm
    )
    
    return whisper_request


def respond_to_whisper_request(
    whisper_request: WhisperRequest,
    responding_user: UserProfile,
    accept: bool,
    additional_participants: Optional[List[int]] = None
) -> Optional[WhisperConversation]:
    """
    Respond to a whisper request by accepting or declining it.
    
    Args:
        whisper_request: The whisper request to respond to
        responding_user: User responding to the request
        accept: True to accept, False to decline
        additional_participants: Additional participant IDs if accepting
        
    Returns:
        WhisperConversation if accepted, None if declined
        
    Raises:
        WhisperPermissionError: If user lacks permission
        WhisperValidationError: If request is invalid
    """
    # Validate that the responding user is the recipient
    if whisper_request.recipient != responding_user:
        raise WhisperPermissionError("You can only respond to your own whisper requests")
    
    # Check if request is still pending
    if whisper_request.status != WhisperRequest.Status.PENDING:
        raise WhisperValidationError("This whisper request is no longer pending")
    
    # Update request status
    if accept:
        whisper_request.status = WhisperRequest.Status.ACCEPTED
        
        # Create whisper conversation
        base_participants = [whisper_request.requester.id]
        if additional_participants:
            # Validate additional participants
            validate_whisper_participants(
                responding_user, additional_participants, whisper_request.parent_recipient
            )
            base_participants.extend(additional_participants)
        
        # Create the conversation
        whisper_conversation = create_whisper_conversation(
            responding_user,
            base_participants,
            whisper_request.parent_recipient
        )
        
        # Link the request to the conversation
        whisper_request.whisper_conversation = whisper_conversation
        whisper_request.save()
        
        return whisper_conversation
    else:
        whisper_request.status = WhisperRequest.Status.DECLINED
        whisper_request.save()
        return None


def get_pending_whisper_requests_for_user(user: UserProfile) -> List[WhisperRequest]:
    """
    Get all pending whisper requests for a user.
    
    Args:
        user: User to get requests for
        
    Returns:
        List of pending WhisperRequest objects
    """
    return list(
        WhisperRequest.objects.filter(
            recipient=user,
            status=WhisperRequest.Status.PENDING
        ).select_related('requester', 'parent_recipient').order_by('-created_at')
    )


def get_sent_whisper_requests_for_user(user: UserProfile) -> List[WhisperRequest]:
    """
    Get all whisper requests sent by a user.
    
    Args:
        user: User to get sent requests for
        
    Returns:
        List of WhisperRequest objects sent by the user
    """
    return list(
        WhisperRequest.objects.filter(
            requester=user
        ).select_related('recipient', 'parent_recipient').order_by('-created_at')
    )


def cancel_whisper_request(
    whisper_request: WhisperRequest,
    requesting_user: UserProfile
) -> None:
    """
    Cancel a pending whisper request.
    
    Args:
        whisper_request: The whisper request to cancel
        requesting_user: User requesting the cancellation
        
    Raises:
        WhisperPermissionError: If user lacks permission
        WhisperValidationError: If request cannot be cancelled
    """
    # Only the requester can cancel their own requests
    if whisper_request.requester != requesting_user:
        raise WhisperPermissionError("You can only cancel your own whisper requests")
    
    # Can only cancel pending requests
    if whisper_request.status != WhisperRequest.Status.PENDING:
        raise WhisperValidationError("Can only cancel pending whisper requests")
    
    # Mark as expired (we use expired status for cancelled requests)
    whisper_request.status = WhisperRequest.Status.EXPIRED
    whisper_request.save()


def get_whisper_request_by_id(request_id: int, user: UserProfile) -> WhisperRequest:
    """
    Get a whisper request by ID, ensuring the user has permission to access it.
    
    Args:
        request_id: ID of the whisper request
        user: User requesting access
        
    Returns:
        WhisperRequest object
        
    Raises:
        WhisperPermissionError: If user lacks permission
        WhisperValidationError: If request doesn't exist
    """
    try:
        whisper_request = WhisperRequest.objects.select_related(
            'requester', 'recipient', 'parent_recipient'
        ).get(id=request_id)
    except WhisperRequest.DoesNotExist:
        raise WhisperValidationError("Whisper request not found")
    
    # User must be either the requester or recipient
    if user not in [whisper_request.requester, whisper_request.recipient]:
        raise WhisperPermissionError("You don't have access to this whisper request")
    
    return whisper_request


def bulk_expire_whisper_requests_for_conversation(
    whisper_conversation: WhisperConversation
) -> int:
    """
    Expire all pending whisper requests related to a conversation when it's created.
    
    Args:
        whisper_conversation: The whisper conversation that was created
        
    Returns:
        Number of requests expired
    """
    # Get all participants in the conversation
    participant_ids = list(whisper_conversation.get_participant_ids())
    
    # Find pending requests between any participants for the same parent conversation
    pending_requests = WhisperRequest.objects.filter(
        parent_recipient=whisper_conversation.parent_recipient,
        status=WhisperRequest.Status.PENDING,
        requester_id__in=participant_ids,
        recipient_id__in=participant_ids
    )
    
    count = pending_requests.count()
    pending_requests.update(status=WhisperRequest.Status.EXPIRED)
    
    return count


def get_whisper_request_stats_for_user(user: UserProfile) -> Dict[str, int]:
    """
    Get statistics about whisper requests for a user.
    
    Args:
        user: User to get stats for
        
    Returns:
        Dictionary with request statistics
    """
    received_requests = WhisperRequest.objects.filter(recipient=user)
    sent_requests = WhisperRequest.objects.filter(requester=user)
    
    return {
        'received_pending': received_requests.filter(status=WhisperRequest.Status.PENDING).count(),
        'received_total': received_requests.count(),
        'received_accepted': received_requests.filter(status=WhisperRequest.Status.ACCEPTED).count(),
        'received_declined': received_requests.filter(status=WhisperRequest.Status.DECLINED).count(),
        'sent_pending': sent_requests.filter(status=WhisperRequest.Status.PENDING).count(),
        'sent_total': sent_requests.count(),
        'sent_accepted': sent_requests.filter(status=WhisperRequest.Status.ACCEPTED).count(),
        'sent_declined': sent_requests.filter(status=WhisperRequest.Status.DECLINED).count(),
    }


def validate_whisper_request_rate_limit(
    requester: UserProfile,
    recipient: UserProfile,
    time_window_minutes: int = 60,
    max_requests: int = 5
) -> None:
    """
    Validate that the user hasn't exceeded whisper request rate limits.
    
    Args:
        requester: User sending the request
        recipient: User receiving the request
        time_window_minutes: Time window for rate limiting
        max_requests: Maximum requests allowed in time window
        
    Raises:
        WhisperValidationError: If rate limit exceeded
    """
    time_threshold = timezone_now() - timedelta(minutes=time_window_minutes)
    
    # Check requests from this user to any recipient
    recent_requests_count = WhisperRequest.objects.filter(
        requester=requester,
        created_at__gte=time_threshold
    ).count()
    
    if recent_requests_count >= max_requests:
        raise WhisperValidationError(
            f"Too many whisper requests sent recently. Please wait before sending more."
        )
    
    # Check requests from this user to this specific recipient
    recent_requests_to_user = WhisperRequest.objects.filter(
        requester=requester,
        recipient=recipient,
        created_at__gte=time_threshold
    ).count()
    
    if recent_requests_to_user >= 2:  # Lower limit for same recipient
        raise WhisperValidationError(
            f"Too many whisper requests sent to this user recently."
        )