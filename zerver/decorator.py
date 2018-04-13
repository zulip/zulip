
from django.utils.translation import ugettext as _
from django.http import HttpResponseRedirect, HttpResponse
from django.contrib.auth import REDIRECT_FIELD_NAME, login as django_login
from django.views.decorators.csrf import csrf_exempt
from django.http import QueryDict, HttpResponseNotAllowed, HttpRequest
from django.http.multipartparser import MultiPartParser
from zerver.models import Realm, UserProfile, get_client, get_user_profile_by_api_key
from zerver.lib.response import json_error, json_unauthorized, json_success
from django.shortcuts import resolve_url
from django.utils.decorators import available_attrs
from django.utils.timezone import now as timezone_now
from django.conf import settings
from zerver.lib.queue import queue_json_publish
from zerver.lib.subdomains import get_subdomain, user_matches_subdomain
from zerver.lib.timestamp import datetime_to_timestamp, timestamp_to_datetime
from zerver.lib.utils import statsd, is_remote_server
from zerver.lib.exceptions import RateLimited, JsonableError, ErrorCode
from zerver.lib.types import ViewFuncT

from zerver.lib.rate_limiter import incr_ratelimit, is_ratelimited, \
    api_calls_left, RateLimitedUser
from zerver.lib.request import REQ, has_request_variables, JsonableError, RequestVariableMissingError
from django.core.handlers import base

from functools import wraps
import base64
import datetime
import ujson
import logging
from io import BytesIO
import urllib

from typing import Union, Any, Callable, Sequence, Dict, Optional, TypeVar, Text, Tuple, cast
from zerver.lib.logging_util import log_to_file

# This is a hack to ensure that RemoteZulipServer always exists even
# if Zilencer isn't enabled.
if settings.ZILENCER_ENABLED:
    from zilencer.models import get_remote_server_by_uuid, RemoteZulipServer
else:
    from mock import Mock
    get_remote_server_by_uuid = Mock()
    RemoteZulipServer = Mock()  # type: ignore # https://github.com/JukkaL/mypy/issues/1188

ReturnT = TypeVar('ReturnT')

webhook_logger = logging.getLogger("zulip.zerver.webhooks")
log_to_file(webhook_logger, settings.API_KEY_ONLY_WEBHOOK_LOG_PATH)

class _RespondAsynchronously:
    pass

# Return RespondAsynchronously from an @asynchronous view if the
# response will be provided later by calling handler.zulip_finish(),
# or has already been provided this way. We use this for longpolling
# mode.
RespondAsynchronously = _RespondAsynchronously()

AsyncWrapperT = Callable[..., Union[HttpResponse, _RespondAsynchronously]]
def asynchronous(method: Callable[..., Union[HttpResponse, _RespondAsynchronously]]) -> AsyncWrapperT:
    # TODO: this should be the correct annotation when mypy gets fixed: type:
    #   (Callable[[HttpRequest, base.BaseHandler, Sequence[Any], Dict[str, Any]],
    #     Union[HttpResponse, _RespondAsynchronously]]) ->
    #   Callable[[HttpRequest, Sequence[Any], Dict[str, Any]], Union[HttpResponse, _RespondAsynchronously]]
    # TODO: see https://github.com/python/mypy/issues/1655
    @wraps(method)
    def wrapper(request: HttpRequest, *args: Any,
                **kwargs: Any) -> Union[HttpResponse, _RespondAsynchronously]:
        return method(request, handler=request._tornado_handler, *args, **kwargs)
    if getattr(method, 'csrf_exempt', False):
        wrapper.csrf_exempt = True  # type: ignore # https://github.com/JukkaL/mypy/issues/1170
    return wrapper

def cachify(method: Callable[..., ReturnT]) -> Callable[..., ReturnT]:
    dct = {}  # type: Dict[Tuple[Any, ...], ReturnT]

    def cache_wrapper(*args: Any) -> ReturnT:
        tup = tuple(args)
        if tup in dct:
            return dct[tup]
        result = method(*args)
        dct[tup] = result
        return result
    return cache_wrapper

def update_user_activity(request: HttpRequest, user_profile: UserProfile,
                         query: Optional[str]) -> None:
    # update_active_status also pushes to rabbitmq, and it seems
    # redundant to log that here as well.
    if request.META["PATH_INFO"] == '/json/users/me/presence':
        return

    if query is not None:
        pass
    elif hasattr(request, '_query'):
        query = request._query
    else:
        query = request.META['PATH_INFO']

    event = {'query': query,
             'user_profile_id': user_profile.id,
             'time': datetime_to_timestamp(timezone_now()),
             'client': request.client.name}
    queue_json_publish("user_activity", event, lambda event: None)

# Based on django.views.decorators.http.require_http_methods
def require_post(func: ViewFuncT) -> ViewFuncT:
    @wraps(func)
    def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        if (request.method != "POST" and
            not (request.method == "SOCKET" and
                 request.META['zulip.emulated_method'] == "POST")):
            if request.method == "SOCKET":
                err_method = "SOCKET/%s" % (request.META['zulip.emulated_method'],)
            else:
                err_method = request.method
            logging.warning('Method Not Allowed (%s): %s', err_method, request.path,
                            extra={'status_code': 405, 'request': request})
            return HttpResponseNotAllowed(["POST"])
        return func(request, *args, **kwargs)
    return wrapper  # type: ignore # https://github.com/python/mypy/issues/1927

def require_realm_admin(func: ViewFuncT) -> ViewFuncT:
    @wraps(func)
    def wrapper(request: HttpRequest, user_profile: UserProfile, *args: Any, **kwargs: Any) -> HttpResponse:
        if not user_profile.is_realm_admin:
            raise JsonableError(_("Must be an organization administrator"))
        return func(request, user_profile, *args, **kwargs)
    return wrapper  # type: ignore # https://github.com/python/mypy/issues/1927

from zerver.lib.user_agent import parse_user_agent

def get_client_name(request: HttpRequest, is_browser_view: bool) -> Text:
    # If the API request specified a client in the request content,
    # that has priority.  Otherwise, extract the client from the
    # User-Agent.
    if 'client' in request.GET:
        return request.GET['client']
    if 'client' in request.POST:
        return request.POST['client']
    if "HTTP_USER_AGENT" in request.META:
        user_agent = parse_user_agent(request.META["HTTP_USER_AGENT"])
    else:
        user_agent = None
    if user_agent is not None:
        # We could check for a browser's name being "Mozilla", but
        # e.g. Opera and MobileSafari don't set that, and it seems
        # more robust to just key off whether it was a browser view
        if is_browser_view and not user_agent["name"].startswith("Zulip"):
            # Avoid changing the client string for browsers, but let
            # the Zulip desktop and mobile apps be themselves.
            return "website"
        else:
            return user_agent["name"]
    else:
        # In the future, we will require setting USER_AGENT, but for
        # now we just want to tag these requests so we can review them
        # in logs and figure out the extent of the problem
        if is_browser_view:
            return "website"
        else:
            return "Unspecified"

def process_client(request: HttpRequest, user_profile: UserProfile,
                   *, is_browser_view: bool=False,
                   client_name: Optional[Text]=None,
                   remote_server_request: bool=False,
                   query: Optional[Text]=None) -> None:
    if client_name is None:
        client_name = get_client_name(request, is_browser_view)

    request.client = get_client(client_name)
    if not remote_server_request:
        update_user_activity(request, user_profile, query)

class InvalidZulipServerError(JsonableError):
    code = ErrorCode.INVALID_ZULIP_SERVER
    data_fields = ['role']

    def __init__(self, role: Text) -> None:
        self.role = role  # type: Text

    @staticmethod
    def msg_format() -> Text:
        return "Zulip server auth failure: {role} is not registered"

class InvalidZulipServerKeyError(JsonableError):
    @staticmethod
    def msg_format() -> Text:
        return "Zulip server auth failure: key does not match role {role}"

def validate_api_key(request: HttpRequest, role: Optional[Text],
                     api_key: Text, is_webhook: bool=False,
                     client_name: Optional[Text]=None) -> Union[UserProfile, RemoteZulipServer]:
    # Remove whitespace to protect users from trivial errors.
    api_key = api_key.strip()
    if role is not None:
        role = role.strip()

    if settings.ZILENCER_ENABLED and role is not None and is_remote_server(role):
        try:
            remote_server = get_remote_server_by_uuid(role)
        except RemoteZulipServer.DoesNotExist:
            raise InvalidZulipServerError(role)
        if api_key != remote_server.api_key:
            raise InvalidZulipServerKeyError(role)

        if get_subdomain(request) != Realm.SUBDOMAIN_FOR_ROOT_DOMAIN:
            raise JsonableError(_("Invalid subdomain for push notifications bouncer"))
        request.user = remote_server
        request._email = "zulip-server:" + role
        remote_server.rate_limits = ""
        process_client(request, remote_server, remote_server_request=True)
        return remote_server

    user_profile = access_user_by_api_key(request, api_key, email=role)
    if user_profile.is_incoming_webhook and not is_webhook:
        raise JsonableError(_("This API is not available to incoming webhook bots."))

    request.user = user_profile
    request._email = user_profile.email
    process_client(request, user_profile, client_name=client_name)

    return user_profile

def validate_account_and_subdomain(request: HttpRequest, user_profile: UserProfile) -> None:
    if not user_profile.is_active:
        raise JsonableError(_("Account not active"))

    if user_profile.realm.deactivated:
        raise JsonableError(_("This organization has been deactivated"))

    # Either the subdomain matches, or processing a websockets message
    # in the message_sender worker (which will have already had the
    # subdomain validated), or we're accessing Tornado from and to
    # localhost (aka spoofing a request as the user).
    if (not user_matches_subdomain(get_subdomain(request), user_profile) and
        not (request.method == "SOCKET" and
             request.META['SERVER_NAME'] == "127.0.0.1") and
        not (settings.RUNNING_INSIDE_TORNADO and
             request.META["SERVER_NAME"] == "127.0.0.1" and
             request.META["REMOTE_ADDR"] == "127.0.0.1")):
        logging.warning("User %s (%s) attempted to access API on wrong subdomain (%s)" % (
            user_profile.email, user_profile.realm.subdomain, get_subdomain(request)))
        raise JsonableError(_("Account is not associated with this subdomain"))

def access_user_by_api_key(request: HttpRequest, api_key: Text, email: Optional[Text]=None) -> UserProfile:
    try:
        user_profile = get_user_profile_by_api_key(api_key)
    except UserProfile.DoesNotExist:
        raise JsonableError(_("Invalid API key"))
    if email is not None and email.lower() != user_profile.email.lower():
        # This covers the case that the API key is correct, but for a
        # different user.  We may end up wanting to relaxing this
        # constraint or give a different error message in the future.
        raise JsonableError(_("Invalid API key"))

    validate_account_and_subdomain(request, user_profile)

    return user_profile

def log_exception_to_webhook_logger(request: HttpRequest, user_profile: UserProfile,
                                    request_body: Optional[Text]=None) -> None:
    if request_body is not None:
        payload = request_body
    else:
        payload = request.body

    if request.content_type == 'application/json':
        try:
            payload = ujson.dumps(ujson.loads(payload), indent=4)
        except ValueError:
            request_body = str(payload)
    else:
        request_body = str(payload)

    custom_header_template = "{header}: {value}\n"

    header_message = ""
    for header in request.META.keys():
        if header.lower().startswith('http_x'):
            header_message += custom_header_template.format(
                header=header, value=request.META[header])

    if not header_message:
        header_message = None

    message = """
user: {email} ({realm})
client: {client_name}
URL: {path_info}
content_type: {content_type}
custom_http_headers:
{custom_headers}
body:

{body}
    """.format(
        email=user_profile.email,
        realm=user_profile.realm.string_id,
        client_name=request.client.name,
        body=payload,
        path_info=request.META.get('PATH_INFO', None),
        content_type=request.content_type,
        custom_headers=header_message,
    )
    message = message.strip(' ')
    webhook_logger.exception(message)

def full_webhook_client_name(raw_client_name: Optional[str]=None) -> Optional[str]:
    if raw_client_name is None:
        return None
    return "Zulip{}Webhook".format(raw_client_name)

# Use this for webhook views that don't get an email passed in.
def api_key_only_webhook_view(webhook_client_name: Text) -> Callable[[ViewFuncT], ViewFuncT]:
    # TODO The typing here could be improved by using the Extended Callable types:
    # https://mypy.readthedocs.io/en/latest/kinds_of_types.html#extended-callable-types
    def _wrapped_view_func(view_func: ViewFuncT) -> ViewFuncT:
        @csrf_exempt
        @has_request_variables
        @wraps(view_func)
        def _wrapped_func_arguments(request: HttpRequest, api_key: Text=REQ(),
                                    *args: Any, **kwargs: Any) -> HttpResponse:
            user_profile = validate_api_key(request, None, api_key, is_webhook=True,
                                            client_name=full_webhook_client_name(webhook_client_name))

            if settings.RATE_LIMITING:
                rate_limit_user(request, user_profile, domain='all')
            try:
                return view_func(request, user_profile, *args, **kwargs)
            except Exception as err:
                log_exception_to_webhook_logger(request, user_profile)
                raise err

        return _wrapped_func_arguments
    return _wrapped_view_func

# From Django 1.8, modified to leave off ?next=/
def redirect_to_login(next: Text, login_url: Optional[Text]=None,
                      redirect_field_name: Text=REDIRECT_FIELD_NAME) -> HttpResponseRedirect:
    """
    Redirects the user to the login page, passing the given 'next' page
    """
    resolved_url = resolve_url(login_url or settings.LOGIN_URL)

    login_url_parts = list(urllib.parse.urlparse(resolved_url))
    if redirect_field_name:
        querystring = QueryDict(login_url_parts[4], mutable=True)
        querystring[redirect_field_name] = next
        # Don't add ?next=/, to keep our URLs clean
        if next != '/':
            login_url_parts[4] = querystring.urlencode(safe='/')

    return HttpResponseRedirect(urllib.parse.urlunparse(login_url_parts))

# From Django 1.8
def user_passes_test(test_func: Callable[[HttpResponse], bool], login_url: Optional[Text]=None,
                     redirect_field_name: Text=REDIRECT_FIELD_NAME) -> Callable[[ViewFuncT], ViewFuncT]:
    """
    Decorator for views that checks that the user passes the given test,
    redirecting to the log-in page if necessary. The test should be a callable
    that takes the user object and returns True if the user passes.
    """
    def decorator(view_func: ViewFuncT) -> ViewFuncT:
        @wraps(view_func, assigned=available_attrs(view_func))
        def _wrapped_view(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
            if test_func(request):
                return view_func(request, *args, **kwargs)
            path = request.build_absolute_uri()
            resolved_login_url = resolve_url(login_url or settings.LOGIN_URL)
            # If the login url is the same scheme and net location then just
            # use the path as the "next" url.
            login_scheme, login_netloc = urllib.parse.urlparse(resolved_login_url)[:2]
            current_scheme, current_netloc = urllib.parse.urlparse(path)[:2]
            if ((not login_scheme or login_scheme == current_scheme) and
                    (not login_netloc or login_netloc == current_netloc)):
                path = request.get_full_path()
            return redirect_to_login(
                path, resolved_login_url, redirect_field_name)
        return _wrapped_view  # type: ignore # https://github.com/python/mypy/issues/1927
    return decorator

def logged_in_and_active(request: HttpRequest) -> bool:
    if not request.user.is_authenticated:
        return False
    if not request.user.is_active:
        return False
    if request.user.realm.deactivated:
        return False
    return user_matches_subdomain(get_subdomain(request), request.user)

def do_login(request: HttpRequest, user_profile: UserProfile) -> None:
    """Creates a session, logging in the user, using the Django method,
    and also adds helpful data needed by our server logs.
    """
    django_login(request, user_profile)
    request._email = user_profile.email
    process_client(request, user_profile, is_browser_view=True)

def log_view_func(view_func: ViewFuncT) -> ViewFuncT:
    @wraps(view_func)
    def _wrapped_view_func(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        request._query = view_func.__name__
        return view_func(request, *args, **kwargs)
    return _wrapped_view_func  # type: ignore # https://github.com/python/mypy/issues/1927

def add_logging_data(view_func: ViewFuncT) -> ViewFuncT:
    @wraps(view_func)
    def _wrapped_view_func(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        request._email = request.user.email
        process_client(request, request.user, is_browser_view=True,
                       query=view_func.__name__)
        return rate_limit()(view_func)(request, *args, **kwargs)
    return _wrapped_view_func  # type: ignore # https://github.com/python/mypy/issues/1927

def human_users_only(view_func: ViewFuncT) -> ViewFuncT:
    @wraps(view_func)
    def _wrapped_view_func(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        if request.user.is_bot:
            return json_error(_("This endpoint does not accept bot requests."))
        return view_func(request, *args, **kwargs)
    return _wrapped_view_func  # type: ignore # https://github.com/python/mypy/issues/1927

# Based on Django 1.8's @login_required
def zulip_login_required(
        function: Optional[ViewFuncT]=None,
        redirect_field_name: Text=REDIRECT_FIELD_NAME,
        login_url: Text=settings.HOME_NOT_LOGGED_IN,
) -> Union[Callable[[ViewFuncT], ViewFuncT], ViewFuncT]:
    actual_decorator = user_passes_test(
        logged_in_and_active,
        login_url=login_url,
        redirect_field_name=redirect_field_name
    )
    if function:
        # Add necessary logging data via add_logging_data
        return actual_decorator(add_logging_data(function))
    return actual_decorator

def require_server_admin(view_func: ViewFuncT) -> ViewFuncT:
    @zulip_login_required
    @wraps(view_func)
    def _wrapped_view_func(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        if not request.user.is_staff:
            return HttpResponseRedirect(settings.HOME_NOT_LOGGED_IN)

        return add_logging_data(view_func)(request, *args, **kwargs)
    return _wrapped_view_func  # type: ignore # https://github.com/python/mypy/issues/1927

# authenticated_api_view will add the authenticated user's
# user_profile to the view function's arguments list, since we have to
# look it up anyway.  It is deprecated in favor on the REST API
# versions.
def authenticated_api_view(is_webhook: bool=False) -> Callable[[ViewFuncT], ViewFuncT]:
    def _wrapped_view_func(view_func: ViewFuncT) -> ViewFuncT:
        @csrf_exempt
        @require_post
        @has_request_variables
        @wraps(view_func)
        def _wrapped_func_arguments(request: HttpRequest, email: Text=REQ(),
                                    api_key: Optional[Text]=REQ(default=None),
                                    api_key_legacy: Optional[Text]=REQ('api-key', default=None),
                                    *args: Any, **kwargs: Any) -> HttpResponse:
            if api_key is None:
                api_key = api_key_legacy
            if api_key is None:
                raise RequestVariableMissingError("api_key")
            user_profile = validate_api_key(request, email, api_key, is_webhook)
            # Apply rate limiting
            limited_func = rate_limit()(view_func)
            try:
                return limited_func(request, user_profile, *args, **kwargs)
            except Exception as err:
                if is_webhook:
                    # In this case, request_body is passed explicitly because the body
                    # of the request has already been read in has_request_variables and
                    # can't be read/accessed more than once, so we just access it from
                    # the request.POST QueryDict.
                    log_exception_to_webhook_logger(request, user_profile,
                                                    request_body=request.POST.get('payload'))
                raise err

        return _wrapped_func_arguments
    return _wrapped_view_func

# This API endpoint is used only for the mobile apps.  It is part of a
# workaround for the fact that React Native doesn't support setting
# HTTP basic authentication headers.
def authenticated_uploads_api_view() -> Callable[[ViewFuncT], ViewFuncT]:
    def _wrapped_view_func(view_func: ViewFuncT) -> ViewFuncT:
        @csrf_exempt
        @has_request_variables
        @wraps(view_func)
        def _wrapped_func_arguments(request: HttpRequest,
                                    api_key: str=REQ(),
                                    *args: Any, **kwargs: Any) -> HttpResponse:
            user_profile = validate_api_key(request, None, api_key, False)
            limited_func = rate_limit()(view_func)
            return limited_func(request, user_profile, *args, **kwargs)
        return _wrapped_func_arguments
    return _wrapped_view_func

# A more REST-y authentication decorator, using, in particular, HTTP Basic
# authentication.
#
# If webhook_client_name is specific, the request is a webhook view
# with that string as the basis for the client string.
def authenticated_rest_api_view(*, webhook_client_name: str=None,
                                is_webhook: bool=False) -> Callable[[ViewFuncT], ViewFuncT]:
    def _wrapped_view_func(view_func: ViewFuncT) -> ViewFuncT:
        @csrf_exempt
        @wraps(view_func)
        def _wrapped_func_arguments(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
            # First try block attempts to get the credentials we need to do authentication
            try:
                # Grab the base64-encoded authentication string, decode it, and split it into
                # the email and API key
                auth_type, credentials = request.META['HTTP_AUTHORIZATION'].split()
                # case insensitive per RFC 1945
                if auth_type.lower() != "basic":
                    return json_error(_("This endpoint requires HTTP basic authentication."))
                role, api_key = base64.b64decode(credentials).decode('utf-8').split(":")
            except ValueError:
                return json_unauthorized(_("Invalid authorization header for basic auth"))
            except KeyError:
                return json_unauthorized("Missing authorization header for basic auth")

            # Now we try to do authentication or die
            try:
                # profile is a Union[UserProfile, RemoteZulipServer]
                profile = validate_api_key(request, role, api_key,
                                           is_webhook=is_webhook or webhook_client_name is not None,
                                           client_name=full_webhook_client_name(webhook_client_name))
            except JsonableError as e:
                return json_unauthorized(e.msg)
            # Apply rate limiting
            return rate_limit()(view_func)(request, profile, *args, **kwargs)
        return _wrapped_func_arguments
    return _wrapped_view_func

def process_as_post(view_func: ViewFuncT) -> ViewFuncT:
    @wraps(view_func)
    def _wrapped_view_func(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        # Adapted from django/http/__init__.py.
        # So by default Django doesn't populate request.POST for anything besides
        # POST requests. We want this dict populated for PATCH/PUT, so we have to
        # do it ourselves.
        #
        # This will not be required in the future, a bug will be filed against
        # Django upstream.

        if not request.POST:
            # Only take action if POST is empty.
            if request.META.get('CONTENT_TYPE', '').startswith('multipart'):
                # Note that request._files is just the private attribute that backs the
                # FILES property, so we are essentially setting request.FILES here.  (In
                # Django 1.5 FILES was still a read-only property.)
                request.POST, request._files = MultiPartParser(
                    request.META,
                    BytesIO(request.body),
                    request.upload_handlers,
                    request.encoding
                ).parse()
            else:
                request.POST = QueryDict(request.body, encoding=request.encoding)

        return view_func(request, *args, **kwargs)

    return _wrapped_view_func  # type: ignore # https://github.com/python/mypy/issues/1927

def authenticate_log_and_execute_json(request: HttpRequest,
                                      view_func: ViewFuncT,
                                      *args: Any, **kwargs: Any) -> HttpResponse:
    if not request.user.is_authenticated:
        return json_error(_("Not logged in"), status=401)
    user_profile = request.user
    validate_account_and_subdomain(request, user_profile)

    if user_profile.is_incoming_webhook:
        raise JsonableError(_("Webhook bots can only access webhooks"))

    process_client(request, user_profile, is_browser_view=True,
                   query=view_func.__name__)
    request._email = user_profile.email
    return rate_limit()(view_func)(request, user_profile, *args, **kwargs)

# Checks if the request is a POST request and that the user is logged
# in.  If not, return an error (the @login_required behavior of
# redirecting to a login page doesn't make sense for json views)
def authenticated_json_post_view(view_func: ViewFuncT) -> ViewFuncT:
    @require_post
    @has_request_variables
    @wraps(view_func)
    def _wrapped_view_func(request: HttpRequest,
                           *args: Any, **kwargs: Any) -> HttpResponse:
        return authenticate_log_and_execute_json(request, view_func, *args, **kwargs)
    return _wrapped_view_func  # type: ignore # https://github.com/python/mypy/issues/1927

def authenticated_json_view(view_func: ViewFuncT) -> ViewFuncT:
    @wraps(view_func)
    def _wrapped_view_func(request: HttpRequest,
                           *args: Any, **kwargs: Any) -> HttpResponse:
        return authenticate_log_and_execute_json(request, view_func, *args, **kwargs)
    return _wrapped_view_func  # type: ignore # https://github.com/python/mypy/issues/1927

def is_local_addr(addr: Text) -> bool:
    return addr in ('127.0.0.1', '::1')

# These views are used by the main Django server to notify the Tornado server
# of events.  We protect them from the outside world by checking a shared
# secret, and also the originating IP (for now).
def authenticate_notify(request: HttpRequest) -> bool:
    return (is_local_addr(request.META['REMOTE_ADDR']) and
            request.POST.get('secret') == settings.SHARED_SECRET)

def client_is_exempt_from_rate_limiting(request: HttpRequest) -> bool:

    # Don't rate limit requests from Django that come from our own servers,
    # and don't rate-limit dev instances
    return ((request.client and request.client.name.lower() == 'internal') and
            (is_local_addr(request.META['REMOTE_ADDR']) or
             settings.DEBUG_RATE_LIMITING))

def internal_notify_view(is_tornado_view: bool) -> Callable[[ViewFuncT], ViewFuncT]:
    # The typing here could be improved by using the Extended Callable types:
    # https://mypy.readthedocs.io/en/latest/kinds_of_types.html#extended-callable-types
    """Used for situations where something running on the Zulip server
    needs to make a request to the (other) Django/Tornado processes running on
    the server."""
    def _wrapped_view_func(view_func: ViewFuncT) -> ViewFuncT:
        @csrf_exempt
        @require_post
        @wraps(view_func)
        def _wrapped_func_arguments(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
            if not authenticate_notify(request):
                return json_error(_('Access denied'), status=403)
            is_tornado_request = hasattr(request, '_tornado_handler')
            # These next 2 are not security checks; they are internal
            # assertions to help us find bugs.
            if is_tornado_view and not is_tornado_request:
                raise RuntimeError('Tornado notify view called with no Tornado handler')
            if not is_tornado_view and is_tornado_request:
                raise RuntimeError('Django notify view called with Tornado handler')
            request._email = "internal"
            return view_func(request, *args, **kwargs)
        return _wrapped_func_arguments
    return _wrapped_view_func

# Converter functions for use with has_request_variables
def to_non_negative_int(s: Text) -> int:
    x = int(s)
    if x < 0:
        raise ValueError("argument is negative")
    return x


def to_not_negative_int_or_none(s: Text) -> Optional[int]:
    if s:
        return to_non_negative_int(s)
    return None


def flexible_boolean(boolean: Text) -> bool:
    """Returns True for any of "1", "true", or "True".  Returns False otherwise."""
    if boolean in ("1", "true", "True"):
        return True
    else:
        return False

def to_utc_datetime(timestamp: Text) -> datetime.datetime:
    return timestamp_to_datetime(float(timestamp))

def statsd_increment(counter: Text, val: int=1,
                     ) -> Callable[[Callable[..., ReturnT]], Callable[..., ReturnT]]:
    """Increments a statsd counter on completion of the
    decorated function.

    Pass the name of the counter to this decorator-returning function."""
    def wrapper(func: Callable[..., ReturnT]) -> Callable[..., ReturnT]:
        @wraps(func)
        def wrapped_func(*args: Any, **kwargs: Any) -> ReturnT:
            ret = func(*args, **kwargs)
            statsd.incr(counter, val)
            return ret
        return wrapped_func
    return wrapper

def rate_limit_user(request: HttpRequest, user: UserProfile, domain: Text) -> None:
    """Returns whether or not a user was rate limited. Will raise a RateLimited exception
    if the user has been rate limited, otherwise returns and modifies request to contain
    the rate limit information"""

    entity = RateLimitedUser(user, domain=domain)
    ratelimited, time = is_ratelimited(entity)
    request._ratelimit_applied_limits = True
    request._ratelimit_secs_to_freedom = time
    request._ratelimit_over_limit = ratelimited
    # Abort this request if the user is over their rate limits
    if ratelimited:
        statsd.incr("ratelimiter.limited.%s.%s" % (type(user), user.id))
        raise RateLimited()

    incr_ratelimit(entity)
    calls_remaining, time_reset = api_calls_left(entity)

    request._ratelimit_remaining = calls_remaining
    request._ratelimit_secs_to_freedom = time_reset

def rate_limit(domain: Text='all') -> Callable[[ViewFuncT], ViewFuncT]:
    """Rate-limits a view. Takes an optional 'domain' param if you wish to
    rate limit different types of API calls independently.

    Returns a decorator"""
    def wrapper(func: ViewFuncT) -> ViewFuncT:
        @wraps(func)
        def wrapped_func(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:

            # It is really tempting to not even wrap our original function
            # when settings.RATE_LIMITING is False, but it would make
            # for awkward unit testing in some situations.
            if not settings.RATE_LIMITING:
                return func(request, *args, **kwargs)

            if client_is_exempt_from_rate_limiting(request):
                return func(request, *args, **kwargs)

            try:
                user = request.user
            except Exception:
                # TODO: This logic is not tested, and I'm not sure we are
                # doing the right thing here.
                user = None

            if not user:
                logging.error("Requested rate-limiting on %s but user is not authenticated!" %
                              func.__name__)
                return func(request, *args, **kwargs)

            # Rate-limiting data is stored in redis
            # We also only support rate-limiting authenticated
            # views right now.
            # TODO(leo) - implement per-IP non-authed rate limiting
            rate_limit_user(request, user, domain)

            return func(request, *args, **kwargs)
        return wrapped_func  # type: ignore # https://github.com/python/mypy/issues/1927
    return wrapper

def return_success_on_head_request(view_func: ViewFuncT) -> ViewFuncT:
    @wraps(view_func)
    def _wrapped_view_func(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        if request.method == 'HEAD':
            return json_success()
        return view_func(request, *args, **kwargs)
    return _wrapped_view_func  # type: ignore # https://github.com/python/mypy/issues/1927
