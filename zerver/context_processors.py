from typing import Any, Dict, Optional
from urllib.parse import urljoin

from django.conf import settings
from django.http import HttpRequest
from django.utils.html import escape
from django.utils.safestring import SafeString

from version import (
    LATEST_MAJOR_VERSION,
    LATEST_RELEASE_ANNOUNCEMENT,
    LATEST_RELEASE_VERSION,
    ZULIP_VERSION,
)
from zerver.decorator import get_client_name
from zerver.lib.exceptions import InvalidSubdomainError
from zerver.lib.realm_description import get_realm_rendered_description, get_realm_text_description
from zerver.lib.realm_icon import get_realm_icon_url
from zerver.lib.send_email import FromAddress
from zerver.lib.subdomains import get_subdomain
from zerver.models import Realm, UserProfile, get_realm
from zproject.backends import (
    AUTH_BACKEND_NAME_MAP,
    any_social_backend_enabled,
    auth_enabled_helper,
    get_external_method_dicts,
    password_auth_enabled,
    require_email_format_usernames,
)


def common_context(user: UserProfile) -> Dict[str, Any]:
    """Common context used for things like outgoing emails that don't
    have a request.
    """
    return {
        'realm_uri': user.realm.uri,
        'realm_name': user.realm.name,
        'root_domain_uri': settings.ROOT_DOMAIN_URI,
        'external_uri_scheme': settings.EXTERNAL_URI_SCHEME,
        'external_host': settings.EXTERNAL_HOST,
        'user_name': user.full_name,
    }

def get_realm_from_request(request: HttpRequest) -> Optional[Realm]:
    if hasattr(request, "user") and hasattr(request.user, "realm"):
        return request.user.realm
    if not hasattr(request, "realm"):
        # We cache the realm object from this function on the request,
        # so that functions that call get_realm_from_request don't
        # need to do duplicate queries on the same realm while
        # processing a single request.
        subdomain = get_subdomain(request)
        try:
            request.realm = get_realm(subdomain)
        except Realm.DoesNotExist:
            request.realm = None
    return request.realm

def get_valid_realm_from_request(request: HttpRequest) -> Realm:
    realm = get_realm_from_request(request)
    if realm is None:
        raise InvalidSubdomainError()
    return realm

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

    if (settings.ROOT_DOMAIN_LANDING_PAGE
            and get_subdomain(request) == Realm.SUBDOMAIN_FOR_ROOT_DOMAIN):
        register_link_disabled = True
        login_link_disabled = True
        find_team_link_disabled = False
        allow_search_engine_indexing = True

    apps_page_url = 'https://zulip.com/apps/'
    if settings.ZILENCER_ENABLED:
        apps_page_url = '/apps/'

    apps_page_web = settings.ROOT_DOMAIN_URI + '/accounts/go/'

    user_is_authenticated = False
    if hasattr(request, 'user') and hasattr(request.user, 'is_authenticated'):
        user_is_authenticated = request.user.is_authenticated

    if settings.DEVELOPMENT:
        secrets_path = "zproject/dev-secrets.conf"
        settings_path = "zproject/dev_settings.py"
        settings_comments_path = "zproject/prod_settings_template.py"
    else:
        secrets_path = "/etc/zulip/zulip-secrets.conf"
        settings_path = "/etc/zulip/settings.py"
        settings_comments_path = "/etc/zulip/settings.py"

    support_email = FromAddress.SUPPORT
    support_email_html_tag = SafeString(f'<a href="mailto:{escape(support_email)}">{escape(support_email)}</a>')

    # We can't use request.client here because we might not be using
    # an auth decorator that sets it, but we can call its helper to
    # get the same result.
    platform = get_client_name(request)

    context = {
        'root_domain_landing_page': settings.ROOT_DOMAIN_LANDING_PAGE,
        'custom_logo_url': settings.CUSTOM_LOGO_URL,
        'register_link_disabled': register_link_disabled,
        'login_link_disabled': login_link_disabled,
        'terms_of_service': settings.TERMS_OF_SERVICE,
        'privacy_policy': settings.PRIVACY_POLICY,
        'login_url': settings.HOME_NOT_LOGGED_IN,
        'only_sso': settings.ONLY_SSO,
        'external_host': settings.EXTERNAL_HOST,
        'external_uri_scheme': settings.EXTERNAL_URI_SCHEME,
        'realm_uri': realm_uri,
        'realm_name': realm_name,
        'realm_icon': realm_icon,
        'root_domain_uri': settings.ROOT_DOMAIN_URI,
        'apps_page_url': apps_page_url,
        'apps_page_web': apps_page_web,
        'open_realm_creation': settings.OPEN_REALM_CREATION,
        'development_environment': settings.DEVELOPMENT,
        'support_email': support_email,
        'support_email_html_tag': support_email_html_tag,
        'find_team_link_disabled': find_team_link_disabled,
        'password_min_length': settings.PASSWORD_MIN_LENGTH,
        'password_min_guesses': settings.PASSWORD_MIN_GUESSES,
        'zulip_version': ZULIP_VERSION,
        'user_is_authenticated': user_is_authenticated,
        'settings_path': settings_path,
        'secrets_path': secrets_path,
        'settings_comments_path': settings_comments_path,
        'platform': platform,
        'allow_search_engine_indexing': allow_search_engine_indexing,
        'landing_page_navbar_message': settings.LANDING_PAGE_NAVBAR_MESSAGE,
    }

    context['OPEN_GRAPH_URL'] = f'{realm_uri}{request.path}'
    if realm is not None and realm.icon_source == realm.ICON_UPLOADED:
        context['OPEN_GRAPH_IMAGE'] = urljoin(realm_uri, realm_icon)

    return context

def login_context(request: HttpRequest) -> Dict[str, Any]:
    realm = get_realm_from_request(request)

    if realm is None:
        realm_description = None
        realm_invite_required = False
    else:
        realm_description = get_realm_rendered_description(realm)
        realm_invite_required = realm.invite_required

    context: Dict[str, Any] = {
        'realm_invite_required': realm_invite_required,
        'realm_description': realm_description,
        'require_email_format_usernames': require_email_format_usernames(realm),
        'password_auth_enabled': password_auth_enabled(realm),
        'any_social_backend_enabled': any_social_backend_enabled(realm),
        'two_factor_authentication_enabled': settings.TWO_FACTOR_AUTHENTICATION_ENABLED,
    }

    if realm is not None and realm.description:
        context['OPEN_GRAPH_TITLE'] = realm.name
        context['OPEN_GRAPH_DESCRIPTION'] = get_realm_text_description(realm)

    # Add the keys for our standard authentication backends.
    no_auth_enabled = True
    for auth_backend_name in AUTH_BACKEND_NAME_MAP:
        name_lower = auth_backend_name.lower()
        key = f"{name_lower}_auth_enabled"
        is_enabled = auth_enabled_helper([auth_backend_name], realm)
        context[key] = is_enabled
        if is_enabled:
            no_auth_enabled = False

    context['external_authentication_methods'] = get_external_method_dicts(realm)
    context['no_auth_enabled'] = no_auth_enabled

    # Include another copy of external_authentication_methods in page_params for use
    # by the desktop client. We expand it with IDs of the <button> elements corresponding
    # to the authentication methods.
    context['page_params'] = dict(
        external_authentication_methods = get_external_method_dicts(realm),
    )
    for auth_dict in context['page_params']['external_authentication_methods']:
        auth_dict['button_id_suffix'] = "auth_button_{}".format(auth_dict['name'])

    return context

def latest_info_context() -> Dict[str, str]:
    context = {
        'latest_release_version': LATEST_RELEASE_VERSION,
        'latest_major_version': LATEST_MAJOR_VERSION,
        'latest_release_announcement': LATEST_RELEASE_ANNOUNCEMENT,
    }
    return context
