from collections import defaultdict
from collections.abc import Iterable
from typing import TypedDict

from zerver.lib import retention
from zerver.lib.message import classify_stream_messages, event_recipient_ids_for_action_on_messages
from zerver.lib.retention import move_messages_to_archive
from zerver.models import Message, Realm, Stream, UserProfile
from zerver.models.recipients import Recipient
from zerver.tornado.django_api import send_event_on_commit


class DeleteMessagesEvent(TypedDict, total=False):
    type: str
    message_ids: list[int]
    message_type: str
    topic: str
    stream_id: int


class MessageDeleteAction(TypedDict, total=False):
    delete_public_stream_messages: bool
    delete_private_stream_messages: bool
    delete_direct_messages: bool


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


def _process_grouped_messages_deletion(
    realm: Realm,
    grouped_messages: list[Message],
    *,
    stream: Stream | None,
    topic: str | None,
    acting_user: UserProfile | None,
) -> None:
    """
    Helper for do_delete_messages. Should not be called directly otherwise.
    """

    message_ids = [message.id for message in grouped_messages]
    if not message_ids:
        return  # nocoverage

    event: DeleteMessagesEvent = {
        "type": "delete_message",
        "message_ids": sorted(message_ids),
    }
    if stream is None:
        assert topic is None
        message_type = "private"
        archiving_chunk_size = retention.MESSAGE_BATCH_SIZE
    else:
        assert topic is not None
        message_type = "stream"
        event["stream_id"] = stream.id
        event["topic"] = topic
        archiving_chunk_size = retention.STREAM_MESSAGE_BATCH_SIZE
    event["message_type"] = message_type

    # We exclude long-term idle users, since they by definition have no active clients.
    users_to_notify = event_recipient_ids_for_action_on_messages(
        grouped_messages,
        channel=stream if message_type == "stream" else None,
    )

    if acting_user is not None:
        # Always send event to the user who deleted the message.
        users_to_notify.add(acting_user.id)

    move_messages_to_archive(message_ids, realm=realm, chunk_size=archiving_chunk_size)
    if stream is not None:
        check_update_first_message_id(realm, stream, message_ids, users_to_notify)

    send_event_on_commit(realm, event, users_to_notify)


def do_delete_messages(
    realm: Realm,
    messages: Iterable[Message],
    *,
    acting_user: UserProfile | None,
    streams_by_recipient_id: dict[int, Stream] | None = None,
) -> None:
    """1:1 Direct messages must be grouped to a single convesration by
    the caller, since this logic does not know how to handle multiple
    senders sharing a single Recipient object.

    When the Recipient.PERSONAL is no longer a case to consider, this
    restriction can be deleted.
    Args:
        streams_by_recipient_id: Optional dict mapping recipient_id to Stream objects
                                to avoid redundant database queries.
    """
    private_messages_by_recipient: defaultdict[int, list[Message]] = defaultdict(list)
    stream_messages_by_recipient_and_topic: defaultdict[tuple[int, str], list[Message]] = (
        defaultdict(list)
    )
    stream_by_recipient_id = streams_by_recipient_id or {}
    for message in messages:
        if message.is_stream_message():
            recipient_id = message.recipient_id
            # topics are case-insensitive.
            topic_name = message.topic_name().lower()
            stream_messages_by_recipient_and_topic[(recipient_id, topic_name)].append(message)
        else:
            recipient_id = message.recipient.id
            private_messages_by_recipient[recipient_id].append(message)

    for recipient_id, grouped_messages in sorted(private_messages_by_recipient.items()):
        _process_grouped_messages_deletion(
            realm, grouped_messages, stream=None, topic=None, acting_user=acting_user
        )

    for (
        (recipient_id, topic_name),
        grouped_messages,
    ) in sorted(stream_messages_by_recipient_and_topic.items()):
        if recipient_id not in stream_by_recipient_id:
            stream_by_recipient_id[recipient_id] = Stream.objects.get(recipient_id=recipient_id)
        stream = stream_by_recipient_id[recipient_id]
        _process_grouped_messages_deletion(
            realm, grouped_messages, stream=stream, topic=topic_name, acting_user=acting_user
        )


def do_delete_messages_by_sender(user: UserProfile) -> None:
    message_ids = list(
        # Uses index: zerver_message_realm_sender_recipient (prefix)
        Message.objects.filter(realm_id=user.realm_id, sender=user)
        .values_list("id", flat=True)
        .order_by("id")
    )
    if message_ids:
        move_messages_to_archive(message_ids, chunk_size=retention.STREAM_MESSAGE_BATCH_SIZE)


def _group_personal_messages_by_conversation(
    user_direct_messages: list[Message], sender_id: int
) -> tuple[dict[int, list[Message]], list[Message]]:
    """
    Group 1:1 DMs by the other participant to ensure proper event handling.
    This prevents issues where events are sent to wrong users when processing
    messages from different directions of the same conversation separately.

    Returns:
        - Dictionary mapping other participant ID to their 1:1 messages with sender
        - List of group DM messages (which can be processed normally)
    """
    personal_messages_by_other_user: dict[int, list[Message]] = {}
    direct_message_group_messages: list[Message] = []

    for message in user_direct_messages:
        if message.recipient.type == Recipient.PERSONAL:
            # For 1:1 DMs, group by the other participant
            # message.recipient.type_id is the recipient user ID
            other_user_id = message.recipient.type_id
            if other_user_id not in personal_messages_by_other_user:
                personal_messages_by_other_user[other_user_id] = []
            personal_messages_by_other_user[other_user_id].append(message)
        else:
            # For group DMs, we can process them normally since they share the same recipient
            direct_message_group_messages.append(message)

    return personal_messages_by_other_user, direct_message_group_messages


def delete_deactivated_user_messages(
    realm: Realm, user_profile: UserProfile, message_delete_action: MessageDeleteAction
) -> None:
    if not (
        message_delete_action.get("delete_public_stream_messages", False)
        or message_delete_action.get("delete_private_stream_messages", False)
        or message_delete_action.get("delete_direct_messages", False)
    ):
        return

    if message_delete_action.get(
        "delete_public_stream_messages", False
    ) or message_delete_action.get("delete_private_stream_messages", False):
        user_stream_messages = list(
            Message.objects.filter(
                realm_id=user_profile.realm_id,
                sender=user_profile,
                recipient__type=Recipient.STREAM,
            ).select_related("recipient")
        )

        messages_to_delete = []
        if message_delete_action.get(
            "delete_public_stream_messages", False
        ) and message_delete_action.get("delete_private_stream_messages", False):
            # Delete all stream messages
            messages_to_delete = user_stream_messages
        else:
            # Only delete specific types
            private_stream_messages, public_stream_messages = classify_stream_messages(
                realm, user_stream_messages
            )
            if message_delete_action.get("delete_public_stream_messages", False):
                messages_to_delete.extend(public_stream_messages)
            if message_delete_action.get("delete_private_stream_messages", False):
                messages_to_delete.extend(private_stream_messages)

        if messages_to_delete:
            do_delete_messages(user_profile.realm, messages_to_delete, acting_user=user_profile)

    if message_delete_action.get("delete_direct_messages", False):
        user_direct_messages = list(
            Message.objects.filter(
                realm_id=user_profile.realm_id,
                sender=user_profile,
                recipient__type__in=[Recipient.PERSONAL, Recipient.DIRECT_MESSAGE_GROUP],
            ).select_related("recipient")
        )

        personal_messages_by_other_user, direct_message_group_messages = (
            _group_personal_messages_by_conversation(user_direct_messages, user_profile.id)
        )

        # Delete 1:1 messages for each conversation separately
        for conversation_messages in personal_messages_by_other_user.values():
            do_delete_messages(user_profile.realm, conversation_messages, acting_user=user_profile)

        # Delete group DM messages together
        if direct_message_group_messages:
            do_delete_messages(
                user_profile.realm, direct_message_group_messages, acting_user=user_profile
            )
