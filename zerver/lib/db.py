import time
from typing import Any, Callable, Dict, Iterable, List, Mapping, Sequence, TypeVar, Union

from psycopg2.extensions import connection, cursor
from psycopg2.sql import Composable

CursorObj = TypeVar("CursorObj", bound=cursor)
Query = Union[str, bytes, Composable]
Params = Union[Sequence[object], Mapping[str, object], None]
ParamsT = TypeVar("ParamsT")


# Similar to the tracking done in Django's CursorDebugWrapper, but done at the
# psycopg2 cursor level so it works with SQLAlchemy.
def wrapper_execute(
    self: CursorObj, action: Callable[[Query, ParamsT], None], sql: Query, params: ParamsT
) -> None:
    start = time.time()
    try:
        action(sql, params)
    finally:
        stop = time.time()
        duration = stop - start
        self.connection.queries.append(
            {
                "time": f"{duration:.3f}",
            }
        )


class TimeTrackingCursor(cursor):
    """A psycopg2 cursor class that tracks the time spent executing queries."""

    def execute(self, query: Query, vars: Params = None) -> None:
        wrapper_execute(self, super().execute, query, vars)

    def executemany(self, query: Query, vars: Iterable[Params]) -> None:  # nocoverage
        wrapper_execute(self, super().executemany, query, vars)


CursorT = TypeVar("CursorT", bound=cursor)


class TimeTrackingConnection(connection):
    """A psycopg2 connection class that uses TimeTrackingCursors."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.queries: List[Dict[str, str]] = []
        super().__init__(*args, **kwargs)


def reset_queries() -> None:
    from django.db import connections

    for conn in connections.all():
        if conn.connection is not None:
            conn.connection.queries = []
