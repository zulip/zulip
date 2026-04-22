from collections.abc import Iterator
from contextlib import contextmanager

import sqlalchemy
from django.db import connections
from sqlalchemy.engine import Connection, Engine
from typing_extensions import override

from zerver.lib.db import TimeTrackingConnection
from zerver.lib.db_replica import DEFAULT_DB_ALIAS, active_replica_alias


# This is a Pool that doesn't close connections.  Therefore it can be used with
# existing Django database connections.
class NonClosingPool(sqlalchemy.pool.NullPool):
    @override
    def status(self) -> str:
        return "NonClosingPool"

    def _do_return_conn(self, conn: sqlalchemy.engine.base.Connection) -> None:
        pass


# One SQLAlchemy engine per Django DB alias we touch from the query
# layer; engines are cheap to hold open and we only create the ones we
# actually use.
sqlalchemy_engines: dict[str, Engine] = {}


def _get_engine(alias: str) -> Engine:
    if alias not in sqlalchemy_engines:
        # Resolve the Django DatabaseWrapper inside the creator, not at
        # engine-creation time: django.db.connections[alias] is
        # thread-local, so capturing it in a closure would pin every
        # worker thread to the creating thread's wrapper.
        def get_dj_conn() -> TimeTrackingConnection:
            django_conn = connections[alias]
            django_conn.ensure_connection()
            return django_conn.connection

        sqlalchemy_engines[alias] = sqlalchemy.create_engine(
            "postgresql://",
            creator=get_dj_conn,
            poolclass=NonClosingPool,
            pool_reset_on_return=None,
        )
    return sqlalchemy_engines[alias]


@contextmanager
def get_sqlalchemy_connection() -> Iterator[Connection]:
    alias = active_replica_alias() or DEFAULT_DB_ALIAS
    engine = _get_engine(alias)
    with engine.connect().execution_options(autocommit=False) as sa_connection:
        yield sa_connection
