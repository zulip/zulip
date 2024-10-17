from django.contrib.sessions.backends.db import SessionStore as DbSessionStore
from typing_extensions import override

from zerver.models import RealmSession
from zerver.models.sessions import create_realm_session_instance


# Used in tests.
class SessionStore(DbSessionStore):
    @classmethod
    @override
    def get_model_class(cls) -> type[RealmSession]:
        return RealmSession

    @override
    def create_model_instance(self, data: dict[str, int | str]) -> RealmSession:
        session_object: RealmSession = super().create_model_instance(data)  # type: ignore[assignment] # https://github.com/typeddjango/django-stubs/issues/2056
        return create_realm_session_instance(session_object, data)
