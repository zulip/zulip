from typing import Dict, Optional, Type, Union

from django.contrib.sessions.backends.cached_db import SessionStore as CachedDbSessionStore
from django.contrib.sessions.base_session import AbstractBaseSession
from django.db import models
from django.db.transaction import get_connection
from typing_extensions import override

from zerver.models.realms import Realm
from zerver.models.users import UserProfile


# custom session model
class RealmSession(AbstractBaseSession):  # type: ignore[explicit-override] # some called functions by this class like get_next_by_expire_date override the parent functions, but since we don't explictly use or define them we cannot use @override
    realm = models.ForeignKey(Realm, null=True, on_delete=models.CASCADE)
    user = models.ForeignKey(UserProfile, null=True, on_delete=models.CASCADE)
    ip_address = models.GenericIPAddressField(null=True)

    class Meta:
        (models.Index(fields=("realm", "user"), name="zerver_realmsession_realm_user_idx"),)

    @classmethod
    @override
    def get_session_store_class(cls) -> Type["RealmSessionStore"]:
        return RealmSessionStore


class LeaklessCachedDbSessionStore(CachedDbSessionStore):
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
    def delete(self, session_key: Optional[str] = None) -> None:
        assert not get_connection().in_atomic_block
        super().delete(session_key)


class RealmSessionStore(LeaklessCachedDbSessionStore):
    cache_key_prefix = "sessions.realm_session_store"

    @classmethod
    @override
    def get_model_class(cls) -> Type[RealmSession]:
        return RealmSession

    @override
    def create_model_instance(self, data: Dict[str, Union[int, str]]) -> RealmSession:
        obj = super().create_model_instance(data)
        assert isinstance(obj, RealmSession)

        if "realm_id" in data:
            realm_id = int(data["realm_id"])
        else:
            realm_id = None

        if "user_id" in data:
            user_id = int(data["user_id"])
        else:
            user_id = None

        ip_address = data.get("ip_address")

        obj.realm_id = realm_id
        obj.user_id = user_id
        obj.ip_address = ip_address

        return obj
