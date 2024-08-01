from django.contrib.sessions.backends.cached_db import SessionStore as CachedDbSessionStore
from django.db.transaction import get_connection
from typing_extensions import override


class SessionStore(CachedDbSessionStore):
    """Caching session object which does not leak into the cache.

    django.contrib.sessions.backends.cached_db does write-through to
    the cache and the backing database.  If the database is in a
    transaction, this may leak not-yet-committed changes to the cache,
    which can lead to inconsistent state.  This class wraps changes to
    the session in assertions which enforce that the database cannot
    be in a transaction before writing.

    """

    @override
    def save(self, must_create: bool = False) -> None:
        assert not get_connection().in_atomic_block
        super().save(must_create)

    @override
    def delete(self, session_key: str | None = None) -> None:
        assert not get_connection().in_atomic_block
        super().delete(session_key)
