
from datetime import timedelta

from django.db import connection, transaction
from django.utils.timezone import now as timezone_now
from zerver.models import (Message, UserMessage, ArchivedMessage, ArchivedUserMessage, Realm,
                           Attachment, ArchivedAttachment)

from typing import Any, List


@transaction.atomic
def move_expired_rows(src_model: Any, raw_query: str, **kwargs: Any) -> None:
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


def move_expired_messages_to_archive(realm: Realm) -> None:
    query = """
    INSERT INTO zerver_archivedmessage ({dst_fields}, archive_timestamp)
    SELECT {src_fields}, '{archive_timestamp}'
    FROM zerver_message
    INNER JOIN zerver_userprofile ON zerver_message.sender_id = zerver_userprofile.id
    LEFT JOIN zerver_archivedmessage ON zerver_archivedmessage.id = zerver_message.id
    WHERE zerver_userprofile.realm_id = {realm_id}
          AND  zerver_message.pub_date < '{check_date}'
          AND zerver_archivedmessage.id is NULL
    """
    assert realm.message_retention_days is not None
    check_date = timezone_now() - timedelta(days=realm.message_retention_days)
    move_expired_rows(Message, query, realm_id=realm.id, check_date=check_date.isoformat())


def move_expired_user_messages_to_archive(realm: Realm) -> None:
    query = """
    INSERT INTO zerver_archivedusermessage ({dst_fields}, archive_timestamp)
    SELECT {src_fields}, '{archive_timestamp}'
    FROM zerver_usermessage
    INNER JOIN zerver_userprofile ON zerver_usermessage.user_profile_id = zerver_userprofile.id
    INNER JOIN zerver_archivedmessage ON zerver_archivedmessage.id = zerver_usermessage.message_id
    LEFT JOIN zerver_archivedusermessage ON zerver_archivedusermessage.id = zerver_usermessage.id
    LEFT JOIN zerver_message ON zerver_usermessage.message_id = zerver_message.id
    WHERE zerver_userprofile.realm_id = {realm_id}
        AND  zerver_message.pub_date < '{check_date}'
        AND zerver_archivedusermessage.id is NULL
    """
    assert realm.message_retention_days is not None
    check_date = timezone_now() - timedelta(days=realm.message_retention_days)
    move_expired_rows(UserMessage, query, realm_id=realm.id, check_date=check_date.isoformat())

def move_expired_attachments_to_archive(realm: Realm) -> None:
    query = """
       INSERT INTO zerver_archivedattachment ({dst_fields}, archive_timestamp)
       SELECT {src_fields}, '{archive_timestamp}'
       FROM zerver_attachment
       INNER JOIN zerver_attachment_messages
           ON zerver_attachment_messages.attachment_id = zerver_attachment.id
       INNER JOIN zerver_archivedmessage
           ON zerver_archivedmessage.id = zerver_attachment_messages.message_id
       LEFT JOIN zerver_archivedattachment ON zerver_archivedattachment.id = zerver_attachment.id
       WHERE zerver_attachment.realm_id = {realm_id}
            AND zerver_archivedattachment.id IS NULL
       GROUP BY zerver_attachment.id
    """
    assert realm.message_retention_days is not None
    check_date = timezone_now() - timedelta(days=realm.message_retention_days)
    move_expired_rows(Attachment, query, realm_id=realm.id, check_date=check_date.isoformat())


def move_expired_attachments_message_rows_to_archive(realm: Realm) -> None:
    query = """
       INSERT INTO zerver_archivedattachment_messages (id, archivedattachment_id, archivedmessage_id)
       SELECT zerver_attachment_messages.id, zerver_attachment_messages.attachment_id,
           zerver_attachment_messages.message_id
       FROM zerver_attachment_messages
       INNER JOIN zerver_attachment
           ON zerver_attachment_messages.attachment_id = zerver_attachment.id
       INNER JOIN zerver_message ON zerver_attachment_messages.message_id = zerver_message.id
       LEFT JOIN zerver_archivedattachment_messages
           ON zerver_archivedattachment_messages.id = zerver_attachment_messages.id
       WHERE zerver_attachment.realm_id = {realm_id}
            AND  zerver_message.pub_date < '{check_date}'
            AND  zerver_archivedattachment_messages.id IS NULL
    """
    assert realm.message_retention_days is not None
    check_date = timezone_now() - timedelta(days=realm.message_retention_days)
    with connection.cursor() as cursor:
        cursor.execute(query.format(realm_id=realm.id, check_date=check_date.isoformat()))


def delete_expired_messages(realm: Realm) -> None:
    removing_messages = Message.objects.filter(
        usermessage__isnull=True, id__in=ArchivedMessage.objects.all(),
        sender__realm_id=realm.id
    )
    removing_messages.delete()


def delete_expired_user_messages(realm: Realm) -> None:
    removing_user_messages = UserMessage.objects.filter(
        id__in=ArchivedUserMessage.objects.all(),
        user_profile__realm_id=realm.id
    )
    removing_user_messages.delete()


def delete_expired_attachments(realm: Realm) -> None:
    attachments_to_remove = Attachment.objects.filter(
        messages__isnull=True, id__in=ArchivedAttachment.objects.all(),
        realm_id=realm.id
    )
    attachments_to_remove.delete()


def clean_unused_messages() -> None:
    unused_messages = Message.objects.filter(
        usermessage__isnull=True, id__in=ArchivedMessage.objects.all()
    )
    unused_messages.delete()


def archive_messages() -> None:
    for realm in Realm.objects.filter(message_retention_days__isnull=False).order_by("id"):
        move_expired_messages_to_archive(realm)
        move_expired_user_messages_to_archive(realm)
        move_expired_attachments_to_archive(realm)
        move_expired_attachments_message_rows_to_archive(realm)
        delete_expired_user_messages(realm)
        delete_expired_messages(realm)
        delete_expired_attachments(realm)
    clean_unused_messages()


def move_attachment_message_to_archive_by_message(message_ids: List[int]) -> None:
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
    arc_messages = []
    for message in messages:
        arc_message = ArchivedMessage(**message)
        arc_messages.append(arc_message)
    ArchivedMessage.objects.bulk_create(arc_messages)
    # Move user_messages to the archive.
    user_messages = UserMessage.objects.filter(
        message_id__in=message_ids).exclude(id__in=ArchivedUserMessage.objects.all())
    archiving_messages = []
    for user_message in user_messages.values():
        archiving_messages.append(ArchivedUserMessage(**user_message))
    ArchivedUserMessage.objects.bulk_create(archiving_messages)

    # Move attachments to archive
    attachments = Attachment.objects.filter(messages__id__in=message_ids).exclude(
        id__in=ArchivedAttachment.objects.all()).distinct()
    archiving_attachments = []
    for attachment in attachments.values():
        archiving_attachments.append(ArchivedAttachment(**attachment))
    ArchivedAttachment.objects.bulk_create(archiving_attachments)
    move_attachment_message_to_archive_by_message(message_ids)
    # Remove data from main tables
    Message.objects.filter(id__in=message_ids).delete()
    user_messages.filter(id__in=ArchivedUserMessage.objects.all(),
                         message_id__isnull=True).delete()
    archived_attachments = ArchivedAttachment.objects.filter(messages__id__in=message_ids).distinct()
    Attachment.objects.filter(messages__isnull=True, id__in=archived_attachments).delete()
