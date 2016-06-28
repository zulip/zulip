from __future__ import absolute_import

import time
from psycopg2.extensions import cursor, connection

from typing import Callable, Optional, Iterable, Any, Dict, Union, TypeVar, \
    Mapping, Sequence
from six import text_type
from zerver.lib.str_utils import NonBinaryStr

CursorObj = TypeVar('CursorObj', bound=cursor)
ParamsT = Union[Iterable[Any], Mapping[text_type, Any]]

# Similar to the tracking done in Django's CursorDebugWrapper, but done at the
# psycopg2 cursor level so it works with SQLAlchemy.
def wrapper_execute(self, action, sql, params=()):
    # type: (CursorObj, Callable[[NonBinaryStr, Optional[ParamsT]], CursorObj], NonBinaryStr, ParamsT) -> CursorObj
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
        # type: (NonBinaryStr, Optional[ParamsT]) -> TimeTrackingCursor
        return wrapper_execute(self, super(TimeTrackingCursor, self).execute, query, vars)

    def executemany(self, query, vars):
        # type: (NonBinaryStr, Iterable[Any]) -> TimeTrackingCursor
        return wrapper_execute(self, super(TimeTrackingCursor, self).executemany, query, vars)

class TimeTrackingConnection(connection):
    """A psycopg2 connection class that uses TimeTrackingCursors."""

    def __init__(self, *args, **kwargs):
        # type: (Sequence[Any], Mapping[text_type, Any]) -> None
        self.queries = [] # type: List[Dict[str, str]]
        super(TimeTrackingConnection, self).__init__(*args, **kwargs)

    def cursor(self, name=None):
        # type: (Optional[text_type]) -> TimeTrackingCursor
        if name is None:
            return super(TimeTrackingConnection, self).cursor(cursor_factory=TimeTrackingCursor)
        else:
            return super(TimeTrackingConnection, self).cursor(name, cursor_factory=TimeTrackingCursor)

def reset_queries():
    # type: () -> None
    from django.db import connections
    for conn in connections.all():
        if conn.connection is not None:
            conn.connection.queries = []
