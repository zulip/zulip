from collections import defaultdict
from collections.abc import Collection, Iterable
from typing import Any, TypedDict

from django.db.models import Q
from django.utils.timezone import now as timezone_now
from pydantic import BaseModel

from zerver.lib import retention
from zerver.lib.message import bulk_access_messages
from zerver.lib.message_cache import MessageDict
from zerver.lib.retention import move_messages_to_archive
from zerver.lib.streams import get_public_streams_queryset, subscribed_to_stream
from zerver.lib.users import get_user_ids_who_can_access_user, user_access_restricted_in_realm
from zerver.models import ArchiveTransaction, Message, Realm, Stream, UserMessage, UserProfile
from zerver.models.recipients import Recipient
from zerver.tornado.django_api import send_event_on_commit


class DeleteMessagesEvent(TypedDict, total=False):
    type: str
    message_ids: list[int]
    message_type: str
    topic: str
    stream_id: int


class DeactivateUserActions(BaseModel):
    delete_profile: bool = False
    delete_public_channel_messages: bool = False
    delete_private_channel_messages: bool = False
    delete_direct_messages: bool = False


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
    message_ids = [message.id for message in messages]
    move_messages_to_archive(
        message_ids,
        realm=realm,
        chunk_size=retention.STREAM_MESSAGE_BATCH_SIZE,
        acting_user=acting_user,
    )


def do_restore_messages(
    realm: Realm,
    archive_transactions: Collection[ArchiveTransaction],
    *,
    acting_user: UserProfile,
) -> list[int]:
    """Restore the messages archived in the given transactions, re-displaying
    them for all of their original recipients.

    This implements a user-facing "undo" of a recent deletion. The caller is
    responsible for authorizing the restore (confirming that acting_user
    performed the deletion and is still within the undo window) and must run
    inside a durable transaction so the restore and its events commit
    atomically.
    """
    restored_message_ids: list[int] = []
    for archive_transaction in archive_transactions:
        restored_message_ids += retention.restore_messages_from_archive(archive_transaction.id)
        retention.restore_models_with_message_key_from_archive(archive_transaction.id)
        retention.restore_attachments_from_archive(archive_transaction.id)
        retention.restore_attachment_messages_from_archive(archive_transaction.id)
        archive_transaction.restored = True
        archive_transaction.restored_timestamp = timezone_now()
        archive_transaction.save(update_fields=["restored", "restored_timestamp"])

    if restored_message_ids:
        notify_restored_messages(realm, restored_message_ids, acting_user=acting_user)

    return restored_message_ids


def notify_restored_messages(
    realm: Realm, message_ids: list[int], *, acting_user: UserProfile
) -> None:
    messages = list(
        Message.objects.filter(id__in=message_ids)
        .select_related(*Message.DEFAULT_SELECT_RELATED)
        .order_by("id")
    )

    # The acting user must see the messages reappear on undo even if they
    # aren't a recipient (e.g. an admin restoring in a channel they don't
    # follow), mirroring the delete path. Access is re-checked, not assumed.
    acting_user_accessible_message_ids = {
        message.id
        for message in bulk_access_messages(acting_user, messages, is_modifying_message=False)
    }

    # The recipients and their per-message flags come from the restored
    # UserMessage rows: exactly the users who had each message, with the
    # read/mention state they had when it was deleted. Long-term-idle users
    # have no active clients, so we skip live updates for them.
    flags_by_message: dict[int, dict[int, list[str]]] = defaultdict(dict)
    for user_message in UserMessage.objects.filter(message_id__in=message_ids).exclude(
        user_profile__long_term_idle=True
    ):
        flags_by_message[user_message.message_id][user_message.user_profile_id] = (
            user_message.flags_list()
        )

    # Map channel messages to their Stream without an N+1 query.
    channel_recipient_ids = {
        message.recipient_id for message in messages if message.is_channel_message
    }
    streams_by_recipient_id = {
        stream.recipient_id: stream
        for stream in Stream.objects.filter(recipient_id__in=channel_recipient_ids)
    }

    # Channels with at least one restored message, and the user IDs to notify
    # of any resulting first_message_id change, gathered as we build events.
    affected_streams: dict[int, Stream] = {}
    notify_user_ids_by_stream: dict[int, set[int]] = defaultdict(set)

    for message in messages:
        users: list[dict[str, Any]] = [
            dict(id=user_id, flags=flags, mentioned_user_group_id=None)
            for user_id, flags in flags_by_message[message.id].items()
        ]

        # Add the acting user (as read) if they can access the message but
        # weren't already a recipient above.
        if (
            message.id in acting_user_accessible_message_ids
            and acting_user.id not in flags_by_message[message.id]
        ):
            users.append(dict(id=acting_user.id, flags=["read"], mentioned_user_group_id=None))

        event: dict[str, Any] = dict(
            type="restored_message",
            message_dict=MessageDict.wide_dict(message, realm.id),
            realm_host=realm.host,
        )

        if message.is_channel_message:
            stream = streams_by_recipient_id[message.recipient_id]
            affected_streams[stream.id] = stream
            notify_user_ids_by_stream[stream.id].update(user["id"] for user in users)
            if stream.is_public():
                event["realm_id"] = realm.id
                event["stream_name"] = stream.name

            # If the sender is only accessible to a subset of recipients (e.g.
            # a guest who is not subscribed here), strip their identity from the
            # payload for the others, matching the original message event.
            sender = message.sender
            if user_access_restricted_in_realm(sender) and not subscribed_to_stream(
                sender, stream.id
            ):
                user_ids_who_can_access_sender = set(get_user_ids_who_can_access_user(sender))
                event["user_ids_without_access_to_sender"] = [
                    user["id"] for user in users if user["id"] not in user_ids_who_can_access_sender
                ]

        send_event_on_commit(realm, event, users)

    # A restored message may predate a channel's current first message, so
    # recompute first_message_id for each affected channel.
    for stream_id, stream in affected_streams.items():
        update_first_message_id_on_restore(realm, stream, notify_user_ids_by_stream[stream_id])


def update_first_message_id_on_restore(
    realm: Realm, stream: Stream, users_to_notify: Iterable[int]
) -> None:
    # The inverse of check_update_first_message_id: a restore can lower a
    # channel's first_message_id if an older message was brought back.
    assert stream.recipient_id is not None
    first_message_id = (
        Message.objects.filter(realm_id=realm.id, recipient_id=stream.recipient_id)
        .values_list("id", flat=True)
        .order_by("id")
        .first()
    )
    if first_message_id == stream.first_message_id:
        return

    stream.first_message_id = first_message_id
    stream.save(update_fields=["first_message_id"])

    stream_event = dict(
        type="stream",
        op="update",
        property="first_message_id",
        value=first_message_id,
        stream_id=stream.id,
        name=stream.name,
    )
    send_event_on_commit(realm, stream_event, users_to_notify)


def do_delete_messages_by_sender(user: UserProfile, skip_notify: bool = False) -> None:
    message_ids = list(
        # Uses index: zerver_message_realm_sender_recipient (prefix)
        Message.objects.filter(realm_id=user.realm_id, sender=user)
        .values_list("id", flat=True)
        .order_by("id")
    )
    move_messages_to_archive(
        message_ids,
        user.realm,
        chunk_size=retention.STREAM_MESSAGE_BATCH_SIZE,
        skip_notify=skip_notify,
    )


def delete_deactivated_user_messages(
    realm: Realm,
    user_profile: UserProfile,
    deactivate_user_actions: DeactivateUserActions,
    acting_user: UserProfile | None,
) -> None:
    delete_public_channel_messages = deactivate_user_actions.delete_public_channel_messages
    delete_private_channel_messages = deactivate_user_actions.delete_private_channel_messages
    delete_direct_messages = deactivate_user_actions.delete_direct_messages

    if not (
        delete_public_channel_messages or delete_private_channel_messages or delete_direct_messages
    ):
        return

    message_filter_query = Q()
    message_exclude_query = Q()

    if delete_direct_messages:
        message_filter_query |= Q(recipient__type=Recipient.DIRECT_MESSAGE_GROUP)

    public_channel_ids = get_public_streams_queryset(realm).values_list("id", flat=True)
    if delete_public_channel_messages and delete_private_channel_messages:
        message_filter_query |= Q(recipient__type=Recipient.STREAM)
    elif delete_public_channel_messages:
        message_filter_query |= Q(
            recipient__type=Recipient.STREAM,
            recipient__type_id__in=list(public_channel_ids),
        )
    elif delete_private_channel_messages:
        message_filter_query |= Q(recipient__type=Recipient.STREAM)
        message_exclude_query |= Q(
            recipient__type=Recipient.STREAM,
            recipient__type_id__in=list(public_channel_ids),
        )

    messages = list(
        Message.objects.filter(sender=user_profile, realm_id=user_profile.realm_id)
        .filter(message_filter_query)
        .exclude(message_exclude_query)
        .select_related("recipient")
    )
    do_delete_messages(user_profile.realm, messages, acting_user=acting_user)
