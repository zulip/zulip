from django.utils.translation import gettext as _

from zerver.lib.exceptions import JsonableError
from zerver.models import Realm, SubMessage, UserMessage
from zerver.tornado.django_api import send_event_on_commit


def verify_submessage_sender(
    *,
    message_id: int,
    message_sender_id: int,
    submessage_sender_id: int,
) -> None:
    """Even though our submessage architecture is geared toward
    collaboration among all message readers, we still enforce
    the the first person to attach a submessage to the message
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

    event = dict(
        type="submessage",
        msg_type=msg_type,
        message_id=message_id,
        submessage_id=submessage.id,
        sender_id=sender_id,
        content=content,
    )
    ums = UserMessage.objects.filter(message_id=message_id)
    target_user_ids = [um.user_profile_id for um in ums]

    send_event_on_commit(realm, event, target_user_ids)
