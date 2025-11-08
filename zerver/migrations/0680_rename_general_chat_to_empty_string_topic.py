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
        "prev_topic": "general chat",
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


def move_messages_from_general_chat_to_empty_string_topic(
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

    The technical way to do that is to move messages in "general chat"
    topics to `""`, since we've endeavored to make the distinction between
    those two storage approaches invisible to legacy clients at the API layer.
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
            # Uses index "zerver_message_realm_upper_subject"
            message_queryset = Message.objects.filter(realm=realm, subject__iexact="general chat")
            channel_ids = list(
                message_queryset.distinct("recipient__type_id").values_list(
                    "recipient__type_id", flat=True
                )
            )

            update_messages_for_topic_edit(message_queryset, notification_bot)

            # Limiting the UserTopic query to only those channels that
            # contain an actual general chat topic does not guaranteed
            # updating all UserTopic rows, since it's possible to
            # follow/mute an empty topic. But it does guarantee that
            # we update all rows that have any current effect.
            update_user_topic(channel_ids, UserTopic)

            # Uses index zerver_archivedmessage_realm_id_fab86889
            archived_message_queryset = ArchivedMessage.objects.filter(
                realm=realm, subject__iexact="general chat"
            )
            update_messages_for_topic_edit(archived_message_queryset, notification_bot)

            ScheduledMessage.objects.filter(realm=realm, subject__iexact="general chat").update(
                subject=""
            )


class Migration(migrations.Migration):
    """
    Zulip now supports empty string as a valid topic name.
    For clients predating this feature, such messages appear
    in "general chat" topic. Messages sent to "general chat" are
    stored in the database as having a "" topic. This migration
    moves the messages from "general chat" topic to `""`.
    """

    atomic = False

    dependencies = [
        ("zerver", "0679_zerver_message_edit_history_id"),
    ]

    operations = [
        migrations.RunPython(
            move_messages_from_general_chat_to_empty_string_topic,
            reverse_code=migrations.RunPython.noop,
            elidable=True,
        ),
    ]
