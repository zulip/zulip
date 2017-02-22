from django.db.backends.postgresql import base

if False:
    from typing import Any

class DatabaseWrapper(base.DatabaseWrapper):
    def __init__(self, *args, **kwargs):
        # type: (*Any, **Any) -> None
        super(DatabaseWrapper, self).__init__(*args, **kwargs)
        # Always log queries and track times.
        self.force_debug_cursor = True
