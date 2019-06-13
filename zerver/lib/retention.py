
from datetime import timedelta

from django.conf import settings
from django.db import connection, transaction
from django.db.models import Q
from django.utils.timezone import now as timezone_now

from zerver.lib.logging_util import log_to_file
from zerver.models import (Message, UserMessage, ArchivedMessage, ArchivedUserMessage, Realm,
                           Attachment, ArchivedAttachment, Reaction, ArchivedReaction,
                           SubMessage, ArchivedSubMessage, Recipient, Stream,
                           get_stream_recipients, get_user_including_cross_realm)

from typing import Any, Dict, Iterator, List

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

@transaction.atomic
def move_rows(src_model: Any, raw_query: str, returning_id: bool=False,
              **kwargs: Any) -> List[int]:
    src_db_table = src_model._meta.db_table
    src_fields = ["{}.{}".format(src_db_table, field.column) for field in src_model._meta.fields]
    dst_fields = [field.column for field in src_model._meta.fields]
    sql_args = {
        'src_fields': ','.join(src_fields),
        'dst_fields': ','.join(dst_fields),
        'archive_timestamp': timezone_now()
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

def run_message_batch_query(query: str, chunk_size: int=MESSAGE_BATCH_SIZE,
                            **kwargs: Any) -> Iterator[List[int]]:
    while True:
        new_chunk = move_rows(Message, query, chunk_size=chunk_size, **kwargs)
        if new_chunk:
            yield new_chunk

        # We run the loop, until the query returns fewer results than chunk_size, which means we are done:
        if len(new_chunk) < chunk_size:
            break

# Note about batching these Message archiving queries:
# We can simply use LIMIT without worrying about OFFSETs and ordering
# while executing batches, because any Message already archived (in the previous batch)
# will not show up in the "SELECT ... FROM zerver_message ..." query for the next batches.

def move_expired_messages_to_archive_by_recipient(recipient: Recipient,
                                                  message_retention_days: int,
                                                  chunk_size: int=MESSAGE_BATCH_SIZE) -> Iterator[List[int]]:
    # Important: This function is a generator, and you need to iterate
    # through the Iterator it returns to execute the queries.
    query = """
    INSERT INTO zerver_archivedmessage ({dst_fields}, archive_timestamp)
        SELECT {src_fields}, '{archive_timestamp}'
        FROM zerver_message
        LEFT JOIN zerver_archivedmessage ON zerver_archivedmessage.id = zerver_message.id
        WHERE zerver_message.recipient_id = {recipient_id}
            AND zerver_message.pub_date < '{check_date}'
            AND zerver_archivedmessage.id is NULL
        LIMIT {chunk_size}
    RETURNING id
    """
    check_date = timezone_now() - timedelta(days=message_retention_days)

    yield from run_message_batch_query(query, returning_id=True,
                                       recipient_id=recipient.id, check_date=check_date.isoformat(),
                                       chunk_size=chunk_size)

def move_expired_personal_and_huddle_messages_to_archive(realm: Realm,
                                                         chunk_size: int=MESSAGE_BATCH_SIZE
                                                         ) -> Iterator[List[int]]:
    # Important: This function is a generator, and you need to iterate
    # through the Iterator it returns to execute the queries.
    cross_realm_bot_ids_list = [get_user_including_cross_realm(email).id
                                for email in settings.CROSS_REALM_BOT_EMAILS]
    cross_realm_bot_ids = str(tuple(cross_realm_bot_ids_list))
    recipient_types = (Recipient.PERSONAL, Recipient.HUDDLE)

    # Archive expired personal and huddle Messages in the realm, except cross-realm messages:
    # TODO: Remove the "zerver_userprofile.id NOT IN {cross_realm_bot_ids}" clause
    # once https://github.com/zulip/zulip/issues/11015 is solved.
    query = """
    INSERT INTO zerver_archivedmessage ({dst_fields}, archive_timestamp)
        SELECT {src_fields}, '{archive_timestamp}'
        FROM zerver_message
        INNER JOIN zerver_recipient ON zerver_recipient.id = zerver_message.recipient_id
        INNER JOIN zerver_userprofile ON zerver_userprofile.id = zerver_message.sender_id
        LEFT JOIN zerver_archivedmessage ON zerver_archivedmessage.id = zerver_message.id
        WHERE zerver_userprofile.id NOT IN {cross_realm_bot_ids}
            AND zerver_userprofile.realm_id = {realm_id}
            AND zerver_recipient.type in {recipient_types}
            AND zerver_message.pub_date < '{check_date}'
            AND zerver_archivedmessage.id is NULL
        LIMIT {chunk_size}
    RETURNING id
    """
    assert realm.message_retention_days is not None
    check_date = timezone_now() - timedelta(days=realm.message_retention_days)

    yield from run_message_batch_query(query, returning_id=True, cross_realm_bot_ids=cross_realm_bot_ids,
                                       realm_id=realm.id, recipient_types=recipient_types,
                                       check_date=check_date.isoformat(), chunk_size=chunk_size)

def move_models_with_message_key_to_archive(msg_ids: List[int]) -> None:
    assert len(msg_ids) > 0

    for model in models_with_message_key:
        query = """
        INSERT INTO {archive_table_name} ({dst_fields}, archive_timestamp)
        SELECT {src_fields}, '{archive_timestamp}'
        FROM {table_name}
        LEFT JOIN {archive_table_name} ON {archive_table_name}.id = {table_name}.id
        WHERE {table_name}.message_id IN {message_ids}
            AND {archive_table_name}.id IS NULL
        """
        move_rows(model['class'], query, table_name=model['table_name'],
                  archive_table_name=model['archive_table_name'],
                  message_ids=ids_list_to_sql_query_format(msg_ids))

def move_attachments_to_archive(msg_ids: List[int]) -> None:
    assert len(msg_ids) > 0

    query = """
       INSERT INTO zerver_archivedattachment ({dst_fields}, archive_timestamp)
       SELECT {src_fields}, '{archive_timestamp}'
       FROM zerver_attachment
       INNER JOIN zerver_attachment_messages
           ON zerver_attachment_messages.attachment_id = zerver_attachment.id
       LEFT JOIN zerver_archivedattachment ON zerver_archivedattachment.id = zerver_attachment.id
       WHERE zerver_attachment_messages.message_id IN {message_ids}
            AND zerver_archivedattachment.id IS NULL
       GROUP BY zerver_attachment.id
    """
    move_rows(Attachment, query, message_ids=ids_list_to_sql_query_format(msg_ids))


def move_attachment_messages_to_archive(msg_ids: List[int]) -> None:
    assert len(msg_ids) > 0

    query = """
       INSERT INTO zerver_archivedattachment_messages (id, archivedattachment_id, archivedmessage_id)
       SELECT zerver_attachment_messages.id, zerver_attachment_messages.attachment_id,
           zerver_attachment_messages.message_id
       FROM zerver_attachment_messages
       LEFT JOIN zerver_archivedattachment_messages
           ON zerver_archivedattachment_messages.id = zerver_attachment_messages.id
       WHERE  zerver_attachment_messages.message_id IN {message_ids}
            AND  zerver_archivedattachment_messages.id IS NULL
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
                                  chunk_size: int=MESSAGE_BATCH_SIZE) -> int:
    message_id_chunks = move_expired_messages_to_archive_by_recipient(recipient, message_retention_days,
                                                                      chunk_size)
    message_count = 0
    for chunk in message_id_chunks:
        move_related_objects_to_archive(chunk)
        delete_messages(chunk)
        message_count += len(chunk)

    return message_count

def archive_personal_and_huddle_messages(realm: Realm, chunk_size: int=MESSAGE_BATCH_SIZE) -> None:
    logger.info("Archiving personal and huddle messages for realm " + realm.string_id)

    message_id_chunks = move_expired_personal_and_huddle_messages_to_archive(realm, chunk_size)
    message_count = 0
    for chunk in message_id_chunks:
        move_related_objects_to_archive(chunk)
        delete_messages(chunk)
        message_count += len(chunk)

    logger.info("Done. Archived {} messages".format(message_count))

def archive_stream_messages(realm: Realm, chunk_size: int=MESSAGE_BATCH_SIZE) -> None:
    logger.info("Archiving stream messages for realm " + realm.string_id)
    # We don't archive, if the stream has message_retention_days set to -1,
    # or if neither the stream nor the realm have a retention policy.
    streams = Stream.objects.exclude(message_retention_days=-1).filter(
        Q(message_retention_days__isnull=False) | Q(realm__message_retention_days__isnull=False),
        realm_id=realm.id
    )
    retention_policy_dict = {}  # type: Dict[int, int]
    for stream in streams:
        #  if stream.message_retention_days is null, use the realm's policy
        if stream.message_retention_days:
            retention_policy_dict[stream.id] = stream.message_retention_days
        else:
            retention_policy_dict[stream.id] = stream.realm.message_retention_days

    recipients = get_stream_recipients([stream.id for stream in streams])
    message_count = 0
    for recipient in recipients:
        message_count += archive_messages_by_recipient(
            recipient, retention_policy_dict[recipient.type_id], chunk_size
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

@transaction.atomic
def move_messages_to_archive(message_ids: List[int]) -> None:
    messages = list(Message.objects.filter(id__in=message_ids).values())
    if not messages:
        raise Message.DoesNotExist

    ArchivedMessage.objects.bulk_create([ArchivedMessage(**message) for message in messages])

    move_related_objects_to_archive(message_ids)
    # Remove data from main tables
    delete_messages(message_ids)

    archived_attachments = ArchivedAttachment.objects.filter(messages__id__in=message_ids).distinct()
    Attachment.objects.filter(messages__isnull=True, id__in=archived_attachments).delete()
