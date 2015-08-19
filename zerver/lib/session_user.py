from __future__ import absolute_import

from django.contrib.auth import SESSION_KEY, get_user_model

def get_session_dict_user(session_dict):
    # Compare django.contrib.auth._get_user_session_key
    try:
        return get_user_model()._meta.pk.to_python(session_dict[SESSION_KEY])
    except KeyError:
        return None

def get_session_user(session):
    return get_session_dict_user(session.get_decoded())
