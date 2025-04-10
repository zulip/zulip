from collections import defaultdict

from django.db import connection, migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps
from psycopg2 import sql


def set_stream_subscribe_count(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    Stream = apps.get_model("zerver", "Stream")
    Subscription = apps.get_model("zerver", "subscription")

    stream_subsriptions = Subscription.objects.filter(
        recipient__type=2,
        recipient__type_id__in=Stream.objects.values("id"),
        active=True,
        is_user_active=True,
    ).select_related("recipient")

    subscriber_count_changes: dict[int, set[int]] = defaultdict(set)

    for sub in stream_subsriptions:
        subscriber_count_changes[sub.recipient.type_id].add(sub.user_profile_id)

    if len(subscriber_count_changes) == 0:
        return

    stream_delta_values = sql.SQL(", ").join(
        [
            sql.SQL("({}, {})").format(sql.Literal(stream_id), sql.Literal(len(subscribers)))
            for stream_id, subscribers in subscriber_count_changes.items()
        ]
    )

    query = sql.SQL(
        """UPDATE {stream_table}
            SET subscriber_count = {stream_table}.subscriber_count + delta_table.delta
            FROM (VALUES {stream_delta_values}) AS delta_table(id, delta)
            WHERE {stream_table}.id = delta_table.id;
        """
    ).format(
        stream_table=sql.Identifier(Stream._meta.db_table),
        stream_delta_values=stream_delta_values,
    )

    with connection.cursor() as cursor:
        cursor.execute(query)


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0698_stream_subscriber_count"),
    ]

    operations = [
        migrations.RunPython(set_stream_subscribe_count),
    ]
