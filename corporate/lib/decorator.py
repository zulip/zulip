from functools import wraps
from typing import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from typing_extensions import Concatenate, ParamSpec

from corporate.lib.remote_billing_util import (
    get_remote_realm_from_session,
    get_remote_server_from_session,
)
from zerver.lib.subdomains import get_subdomain
from zilencer.models import RemoteRealm, RemoteZulipServer

ParamT = ParamSpec("ParamT")


def is_self_hosting_management_subdomain(request: HttpRequest) -> bool:  # nocoverage
    subdomain = get_subdomain(request)
    return settings.DEVELOPMENT and subdomain == settings.SELF_HOSTING_MANAGEMENT_SUBDOMAIN


def self_hosting_management_endpoint(
    view_func: Callable[Concatenate[HttpRequest, ParamT], HttpResponse]
) -> Callable[Concatenate[HttpRequest, ParamT], HttpResponse]:  # nocoverage
    @wraps(view_func)
    def _wrapped_view_func(
        request: HttpRequest, /, *args: ParamT.args, **kwargs: ParamT.kwargs
    ) -> HttpResponse:
        if not is_self_hosting_management_subdomain(request):
            return render(request, "404.html", status=404)
        return view_func(request, *args, **kwargs)

    return _wrapped_view_func


def authenticated_remote_realm_management_endpoint(
    view_func: Callable[Concatenate[HttpRequest, RemoteRealm, ParamT], HttpResponse]
) -> Callable[Concatenate[HttpRequest, ParamT], HttpResponse]:  # nocoverage
    @wraps(view_func)
    def _wrapped_view_func(
        request: HttpRequest,
        /,
        *args: ParamT.args,
        **kwargs: ParamT.kwargs,
    ) -> HttpResponse:
        if not is_self_hosting_management_subdomain(request):
            return render(request, "404.html", status=404)

        realm_uuid = kwargs.get("realm_uuid")
        server_uuid = kwargs.get("server_uuid")
        if realm_uuid is not None and not isinstance(realm_uuid, str):
            raise TypeError("realm_uuid must be a string or None")
        if server_uuid is not None and not isinstance(server_uuid, str):
            raise TypeError("server_uuid must be a string or None")
        remote_realm = get_remote_realm_from_session(
            request, realm_uuid=realm_uuid, server_uuid=server_uuid
        )
        return view_func(request, remote_realm, *args, **kwargs)

    return _wrapped_view_func


def authenticated_remote_server_management_endpoint(
    view_func: Callable[Concatenate[HttpRequest, RemoteZulipServer, ParamT], HttpResponse]
) -> Callable[Concatenate[HttpRequest, ParamT], HttpResponse]:  # nocoverage
    @wraps(view_func)
    def _wrapped_view_func(
        request: HttpRequest,
        /,
        *args: ParamT.args,
        **kwargs: ParamT.kwargs,
    ) -> HttpResponse:
        if not is_self_hosting_management_subdomain(request):
            return render(request, "404.html", status=404)

        server_uuid = kwargs.get("server_uuid")
        if not isinstance(server_uuid, str):
            raise TypeError("server_uuid must be a string")

        remote_server = get_remote_server_from_session(request, server_uuid=server_uuid)
        return view_func(request, remote_server, *args, **kwargs)

    return _wrapped_view_func
