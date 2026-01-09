from django.utils.translation import gettext as _

from zerver.actions.user_topics import do_set_user_topic_visibility_policy
from zerver.lib.cache import cache_delete, to_dict_cache_key_id
from zerver.lib.exceptions import JsonableError
from zerver.lib.message import (
    event_recipient_ids_for_action_on_messages,
    set_visibility_policy_possible,
    should_change_visibility_policy,
    visibility_policy_for_participation,
)
from zerver.lib.streams import access_stream_by_id
from zerver.models import Realm, SubMessage, UserProfile
from zerver.tornado.django_api import send_event_on_commit


def verify_submessage_sender(
    *,
    message_id: int,
    message_sender_id: int,
    submessage_sender_id: int,
) -> None:
    """Even though our submessage architecture is geared toward
    collaboration among all message readers, we still enforce
    the first person to attach a submessage to the message
    must be the original sender of the message.
    """

    if message_sender_id == submessage_sender_id:
        return

    if SubMessage.objects.filter(
        message_id=message_id,
        sender_id=message_sender_id,
    ).exists():
        return

    raise JsonableError(_("You cannot attach a submessage to this message."))


def do_add_submessage(
    realm: Realm,
    sender_id: int,
    message_id: int,
    msg_type: str,
    content: str,
    *,
    visible_user_ids: list[int] | None = None,
) -> None:
    """Should be called while holding a SELECT FOR UPDATE lock
    (e.g. via access_message(..., lock_message=True)) on the
    Message row, to prevent race conditions.

    If visible_user_ids is provided, the submessage will only be
    visible to those specific users (ephemeral/private responses).
    """
    submessage = SubMessage(
        sender_id=sender_id,
        message_id=message_id,
        msg_type=msg_type,
        content=content,
        visible_to=visible_user_ids,
    )
    submessage.save()

    # Invalidate the message cache since submessages are cached with the message
    cache_delete(to_dict_cache_key_id(message_id))

    # Determine and set the visibility_policy depending on 'automatically_follow_topics_policy'
    # and 'automatically_unmute_topics_policy'.
    sender = submessage.sender
    if set_visibility_policy_possible(
        sender, submessage.message
    ) and UserProfile.AUTOMATICALLY_CHANGE_VISIBILITY_POLICY_ON_PARTICIPATION in [
        sender.automatically_follow_topics_policy,
        sender.automatically_unmute_topics_in_muted_streams_policy,
    ]:
        stream_id = submessage.message.recipient.type_id
        (stream, sub) = access_stream_by_id(sender, stream_id)
        assert stream is not None
        if sub:
            new_visibility_policy = visibility_policy_for_participation(sender, sub.is_muted)
            if new_visibility_policy and should_change_visibility_policy(
                new_visibility_policy,
                sender,
                stream_id,
                topic_name=submessage.message.topic_name(),
            ):
                do_set_user_topic_visibility_policy(
                    user_profile=sender,
                    stream=stream,
                    topic_name=submessage.message.topic_name(),
                    visibility_policy=new_visibility_policy,
                )

    event = dict(
        type="submessage",
        msg_type=msg_type,
        message_id=message_id,
        submessage_id=submessage.id,
        sender_id=sender_id,
        content=content,
        # Include visibility info so frontend can render ephemeral indicator
        visible_to=visible_user_ids,
    )

    # Determine target users for the event
    all_recipient_ids = event_recipient_ids_for_action_on_messages(
        [submessage.message.id], submessage.message.is_channel_message
    )

    if visible_user_ids is not None:
        # Filter to only users who can see the message AND are in the visibility list
        target_user_ids = list(all_recipient_ids & set(visible_user_ids))
    else:
        target_user_ids = list(all_recipient_ids)

    send_event_on_commit(realm, event, target_user_ids)


def do_delete_submessage(
    user_profile: UserProfile,
    submessage_id: int,
) -> None:
    """Delete a submessage. Users can only delete submessages that are
    visible only to them (ephemeral responses).
    """
    try:
        submessage = SubMessage.objects.get(id=submessage_id)
    except SubMessage.DoesNotExist:
        raise JsonableError(_("Submessage not found."))

    # Only allow deletion of ephemeral messages visible to the user
    visible_to = submessage.visible_to
    if visible_to is None:
        raise JsonableError(_("Cannot delete this submessage."))

    if user_profile.id not in visible_to:
        raise JsonableError(_("Cannot delete this submessage."))

    message_id = submessage.message_id

    # If the user is the only one who can see it, delete it entirely
    if len(visible_to) == 1:
        submessage.delete()
    else:
        # Remove this user from the visibility list
        visible_to.remove(user_profile.id)
        submessage.visible_to = visible_to
        submessage.save(update_fields=["visible_to"])

    # Invalidate the message cache since submessages are cached with the message
    cache_delete(to_dict_cache_key_id(message_id))

    # Send event to notify the user
    event = dict(
        type="submessage",
        op="remove",
        message_id=message_id,
        submessage_id=submessage_id,
    )
    send_event_on_commit(user_profile.realm, event, [user_profile.id])
