
from datetime import timedelta

from django.db import connection, transaction
from django.utils.timezone import now as timezone_now
from zerver.models import (Message, UserMessage, ArchivedMessage, ArchivedUserMessage, Realm,
                           Attachment, ArchivedAttachment, Reaction, ArchivedReaction,
                           SubMessage, ArchivedSubMessage)

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
]  # type: List[Dict[str, Any]]

@transaction.atomic
def move_expired_rows(src_model: Any, raw_query: str, returning_id: bool=False,
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

def move_expired_messages_to_archive(realm: Realm) -> List[int]:
    query = """
    INSERT INTO zerver_archivedmessage ({dst_fields}, archive_timestamp)
    SELECT {src_fields}, '{archive_timestamp}'
    FROM zerver_message
    INNER JOIN zerver_userprofile ON zerver_message.sender_id = zerver_userprofile.id
    LEFT JOIN zerver_archivedmessage ON zerver_archivedmessage.id = zerver_message.id
    WHERE zerver_userprofile.realm_id = {realm_id}
          AND  zerver_message.pub_date < '{check_date}'
          AND zerver_archivedmessage.id is NULL
    RETURNING id
    """
    assert realm.message_retention_days is not None
    check_date = timezone_now() - timedelta(days=realm.message_retention_days)

    return move_expired_rows(Message, query, returning_id=True,
                             realm_id=realm.id, check_date=check_date.isoformat())

def move_expired_user_messages_to_archive(msg_ids: List[int]) -> List[int]:
    if not msg_ids:
        return []

    query = """
    INSERT INTO zerver_archivedusermessage ({dst_fields}, archive_timestamp)
    SELECT {src_fields}, '{archive_timestamp}'
    FROM zerver_usermessage
    LEFT JOIN zerver_archivedusermessage ON zerver_archivedusermessage.id = zerver_usermessage.id
    WHERE zerver_usermessage.message_id IN {message_ids}
        AND zerver_archivedusermessage.id is NULL
    RETURNING id
    """

    return move_expired_rows(UserMessage, query, returning_id=True,
                             message_ids=ids_list_to_sql_query_format(msg_ids))

def move_expired_models_with_message_key_to_archive(msg_ids: List[int]) -> None:
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
        move_expired_rows(model['class'], query, table_name=model['table_name'],
                          archive_table_name=model['archive_table_name'],
                          message_ids=ids_list_to_sql_query_format(msg_ids))

def move_expired_attachments_to_archive(realm: Realm, msg_ids: List[int]) -> None:
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
            AND zerver_attachment.realm_id = {realm_id}
            AND zerver_archivedattachment.id IS NULL
       GROUP BY zerver_attachment.id
    """
    assert realm.message_retention_days is not None
    move_expired_rows(Attachment, query, realm_id=realm.id,
                      message_ids=ids_list_to_sql_query_format(msg_ids))


def move_expired_attachments_message_rows_to_archive(realm: Realm, msg_ids: List[int]) -> None:
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
            AND zerver_attachment.realm_id = {realm_id}
            AND  zerver_archivedattachment_messages.id IS NULL
    """
    assert realm.message_retention_days is not None
    with connection.cursor() as cursor:
        cursor.execute(query.format(realm_id=realm.id,
                                    message_ids=ids_list_to_sql_query_format(msg_ids)))


def delete_expired_messages(realm: Realm, msg_ids: List[int]) -> None:
    removing_messages = Message.objects.filter(
        usermessage__isnull=True, id__in=msg_ids,
        sender__realm_id=realm.id
    )
    removing_messages.delete()


def delete_expired_user_messages(realm: Realm, usermsg_ids: List[int]) -> None:
    assert realm.message_retention_days is not None
    removing_user_messages = UserMessage.objects.filter(
        id__in=usermsg_ids,
        user_profile__realm_id=realm.id,
    )
    removing_user_messages.delete()


def delete_expired_attachments(realm: Realm) -> None:
    attachments_to_remove = Attachment.objects.filter(
        messages__isnull=True, id__in=ArchivedAttachment.objects.all(),
        realm_id=realm.id
    )
    attachments_to_remove.delete()

def move_expired_to_archive() -> Dict[int, Dict[str, List[int]]]:
    archived_data_info = {}  # type: Dict[int, Dict[str, List[int]]]
    for realm in Realm.objects.filter(message_retention_days__isnull=False).order_by("id"):
        msg_ids = move_expired_messages_to_archive(realm)
        usermsg_ids = move_expired_user_messages_to_archive(msg_ids)
        move_expired_models_with_message_key_to_archive(msg_ids)
        move_expired_attachments_to_archive(realm, msg_ids)
        move_expired_attachments_message_rows_to_archive(realm, msg_ids)

        archived_data_info[realm.id] = {
            'message_ids': msg_ids,
            'usermessage_ids': usermsg_ids,
        }

    return archived_data_info

def clean_expired(archived_data_info: Dict[int, Dict[str, List[int]]]) -> None:
    for realm in Realm.objects.filter(message_retention_days__isnull=False).order_by("id"):
        delete_expired_user_messages(realm, archived_data_info[realm.id]['usermessage_ids'])
        delete_expired_messages(realm, archived_data_info[realm.id]['message_ids'])
        delete_expired_attachments(realm)

def archive_messages() -> None:
    archived_data_info = move_expired_to_archive()
    clean_expired(archived_data_info)

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
