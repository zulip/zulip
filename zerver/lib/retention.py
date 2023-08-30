# Core implementation of message retention policies and low-level
# helpers for deleting messages.
#
# Because bugs in code that deletes message content can cause
# irreversible harm in installations without backups, this is a
# particularly sensitive system that requires careful design,
# thoughtful database transaction boundaries, and a well-written test
# suite to make bugs unlikely and mitigate their impact.
#
# The core design principle of this system is we never delete a live
# Message/Reaction/etc. object.  Instead, we use move_rows, which moves
# objects to a "deleted objects" table like ArchiveMessage, recording
# the change using a structure linked to an ArchiveTransaction object
# that can be used to undo that deletion transaction in a clean
# fashion.
#
# We move all of the data associated with a given block of messages in
# a single database transaction in order to avoid broken intermediate
# states where, for example, a message's reactions were deleted but
# not the messages themselves.
#
# And then a separate process deletes ArchiveTransaction objects
# ARCHIVED_DATA_VACUUMING_DELAY_DAYS after they were created.
#
# Because of the nice properties of this deletion system, we use the
# same system for routine deletions via the Zulip UI (deleting a
# message or group of messages) as we use for message retention policy
# deletions.
import logging
import time
from datetime import timedelta
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple, Type, Union

from django.conf import settings
from django.db import connection, transaction
from django.db.models import Model
from django.utils.timezone import now as timezone_now
from psycopg2.sql import SQL, Composable, Identifier, Literal

from zerver.lib.logging_util import log_to_file
from zerver.lib.request import RequestVariableConversionError
from zerver.models import (
    ArchivedAttachment,
    ArchivedReaction,
    ArchivedSubMessage,
    ArchivedUserMessage,
    ArchiveTransaction,
    Attachment,
    Message,
    Reaction,
    Realm,
    Recipient,
    Stream,
    SubMessage,
    UserMessage,
)

logger = logging.getLogger("zulip.retention")
log_to_file(logger, settings.RETENTION_LOG_PATH)

MESSAGE_BATCH_SIZE = 1000
STREAM_MESSAGE_BATCH_SIZE = 100
TRANSACTION_DELETION_BATCH_SIZE = 100

# This data structure declares the details of all database tables that
# hang off the Message table (with a foreign key to Message being part
# of its primary lookup key).  This structure allows us to share the
# code for managing these related tables.
models_with_message_key: List[Dict[str, Any]] = [
    {
        "class": Reaction,
        "archive_class": ArchivedReaction,
        "table_name": "zerver_reaction",
        "archive_table_name": "zerver_archivedreaction",
    },
    {
        "class": SubMessage,
        "archive_class": ArchivedSubMessage,
        "table_name": "zerver_submessage",
        "archive_table_name": "zerver_archivedsubmessage",
    },
    {
        "class": UserMessage,
        "archive_class": ArchivedUserMessage,
        "table_name": "zerver_usermessage",
        "archive_table_name": "zerver_archivedusermessage",
    },
]

EXCLUDE_FIELDS = {Message._meta.get_field("search_tsvector")}


@transaction.atomic(savepoint=False)
def move_rows(
    base_model: Type[Model],
    raw_query: SQL,
    *,
    src_db_table: Optional[str] = None,
    returning_id: bool = False,
    **kwargs: Composable,
) -> List[int]:
    """Core helper for bulk moving rows between a table and its archive table"""
    if src_db_table is None:
        # Use base_model's db_table unless otherwise specified.
        src_db_table = base_model._meta.db_table

    fields = [field for field in base_model._meta.fields if field not in EXCLUDE_FIELDS]
    src_fields = [Identifier(src_db_table, field.column) for field in fields]
    dst_fields = [Identifier(field.column) for field in fields]
    with connection.cursor() as cursor:
        cursor.execute(
            raw_query.format(
                src_fields=SQL(",").join(src_fields), dst_fields=SQL(",").join(dst_fields), **kwargs
            )
        )
        if returning_id:
            return [id for (id,) in cursor.fetchall()]  # return list of row ids
        else:
            return []


def run_archiving_in_chunks(
    query: SQL,
    type: int,
    realm: Optional[Realm] = None,
    chunk_size: int = MESSAGE_BATCH_SIZE,
    **kwargs: Composable,
) -> int:
    # This function is carefully designed to achieve our
    # transactionality goals: A batch of messages is either fully
    # archived-and-deleted or not transactionally.
    #
    # We implement this design by executing queries that archive messages and their related objects
    # (such as UserMessage, Reaction, and Attachment) inside the same transaction.atomic() block.
    assert type in (ArchiveTransaction.MANUAL, ArchiveTransaction.RETENTION_POLICY_BASED)

    message_count = 0
    while True:
        start_time = time.time()
        with transaction.atomic():
            archive_transaction = ArchiveTransaction.objects.create(type=type, realm=realm)
            new_chunk = move_rows(
                Message,
                query,
                src_db_table=None,
                chunk_size=Literal(chunk_size),
                returning_id=True,
                archive_transaction_id=Literal(archive_transaction.id),
                **kwargs,
            )
            if new_chunk:
                move_related_objects_to_archive(new_chunk)
                delete_messages(new_chunk)
                message_count += len(new_chunk)
            else:
                archive_transaction.delete()  # Nothing was archived
        total_time = time.time() - start_time

        # This line needs to be outside of the atomic block, to capture the actual moment
        # archiving of the chunk is finished (since Django does some significant additional work
        # when leaving the block).
        if len(new_chunk) > 0:
            logger.info(
                "Archived %s messages in %.2fs in transaction %s.",
                len(new_chunk),
                total_time,
                archive_transaction.id,
            )

        # We run the loop, until the query returns fewer results than chunk_size,
        # which means we are done:
        if len(new_chunk) < chunk_size:
            break

    return message_count


# Note about batching these Message archiving queries:
# We can simply use LIMIT without worrying about OFFSETs and ordering
# while executing batches, because any Message already archived (in the previous batch)
# will not show up in the "SELECT ... FROM zerver_message ..." query for the next batches.


def move_expired_messages_to_archive_by_recipient(
    recipient: Recipient,
    message_retention_days: int,
    realm: Realm,
    chunk_size: int = MESSAGE_BATCH_SIZE,
) -> int:
    assert message_retention_days != -1

    # Uses index: zerver_message_realm_recipient_date_sent
    query = SQL(
        """
    INSERT INTO zerver_archivedmessage ({dst_fields}, archive_transaction_id)
        SELECT {src_fields}, {archive_transaction_id}
        FROM zerver_message
        WHERE zerver_message.realm_id = {realm_id}
            AND zerver_message.recipient_id = {recipient_id}
            AND zerver_message.date_sent < {check_date}
        LIMIT {chunk_size}
    ON CONFLICT (id) DO UPDATE SET archive_transaction_id = {archive_transaction_id}
    RETURNING id
    """
    )
    check_date = timezone_now() - timedelta(days=message_retention_days)

    return run_archiving_in_chunks(
        query,
        type=ArchiveTransaction.RETENTION_POLICY_BASED,
        realm=realm,
        realm_id=Literal(realm.id),
        recipient_id=Literal(recipient.id),
        check_date=Literal(check_date.isoformat()),
        chunk_size=chunk_size,
    )


def move_expired_personal_and_huddle_messages_to_archive(
    realm: Realm,
    chunk_size: int = MESSAGE_BATCH_SIZE,
) -> int:
    message_retention_days = realm.message_retention_days
    assert message_retention_days != -1
    check_date = timezone_now() - timedelta(days=message_retention_days)

    recipient_types = (Recipient.PERSONAL, Recipient.HUDDLE)

    # Archive expired personal and huddle Messages in the realm, including cross-realm messages.
    # Uses index: zerver_message_realm_recipient_date_sent
    query = SQL(
        """
    INSERT INTO zerver_archivedmessage ({dst_fields}, archive_transaction_id)
        SELECT {src_fields}, {archive_transaction_id}
        FROM zerver_message
        INNER JOIN zerver_recipient ON zerver_recipient.id = zerver_message.recipient_id
        WHERE zerver_message.realm_id = {realm_id}
            AND zerver_recipient.type in {recipient_types}
            AND zerver_message.date_sent < {check_date}
        LIMIT {chunk_size}
    ON CONFLICT (id) DO UPDATE SET archive_transaction_id = {archive_transaction_id}
    RETURNING id
    """
    )

    message_count = run_archiving_in_chunks(
        query,
        type=ArchiveTransaction.RETENTION_POLICY_BASED,
        realm=realm,
        realm_id=Literal(realm.id),
        recipient_types=Literal(recipient_types),
        check_date=Literal(check_date.isoformat()),
        chunk_size=chunk_size,
    )

    return message_count


def move_models_with_message_key_to_archive(msg_ids: List[int]) -> None:
    assert len(msg_ids) > 0

    for model in models_with_message_key:
        query = SQL(
            """
        INSERT INTO {archive_table_name} ({dst_fields})
            SELECT {src_fields}
            FROM {table_name}
            WHERE {table_name}.message_id IN {message_ids}
        ON CONFLICT (id) DO NOTHING
        """
        )
        move_rows(
            model["class"],
            query,
            table_name=Identifier(model["table_name"]),
            archive_table_name=Identifier(model["archive_table_name"]),
            message_ids=Literal(tuple(msg_ids)),
        )


# Attachments can't use the common models_with_message_key system,
# because they can be referenced by more than one Message, and we only
# want to delete the Attachment if we're deleting the last message
# referencing them.
def move_attachments_to_archive(msg_ids: List[int]) -> None:
    assert len(msg_ids) > 0

    query = SQL(
        """
    INSERT INTO zerver_archivedattachment ({dst_fields})
        SELECT {src_fields}
        FROM zerver_attachment
        INNER JOIN zerver_attachment_messages
            ON zerver_attachment_messages.attachment_id = zerver_attachment.id
        WHERE zerver_attachment_messages.message_id IN {message_ids}
        GROUP BY zerver_attachment.id
    ON CONFLICT (id) DO NOTHING
    """
    )
    move_rows(Attachment, query, message_ids=Literal(tuple(msg_ids)))


def move_attachment_messages_to_archive(msg_ids: List[int]) -> None:
    assert len(msg_ids) > 0

    query = SQL(
        """
    INSERT INTO zerver_archivedattachment_messages (id, archivedattachment_id, archivedmessage_id)
        SELECT zerver_attachment_messages.id, zerver_attachment_messages.attachment_id,
            zerver_attachment_messages.message_id
        FROM zerver_attachment_messages
        WHERE  zerver_attachment_messages.message_id IN %(message_ids)s
    ON CONFLICT (id) DO NOTHING
    """
    )
    with connection.cursor() as cursor:
        cursor.execute(query, dict(message_ids=tuple(msg_ids)))


def delete_messages(msg_ids: List[int]) -> None:
    # Important note: This also deletes related objects with a foreign
    # key to Message (due to `on_delete=CASCADE` in our models
    # configuration), so we need to be sure we've taken care of
    # archiving the messages before doing this step.
    #
    # Uses index: zerver_message_pkey
    Message.objects.filter(id__in=msg_ids).delete()


def delete_expired_attachments(realm: Realm) -> None:
    (num_deleted, ignored) = Attachment.objects.filter(
        messages__isnull=True,
        scheduled_messages__isnull=True,
        realm_id=realm.id,
        id__in=ArchivedAttachment.objects.filter(realm_id=realm.id),
    ).delete()

    if num_deleted > 0:
        logger.info("Cleaned up %s attachments for realm %s", num_deleted, realm.string_id)


def move_related_objects_to_archive(msg_ids: List[int]) -> None:
    move_models_with_message_key_to_archive(msg_ids)
    move_attachments_to_archive(msg_ids)
    move_attachment_messages_to_archive(msg_ids)


def archive_messages_by_recipient(
    recipient: Recipient,
    message_retention_days: int,
    realm: Realm,
    chunk_size: int = MESSAGE_BATCH_SIZE,
) -> int:
    return move_expired_messages_to_archive_by_recipient(
        recipient, message_retention_days, realm, chunk_size
    )


def archive_personal_and_huddle_messages(
    realm: Realm, chunk_size: int = MESSAGE_BATCH_SIZE
) -> None:
    logger.info("Archiving personal and huddle messages for realm %s", realm.string_id)
    message_count = move_expired_personal_and_huddle_messages_to_archive(realm, chunk_size)
    logger.info("Done. Archived %s messages", message_count)


def archive_stream_messages(
    realm: Realm, streams: List[Stream], chunk_size: int = STREAM_MESSAGE_BATCH_SIZE
) -> None:
    if not streams:
        return  # nocoverage # TODO

    logger.info("Archiving stream messages for realm %s", realm.string_id)
    retention_policy_dict: Dict[int, int] = {}
    for stream in streams:
        #  if stream.message_retention_days is null, use the realm's policy
        if stream.message_retention_days:
            retention_policy_dict[stream.id] = stream.message_retention_days
        else:
            assert realm.message_retention_days != -1
            retention_policy_dict[stream.id] = realm.message_retention_days

    recipients = [stream.recipient for stream in streams]
    message_count = 0
    for recipient in recipients:
        assert recipient is not None
        message_count += archive_messages_by_recipient(
            recipient,
            retention_policy_dict[recipient.type_id],
            realm,
            chunk_size,
        )

    logger.info("Done. Archived %s messages.", message_count)


def archive_messages(chunk_size: int = MESSAGE_BATCH_SIZE) -> None:
    logger.info("Starting the archiving process with chunk_size %s", chunk_size)

    for realm, streams in get_realms_and_streams_for_archiving():
        archive_stream_messages(realm, streams, chunk_size=STREAM_MESSAGE_BATCH_SIZE)
        if realm.message_retention_days != -1:
            archive_personal_and_huddle_messages(realm, chunk_size)

        # Messages have been archived for the realm, now we can clean up attachments:
        delete_expired_attachments(realm)


def get_realms_and_streams_for_archiving() -> List[Tuple[Realm, List[Stream]]]:
    """
    This function constructs a list of (realm, streams_of_the_realm) tuples
    where each realm is a Realm that requires calling the archiving functions on it,
    and streams_of_the_realm is a list of streams of the realm to call archive_stream_messages with.

    The purpose of this is performance - for servers with thousands of realms, it is important
    to fetch all this data in bulk.
    """

    realm_id_to_realm = {}
    realm_id_to_streams_list: Dict[int, List[Stream]] = {}

    # All realms with a retention policy set qualify for archiving:
    for realm in Realm.objects.exclude(message_retention_days=-1):
        realm_id_to_realm[realm.id] = realm
        realm_id_to_streams_list[realm.id] = []

    # Now we find all streams that require archiving.
    # First category are streams in retention-enabled realms,
    # that don't have retention explicitly disabled (through the value -1).
    query_one = (
        Stream.objects.exclude(message_retention_days=-1)
        .exclude(realm__message_retention_days=-1)
        .select_related("realm", "recipient")
    )
    # Second category are streams that are in realms without a realm-wide retention policy,
    # but have their own stream-specific policy enabled.
    query_two = (
        Stream.objects.filter(realm__message_retention_days=-1)
        .exclude(message_retention_days__isnull=True)
        .exclude(message_retention_days=-1)
        .select_related("realm", "recipient")
    )
    query = query_one.union(query_two)

    for stream in query:
        realm = stream.realm
        realm_id_to_realm[realm.id] = realm
        if realm.id not in realm_id_to_streams_list:
            realm_id_to_streams_list[realm.id] = []

        realm_id_to_streams_list[realm.id].append(stream)

    return [
        (realm_id_to_realm[realm_id], realm_id_to_streams_list[realm_id])
        for realm_id in realm_id_to_realm
    ]


def move_messages_to_archive(
    message_ids: List[int], realm: Optional[Realm] = None, chunk_size: int = MESSAGE_BATCH_SIZE
) -> None:
    # Uses index: zerver_message_pkey
    query = SQL(
        """
    INSERT INTO zerver_archivedmessage ({dst_fields}, archive_transaction_id)
        SELECT {src_fields}, {archive_transaction_id}
        FROM zerver_message
        WHERE zerver_message.id IN {message_ids}
        LIMIT {chunk_size}
    ON CONFLICT (id) DO UPDATE SET archive_transaction_id = {archive_transaction_id}
    RETURNING id
    """
    )
    count = run_archiving_in_chunks(
        query,
        type=ArchiveTransaction.MANUAL,
        message_ids=Literal(tuple(message_ids)),
        realm=realm,
        chunk_size=chunk_size,
    )

    if count == 0:
        raise Message.DoesNotExist
    # Clean up attachments:
    archived_attachments = ArchivedAttachment.objects.filter(
        messages__id__in=message_ids
    ).distinct()
    Attachment.objects.filter(
        messages__isnull=True, scheduled_messages__isnull=True, id__in=archived_attachments
    ).delete()


def restore_messages_from_archive(archive_transaction_id: int) -> List[int]:
    query = SQL(
        """
        INSERT INTO zerver_message ({dst_fields})
            SELECT {src_fields}
            FROM zerver_archivedmessage
            WHERE zerver_archivedmessage.archive_transaction_id = {archive_transaction_id}
        ON CONFLICT (id) DO NOTHING
        RETURNING id
        """
    )
    return move_rows(
        Message,
        query,
        src_db_table="zerver_archivedmessage",
        returning_id=True,
        archive_transaction_id=Literal(archive_transaction_id),
    )


def restore_models_with_message_key_from_archive(archive_transaction_id: int) -> None:
    for model in models_with_message_key:
        query = SQL(
            """
        INSERT INTO {table_name} ({dst_fields})
            SELECT {src_fields}
            FROM {archive_table_name}
            INNER JOIN zerver_archivedmessage ON {archive_table_name}.message_id = zerver_archivedmessage.id
            WHERE zerver_archivedmessage.archive_transaction_id = {archive_transaction_id}
        ON CONFLICT (id) DO NOTHING
        """
        )

        move_rows(
            model["class"],
            query,
            src_db_table=model["archive_table_name"],
            table_name=Identifier(model["table_name"]),
            archive_transaction_id=Literal(archive_transaction_id),
            archive_table_name=Identifier(model["archive_table_name"]),
        )


def restore_attachments_from_archive(archive_transaction_id: int) -> None:
    query = SQL(
        """
    INSERT INTO zerver_attachment ({dst_fields})
        SELECT {src_fields}
        FROM zerver_archivedattachment
        INNER JOIN zerver_archivedattachment_messages
            ON zerver_archivedattachment_messages.archivedattachment_id = zerver_archivedattachment.id
        INNER JOIN zerver_archivedmessage
            ON  zerver_archivedattachment_messages.archivedmessage_id = zerver_archivedmessage.id
        WHERE zerver_archivedmessage.archive_transaction_id = {archive_transaction_id}
        GROUP BY zerver_archivedattachment.id
    ON CONFLICT (id) DO NOTHING
    """
    )
    move_rows(
        Attachment,
        query,
        src_db_table="zerver_archivedattachment",
        archive_transaction_id=Literal(archive_transaction_id),
    )


def restore_attachment_messages_from_archive(archive_transaction_id: int) -> None:
    query = SQL(
        """
    INSERT INTO zerver_attachment_messages (id, attachment_id, message_id)
        SELECT zerver_archivedattachment_messages.id,
            zerver_archivedattachment_messages.archivedattachment_id,
            zerver_archivedattachment_messages.archivedmessage_id
        FROM zerver_archivedattachment_messages
        INNER JOIN zerver_archivedmessage
            ON  zerver_archivedattachment_messages.archivedmessage_id = zerver_archivedmessage.id
        WHERE zerver_archivedmessage.archive_transaction_id = %(archive_transaction_id)s
    ON CONFLICT (id) DO NOTHING
    """
    )
    with connection.cursor() as cursor:
        cursor.execute(query, dict(archive_transaction_id=archive_transaction_id))


def restore_data_from_archive(archive_transaction: ArchiveTransaction) -> int:
    logger.info("Restoring %s", archive_transaction)
    # transaction.atomic needs to be used here, rather than being a wrapper on the whole function,
    # so that when we log "Finished", the process has indeed finished - and that happens only after
    # leaving the atomic block - Django does work committing the changes to the database when
    # the block ends.
    with transaction.atomic():
        msg_ids = restore_messages_from_archive(archive_transaction.id)
        restore_models_with_message_key_from_archive(archive_transaction.id)
        restore_attachments_from_archive(archive_transaction.id)
        restore_attachment_messages_from_archive(archive_transaction.id)

        archive_transaction.restored = True
        archive_transaction.save()

    logger.info("Finished. Restored %s messages", len(msg_ids))
    return len(msg_ids)


def restore_data_from_archive_by_transactions(
    archive_transactions: Iterable[ArchiveTransaction],
) -> int:
    # Looping over the list of ids means we're batching the restoration process by the size of the
    # transactions:
    message_count = 0
    for archive_transaction in archive_transactions:
        message_count += restore_data_from_archive(archive_transaction)

    return message_count


def restore_data_from_archive_by_realm(realm: Realm) -> None:
    transactions = ArchiveTransaction.objects.exclude(restored=True).filter(
        realm=realm, type=ArchiveTransaction.RETENTION_POLICY_BASED
    )
    logger.info("Restoring %s transactions from realm %s", len(transactions), realm.string_id)
    message_count = restore_data_from_archive_by_transactions(transactions)

    logger.info("Finished. Restored %s messages from realm %s", message_count, realm.string_id)


def restore_all_data_from_archive(restore_manual_transactions: bool = True) -> None:
    for realm in Realm.objects.all():
        restore_data_from_archive_by_realm(realm)

    if restore_manual_transactions:
        restore_data_from_archive_by_transactions(
            ArchiveTransaction.objects.exclude(restored=True).filter(
                type=ArchiveTransaction.MANUAL
            ),
        )


def restore_retention_policy_deletions_for_stream(stream: Stream) -> None:
    """
    Utility function for calling in the Django shell if a stream's policy was
    set to something too aggressive and the administrator wants to restore
    the messages deleted as a result.
    """
    relevant_transactions = ArchiveTransaction.objects.filter(
        archivedmessage__recipient=stream.recipient, type=ArchiveTransaction.RETENTION_POLICY_BASED
    ).distinct("id")

    restore_data_from_archive_by_transactions(list(relevant_transactions))


def clean_archived_data() -> None:
    """This function deletes archived data that was archived at least
    settings.ARCHIVED_DATA_VACUUMING_DELAY_DAYS days ago.

    It works by deleting ArchiveTransaction objects that are
    sufficiently old. We've configured most archive tables, like
    ArchiveMessage, with on_delete=CASCADE, so that deleting an
    ArchiveTransaction entails deleting associated objects, including
    ArchivedMessage, ArchivedUserMessage, ArchivedReaction.

    The exception to this rule is ArchivedAttachment. Archive
    attachment objects that were only referenced by ArchivedMessage
    objects that have now been deleted will be left with an empty
    `.messages` relation. A separate step,
    delete_old_unclaimed_attachments, will delete those
    ArchivedAttachment objects (and delete the files themselves from
    the storage).
    """
    logger.info("Cleaning old archive data.")
    check_date = timezone_now() - timedelta(days=settings.ARCHIVED_DATA_VACUUMING_DELAY_DAYS)
    # Associated archived objects will get deleted through the on_delete=CASCADE property:
    count = 0
    transaction_ids = list(
        ArchiveTransaction.objects.filter(timestamp__lt=check_date).values_list("id", flat=True)
    )
    while len(transaction_ids) > 0:
        transaction_block = transaction_ids[0:TRANSACTION_DELETION_BATCH_SIZE]
        transaction_ids = transaction_ids[TRANSACTION_DELETION_BATCH_SIZE:]
        ArchiveTransaction.objects.filter(id__in=transaction_block).delete()
        count += len(transaction_block)

    logger.info("Deleted %s old ArchiveTransactions.", count)


def parse_message_retention_days(
    value: Union[int, str],
    special_values_map: Mapping[str, Optional[int]],
) -> Optional[int]:
    if isinstance(value, str) and value in special_values_map:
        return special_values_map[value]
    if isinstance(value, str) or value <= 0:
        raise RequestVariableConversionError("message_retention_days", value)
    assert isinstance(value, int)
    return value
