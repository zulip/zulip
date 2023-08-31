import time
from typing import List

from django.db.backends.utils import CursorWrapper
from psycopg2.sql import SQL, Composable, Identifier


def do_batch_update(
    cursor: CursorWrapper,
    table: str,
    assignments: List[Composable],
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
