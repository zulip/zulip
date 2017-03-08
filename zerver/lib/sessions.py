from __future__ import absolute_import

import logging

from django.conf import settings
from django.contrib.auth import SESSION_KEY, get_user_model
from django.contrib.sessions.models import Session
from django.utils import timezone
from importlib import import_module
from typing import List, Mapping, Optional, Text

from zerver.models import Realm, UserProfile, get_user_profile_by_id

session_engine = import_module(settings.SESSION_ENGINE)

def get_session_dict_user(session_dict):
    # type: (Mapping[Text, int]) -> Optional[int]
    # Compare django.contrib.auth._get_user_session_key
    try:
        return get_user_model()._meta.pk.to_python(session_dict[SESSION_KEY])
    except KeyError:
        return None

def get_session_user(session):
    # type: (Session) -> int
    return get_session_dict_user(session.get_decoded())

def user_sessions(user_profile):
    # type: (UserProfile) -> List[Session]
    return [s for s in Session.objects.all()
            if get_session_user(s) == user_profile.id]

def delete_session(session):
    # type: (Session) -> None
    session_engine.SessionStore(session.session_key).delete() # type: ignore # import_module

def delete_user_sessions(user_profile):
    # type: (UserProfile) -> None
    for session in Session.objects.all():
        if get_session_user(session) == user_profile.id:
            delete_session(session)

def delete_realm_user_sessions(realm):
    # type: (Realm) -> None
    realm_user_ids = [user_profile.id for user_profile in
                      UserProfile.objects.filter(realm=realm)]
    for session in Session.objects.filter(expire_date__gte=timezone.now()):
        if get_session_user(session) in realm_user_ids:
            delete_session(session)

def delete_all_user_sessions():
    # type: () -> None
    for session in Session.objects.all():
        delete_session(session)

def delete_all_deactivated_user_sessions():
    # type: () -> None
    for session in Session.objects.all():
        user_profile_id = get_session_user(session)
        if user_profile_id is None:
            continue
        user_profile = get_user_profile_by_id(user_profile_id)
        if not user_profile.is_active or user_profile.realm.deactivated:
            logging.info("Deactivating session for deactivated user %s" % (user_profile.email,))
            delete_session(session)
