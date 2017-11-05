
from datetime import timedelta

from django.db import connection, transaction
from django.forms.models import model_to_dict
from django.utils.timezone import now as timezone_now
from zerver.models import Realm, Message, UserMessage, ArchivedMessage, ArchivedUserMessage, \
    Attachment, ArchivedAttachment

from typing import Any, Dict, Optional, Generator


def get_realm_expired_messages(realm: Any) -> Optional[Dict[str, Any]]:
    expired_date = timezone_now() - timedelta(days=realm.message_retention_days)
    expired_messages = Message.objects.order_by('id').filter(sender__realm=realm,
                                                             pub_date__lt=expired_date)
    if not expired_messages.exists():
        return None
    return {'realm_id': realm.id, 'expired_messages': expired_messages}


def get_expired_messages() -> Generator[Any, None, None]:
    # Get all expired messages by Realm.
    realms = Realm.objects.order_by('string_id').filter(
        deactivated=False, message_retention_days__isnull=False)
    for realm in realms:
        realm_expired_messages = get_realm_expired_messages(realm)
        if realm_expired_messages:
            yield realm_expired_messages


def move_attachment_message_to_archive_by_message(message_id: int) -> None:
    # Move attachments messages relation table data to archive.
    query = """
        INSERT INTO zerver_archivedattachment_messages (id, archivedattachment_id,
            archivedmessage_id)
        SELECT zerver_attachment_messages.id, zerver_attachment_messages.attachment_id,
            zerver_attachment_messages.message_id
        FROM zerver_attachment_messages
        LEFT JOIN zerver_archivedattachment_messages
            ON zerver_archivedattachment_messages.id = zerver_attachment_messages.id
        WHERE zerver_attachment_messages.message_id = {message_id}
            AND  zerver_archivedattachment_messages.id IS NULL
    """
    with connection.cursor() as cursor:
        cursor.execute(query.format(message_id=message_id))


@transaction.atomic
def move_message_to_archive(message_id: int) -> None:
    msg = list(Message.objects.filter(id=message_id).values())
    if not msg:
        raise Message.DoesNotExist
    arc_message = ArchivedMessage(**msg[0])
    arc_message.save()

    # Move user_messages to the archive.
    user_messages = UserMessage.objects.filter(
        message_id=message_id).exclude(id__in=ArchivedUserMessage.objects.all())
    archiving_messages = []
    for user_message in user_messages.values():
        archiving_messages.append(ArchivedUserMessage(**user_message))
    ArchivedUserMessage.objects.bulk_create(archiving_messages)

    # Move attachments to archive
    attachments = Attachment.objects.filter(messages__id=message_id).exclude(
        id__in=ArchivedAttachment.objects.all())
    archiving_attachments = []
    for attachment in attachments.values():
        archiving_attachments.append(ArchivedAttachment(**attachment))
    ArchivedAttachment.objects.bulk_create(archiving_attachments)
    move_attachment_message_to_archive_by_message(message_id)

    # Remove data from main tables
    Message.objects.get(id=message_id).delete()
    user_messages.filter(id__in=ArchivedUserMessage.objects.all(),
                         message_id__isnull=True).delete()
    archived_attachments = ArchivedAttachment.objects.filter(messages__id=message_id)
    Attachment.objects.filter(messages__isnull=True, id__in=archived_attachments).delete()
