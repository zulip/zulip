# Generated by Django 4.2.11 on 2024-04-03 13:36

from django.db import connection, migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps
from psycopg2.sql import SQL


def create_named_user_group_objects_for_groups(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    BATCH_SIZE = 1000
    with connection.cursor() as cursor:
        cursor.execute(SQL("SELECT MAX(id) FROM zerver_usergroup"))
        (max_id,) = cursor.fetchone()

    if max_id is None:
        return

    # Make sure we run past the end in case of new rows created while we run.
    max_id += BATCH_SIZE / 2
    lower_id_bound = 0
    while lower_id_bound < max_id:
        upper_id_bound = min(lower_id_bound + BATCH_SIZE, max_id)
        with connection.cursor() as cursor:
            query = SQL("""
                INSERT INTO zerver_namedusergroup (usergroup_ptr_id, realm_id, name, description, is_system_group, can_mention_group_id)
                SELECT id, realm_id, name, description, is_system_group, can_mention_group_id
                FROM zerver_usergroup
                WHERE id > %(lower_id_bound)s AND id <= %(upper_id_bound)s
                ON CONFLICT (usergroup_ptr_id) DO UPDATE SET
                    name = excluded.name,
                    description = excluded.description,
                    can_mention_group_id = excluded.can_mention_group_id
                """)
            cursor.execute(
                query,
                {
                    "lower_id_bound": lower_id_bound,
                    "upper_id_bound": upper_id_bound,
                },
            )

        print(f"Processed {upper_id_bound} / {max_id}")
        lower_id_bound += BATCH_SIZE


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("zerver", "0512_namedusergroup"),
    ]

    operations = [
        migrations.RunPython(
            create_named_user_group_objects_for_groups,
            elidable=True,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
