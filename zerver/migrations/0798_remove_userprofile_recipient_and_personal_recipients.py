import hashlib

from django.db import connection, migrations, transaction
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps
from psycopg2.sql import SQL, Identifier

PERSONAL_RECIPIENT_TYPE = 1
DIRECT_MESSAGE_GROUP_RECIPIENT_TYPE = 3
BATCH_SIZE = 5000

# Tables whose rows can point at a personal recipient, with the column
# identifying the message's sender.  Copied, like the backfill below,
# from migration 0790.
TABLES = [
    ("zerver_message", "sender_id"),
    ("zerver_archivedmessage", "sender_id"),
    ("zerver_scheduledmessage", "sender_id"),
    ("zerver_draft", "user_profile_id"),
]


def get_direct_message_group_hash(id_list: list[int]) -> str:
    """
    Takes a list of user IDs and returns a hash for the group consisting of
    these users. This is used to create a unique identifier for direct message groups.

    This function is copied from zerver/model/recipients.py to avoid import issues.
    """
    sorted_ids = sorted(id_list)
    hash_key = ",".join(str(x) for x in sorted_ids)
    return hashlib.sha1(hash_key.encode()).hexdigest()


def get_or_create_direct_message_group(apps: StateApps, id_list: list[int]) -> int:
    """
    Takes a list of user IDs and returns the DirectMessageGroup object for
    the group consisting of these users. If the DirectMessageGroup object
    does not yet exist, it will be transparently created.
    """

    direct_message_group_hash = get_direct_message_group_hash(id_list)
    with transaction.atomic(savepoint=False), connection.cursor() as cursor:
        # The "do update" is mostly superfluous here, but required so
        # that we get the id back if the row already existed.
        cursor.execute(
            """
            INSERT INTO zerver_huddle (huddle_hash, group_size)
            VALUES (%s, %s)
            ON CONFLICT (huddle_hash) DO UPDATE SET group_size = %s
            RETURNING id, recipient_id
            """,
            [direct_message_group_hash, len(id_list), len(id_list)],
        )
        direct_message_group_id, recipient_id = cursor.fetchone()
        if recipient_id is not None:
            return recipient_id

        cursor.execute(
            """
            INSERT INTO zerver_recipient (type_id, type)
            VALUES (%s, %s)
            RETURNING id
            """,
            [direct_message_group_id, DIRECT_MESSAGE_GROUP_RECIPIENT_TYPE],
        )
        recipient_id = cursor.fetchone()[0]

        cursor.execute(
            """
            UPDATE zerver_huddle SET recipient_id = %s WHERE id = %s
            """,
            [recipient_id, direct_message_group_id],
        )

        cursor.execute(
            """
            INSERT INTO zerver_subscription
                (recipient_id, user_profile_id, is_user_active,
                 active, is_muted, color, pin_to_top,
                 desktop_notifications, audible_notifications,
                 push_notifications, email_notifications,
                 wildcard_mentions_notify)
            SELECT %s, id, is_active,
                   true, false, '#c2c2c2', false,
                   NULL, NULL, NULL, NULL, NULL
            FROM zerver_userprofile
            WHERE id IN %s
            """,
            [recipient_id, tuple(id_list)],
        )
        return recipient_id


def backfill_update_recipient_type_of_personal_messages_to_dm_group(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    """Convert messages still attached to personal recipients into direct
    message groups.

    Copied from migration 0790, which is meant to have already done
    this. A deployment that ran an intermediate `main` commit can reach
    0798 with such messages still present, which would make the personal
    recipient DELETE below fail; rerunning the conversion here repairs
    that.  It only selects personal recipients that still have
    referencing rows, so it is a no-op once 0790 has run cleanly.
    """
    print()

    with connection.cursor() as cursor:
        # We use a temp table name distinct from the personal_recipients_to_process
        # table in migration 0790, which does the same work. An install or upgrade
        # applies both migrations in a single `migrate` run on one
        # connection, so reusing the name here would collide.
        #
        # Only include personal recipients that have rows in at least
        # one of the four tables we need to convert.
        cursor.execute(
            "CREATE TEMP TABLE personal_recipients_to_process_0798 AS "
            "SELECT r.id, type_id FROM zerver_recipient r "
            "JOIN zerver_userprofile u ON u.id = r.type_id "
            "WHERE r.type = %s AND ("
            "  EXISTS (SELECT 1 FROM zerver_message WHERE recipient_id = r.id)"
            "  OR EXISTS (SELECT 1 FROM zerver_archivedmessage WHERE recipient_id = r.id)"
            "  OR EXISTS (SELECT 1 FROM zerver_scheduledmessage WHERE recipient_id = r.id)"
            "  OR EXISTS (SELECT 1 FROM zerver_draft WHERE recipient_id = r.id)"
            ") ORDER BY u.realm_id, r.id",
            [PERSONAL_RECIPIENT_TYPE],
        )
        cursor.execute(
            "CREATE INDEX personal_recipients_to_process_0798_id"
            " ON personal_recipients_to_process_0798 (id)"
        )
        cursor.execute("SELECT COUNT(*) FROM personal_recipients_to_process_0798")
        (total,) = cursor.fetchone()
        if total == 0:
            return

        print(f"Processing {total} personal recipients...")

        processed = 0
        while True:
            cursor.execute(
                "SELECT id, type_id FROM personal_recipients_to_process_0798 LIMIT %s",
                # Use the batch size matching 0790:
                [500],
            )
            batch = cursor.fetchall()
            if not batch:
                break

            for personal_rec_id, receiving_user_id in batch:
                # Collect distinct senders per table for this recipient.
                sender_tables: dict[int, list[tuple[str, str]]] = {}
                for table, col in TABLES:
                    cursor.execute(
                        SQL("SELECT DISTINCT {} FROM {} WHERE recipient_id = %s").format(
                            Identifier(col), Identifier(table)
                        ),
                        [personal_rec_id],
                    )
                    for (sender_id,) in cursor.fetchall():
                        sender_tables.setdefault(sender_id, []).append((table, col))

                # For each sender, create the DMG and update rows atomically.
                for sender_id, tables_to_update in sender_tables.items():
                    if sender_id == receiving_user_id:
                        id_list = [sender_id]
                    else:
                        id_list = [sender_id, receiving_user_id]

                    with transaction.atomic():
                        group_recipient_id = get_or_create_direct_message_group(apps, id_list)
                        for table, col in tables_to_update:
                            cursor.execute(
                                SQL(
                                    "UPDATE {} SET recipient_id = %s"
                                    " WHERE {} = %s AND recipient_id = %s"
                                ).format(Identifier(table), Identifier(col)),
                                [group_recipient_id, sender_id, personal_rec_id],
                            )

            cursor.execute(
                "DELETE FROM personal_recipients_to_process_0798 WHERE id = ANY(%s)",
                [[row[0] for row in batch]],
            )
            processed += len(batch)
            print(f"  Processed {processed}/{total} personal recipients.")

        print("Migration completed.")


def delete_personal_recipient_data(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    """Delete Subscription rows and then Recipient rows for personal recipients.

    Done in batches to avoid long-running transactions on large
    deployments. Both loops are idempotent: re-running simply continues
    deleting whatever rows remain.
    """
    with connection.cursor() as cursor:
        while True:
            cursor.execute(
                SQL(
                    """
                    DELETE FROM zerver_subscription
                    WHERE id IN (
                        SELECT s.id FROM zerver_subscription s
                        JOIN zerver_recipient r ON s.recipient_id = r.id
                        WHERE r.type = %s
                        LIMIT %s
                    )
                    """
                ),
                [PERSONAL_RECIPIENT_TYPE, BATCH_SIZE],
            )
            if cursor.rowcount == 0:
                break

        while True:
            cursor.execute(
                SQL(
                    """
                    DELETE FROM zerver_recipient
                    WHERE id IN (
                        SELECT id FROM zerver_recipient
                        WHERE type = %s
                        LIMIT %s
                    )
                    """
                ),
                [PERSONAL_RECIPIENT_TYPE, BATCH_SIZE],
            )
            if cursor.rowcount == 0:
                break


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("zerver", "0797_userprofile_is_deleted"),
    ]

    operations = [
        migrations.RunPython(
            backfill_update_recipient_type_of_personal_messages_to_dm_group,
            reverse_code=migrations.RunPython.noop,
            elidable=True,
        ),
        # Drop the column via DROP COLUMN IF EXISTS to make the migration idempotent
        # and easier to re-run if needed. This is sometimes necessary for self-hosters
        # that improperly ran user_profile.delete() in the past and thus experience
        # DELETE FROM zerver_recipient crashes later in the migration. In such cases,
        # some db surgery and re-run of the migration is needed.
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    "ALTER TABLE zerver_userprofile DROP COLUMN IF EXISTS recipient_id",
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
            state_operations=[
                migrations.RemoveField(
                    model_name="userprofile",
                    name="recipient",
                ),
            ],
        ),
        migrations.RunPython(
            delete_personal_recipient_data,
            reverse_code=migrations.RunPython.noop,
            elidable=True,
        ),
    ]
