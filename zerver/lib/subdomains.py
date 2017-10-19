# -*- coding: utf-8 -*-

from django.conf import settings
from django.http import HttpRequest
from typing import Optional, Text

def _extract_subdomain(request):
    # type: (HttpRequest) -> Text
    domain = request.get_host().lower()
    index = domain.find("." + settings.EXTERNAL_HOST)
    if index == -1:
        return ""
    return domain[0:index]

def get_subdomain(request):
    # type: (HttpRequest) -> Text
    subdomain = _extract_subdomain(request)
    if subdomain in settings.ROOT_SUBDOMAIN_ALIASES:
        return ""
    return subdomain

def is_subdomain_root_or_alias(request):
    # type: (HttpRequest) -> bool
    subdomain = _extract_subdomain(request)
    return not subdomain or subdomain in settings.ROOT_SUBDOMAIN_ALIASES

def check_subdomain(realm_subdomain, user_subdomain):
    # type: (Optional[Text], Text) -> bool
    if realm_subdomain is not None:
        if realm_subdomain != user_subdomain:
            return False
    return True
