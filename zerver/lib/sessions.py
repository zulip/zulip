import logging
from collections.abc import Mapping
from datetime import timedelta
from importlib import import_module
from typing import Any, Protocol, cast

from django.conf import settings
from django.contrib.auth import SESSION_KEY, get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.backends.base import SessionBase
from django.contrib.sessions.models import Session
from django.http import HttpRequest
from django.utils.functional import LazyObject
from django.utils.timezone import now as timezone_now

from zerver.lib.request import RequestNotes
from zerver.lib.timestamp import datetime_to_timestamp, timestamp_to_datetime
from zerver.models import Realm, UserProfile
from zerver.models.users import get_user_profile_narrow_by_id


class SessionEngine(Protocol):
    SessionStore: type[SessionBase]


session_engine = cast(SessionEngine, import_module(settings.SESSION_ENGINE))


def get_session_dict_user(session_dict: Mapping[str, int]) -> int | None:
    # Compare django.contrib.auth._get_user_session_key
    try:
        pk = get_user_model()._meta.pk
        assert pk is not None
        return pk.to_python(session_dict[SESSION_KEY])
    except KeyError:
        return None


def get_session_user_id(session: Session) -> int | None:
    return get_session_dict_user(session.get_decoded())


def user_sessions(user_profile: UserProfile) -> list[Session]:
    return [s for s in Session.objects.all() if get_session_user_id(s) == user_profile.id]


def delete_session(session: Session) -> None:
    session_engine.SessionStore(session.session_key).delete()


def delete_user_sessions(user_profile: UserProfile) -> None:
    for session in Session.objects.all():
        if get_session_user_id(session) == user_profile.id:
            delete_session(session)


def delete_realm_user_sessions(realm: Realm) -> None:
    realm_user_ids = set(UserProfile.objects.filter(realm=realm).values_list("id", flat=True))
    for session in Session.objects.all():
        if get_session_user_id(session) in realm_user_ids:
            delete_session(session)


def delete_all_user_sessions() -> None:
    for session in Session.objects.all():
        delete_session(session)


def delete_all_deactivated_user_sessions() -> None:
    for session in Session.objects.all():
        user_profile_id = get_session_user_id(session)
        if user_profile_id is None:  # nocoverage  # TODO: Investigate why we lost coverage on this
            continue
        user_profile = get_user_profile_narrow_by_id(user_profile_id)
        if not user_profile.is_active or user_profile.realm.deactivated:
            logging.info("Deactivating session for deactivated user %s", user_profile.id)
            delete_session(session)


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


def narrow_request_user(
    request: HttpRequest, *, user_id: int | None = None
) -> UserProfile | AnonymousUser:
    # In Tornado and other performance-critical paths, we want to not
    # load the extremely wide default UserProfile select_related.  We
    # respect the request.user if it has been explicitly set already,
    # and otherwise perform a cached lookup of a much narrower view of
    # the UserProfile; this is faster than the normal UserProfile both
    # for cache misses (1.8ms vs 15ms) and cache hits (147μs vs
    # 387μs).  We fill the requester_for_logs to skip a session and
    # user memcached fetch when writing the log lines.
    if not isinstance(request.user, LazyObject):
        return request.user  # nocoverage

    if user_id is None:
        user_id = get_session_dict_user(request.session)
    if user_id is None:
        return AnonymousUser()  # nocoverage

    try:
        request.user = get_user_profile_narrow_by_id(user_id)
        RequestNotes.get_notes(
            request
        ).requester_for_logs = request.user.format_requester_for_logs()
    except UserProfile.DoesNotExist:  # nocoverage
        request.user = AnonymousUser()

    return request.user
