from functools import wraps
from typing import Callable, Dict, Set, Tuple, Union

from django.http import HttpRequest, HttpResponse, HttpResponseBase
from django.urls import path
from django.urls.resolvers import URLPattern
from django.utils.cache import add_never_cache_headers
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from typing_extensions import Concatenate, ParamSpec

from zerver.decorator import (
    authenticated_json_view,
    authenticated_rest_api_view,
    authenticated_uploads_api_view,
    process_as_post,
    public_json_view,
)
from zerver.lib.exceptions import MissingAuthenticationError
from zerver.lib.request import RequestNotes
from zerver.lib.response import json_method_not_allowed

ParamT = ParamSpec("ParamT")
METHODS = ("GET", "HEAD", "POST", "PUT", "DELETE", "PATCH")


def default_never_cache_responses(
    view_func: Callable[Concatenate[HttpRequest, ParamT], HttpResponse]
) -> Callable[Concatenate[HttpRequest, ParamT], HttpResponse]:
    """Patched version of the standard Django never_cache_responses
    decorator that adds headers to a response so that it will never be
    cached, unless the view code has already set a Cache-Control
    header.
    """

    @wraps(view_func)
    def _wrapped_view_func(
        request: HttpRequest, /, *args: ParamT.args, **kwargs: ParamT.kwargs
    ) -> HttpResponse:
        response = view_func(request, *args, **kwargs)
        if response.has_header("Cache-Control"):
            return response

        add_never_cache_headers(response)
        return response

    return _wrapped_view_func


def get_target_view_function_or_response(
    request: HttpRequest, rest_dispatch_kwargs: Dict[str, object]
) -> Union[Tuple[Callable[..., HttpResponse], Set[str]], HttpResponse]:
    """Helper for REST API request dispatch. The rest_dispatch_kwargs
    parameter is expected to be a dictionary mapping HTTP methods to
    a mix of view functions and (view_function, {view_flags}) tuples.

    * Returns an error HttpResponse for unsupported HTTP methods.

    * Otherwise, returns a tuple containing the view function
      corresponding to the request's HTTP method, as well as the
      appropriate set of view flags.

    HACK: Mutates the passed rest_dispatch_kwargs, removing the HTTP
    method details but leaving any other parameters for the caller to
    pass directly to the view function. We should see if we can remove
    this feature; it's not clear it's actually used.

    """
    supported_methods: Dict[str, object] = {}
    request_notes = RequestNotes.get_notes(request)
    if request_notes.saved_response is not None:
        # For completing long-polled Tornado requests, we skip the
        # view function logic and just return the response.
        return request_notes.saved_response

    # The list() duplicates rest_dispatch_kwargs, since this loop
    # mutates the original.
    for arg in list(rest_dispatch_kwargs):
        if arg in METHODS:
            supported_methods[arg] = rest_dispatch_kwargs[arg]
            del rest_dispatch_kwargs[arg]

    if "GET" in supported_methods:
        supported_methods.setdefault("HEAD", supported_methods["GET"])

    if request.method == "OPTIONS":
        response = HttpResponse(status=204)  # No content
        response["Allow"] = ", ".join(sorted(supported_methods.keys()))
        return response

    # Override requested method if magic method=??? parameter exists
    method_to_use = request.method
    if request.POST and "method" in request.POST:
        method_to_use = request.POST["method"]

    if method_to_use in supported_methods:
        entry = supported_methods[method_to_use]
        if isinstance(entry, tuple):
            handler, view_flags = entry
            assert callable(handler)
            assert isinstance(view_flags, set)
            return handler, view_flags
        assert callable(entry)
        return entry, set()

    return json_method_not_allowed(list(supported_methods.keys()))


@default_never_cache_responses
@csrf_exempt
def rest_dispatch(request: HttpRequest, /, **kwargs: object) -> HttpResponse:
    """Dispatch to a REST API endpoint.

    Authentication is verified in the following ways:
        * for paths beginning with /api, HTTP basic auth
        * for paths beginning with /json (used by the web client), the session token

    Unauthenticated requests may use this endpoint only with the
    allow_anonymous_user_web view flag.

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
    result = get_target_view_function_or_response(request, kwargs)
    if isinstance(result, HttpResponse):
        return result
    target_function, view_flags = result
    request_notes = RequestNotes.get_notes(request)

    # Set request_notes.query for update_activity_user(), which is called
    # by some of the later wrappers.
    request_notes.query = target_function.__name__

    # We want to support authentication by both cookies (web client)
    # and API keys (API clients). In the former case, we want to
    # do a check to ensure that CSRF etc is honored, but in the latter
    # we can skip all of that.
    #
    # Security implications of this portion of the code are minimal,
    # as we should worst-case fail closed if we miscategorize a request.

    # for some special views (e.g. serving a file that has been
    # uploaded), we support using the same URL for web and API clients.
    if "override_api_url_scheme" in view_flags and "Authorization" in request.headers:
        # This request uses standard API based authentication.
        # For override_api_url_scheme views, we skip our normal
        # rate limiting, because there are good reasons clients
        # might need to (e.g.) request a large number of uploaded
        # files or avatars in quick succession.
        target_function = authenticated_rest_api_view(skip_rate_limiting=True)(target_function)
    elif "override_api_url_scheme" in view_flags and request.GET.get("api_key") is not None:
        # This request uses legacy API authentication.  We
        # unfortunately need that in the React Native mobile apps,
        # because there's no way to set the Authorization header in
        # React Native.  See last block for rate limiting notes.
        target_function = authenticated_uploads_api_view(skip_rate_limiting=True)(target_function)
    # /json views (web client) validate with a session token (cookie)
    elif not request.path.startswith("/api") and request.user.is_authenticated:
        # Authenticated via sessions framework, only CSRF check needed
        auth_kwargs = {}
        if "override_api_url_scheme" in view_flags:
            auth_kwargs["skip_rate_limiting"] = True
        target_function = csrf_protect(authenticated_json_view(target_function, **auth_kwargs))

    # most clients (mobile, bots, etc) use HTTP basic auth and REST calls, where instead of
    # username:password, we use email:apiKey
    elif request.path.startswith("/api") and "Authorization" in request.headers:
        # Wrap function with decorator to authenticate the user before
        # proceeding
        target_function = authenticated_rest_api_view(
            allow_webhook_access="allow_incoming_webhooks" in view_flags,
        )(target_function)
    elif (
        request.path.startswith(("/json", "/avatar", "/user_uploads", "/thumbnail"))
        and "allow_anonymous_user_web" in view_flags
    ):
        # For endpoints that support anonymous web access, we do that.
        # TODO: Allow /api calls when this is stable enough.
        target_function = csrf_protect(public_json_view(target_function))
    else:
        # Otherwise, throw an authentication error; our middleware
        # will generate the appropriate HTTP response.
        raise MissingAuthenticationError

    if request.method in ["DELETE", "PATCH", "PUT"]:
        # process_as_post needs to be the outer decorator, because
        # otherwise we might access and thus cache a value for
        # request.POST.
        target_function = process_as_post(target_function)

    return target_function(request, **kwargs)


def rest_path(
    route: str,
    **handlers: Union[
        Callable[..., HttpResponseBase],
        Tuple[Callable[..., HttpResponseBase], Set[str]],
    ],
) -> URLPattern:
    return path(route, rest_dispatch, handlers)
