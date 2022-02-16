import base64
import datetime
import logging
import urllib
from functools import wraps
from io import BytesIO
from typing import Callable, Dict, Optional, Sequence, Set, Tuple, TypeVar, Union, cast, overload

import django_otp
import orjson
from circuitbreaker import CircuitBreakerError, circuit
from django.conf import settings
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib.auth import login as django_login
from django.contrib.auth.decorators import user_passes_test as django_user_passes_test
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth.views import redirect_to_login
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect, QueryDict
from django.http.multipartparser import MultiPartParser
from django.shortcuts import resolve_url
from django.template.response import SimpleTemplateResponse, TemplateResponse
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt
from django_otp import user_has_device
from two_factor.utils import default_device

from zerver.lib.cache import cache_with_key
from zerver.lib.exceptions import (
    AccessDeniedError,
    AnomalousWebhookPayload,
    ErrorCode,
    InvalidAPIKeyError,
    InvalidAPIKeyFormatError,
    InvalidJSONError,
    JsonableError,
    OrganizationAdministratorRequired,
    OrganizationMemberRequired,
    OrganizationOwnerRequired,
    RateLimited,
    RealmDeactivatedError,
    RemoteServerDeactivatedError,
    UnsupportedWebhookEventType,
    UserDeactivatedError,
    WebhookError,
)
from zerver.lib.queue import queue_json_publish
from zerver.lib.rate_limiter import RateLimitedIPAddr, RateLimitedUser
from zerver.lib.request import REQ, RequestNotes, has_request_variables
from zerver.lib.response import json_method_not_allowed, json_success, json_unauthorized
from zerver.lib.subdomains import get_subdomain, user_matches_subdomain
from zerver.lib.timestamp import datetime_to_timestamp, timestamp_to_datetime
from zerver.lib.types import ViewFuncT
from zerver.lib.utils import has_api_key_format, statsd
from zerver.models import Realm, UserProfile, get_client, get_user_profile_by_api_key

if settings.ZILENCER_ENABLED:
    from zilencer.models import (
        RateLimitedRemoteZulipServer,
        RemoteZulipServer,
        get_remote_server_by_uuid,
    )

rate_limiter_logger = logging.getLogger("zerver.lib.rate_limiter")

webhook_logger = logging.getLogger("zulip.zerver.webhooks")
webhook_unsupported_events_logger = logging.getLogger("zulip.zerver.webhooks.unsupported")
webhook_anomalous_payloads_logger = logging.getLogger("zulip.zerver.webhooks.anomalous")

FuncT = TypeVar("FuncT", bound=Callable[..., object])


def cachify(method: FuncT) -> FuncT:
    dct: Dict[Tuple[object, ...], object] = {}

    def cache_wrapper(*args: object) -> object:
        tup = tuple(args)
        if tup in dct:
            return dct[tup]
        result = method(*args)
        dct[tup] = result
        return result

    return cast(FuncT, cache_wrapper)  # https://github.com/python/mypy/issues/1927


def update_user_activity(
    request: HttpRequest, user_profile: UserProfile, query: Optional[str]
) -> None:
    # update_active_status also pushes to RabbitMQ, and it seems
    # redundant to log that here as well.
    if request.META["PATH_INFO"] == "/json/users/me/presence":
        return

    request_notes = RequestNotes.get_notes(request)
    if query is not None:
        pass
    elif request_notes.query is not None:
        query = request_notes.query
    else:
        query = request.META["PATH_INFO"]

    assert request_notes.client is not None
    event = {
        "query": query,
        "user_profile_id": user_profile.id,
        "time": datetime_to_timestamp(timezone_now()),
        "client_id": request_notes.client.id,
    }
    queue_json_publish("user_activity", event, lambda event: None)


# Based on django.views.decorators.http.require_http_methods
def require_post(func: ViewFuncT) -> ViewFuncT:
    @wraps(func)
    def wrapper(request: HttpRequest, *args: object, **kwargs: object) -> HttpResponse:
        if request.method != "POST":
            err_method = request.method
            logging.warning(
                "Method Not Allowed (%s): %s",
                err_method,
                request.path,
                extra={"status_code": 405, "request": request},
            )
            if RequestNotes.get_notes(request).error_format == "JSON":
                return json_method_not_allowed(["POST"])
            else:
                return TemplateResponse(
                    request, "404.html", context={"status_code": 405}, status=405
                )
        return func(request, *args, **kwargs)

    return cast(ViewFuncT, wrapper)  # https://github.com/python/mypy/issues/1927


def require_realm_owner(func: ViewFuncT) -> ViewFuncT:
    @wraps(func)
    def wrapper(
        request: HttpRequest, user_profile: UserProfile, *args: object, **kwargs: object
    ) -> HttpResponse:
        if not user_profile.is_realm_owner:
            raise OrganizationOwnerRequired()
        return func(request, user_profile, *args, **kwargs)

    return cast(ViewFuncT, wrapper)  # https://github.com/python/mypy/issues/1927


def require_realm_admin(func: ViewFuncT) -> ViewFuncT:
    @wraps(func)
    def wrapper(
        request: HttpRequest, user_profile: UserProfile, *args: object, **kwargs: object
    ) -> HttpResponse:
        if not user_profile.is_realm_admin:
            raise OrganizationAdministratorRequired()
        return func(request, user_profile, *args, **kwargs)

    return cast(ViewFuncT, wrapper)  # https://github.com/python/mypy/issues/1927


def require_organization_member(func: ViewFuncT) -> ViewFuncT:
    @wraps(func)
    def wrapper(
        request: HttpRequest, user_profile: UserProfile, *args: object, **kwargs: object
    ) -> HttpResponse:
        if user_profile.role > UserProfile.ROLE_MEMBER:
            raise OrganizationMemberRequired()
        return func(request, user_profile, *args, **kwargs)

    return cast(ViewFuncT, wrapper)  # https://github.com/python/mypy/issues/1927


def require_billing_access(func: ViewFuncT) -> ViewFuncT:
    @wraps(func)
    def wrapper(
        request: HttpRequest, user_profile: UserProfile, *args: object, **kwargs: object
    ) -> HttpResponse:
        if not user_profile.has_billing_access:
            raise JsonableError(_("Must be a billing administrator or an organization owner"))
        return func(request, user_profile, *args, **kwargs)

    return cast(ViewFuncT, wrapper)  # https://github.com/python/mypy/issues/1927


def process_client(
    request: HttpRequest,
    user: Union[UserProfile, AnonymousUser],
    *,
    is_browser_view: bool = False,
    client_name: Optional[str] = None,
    skip_update_user_activity: bool = False,
    query: Optional[str] = None,
) -> None:
    request_notes = RequestNotes.get_notes(request)
    if client_name is None:
        client_name = request_notes.client_name

    assert client_name is not None

    # We could check for a browser's name being "Mozilla", but
    # e.g. Opera and MobileSafari don't set that, and it seems
    # more robust to just key off whether it was a browser view
    if is_browser_view and not client_name.startswith("Zulip"):
        # Avoid changing the client string for browsers, but let
        # the Zulip desktop apps be themselves.
        client_name = "website"

    request_notes.client = get_client(client_name)
    if not skip_update_user_activity and user.is_authenticated:
        update_user_activity(request, user, query)


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


def validate_api_key(
    request: HttpRequest,
    role: Optional[str],
    api_key: str,
    allow_webhook_access: bool = False,
    client_name: Optional[str] = None,
) -> Union[UserProfile, "RemoteZulipServer"]:
    # Remove whitespace to protect users from trivial errors.
    api_key = api_key.strip()
    if role is not None:
        role = role.strip()

    # If `role` doesn't look like an email, it might be a uuid.
    if settings.ZILENCER_ENABLED and role is not None and "@" not in role:
        try:
            remote_server = get_remote_server_by_uuid(role)
        except RemoteZulipServer.DoesNotExist:
            raise InvalidZulipServerError(role)
        if api_key != remote_server.api_key:
            raise InvalidZulipServerKeyError(role)

        if remote_server.deactivated:
            raise RemoteServerDeactivatedError()

        if get_subdomain(request) != Realm.SUBDOMAIN_FOR_ROOT_DOMAIN:
            raise JsonableError(_("Invalid subdomain for push notifications bouncer"))
        request.user = remote_server
        remote_server.rate_limits = ""
        # Skip updating UserActivity, since remote_server isn't actually a UserProfile object.
        process_client(request, remote_server, skip_update_user_activity=True)
        return remote_server

    user_profile = access_user_by_api_key(request, api_key, email=role)
    if user_profile.is_incoming_webhook and not allow_webhook_access:
        raise JsonableError(_("This API is not available to incoming webhook bots."))

    request.user = user_profile
    process_client(request, user_profile, client_name=client_name)

    return user_profile


def validate_account_and_subdomain(request: HttpRequest, user_profile: UserProfile) -> None:
    if user_profile.realm.deactivated:
        raise RealmDeactivatedError()
    if not user_profile.is_active:
        raise UserDeactivatedError()

    # Either the subdomain matches, or we're accessing Tornado from
    # and to localhost (aka spoofing a request as the user).
    if not user_matches_subdomain(get_subdomain(request), user_profile) and not (
        settings.RUNNING_INSIDE_TORNADO
        and request.META["SERVER_NAME"] == "127.0.0.1"
        and request.META["REMOTE_ADDR"] == "127.0.0.1"
    ):
        logging.warning(
            "User %s (%s) attempted to access API on wrong subdomain (%s)",
            user_profile.delivery_email,
            user_profile.realm.subdomain,
            get_subdomain(request),
        )
        raise JsonableError(_("Account is not associated with this subdomain"))


def access_user_by_api_key(
    request: HttpRequest, api_key: str, email: Optional[str] = None
) -> UserProfile:
    if not has_api_key_format(api_key):
        raise InvalidAPIKeyFormatError()

    try:
        user_profile = get_user_profile_by_api_key(api_key)
    except UserProfile.DoesNotExist:
        raise InvalidAPIKeyError()
    if email is not None and email.lower() != user_profile.delivery_email.lower():
        # This covers the case that the API key is correct, but for a
        # different user.  We may end up wanting to relaxing this
        # constraint or give a different error message in the future.
        raise InvalidAPIKeyError()

    validate_account_and_subdomain(request, user_profile)

    return user_profile


def log_unsupported_webhook_event(summary: str) -> None:
    # This helper is primarily used by some of our more complicated
    # webhook integrations (e.g. GitHub) that need to log an unsupported
    # event based on attributes nested deep within a complicated JSON
    # payload. In such cases, the error message we want to log may not
    # really fit what a regular UnsupportedWebhookEventType exception
    # represents.
    webhook_unsupported_events_logger.exception(summary, stack_info=True)


def log_exception_to_webhook_logger(err: Exception) -> None:
    if isinstance(err, AnomalousWebhookPayload):
        webhook_anomalous_payloads_logger.exception(str(err), stack_info=True)
    elif isinstance(err, UnsupportedWebhookEventType):
        webhook_unsupported_events_logger.exception(str(err), stack_info=True)
    else:
        webhook_logger.exception(str(err), stack_info=True)


def full_webhook_client_name(raw_client_name: Optional[str] = None) -> Optional[str]:
    if raw_client_name is None:
        return None
    return f"Zulip{raw_client_name}Webhook"


# Use this for webhook views that don't get an email passed in.
def webhook_view(
    webhook_client_name: str,
    notify_bot_owner_on_invalid_json: bool = True,
    all_event_types: Optional[Sequence[str]] = None,
) -> Callable[[Callable[..., HttpResponse]], Callable[..., HttpResponse]]:
    # Unfortunately, callback protocols are insufficient for this:
    # https://mypy.readthedocs.io/en/stable/protocols.html#callback-protocols
    # Variadic generics are necessary: https://github.com/python/typing/issues/193
    def _wrapped_view_func(view_func: Callable[..., HttpResponse]) -> Callable[..., HttpResponse]:
        @csrf_exempt
        @has_request_variables
        @wraps(view_func)
        def _wrapped_func_arguments(
            request: HttpRequest, api_key: str = REQ(), *args: object, **kwargs: object
        ) -> HttpResponse:
            user_profile = validate_api_key(
                request,
                None,
                api_key,
                allow_webhook_access=True,
                client_name=full_webhook_client_name(webhook_client_name),
            )

            if settings.RATE_LIMITING:
                rate_limit_user(request, user_profile, domain="api_by_user")
            try:
                return view_func(request, user_profile, *args, **kwargs)
            except Exception as err:
                if isinstance(err, InvalidJSONError) and notify_bot_owner_on_invalid_json:
                    # NOTE: importing this at the top of file leads to a
                    # cyclic import; correct fix is probably to move
                    # notify_bot_owner_about_invalid_json to a smaller file.
                    from zerver.lib.webhooks.common import notify_bot_owner_about_invalid_json

                    notify_bot_owner_about_invalid_json(user_profile, webhook_client_name)
                elif isinstance(err, JsonableError) and not isinstance(err, WebhookError):
                    pass
                else:
                    if isinstance(err, WebhookError):
                        err.webhook_name = webhook_client_name
                    log_exception_to_webhook_logger(err)
                raise err

        _wrapped_func_arguments._all_event_types = all_event_types
        return _wrapped_func_arguments

    return _wrapped_view_func


def zulip_redirect_to_login(
    request: HttpRequest,
    login_url: Optional[str] = None,
    redirect_field_name: str = REDIRECT_FIELD_NAME,
) -> HttpResponseRedirect:
    path = request.build_absolute_uri()
    resolved_login_url = resolve_url(login_url or settings.LOGIN_URL)
    # If the login URL is the same scheme and net location then just
    # use the path as the "next" url.
    login_scheme, login_netloc = urllib.parse.urlparse(resolved_login_url)[:2]
    current_scheme, current_netloc = urllib.parse.urlparse(path)[:2]
    if (not login_scheme or login_scheme == current_scheme) and (
        not login_netloc or login_netloc == current_netloc
    ):
        path = request.get_full_path()

    if path == "/":
        # Don't add ?next=/, to keep our URLs clean
        return HttpResponseRedirect(resolved_login_url)
    return redirect_to_login(path, resolved_login_url, redirect_field_name)


# From Django 2.2, modified to pass the request rather than just the
# user into test_func; this is useful so that we can revalidate the
# subdomain matches the user's realm.  It is likely that we could make
# the subdomain validation happen elsewhere and switch to using the
# stock Django version.
def user_passes_test(
    test_func: Callable[[HttpRequest], bool],
    login_url: Optional[str] = None,
    redirect_field_name: str = REDIRECT_FIELD_NAME,
) -> Callable[[ViewFuncT], ViewFuncT]:
    """
    Decorator for views that checks that the user passes the given test,
    redirecting to the log-in page if necessary. The test should be a callable
    that takes the user object and returns True if the user passes.
    """

    def decorator(view_func: ViewFuncT) -> ViewFuncT:
        @wraps(view_func)
        def _wrapped_view(request: HttpRequest, *args: object, **kwargs: object) -> HttpResponse:
            if test_func(request):
                return view_func(request, *args, **kwargs)
            return zulip_redirect_to_login(request, login_url, redirect_field_name)

        return cast(ViewFuncT, _wrapped_view)  # https://github.com/python/mypy/issues/1927

    return decorator


def logged_in_and_active(request: HttpRequest) -> bool:
    if not request.user.is_authenticated:
        return False
    if not request.user.is_active:
        return False
    if request.user.realm.deactivated:
        return False
    return user_matches_subdomain(get_subdomain(request), request.user)


def do_two_factor_login(request: HttpRequest, user_profile: UserProfile) -> None:
    device = default_device(user_profile)
    if device:
        django_otp.login(request, device)


def do_login(request: HttpRequest, user_profile: UserProfile) -> None:
    """Creates a session, logging in the user, using the Django method,
    and also adds helpful data needed by our server logs.
    """
    django_login(request, user_profile)
    RequestNotes.get_notes(request).requestor_for_logs = user_profile.format_requestor_for_logs()
    process_client(request, user_profile, is_browser_view=True)
    if settings.TWO_FACTOR_AUTHENTICATION_ENABLED:
        # Log in with two factor authentication as well.
        do_two_factor_login(request, user_profile)


def log_view_func(view_func: ViewFuncT) -> ViewFuncT:
    @wraps(view_func)
    def _wrapped_view_func(request: HttpRequest, *args: object, **kwargs: object) -> HttpResponse:
        RequestNotes.get_notes(request).query = view_func.__name__
        return view_func(request, *args, **kwargs)

    return cast(ViewFuncT, _wrapped_view_func)  # https://github.com/python/mypy/issues/1927


def add_logging_data(view_func: ViewFuncT) -> ViewFuncT:
    @wraps(view_func)
    def _wrapped_view_func(request: HttpRequest, *args: object, **kwargs: object) -> HttpResponse:
        process_client(request, request.user, is_browser_view=True, query=view_func.__name__)
        return rate_limit()(view_func)(request, *args, **kwargs)

    return cast(ViewFuncT, _wrapped_view_func)  # https://github.com/python/mypy/issues/1927


def human_users_only(view_func: ViewFuncT) -> ViewFuncT:
    @wraps(view_func)
    def _wrapped_view_func(request: HttpRequest, *args: object, **kwargs: object) -> HttpResponse:
        assert request.user.is_authenticated
        if request.user.is_bot:
            raise JsonableError(_("This endpoint does not accept bot requests."))
        return view_func(request, *args, **kwargs)

    return cast(ViewFuncT, _wrapped_view_func)  # https://github.com/python/mypy/issues/1927


@overload
def zulip_login_required(
    function: ViewFuncT,
    redirect_field_name: str = REDIRECT_FIELD_NAME,
    login_url: str = settings.HOME_NOT_LOGGED_IN,
) -> ViewFuncT:
    ...


@overload
def zulip_login_required(
    function: None,
    redirect_field_name: str = REDIRECT_FIELD_NAME,
    login_url: str = settings.HOME_NOT_LOGGED_IN,
) -> Callable[[ViewFuncT], ViewFuncT]:
    ...


# Based on Django 1.8's @login_required
def zulip_login_required(
    function: Optional[ViewFuncT] = None,
    redirect_field_name: str = REDIRECT_FIELD_NAME,
    login_url: str = settings.HOME_NOT_LOGGED_IN,
) -> Union[Callable[[ViewFuncT], ViewFuncT], ViewFuncT]:
    actual_decorator = lambda function: user_passes_test(
        logged_in_and_active,
        login_url=login_url,
        redirect_field_name=redirect_field_name,
    )(
        zulip_otp_required(
            redirect_field_name=redirect_field_name,
            login_url=login_url,
        )(add_logging_data(function))
    )

    if function:
        return actual_decorator(function)
    return actual_decorator  # nocoverage # We don't use this without a function


def web_public_view(
    view_func: ViewFuncT,
    redirect_field_name: str = REDIRECT_FIELD_NAME,
    login_url: str = settings.HOME_NOT_LOGGED_IN,
) -> Union[Callable[[ViewFuncT], ViewFuncT], ViewFuncT]:
    """
    This wrapper adds client info for unauthenticated users but
    forces authenticated users to go through 2fa.
    """
    actual_decorator = lambda view_func: zulip_otp_required(
        redirect_field_name=redirect_field_name, login_url=login_url
    )(add_logging_data(view_func))

    return actual_decorator(view_func)


def require_server_admin(view_func: ViewFuncT) -> ViewFuncT:
    @zulip_login_required
    @wraps(view_func)
    def _wrapped_view_func(request: HttpRequest, *args: object, **kwargs: object) -> HttpResponse:
        if not request.user.is_staff:
            return HttpResponseRedirect(settings.HOME_NOT_LOGGED_IN)

        return add_logging_data(view_func)(request, *args, **kwargs)

    return cast(ViewFuncT, _wrapped_view_func)  # https://github.com/python/mypy/issues/1927


def require_server_admin_api(view_func: ViewFuncT) -> ViewFuncT:
    @zulip_login_required
    @wraps(view_func)
    def _wrapped_view_func(
        request: HttpRequest, user_profile: UserProfile, *args: object, **kwargs: object
    ) -> HttpResponse:
        if not user_profile.is_staff:
            raise JsonableError(_("Must be an server administrator"))
        return view_func(request, user_profile, *args, **kwargs)

    return cast(ViewFuncT, _wrapped_view_func)  # https://github.com/python/mypy/issues/1927


def require_non_guest_user(view_func: ViewFuncT) -> ViewFuncT:
    @wraps(view_func)
    def _wrapped_view_func(
        request: HttpRequest, user_profile: UserProfile, *args: object, **kwargs: object
    ) -> HttpResponse:
        if user_profile.is_guest:
            raise JsonableError(_("Not allowed for guest users"))
        return view_func(request, user_profile, *args, **kwargs)

    return cast(ViewFuncT, _wrapped_view_func)  # https://github.com/python/mypy/issues/1927


def require_member_or_admin(view_func: ViewFuncT) -> ViewFuncT:
    @wraps(view_func)
    def _wrapped_view_func(
        request: HttpRequest, user_profile: UserProfile, *args: object, **kwargs: object
    ) -> HttpResponse:
        if user_profile.is_guest:
            raise JsonableError(_("Not allowed for guest users"))
        if user_profile.is_bot:
            raise JsonableError(_("This endpoint does not accept bot requests."))
        return view_func(request, user_profile, *args, **kwargs)

    return cast(ViewFuncT, _wrapped_view_func)  # https://github.com/python/mypy/issues/1927


def require_user_group_edit_permission(view_func: ViewFuncT) -> ViewFuncT:
    @require_member_or_admin
    @wraps(view_func)
    def _wrapped_view_func(
        request: HttpRequest, user_profile: UserProfile, *args: object, **kwargs: object
    ) -> HttpResponse:
        if not user_profile.can_edit_user_groups():
            raise JsonableError(_("Insufficient permission"))
        return view_func(request, user_profile, *args, **kwargs)

    return cast(ViewFuncT, _wrapped_view_func)  # https://github.com/python/mypy/issues/1927


# This API endpoint is used only for the mobile apps.  It is part of a
# workaround for the fact that React Native doesn't support setting
# HTTP basic authentication headers.
def authenticated_uploads_api_view(
    skip_rate_limiting: bool = False,
) -> Callable[[Callable[..., HttpResponse]], Callable[..., HttpResponse]]:
    def _wrapped_view_func(view_func: Callable[..., HttpResponse]) -> Callable[..., HttpResponse]:
        @csrf_exempt
        @has_request_variables
        @wraps(view_func)
        def _wrapped_func_arguments(
            request: HttpRequest, api_key: str = REQ(), *args: object, **kwargs: object
        ) -> HttpResponse:
            user_profile = validate_api_key(request, None, api_key, False)
            if not skip_rate_limiting:
                limited_func = rate_limit()(view_func)
            else:
                limited_func = view_func
            return limited_func(request, user_profile, *args, **kwargs)

        return _wrapped_func_arguments

    return _wrapped_view_func


# A more REST-y authentication decorator, using, in particular, HTTP basic
# authentication.
#
# If webhook_client_name is specific, the request is a webhook view
# with that string as the basis for the client string.
def authenticated_rest_api_view(
    *,
    webhook_client_name: Optional[str] = None,
    allow_webhook_access: bool = False,
    skip_rate_limiting: bool = False,
) -> Callable[[Callable[..., HttpResponse]], Callable[..., HttpResponse]]:
    if webhook_client_name is not None:
        allow_webhook_access = True

    def _wrapped_view_func(view_func: Callable[..., HttpResponse]) -> Callable[..., HttpResponse]:
        @csrf_exempt
        @wraps(view_func)
        def _wrapped_func_arguments(
            request: HttpRequest, *args: object, **kwargs: object
        ) -> HttpResponse:
            # First try block attempts to get the credentials we need to do authentication
            try:
                # Grab the base64-encoded authentication string, decode it, and split it into
                # the email and API key
                auth_type, credentials = request.META["HTTP_AUTHORIZATION"].split()
                # case insensitive per RFC 1945
                if auth_type.lower() != "basic":
                    raise JsonableError(_("This endpoint requires HTTP basic authentication."))
                role, api_key = base64.b64decode(credentials).decode().split(":")
            except ValueError:
                return json_unauthorized(_("Invalid authorization header for basic auth"))
            except KeyError:
                return json_unauthorized(_("Missing authorization header for basic auth"))

            # Now we try to do authentication or die
            try:
                # profile is a Union[UserProfile, RemoteZulipServer]
                profile = validate_api_key(
                    request,
                    role,
                    api_key,
                    allow_webhook_access=allow_webhook_access,
                    client_name=full_webhook_client_name(webhook_client_name),
                )
            except JsonableError as e:
                return json_unauthorized(e.msg)
            try:
                if not skip_rate_limiting:
                    # Apply rate limiting
                    target_view_func = rate_limit()(view_func)
                else:
                    target_view_func = view_func
                return target_view_func(request, profile, *args, **kwargs)
            except Exception as err:
                if not webhook_client_name:
                    raise err
                if isinstance(err, JsonableError) and not isinstance(
                    err, WebhookError
                ):  # nocoverage
                    raise err

                if isinstance(err, WebhookError):
                    err.webhook_name = webhook_client_name
                log_exception_to_webhook_logger(err)
                raise err

        return _wrapped_func_arguments

    return _wrapped_view_func


def process_as_post(view_func: ViewFuncT) -> ViewFuncT:
    @wraps(view_func)
    def _wrapped_view_func(request: HttpRequest, *args: object, **kwargs: object) -> HttpResponse:
        # Adapted from django/http/__init__.py.
        # So by default Django doesn't populate request.POST for anything besides
        # POST requests. We want this dict populated for PATCH/PUT, so we have to
        # do it ourselves.
        #
        # This will not be required in the future, a bug will be filed against
        # Django upstream.

        if not request.POST:
            # Only take action if POST is empty.
            if request.META.get("CONTENT_TYPE", "").startswith("multipart"):
                # Note that request._files is just the private attribute that backs the
                # FILES property, so we are essentially setting request.FILES here.  (In
                # Django 1.5 FILES was still a read-only property.)
                request.POST, request._files = MultiPartParser(
                    request.META,
                    BytesIO(request.body),
                    request.upload_handlers,
                    request.encoding,
                ).parse()
            else:
                request.POST = QueryDict(request.body, encoding=request.encoding)

        return view_func(request, *args, **kwargs)

    return cast(ViewFuncT, _wrapped_view_func)  # https://github.com/python/mypy/issues/1927


def authenticate_log_and_execute_json(
    request: HttpRequest,
    view_func: ViewFuncT,
    *args: object,
    skip_rate_limiting: bool = False,
    allow_unauthenticated: bool = False,
    **kwargs: object,
) -> HttpResponse:
    if not skip_rate_limiting:
        limited_view_func = rate_limit()(view_func)
    else:
        limited_view_func = view_func

    if not request.user.is_authenticated:
        if not allow_unauthenticated:
            return json_unauthorized()

        process_client(
            request,
            request.user,
            is_browser_view=True,
            skip_update_user_activity=True,
            query=view_func.__name__,
        )
        return limited_view_func(request, request.user, *args, **kwargs)

    user_profile = request.user
    validate_account_and_subdomain(request, user_profile)

    if user_profile.is_incoming_webhook:
        raise JsonableError(_("Webhook bots can only access webhooks"))

    process_client(request, user_profile, is_browser_view=True, query=view_func.__name__)
    return limited_view_func(request, user_profile, *args, **kwargs)


# Checks if the user is logged in.  If not, return an error (the
# @login_required behavior of redirecting to a login page doesn't make
# sense for json views)
def authenticated_json_view(
    view_func: Callable[..., HttpResponse],
    skip_rate_limiting: bool = False,
    allow_unauthenticated: bool = False,
) -> Callable[..., HttpResponse]:
    @wraps(view_func)
    def _wrapped_view_func(request: HttpRequest, *args: object, **kwargs: object) -> HttpResponse:
        return authenticate_log_and_execute_json(
            request,
            view_func,
            *args,
            skip_rate_limiting=skip_rate_limiting,
            allow_unauthenticated=allow_unauthenticated,
            **kwargs,
        )

    return _wrapped_view_func


def is_local_addr(addr: str) -> bool:
    return addr in ("127.0.0.1", "::1")


# These views are used by the main Django server to notify the Tornado server
# of events.  We protect them from the outside world by checking a shared
# secret, and also the originating IP (for now).
def authenticate_notify(request: HttpRequest) -> bool:
    return (
        is_local_addr(request.META["REMOTE_ADDR"])
        and request.POST.get("secret") == settings.SHARED_SECRET
    )


def client_is_exempt_from_rate_limiting(request: HttpRequest) -> bool:

    # Don't rate limit requests from Django that come from our own servers,
    # and don't rate-limit dev instances
    client = RequestNotes.get_notes(request).client
    return (client is not None and client.name.lower() == "internal") and (
        is_local_addr(request.META["REMOTE_ADDR"]) or settings.DEBUG_RATE_LIMITING
    )


def internal_notify_view(
    is_tornado_view: bool,
) -> Callable[[ViewFuncT], Callable[..., HttpResponse]]:
    # The typing here could be improved by using the extended Callable types:
    # https://mypy.readthedocs.io/en/stable/additional_features.html#extended-callable-types
    """Used for situations where something running on the Zulip server
    needs to make a request to the (other) Django/Tornado processes running on
    the server."""

    def _wrapped_view_func(view_func: ViewFuncT) -> Callable[..., HttpResponse]:
        @csrf_exempt
        @require_post
        @wraps(view_func)
        def _wrapped_func_arguments(
            request: HttpRequest, *args: object, **kwargs: object
        ) -> HttpResponse:
            if not authenticate_notify(request):
                raise AccessDeniedError()
            request_notes = RequestNotes.get_notes(request)
            is_tornado_request = request_notes.tornado_handler is not None
            # These next 2 are not security checks; they are internal
            # assertions to help us find bugs.
            if is_tornado_view and not is_tornado_request:
                raise RuntimeError("Tornado notify view called with no Tornado handler")
            if not is_tornado_view and is_tornado_request:
                raise RuntimeError("Django notify view called with Tornado handler")
            request_notes.requestor_for_logs = "internal"
            return view_func(request, *args, **kwargs)

        return _wrapped_func_arguments

    return _wrapped_view_func


def to_utc_datetime(timestamp: str) -> datetime.datetime:
    return timestamp_to_datetime(float(timestamp))


def statsd_increment(counter: str, val: int = 1) -> Callable[[FuncT], FuncT]:
    """Increments a statsd counter on completion of the
    decorated function.

    Pass the name of the counter to this decorator-returning function."""

    def wrapper(func: FuncT) -> FuncT:
        @wraps(func)
        def wrapped_func(*args: object, **kwargs: object) -> object:
            ret = func(*args, **kwargs)
            statsd.incr(counter, val)
            return ret

        return cast(FuncT, wrapped_func)  # https://github.com/python/mypy/issues/1927

    return wrapper


def rate_limit_user(request: HttpRequest, user: UserProfile, domain: str) -> None:
    """Returns whether or not a user was rate limited. Will raise a RateLimited exception
    if the user has been rate limited, otherwise returns and modifies request to contain
    the rate limit information"""

    RateLimitedUser(user, domain=domain).rate_limit_request(request)


@cache_with_key(lambda: "tor_ip_addresses:", timeout=60 * 60)
@circuit(failure_threshold=2, recovery_timeout=60 * 10)
def get_tor_ips() -> Set[str]:
    if not settings.RATE_LIMIT_TOR_TOGETHER:
        return set()

    # Cron job in /etc/cron.d/fetch-for-exit-nodes fetches this
    # hourly; we cache it in memcached to prevent going to disk on
    # every unauth'd request.  In case of failures to read, we
    # circuit-break so 2 failures cause a 10-minute backoff.

    with open(settings.TOR_EXIT_NODE_FILE_PATH, "rb") as f:
        exit_node_list = orjson.loads(f.read())

    # This should always be non-empty; if it's empty, assume something
    # went wrong with writing and treat it as a non-existent file.
    # Circuit-breaking will ensure that we back off on re-reading the
    # file.
    if len(exit_node_list) == 0:
        raise OSError("File is empty")

    return set(exit_node_list)


def rate_limit_ip(request: HttpRequest, ip_addr: str, domain: str) -> None:
    RateLimitedIPAddr(ip_addr, domain=domain).rate_limit_request(request)


def rate_limit_request_by_ip(request: HttpRequest, domain: str) -> None:
    # REMOTE_ADDR is set by SetRemoteAddrFromRealIpHeader in conjunction
    # with the nginx configuration to guarantee this to be *the* correct
    # IP address to use - without worrying we'll grab the IP of a proxy.
    ip_addr = request.META["REMOTE_ADDR"]
    assert ip_addr

    try:
        # We lump all TOR exit nodes into one bucket; this prevents
        # abuse from TOR, while still allowing some access to these
        # endpoints for legitimate users.  Checking for local
        # addresses is a shortcut somewhat for ease of testing without
        # mocking the TOR endpoint in every test.
        if is_local_addr(ip_addr):
            pass
        elif ip_addr in get_tor_ips():
            ip_addr = "tor-exit-node"
    except (OSError, CircuitBreakerError) as err:
        # In the event that we can't get an updated list of TOR exit
        # nodes, assume the IP is _not_ one, and leave it unchanged.
        # We log a warning so that this endpoint being taken out of
        # service doesn't silently remove this functionality.
        rate_limiter_logger.warning("Failed to fetch TOR exit node list: %s", err)
        pass
    rate_limit_ip(request, ip_addr, domain=domain)


def rate_limit_remote_server(
    request: HttpRequest, remote_server: "RemoteZulipServer", domain: str
) -> None:
    try:
        RateLimitedRemoteZulipServer(remote_server, domain=domain).rate_limit_request(request)
    except RateLimited as e:
        rate_limiter_logger.warning(
            "Remote server %s exceeded rate limits on domain %s", remote_server, domain
        )
        raise e


def rate_limit() -> Callable[[ViewFuncT], ViewFuncT]:
    """Rate-limits a view. Returns a decorator"""

    def wrapper(func: ViewFuncT) -> ViewFuncT:
        @wraps(func)
        def wrapped_func(request: HttpRequest, *args: object, **kwargs: object) -> HttpResponse:

            # It is really tempting to not even wrap our original function
            # when settings.RATE_LIMITING is False, but it would make
            # for awkward unit testing in some situations.
            if not settings.RATE_LIMITING:
                return func(request, *args, **kwargs)

            if client_is_exempt_from_rate_limiting(request):
                return func(request, *args, **kwargs)

            user = request.user

            if isinstance(user, AnonymousUser):
                rate_limit_request_by_ip(request, domain="api_by_ip")
                return func(request, *args, **kwargs)
            elif settings.ZILENCER_ENABLED and isinstance(user, RemoteZulipServer):
                rate_limit_remote_server(request, user, domain="api_by_remote_server")
            else:
                assert isinstance(user, UserProfile)
                rate_limit_user(request, user, domain="api_by_user")

            return func(request, *args, **kwargs)

        return cast(ViewFuncT, wrapped_func)  # https://github.com/python/mypy/issues/1927

    return wrapper


def return_success_on_head_request(view_func: ViewFuncT) -> ViewFuncT:
    @wraps(view_func)
    def _wrapped_view_func(request: HttpRequest, *args: object, **kwargs: object) -> HttpResponse:
        if request.method == "HEAD":
            return json_success(request)
        return view_func(request, *args, **kwargs)

    return cast(ViewFuncT, _wrapped_view_func)  # https://github.com/python/mypy/issues/1927


def zulip_otp_required(
    redirect_field_name: str = "next",
    login_url: str = settings.HOME_NOT_LOGGED_IN,
) -> Callable[[ViewFuncT], ViewFuncT]:
    """
    The reason we need to create this function is that the stock
    otp_required decorator doesn't play well with tests. We cannot
    enable/disable if_configured parameter during tests since the decorator
    retains its value due to closure.

    Similar to :func:`~django.contrib.auth.decorators.login_required`, but
    requires the user to be :term:`verified`. By default, this redirects users
    to :setting:`OTP_LOGIN_URL`.
    """

    def test(user: UserProfile) -> bool:
        """
        :if_configured: If ``True``, an authenticated user with no confirmed
        OTP devices will be allowed. Also, non-authenticated users will be
        allowed as spectator users. Default is ``False``. If ``False``,
        2FA will not do any authentication.
        """
        if_configured = settings.TWO_FACTOR_AUTHENTICATION_ENABLED
        if not if_configured:
            return True

        # User has completed 2FA verification
        if user.is_verified():
            return True

        # This request is unauthenticated (logged-out) access; 2FA is
        # not required or possible.
        #
        # TODO: Add a test for 2FA-enabled with web-public views.
        if not user.is_authenticated:  # nocoverage
            return True

        # If the user doesn't have 2FA set up, we can't enforce 2FA.
        if not user_has_device(user):
            return True

        # User has configured 2FA and is not verified, so the user
        # fails the test (and we should redirect to the 2FA view).
        return False

    decorator = django_user_passes_test(
        test, login_url=login_url, redirect_field_name=redirect_field_name
    )

    return decorator


def add_google_analytics_context(context: Dict[str, object]) -> None:
    if settings.GOOGLE_ANALYTICS_ID is not None:  # nocoverage
        page_params = context.setdefault("page_params", {})
        assert isinstance(page_params, dict)
        page_params["google_analytics_id"] = settings.GOOGLE_ANALYTICS_ID


def add_google_analytics(view_func: ViewFuncT) -> ViewFuncT:
    @wraps(view_func)
    def _wrapped_view_func(request: HttpRequest, *args: object, **kwargs: object) -> HttpResponse:
        response = view_func(request, *args, **kwargs)
        if isinstance(response, SimpleTemplateResponse):
            if response.context_data is None:
                response.context_data = {}
            add_google_analytics_context(response.context_data)
        elif response.status_code == 200:  # nocoverage
            raise TypeError("add_google_analytics requires a TemplateResponse")
        return response

    return cast(ViewFuncT, _wrapped_view_func)  # https://github.com/python/mypy/issues/1927
