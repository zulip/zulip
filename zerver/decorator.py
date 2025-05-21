import base64
import logging
from collections.abc import Callable, Sequence
from datetime import datetime
from functools import wraps
from io import BytesIO
from typing import TYPE_CHECKING, Concatenate, TypeVar, cast, overload
from urllib.parse import urlsplit

import django_otp
from django.conf import settings
from django.contrib.auth import REDIRECT_FIELD_NAME, authenticate
from django.contrib.auth import login as django_login
from django.contrib.auth.decorators import user_passes_test as django_user_passes_test
from django.contrib.auth.models import AbstractBaseUser, AnonymousUser
from django.contrib.auth.views import redirect_to_login
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect, QueryDict
from django.http.multipartparser import MultiPartParser
from django.shortcuts import resolve_url
from django.template.response import SimpleTemplateResponse, TemplateResponse
from django.utils.crypto import constant_time_compare
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt
from django_otp import user_has_device
from two_factor.utils import default_device
from typing_extensions import ParamSpec

from zerver.context_processors import get_valid_realm_from_request
from zerver.lib.exceptions import (
    AccessDeniedError,
    AnomalousWebhookPayloadError,
    InvalidAPIKeyError,
    InvalidAPIKeyFormatError,
    InvalidJSONError,
    JsonableError,
    OrganizationAdministratorRequiredError,
    OrganizationMemberRequiredError,
    OrganizationOwnerRequiredError,
    RealmDeactivatedError,
    UnauthorizedError,
    UnsupportedWebhookEventTypeError,
    UserDeactivatedError,
    WebhookError,
)
from zerver.lib.queue import queue_json_publish_rollback_unsafe
from zerver.lib.rate_limiter import is_local_addr, rate_limit_request_by_ip, rate_limit_user
from zerver.lib.request import RequestNotes
from zerver.lib.response import json_method_not_allowed
from zerver.lib.subdomains import get_subdomain, user_matches_subdomain
from zerver.lib.timestamp import datetime_to_timestamp, timestamp_to_datetime
from zerver.lib.typed_endpoint import typed_endpoint
from zerver.lib.users import is_2fa_verified
from zerver.lib.utils import has_api_key_format
from zerver.lib.webhooks.common import (
    MissingHTTPEventHeaderError,
    notify_bot_owner_about_invalid_json,
)
from zerver.models import UserProfile
from zerver.models.clients import get_client
from zerver.models.users import get_user_profile_by_api_key

if TYPE_CHECKING:
    from django.http.request import _ImmutableQueryDict

webhook_logger = logging.getLogger("zulip.zerver.webhooks")
webhook_unsupported_events_logger = logging.getLogger("zulip.zerver.webhooks.unsupported")
webhook_anomalous_payloads_logger = logging.getLogger("zulip.zerver.webhooks.anomalous")

ParamT = ParamSpec("ParamT")
ReturnT = TypeVar("ReturnT")


def update_user_activity(
    request: HttpRequest, user_profile: UserProfile, query: str | None
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

    queue_name = "user_activity"
    if settings.USER_ACTIVITY_SHARDS > 1:  # nocoverage
        shard_id = user_profile.id % settings.USER_ACTIVITY_SHARDS + 1
        queue_name = f"user_activity_shard{shard_id}"

    queue_json_publish_rollback_unsafe(queue_name, event, lambda event: None)


# Based on django.views.decorators.http.require_http_methods
def require_post(
    func: Callable[Concatenate[HttpRequest, ParamT], HttpResponse],
) -> Callable[Concatenate[HttpRequest, ParamT], HttpResponse]:
    # Arguments before ParamT needs to be positional-only as required by Concatenate
    @wraps(func)
    def wrapper(
        request: HttpRequest, /, *args: ParamT.args, **kwargs: ParamT.kwargs
    ) -> HttpResponse:
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
                    request, "4xx.html", context={"status_code": 405}, status=405
                )
        return func(request, *args, **kwargs)

    return wrapper


def require_realm_owner(
    func: Callable[Concatenate[HttpRequest, UserProfile, ParamT], HttpResponse],
) -> Callable[Concatenate[HttpRequest, UserProfile, ParamT], HttpResponse]:
    @wraps(func)
    def wrapper(
        request: HttpRequest,
        user_profile: UserProfile,
        /,
        *args: ParamT.args,
        **kwargs: ParamT.kwargs,
    ) -> HttpResponse:
        if not user_profile.is_realm_owner:
            raise OrganizationOwnerRequiredError
        return func(request, user_profile, *args, **kwargs)

    return wrapper


def require_realm_admin(
    func: Callable[Concatenate[HttpRequest, UserProfile, ParamT], HttpResponse],
) -> Callable[Concatenate[HttpRequest, UserProfile, ParamT], HttpResponse]:
    @wraps(func)
    def wrapper(
        request: HttpRequest,
        user_profile: UserProfile,
        /,
        *args: ParamT.args,
        **kwargs: ParamT.kwargs,
    ) -> HttpResponse:
        if not user_profile.is_realm_admin:
            raise OrganizationAdministratorRequiredError
        return func(request, user_profile, *args, **kwargs)

    return wrapper


def check_if_user_can_manage_default_streams(
    func: Callable[Concatenate[HttpRequest, UserProfile, ParamT], HttpResponse],
) -> Callable[Concatenate[HttpRequest, UserProfile, ParamT], HttpResponse]:
    @wraps(func)
    def wrapper(
        request: HttpRequest,
        user_profile: UserProfile,
        /,
        *args: ParamT.args,
        **kwargs: ParamT.kwargs,
    ) -> HttpResponse:
        if not user_profile.can_manage_default_streams():
            raise OrganizationAdministratorRequiredError
        return func(request, user_profile, *args, **kwargs)

    return wrapper


def require_organization_member(
    func: Callable[Concatenate[HttpRequest, UserProfile, ParamT], HttpResponse],
) -> Callable[Concatenate[HttpRequest, UserProfile, ParamT], HttpResponse]:
    @wraps(func)
    def wrapper(
        request: HttpRequest,
        user_profile: UserProfile,
        /,
        *args: ParamT.args,
        **kwargs: ParamT.kwargs,
    ) -> HttpResponse:
        if user_profile.role > UserProfile.ROLE_MEMBER:
            raise OrganizationMemberRequiredError
        return func(request, user_profile, *args, **kwargs)

    return wrapper


def require_billing_access(
    func: Callable[Concatenate[HttpRequest, UserProfile, ParamT], HttpResponse],
) -> Callable[Concatenate[HttpRequest, UserProfile, ParamT], HttpResponse]:
    @wraps(func)
    def wrapper(
        request: HttpRequest,
        user_profile: UserProfile,
        /,
        *args: ParamT.args,
        **kwargs: ParamT.kwargs,
    ) -> HttpResponse:
        if not user_profile.has_billing_access:
            raise JsonableError(_("Insufficient permission"))
        return func(request, user_profile, *args, **kwargs)

    return wrapper


def process_client(
    request: HttpRequest,
    user: UserProfile | AnonymousUser | None = None,
    *,
    is_browser_view: bool = False,
    client_name: str | None = None,
    query: str | None = None,
) -> None:
    """The optional user parameter requests that a UserActivity row be
    created/updated to record this request.

    In particular, unauthenticate requests and those authenticated to
    a non-user object like RemoteZulipServer should not pass the
    `user` parameter.
    """
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
    if user is not None and user.is_authenticated:
        update_user_activity(request, user, query)


def validate_api_key(
    request: HttpRequest,
    role: str | None,
    api_key: str,
    allow_webhook_access: bool = False,
    client_name: str | None = None,
) -> UserProfile:
    # Remove whitespace to protect users from trivial errors.
    api_key = api_key.strip()
    if role is not None:
        role = role.strip()

    user_profile = access_user_by_api_key(request, api_key, email=role)
    if user_profile.is_incoming_webhook and not allow_webhook_access:
        raise JsonableError(_("This API is not available to incoming webhook bots."))

    request.user = user_profile
    process_client(request, user_profile, client_name=client_name)

    return user_profile


def validate_account_and_subdomain(request: HttpRequest, user_profile: UserProfile) -> None:
    if user_profile.realm.deactivated:
        raise RealmDeactivatedError
    if not user_profile.is_active:
        raise UserDeactivatedError

    remote_addr = request.META.get("REMOTE_ADDR", None)
    server_name = request.META.get("SERVER_NAME", None)

    if (
        settings.RUNNING_INSIDE_TORNADO
        and remote_addr == "127.0.0.1"
        and server_name == "127.0.0.1"
    ):  # nocoverage
        # We're accessing Tornado from and to localhost (aka spoofing
        # a request as the user)
        return
    if remote_addr == "127.0.0.1" and server_name == "localhost":  # nocoverage
        # For tusd hook requests.
        return

    if user_matches_subdomain(get_subdomain(request), user_profile):
        return

    logging.warning(
        "User %s (%s) attempted to access API on wrong subdomain (%s)",
        user_profile.delivery_email,
        user_profile.realm.subdomain,
        get_subdomain(request),
    )
    raise JsonableError(_("Account is not associated with this subdomain"))


def access_user_by_api_key(
    request: HttpRequest, api_key: str, email: str | None = None
) -> UserProfile:
    if not has_api_key_format(api_key):
        raise InvalidAPIKeyFormatError

    try:
        user_profile = get_user_profile_by_api_key(api_key)
    except UserProfile.DoesNotExist:
        raise InvalidAPIKeyError
    if email is not None and email.lower() != user_profile.delivery_email.lower():
        # This covers the case that the API key is correct, but for a
        # different user.  We may end up wanting to relaxing this
        # constraint or give a different error message in the future.
        raise InvalidAPIKeyError

    validate_account_and_subdomain(request, user_profile)

    return user_profile


def log_unsupported_webhook_event(request: HttpRequest, summary: str) -> None:
    # This helper is primarily used by some of our more complicated
    # webhook integrations (e.g. GitHub) that need to log an unsupported
    # event based on attributes nested deep within a complicated JSON
    # payload. In such cases, the error message we want to log may not
    # really fit what a regular UnsupportedWebhookEventTypeError exception
    # represents.
    extra = {"request": request}
    webhook_unsupported_events_logger.exception(summary, stack_info=True, extra=extra)


def log_exception_to_webhook_logger(request: HttpRequest, err: Exception) -> None:
    extra = {"request": request}

    # We deliberately skip logging this client error, as it results from a malformed request
    # and doesn't indicate an issue on our end.
    if isinstance(err, MissingHTTPEventHeaderError):
        return

    # We intentionally omit the stack_info for these events, where
    # they are intentionally raised, and the stack_info between that
    # point and this one is not interesting.
    if isinstance(err, AnomalousWebhookPayloadError):
        webhook_anomalous_payloads_logger.exception(err, extra=extra)
    elif isinstance(err, UnsupportedWebhookEventTypeError):
        webhook_unsupported_events_logger.exception(err, extra=extra)
    else:
        webhook_logger.exception(err, stack_info=True, extra=extra)


def full_webhook_client_name(raw_client_name: str | None = None) -> str | None:
    if raw_client_name is None:
        return None
    return f"Zulip{raw_client_name}Webhook"


# Use this for webhook views that don't get an email passed in.
def webhook_view(
    webhook_client_name: str,
    notify_bot_owner_on_invalid_json: bool = True,
    all_event_types: Sequence[str] | None = None,
) -> Callable[[Callable[..., HttpResponse]], Callable[..., HttpResponse]]:
    # Unfortunately, callback protocols are insufficient for this:
    # https://mypy.readthedocs.io/en/stable/protocols.html#callback-protocols
    # Variadic generics are necessary: https://github.com/python/typing/issues/193
    def _wrapped_view_func(view_func: Callable[..., HttpResponse]) -> Callable[..., HttpResponse]:
        @csrf_exempt
        @wraps(view_func)
        @typed_endpoint
        def _wrapped_func_arguments(
            request: HttpRequest, /, *args: object, api_key: str, **kwargs: object
        ) -> HttpResponse:
            user_profile = validate_api_key(
                request,
                None,
                api_key,
                allow_webhook_access=True,
                client_name=full_webhook_client_name(webhook_client_name),
            )

            request_notes = RequestNotes.get_notes(request)
            request_notes.is_webhook_view = True

            rate_limit_user(request, user_profile, domain="api_by_user")
            try:
                return view_func(request, user_profile, *args, **kwargs)
            except Exception as err:
                if not isinstance(err, JsonableError):
                    # An unexpected exception of some form -- log it
                    log_exception_to_webhook_logger(request, err)
                elif isinstance(err, WebhookError):
                    # Anything explicitly a webhook error deserves to
                    # go to the webhook logs.  The error middleware
                    # skips logging these exceptions a second time.
                    err.webhook_name = webhook_client_name
                    log_exception_to_webhook_logger(request, err)
                elif isinstance(err, InvalidJSONError) and notify_bot_owner_on_invalid_json:
                    # Invalid JSON is not notable for the logs -- it's
                    # the sender's fault, so tell the owner
                    notify_bot_owner_about_invalid_json(user_profile, webhook_client_name)

                raise err

        # Store the event types registered for this webhook as an attribute, which can be access
        # later conveniently in zerver.lib.test_classes.WebhookTestCase.
        _wrapped_func_arguments._all_event_types = all_event_types  # type: ignore[attr-defined] # custom attribute
        return _wrapped_func_arguments

    return _wrapped_view_func


def zulip_redirect_to_login(
    request: HttpRequest,
    login_url: str | None = None,
    redirect_field_name: str = REDIRECT_FIELD_NAME,
) -> HttpResponseRedirect:
    path = request.build_absolute_uri()
    resolved_login_url = resolve_url(login_url or settings.LOGIN_URL)
    # If the login URL is the same scheme and net location then just
    # use the path as the "next" url.
    login_scheme, login_netloc = urlsplit(resolved_login_url)[:2]
    current_scheme, current_netloc = urlsplit(path)[:2]
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
    login_url: str | None = None,
    redirect_field_name: str = REDIRECT_FIELD_NAME,
) -> Callable[
    [Callable[Concatenate[HttpRequest, ParamT], HttpResponse]],
    Callable[Concatenate[HttpRequest, ParamT], HttpResponse],
]:
    """
    Decorator for views that checks that the user passes the given test,
    redirecting to the log-in page if necessary. The test should be a callable
    that takes the user object and returns True if the user passes.
    """

    def decorator(
        view_func: Callable[Concatenate[HttpRequest, ParamT], HttpResponse],
    ) -> Callable[Concatenate[HttpRequest, ParamT], HttpResponse]:
        @wraps(view_func)
        def _wrapped_view(
            request: HttpRequest, /, *args: ParamT.args, **kwargs: ParamT.kwargs
        ) -> HttpResponse:
            if test_func(request):
                return view_func(request, *args, **kwargs)
            return zulip_redirect_to_login(request, login_url, redirect_field_name)

        return _wrapped_view

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

    # As a hardening measure, pass the user_profile through the dummy backend,
    # which does the minimal validation that the user is allowed to log in.
    # This, and stronger validation, should have already been done by the
    # caller, so we raise an AssertionError if this doesn't work as expected.
    # This is to prevent misuse of this function, as it would pose a major
    # security issue.
    realm = get_valid_realm_from_request(request)
    validated_user_profile = authenticate(
        request=request, username=user_profile.delivery_email, realm=realm, use_dummy_backend=True
    )
    if validated_user_profile is None or validated_user_profile != user_profile:
        raise AssertionError("do_login called for a user_profile that shouldn't be able to log in")

    assert isinstance(validated_user_profile, UserProfile)

    django_login(request, validated_user_profile)
    RequestNotes.get_notes(
        request
    ).requester_for_logs = validated_user_profile.format_requester_for_logs()
    process_client(request, validated_user_profile, is_browser_view=True)
    if settings.TWO_FACTOR_AUTHENTICATION_ENABLED:
        # Log in with two factor authentication as well.
        do_two_factor_login(request, validated_user_profile)


def log_view_func(
    view_func: Callable[Concatenate[HttpRequest, ParamT], HttpResponse],
) -> Callable[Concatenate[HttpRequest, ParamT], HttpResponse]:
    @wraps(view_func)
    def _wrapped_view_func(
        request: HttpRequest, /, *args: ParamT.args, **kwargs: ParamT.kwargs
    ) -> HttpResponse:
        RequestNotes.get_notes(request).query = view_func.__name__
        return view_func(request, *args, **kwargs)

    return _wrapped_view_func


def add_logging_data(
    view_func: Callable[Concatenate[HttpRequest, ParamT], HttpResponse],
) -> Callable[Concatenate[HttpRequest, ParamT], HttpResponse]:
    @wraps(view_func)
    def _wrapped_view_func(
        request: HttpRequest, /, *args: ParamT.args, **kwargs: ParamT.kwargs
    ) -> HttpResponse:
        process_client(request, request.user, is_browser_view=True, query=view_func.__name__)

        if request.user.is_authenticated:
            rate_limit_user(request, request.user, domain="api_by_user")
        else:
            rate_limit_request_by_ip(request, domain="api_by_ip")

        return view_func(request, *args, **kwargs)

    return _wrapped_view_func


def human_users_only(
    view_func: Callable[Concatenate[HttpRequest, ParamT], HttpResponse],
) -> Callable[Concatenate[HttpRequest, ParamT], HttpResponse]:
    @wraps(view_func)
    def _wrapped_view_func(
        request: HttpRequest, /, *args: ParamT.args, **kwargs: ParamT.kwargs
    ) -> HttpResponse:
        assert request.user.is_authenticated
        # Check bot_type here, rather than is_bot, because  the
        # narrow user cache only has that (nullable) type
        if request.user.bot_type is not None:
            raise JsonableError(_("This endpoint does not accept bot requests."))
        return view_func(request, *args, **kwargs)

    return _wrapped_view_func


# Based on Django 1.8's @login_required
@overload
def zulip_login_required(
    function: Callable[Concatenate[HttpRequest, ParamT], HttpResponse],
    redirect_field_name: str = REDIRECT_FIELD_NAME,
    login_url: str = settings.HOME_NOT_LOGGED_IN,
) -> Callable[Concatenate[HttpRequest, ParamT], HttpResponse]: ...
@overload
def zulip_login_required(
    function: None,
    redirect_field_name: str = REDIRECT_FIELD_NAME,
    login_url: str = settings.HOME_NOT_LOGGED_IN,
) -> Callable[
    [Callable[Concatenate[HttpRequest, ParamT], HttpResponse]],
    Callable[Concatenate[HttpRequest, ParamT], HttpResponse],
]: ...
def zulip_login_required(
    function: Callable[Concatenate[HttpRequest, ParamT], HttpResponse] | None = None,
    redirect_field_name: str = REDIRECT_FIELD_NAME,
    login_url: str = settings.HOME_NOT_LOGGED_IN,
) -> (
    Callable[
        [Callable[Concatenate[HttpRequest, ParamT], HttpResponse]],
        Callable[Concatenate[HttpRequest, ParamT], HttpResponse],
    ]
    | Callable[Concatenate[HttpRequest, ParamT], HttpResponse]
):
    actual_decorator = lambda function: user_passes_test(
        logged_in_and_active,
        login_url=login_url,
        redirect_field_name=redirect_field_name,
    )(
        zulip_otp_required_if_logged_in(
            redirect_field_name=redirect_field_name,
            login_url=login_url,
        )(add_logging_data(function))
    )

    if function:
        return actual_decorator(function)
    return actual_decorator  # nocoverage # We don't use this without a function


def web_public_view(
    view_func: Callable[Concatenate[HttpRequest, ParamT], HttpResponse],
    redirect_field_name: str = REDIRECT_FIELD_NAME,
    login_url: str = settings.HOME_NOT_LOGGED_IN,
) -> Callable[Concatenate[HttpRequest, ParamT], HttpResponse]:
    """
    This wrapper adds client info for unauthenticated users but
    forces authenticated users to go through 2fa.
    """
    actual_decorator = lambda view_func: zulip_otp_required_if_logged_in(
        redirect_field_name=redirect_field_name, login_url=login_url
    )(add_logging_data(view_func))

    return actual_decorator(view_func)


def require_server_admin(
    view_func: Callable[Concatenate[HttpRequest, ParamT], HttpResponse],
) -> Callable[Concatenate[HttpRequest, ParamT], HttpResponse]:
    @zulip_login_required
    @wraps(view_func)
    def _wrapped_view_func(
        request: HttpRequest, /, *args: ParamT.args, **kwargs: ParamT.kwargs
    ) -> HttpResponse:
        if not request.user.is_staff:
            return HttpResponseRedirect(settings.HOME_NOT_LOGGED_IN)

        return add_logging_data(view_func)(request, *args, **kwargs)

    return _wrapped_view_func


def require_server_admin_api(
    view_func: Callable[Concatenate[HttpRequest, ParamT], HttpResponse],
) -> Callable[Concatenate[HttpRequest, ParamT], HttpResponse]:
    @zulip_login_required
    @wraps(view_func)
    def _wrapped_view_func(
        request: HttpRequest,
        /,
        *args: ParamT.args,
        **kwargs: ParamT.kwargs,
    ) -> HttpResponse:
        if not request.user.is_staff:
            raise JsonableError(_("Must be an server administrator"))
        return view_func(request, *args, **kwargs)

    return _wrapped_view_func


def require_non_guest_user(
    view_func: Callable[Concatenate[HttpRequest, UserProfile, ParamT], HttpResponse],
) -> Callable[Concatenate[HttpRequest, UserProfile, ParamT], HttpResponse]:
    @wraps(view_func)
    def _wrapped_view_func(
        request: HttpRequest,
        user_profile: UserProfile,
        /,
        *args: ParamT.args,
        **kwargs: ParamT.kwargs,
    ) -> HttpResponse:
        if user_profile.is_guest:
            raise JsonableError(_("Not allowed for guest users"))
        return view_func(request, user_profile, *args, **kwargs)

    return _wrapped_view_func


def require_member_or_admin(
    view_func: Callable[Concatenate[HttpRequest, UserProfile, ParamT], HttpResponse],
) -> Callable[Concatenate[HttpRequest, UserProfile, ParamT], HttpResponse]:
    @wraps(view_func)
    def _wrapped_view_func(
        request: HttpRequest,
        user_profile: UserProfile,
        /,
        *args: ParamT.args,
        **kwargs: ParamT.kwargs,
    ) -> HttpResponse:
        if user_profile.is_guest:
            raise JsonableError(_("Not allowed for guest users"))
        # Check bot_type here, rather than is_bot, because  the
        # narrow user cache only has that (nullable) type
        if user_profile.bot_type is not None:
            raise JsonableError(_("This endpoint does not accept bot requests."))
        return view_func(request, user_profile, *args, **kwargs)

    return _wrapped_view_func


def require_user_group_create_permission(
    view_func: Callable[Concatenate[HttpRequest, UserProfile, ParamT], HttpResponse],
) -> Callable[Concatenate[HttpRequest, UserProfile, ParamT], HttpResponse]:
    @require_member_or_admin
    @wraps(view_func)
    def _wrapped_view_func(
        request: HttpRequest,
        user_profile: UserProfile,
        /,
        *args: ParamT.args,
        **kwargs: ParamT.kwargs,
    ) -> HttpResponse:
        if not user_profile.can_create_user_groups():
            raise JsonableError(_("Insufficient permission"))
        return view_func(request, user_profile, *args, **kwargs)

    return _wrapped_view_func


# This API endpoint is used only for the mobile apps.  It is part of a
# workaround for the fact that React Native doesn't support setting
# HTTP basic authentication headers.
def authenticated_uploads_api_view(
    skip_rate_limiting: bool = False,
) -> Callable[[Callable[..., HttpResponse]], Callable[..., HttpResponse]]:
    def _wrapped_view_func(view_func: Callable[..., HttpResponse]) -> Callable[..., HttpResponse]:
        @csrf_exempt
        @wraps(view_func)
        @typed_endpoint
        def _wrapped_func_arguments(
            request: HttpRequest, /, *args: object, api_key: str, **kwargs: object
        ) -> HttpResponse:
            user_profile = validate_api_key(request, None, api_key, False)
            if not skip_rate_limiting:
                rate_limit_user(request, user_profile, domain="api_by_user")
            return view_func(request, user_profile, *args, **kwargs)

        return _wrapped_func_arguments

    return _wrapped_view_func


def get_basic_credentials(
    request: HttpRequest, beanstalk_email_decode: bool = False
) -> tuple[str, str]:
    """
    Extracts the role and API key as a tuple from the Authorization header
    for HTTP basic authentication.
    """
    try:
        # Grab the base64-encoded authentication string, decode it, and split it into
        # the email and API key
        auth_type, credentials = request.headers["Authorization"].split()
        # case insensitive per RFC 1945
        if auth_type.lower() != "basic":
            raise JsonableError(_("This endpoint requires HTTP basic authentication."))
        role, api_key = base64.b64decode(credentials).decode().split(":")
        if beanstalk_email_decode:
            # Beanstalk's web hook UI rejects URL with a @ in the username section
            # So we ask the user to replace them with %40
            role = role.replace("%40", "@")
    except ValueError:
        raise UnauthorizedError(_("Invalid authorization header for basic auth"))
    except KeyError:
        raise UnauthorizedError(_("Missing authorization header for basic auth"))

    return role, api_key


# A more REST-y authentication decorator, using, in particular, HTTP basic
# authentication.
#
# If webhook_client_name is specific, the request is a webhook view
# with that string as the basis for the client string.
def authenticated_rest_api_view(
    *,
    webhook_client_name: str | None = None,
    allow_webhook_access: bool = False,
    skip_rate_limiting: bool = False,
    beanstalk_email_decode: bool = False,
) -> Callable[
    [Callable[Concatenate[HttpRequest, UserProfile, ParamT], HttpResponse]],
    Callable[Concatenate[HttpRequest, ParamT], HttpResponse],
]:
    if webhook_client_name is not None:
        allow_webhook_access = True

    def _wrapped_view_func(
        view_func: Callable[Concatenate[HttpRequest, UserProfile, ParamT], HttpResponse],
    ) -> Callable[Concatenate[HttpRequest, ParamT], HttpResponse]:
        @csrf_exempt
        @wraps(view_func)
        def _wrapped_func_arguments(
            request: HttpRequest, /, *args: ParamT.args, **kwargs: ParamT.kwargs
        ) -> HttpResponse:
            role, api_key = get_basic_credentials(
                request, beanstalk_email_decode=beanstalk_email_decode
            )

            # Now we try to do authentication or die
            try:
                user_profile = validate_api_key(
                    request,
                    role,
                    api_key,
                    allow_webhook_access=allow_webhook_access,
                    client_name=full_webhook_client_name(webhook_client_name),
                )

                if webhook_client_name is not None:
                    request_notes = RequestNotes.get_notes(request)
                    request_notes.is_webhook_view = True

            except JsonableError as e:
                raise UnauthorizedError(e.msg)
            try:
                if not skip_rate_limiting:
                    rate_limit_user(request, user_profile, domain="api_by_user")
                return view_func(request, user_profile, *args, **kwargs)
            except Exception as err:
                if not webhook_client_name:
                    raise err

                if not isinstance(err, JsonableError):
                    # An unexpected exception of some form -- log it
                    log_exception_to_webhook_logger(request, err)
                elif isinstance(err, WebhookError):
                    # Anything explicitly a webhook error deserves to
                    # go to the webhook logs.  The error middleware
                    # skips logging these exceptions a second time.
                    err.webhook_name = webhook_client_name
                    log_exception_to_webhook_logger(request, err)

                raise err

        return _wrapped_func_arguments

    return _wrapped_view_func


def process_as_post(
    view_func: Callable[Concatenate[HttpRequest, ParamT], HttpResponse],
) -> Callable[Concatenate[HttpRequest, ParamT], HttpResponse]:
    @wraps(view_func)
    def _wrapped_view_func(
        request: HttpRequest, /, *args: ParamT.args, **kwargs: ParamT.kwargs
    ) -> HttpResponse:
        # Adapted from django/http/__init__.py.
        # So by default Django doesn't populate request.POST for anything besides
        # POST requests. We want this dict populated for PATCH/PUT, so we have to
        # do it ourselves.
        #
        # This will not be required in the future, a bug will be filed against
        # Django upstream.

        if not request.POST:
            # Only take action if POST is empty.
            if request.content_type == "multipart/form-data":
                POST, files = MultiPartParser(
                    request.META,
                    BytesIO(request.body),
                    request.upload_handlers,
                    request.encoding,
                ).parse()
                # request.POST is an immutable QueryDict in most cases, while
                # MultiPartParser.parse() returns a mutable instance of QueryDict.
                # This can be fix when https://code.djangoproject.com/ticket/17235
                # is resolved.
                # django-stubs makes QueryDict of different mutabilities incompatible
                # types. There is no way to acknowledge the django-stubs mypy plugin
                # the change of POST's mutability, so we bypass the check with cast.
                # See also: https://github.com/typeddjango/django-stubs/pull/925#issue-1206399444
                POST._mutable = False
                request.POST = cast("_ImmutableQueryDict", POST)
                request.FILES.update(files)
            elif request.content_type == "application/x-www-form-urlencoded":
                request.POST = QueryDict(request.body, encoding=request.encoding)

        return view_func(request, *args, **kwargs)

    return _wrapped_view_func


def public_json_view(
    view_func: Callable[
        Concatenate[HttpRequest, UserProfile | AnonymousUser, ParamT], HttpResponse
    ],
    skip_rate_limiting: bool = False,
) -> Callable[Concatenate[HttpRequest, ParamT], HttpResponse]:
    @wraps(view_func)
    def _wrapped_view_func(
        request: HttpRequest,
        /,
        *args: ParamT.args,
        **kwargs: ParamT.kwargs,
    ) -> HttpResponse:
        if request.user.is_authenticated:
            # For authenticated users, process the request with their permissions.
            return authenticated_json_view(view_func, skip_rate_limiting=skip_rate_limiting)(
                request, *args, **kwargs
            )

        # Otherwise, process the request for a logged-out visitor.
        if not skip_rate_limiting:
            rate_limit_request_by_ip(request, domain="api_by_ip")

        process_client(
            request,
            is_browser_view=True,
            query=view_func.__name__,
        )
        return view_func(request, request.user, *args, **kwargs)

    return _wrapped_view_func


# Checks if the user is logged in.  If not, return an error (the
# @login_required behavior of redirecting to a login page doesn't make
# sense for json views)
def authenticated_json_view(
    view_func: Callable[Concatenate[HttpRequest, UserProfile, ParamT], HttpResponse],
    skip_rate_limiting: bool = False,
) -> Callable[Concatenate[HttpRequest, ParamT], HttpResponse]:
    @wraps(view_func)
    def _wrapped_view_func(
        request: HttpRequest,
        /,
        *args: ParamT.args,
        **kwargs: ParamT.kwargs,
    ) -> HttpResponse:
        if not request.user.is_authenticated:
            raise UnauthorizedError

        user_profile = request.user
        if not skip_rate_limiting:
            rate_limit_user(request, user_profile, domain="api_by_user")

        validate_account_and_subdomain(request, user_profile)

        if user_profile.is_incoming_webhook:
            raise JsonableError(_("Webhook bots can only access webhooks"))

        process_client(request, user_profile, is_browser_view=True, query=view_func.__name__)
        return view_func(request, user_profile, *args, **kwargs)

    return _wrapped_view_func


# These views are used for communication from Django to Tornado, or
# from command-line tools into Django.  We protect them from the
# outside world by checking a shared secret, and also the originating
# IP (for now).
@typed_endpoint
def authenticate_internal_api(request: HttpRequest, *, secret: str) -> bool:
    return is_local_addr(request.META["REMOTE_ADDR"]) and constant_time_compare(
        secret, settings.SHARED_SECRET
    )


def internal_api_view(
    is_tornado_view: bool,
) -> Callable[
    [Callable[Concatenate[HttpRequest, ParamT], HttpResponse]],
    Callable[Concatenate[HttpRequest, ParamT], HttpResponse],
]:
    """Used for situations where something running on the Zulip server
    needs to make a request to the (other) Django/Tornado processes running on
    the server."""

    def _wrapped_view_func(
        view_func: Callable[Concatenate[HttpRequest, ParamT], HttpResponse],
    ) -> Callable[..., HttpResponse]:
        @csrf_exempt
        @require_post
        @wraps(view_func)
        def _wrapped_func_arguments(
            request: HttpRequest, /, *args: ParamT.args, **kwargs: ParamT.kwargs
        ) -> HttpResponse:
            if not authenticate_internal_api(request):  # type: ignore[call-arg] # @typed_endpoint fills in secret from the request
                raise AccessDeniedError
            request_notes = RequestNotes.get_notes(request)
            is_tornado_request = request_notes.tornado_handler_id is not None
            # These next 2 are not security checks; they are internal
            # assertions to help us find bugs.
            if is_tornado_view and not is_tornado_request:
                raise RuntimeError("Tornado notify view called with no Tornado handler")
            if not is_tornado_view and is_tornado_request:
                raise RuntimeError("Django notify view called with Tornado handler")
            request_notes.requester_for_logs = "internal"
            return view_func(request, *args, **kwargs)

        return _wrapped_func_arguments

    return _wrapped_view_func


def to_utc_datetime(timestamp: str) -> datetime:
    return timestamp_to_datetime(float(timestamp))


def return_success_on_head_request(
    view_func: Callable[Concatenate[HttpRequest, ParamT], HttpResponse],
) -> Callable[Concatenate[HttpRequest, ParamT], HttpResponse]:
    @wraps(view_func)
    def _wrapped_view_func(
        request: HttpRequest, /, *args: ParamT.args, **kwargs: ParamT.kwargs
    ) -> HttpResponse:
        if request.method == "HEAD":
            return HttpResponse()
        return view_func(request, *args, **kwargs)

    return _wrapped_view_func


def zulip_otp_required_if_logged_in(
    redirect_field_name: str = "next",
    login_url: str = settings.HOME_NOT_LOGGED_IN,
) -> Callable[
    [Callable[Concatenate[HttpRequest, ParamT], HttpResponse]],
    Callable[Concatenate[HttpRequest, ParamT], HttpResponse],
]:
    """
    The reason we need to create this function is that the stock
    otp_required decorator doesn't play well with tests. We cannot
    enable/disable if_configured parameter during tests since the decorator
    retains its value due to closure.

    Similar to :func:`~django.contrib.auth.decorators.login_required`, but
    requires the user to be :term:`verified`. By default, this redirects users
    to :setting:`OTP_LOGIN_URL`. Returns True if the user is not authenticated.
    """

    def test(user: AbstractBaseUser | AnonymousUser) -> bool:
        """
        :if_configured: If ``True``, an authenticated user with no confirmed
        OTP devices will be allowed. Also, non-authenticated users will be
        allowed as spectator users. Default is ``False``. If ``False``,
        2FA will not do any authentication.
        """
        if_configured = settings.TWO_FACTOR_AUTHENTICATION_ENABLED
        if not if_configured:
            return True

        # This request is unauthenticated (logged-out) access; 2FA is
        # not required or possible.
        if not user.is_authenticated:
            return True

        assert isinstance(user, UserProfile)
        # User has completed 2FA verification
        if is_2fa_verified(user):
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


def add_google_analytics_context(context: dict[str, object]) -> None:
    if settings.GOOGLE_ANALYTICS_ID is not None:  # nocoverage
        page_params = context.setdefault("page_params", {})
        assert isinstance(page_params, dict)
        page_params["google_analytics_id"] = settings.GOOGLE_ANALYTICS_ID


def add_google_analytics(
    view_func: Callable[Concatenate[HttpRequest, ParamT], HttpResponse],
) -> Callable[Concatenate[HttpRequest, ParamT], HttpResponse]:
    @wraps(view_func)
    def _wrapped_view_func(
        request: HttpRequest, /, *args: ParamT.args, **kwargs: ParamT.kwargs
    ) -> HttpResponse:
        response = view_func(request, *args, **kwargs)
        if isinstance(response, SimpleTemplateResponse):
            if response.context_data is None:
                response.context_data = {}
            add_google_analytics_context(response.context_data)
        elif response.status_code == 200:  # nocoverage
            raise TypeError("add_google_analytics requires a TemplateResponse")
        return response

    return _wrapped_view_func
