from functools import wraps
from typing import Any, Callable, Dict, Mapping, Set, Tuple, Union, cast

from django.http import HttpRequest, HttpResponse
from django.urls import path
from django.urls.resolvers import URLPattern
from django.utils.cache import add_never_cache_headers
from django.views.decorators.csrf import csrf_exempt, csrf_protect

from zerver.decorator import (
    authenticated_json_view,
    authenticated_rest_api_view,
    authenticated_uploads_api_view,
    process_as_post,
)
from zerver.lib.exceptions import MissingAuthenticationError
from zerver.lib.response import json_method_not_allowed
from zerver.lib.types import ViewFuncT

METHODS = ('GET', 'HEAD', 'POST', 'PUT', 'DELETE', 'PATCH')
FLAGS = ('override_api_url_scheme')

def default_never_cache_responses(view_func: ViewFuncT) -> ViewFuncT:
    """Patched version of the standard Django never_cache_responses
    decorator that adds headers to a response so that it will never be
    cached, unless the view code has already set a Cache-Control
    header.
    """
    @wraps(view_func)
    def _wrapped_view_func(request: HttpRequest, *args: object, **kwargs: object) -> HttpResponse:
        response = view_func(request, *args, **kwargs)
        if response.has_header("Cache-Control"):
            return response

        add_never_cache_headers(response)
        return response
    return cast(ViewFuncT, _wrapped_view_func)  # https://github.com/python/mypy/issues/1927

@default_never_cache_responses
@csrf_exempt
def rest_dispatch(request: HttpRequest, **kwargs: Any) -> HttpResponse:
    """Dispatch to a REST API endpoint.

    Unauthenticated endpoints should not use this, as authentication is verified
    in the following ways:
        * for paths beginning with /api, HTTP basic auth
        * for paths beginning with /json (used by the web client), the session token

    This calls the function named in kwargs[request.method], if that request
    method is supported, and after wrapping that function to:

        * protect against CSRF (if the user is already authenticated through
          a Django session)
        * authenticate via an API key (otherwise)
        * coerce PUT/PATCH/DELETE into having POST-like semantics for
          retrieving variables

    Any keyword args that are *not* HTTP methods are passed through to the
    target function.

    Never make a urls.py pattern put user input into a variable called GET, POST,
    etc, as that is where we route HTTP verbs to target functions.
    """
    supported_methods: Dict[str, Any] = {}

    if hasattr(request, "saved_response"):
        # For completing long-polled Tornado requests, we skip the
        # view function logic and just return the response.
        return request.saved_response

    # duplicate kwargs so we can mutate the original as we go
    for arg in list(kwargs):
        if arg in METHODS:
            supported_methods[arg] = kwargs[arg]
            del kwargs[arg]

    if 'GET' in supported_methods:
        supported_methods.setdefault('HEAD', supported_methods['GET'])

    if request.method == 'OPTIONS':
        response = HttpResponse(status=204)  # No content
        response['Allow'] = ', '.join(sorted(supported_methods.keys()))
        return response

    # Override requested method if magic method=??? parameter exists
    method_to_use = request.method
    if request.POST and 'method' in request.POST:
        method_to_use = request.POST['method']

    if method_to_use in supported_methods:
        entry = supported_methods[method_to_use]
        if isinstance(entry, tuple):
            target_function, view_flags = entry
        else:
            target_function = supported_methods[method_to_use]
            view_flags = set()

        # Set request._query for update_activity_user(), which is called
        # by some of the later wrappers.
        request._query = target_function.__name__

        # We want to support authentication by both cookies (web client)
        # and API keys (API clients). In the former case, we want to
        # do a check to ensure that CSRF etc is honored, but in the latter
        # we can skip all of that.
        #
        # Security implications of this portion of the code are minimal,
        # as we should worst-case fail closed if we miscategorise a request.

        # for some special views (e.g. serving a file that has been
        # uploaded), we support using the same URL for web and API clients.
        if ('override_api_url_scheme' in view_flags and
                request.META.get('HTTP_AUTHORIZATION', None) is not None):
            # This request uses standard API based authentication.
            # For override_api_url_scheme views, we skip our normal
            # rate limiting, because there are good reasons clients
            # might need to (e.g.) request a large number of uploaded
            # files or avatars in quick succession.
            target_function = authenticated_rest_api_view(skip_rate_limiting=True)(target_function)
        elif ('override_api_url_scheme' in view_flags and
              request.GET.get('api_key') is not None):
            # This request uses legacy API authentication.  We
            # unfortunately need that in the React Native mobile apps,
            # because there's no way to set HTTP_AUTHORIZATION in
            # React Native.  See last block for rate limiting notes.
            target_function = authenticated_uploads_api_view(skip_rate_limiting=True)(target_function)
        # /json views (web client) validate with a session token (cookie)
        elif not request.path.startswith("/api") and request.user.is_authenticated:
            # Authenticated via sessions framework, only CSRF check needed
            auth_kwargs = {}
            if 'override_api_url_scheme' in view_flags:
                auth_kwargs["skip_rate_limiting"] = True
            target_function = csrf_protect(authenticated_json_view(target_function, **auth_kwargs))

        # most clients (mobile, bots, etc) use HTTP basic auth and REST calls, where instead of
        # username:password, we use email:apiKey
        elif request.META.get('HTTP_AUTHORIZATION', None):
            # Wrap function with decorator to authenticate the user before
            # proceeding
            target_function = authenticated_rest_api_view(
                allow_webhook_access='allow_incoming_webhooks' in view_flags,
            )(target_function)
        elif request.path.startswith("/json") and 'allow_anonymous_user_web' in view_flags:
            # For endpoints that support anonymous web access, we do that.
            # TODO: Allow /api calls when this is stable enough.
            auth_kwargs = dict(allow_unauthenticated=True)
            target_function = csrf_protect(authenticated_json_view(
                target_function, **auth_kwargs))
        else:
            # Otherwise, throw an authentication error; our middleware
            # will generate the appropriate HTTP response.
            raise MissingAuthenticationError()

        if request.method not in ["GET", "POST"]:
            # process_as_post needs to be the outer decorator, because
            # otherwise we might access and thus cache a value for
            # request.REQUEST.
            target_function = process_as_post(target_function)

        return target_function(request, **kwargs)

    return json_method_not_allowed(list(supported_methods.keys()))

def rest_path(
    route: str,
    kwargs: Mapping[str, object] = {},
    **handlers: Union[Callable[..., HttpResponse], Tuple[Callable[..., HttpResponse], Set[str]]],
) -> URLPattern:
    return path(route, rest_dispatch, {**kwargs, **handlers})
