# -*- coding: utf-8 -*-
from typing import Any
from six import text_type
from django.db import connections, DEFAULT_DB_ALIAS

def check_if_database_exist(database_name, **options):
    # type: (text_type, **Any) -> bool
    db = options.get('database', DEFAULT_DB_ALIAS)
    connection = connections[db]

    with connection.cursor() as cursor:
        cursor.execute("SELECT 1 from pg_database WHERE datname='{}';".format(database_name))
        return_value = bool(cursor.fetchone())
    connections.close_all()
    return return_value
