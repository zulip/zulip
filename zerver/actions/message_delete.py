from collections.abc import Iterable
from typing import TypedDict

from zerver.lib import retention
from zerver.lib.retention import move_messages_to_archive
from zerver.models import Message, Realm, Stream, UserProfile
from zerver.tornado.django_api import send_event_on_commit


class DeleteMessagesEvent(TypedDict, total=False):
    type: str
    message_ids: list[int]
    message_type: str
    topic: str
    stream_id: int


def check_update_first_message_id(
    realm: Realm, stream: Stream, message_ids: list[int], users_to_notify: Iterable[int]
) -> None:
    # This will not update the `first_message_id` of streams where the
    # first message was deleted prior to the implementation of this function.
    assert stream.recipient_id is not None
    if stream.first_message_id not in message_ids:
        return
    current_first_message_id = (
        Message.objects.filter(realm_id=realm.id, recipient_id=stream.recipient_id)
        .values_list("id", flat=True)
        .order_by("id")
        .first()
    )

    stream.first_message_id = current_first_message_id
    stream.save(update_fields=["first_message_id"])

    stream_event = dict(
        type="stream",
        op="update",
        property="first_message_id",
        value=stream.first_message_id,
        stream_id=stream.id,
        name=stream.name,
    )
    send_event_on_commit(realm, stream_event, users_to_notify)


def do_delete_messages(
    realm: Realm, messages: Iterable[Message], *, acting_user: UserProfile | None
) -> None:
    """1:1 Direct messages must be grouped to a single conversation by
    the caller, since this logic does not know how to handle multiple
    senders sharing a single Recipient object.

    When the Recipient.PERSONAL is no longer a case to consider, this
    restriction can be deleted.
    """
    message_ids = [message.id for message in messages]
    move_messages_to_archive(
        message_ids,
        realm=realm,
        chunk_size=retention.STREAM_MESSAGE_BATCH_SIZE,
        acting_user=acting_user,
    )


def do_delete_messages_by_sender(user: UserProfile) -> None:
    message_ids = list(
        # Uses index: zerver_message_realm_sender_recipient (prefix)
        Message.objects.filter(realm_id=user.realm_id, sender=user)
        .values_list("id", flat=True)
        .order_by("id")
    )
    move_messages_to_archive(
        message_ids, user.realm, chunk_size=retention.STREAM_MESSAGE_BATCH_SIZE
    )
