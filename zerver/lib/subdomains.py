# -*- coding: utf-8 -*-

from django.conf import settings
from django.http import HttpRequest
from typing import Optional, Text

from zerver.models import get_realm, Realm, UserProfile

def _extract_subdomain(request):
    # type: (HttpRequest) -> Text
    domain = request.get_host().lower()
    index = domain.find("." + settings.EXTERNAL_HOST)
    if index == -1:
        return Realm.SUBDOMAIN_FOR_ROOT_DOMAIN
    return domain[0:index]

def get_subdomain(request):
    # type: (HttpRequest) -> Text
    subdomain = _extract_subdomain(request)
    if subdomain in settings.ROOT_SUBDOMAIN_ALIASES:
        return Realm.SUBDOMAIN_FOR_ROOT_DOMAIN
    return subdomain

def is_subdomain_root_or_alias(request):
    # type: (HttpRequest) -> bool
    subdomain = _extract_subdomain(request)
    return (subdomain == Realm.SUBDOMAIN_FOR_ROOT_DOMAIN
            or subdomain in settings.ROOT_SUBDOMAIN_ALIASES)

def user_matches_subdomain(realm_subdomain, user_profile):
    # type: (Optional[Text], UserProfile) -> bool
    if realm_subdomain is None:
        return True
    return user_profile.realm.subdomain == realm_subdomain

def is_root_domain_available():
    # type: () -> bool
    if settings.ROOT_DOMAIN_LANDING_PAGE:
        return False
    return get_realm(Realm.SUBDOMAIN_FOR_ROOT_DOMAIN) is None
