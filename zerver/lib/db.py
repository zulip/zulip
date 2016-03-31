from __future__ import absolute_import

import time
from psycopg2.extensions import cursor, connection

# Similar to the tracking done in Django's CursorDebugWrapper, but done at the
# psycopg2 cursor level so it works with SQLAlchemy.
def wrapper_execute(self, action, sql, params=()):
    start = time.time()
    try:
        return action(sql, params)
    finally:
        stop = time.time()
        duration = stop - start
        self.connection.queries.append({
                'time': "%.3f" % duration,
                })

class TimeTrackingCursor(cursor):
    """A psycopg2 cursor class that tracks the time spent executing queries."""

    def execute(self, query, vars=None):
        return wrapper_execute(self, super(TimeTrackingCursor, self).execute, query, vars)

    def executemany(self, query, vars):
        return wrapper_execute(self, super(TimeTrackingCursor, self).executemany, query, vars)

class TimeTrackingConnection(connection):
    """A psycopg2 connection class that uses TimeTrackingCursors."""

    def __init__(self, *args, **kwargs):
        self.queries = [] # type: List[Dict[str, str]]
        super(TimeTrackingConnection, self).__init__(*args, **kwargs)

    def cursor(self, name=None):
        if name is None:
            return super(TimeTrackingConnection, self).cursor(cursor_factory=TimeTrackingCursor)
        else:
            return super(TimeTrackingConnection, self).cursor(name, cursor_factory=TimeTrackingCursor)

def reset_queries():
    from django.db import connections
    for conn in connections.all():
        if conn.connection is not None:
            conn.connection.queries = []
