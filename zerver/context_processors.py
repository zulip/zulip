from typing import Any, Dict, Mapping, Optional
from urllib.parse import urljoin

from django.conf import settings
from django.contrib.staticfiles.storage import staticfiles_storage
from django.http import HttpRequest
from django.utils.html import escape
from django.utils.safestring import SafeString
from django.utils.translation import get_language

from version import (
    LATEST_MAJOR_VERSION,
    LATEST_RELEASE_ANNOUNCEMENT,
    LATEST_RELEASE_VERSION,
    ZULIP_VERSION,
)
from zerver.lib.exceptions import InvalidSubdomainError
from zerver.lib.realm_description import get_realm_rendered_description, get_realm_text_description
from zerver.lib.realm_icon import get_realm_icon_url
from zerver.lib.request import RequestNotes
from zerver.lib.send_email import FromAddress
from zerver.lib.subdomains import get_subdomain, is_root_domain_available
from zerver.models import Realm, UserProfile, get_realm
from zproject.backends import (
    AUTH_BACKEND_NAME_MAP,
    auth_enabled_helper,
    get_external_method_dicts,
    password_auth_enabled,
    require_email_format_usernames,
)
from zproject.config import get_config

DEFAULT_PAGE_PARAMS: Mapping[str, Any] = {
    "development_environment": settings.DEVELOPMENT,
    "webpack_public_path": staticfiles_storage.url(settings.WEBPACK_BUNDLES),
}


def common_context(user: UserProfile) -> Dict[str, Any]:
    """Common context used for things like outgoing emails that don't
    have a request.
    """
    return {
        "realm_uri": user.realm.uri,
        "realm_name": user.realm.name,
        "root_domain_url": settings.ROOT_DOMAIN_URI,
        "external_url_scheme": settings.EXTERNAL_URI_SCHEME,
        "external_host": settings.EXTERNAL_HOST,
        "user_name": user.full_name,
        "corporate_enabled": settings.CORPORATE_ENABLED,
    }


def get_realm_from_request(request: HttpRequest) -> Optional[Realm]:
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


def zulip_default_context(request: HttpRequest) -> Dict[str, Any]:
    """Context available to all Zulip Jinja2 templates that have a request
    passed in.  Designed to provide the long list of variables at the
    bottom of this function in a wide range of situations: logged-in
    or logged-out, subdomains or not, etc.

    The main variable in the below is whether we know what realm the
    user is trying to interact with.
    """
    realm = get_realm_from_request(request)

    if realm is None:
        realm_uri = settings.ROOT_DOMAIN_URI
        realm_name = None
        realm_icon = None
    else:
        realm_uri = realm.uri
        realm_name = realm.name
        realm_icon = get_realm_icon_url(realm)

    register_link_disabled = settings.REGISTER_LINK_DISABLED
    login_link_disabled = settings.LOGIN_LINK_DISABLED
    find_team_link_disabled = settings.FIND_TEAM_LINK_DISABLED
    allow_search_engine_indexing = False

    if (
        settings.ROOT_DOMAIN_LANDING_PAGE
        and get_subdomain(request) == Realm.SUBDOMAIN_FOR_ROOT_DOMAIN
    ):
        register_link_disabled = True
        login_link_disabled = True
        find_team_link_disabled = False
        allow_search_engine_indexing = True

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

    default_page_params: Dict[str, Any] = {
        **DEFAULT_PAGE_PARAMS,
        "server_sentry_dsn": settings.SENTRY_FRONTEND_DSN,
        "request_language": get_language(),
    }
    if settings.SENTRY_FRONTEND_DSN is not None:
        if realm is not None:
            default_page_params["realm_sentry_key"] = realm.string_id
        default_page_params["server_sentry_environment"] = get_config(
            "machine", "deploy_type", "development"
        )
        default_page_params["server_sentry_sample_rate"] = settings.SENTRY_FRONTEND_SAMPLE_RATE
        default_page_params["server_sentry_trace_rate"] = settings.SENTRY_FRONTEND_TRACE_RATE

    context = {
        "root_domain_landing_page": settings.ROOT_DOMAIN_LANDING_PAGE,
        "custom_logo_url": settings.CUSTOM_LOGO_URL,
        "register_link_disabled": register_link_disabled,
        "login_link_disabled": login_link_disabled,
        "terms_of_service": settings.TERMS_OF_SERVICE_VERSION is not None,
        "login_url": settings.HOME_NOT_LOGGED_IN,
        "only_sso": settings.ONLY_SSO,
        "external_host": settings.EXTERNAL_HOST,
        "external_url_scheme": settings.EXTERNAL_URI_SCHEME,
        "realm_uri": realm_uri,
        "realm_name": realm_name,
        "realm_icon": realm_icon,
        "root_domain_url": settings.ROOT_DOMAIN_URI,
        "apps_page_url": get_apps_page_url(),
        "apps_page_web": apps_page_web,
        "open_realm_creation": settings.OPEN_REALM_CREATION,
        "development_environment": settings.DEVELOPMENT,
        "support_email": support_email,
        "support_email_html_tag": support_email_html_tag,
        "find_team_link_disabled": find_team_link_disabled,
        "password_min_length": settings.PASSWORD_MIN_LENGTH,
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
        "default_page_params": default_page_params,
        "corporate_enabled": corporate_enabled,
    }

    context["PAGE_METADATA_URL"] = f"{realm_uri}{request.path}"
    if realm is not None and realm.icon_source == realm.ICON_UPLOADED:
        context["PAGE_METADATA_IMAGE"] = urljoin(realm_uri, realm_icon)

    return context


def login_context(request: HttpRequest) -> Dict[str, Any]:
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

    context: Dict[str, Any] = {
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

    # Include another copy of external_authentication_methods in page_params for use
    # by the desktop client. We expand it with IDs of the <button> elements corresponding
    # to the authentication methods.
    context["page_params"] = dict(
        external_authentication_methods=get_external_method_dicts(realm),
    )
    for auth_dict in context["page_params"]["external_authentication_methods"]:
        auth_dict["button_id_suffix"] = "auth_button_{}".format(auth_dict["name"])

    return context


def latest_info_context() -> Dict[str, str]:
    context = {
        "latest_release_version": LATEST_RELEASE_VERSION,
        "latest_major_version": LATEST_MAJOR_VERSION,
        "latest_release_announcement": LATEST_RELEASE_ANNOUNCEMENT,
    }
    return context


def get_realm_create_form_context() -> Dict[str, Any]:
    context = {
        "MAX_REALM_NAME_LENGTH": str(Realm.MAX_REALM_NAME_LENGTH),
        "MAX_REALM_SUBDOMAIN_LENGTH": str(Realm.MAX_REALM_SUBDOMAIN_LENGTH),
        "root_domain_available": is_root_domain_available(),
        "sorted_realm_types": sorted(Realm.ORG_TYPES.values(), key=lambda d: d["display_order"]),
    }
    return context
