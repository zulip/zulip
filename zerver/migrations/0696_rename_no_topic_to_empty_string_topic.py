from typing import Any

import orjson
from django.conf import settings
from django.db import connection, migrations, transaction
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps
from django.db.models import F, Func, JSONField, TextField, Value
from django.db.models.functions import Cast
from django.utils.timezone import now as timezone_now
from psycopg2.sql import SQL, Literal

LAST_EDIT_TIME = timezone_now()
LAST_EDIT_TIMESTAMP = int(LAST_EDIT_TIME.timestamp())


def update_messages_for_topic_edit(message_queryset: Any, notification_bot: Any) -> None:
    edit_history_entry = {
        "user_id": notification_bot.id,
        "timestamp": LAST_EDIT_TIMESTAMP,
        "prev_topic": "(no topic)",
        "topic": "",
    }
    update_fields: dict[str, object] = {
        "subject": "",
        "last_edit_time": LAST_EDIT_TIME,
        "edit_history": Cast(
            Func(
                Cast(
                    Value(orjson.dumps([edit_history_entry]).decode()),
                    JSONField(),
                ),
                Cast(
                    Func(
                        F("edit_history"),
                        Value("[]"),
                        function="COALESCE",
                    ),
                    JSONField(),
                ),
                function="",
                arg_joiner=" || ",
            ),
            TextField(),
        ),
    }
    message_queryset.update(**update_fields)


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
        AND lower(topic_name) = '(no topic)'
        ON CONFLICT (user_profile_id, stream_id, lower(topic_name)) DO UPDATE SET
        last_updated = EXCLUDED.last_updated,
        visibility_policy = EXCLUDED.visibility_policy;
        """
    ).format(channel_ids=channel_ids_str)
    with connection.cursor() as cursor:
        cursor.execute(query)

    user_topic_model.objects.filter(
        stream_id__in=channel_ids, topic_name__iexact="(no topic)"
    ).delete()


def move_messages_from_no_topic_to_empty_string_topic(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    """Move messages from "(no topic)" to the empty string topic.

    This helps in our plan to interpret messages sent to
    "(no topic)" as being sent to "".

    That interpretation is particularly helpful for older
    clients where sending messages with empty topic input box
    results in messages being sent to "(no topic)" topic.

    Note: In 0680, we moved messages from the "general chat" topic
    to the empty string topic. Therefore, we skip moving messages
    from "(no topic)" if an empty string topic already exists.

    Such cases—where both "(no topic)" and an empty string topic
    coexist in a channel—should be rare. The solution is to either
    manually rename the "(no topic)" topic or manually move its
    messages to the empty string topic.
    """
    Realm = apps.get_model("zerver", "Realm")
    Message = apps.get_model("zerver", "Message")
    UserTopic = apps.get_model("zerver", "UserTopic")
    ArchivedMessage = apps.get_model("zerver", "ArchivedMessage")
    ScheduledMessage = apps.get_model("zerver", "ScheduledMessage")
    UserProfile = apps.get_model("zerver", "UserProfile")

    try:
        internal_realm = Realm.objects.get(string_id=settings.SYSTEM_BOT_REALM)
    except Realm.DoesNotExist:
        # Server not initialized.
        return
    notification_bot = UserProfile.objects.get(
        email__iexact=settings.NOTIFICATION_BOT, realm=internal_realm
    )

    for realm in Realm.objects.all():
        with transaction.atomic(durable=True):
            # Uses index "zerver_message_realm_recipient_subject"
            channel_ids_with_empty_string_topic = set(
                Message.objects.filter(realm=realm, is_channel_message=True, subject="")
                .distinct("recipient__type_id")
                .values_list("recipient__type_id", flat=True)
            )
            # Uses index "zerver_message_realm_upper_subject"
            message_queryset = Message.objects.filter(
                realm=realm, is_channel_message=True, subject__iexact="(no topic)"
            ).exclude(recipient__type_id__in=channel_ids_with_empty_string_topic)
            channel_ids = list(
                message_queryset.distinct("recipient__type_id").values_list(
                    "recipient__type_id", flat=True
                )
            )

            update_messages_for_topic_edit(message_queryset, notification_bot)

            update_user_topic(channel_ids, UserTopic)

            # Uses index zerver_archivedmessage_realm_id_fab86889
            archived_channel_ids_with_empty_string_topic = set(
                ArchivedMessage.objects.filter(realm=realm, is_channel_message=True, subject="")
                .distinct("recipient__type_id")
                .values_list("recipient__type_id", flat=True)
            )
            channel_ids_with_empty_string_topic = channel_ids_with_empty_string_topic.union(
                archived_channel_ids_with_empty_string_topic
            )
            # Uses index zerver_archivedmessage_realm_id_fab86889
            archived_message_queryset = ArchivedMessage.objects.filter(
                realm=realm, is_channel_message=True, subject__iexact="(no topic)"
            ).exclude(recipient__type_id__in=channel_ids_with_empty_string_topic)
            update_messages_for_topic_edit(archived_message_queryset, notification_bot)

            ScheduledMessage.objects.filter(realm=realm, subject__iexact="(no topic)").update(
                subject=""
            )


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("zerver", "0695_is_channel_message_stats"),
    ]

    operations = [
        migrations.RunPython(
            move_messages_from_no_topic_to_empty_string_topic,
            reverse_code=migrations.RunPython.noop,
            elidable=True,
        ),
    ]
