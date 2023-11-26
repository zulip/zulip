from functools import wraps
from typing import Callable, TypeVar

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from typing_extensions import Concatenate, ParamSpec

from zerver.lib.subdomains import get_subdomain

ParamT = ParamSpec("ParamT")


def self_hosting_management_endpoint(
    view_func: Callable[Concatenate[HttpRequest, ParamT], HttpResponse]
) -> Callable[Concatenate[HttpRequest, ParamT], HttpResponse]:  # nocoverage
    @wraps(view_func)
    def _wrapped_view_func(
        request: HttpRequest, /, *args: ParamT.args, **kwargs: ParamT.kwargs
    ) -> HttpResponse:
        subdomain = get_subdomain(request)
        if not settings.DEVELOPMENT or subdomain != settings.SELF_HOSTING_MANAGEMENT_SUBDOMAIN:
            return render(request, "404.html", status=404)
        return view_func(request, *args, **kwargs)

    return _wrapped_view_func
