
import logging

from django.conf import settings
from django.contrib.auth import SESSION_KEY, get_user_model
from django.contrib.sessions.models import Session
from django.http import HttpRequest, HttpResponse
from django.utils.timezone import now as timezone_now
from importlib import import_module
from typing import List, Mapping, Optional

from zerver.models import Realm, UserProfile, get_user_profile_by_id
from zerver.lib.subdomains import is_subdomain_root_or_alias

session_engine = import_module(settings.SESSION_ENGINE)

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
    session_engine.SessionStore(session.session_key).delete()  # type: ignore # import_module

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
        if user_profile_id is None:
            continue
        user_profile = get_user_profile_by_id(user_profile_id)
        if not user_profile.is_active or user_profile.realm.deactivated:
            logging.info("Deactivating session for deactivated user %s" % (user_profile.email,))
            delete_session(session)

def maybe_remove_session_cookie_at_root_domain(request: HttpRequest,
                                               response: HttpResponse) -> HttpResponse:
    request_host = request.get_host().split(':')[0]
    root_session_cookie_domain = settings.EXTERNAL_HOST.split(":")[0]
    if (not is_subdomain_root_or_alias(request) and
            root_session_cookie_domain in request_host and
            root_session_cookie_domain != request_host):
        # We delete the sessionid cookie on the root domain only if it is a
        # multi realm server. We do this so that the cookie on root domain
        # does not mask the real session cookie set for this realm (which is
        # hosted on a subdomain) and leave users in endless login loops.
        # See issue https://github.com/zulip/zulip/issues/9940 for details.
        response.delete_cookie(settings.SESSION_COOKIE_NAME,
                               domain=root_session_cookie_domain)
    return response
