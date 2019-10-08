# -*- coding: utf-8 -*-

from django.conf import settings
from django.http import HttpRequest
import re
from typing import Optional

from zerver.models import get_realm, Realm, UserProfile

def get_subdomain(request: HttpRequest) -> str:

    # The HTTP spec allows, but doesn't require, a client to omit the
    # port in the `Host` header if it's "the default port for the
    # service requested", i.e. typically either 443 or 80; and
    # whatever Django gets there, or from proxies reporting that via
    # X-Forwarded-Host, it passes right through the same way.  So our
    # logic is a bit complicated to allow for that variation.
    #
    # For both EXTERNAL_HOST and REALM_HOSTS, we take a missing port
    # to mean that any port should be accepted in Host.  It's not
    # totally clear that's the right behavior, but it keeps
    # compatibility with older versions of Zulip, so that's a start.

    host = request.get_host().lower()

    m = re.search(r'\.%s(:\d+)?$' % (settings.EXTERNAL_HOST,),
                  host)
    if m:
        subdomain = host[:m.start()]
        if subdomain in settings.ROOT_SUBDOMAIN_ALIASES:
            return Realm.SUBDOMAIN_FOR_ROOT_DOMAIN
        return subdomain

    for subdomain, realm_host in settings.REALM_HOSTS.items():
        if re.search(r'^%s(:\d+)?$' % (realm_host,),
                     host):
            return subdomain

    return Realm.SUBDOMAIN_FOR_ROOT_DOMAIN

def is_subdomain_root_or_alias(request: HttpRequest) -> bool:
    return get_subdomain(request) == Realm.SUBDOMAIN_FOR_ROOT_DOMAIN

def user_matches_subdomain(realm_subdomain: Optional[str], user_profile: UserProfile) -> bool:
    if realm_subdomain is None:
        return True  # nocoverage # This state may no longer be possible.
    return user_profile.realm.subdomain == realm_subdomain

def is_root_domain_available() -> bool:
    if settings.ROOT_DOMAIN_LANDING_PAGE:
        return False
    return get_realm(Realm.SUBDOMAIN_FOR_ROOT_DOMAIN) is None
