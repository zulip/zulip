
from datetime import timedelta

from django.conf import settings
from django.db import connection, transaction
from django.db.models import Q
from django.utils.timezone import now as timezone_now
from zerver.models import (Message, UserMessage, ArchivedMessage, ArchivedUserMessage, Realm,
                           Attachment, ArchivedAttachment, Reaction, ArchivedReaction,
                           SubMessage, ArchivedSubMessage, Recipient, Stream,
                           get_stream_recipients, get_user_including_cross_realm)

from typing import Any, Dict, List

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

def move_expired_messages_to_archive_by_recipient(recipient: Recipient,
                                                  message_retention_days: int) -> List[int]:
    query = """
    INSERT INTO zerver_archivedmessage ({dst_fields}, archive_timestamp)
    SELECT {src_fields}, '{archive_timestamp}'
    FROM zerver_message
    LEFT JOIN zerver_archivedmessage ON zerver_archivedmessage.id = zerver_message.id
    WHERE zerver_message.recipient_id = {recipient_id}
        AND zerver_message.pub_date < '{check_date}'
        AND zerver_archivedmessage.id is NULL
    RETURNING id
    """
    check_date = timezone_now() - timedelta(days=message_retention_days)

    return move_rows(Message, query, returning_id=True,
                     recipient_id=recipient.id, check_date=check_date.isoformat())

def move_expired_personal_and_huddle_messages_to_archive(realm: Realm) -> List[int]:
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
    RETURNING id
    """
    assert realm.message_retention_days is not None
    check_date = timezone_now() - timedelta(days=realm.message_retention_days)

    return move_rows(Message, query, returning_id=True, cross_realm_bot_ids=cross_realm_bot_ids,
                     realm_id=realm.id, recipient_types=recipient_types, check_date=check_date.isoformat())

def move_models_with_message_key_to_archive(msg_ids: List[int]) -> None:
    if not msg_ids:
        return

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
    if not msg_ids:
        return

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


def move_attachments_message_rows_to_archive(msg_ids: List[int]) -> None:
    if not msg_ids:
        return

    query = """
       INSERT INTO zerver_archivedattachment_messages (id, archivedattachment_id, archivedmessage_id)
       SELECT zerver_attachment_messages.id, zerver_attachment_messages.attachment_id,
           zerver_attachment_messages.message_id
       FROM zerver_attachment_messages
       INNER JOIN zerver_attachment
           ON zerver_attachment_messages.attachment_id = zerver_attachment.id
       LEFT JOIN zerver_archivedattachment_messages
           ON zerver_archivedattachment_messages.id = zerver_attachment_messages.id
       WHERE  zerver_attachment_messages.message_id IN {message_ids}
            AND  zerver_archivedattachment_messages.id IS NULL
    """
    with connection.cursor() as cursor:
        cursor.execute(query.format(message_ids=ids_list_to_sql_query_format(msg_ids)))

def delete_messages(msg_ids: List[int]) -> None:
    Message.objects.filter(id__in=msg_ids).delete()

def delete_expired_attachments() -> None:
    Attachment.objects.filter(
        messages__isnull=True, id__in=ArchivedAttachment.objects.all(),
    ).delete()

def move_related_objects_to_archive(msg_ids: List[int]) -> None:
    move_models_with_message_key_to_archive(msg_ids)
    move_attachments_to_archive(msg_ids)
    move_attachments_message_rows_to_archive(msg_ids)

def archive_messages_by_recipient(recipient: Recipient, message_retention_days: int) -> None:
    msg_ids = move_expired_messages_to_archive_by_recipient(recipient, message_retention_days)
    move_related_objects_to_archive(msg_ids)
    delete_messages(msg_ids)

def archive_personal_and_huddle_messages() -> None:
    for realm in Realm.objects.filter(message_retention_days__isnull=False):
        msg_ids = move_expired_personal_and_huddle_messages_to_archive(realm)
        move_related_objects_to_archive(msg_ids)
        delete_messages(msg_ids)

def archive_stream_messages() -> None:
    # We don't archive, if the stream has message_retention_days set to -1,
    # or if neither the stream nor the realm have a retention policy.
    streams = Stream.objects.exclude(message_retention_days=-1).filter(
        Q(message_retention_days__isnull=False) | Q(realm__message_retention_days__isnull=False)
    )
    retention_policy_dict = {}  # type: Dict[int, int]
    for stream in streams:
        #  if stream.message_retention_days is null, use the realm's policy
        if stream.message_retention_days:
            retention_policy_dict[stream.id] = stream.message_retention_days
        else:
            retention_policy_dict[stream.id] = stream.realm.message_retention_days

    recipients = get_stream_recipients([stream.id for stream in streams])
    for recipient in recipients:
        archive_messages_by_recipient(recipient, retention_policy_dict[recipient.type_id])

def archive_messages() -> None:
    archive_stream_messages()
    archive_personal_and_huddle_messages()

    # Since figuring out which attachments can be deleted requires scanning the whole
    # ArchivedAttachment table, we should do this just once, at the end of the archiving process:
    delete_expired_attachments()

def move_attachment_messages_to_archive_by_message(message_ids: List[int]) -> None:
    # Move attachments messages relation table data to archive.
    id_list = ', '.join(str(message_id) for message_id in message_ids)

    query = """
        INSERT INTO zerver_archivedattachment_messages (id, archivedattachment_id,
            archivedmessage_id)
        SELECT zerver_attachment_messages.id, zerver_attachment_messages.attachment_id,
            zerver_attachment_messages.message_id
        FROM zerver_attachment_messages
        LEFT JOIN zerver_archivedattachment_messages
            ON zerver_archivedattachment_messages.id = zerver_attachment_messages.id
        WHERE zerver_attachment_messages.message_id in ({message_ids})
            AND  zerver_archivedattachment_messages.id IS NULL
    """
    with connection.cursor() as cursor:
        cursor.execute(query.format(message_ids=id_list))


@transaction.atomic
def move_messages_to_archive(message_ids: List[int]) -> None:
    messages = list(Message.objects.filter(id__in=message_ids).values())
    if not messages:
        raise Message.DoesNotExist

    ArchivedMessage.objects.bulk_create([ArchivedMessage(**message) for message in messages])

    # Move user_messages to the archive.
    user_messages = UserMessage.objects.filter(
        message_id__in=message_ids).exclude(id__in=ArchivedUserMessage.objects.all()).values()
    user_messages_ids = [user_message['id'] for user_message in user_messages]
    ArchivedUserMessage.objects.bulk_create(
        [ArchivedUserMessage(**user_message) for user_message in user_messages]
    )

    for model in models_with_message_key:
        elements = model['class'].objects.filter(message_id__in=message_ids).exclude(
            id__in=model['archive_class'].objects.all()
        ).values()

        model['archive_class'].objects.bulk_create(
            [model['archive_class'](**element) for element in elements]
        )

    # Move attachments to archive
    attachments = Attachment.objects.filter(messages__id__in=message_ids).exclude(
        id__in=ArchivedAttachment.objects.all()).distinct().values()
    ArchivedAttachment.objects.bulk_create(
        [ArchivedAttachment(**attachment) for attachment in attachments]
    )

    move_attachment_messages_to_archive_by_message(message_ids)

    # Remove data from main tables
    Message.objects.filter(id__in=message_ids).delete()
    UserMessage.objects.filter(id__in=user_messages_ids, message_id__isnull=True).delete()

    archived_attachments = ArchivedAttachment.objects.filter(messages__id__in=message_ids).distinct()
    Attachment.objects.filter(messages__isnull=True, id__in=archived_attachments).delete()
