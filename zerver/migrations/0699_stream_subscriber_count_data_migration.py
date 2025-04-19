from django.db import connection, migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps
from psycopg2 import sql


def set_stream_subscribe_count(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    Realm = apps.get_model("zerver", "realm")
    Stream = apps.get_model("zerver", "Stream")
    Subscription = apps.get_model("zerver", "subscription")
    Recipient = apps.get_model("zerver", "recipient")

    # Here we compute per-stream subscriber_count in the sub-query which returns a delta_table,
    # then Update it in-place using that computed value.
    # The whole query is then executed by one batch per realm.
    query = sql.SQL(
        """UPDATE {stream_table} AS stream
            SET subscriber_count = delta_table.n_subscripers
            FROM (
                SELECT recipient.type_id AS stream_id,
                COUNT(subscription.user_profile_id) AS n_subscripers
                FROM {subscription_table} AS subscription
                JOIN {recipient_table} AS recipient
                    ON subscription.recipient_id = recipient.id
                WHERE
                    recipient.type = 2
                    AND subscription.active = True
                    AND subscription.is_user_active = True
                GROUP BY stream_id
            ) AS delta_table
            WHERE
                stream.realm_id = %(realm_id)s
                AND stream.id = delta_table.stream_id;
        """
    ).format(
        stream_table=sql.Identifier(Stream._meta.db_table),
        subscription_table=sql.Identifier(Subscription._meta.db_table),
        recipient_table=sql.Identifier(Recipient._meta.db_table),
    )

    cursor = connection.cursor()
    for realm in Realm.objects.all():
        cursor.execute(query, {"realm_id": realm.id})


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0698_stream_subscriber_count"),
    ]

    operations = [
        migrations.RunPython(set_stream_subscribe_count),
    ]
