from datetime import timedelta

from django.conf import settings
from django.db import connection, migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps
from psycopg2.sql import SQL, Identifier, Literal


def fix_email_gateway_attachment_owner(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    Realm = apps.get_model("zerver", "Realm")
    UserProfile = apps.get_model("zerver", "UserProfile")
    Client = apps.get_model("zerver", "Client")
    Message = apps.get_model("zerver", "Message")
    ArchivedMessage = apps.get_model("zerver", "ArchivedMessage")
    Stream = apps.get_model("zerver", "Stream")
    Attachment = apps.get_model("zerver", "Attachment")
    ArchivedAttachment = apps.get_model("zerver", "ArchivedAttachment")

    if not Realm.objects.exists():
        return

    mail_gateway_bot = UserProfile.objects.get(email__iexact=settings.EMAIL_GATEWAY_BOT)

    # "Internal" is the client-id of all mail gateway posts
    internal_client, _ = Client.objects.get_or_create(name="Internal")

    # We only look in Attachment and not ArchivedAttachment because,
    # never having been associated with a message, there is no way for
    # the attachments to have been archived.
    orphan_attachments = Attachment.objects.filter(
        messages=None,
        owner_id=mail_gateway_bot.id,
    )
    if len(orphan_attachments) == 0:
        return

    print("")
    print(f"Found {len(orphan_attachments)} email gateway attachments to reattach")
    for attachment in orphan_attachments:
        # We look for the message posted by "Internal" at the same
        # time, in the same realm, which has a link to the attachment
        # but no "has_attachments".  There are potentially other,
        # later, messages (possibly from other users, to other
        # places!) which tried to link to the attachment; we do not
        # fix those references, because finding them efficiently is
        # quite hard, as is calculating if they "should" have had
        # access to the attachment at the time.
        print(
            f"Looking for a message to attach {attachment.path_id}, created {attachment.create_time}"
        )
        possible_matches = []
        for model_class in (Message, ArchivedMessage):
            possible_matches.extend(
                # All messages with this bug will have
                # `has_attachment=False`, since they failed to attach
                # the contents.  However, we cannot limit to
                # sender=mail_gateway_bot because they were sent "as"
                # some other user.
                model_class.objects.filter(
                    has_attachment=False,
                    realm_id=attachment.realm_id,
                    sending_client_id=internal_client.id,
                    date_sent__gte=attachment.create_time,
                    date_sent__lte=attachment.create_time + timedelta(minutes=5),
                    content__contains="/user_uploads/" + attachment.path_id,
                ).order_by("date_sent")
            )
        if len(possible_matches) == 0:
            print("  No matches!")
            continue

        # If there are 1 or more matches, we assume the earliest is
        # the correct one, since it's ~impossible to have predicted
        # the URL before it was first sent.
        message = possible_matches[0]
        print(f"  Found {message.id} @ {message.date_sent} by {message.sender.delivery_email})")

        # If this is an ArchivedMessage, then we have to move the
        # Attachment into an ArchivedAttachment.  We also have to
        # generate an zerver_archivedattachment_message row with an id
        # based on the next free from zerver_attachment_message, since
        # those are one id space.
        if isinstance(message, ArchivedMessage):
            # move_rows
            fields = list(Attachment._meta.fields)
            src_fields = [Identifier("zerver_attachment", field.column) for field in fields]
            dst_fields = [Identifier(field.column) for field in fields]
            with connection.cursor() as cursor:
                raw_query = SQL(
                    """
                    INSERT INTO zerver_archivedattachment ({dst_fields})
                        SELECT {src_fields}
                        FROM zerver_attachment
                        WHERE id = {id}
                    ON CONFLICT (id) DO NOTHING
                    RETURNING id
                    """
                )
                cursor.execute(
                    raw_query.format(
                        src_fields=SQL(",").join(src_fields),
                        dst_fields=SQL(",").join(dst_fields),
                        id=Literal(attachment.id),
                    )
                )
                archived_ids = [id for (id,) in cursor.fetchall()]
                if len(archived_ids) != 1:
                    print("!!! Did not create one archived attachment row!")
            attachment.delete()
            attachment = ArchivedAttachment.objects.get(id=archived_ids[0])

        # Determine message (and thus attachment) properties; this is
        # from do_claim_attachments
        is_message_realm_public = False
        is_message_web_public = False
        if message.recipient.type == 2:  # Recipient.STREAM
            stream = Stream.objects.get(id=message.recipient.type_id)
            is_message_realm_public = not stream.invite_only and not stream.is_in_zephyr_realm
            is_message_web_public = stream.is_web_public

        attachment.owner_id = message.sender_id
        attachment.is_web_public = is_message_web_public
        attachment.is_realm_public = is_message_realm_public
        attachment.save(update_fields=["owner_id", "is_web_public", "is_realm_public"])

        if isinstance(attachment, ArchivedAttachment):
            assert isinstance(message, ArchivedMessage)
            # We need to use the sequence from
            # zerver_attachment_messages, since that id is reused when
            # restoring the message.
            with connection.cursor() as cursor:
                raw_query = SQL(
                    """
                    INSERT INTO zerver_archivedattachment_messages
                           (id, archivedattachment_id, archivedmessage_id)
                    VALUES (nextval(pg_get_serial_sequence('zerver_attachment_messages', 'id')),
                            {attachment_id}, {message_id})
                    """
                )
                cursor.execute(
                    raw_query.format(
                        attachment_id=Literal(attachment.id),
                        message_id=Literal(message.id),
                    )
                )
        else:
            assert isinstance(message, Message)
            attachment.messages.add(message)

        message.has_attachment = True
        message.save(update_fields=["has_attachment"])


class Migration(migrations.Migration):
    """
    Messages sent "as" a user via the email gateway had their
    attachments left orphan, accidentally owned by the email gateway
    bot.  Find each such orphaned attachment, and re-own it and attach
    it to the appropriate message.

    """

    dependencies = [
        ("zerver", "0422_multiuseinvite_status"),
    ]

    operations = [
        migrations.RunPython(
            fix_email_gateway_attachment_owner,
            reverse_code=migrations.RunPython.noop,
            elidable=True,
        )
    ]
