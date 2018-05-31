from typing import Any, Callable, Dict, List, Tuple
from django.db.models.query import QuerySet
import re
import time

def create_index_if_not_exist(index_name: str, table_name: str, column_string: str,
                              where_clause: str) -> str:
    #
    # FUTURE TODO: When we no longer need to support postgres 9.3 for Trusty,
    #              we can use "IF NOT EXISTS", which is part of postgres 9.5
    #              (and which already is supported on Xenial systems).
    stmt = '''
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_class
                where relname = '%s'
                ) THEN
                    CREATE INDEX
                    %s
                    ON %s (%s)
                    %s;
            END IF;
        END$$;
        ''' % (index_name, index_name, table_name, column_string, where_clause)
    return stmt


def do_batch_update(cursor: Any,
                    table: str,
                    cols: List[str],
                    vals: List[str],
                    batch_size: int=10000,
                    sleep: float=0.1,
                    escape: bool=True) -> None:
    stmt = '''
        UPDATE %s
        SET (%s) = (%s)
        WHERE id >= %%s AND id < %%s
    ''' % (table, ', '.join(cols), ', '.join(['%s'] * len(cols)))

    cursor.execute("SELECT MIN(id), MAX(id) FROM %s" % (table,))
    (min_id, max_id) = cursor.fetchall()[0]
    if min_id is None:
        return

    print("%s rows need updating" % (max_id - min_id + 1,))
    while min_id <= max_id:
        lower = min_id
        upper = min_id + batch_size
        print('About to update range [%s,%s)' % (lower, upper))
        params = list(vals) + [lower, upper]
        if escape:
            cursor.execute(stmt, params=params)
        else:
            cursor.execute(stmt % tuple(params))
        min_id = upper
        time.sleep(sleep)

        # Once we've finished, check if any new rows were inserted to the table
        if min_id > max_id:
            cursor.execute("SELECT MAX(id) FROM %s" % (table,))
            max_id = cursor.fetchall()[0][0]
