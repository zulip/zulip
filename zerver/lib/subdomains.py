# -*- coding: utf-8 -*-

from django.conf import settings
from django.http import HttpRequest
from typing import Optional, Text

from zerver.models import get_realm, Realm, UserProfile

def get_subdomain(request):
    # type: (HttpRequest) -> Text
    host = request.get_host().lower()
    index = host.find("." + settings.EXTERNAL_HOST)
    if index == -1:
        return Realm.SUBDOMAIN_FOR_ROOT_DOMAIN
    subdomain = host[0:index]
    if subdomain in settings.ROOT_SUBDOMAIN_ALIASES:
        return Realm.SUBDOMAIN_FOR_ROOT_DOMAIN
    return subdomain

def is_subdomain_root_or_alias(request):
    # type: (HttpRequest) -> bool
    return get_subdomain(request) == Realm.SUBDOMAIN_FOR_ROOT_DOMAIN

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
