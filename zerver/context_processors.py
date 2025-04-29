from collections.abc import Mapping
from typing import Any
from urllib.parse import urljoin

from django.conf import settings
from django.http import HttpRequest
from django.utils.html import escape
from django.utils.safestring import SafeString
from django.utils.translation import get_language
from django.utils.translation import override as override_language

from version import (
    LATEST_MAJOR_VERSION,
    LATEST_RELEASE_ANNOUNCEMENT,
    LATEST_RELEASE_VERSION,
    ZULIP_VERSION,
)
from zerver.lib.exceptions import InvalidSubdomainError
from zerver.lib.i18n import get_language_list
from zerver.lib.realm_description import get_realm_rendered_description, get_realm_text_description
from zerver.lib.realm_icon import get_realm_icon_url
from zerver.lib.request import RequestNotes
from zerver.lib.send_email import FromAddress
from zerver.lib.subdomains import get_subdomain, is_root_domain_available
from zerver.models import PreregistrationRealm, Realm, UserProfile
from zerver.models.realms import get_realm
from zproject.backends import (
    AUTH_BACKEND_NAME_MAP,
    auth_enabled_helper,
    get_external_method_dicts,
    password_auth_enabled,
    require_email_format_usernames,
)
from zproject.config import get_config

DEFAULT_PAGE_PARAMS: Mapping[str, Any] = {
    "page_type": "default",
    "development_environment": settings.DEVELOPMENT,
}


def common_context(user: UserProfile) -> dict[str, Any]:
    """Common context used for things like outgoing emails that don't
    have a request.
    """
    return {
        "realm_url": user.realm.url,
        "realm_name": user.realm.name,
        "root_domain_url": settings.ROOT_DOMAIN_URI,
        "external_url_scheme": settings.EXTERNAL_URI_SCHEME,
        "external_host": settings.EXTERNAL_HOST,
        "user_name": user.full_name,
        "corporate_enabled": settings.CORPORATE_ENABLED,
    }


def get_realm_from_request(request: HttpRequest) -> Realm | None:
    request_notes = RequestNotes.get_notes(request)
    if request.user.is_authenticated:
        return request.user.realm
    if not request_notes.has_fetched_realm:
        # We cache the realm object from this function on the request data,
        # so that functions that call get_realm_from_request don't
        # need to do duplicate queries on the same realm while
        # processing a single request.
        subdomain = get_subdomain(request)
        request_notes = RequestNotes.get_notes(request)
        try:
            request_notes.realm = get_realm(subdomain)
        except Realm.DoesNotExist:
            request_notes.realm = None
        request_notes.has_fetched_realm = True
    return request_notes.realm


def get_valid_realm_from_request(request: HttpRequest) -> Realm:
    realm = get_realm_from_request(request)
    if realm is None:
        raise InvalidSubdomainError
    return realm


def get_apps_page_url() -> str:
    if settings.CORPORATE_ENABLED:
        return "/apps/"
    return "https://zulip.com/apps/"


def is_isolated_page(request: HttpRequest) -> bool:
    """Accept a GET param `?nav=no` to render an isolated, navless page."""
    return request.GET.get("nav") == "no"


def zulip_default_corporate_context(request: HttpRequest) -> dict[str, Any]:
    from corporate.lib.decorator import is_self_hosting_management_subdomain

    # Check if view function is in corporate app.
    if request.resolver_match is not None and not request.resolver_match.func.__module__.startswith(
        "corporate"
    ):
        return {
            "is_self_hosting_management_page": False,
        }

    # Add common context variables that are only used on the corporate site.
    return {
        "is_self_hosting_management_page": is_self_hosting_management_subdomain(request),
    }


def zulip_default_context(request: HttpRequest) -> dict[str, Any]:
    """Context available to all Zulip Jinja2 templates that have a request
    passed in.  Designed to provide the long list of variables at the
    bottom of this function in a wide range of situations: logged-in
    or logged-out, subdomains or not, etc.

    The main variable in the below is whether we know what realm the
    user is trying to interact with.
    """
    realm = get_realm_from_request(request)

    if realm is None:
        realm_url = settings.ROOT_DOMAIN_URI
        realm_name = None
        realm_icon = None
    else:
        realm_url = realm.url
        realm_name = realm.name
        realm_icon = get_realm_icon_url(realm)

    skip_footer = False
    register_link_disabled = settings.REGISTER_LINK_DISABLED
    allow_search_engine_indexing = False
    non_realm_specific_page = False

    if (
        settings.ROOT_DOMAIN_LANDING_PAGE
        and get_subdomain(request) == Realm.SUBDOMAIN_FOR_ROOT_DOMAIN
    ):
        register_link_disabled = True
        allow_search_engine_indexing = True
        non_realm_specific_page = True
    elif realm is None:
        register_link_disabled = True
        skip_footer = True
        non_realm_specific_page = True

    apps_page_web = settings.ROOT_DOMAIN_URI + "/accounts/go/"

    if settings.DEVELOPMENT:
        secrets_path = "zproject/dev-secrets.conf"
        settings_path = "zproject/dev_settings.py"
        settings_comments_path = "zproject/prod_settings_template.py"
    else:
        secrets_path = "/etc/zulip/zulip-secrets.conf"
        settings_path = "/etc/zulip/settings.py"
        settings_comments_path = "/etc/zulip/settings.py"

    # Used to remove links to Zulip docs and landing page from footer of self-hosted pages.
    corporate_enabled = settings.CORPORATE_ENABLED

    support_email = FromAddress.SUPPORT
    support_email_html_tag = SafeString(
        f'<a href="mailto:{escape(support_email)}">{escape(support_email)}</a>'
    )

    # Sync this with default_params_schema in base_page_params.ts.
    default_page_params: dict[str, Any] = {
        **DEFAULT_PAGE_PARAMS,
        "request_language": get_language(),
    }

    context = {
        "root_domain_landing_page": settings.ROOT_DOMAIN_LANDING_PAGE,
        "custom_logo_url": settings.CUSTOM_LOGO_URL,
        "register_link_disabled": register_link_disabled,
        "terms_of_service": settings.TERMS_OF_SERVICE_VERSION is not None,
        "login_url": settings.HOME_NOT_LOGGED_IN,
        "only_sso": settings.ONLY_SSO,
        "external_host": settings.EXTERNAL_HOST,
        "external_url_scheme": settings.EXTERNAL_URI_SCHEME,
        "realm_url": realm_url,
        "realm_name": realm_name,
        "realm_icon": realm_icon,
        "root_domain_url": settings.ROOT_DOMAIN_URI,
        "apps_page_url": get_apps_page_url(),
        "apps_page_web": apps_page_web,
        "open_realm_creation": settings.OPEN_REALM_CREATION,
        "development_environment": settings.DEVELOPMENT,
        "support_email": support_email,
        "support_email_html_tag": support_email_html_tag,
        "password_min_length": settings.PASSWORD_MIN_LENGTH,
        "password_max_length": settings.PASSWORD_MAX_LENGTH,
        "password_min_guesses": settings.PASSWORD_MIN_GUESSES,
        "zulip_version": ZULIP_VERSION,
        "user_is_authenticated": request.user.is_authenticated,
        "settings_path": settings_path,
        "secrets_path": secrets_path,
        "settings_comments_path": settings_comments_path,
        "platform": RequestNotes.get_notes(request).client_name,
        "allow_search_engine_indexing": allow_search_engine_indexing,
        "landing_page_navbar_message": settings.LANDING_PAGE_NAVBAR_MESSAGE,
        "is_isolated_page": is_isolated_page(request),
        "skip_footer": skip_footer,
        "default_page_params": default_page_params,
        "corporate_enabled": corporate_enabled,
        "non_realm_specific_page": non_realm_specific_page,
    }

    if settings.SENTRY_FRONTEND_DSN is not None:
        sentry_params = {
            "dsn": settings.SENTRY_FRONTEND_DSN,
            "environment": get_config("machine", "deploy_type", "development"),
            "realm_key": "www" if realm is None else realm.string_id or "(root)",
            "sample_rate": settings.SENTRY_FRONTEND_SAMPLE_RATE,
            "server_version": ZULIP_VERSION,
            "trace_rate": settings.SENTRY_FRONTEND_TRACE_RATE,
        }
        if request.user.is_authenticated:
            with override_language(None):
                sentry_params["user"] = {
                    "id": request.user.id,
                    "role": request.user.get_role_name(),
                }
        context["sentry_params"] = sentry_params

    context["PAGE_METADATA_URL"] = f"{realm_url}{request.path}"
    if realm is not None and realm.icon_source == realm.ICON_UPLOADED:
        context["PAGE_METADATA_IMAGE"] = urljoin(realm_url, realm_icon)

    return context


def login_context(request: HttpRequest) -> dict[str, Any]:
    realm = get_realm_from_request(request)

    if realm is None:
        realm_description = None
        realm_invite_required = False
        realm_web_public_access_enabled = False
    else:
        realm_description = get_realm_rendered_description(realm)
        realm_invite_required = realm.invite_required
        # We offer web-public access only if the realm has actual web
        # public streams configured, in addition to having it enabled.
        realm_web_public_access_enabled = realm.allow_web_public_streams_access()

    context: dict[str, Any] = {
        "realm_invite_required": realm_invite_required,
        "realm_description": realm_description,
        "require_email_format_usernames": require_email_format_usernames(realm),
        "password_auth_enabled": password_auth_enabled(realm),
        "two_factor_authentication_enabled": settings.TWO_FACTOR_AUTHENTICATION_ENABLED,
        "realm_web_public_access_enabled": realm_web_public_access_enabled,
    }

    if realm is not None and realm.description:
        context["PAGE_TITLE"] = realm.name
        context["PAGE_DESCRIPTION"] = get_realm_text_description(realm)

    # Add the keys for our standard authentication backends.
    no_auth_enabled = True
    for auth_backend_name in AUTH_BACKEND_NAME_MAP:
        name_lower = auth_backend_name.lower()
        key = f"{name_lower}_auth_enabled"
        is_enabled = auth_enabled_helper([auth_backend_name], realm)
        context[key] = is_enabled
        if is_enabled:
            no_auth_enabled = False

    context["external_authentication_methods"] = get_external_method_dicts(realm)
    context["no_auth_enabled"] = no_auth_enabled

    return context


def latest_info_context() -> dict[str, str]:
    context = {
        "latest_release_version": LATEST_RELEASE_VERSION,
        "latest_major_version": LATEST_MAJOR_VERSION,
        "latest_release_announcement": LATEST_RELEASE_ANNOUNCEMENT,
    }
    return context


def is_realm_import_enabled() -> bool:
    return settings.MAX_WEB_DATA_IMPORT_SIZE_MB != 0


def get_realm_create_form_context() -> dict[str, Any]:
    context = {
        "language_list": get_language_list(),
        "MAX_REALM_NAME_LENGTH": str(Realm.MAX_REALM_NAME_LENGTH),
        "MAX_REALM_SUBDOMAIN_LENGTH": str(Realm.MAX_REALM_SUBDOMAIN_LENGTH),
        "root_domain_available": is_root_domain_available(),
        "sorted_realm_types": sorted(Realm.ORG_TYPES.values(), key=lambda d: d["display_order"]),
        "is_realm_import_enabled": is_realm_import_enabled(),
        "import_from_choices": PreregistrationRealm.IMPORT_FROM_CHOICES,
    }
    return context
