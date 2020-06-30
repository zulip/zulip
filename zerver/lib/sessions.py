import logging
from datetime import timedelta
from importlib import import_module
from typing import Any, List, Mapping, Optional, Type, cast

from django.conf import settings
from django.contrib.auth import SESSION_KEY, get_user_model
from django.contrib.sessions.backends.base import SessionBase
from django.contrib.sessions.models import Session
from django.utils.timezone import now as timezone_now
from typing_extensions import Protocol

from zerver.lib.timestamp import datetime_to_timestamp, timestamp_to_datetime
from zerver.models import Realm, UserProfile, get_user_profile_by_id


class SessionEngine(Protocol):
    SessionStore: Type[SessionBase]

session_engine = cast(SessionEngine, import_module(settings.SESSION_ENGINE))

def get_session_dict_user(session_dict: Mapping[str, int]) -> Optional[int]:
    # Compare django.contrib.auth._get_user_session_key
    try:
        return get_user_model()._meta.pk.to_python(session_dict[SESSION_KEY])
    except KeyError:
        return None

def get_session_user(session: Session) -> Optional[int]:
    return get_session_dict_user(session.get_decoded())

def user_sessions(user_profile: UserProfile) -> List[Session]:
    return [s for s in Session.objects.all()
            if get_session_user(s) == user_profile.id]

def delete_session(session: Session) -> None:
    session_engine.SessionStore(session.session_key).delete()

def delete_user_sessions(user_profile: UserProfile) -> None:
    for session in Session.objects.all():
        if get_session_user(session) == user_profile.id:
            delete_session(session)

def delete_realm_user_sessions(realm: Realm) -> None:
    realm_user_ids = [user_profile.id for user_profile in
                      UserProfile.objects.filter(realm=realm)]
    for session in Session.objects.filter(expire_date__gte=timezone_now()):
        if get_session_user(session) in realm_user_ids:
            delete_session(session)

def delete_all_user_sessions() -> None:
    for session in Session.objects.all():
        delete_session(session)

def delete_all_deactivated_user_sessions() -> None:
    for session in Session.objects.all():
        user_profile_id = get_session_user(session)
        if user_profile_id is None:  # nocoverage  # TODO: Investigate why we lost coverage on this
            continue
        user_profile = get_user_profile_by_id(user_profile_id)
        if not user_profile.is_active or user_profile.realm.deactivated:
            logging.info("Deactivating session for deactivated user %s", user_profile.id)
            delete_session(session)

def set_expirable_session_var(session: Session, var_name: str, var_value: Any, expiry_seconds: int) -> None:
    expire_at = datetime_to_timestamp(timezone_now() + timedelta(seconds=expiry_seconds))
    session[var_name] = {'value': var_value, 'expire_at': expire_at}

def get_expirable_session_var(session: Session, var_name: str, default_value: Any=None,
                              delete: bool=False) -> Any:
    if var_name not in session:
        return default_value

    try:
        value, expire_at = (session[var_name]['value'], session[var_name]['expire_at'])
    except (KeyError, TypeError):
        logging.warning("get_expirable_session_var: error getting %s", var_name, exc_info=True)
        return default_value

    if timestamp_to_datetime(expire_at) < timezone_now():
        del session[var_name]
        return default_value

    if delete:
        del session[var_name]
    return value
