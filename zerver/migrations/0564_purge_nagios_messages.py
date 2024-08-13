import time

from django.conf import settings
from django.db import connection, migrations, transaction
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps
from psycopg2.sql import SQL, Literal


def purge_nagios_messages(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    Realm = apps.get_model("zerver", "Realm")
    UserProfile = apps.get_model("zerver", "UserProfile")

    with connection.cursor() as cursor:
        cursor.execute("SELECT MIN(id), MAX(id) FROM zerver_message")
        (min_id, max_id) = cursor.fetchone()
        if min_id is None:
            return

        bot_realm = Realm.objects.get(string_id=settings.SYSTEM_BOT_REALM)
        nagios_bot_tuples = [
            (settings.NAGIOS_SEND_BOT, settings.NAGIOS_RECEIVE_BOT),
            (settings.NAGIOS_STAGING_SEND_BOT, settings.NAGIOS_STAGING_RECEIVE_BOT),
        ]
        for sender_email, recipient_email in nagios_bot_tuples:
            try:
                sender_id = UserProfile.objects.get(
                    delivery_email=sender_email, realm_id=bot_realm.id
                ).id
                recipient_id = UserProfile.objects.get(
                    delivery_email=recipient_email, realm_id=bot_realm.id
                ).recipient_id
            except UserProfile.DoesNotExist:
                # If these special users don't exist, there's nothing to do.
                continue

            batch_size = 10000
            while True:
                with transaction.atomic():
                    # This query is an index only scan of the
                    # zerver_message_realm_sender_recipient_id index
                    message_id_query = SQL(
                        """
                        SELECT id
                          FROM zerver_message
                         WHERE realm_id = {realm_id}
                           AND sender_id = {sender_id}
                           AND recipient_id = {recipient_id}
                         ORDER BY id ASC
                         LIMIT {batch_size}
                           FOR UPDATE
                        """
                    ).format(
                        realm_id=Literal(bot_realm.id),
                        sender_id=Literal(sender_id),
                        recipient_id=Literal(recipient_id),
                        batch_size=Literal(batch_size),
                    )
                    cursor.execute(message_id_query)
                    message_ids = [id for (id,) in cursor.fetchall()]

                    if not message_ids:
                        break

                    message_id_str = SQL(",").join(map(Literal, message_ids))
                    cursor.execute(
                        SQL(
                            "DELETE FROM zerver_usermessage WHERE message_id IN ({message_ids})"
                        ).format(message_ids=message_id_str)
                    )
                    # We do not expect any attachments, but for
                    # correctness, we ensure they are detached before
                    # deleting the messages
                    cursor.execute(
                        SQL(
                            "DELETE FROM zerver_attachment_messages WHERE message_id IN ({message_ids})"
                        ).format(message_ids=message_id_str)
                    )
                    cursor.execute(
                        SQL("DELETE FROM zerver_message WHERE id IN ({message_ids})").format(
                            message_ids=message_id_str
                        )
                    )

                time.sleep(0.1)


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("zerver", "0563_zulipinternal_can_delete"),
    ]

    operations = [migrations.RunPython(purge_nagios_messages, elidable=True)]
