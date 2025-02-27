from typing import Any

from django.db import connection, migrations, models, transaction
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps
from psycopg2.sql import SQL, Identifier, Literal


def update_user_topic(channel_ids: list[int], user_topic_model: type[Any]) -> None:
    if not channel_ids:
        return

    # Both insert and delete query uses index "zerver_mutedtopic_stream_topic".
    channel_ids_str = SQL(",").join(map(Literal, channel_ids))
    query = SQL(
        """
        INSERT INTO zerver_usertopic(user_profile_id, stream_id, recipient_id, topic_name, last_updated, visibility_policy)
        SELECT user_profile_id, stream_id, recipient_id, '', last_updated, visibility_policy
        FROM zerver_usertopic
        WHERE stream_id IN ({channel_ids})
        AND lower(topic_name) = 'general chat'
        ON CONFLICT (user_profile_id, stream_id, lower(topic_name)) DO UPDATE SET
        last_updated = EXCLUDED.last_updated,
        visibility_policy = EXCLUDED.visibility_policy;
        """
    ).format(channel_ids=channel_ids_str)
    with connection.cursor() as cursor:
        cursor.execute(query)

    user_topic_model.objects.filter(
        stream_id__in=channel_ids, topic_name__iexact="general chat"
    ).delete()


def update_edit_history(message_model: type[Any]) -> None:
    BATCH_SIZE = 10000
    lower_id_bound = 0

    max_id = message_model.objects.aggregate(models.Max("id"))["id__max"]
    if max_id is None:
        return

    while lower_id_bound < max_id:
        upper_id_bound = min(lower_id_bound + BATCH_SIZE, max_id)
        with connection.cursor() as cursor:
            query = SQL(
                """
                UPDATE {table_name}
                SET edit_history = (
                    SELECT JSONB_AGG(
                        elem
                        ||
                        (CASE
                            WHEN elem ? 'prev_topic' AND elem->>'prev_topic' = 'general chat'
                            THEN '{{"prev_topic": ""}}'::jsonb
                            ELSE '{{}}'::jsonb
                        END)
                        ||
                        (CASE
                            WHEN elem ? 'topic' AND elem->>'topic' = 'general chat'
                            THEN '{{"topic": ""}}'::jsonb
                            ELSE '{{}}'::jsonb
                        END)
                    )::text
                    FROM JSONB_ARRAY_ELEMENTS(edit_history::jsonb) AS elem
                )
                WHERE edit_history IS NOT NULL
                AND id > %(lower_id_bound)s AND id <= %(upper_id_bound)s
                AND (
                    edit_history::jsonb @> '[{{"prev_topic": "general chat"}}]' OR
                    edit_history::jsonb @> '[{{"topic": "general chat"}}]'
                );
            """
            ).format(table_name=Identifier(message_model._meta.db_table))
            cursor.execute(
                query,
                {
                    "lower_id_bound": lower_id_bound,
                    "upper_id_bound": upper_id_bound,
                },
            )

        print(f"Processed {upper_id_bound} / {max_id}")
        lower_id_bound += BATCH_SIZE


def rename_general_chat_to_empty_string_topic(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    """Because legacy clients will be unable to distinguish the topic "general chat"
    from the "" topic (displayed as italicized "general chat"), it's helpful
    to not have both types of topics exist in an organization.

    Further, the "general chat" topic is likely to in almost every
    case be the result of an organization that followed our advice to
    just make a "general chat" topic for topic-free chat; the new
    "general chat" feature naturally replaces that learned
    behavior.

    So it makes sense to just consider those older "general chat"
    topics to be the same as the modern general chat topic.

    The technical way to do that is to rewrite those topics in the
    database to be represented as `""` rather than "general chat",
    since we've endeavored to make the distinction between those two
    storage approaches invisible to legacy clients at the API layer.

    Thus, we don't generate edit history entries for this, since we're
    thinking of it as redefining how "general chat" is stored in the
    database.
    """
    Realm = apps.get_model("zerver", "Realm")
    Message = apps.get_model("zerver", "Message")
    UserTopic = apps.get_model("zerver", "UserTopic")
    ArchivedMessage = apps.get_model("zerver", "ArchivedMessage")
    ScheduledMessage = apps.get_model("zerver", "ScheduledMessage")

    for realm in Realm.objects.all():
        with transaction.atomic(durable=True):
            # Uses index "zerver_message_realm_upper_subject"
            message_queryset = Message.objects.filter(realm=realm, subject__iexact="general chat")
            channel_ids = list(
                message_queryset.distinct("recipient__type_id").values_list(
                    "recipient__type_id", flat=True
                )
            )

            message_queryset.update(subject="")

            # Limiting the UserTopic query to only those channels that
            # contain an actual general chat topic does not guaranteed
            # updating all UserTopic rows, since it's possible to
            # follow/mute an empty topic. But it does guarantee that
            # we update all rows that have any current effect.
            update_user_topic(channel_ids, UserTopic)

            ArchivedMessage.objects.filter(realm=realm, subject__iexact="general chat").update(
                subject=""
            )
            ScheduledMessage.objects.filter(realm=realm, subject__iexact="general chat").update(
                subject=""
            )

    for message_model in [Message, ArchivedMessage]:
        update_edit_history(message_model)


class Migration(migrations.Migration):
    """
    Zulip now supports empty string as a valid topic name.
    For clients predating this feature, such messages appear
    in "general chat" topic. Messages sent to "general chat" are
    stored in the database as having a "" topic. This migration
    renames the existing "general chat" topic in the database to "".
    """

    atomic = False

    dependencies = [
        ("zerver", "0679_zerver_message_edit_history_id"),
    ]

    operations = [
        migrations.RunPython(
            rename_general_chat_to_empty_string_topic,
            reverse_code=migrations.RunPython.noop,
            elidable=True,
        ),
    ]
