from typing import Iterable, List, TypedDict

from zerver.lib import retention
from zerver.lib.retention import move_messages_to_archive
from zerver.lib.stream_subscription import get_active_subscriptions_for_stream_id
from zerver.models import Message, Realm, Stream, UserMessage, UserProfile
from zerver.tornado.django_api import send_event_on_commit


class DeleteMessagesEvent(TypedDict, total=False):
    type: str
    message_ids: List[int]
    message_type: str
    topic: str
    stream_id: int


def check_update_first_message_id(
    realm: Realm, stream: Stream, message_ids: List[int], users_to_notify: Iterable[int]
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
    )
    send_event_on_commit(realm, stream_event, users_to_notify)


def do_delete_messages(realm: Realm, messages: Iterable[Message]) -> None:
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
    users_to_notify = []
    if not sample_message.is_stream_message():
        assert len(messages) == 1
        message_type = "private"
        ums = UserMessage.objects.filter(message_id__in=message_ids)
        users_to_notify = [um.user_profile_id for um in ums]
        archiving_chunk_size = retention.MESSAGE_BATCH_SIZE

    if message_type == "stream":
        stream_id = sample_message.recipient.type_id
        event["stream_id"] = stream_id
        event["topic"] = sample_message.topic_name()
        subscriptions = get_active_subscriptions_for_stream_id(
            stream_id, include_deactivated_users=False
        )
        # We exclude long-term idle users, since they by definition have no active clients.
        subscriptions = subscriptions.exclude(user_profile__long_term_idle=True)
        users_to_notify = list(subscriptions.values_list("user_profile_id", flat=True))
        archiving_chunk_size = retention.STREAM_MESSAGE_BATCH_SIZE

    move_messages_to_archive(message_ids, realm=realm, chunk_size=archiving_chunk_size)
    if message_type == "stream":
        stream = Stream.objects.get(id=sample_message.recipient.type_id)
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
