import zoneinfo
from email.utils import format_datetime as email_format_datetime
from typing import Any

from django.conf import settings
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver
from django.utils.timezone import get_current_timezone_name as timezone_get_current_timezone_name
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _
from ua_parser import parse_os, parse_user_agent

from confirmation.models import one_click_unsubscribe_link
from zerver.lib.queue import queue_json_publish_rollback_unsafe
from zerver.lib.send_email import FromAddress
from zerver.lib.timestamp import format_datetime_to_string
from zerver.lib.timezone import canonicalize_timezone
from zerver.models import RealmAuditLog, UserProfile
from zerver.models.realm_audit_logs import AuditLogEventType

JUST_CREATED_THRESHOLD = 60

# For login flows that don't set request.session["social_auth_backend"]
# upstream (email/password and LDAP web logins go through Django's
# LoginView, which doesn't expose a hook), we fall back to user.backend
# and map the class name to the short slug the backend already exposes
# via its `name` attribute. Keeps audit-log method values consistent
# across all auth methods.
AUTH_BACKEND_AUDIT_LOG_METHOD = {
    "EmailAuthBackend": "email",
    "ZulipLDAPAuthBackend": "ldap",
}


def get_device_browser(user_agent: str) -> str | None:
    if "zulip" in user_agent.lower():
        return "Zulip"

    if browser := parse_user_agent(user_agent):
        browser_family = browser.family
        if browser_family == "IE":
            return "Internet Explorer"
        elif browser_family != "Other":
            return browser_family

    return None


def get_device_os(user_agent: str) -> str | None:
    if os := parse_os(user_agent):
        os_family = os.family
        if os_family == "Mac OS X":
            return "macOS"
        elif os_family != "Other":
            return os_family
    return None


def get_login_audit_log_extra_data(
    user: UserProfile, request: Any, login_method: str | None = None
) -> dict[str, Any]:
    """Build the extra_data dict for a USER_LOGGED_IN / USER_LOGGED_OUT entry.

    Returns a dict with `method`, `ip_address`, `user_agent`, and parsed
    `device_browser` / `device_os` fields populated from the request.

    Resolution of `method`, in order:

    1. The explicit `login_method` argument, if provided. Sessionless
       paths (`process_api_key_fetch_authenticate_result`,
       'finish_mobile_flow') pass this because they don't go through
       Django's session-based login, so the `social_auth_backend`
       session marker isn't populated for them.
    2. `request.session["social_auth_backend"]` — set by
       `login_or_register_remote_user` for social/OIDC/SAML logins,
       and for REMOTE_USER/JWT via plumbing in their views.
       Also set by `login_and_redirect` for email/LDAP registration.
    3. The Django authentication backend class name, mapped through
       `AUTH_BACKEND_AUDIT_LOG_METHOD` so the recorded slug matches
       what the corresponding backend class exposes as its `name`. For
       session-based email/LDAP logins where no `social_auth_backend`
       marker was set, `user.backend` is populated by Django's
       `authenticate()` at login time. At logout, the
       middleware-loaded `request.user` doesn't have `.backend` set,
       so we read from `request.session["_auth_user_backend"]` —
       Django sets this in the session at login and it persists until
       the session is flushed (which happens after the
       `user_logged_out` signal fires).
    """
    extra_data: dict[str, Any] = {}
    if request is None:
        return extra_data

    if login_method is not None:
        extra_data["method"] = login_method
    else:
        method = request.session.get("social_auth_backend")
        if not method:
            backend = getattr(user, "backend", None) or request.session.get("_auth_user_backend")
            if backend:
                backend_class_name = backend.rsplit(".", 1)[-1]
                method = AUTH_BACKEND_AUDIT_LOG_METHOD.get(backend_class_name, backend_class_name)
        if method:
            extra_data["method"] = method

    user_agent = request.headers.get("User-Agent", "")
    extra_data["ip_address"] = request.META.get("REMOTE_ADDR")
    extra_data["user_agent"] = user_agent
    extra_data["device_browser"] = get_device_browser(user_agent)
    extra_data["device_os"] = get_device_os(user_agent)
    return extra_data


def do_create_login_audit_log_entry(
    user: UserProfile, request: Any, *, login_method: str | None = None
) -> None:
    if user.is_bot:
        # Skip bots; they can hit the API-key-fetch path and would
        # generate noise.
        return

    RealmAuditLog.objects.create(
        realm=user.realm,
        acting_user=user,
        modified_user=user,
        event_type=AuditLogEventType.USER_LOGGED_IN,
        event_time=timezone_now(),
        extra_data=get_login_audit_log_extra_data(user, request, login_method),
    )


def do_create_logout_audit_log_entry(user: UserProfile, request: Any) -> None:
    if user.is_bot:
        return

    RealmAuditLog.objects.create(
        realm=user.realm,
        acting_user=user,
        modified_user=user,
        event_type=AuditLogEventType.USER_LOGGED_OUT,
        event_time=timezone_now(),
        extra_data=get_login_audit_log_extra_data(user, request),
    )


@receiver(user_logged_in)
def audit_log_on_login(sender: object, *, user: UserProfile, request: Any, **kwargs: Any) -> None:
    do_create_login_audit_log_entry(user, request)


@receiver(user_logged_out)
def audit_log_on_logout(
    sender: object, *, user: UserProfile | None, request: Any = None, **kwargs: Any
) -> None:
    if user is None:
        # Anonymous logout: nothing to record.
        return
    do_create_logout_audit_log_entry(user, request)


@receiver(user_logged_in, dispatch_uid="only_on_login")
def email_on_new_login(sender: Any, user: UserProfile, request: Any, **kwargs: Any) -> None:
    if not user.enable_login_emails:
        return

    if user.delivery_email == "":
        # Do not attempt to send new login emails for users without an email address.
        # The assertions here are to help document the only circumstance under which
        # this condition should be possible.
        assert (
            user.realm.demo_organization_scheduled_deletion_date is not None and user.is_realm_owner
        )
        return

    # We import here to minimize the dependencies of this module,
    # since it runs as part of `manage.py` initialization
    from zerver.context_processors import common_context

    if not settings.SEND_LOGIN_EMAILS:
        return

    if request:
        # If the user's account was just created, avoid sending an email.
        if (timezone_now() - user.date_joined).total_seconds() <= JUST_CREATED_THRESHOLD:
            return

        user_agent = request.headers.get("User-Agent", "")

        context = common_context(user)
        context["user_email"] = user.delivery_email
        user_tz = user.timezone
        if user_tz == "":
            user_tz = timezone_get_current_timezone_name()
        local_time = timezone_now().astimezone(zoneinfo.ZoneInfo(canonicalize_timezone(user_tz)))
        context["login_time"] = format_datetime_to_string(local_time, user.twenty_four_hour_time)
        context["device_ip"] = request.META.get("REMOTE_ADDR") or _("Unknown IP address")
        context["device_os"] = get_device_os(user_agent) or _("an unknown operating system")
        context["device_browser"] = get_device_browser(user_agent) or _("An unknown browser")
        context["unsubscribe_link"] = one_click_unsubscribe_link(user, "login")

        email_dict = {
            "template_prefix": "zerver/emails/notify_new_login",
            "to_user_ids": [user.id],
            "from_name": FromAddress.security_email_from_name(user_profile=user),
            "from_address": FromAddress.NOREPLY,
            "context": context,
            "date": email_format_datetime(local_time),
        }
        queue_json_publish_rollback_unsafe("email_senders", email_dict)


@receiver(user_logged_out)
def clear_call_tokens_on_logout(
    sender: object, *, user: UserProfile | None, **kwargs: object
) -> None:
    # Loaded lazily so django.setup() succeeds before static asset generation
    from zerver.actions.video_calls import do_set_video_call_provider_token

    if user is not None:
        if user.third_party_api_state.get("zoom") is not None:
            do_set_video_call_provider_token(user, "zoom", None)
        if user.third_party_api_state.get("webex") is not None:
            do_set_video_call_provider_token(user, "webex", None)
