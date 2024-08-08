# https://github.com/typeddjango/django-stubs/issues/1698
# mypy: disable-error-code="explicit-override"

from django.conf import settings
from django.contrib.sessions.backends.cached_db import SessionStore as CachedDbSessionStore
from django.contrib.sessions.base_session import AbstractBaseSession
from django.db import models
from django.db.models.signals import post_delete, pre_save
from django.db.transaction import get_connection
from django.dispatch import receiver
from typing_extensions import override

from zerver.models.realms import Realm
from zerver.models.users import UserProfile


# custom session model
class RealmSession(AbstractBaseSession):
    realm = models.ForeignKey(Realm, null=True, on_delete=models.CASCADE)
    user = models.ForeignKey(UserProfile, null=True, on_delete=models.CASCADE)
    ip_address = models.GenericIPAddressField(null=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=("realm", "user"), name="zerver_realmsession_realm_user_idx"),
        ]

    @classmethod
    @override
    def get_session_store_class(cls) -> type["SessionStore"]:  # nocoverage
        # only called during initialization and not later.
        return SessionStore


@receiver(pre_save, sender=RealmSession)
def set_realm(*, instance: RealmSession, **kwargs: object) -> None:
    if instance.user is not None:
        instance.realm_id = instance.user.realm_id


@receiver(post_delete, sender=RealmSession)
def delete_cached_session(*, instance: RealmSession, **kwargs: object) -> None:  # nocoverage
    # session caching is disabled during tests
    if not settings.TEST_SUITE:
        SessionStore(instance.session_key).delete_cached_session()


# Abstract class is not used directly, so no test coverage.
class LeaklessCachedDbSessionStore(CachedDbSessionStore):  # nocoverage
    """Caching session object which does not leak into the cache.

    django.contrib.sessions.backends.cached_db does write-through to
    the cache and the backing database.  If the database is in a
    transaction, this may leak not-yet-committed changes to the cache,
    which can lead to inconsistent state.  This class wraps changes to
    the session in assertions which enforce that the database cannot
    be in a transaction before writing.

    """

    class Meta:
        abstract = True

    @override
    def save(self, must_create: bool = False) -> None:
        assert not get_connection().in_atomic_block
        super().save(must_create=must_create)

    @override
    def delete(self, session_key: str | None = None) -> None:
        assert not get_connection().in_atomic_block
        super().delete(session_key)


def create_realm_session_instance(
    session_object: RealmSession, session_data: dict[str, int | str]
) -> RealmSession:
    # We always save realm_id in session_data as int.
    realm_id = session_data.get("realm_id")

    if "_auth_user_id" in session_data:
        user_id = int(session_data["_auth_user_id"])
    else:
        user_id = None

    ip_address = session_data.get("ip_address")

    session_object.realm_id = realm_id
    session_object.user_id = user_id
    session_object.ip_address = ip_address

    return session_object


# This SessionsStore is not used in tests,
# its non-cached version 'zerver/models/nocache_sessions.SessionStore' is the one used instead,
# Those class functions are tested in zerver/tests/test_sessions.py
class SessionStore(LeaklessCachedDbSessionStore):  # nocoverage
    cache_key_prefix = "sessions.realm_session_store"

    @classmethod
    @override
    def get_model_class(cls) -> type[RealmSession]:
        return RealmSession

    @override
    def create_model_instance(self, data: dict[str, int | str]) -> RealmSession:
        session_object: RealmSession = super().create_model_instance(data)  # type: ignore[assignment] # https://github.com/typeddjango/django-stubs/issues/2056
        return create_realm_session_instance(session_object, data)

    # similar to super().delete(session_key) but only deletes cached session without touching database.
    def delete_cached_session(self, session_key: str | None = None) -> None:
        if session_key is None:
            if self.session_key is None:
                return
            session_key = self.session_key
        self._cache.delete(self.cache_key_prefix + session_key)  # type: ignore[attr-defined] # not in stubs


# export by default, tells settings.SESSION_ENGINE to use the right sessionstore class.
__all__ = ["SessionStore"]
