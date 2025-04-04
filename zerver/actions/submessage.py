from django.utils.translation import gettext as _

from zerver.actions.user_topics import do_set_user_topic_visibility_policy
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
) -> None:
    """Should be called while holding a SELECT FOR UPDATE lock
    (e.g. via access_message(..., lock_message=True)) on the
    Message row, to prevent race conditions.
    """
    submessage = SubMessage(
        sender_id=sender_id,
        message_id=message_id,
        msg_type=msg_type,
        content=content,
    )
    submessage.save()

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
    )
    target_user_ids = event_recipient_ids_for_action_on_messages([submessage.message])

    send_event_on_commit(realm, event, target_user_ids)
