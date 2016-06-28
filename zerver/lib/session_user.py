from __future__ import absolute_import

from django.contrib.auth import SESSION_KEY, get_user_model
from django.contrib.sessions.models import Session

from typing import Mapping, Optional
from six import text_type


def get_session_dict_user(session_dict):
    # type: (Mapping[text_type, int]) -> Optional[int]
    # Compare django.contrib.auth._get_user_session_key
    try:
        return get_user_model()._meta.pk.to_python(session_dict[SESSION_KEY])
    except KeyError:
        return None

def get_session_user(session):
    # type: (Session) -> int
    return get_session_dict_user(session.get_decoded())
