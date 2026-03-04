<<<<<<< HEAD
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
=======
from typing import Any, List
from django.utils.translation import gettext as _
from zerver.models import UserProfile, Stream, Recipient
from zerver.models.channel_folders import ChannelFolder
from zerver.actions.streams import bulk_add_subscriptions, get_subscriber_ids
from zerver.lib.streams import create_stream_if_needed, access_stream_by_name
from zerver.lib.exceptions import JsonableError

def get_realm_users_list(realm_obj) -> str:
    """Get a list of all active users and their IDs in the current Realm."""
    from zerver.models import Realm
    if isinstance(realm_obj, int):
        realm = Realm.objects.get(id=realm_obj)
    else:
        realm = realm_obj
        
    users = UserProfile.objects.filter(realm=realm, is_active=True).only("id", "full_name")
    lines = [f"ID: {user.id} | Name: {user.full_name}" for user in users]
    return "Realm Users:\n" + "\n".join(lines)

def get_channel_users_list(user_profile: UserProfile, channel_name: str) -> str:
    """Get a list of subscribed users and their IDs for a specific channel."""
    try:
        if isinstance(user_profile, int):
            user_profile = UserProfile.objects.get(id=user_profile)
            
        # access_stream_by_name returns a tuple (Stream, Subscription)
        stream = access_stream_by_name(user_profile, channel_name)[0]
        
        # get_subscriber_ids requires a Stream object
        user_ids = get_subscriber_ids(stream, requesting_user=user_profile)
        
        users = UserProfile.objects.filter(id__in=user_ids, is_active=True).only("id", "full_name")
        lines = [f"ID: {user.id} | Name: {user.full_name}" for user in users]
        return f"Users in #{channel_name}:\n" + "\n".join(lines)
    except Exception as e:
        return f"Error accessing channel '{channel_name}': {str(e)}"

def add_persons_to_channel_by_id(acting_user: UserProfile, channel_name: str, user_ids: List[int]) -> str:
    """Add persons to a private channel categorized under the 'meetings' folder."""
    if isinstance(acting_user, int):
        acting_user = UserProfile.objects.get(id=acting_user)
        
    realm = acting_user.realm
    
    # Ensure the 'meetings' folder exists for this realm
    folder, _ = ChannelFolder.objects.get_or_create(realm=realm, name="meetings")
    
    # 1. Create or get the stream as PRIVATE and assign it to the 'meetings' FOLDER
    stream, created = create_stream_if_needed(
        realm, 
        channel_name, 
        invite_only=False, 
        folder=folder, 
        acting_user=acting_user
    )
    
    # 2. Find and validate users
    users_to_add = UserProfile.objects.filter(realm=realm, id__in=user_ids, is_active=True)
    found_ids = {user.id for user in users_to_add}
    missing_ids = [uid for uid in user_ids if uid not in found_ids]

    if missing_ids:
        return f"Error: User IDs not found or inactive: {missing_ids}"

    if not users_to_add:
         return "No valid users specified."

    # 3. Bulk subscribe users to the stream
    bulk_add_subscriptions(realm, [stream], users_to_add, acting_user=acting_user)
    
    status = "created and " if created else ""
    return f"Successfully {status}added {len(users_to_add)} persons to channel '{channel_name}' (Private, Folder: meetings)."
>>>>>>> origin
