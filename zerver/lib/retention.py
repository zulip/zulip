
from datetime import timedelta

from django.conf import settings
from django.db import connection, transaction, models
from django.db.models import QuerySet
from django.utils.timezone import now as timezone_now
from zerver.lib.upload import delete_message_image
from zerver.models import (Message, UserMessage, ArchivedMessage, ArchivedUserMessage, Realm,
                           Attachment, ArchivedAttachment)

from typing import Any, Dict, List, Optional, Text, Tuple


@transaction.atomic
def move_rows(select_query: str, fields: List[models.fields.Field],
              insert_query: str, **kwargs: Any) -> None:
    dst_fields = [field.column for field in fields]
    sql_args = {
        'dst_fields': ','.join(dst_fields),
        'select_query': select_query
    }
    sql_args.update(kwargs)
    with connection.cursor() as cursor:
        cursor.execute(
            insert_query.format(**sql_args)
        )


@transaction.atomic
def execute_select_query(query: str) -> Optional[List[Tuple[Any]]]:
    with connection.cursor() as cursor:
        cursor.execute(query)
        return cursor.cursor.fetchall()


def fill_select_query(select_query, src_model, fields, **kwargs):
    # type: (str, models.Model, List[models.fields.Field], **Any) -> str
    src_db_table = src_model._meta.db_table
    src_fields = ["{}.{}".format(src_db_table, field.column) for field in fields]
    sql_args = {
        'src_fields': ','.join(src_fields),
    }
    sql_args.update(kwargs)
    return select_query.format(**sql_args)


def move_expired_messages_to_archive(realm: Realm, dry_run: bool=False):
    select_query_template = """
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
    select_query = fill_select_query(select_query_template, Message, Message._meta.fields,
                                     realm_id=realm.id,
                                     check_date=check_date.isoformat(),
                                     archive_timestamp=timezone_now())
    if dry_run:
        return execute_select_query(select_query)
    insert_query = """
        INSERT INTO zerver_archivedmessage ({dst_fields}, archive_timestamp)
        {select_query}
    """
    move_rows(select_query, Message._meta.fields, insert_query)
    return None

def move_expired_user_messages_to_archive(
        realm: Realm, dry_run: bool=False) -> Optional[List[Tuple[Any]]]:
    select_query_template = """
        SELECT {src_fields}, '{archive_timestamp}'
        FROM zerver_usermessage
        INNER JOIN zerver_userprofile ON zerver_usermessage.user_profile_id = zerver_userprofile.id

        LEFT JOIN zerver_archivedusermessage ON zerver_archivedusermessage.id = zerver_usermessage.id
        LEFT JOIN zerver_message ON zerver_usermessage.message_id = zerver_message.id
        WHERE zerver_userprofile.realm_id = {realm_id}
            AND  zerver_message.pub_date < '{check_date}'
            AND zerver_archivedusermessage.id is NULL
    """
    check_query_part = """
        INNER JOIN zerver_archivedmessage ON zerver_archivedmessage.id = zerver_usermessage.message_id
    """

    assert realm.message_retention_days is not None
    check_date = timezone_now() - timedelta(days=realm.message_retention_days)
    select_query = fill_select_query(select_query_template, UserMessage, UserMessage._meta.fields,
                                     realm_id=realm.id,
                                     check_query_part=check_query_part if not dry_run else '',
                                     check_date=check_date.isoformat(),
                                     archive_timestamp=timezone_now())
    if dry_run:
        return execute_select_query(select_query)
    insert_query = """
        INSERT INTO zerver_archivedusermessage ({dst_fields}, archive_timestamp)
        {select_query}
    """
    move_rows(select_query, UserMessage._meta.fields, insert_query)
    return None


def move_expired_attachments_to_archive(realm, dry_run=False):
    # type: (Realm, bool) -> Optional[List[Tuple[Any]]]
    select_query_template = """
        SELECT {src_fields}, '{archive_timestamp}'
        FROM zerver_attachment
        INNER JOIN zerver_attachment_messages ON zerver_attachment_messages.attachment_id = zerver_attachment.id
        {check_query_part}
        LEFT JOIN zerver_archivedattachment ON zerver_archivedattachment.id = zerver_attachment.id
        WHERE zerver_attachment.realm_id = {realm_id}
            AND zerver_archivedattachment.id IS NULL
        GROUP BY zerver_attachment.id
    """
    check_query_part = """
        INNER JOIN zerver_archivedmessage ON zerver_archivedmessage.id = zerver_attachment_messages.message_id
    """
    assert realm.message_retention_days is not None
    check_date = timezone_now() - timedelta(days=realm.message_retention_days)
    select_query = fill_select_query(select_query_template, Attachment, Attachment._meta.fields,
                                     realm_id=realm.id,
                                     check_query_part=check_query_part if not dry_run else '',
                                     check_date=check_date.isoformat(),
                                     archive_timestamp=timezone_now())
    if dry_run:
        return execute_select_query(select_query)
    insert_query = """
       INSERT INTO zerver_archivedattachment ({dst_fields}, archive_timestamp)
        {select_query}
    """
    move_rows(select_query, Attachment._meta.fields, insert_query)
    return None


def move_expired_attachments_message_rows_to_archive(realm, dry_run=False):
    # type: (Realm, bool) -> Optional[List[Tuple[Any]]]
    select_query_template = """
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
    select_query = select_query_template.format(realm_id=realm.id, check_date=check_date)
    if dry_run:
        return execute_select_query(select_query)
    insert_query = """
        INSERT INTO zerver_archivedattachment_messages (id, archivedattachment_id, archivedmessage_id)
        {select_query}
    """
    with connection.cursor() as cursor:
        cursor.execute(insert_query.format(select_query=select_query))
    return None


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


def archive_messages(dry_run: bool=False) -> Optional[List[Dict[str, int]]]:
    # The main function for archiving messages' data.
    dry_run_result = []
    for realm in Realm.objects.filter(message_retention_days__isnull=False).order_by('id'):
        exp_messages = move_expired_messages_to_archive(realm, dry_run)
        exp_user_messages = move_expired_user_messages_to_archive(realm, dry_run)
        exp_attachments = move_expired_attachments_to_archive(realm, dry_run)
        exp_attachments_message = move_expired_attachments_message_rows_to_archive(realm, dry_run)
        if dry_run:
            dry_run_result.append({
                "realm_id": realm.id,
                "exp_messages": len(exp_messages),
                "exp_user_messages": len(exp_user_messages),
                "exp_attachments": len(exp_attachments),
                "exp_attachments_messages": len(exp_attachments_message)
            })
        else:
            delete_expired_user_messages(realm)
            delete_expired_messages(realm)
            delete_expired_attachments(realm)
    if dry_run_result:
        return dry_run_result
    clean_unused_messages()
    return None


def delete_expired_archived_attachments(query):
    # type: (QuerySet) -> None
    # Delete old archived attachments from archive table
    # after retention period for archived data.
    arc_attachments = query.filter(messages__isnull=True)
    for arc_att in arc_attachments:
        delete_message_image(arc_att.path_id)
    arc_attachments.delete()


def delete_expired_archived_data_by_realm(realm_id, dry_run=False):
    # type: (int, bool) -> Dict[str, int]
    # Delete old archived messages and user_messages from archive tables
    # after retention period for archived data.
    arc_expired_date = timezone_now() - timedelta(days=settings.ARCHIVED_DATA_RETENTION_DAYS)
    del_arc_user_messages = ArchivedUserMessage.objects.filter(
        archive_timestamp__lt=arc_expired_date,
        user_profile__realm_id=realm_id)
    del_arc_messages = ArchivedMessage.objects.filter(archive_timestamp__lt=arc_expired_date,
                                                      sender__realm_id=realm_id)
    del_arc_attachments = ArchivedAttachment.objects \
        .filter(archive_timestamp__lt=arc_expired_date, realm_id=realm_id) \
        .exclude(id__in=Attachment.objects.filter(realm_id=realm_id))
    if not dry_run:
        del_arc_user_messages.delete()
        del_arc_messages.filter(archivedusermessage__isnull=True).delete()
        delete_expired_archived_attachments(del_arc_attachments.filter(messages__isnull=True))
    return {
        "realm_id": realm_id,
        "del_arc_user_messages": del_arc_user_messages.count(),
        "del_arc_messages": del_arc_messages.count(),
        "del_arc_attachments": del_arc_attachments.count()
    }


def delete_expired_archived_data(dry_run=False):
    # type: (bool) -> List[Dict[str, int]]
    res = []
    for realm in Realm.objects.filter(message_retention_days__isnull=False).order_by('id'):
        res.append(delete_expired_archived_data_by_realm(realm.id, dry_run))
    return res


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


def restore_archived_messages_by_realm(realm_id, dry_run=False):
    # type: (int, bool) -> Optional[Dict[Text, int]]
    # Function for restoring archived messages by realm for emergency cases.
    select_query_template = """
        SELECT {src_fields}
        FROM zerver_archivedmessage
        INNER JOIN zerver_userprofile ON zerver_archivedmessage.sender_id = zerver_userprofile.id
        LEFT JOIN zerver_message ON zerver_message.id = zerver_archivedmessage.id
        WHERE zerver_userprofile.realm_id = {realm_id}
          AND zerver_message.id is NULL
    """
    select_query = fill_select_query(select_query_template, ArchivedMessage, Message._meta.fields,
                                     realm_id=realm_id)
    if dry_run:
        return execute_select_query(select_query)
    insert_query = """
        INSERT INTO zerver_message ({dst_fields})
        {select_query}
    """
    move_rows(select_query, Message._meta.fields, insert_query)
    return None


def restore_archived_usermessages_by_realm(realm_id, dry_run=False):
    # type: (int, bool) -> QuerySet
    # Function for restoring archived user_messages by realm for emergency cases.
    select_query_template = """
        SELECT {src_fields}
        FROM zerver_archivedusermessage
        INNER JOIN zerver_userprofile ON zerver_archivedusermessage.user_profile_id = zerver_userprofile.id
        {check_query_part}
        LEFT JOIN zerver_usermessage ON zerver_archivedusermessage.id = zerver_usermessage.id
        WHERE zerver_userprofile.realm_id = {realm_id}
             AND zerver_usermessage.id IS NULL
    """
    check_query_part = """
        INNER JOIN zerver_message ON zerver_archivedusermessage.message_id = zerver_message.id
    """
    select_query = fill_select_query(select_query_template, ArchivedUserMessage,
                                     UserMessage._meta.fields, realm_id=realm_id,
                                     check_query_part=check_query_part if not dry_run else '')
    if dry_run:
        return execute_select_query(select_query)
    insert_query = """
        INSERT INTO zerver_usermessage ({dst_fields})
        {select_query}
    """
    move_rows(select_query, UserMessage._meta.fields, insert_query)
    return None


def restore_archived_attachments_by_realm(realm_id, dry_run=False):
    # type: (int, bool) -> Optional[Dict[Text, int]]
    # Function for restoring archived attachments by realm for emergency cases.
    select_query_template = """
       SELECT {src_fields}
       FROM zerver_archivedattachment
       INNER JOIN zerver_archivedattachment_messages
           ON zerver_archivedattachment_messages.archivedattachment_id = zerver_archivedattachment.id
       INNER JOIN zerver_archivedmessage ON zerver_archivedmessage.id = zerver_archivedattachment_messages.archivedmessage_id
       INNER JOIN zerver_archivedusermessage ON zerver_archivedmessage.id = zerver_archivedusermessage.message_id
       INNER JOIN zerver_userprofile ON zerver_archivedmessage.id = zerver_archivedusermessage.message_id
       LEFT JOIN zerver_attachment ON zerver_attachment.id = zerver_archivedattachment.id
       WHERE zerver_userprofile.realm_id = {realm_id}
            AND zerver_attachment.id IS NULL
       GROUP BY zerver_archivedattachment.id
    """
    select_query = fill_select_query(select_query_template, ArchivedAttachment,
                                     Attachment._meta.fields,
                                     realm_id=realm_id)
    if dry_run:
        return execute_select_query(select_query)
    insert_query = """
        INSERT INTO zerver_attachment ({dst_fields})
        {select_query}
    """
    move_rows(select_query, Attachment._meta.fields, insert_query)
    return None


def restore_archived_attachments_message_rows_by_realm(realm_id, dry_run=False):
    # type: (int, bool) -> Optional[Dict[Text, int]]
    # Function for restoring archived data in many-to-many attachment_messages
    # table by realm for emergency cases.
    select_query_template = """
       SELECT zerver_archivedattachment_messages.id, zerver_archivedattachment_messages.archivedattachment_id,
           zerver_archivedattachment_messages.archivedmessage_id
       FROM zerver_archivedattachment_messages
       {check_query_part}
       INNER JOIN zerver_archivedusermessage ON
          zerver_archivedusermessage.message_id = zerver_archivedattachment_messages.archivedmessage_id
       INNER JOIN zerver_userprofile ON zerver_archivedusermessage.user_profile_id = zerver_userprofile.id
       LEFT JOIN zerver_attachment_messages ON
          zerver_archivedattachment_messages.id = zerver_attachment_messages.id
       WHERE zerver_userprofile.realm_id = {realm_id}
            AND zerver_attachment_messages.id IS NULL
       GROUP BY zerver_archivedattachment_messages.id
    """
    check_query_part = """
        INNER JOIN zerver_message ON zerver_archivedattachment_messages.archivedmessage_id = zerver_message.id
        INNER JOIN zerver_attachment ON zerver_archivedattachment_messages.archivedattachment_id = zerver_attachment.id
    """
    select_query = select_query_template.format(
        realm_id=realm_id,
        check_query_part=check_query_part if not dry_run else ''
    )
    if dry_run:
        return execute_select_query(select_query)
    insert_query = """
        INSERT INTO zerver_attachment_messages (id, attachment_id, message_id)
        {select_query}
    """
    with connection.cursor() as cursor:
        cursor.execute(insert_query.format(select_query=select_query))
    return None


def restore_realm_archived_data(realm_id, dry_run=False):
    # type: (int, bool) -> Dict[str, int]
    # The main function for restoring archived messages' data by realm.
    restoring_arc_messages = restore_archived_messages_by_realm(realm_id, dry_run)
    restoring_arc_user_messages = restore_archived_usermessages_by_realm(realm_id, dry_run)
    restoring_arc_attachemnts = restore_archived_attachments_by_realm(realm_id, dry_run)
    rest_arc_attachments_message = restore_archived_attachments_message_rows_by_realm(realm_id,
                                                                                      dry_run)
    if dry_run:
        return {
            "restoring_arc_messages": len(restoring_arc_messages),
            "restoring_arc_user_messages": len(restoring_arc_user_messages),
            "restoring_arc_attachemnts": len(restoring_arc_attachemnts),
            "rest_arc_attachments_messages": len(rest_arc_attachments_message)
        }
    realm = Realm.objects.get(id=realm_id)
    realm.message_retention_days = None
    realm.save()
    return None
