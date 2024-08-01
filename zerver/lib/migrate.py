import time
from collections.abc import Callable
from typing import Any

from django.db import connection
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.backends.utils import CursorWrapper
from django.db.migrations.state import StateApps
from psycopg2.sql import SQL, Composable, Identifier


def do_batch_update(
    cursor: CursorWrapper,
    table: str,
    assignments: list[Composable],
    batch_size: int = 10000,
    sleep: float = 0.1,
) -> None:
    # The string substitution below is complicated by our need to
    # support multiple PostgreSQL versions.
    stmt = SQL(
        """
        UPDATE {}
        SET {}
        WHERE id >= %s AND id < %s
    """
    ).format(
        Identifier(table),
        SQL(", ").join(assignments),
    )

    cursor.execute(SQL("SELECT MIN(id), MAX(id) FROM {}").format(Identifier(table)))
    (min_id, max_id) = cursor.fetchone()
    if min_id is None:
        return

    print(f"\n    Range of rows to update: [{min_id}, {max_id}]")
    while min_id <= max_id:
        lower = min_id
        upper = min_id + batch_size
        print(f"    Updating range [{lower},{upper})")
        cursor.execute(stmt, [lower, upper])

        min_id = upper
        time.sleep(sleep)

        # Once we've finished, check if any new rows were inserted to the table
        if min_id > max_id:
            cursor.execute(SQL("SELECT MAX(id) FROM {}").format(Identifier(table)))
            (max_id,) = cursor.fetchone()

    print("    Finishing...", end="")


def rename_indexes_constraints(
    old_table: str, new_table: str
) -> Callable[[StateApps, BaseDatabaseSchemaEditor], None]:
    # NOTE: `get_constraints`, which this uses, does not include any
    # information about if the index name was manually set from
    # Django, nor if it is a partial index.  This has the theoretical
    # possibility to cause false positives in the duplicate-index
    # check below, which would incorrectly drop one of the wanted
    # indexes.
    #
    # Before using this on a table, ensure that it does not use
    # partial indexes, nor manually-named indexes.
    def inner_migration(apps: StateApps, schema_editor: Any) -> None:
        seen_indexes = set()
        with connection.cursor() as cursor:
            constraints = connection.introspection.get_constraints(cursor, old_table)

            for old_name, infodict in constraints.items():
                if infodict["check"]:
                    suffix = "_check"
                    is_index = False
                elif infodict["foreign_key"] is not None:
                    is_index = False
                    to_table, to_column = infodict["foreign_key"]
                    suffix = f"_fk_{to_table}_{to_column}"
                elif infodict["primary_key"]:
                    suffix = "_pk"
                    is_index = True
                elif infodict["unique"]:
                    suffix = "_uniq"
                    is_index = True
                else:
                    suffix = "_idx" if len(infodict["columns"]) > 1 else ""
                    is_index = True
                new_name = schema_editor._create_index_name(new_table, infodict["columns"], suffix)
                if new_name in seen_indexes:
                    # This index duplicates one we already renamed,
                    # and attempting to rename it would cause a
                    # conflict.  Drop the duplicated index.
                    if is_index:
                        raw_query = SQL("DROP INDEX {old_name}").format(
                            old_name=Identifier(old_name)
                        )
                    else:
                        raw_query = SQL(
                            "ALTER TABLE {table_name} DROP CONSTRAINT {old_name}"
                        ).format(table_name=Identifier(old_table), old_name=Identifier(old_name))
                    cursor.execute(raw_query)
                    continue

                seen_indexes.add(new_name)
                if is_index:
                    raw_query = SQL("ALTER INDEX {old_name} RENAME TO {new_name}").format(
                        old_name=Identifier(old_name), new_name=Identifier(new_name)
                    )
                else:
                    raw_query = SQL(
                        "ALTER TABLE {old_table} RENAME CONSTRAINT {old_name} TO {new_name}"
                    ).format(
                        old_table=Identifier(old_table),
                        old_name=Identifier(old_name),
                        new_name=Identifier(new_name),
                    )
                cursor.execute(raw_query)

            for infodict in connection.introspection.get_sequences(cursor, old_table):
                old_name = infodict["name"]
                column = infodict["column"]
                new_name = f"{new_table}_{column}_seq"

                raw_query = SQL("ALTER SEQUENCE {old_name} RENAME TO {new_name}").format(
                    old_name=Identifier(old_name),
                    new_name=Identifier(new_name),
                )
                cursor.execute(raw_query)

            cursor.execute(
                SQL("ALTER TABLE {old_table} RENAME TO {new_table}").format(
                    old_table=Identifier(old_table), new_table=Identifier(new_table)
                )
            )

    return inner_migration
