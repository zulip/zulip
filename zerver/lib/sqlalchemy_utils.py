from typing import Any, Optional

import sqlalchemy
from django.db import connection

from zerver.lib.db import TimeTrackingConnection


# This is a Pool that doesn't close connections.  Therefore it can be used with
# existing Django database connections.
class NonClosingPool(sqlalchemy.pool.NullPool):
    def status(self) -> str:
        return "NonClosingPool"

    def _do_return_conn(self, conn: sqlalchemy.engine.base.Connection) -> None:
        pass

    def recreate(self) -> 'NonClosingPool':
        return self.__class__(
            creator=self._creator,  # type: ignore[attr-defined] # implementation detail
            recycle=self._recycle,  # type: ignore[attr-defined] # implementation detail
            use_threadlocal=self._use_threadlocal,  # type: ignore[attr-defined] # implementation detail
            reset_on_return=self._reset_on_return,  # type: ignore[attr-defined] # implementation detail
            echo=self.echo,
            logging_name=self._orig_logging_name,  # type: ignore[attr-defined] # implementation detail
            _dispatch=self.dispatch,  # type: ignore[attr-defined] # implementation detail
        )

sqlalchemy_engine: Optional[Any] = None
def get_sqlalchemy_connection() -> sqlalchemy.engine.base.Connection:
    global sqlalchemy_engine
    if sqlalchemy_engine is None:
        def get_dj_conn() -> TimeTrackingConnection:
            connection.ensure_connection()
            return connection.connection
        sqlalchemy_engine = sqlalchemy.create_engine('postgresql://',
                                                     creator=get_dj_conn,
                                                     poolclass=NonClosingPool,
                                                     pool_reset_on_return=False)
    sa_connection = sqlalchemy_engine.connect()
    sa_connection.execution_options(autocommit=False)
    return sa_connection
