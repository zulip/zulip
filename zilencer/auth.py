import logging
from functools import wraps
from typing import Any, Callable

from django.http import HttpRequest, HttpResponse
from django.urls import path
from django.urls.resolvers import URLPattern
from django.utils.crypto import constant_time_compare
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt
from typing_extensions import Concatenate, ParamSpec

from zerver.decorator import get_basic_credentials, process_client
from zerver.lib.exceptions import (
    ErrorCode,
    JsonableError,
    RateLimitedError,
    RemoteServerDeactivatedError,
    UnauthorizedError,
)
from zerver.lib.rate_limiter import should_rate_limit
from zerver.lib.request import RequestNotes
from zerver.lib.rest import default_never_cache_responses, get_target_view_function_or_response
from zerver.lib.subdomains import get_subdomain
from zerver.models import Realm
from zilencer.models import (
    RateLimitedRemoteZulipServer,
    RemoteZulipServer,
    get_remote_server_by_uuid,
)

logger = logging.getLogger(__name__)

ParamT = ParamSpec("ParamT")


class InvalidZulipServerError(JsonableError):
    code = ErrorCode.INVALID_ZULIP_SERVER
    data_fields = ["role"]

    def __init__(self, role: str) -> None:
        self.role: str = role

    @staticmethod
    def msg_format() -> str:
        return "Zulip server auth failure: {role} is not registered -- did you run `manage.py register_server`?"


class InvalidZulipServerKeyError(InvalidZulipServerError):
    @staticmethod
    def msg_format() -> str:
        return "Zulip server auth failure: key does not match role {role}"


def rate_limit_remote_server(
    request: HttpRequest, remote_server: RemoteZulipServer, domain: str
) -> None:
    if not should_rate_limit(request):
        return

    try:
        RateLimitedRemoteZulipServer(remote_server, domain=domain).rate_limit_request(request)
    except RateLimitedError as e:
        logger.warning("Remote server %s exceeded rate limits on domain %s", remote_server, domain)
        raise e


def validate_remote_server(
    request: HttpRequest,
    role: str,
    api_key: str,
) -> RemoteZulipServer:
    try:
        remote_server = get_remote_server_by_uuid(role)
    except RemoteZulipServer.DoesNotExist:
        raise InvalidZulipServerError(role)
    if not constant_time_compare(api_key, remote_server.api_key):
        raise InvalidZulipServerKeyError(role)

    if remote_server.deactivated:
        raise RemoteServerDeactivatedError

    if get_subdomain(request) != Realm.SUBDOMAIN_FOR_ROOT_DOMAIN:
        raise JsonableError(_("Invalid subdomain for push notifications bouncer"))
    RequestNotes.get_notes(request).remote_server = remote_server
    process_client(request)
    return remote_server


def authenticated_remote_server_view(
    view_func: Callable[Concatenate[HttpRequest, RemoteZulipServer, ParamT], HttpResponse]
) -> Callable[Concatenate[HttpRequest, ParamT], HttpResponse]:
    @wraps(view_func)
    def _wrapped_view_func(
        request: HttpRequest, /, *args: ParamT.args, **kwargs: ParamT.kwargs
    ) -> HttpResponse:
        role, api_key = get_basic_credentials(request)
        if "@" in role:
            raise JsonableError(_("Must validate with valid Zulip server API key"))
        try:
            remote_server = validate_remote_server(request, role, api_key)
        except JsonableError as e:
            raise UnauthorizedError(e.msg)

        rate_limit_remote_server(request, remote_server, domain="api_by_remote_server")
        return view_func(request, remote_server, *args, **kwargs)

    return _wrapped_view_func


@default_never_cache_responses
@csrf_exempt
def remote_server_dispatch(request: HttpRequest, /, **kwargs: Any) -> HttpResponse:
    result = get_target_view_function_or_response(request, kwargs)
    if isinstance(result, HttpResponse):
        return result
    target_function, view_flags = result
    return authenticated_remote_server_view(target_function)(request, **kwargs)


def remote_server_path(
    route: str,
    **handlers: Callable[Concatenate[HttpRequest, RemoteZulipServer, ParamT], HttpResponse],
) -> URLPattern:
    return path(route, remote_server_dispatch, handlers)
