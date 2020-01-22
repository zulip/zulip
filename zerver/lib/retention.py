from datetime import timedelta

from django.conf import settings
from django.db import connection, transaction
from django.db.models import Model
from django.utils.timezone import now as timezone_now

from zerver.lib.logging_util import log_to_file
from zerver.models import (Message, UserMessage, ArchivedUserMessage, Realm,
                           Attachment, ArchivedAttachment, Reaction, ArchivedReaction,
                           SubMessage, ArchivedSubMessage, Recipient, Stream, ArchiveTransaction,
                           get_user_including_cross_realm)

from typing import Any, Dict, List, Optional

import logging

logger = logging.getLogger('zulip.retention')
log_to_file(logger, settings.RETENTION_LOG_PATH)

MESSAGE_BATCH_SIZE = 1000

models_with_message_key = [
    {
        'class': Reaction,
        'archive_class': ArchivedReaction,
        'table_name': 'zerver_reaction',
        'archive_table_name': 'zerver_archivedreaction'
    },
    {
        'class': SubMessage,
        'archive_class': ArchivedSubMessage,
        'table_name': 'zerver_submessage',
        'archive_table_name': 'zerver_archivedsubmessage'
    },
    {
        'class': UserMessage,
        'archive_class': ArchivedUserMessage,
        'table_name': 'zerver_usermessage',
        'archive_table_name': 'zerver_archivedusermessage'
    },
]  # type: List[Dict[str, Any]]

@transaction.atomic(savepoint=False)
def move_rows(base_model: Model, raw_query: str, src_db_table: str='', returning_id: bool=False,
              **kwargs: Any) -> List[int]:
    if not src_db_table:
        # Use base_model's db_table unless otherwise specified.
        src_db_table = base_model._meta.db_table

    src_fields = ["{}.{}".format(src_db_table, field.column) for field in base_model._meta.fields]
    dst_fields = [field.column for field in base_model._meta.fields]
    sql_args = {
        'src_fields': ','.join(src_fields),
        'dst_fields': ','.join(dst_fields),
    }
    sql_args.update(kwargs)
    with connection.cursor() as cursor:
        cursor.execute(
            raw_query.format(**sql_args)
        )
        if returning_id:
            return [row[0] for row in cursor.fetchall()]  # return list of row ids
        else:
            return []

def ids_list_to_sql_query_format(ids: List[int]) -> str:
    assert len(ids) > 0

    ids_tuple = tuple(ids)
    if len(ids_tuple) > 1:
        ids_string = str(ids_tuple)
    elif len(ids_tuple) == 1:
        ids_string = '({})'.format(ids_tuple[0])

    return ids_string

def run_archiving_in_chunks(query: str, type: int, realm: Optional[Realm]=None,
                            chunk_size: int=MESSAGE_BATCH_SIZE, **kwargs: Any) -> int:
    # This function is carefully designed to achieve our
    # transactionality goals: A batch of messages is either fully
    # archived-and-deleted or not transactionally.
    #
    # We implement this design by executing queries that archive messages and their related objects
    # (such as UserMessage, Reaction, and Attachment) inside the same transaction.atomic() block.
    assert type in (ArchiveTransaction.MANUAL, ArchiveTransaction.RETENTION_POLICY_BASED)

    message_count = 0
    while True:
        with transaction.atomic():
            archive_transaction = ArchiveTransaction.objects.create(type=type, realm=realm)
            logger.info("Archiving in {}".format(archive_transaction))
            new_chunk = move_rows(Message, query, chunk_size=chunk_size, returning_id=True,
                                  archive_transaction_id=archive_transaction.id, **kwargs)
            if new_chunk:
                move_related_objects_to_archive(new_chunk)
                delete_messages(new_chunk)
                message_count += len(new_chunk)
            else:
                archive_transaction.delete()  # Nothing was archived

        # This line needs to be outside of the atomic block, to capture the actual moment
        # archiving of the chunk is finished (since Django does some significant additional work
        # when leaving the block).
        logger.info("Finished. Archived {} messages in this transaction.".format(len(new_chunk)))

        # We run the loop, until the query returns fewer results than chunk_size,
        # which means we are done:
        if len(new_chunk) < chunk_size:
            break

    return message_count

# Note about batching these Message archiving queries:
# We can simply use LIMIT without worrying about OFFSETs and ordering
# while executing batches, because any Message already archived (in the previous batch)
# will not show up in the "SELECT ... FROM zerver_message ..." query for the next batches.

def move_expired_messages_to_archive_by_recipient(recipient: Recipient,
                                                  message_retention_days: int, realm: Realm,
                                                  chunk_size: int=MESSAGE_BATCH_SIZE) -> int:
    # This function will archive appropriate messages and their related objects.
    query = """
    INSERT INTO zerver_archivedmessage ({dst_fields}, archive_transaction_id)
        SELECT {src_fields}, {archive_transaction_id}
        FROM zerver_message
        WHERE zerver_message.recipient_id = {recipient_id}
            AND zerver_message.date_sent < '{check_date}'
        LIMIT {chunk_size}
    ON CONFLICT (id) DO UPDATE SET archive_transaction_id = {archive_transaction_id}
    RETURNING id
    """
    check_date = timezone_now() - timedelta(days=message_retention_days)

    return run_archiving_in_chunks(query, type=ArchiveTransaction.RETENTION_POLICY_BASED, realm=realm,
                                   recipient_id=recipient.id, check_date=check_date.isoformat(),
                                   chunk_size=chunk_size)

def move_expired_personal_and_huddle_messages_to_archive(realm: Realm,
                                                         chunk_size: int=MESSAGE_BATCH_SIZE
                                                         ) -> int:
    # This function will archive appropriate messages and their related objects.
    cross_realm_bot_ids_list = [get_user_including_cross_realm(email).id
                                for email in settings.CROSS_REALM_BOT_EMAILS]
    cross_realm_bot_ids = str(tuple(cross_realm_bot_ids_list))
    recipient_types = (Recipient.PERSONAL, Recipient.HUDDLE)

    # Archive expired personal and huddle Messages in the realm, except cross-realm messages:
    # TODO: Remove the "zerver_userprofile.id NOT IN {cross_realm_bot_ids}" clause
    # once https://github.com/zulip/zulip/issues/11015 is solved.
    query = """
    INSERT INTO zerver_archivedmessage ({dst_fields}, archive_transaction_id)
        SELECT {src_fields}, {archive_transaction_id}
        FROM zerver_message
        INNER JOIN zerver_recipient ON zerver_recipient.id = zerver_message.recipient_id
        INNER JOIN zerver_userprofile ON zerver_userprofile.id = zerver_message.sender_id
        WHERE zerver_userprofile.id NOT IN {cross_realm_bot_ids}
            AND zerver_userprofile.realm_id = {realm_id}
            AND zerver_recipient.type in {recipient_types}
            AND zerver_message.date_sent < '{check_date}'
        LIMIT {chunk_size}
    ON CONFLICT (id) DO UPDATE SET archive_transaction_id = {archive_transaction_id}
    RETURNING id
    """
    assert realm.message_retention_days is not None
    check_date = timezone_now() - timedelta(days=realm.message_retention_days)

    message_count = run_archiving_in_chunks(query, type=ArchiveTransaction.RETENTION_POLICY_BASED,
                                            realm=realm,
                                            cross_realm_bot_ids=cross_realm_bot_ids,
                                            realm_id=realm.id, recipient_types=recipient_types,
                                            check_date=check_date.isoformat(), chunk_size=chunk_size)

    # Archive cross-realm personal messages to users in the realm:
    # Note: Cross-realm huddle message aren't handled yet, they remain an issue
    # that should be addressed.
    query = """
    INSERT INTO zerver_archivedmessage ({dst_fields}, archive_transaction_id)
        SELECT {src_fields}, {archive_transaction_id}
        FROM zerver_message
        INNER JOIN zerver_recipient ON zerver_recipient.id = zerver_message.recipient_id
        INNER JOIN zerver_userprofile recipient_profile ON recipient_profile.id = zerver_recipient.type_id
        INNER JOIN zerver_userprofile sender_profile ON sender_profile.id = zerver_message.sender_id
        WHERE sender_profile.id IN {cross_realm_bot_ids}
            AND recipient_profile.realm_id = {realm_id}
            AND zerver_recipient.type = {recipient_personal}
            AND zerver_message.date_sent < '{check_date}'
        LIMIT {chunk_size}
    ON CONFLICT (id) DO UPDATE SET archive_transaction_id = {archive_transaction_id}
    RETURNING id
    """
    message_count += run_archiving_in_chunks(query, type=ArchiveTransaction.RETENTION_POLICY_BASED,
                                             realm=realm,
                                             cross_realm_bot_ids=cross_realm_bot_ids,
                                             realm_id=realm.id, recipient_personal=Recipient.PERSONAL,
                                             check_date=check_date.isoformat(), chunk_size=chunk_size)

    return message_count

def move_models_with_message_key_to_archive(msg_ids: List[int]) -> None:
    assert len(msg_ids) > 0

    for model in models_with_message_key:
        query = """
        INSERT INTO {archive_table_name} ({dst_fields})
            SELECT {src_fields}
            FROM {table_name}
            WHERE {table_name}.message_id IN {message_ids}
        ON CONFLICT (id) DO NOTHING
        """
        move_rows(model['class'], query, table_name=model['table_name'],
                  archive_table_name=model['archive_table_name'],
                  message_ids=ids_list_to_sql_query_format(msg_ids))

def move_attachments_to_archive(msg_ids: List[int]) -> None:
    assert len(msg_ids) > 0

    query = """
    INSERT INTO zerver_archivedattachment ({dst_fields})
        SELECT {src_fields}
        FROM zerver_attachment
        INNER JOIN zerver_attachment_messages
            ON zerver_attachment_messages.attachment_id = zerver_attachment.id
        WHERE zerver_attachment_messages.message_id IN {message_ids}
        GROUP BY zerver_attachment.id
    ON CONFLICT (id) DO NOTHING
    """
    move_rows(Attachment, query, message_ids=ids_list_to_sql_query_format(msg_ids))


def move_attachment_messages_to_archive(msg_ids: List[int]) -> None:
    assert len(msg_ids) > 0

    query = """
    INSERT INTO zerver_archivedattachment_messages (id, archivedattachment_id, archivedmessage_id)
        SELECT zerver_attachment_messages.id, zerver_attachment_messages.attachment_id,
            zerver_attachment_messages.message_id
        FROM zerver_attachment_messages
        WHERE  zerver_attachment_messages.message_id IN {message_ids}
    ON CONFLICT (id) DO NOTHING
    """
    with connection.cursor() as cursor:
        cursor.execute(query.format(message_ids=ids_list_to_sql_query_format(msg_ids)))

def delete_messages(msg_ids: List[int]) -> None:
    # Important note: This also deletes related objects with a foreign
    # key to Message (due to `on_delete=CASCADE` in our models
    # configuration), so we need to be sure we've taken care of
    # archiving the messages before doing this step.
    Message.objects.filter(id__in=msg_ids).delete()

def delete_expired_attachments(realm: Realm) -> None:
    logger.info("Cleaning up attachments for realm " + realm.string_id)
    Attachment.objects.filter(
        messages__isnull=True,
        realm_id=realm.id,
        id__in=ArchivedAttachment.objects.filter(realm_id=realm.id),
    ).delete()

def move_related_objects_to_archive(msg_ids: List[int]) -> None:
    move_models_with_message_key_to_archive(msg_ids)
    move_attachments_to_archive(msg_ids)
    move_attachment_messages_to_archive(msg_ids)

def archive_messages_by_recipient(recipient: Recipient, message_retention_days: int,
                                  realm: Realm, chunk_size: int=MESSAGE_BATCH_SIZE) -> int:
    return move_expired_messages_to_archive_by_recipient(recipient, message_retention_days,
                                                         realm, chunk_size)

def archive_personal_and_huddle_messages(realm: Realm, chunk_size: int=MESSAGE_BATCH_SIZE) -> None:
    logger.info("Archiving personal and huddle messages for realm " + realm.string_id)
    message_count = move_expired_personal_and_huddle_messages_to_archive(realm, chunk_size)
    logger.info("Done. Archived {} messages".format(message_count))

def archive_stream_messages(realm: Realm, chunk_size: int=MESSAGE_BATCH_SIZE) -> None:
    logger.info("Archiving stream messages for realm " + realm.string_id)
    # We don't archive, if the stream has message_retention_days set to -1,
    # or if neither the stream nor the realm have a retention policy.
    streams = Stream.objects.select_related("recipient").filter(
        realm_id=realm.id).exclude(message_retention_days=-1)
    if not realm.message_retention_days:
        streams = streams.exclude(message_retention_days__isnull=True)

    retention_policy_dict = {}  # type: Dict[int, int]
    for stream in streams:
        #  if stream.message_retention_days is null, use the realm's policy
        if stream.message_retention_days:
            retention_policy_dict[stream.id] = stream.message_retention_days
        else:
            assert realm.message_retention_days is not None
            retention_policy_dict[stream.id] = realm.message_retention_days

    recipients = [stream.recipient for stream in streams]
    message_count = 0
    for recipient in recipients:
        message_count += archive_messages_by_recipient(
            recipient, retention_policy_dict[recipient.type_id], realm, chunk_size
        )

    logger.info("Done. Archived {} messages.".format(message_count))

def archive_messages(chunk_size: int=MESSAGE_BATCH_SIZE) -> None:
    logger.info("Starting the archiving process with chunk_size {}".format(chunk_size))

    for realm in Realm.objects.all():
        archive_stream_messages(realm, chunk_size)
        if realm.message_retention_days:
            archive_personal_and_huddle_messages(realm, chunk_size)

        # Messages have been archived for the realm, now we can clean up attachments:
        delete_expired_attachments(realm)

def move_messages_to_archive(message_ids: List[int], chunk_size: int=MESSAGE_BATCH_SIZE) -> None:
    query = """
    INSERT INTO zerver_archivedmessage ({dst_fields}, archive_transaction_id)
        SELECT {src_fields}, {archive_transaction_id}
        FROM zerver_message
        WHERE zerver_message.id IN {message_ids}
        LIMIT {chunk_size}
    ON CONFLICT (id) DO UPDATE SET archive_transaction_id = {archive_transaction_id}
    RETURNING id
    """
    count = run_archiving_in_chunks(query, type=ArchiveTransaction.MANUAL,
                                    message_ids=ids_list_to_sql_query_format(message_ids),
                                    chunk_size=chunk_size)

    if count == 0:
        raise Message.DoesNotExist
    # Clean up attachments:
    archived_attachments = ArchivedAttachment.objects.filter(messages__id__in=message_ids).distinct()
    Attachment.objects.filter(messages__isnull=True, id__in=archived_attachments).delete()

def restore_messages_from_archive(archive_transaction_id: int) -> List[int]:
    query = """
        INSERT INTO zerver_message ({dst_fields})
            SELECT {src_fields}
            FROM zerver_archivedmessage
            WHERE zerver_archivedmessage.archive_transaction_id = {archive_transaction_id}
        ON CONFLICT (id) DO NOTHING
        RETURNING id
        """
    return move_rows(Message, query, src_db_table='zerver_archivedmessage', returning_id=True,
                     archive_transaction_id=archive_transaction_id)

def restore_models_with_message_key_from_archive(archive_transaction_id: int) -> None:
    for model in models_with_message_key:
        query = """
        INSERT INTO {table_name} ({dst_fields})
            SELECT {src_fields}
            FROM {archive_table_name}
            INNER JOIN zerver_archivedmessage ON {archive_table_name}.message_id = zerver_archivedmessage.id
            WHERE zerver_archivedmessage.archive_transaction_id = {archive_transaction_id}
        ON CONFLICT (id) DO NOTHING
        """

        move_rows(model['class'], query, src_db_table=model['archive_table_name'],
                  table_name=model['table_name'],
                  archive_transaction_id=archive_transaction_id,
                  archive_table_name=model['archive_table_name'])

def restore_attachments_from_archive(archive_transaction_id: int) -> None:
    query = """
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
    move_rows(Attachment, query, src_db_table='zerver_archivedattachment',
              archive_transaction_id=archive_transaction_id)

def restore_attachment_messages_from_archive(archive_transaction_id: int) -> None:
    query = """
    INSERT INTO zerver_attachment_messages (id, attachment_id, message_id)
        SELECT zerver_archivedattachment_messages.id,
            zerver_archivedattachment_messages.archivedattachment_id,
            zerver_archivedattachment_messages.archivedmessage_id
        FROM zerver_archivedattachment_messages
        INNER JOIN zerver_archivedmessage
            ON  zerver_archivedattachment_messages.archivedmessage_id = zerver_archivedmessage.id
        WHERE zerver_archivedmessage.archive_transaction_id = {archive_transaction_id}
    ON CONFLICT (id) DO NOTHING
    """
    with connection.cursor() as cursor:
        cursor.execute(query.format(archive_transaction_id=archive_transaction_id))

def restore_data_from_archive(archive_transaction: ArchiveTransaction) -> int:
    logger.info("Restoring {}".format(archive_transaction))
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

    logger.info("Finished. Restored {} messages".format(len(msg_ids)))
    return len(msg_ids)

def restore_data_from_archive_by_transactions(archive_transactions: List[ArchiveTransaction]) -> int:
    # Looping over the list of ids means we're batching the restoration process by the size of the
    # transactions:
    message_count = 0
    for archive_transaction in archive_transactions:
        message_count += restore_data_from_archive(archive_transaction)

    return message_count

def restore_data_from_archive_by_realm(realm: Realm) -> None:
    transactions = ArchiveTransaction.objects.exclude(restored=True).filter(
        realm=realm, type=ArchiveTransaction.RETENTION_POLICY_BASED)
    logger.info("Restoring {} transactions from realm {}".format(len(transactions), realm.string_id))
    message_count = restore_data_from_archive_by_transactions(transactions)

    logger.info("Finished. Restored {} messages from realm {}".format(message_count, realm.string_id))

def restore_all_data_from_archive(restore_manual_transactions: bool=True) -> None:
    for realm in Realm.objects.all():
        restore_data_from_archive_by_realm(realm)

    if restore_manual_transactions:
        restore_data_from_archive_by_transactions(
            ArchiveTransaction.objects.exclude(restored=True).filter(type=ArchiveTransaction.MANUAL)
        )

def clean_archived_data() -> None:
    logger.info("Cleaning old archive data.")
    check_date = timezone_now() - timedelta(days=settings.ARCHIVED_DATA_VACUUMING_DELAY_DAYS)
    #  Appropriate archived objects will get deleted through the on_delete=CASCADE property:
    transactions = ArchiveTransaction.objects.filter(timestamp__lt=check_date)
    count = transactions.count()
    transactions.delete()

    logger.info("Deleted {} old ArchiveTransactions.".format(count))
