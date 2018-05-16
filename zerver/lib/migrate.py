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
