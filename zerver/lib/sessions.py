import logging
from collections.abc import Mapping
from datetime import timedelta
from importlib import import_module
from typing import Any, Protocol, cast

from django.conf import settings
from django.contrib.auth import SESSION_KEY, get_user_model
from django.contrib.sessions.backends.base import SessionBase
from django.db.models import Q
from django.http import HttpRequest
from django.utils.timezone import now as timezone_now

from zerver.lib.timestamp import datetime_to_timestamp, timestamp_to_datetime
from zerver.models import Realm, RealmSession, UserProfile


class SessionEngine(Protocol):
    SessionStore: type[SessionBase]


session_engine = cast(SessionEngine, import_module(settings.SESSION_ENGINE))


def save_session_fields(request: HttpRequest, realm: Realm) -> None:
    if not request.session.is_empty():
        request.session._session["ip_address"] = request.META["REMOTE_ADDR"]  # type: ignore[attr-defined] # attribute from the ancestor-class SessionBase.
        request.session._session["realm_id"] = realm.id  # type: ignore[attr-defined] # same as above.


def get_session_dict_user(session_dict: Mapping[str, int]) -> int | None:
    # Compare django.contrib.auth._get_user_session_key
    try:
        pk = get_user_model()._meta.pk
        assert pk is not None
        return pk.to_python(session_dict[SESSION_KEY])
    except KeyError:
        return None


# RealmSession instances have a post_delete signal which deletes cached sessions as well.


def delete_session(session: RealmSession) -> None:
    session_engine.SessionStore(session.session_key).delete()


def delete_user_sessions(user_profile: UserProfile) -> None:
    RealmSession.objects.filter(realm=user_profile.realm, user=user_profile).delete()


def delete_realm_sessions(realm: Realm) -> None:
    RealmSession.objects.filter(realm=realm).delete()


def delete_all_user_sessions() -> None:
    RealmSession.objects.all().delete()


def delete_all_deactivated_user_sessions() -> None:
    RealmSession.objects.filter(Q(user__is_active=False) | Q(realm__deactivated=True)).delete()


def set_expirable_session_var(
    session: SessionBase, var_name: str, var_value: Any, expiry_seconds: int
) -> None:
    expire_at = datetime_to_timestamp(timezone_now() + timedelta(seconds=expiry_seconds))
    session[var_name] = {"value": var_value, "expire_at": expire_at}


def get_expirable_session_var(
    session: SessionBase, var_name: str, default_value: Any = None, delete: bool = False
) -> Any:
    if var_name not in session:
        return default_value

    try:
        value, expire_at = (session[var_name]["value"], session[var_name]["expire_at"])
    except (KeyError, TypeError):
        logging.warning("get_expirable_session_var: error getting %s", var_name, exc_info=True)
        return default_value

    if timestamp_to_datetime(expire_at) < timezone_now():
        del session[var_name]
        return default_value

    if delete:
        del session[var_name]
    return value
