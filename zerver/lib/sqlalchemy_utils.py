from django.db import connection

import sqlalchemy

# This is a Pool that doesn't close connections.  Therefore it can be used with
# existing Django database connections.
class NonClosingPool(sqlalchemy.pool.NullPool):
    def status(self):
        return "NonClosingPool"

    def _do_return_conn(self, conn):
        pass

    def recreate(self):
        return self.__class__(creator=self._creator, # type: ignore # __class__
                              recycle=self._recycle,
                              use_threadlocal=self._use_threadlocal,
                              reset_on_return=self._reset_on_return,
                              echo=self.echo,
                              logging_name=self._orig_logging_name,
                              _dispatch=self.dispatch)

sqlalchemy_engine = None
def get_sqlalchemy_connection():
    global sqlalchemy_engine
    if sqlalchemy_engine is None:
        def get_dj_conn():
            connection.ensure_connection()
            return connection.connection
        sqlalchemy_engine = sqlalchemy.create_engine('postgresql://',
                                                     creator=get_dj_conn,
                                                     poolclass=NonClosingPool,
                                                     pool_reset_on_return=False)
    sa_connection = sqlalchemy_engine.connect()
    sa_connection.execution_options(autocommit=False)
    return sa_connection
