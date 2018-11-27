
import time
from psycopg2.extensions import cursor, connection

from typing import Callable, Optional, Iterable, Any, Dict, List, Union, TypeVar, \
    Mapping

CursorObj = TypeVar('CursorObj', bound=cursor)
ParamsT = Union[Iterable[Any], Mapping[str, Any]]

# Similar to the tracking done in Django's CursorDebugWrapper, but done at the
# psycopg2 cursor level so it works with SQLAlchemy.
def wrapper_execute(self: CursorObj,
                    action: Callable[[str, Optional[ParamsT]], CursorObj],
                    sql: str,
                    params: Optional[ParamsT]=()) -> CursorObj:
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

    def execute(self, query: str,
                vars: Optional[ParamsT]=None) -> 'TimeTrackingCursor':
        return wrapper_execute(self, super().execute, query, vars)

    def executemany(self, query: str,
                    vars: Iterable[Any]) -> 'TimeTrackingCursor':
        return wrapper_execute(self, super().executemany, query, vars)

class TimeTrackingConnection(connection):
    """A psycopg2 connection class that uses TimeTrackingCursors."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.queries = []  # type: List[Dict[str, str]]
        super().__init__(*args, **kwargs)

    def cursor(self, *args: Any, **kwargs: Any) -> TimeTrackingCursor:
        kwargs.setdefault('cursor_factory', TimeTrackingCursor)
        return connection.cursor(self, *args, **kwargs)

def reset_queries() -> None:
    from django.db import connections
    for conn in connections.all():
        if conn.connection is not None:
            conn.connection.queries = []
