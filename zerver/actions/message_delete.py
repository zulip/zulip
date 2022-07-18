from typing import Any, Dict, Iterable, List, TypedDict

from django.db import transaction

from zerver.lib import retention as retention
from zerver.lib.retention import move_messages_to_archive
from zerver.lib.stream_subscription import get_active_subscriptions_for_stream_id
from zerver.models import Message, Realm, Recipient, UserMessage, UserProfile
from zerver.tornado.django_api import send_event


class DeleteMessagesEvent(TypedDict, total=False):
    type: str
    message_ids: List[int]
    message_type: str
    topic: str
    stream_id: int


def do_delete_messages(realm: Realm, messages: Iterable[Message]) -> None:
    # messages in delete_message event belong to the same topic
    # or is a single private message, as any other behaviour is not possible with
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

    event["message_type"] = message_type
    transaction.on_commit(lambda: send_event(realm, event, users_to_notify))


def do_delete_messages_by_sender(user: UserProfile) -> None:
    message_ids = list(
        Message.objects.filter(sender=user).values_list("id", flat=True).order_by("id")
    )
    if message_ids:
        move_messages_to_archive(message_ids, chunk_size=retention.STREAM_MESSAGE_BATCH_SIZE)


def classify_message(messages: Iterable[Message]) -> Dict[str, Dict[int, Any]]:
    # This function sorts the messages into a format that can be
    # used by delete_deactivated_user_messages function to delete
    # messages from a topic together in bulk and messages from a
    # a private message individually.

    message_dict: Dict[str, Dict[int, Any]] = {"stream": {}, "private": {}}
    messages = list(messages)
    stream_messages = [
        message for message in messages if message.recipient.type == Recipient.STREAM
    ]
    private_messages = [
        message for message in messages if message.recipient.type != Recipient.STREAM
    ]

    for message in stream_messages:
        recipient_id = message.recipient.id
        topic_name = message.topic_name()

        if recipient_id in message_dict["stream"]:
            if topic_name in message_dict["stream"][recipient_id]:
                message_dict["stream"][recipient_id][topic_name].append(message)
            else:
                message_dict["stream"][recipient_id][topic_name] = [message]
        else:
            message_dict["stream"][recipient_id] = {}
            message_dict["stream"][recipient_id][topic_name] = [message]

    for message in private_messages:
        recipient_id = message.recipient.id
        if recipient_id in message_dict["private"]:
            message_dict["private"][recipient_id].append(message)
        else:
            message_dict["private"][recipient_id] = [message]

    return message_dict


def delete_deactivated_user_messages(user_profile: UserProfile, delete_policy: int) -> None:

    user_messages = Message.objects.filter(sender=user_profile)

    if delete_policy == Message.DELETE_PUBLIC_STREAM_MESSAGE:
        public_stream_messages = [
            message for message in user_messages if message.is_public_stream_message()
        ]
        public_message_dict = classify_message(public_stream_messages)
        for stream, topic in public_message_dict["stream"].items():
            for topic, messages in topic.items():
                do_delete_messages(user_profile.realm, messages)

    elif delete_policy == Message.DELETE_ALL_MESSAGE:
        user_message_dict = classify_message(user_messages)
        for stream, topic in user_message_dict["stream"].items():
            for topic, messages in topic.items():
                do_delete_messages(user_profile.realm, messages)

        for privates, messages in user_message_dict["private"].items():
            for message in messages:
                do_delete_messages(user_profile.realm, [message])
