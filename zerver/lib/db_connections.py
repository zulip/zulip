from django.db import connections


def reset_queries() -> None:
    for conn in connections.all():
        if conn.connection is not None:
            conn.connection.queries = []
