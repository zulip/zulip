from typing import Text, Any
from django.db.backends.base.operations import BaseDatabaseOperations

if False:
    from zproject.db.backends.sqlalchemy.base import CursorWrapper

class DatabaseOperations(BaseDatabaseOperations):

    def last_executed_query(self, cursor, sql, params):
        # type: (CursorWrapper, Any, Any) -> Text
        if isinstance(sql, Text):
            msg = ("We currently only support programmatically created SQL "
                   "for logging.")
            raise Exception(msg)

        compiled_query = sql.compile(dialect=cursor.dialect,
                                     compile_kwargs={'literal_binds': True})
        return compiled_query.string
