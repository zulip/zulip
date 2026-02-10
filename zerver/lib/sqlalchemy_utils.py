from collections.abc import Iterator
from contextlib import contextmanager

import sqlalchemy
from django.db import connection
from sqlalchemy.engine import Connection, Engine
from typing_extensions import override

from zerver.lib.db import TimeTrackingConnection


# This is a Pool that doesn't close connections.  Therefore it can be used with
# existing Django database connections.
class NonClosingPool(sqlalchemy.pool.NullPool):
    @override
    def status(self) -> str:
        return "NonClosingPool"

    def _do_return_conn(self, conn: sqlalchemy.engine.base.Connection) -> None:
        pass


sqlalchemy_engine: Engine | None = None


@contextmanager
def get_sqlalchemy_connection() -> Iterator[Connection]:
    global sqlalchemy_engine
    if sqlalchemy_engine is None:

        def get_dj_conn() -> TimeTrackingConnection:
            connection.ensure_connection()
            return connection.connection

        sqlalchemy_engine = sqlalchemy.create_engine(
            "postgresql://",
            creator=get_dj_conn,
            poolclass=NonClosingPool,
            pool_reset_on_return=None,
        )
    with sqlalchemy_engine.connect().execution_options(autocommit=False) as sa_connection:
        yield sa_connection
