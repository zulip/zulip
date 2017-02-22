from django.db import connection
from django.db.backends import utils
from django.db.backends.postgresql import base
from django.db.backends.postgresql.features import DatabaseFeatures

from zerver.lib import sqlalchemy_utils
from zproject.db.backends.sqlalchemy.operations import DatabaseOperations

import sqlalchemy

if False:
    from typing import Optional, Dict, Any, Tuple, List
    from sqlalchemy.engine.result import ResultProxy
    from sqlalchemy.dialects.postgresql.psycopg2 import PGDialect_psycopg2
    import psycopg2.extensions.connection

sqlalchemy_engine = None

class CursorWrapper(utils.CursorWrapper):
    """
    The class is needed so that we can pass arguments to SQLAlchemy.
    In Django, execute function takes two arguments, sql and params
    while in SQLAlchemy, execute function takes three arguments, sql,
    *multiparams and **params. This wrapper allows us to pass these
    arguments in params argument of Django.
    """
    def execute(self, sql, params=None):
        # type: (Any, Optional[Dict[str, Any]]) -> ResultProxy
        multiparams, params = self.db.extract_sqlalchemy_params(params)
        return self.cursor.execute(sql, *multiparams, **params)

    @property
    def dialect(self):
        # type: () -> PGDialect_psycopg2
        return self.cursor.dialect


# This is a Pool that doesn't close connections.  Therefore it can be used with
# existing Django database connections.
class NonClosingPool(sqlalchemy.pool.NullPool):
    def status(self):
        # type: () -> str
        return "NonClosingPool"

    def _do_return_conn(self, conn):
        # type: (sqlalchemy.engine.base.Connection) -> None
        pass

    def recreate(self):
        # type: () -> NonClosingPool
        return self.__class__(creator=self._creator,
                              recycle=self._recycle,
                              use_threadlocal=self._use_threadlocal,
                              reset_on_return=self._reset_on_return,
                              echo=self.echo,
                              logging_name=self._orig_logging_name,
                              _dispatch=self.dispatch)

class DatabaseWrapper(base.DatabaseWrapper):
    def __init__(self, *args, **kwargs):
        # type: (*Any, **Any) -> None
        super(DatabaseWrapper, self).__init__(*args, **kwargs)
        self.ops = DatabaseOperations(self)
        # Always log queries and track times.
        self.force_debug_cursor = True

    def init_connection_state(self):
        # type: () -> None
        pass

    def get_connection_params(self):
        # type: () -> None
        pass

    def get_new_connection(self, *args, **kwargs):
        # type: (*Any, **Any) -> sqlalchemy.engine.base.Connection
        global sqlalchemy_engine
        if sqlalchemy_engine is None:
            def get_django_connection():
                # type: () -> psycopg2.extensions.connection
                connection.ensure_connection()
                return connection.connection

            sqlalchemy_engine = sqlalchemy.create_engine(
                'postgresql://',
                creator=get_django_connection,
                poolclass=NonClosingPool,
                pool_reset_on_return=False,
            )
        sa_connection = sqlalchemy_engine.connect()
        sa_connection.execution_options(autocommit=self.autocommit)
        return sa_connection

    def create_cursor(self):
        # type: () -> sqlalchemy.engine.base.Connection
        return CursorWrapper(self.connection, self)

    def set_autocommit(self, autocommit):
        # type: (bool) -> None
        self.autocommit = autocommit

    def extract_sqlalchemy_params(self, params):
        # type: (Dict[str, Any]) -> Tuple[List, Dict]
        if params is None:
            params = {}
        multiparams = params.pop('multiparams', [])
        params = params.pop('params', {})
        return multiparams, params
