from collections.abc import Iterable
from typing import TypedDict

from zerver.lib import retention
from zerver.lib.message import event_recipient_ids_for_action_on_messages
from zerver.lib.retention import move_messages_to_archive
from zerver.models import Message, Realm, Stream, UserProfile
from zerver.models.recipients import Recipient
from zerver.models.streams import get_all_streams
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
    # messages in delete_message event belong to the same topic
    # or is a single direct message, as any other behaviour is not possible with
    # the current callers to this method.
    messages = list(messages)
    message_ids = [message.id for message in messages]
    if not message_ids:
        return

    event: DeleteMessagesEvent = {
        "type": "delete_message",
        "message_ids": message_ids,
    }

    sample_message = messages[0]
    message_type = "stream"
    users_to_notify = set()
    if not sample_message.is_stream_message():
        message_type = "private"
    archiving_chunk_size = (
        retention.STREAM_MESSAGE_BATCH_SIZE
        if message_type == "stream"
        else retention.MESSAGE_BATCH_SIZE
    )

    if message_type == "stream":
        stream_id = sample_message.recipient.type_id
        event["stream_id"] = stream_id
        event["topic"] = sample_message.topic_name()
        stream = Stream.objects.get(id=stream_id)
        archiving_chunk_size = retention.STREAM_MESSAGE_BATCH_SIZE

    # We exclude long-term idle users, since they by definition have no active clients.
    users_to_notify = event_recipient_ids_for_action_on_messages(
        messages,
        channel=stream if message_type == "stream" else None,
    )

    if acting_user is not None:
        # Always send event to the user who deleted the message.
        users_to_notify.add(acting_user.id)

    move_messages_to_archive(message_ids, realm=realm, chunk_size=archiving_chunk_size)
    if message_type == "stream":
        check_update_first_message_id(realm, stream, message_ids, users_to_notify)

    event["message_type"] = message_type
    send_event_on_commit(realm, event, users_to_notify)


def do_delete_messages_by_sender(user: UserProfile) -> None:
    message_ids = list(
        # Uses index: zerver_message_realm_sender_recipient (prefix)
        Message.objects.filter(realm_id=user.realm_id, sender=user)
        .values_list("id", flat=True)
        .order_by("id")
    )
    if message_ids:
        move_messages_to_archive(message_ids, chunk_size=retention.STREAM_MESSAGE_BATCH_SIZE)


def classify_messages(
    realm: Realm, messages: Iterable[Message]
) -> tuple[list[Message], list[Message]]:
    private_stream_messages = []
    public_stream_messages = []

    streams = get_all_streams(realm=realm, include_archived_channels=True)
    public_streams = [stream for stream in streams if stream.is_public()]

    for message in messages:
        if message.recipient.type == Recipient.STREAM:
            stream = Stream.objects.get(id=message.recipient.type_id)
            if stream in public_streams:
                public_stream_messages.append(message)
            else:
                private_stream_messages.append(message)

    return private_stream_messages, public_stream_messages


def delete_deactivated_user_messages(
    realm: Realm, user_profile: UserProfile, message_delete_action: int
) -> None:
    if message_delete_action == Message.NO_DELETE_ACTION:
        return
    user_messages = list(
        Message.objects.filter(realm_id=user_profile.realm_id, sender=user_profile).only(
            "id", "recipient__type", "recipient__type_id"
        )
    )

    private_stream_messages, public_stream_messages = classify_messages(realm, user_messages)
    if message_delete_action == Message.DELETE_PUBLIC_STREAM_MESSAGES:
        do_delete_messages(user_profile.realm, public_stream_messages, acting_user=user_profile)
    elif message_delete_action == Message.DELETE_ALL_MESSAGES:
        do_delete_messages(user_profile.realm, private_stream_messages, acting_user=user_profile)
        do_delete_messages(user_profile.realm, public_stream_messages, acting_user=user_profile)
