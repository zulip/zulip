import sys
from contextlib import ExitStack, redirect_stdout
from typing import TextIO

from django.conf import settings
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps

BUILD_BAD_MOVES_TABLE = """
    CREATE TEMPORARY TABLE bad_moves_cve_2024_27286 AS (
      WITH messages_with_dangling_usermessages AS (
        SELECT zerver_message.id AS message_id,
               ARRAY_AGG(DISTINCT zerver_usermessage.id) AS extra_usermessage_ids,
               edit_history::jsonb

          FROM zerver_message

          JOIN zerver_stream
            ON zerver_stream.recipient_id = zerver_message.recipient_id

          JOIN zerver_usermessage
            ON zerver_usermessage.message_id = zerver_message.id

          LEFT JOIN zerver_subscription
            ON zerver_subscription.recipient_id = zerver_stream.recipient_id
           AND zerver_subscription.user_profile_id = zerver_usermessage.user_profile_id

         WHERE zerver_stream.invite_only
           AND zerver_subscription.id IS NULL
           AND zerver_message.edit_history IS NOT NULL

         GROUP BY zerver_message.id
      )
      SELECT message_id,
             extra_usermessage_ids,
             (history_entry->>'timestamp') AS timestamp_moved,
             (history_entry->>'prev_stream')::numeric AS moved_from_stream_id,
             (history_entry->>'stream')::numeric AS moved_to_stream_id
        FROM messages_with_dangling_usermessages
       CROSS JOIN JSONB_ARRAY_ELEMENTS(edit_history) AS history_entry
       WHERE history_entry->>'prev_stream' IS NOT NULL
       ORDER BY 1 ASC
    )
"""


# The SQL query above builds a `bad_moves_cve_2024_27286` temporary table, which
# finds all moved messages where there are UserMessage rows but no
# Subscription rows.  However, the difficulty is that this has a
# false-negative: between 2bc3924672fb and e566e985e4d2,
# multi-message moves only recorded their move on one of the
# messages.  There may thus be messages with dangling UserMessage
# rows which are in the same topic as ones we found already, but
# do not record as having moved, so were not found by that filter.
#
# We determine when zerver/0310_jsoonfield, the migration next merged
# after e566e985e4d2 was merged, was run, and examine all messages
# moved earlier than that migration.  We do not limit the early side
# of moves, since it is already naturally bounded by when message
# moves were introduced, and it is plausible that servers were running
# message-move the code before it was merged.
#
# For each potential single-message move in this range, we examine all
# other messages in the topic which were sent before the move, and
# check them for dangling UserMessage rows from users who are not
# subscribed.  We then compare those newly-found messages against the
# known bad messages to guess which move was responsible for them.
BROADEN_MOVES = """
    INSERT INTO bad_moves_cve_2024_27286 (
      WITH other_messages AS (
        SELECT messages_in_topic.id AS message_id,
               messages_in_topic.recipient_id,
               UPPER(messages_in_topic.subject) AS upper_topic,
               messages_in_topic.date_sent
          FROM bad_moves_cve_2024_27286

          JOIN zerver_message bad_message
            ON bad_moves_cve_2024_27286.message_id = bad_message.id

          JOIN zerver_message messages_in_topic
            ON bad_message.recipient_id = messages_in_topic.recipient_id
           AND UPPER(bad_message.subject) = UPPER(messages_in_topic.subject)

         WHERE TO_TIMESTAMP(timestamp_moved::numeric) < (
                   SELECT applied FROM django_migrations WHERE app = 'zerver' AND name = '0310_jsonfield'
               )
           AND messages_in_topic.date_sent < TO_TIMESTAMP(timestamp_moved::numeric)
           AND messages_in_topic.id NOT IN (SELECT already.message_id FROM bad_moves_cve_2024_27286 already)

         GROUP BY 1
      ),
      other_bad_messages AS (
        SELECT other_messages.message_id,
               other_messages.recipient_id,
               other_messages.upper_topic,
               other_messages.date_sent,
               ARRAY_AGG(DISTINCT zerver_usermessage.id) as extra_usermessage_ids

          FROM other_messages

          JOIN zerver_usermessage
            ON zerver_usermessage.message_id = other_messages.message_id

          LEFT JOIN zerver_subscription
            ON zerver_subscription.recipient_id = other_messages.recipient_id
           AND zerver_subscription.user_profile_id = zerver_usermessage.user_profile_id

         WHERE zerver_subscription.id IS NULL

         GROUP BY 1, 2, 3, 4
      )
      SELECT other_bad_messages.message_id,
             other_bad_messages.extra_usermessage_ids,
             move_trigger.timestamp_moved,
             move_trigger.moved_from_stream_id,
             move_trigger.moved_to_stream_id
        FROM other_bad_messages
        LEFT JOIN LATERAL (
          SELECT bad_moves_cve_2024_27286.*
            FROM bad_moves_cve_2024_27286
            JOIN zerver_message
              ON zerver_message.id = bad_moves_cve_2024_27286.message_id
            JOIN zerver_stream
              ON zerver_stream.recipient_id = zerver_message.recipient_id
             AND bad_moves_cve_2024_27286.moved_to_stream_id = zerver_stream.id
           WHERE other_bad_messages.recipient_id = zerver_message.recipient_id
             AND other_bad_messages.upper_topic = UPPER(zerver_message.subject)
             AND TO_TIMESTAMP(bad_moves_cve_2024_27286.timestamp_moved::numeric) > other_bad_messages.date_sent
           ORDER BY bad_moves_cve_2024_27286.message_id ASC, bad_moves_cve_2024_27286.timestamp_moved ASC
           LIMIT 1
        ) move_trigger ON true
    )
"""


def log_extra_usermessage_rows(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    Message = apps.get_model("zerver", "message")
    UserMessage = apps.get_model("zerver", "usermessage")
    Stream = apps.get_model("zerver", "stream")

    messages = Message.objects.raw(
        "SELECT * FROM zerver_message JOIN bad_moves_cve_2024_27286 ON message_id = zerver_message.id"
    )
    if len(messages) == 0:  # RawQuerySet does not have .exists() or .count()
        return

    with ExitStack() as stack:
        if settings.PRODUCTION:
            log_file: TextIO = stack.enter_context(
                open("/var/log/zulip/migrations_0501_delete_dangling_usermessages.log", "w")
            )
        else:
            log_file = sys.stderr
            print("", file=log_file)
        stack.enter_context(redirect_stdout(log_file))

        for message in messages:
            realm = message.realm
            # Reimplement realm.uri
            if realm.string_id == "":
                hostname = settings.EXTERNAL_HOST
            else:
                hostname = settings.REALM_HOSTS.get(
                    realm.string_id, f"{realm.string_id}.{settings.EXTERNAL_HOST}"
                )

            stream = Stream.objects.only("id").get(recipient_id=message.recipient_id)
            print(
                f"{settings.EXTERNAL_URI_SCHEME}{hostname}/#narrow/stream/{stream.id}/near/{message.id}",
            )
            print(
                f"    Moved at {message.timestamp_moved} from stream id {message.moved_from_stream_id} to {message.moved_to_stream_id}"
            )

            # Find out how many of those are users, and not bots
            ums = (
                UserMessage.objects.filter(
                    id__in=message.extra_usermessage_ids, user_profile__is_bot=False
                )
                .select_related("user_profile")
                .only("flags", "user_profile__delivery_email")
            )
            print(
                f"    Was still readable by {len(ums)} users, {len(message.extra_usermessage_ids) - len(ums)} bots",
            )
            if len(message.extra_usermessage_ids) > 25:
                continue
            for um in ums:
                read = "(read)" if um.flags & 1 else "(unread)"
                print(f"        {um.user_profile.delivery_email} {read}")
            print("")


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("zerver", "0496_alter_scheduledmessage_read_by_sender"),
    ]

    operations = [
        migrations.RunSQL(BUILD_BAD_MOVES_TABLE, elidable=True),
        migrations.RunSQL(BROADEN_MOVES, elidable=True),
        migrations.RunPython(log_extra_usermessage_rows, reverse_code=migrations.RunPython.noop),
        migrations.RunSQL(
            """
            DELETE FROM zerver_usermessage
             WHERE id IN (SELECT UNNEST(extra_usermessage_ids) FROM bad_moves_cve_2024_27286)
            """,
            elidable=True,
        ),
        migrations.RunSQL("DROP TABLE bad_moves_cve_2024_27286", elidable=True),
    ]
