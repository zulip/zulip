from __future__ import absolute_import

from typing import Any, Dict, List, Optional
from django.http import HttpRequest
from django.conf import settings

from zerver.models import UserProfile, get_realm, get_unique_non_system_realm, Realm
from zproject.backends import (
    any_oauth_backend_enabled,
    dev_auth_enabled,
    github_auth_enabled,
    google_auth_enabled,
    password_auth_enabled,
    email_auth_enabled,
    require_email_format_usernames,
    auth_enabled_helper,
    AUTH_BACKEND_NAME_MAP
)
from zerver.lib.bugdown import convert
from zerver.lib.send_email import FromAddress
from zerver.lib.utils import get_subdomain
from zerver.lib.realm_icon import get_realm_icon_url

from version import ZULIP_VERSION

def common_context(user):
    # type: (UserProfile) -> Dict[str, Any]
    """Common context used for things like outgoing emails that don't
    have a request.
    """
    return {
        'realm_uri': user.realm.uri,
        'root_domain_uri': settings.ROOT_DOMAIN_URI,
        'external_uri_scheme': settings.EXTERNAL_URI_SCHEME,
        'external_host': settings.EXTERNAL_HOST,
    }

def get_realm_from_request(request):
    # type: (HttpRequest) -> Optional[Realm]
    if hasattr(request, "user") and hasattr(request.user, "realm"):
        return request.user.realm
    elif settings.REALMS_HAVE_SUBDOMAINS:
        subdomain = get_subdomain(request)
        return get_realm(subdomain)
    # This will return None if there is no unique, open realm.
    return get_unique_non_system_realm()

def zulip_default_context(request):
    # type: (HttpRequest) -> Dict[str, Any]
    """Context available to all Zulip Jinja2 templates that have a request
    passed in.  Designed to provide the long list of variables at the
    bottom of this function in a wide range of situations: logged-in
    or logged-out, subdomains or not, etc.

    The main variable in the below is whether we know the realm, which
    is the case if there is only one realm, or we're on a
    REALMS_HAVE_SUBDOMAINS subdomain, or the user is logged in.
    """
    realm = get_realm_from_request(request)

    if realm is None:
        realm_uri = settings.ROOT_DOMAIN_URI
        realm_name = None
        realm_icon = None
        realm_description = None
        realm_invite_required = False
    else:
        realm_uri = realm.uri
        realm_name = realm.name
        realm_icon = get_realm_icon_url(realm)
        realm_description_raw = realm.description or "The coolest place in the universe."
        realm_description = convert(realm_description_raw, message_realm=realm)
        realm_invite_required = realm.invite_required

    register_link_disabled = settings.REGISTER_LINK_DISABLED
    login_link_disabled = settings.LOGIN_LINK_DISABLED
    about_link_disabled = settings.ABOUT_LINK_DISABLED
    find_team_link_disabled = settings.FIND_TEAM_LINK_DISABLED

    if settings.ROOT_DOMAIN_LANDING_PAGE and get_subdomain(request) == "":
        register_link_disabled = True
        login_link_disabled = True
        about_link_disabled = True
        find_team_link_disabled = False

    apps_page_url = 'https://zulipchat.com/apps/'
    if settings.ZILENCER_ENABLED:
        apps_page_url = '/apps/'

    user_is_authenticated = False
    if hasattr(request, 'user') and hasattr(request.user, 'is_authenticated'):
        user_is_authenticated = request.user.is_authenticated.value

    if settings.DEVELOPMENT:
        secrets_path = "zproject/dev-secrets.conf"
        settings_path = "zproject/dev_settings.py"
        settings_comments_path = "zproject/prod_settings_template.py"
    else:
        secrets_path = "/etc/zulip/zulip-secrets.conf"
        settings_path = "/etc/zulip/settings.py"
        settings_comments_path = "/etc/zulip/settings.py"

    return {
        'realms_have_subdomains': settings.REALMS_HAVE_SUBDOMAINS,
        'root_domain_landing_page': settings.ROOT_DOMAIN_LANDING_PAGE,
        'custom_logo_url': settings.CUSTOM_LOGO_URL,
        'register_link_disabled': register_link_disabled,
        'login_link_disabled': login_link_disabled,
        'about_link_disabled': about_link_disabled,
        'terms_of_service': settings.TERMS_OF_SERVICE,
        'privacy_policy': settings.PRIVACY_POLICY,
        'login_url': settings.HOME_NOT_LOGGED_IN,
        'only_sso': settings.ONLY_SSO,
        'external_api_path': settings.EXTERNAL_API_PATH,
        'external_api_uri': settings.EXTERNAL_API_URI,
        'external_host': settings.EXTERNAL_HOST,
        'external_uri_scheme': settings.EXTERNAL_URI_SCHEME,
        'realm_invite_required': realm_invite_required,
        'realm_uri': realm_uri,
        'realm_name': realm_name,
        'realm_icon': realm_icon,
        'realm_description': realm_description,
        'root_domain_uri': settings.ROOT_DOMAIN_URI,
        'api_site_required': settings.EXTERNAL_API_PATH != "api.zulip.com",
        'email_gateway_example': settings.EMAIL_GATEWAY_EXAMPLE,
        'apps_page_url': apps_page_url,
        'open_realm_creation': settings.OPEN_REALM_CREATION,
        'password_auth_enabled': password_auth_enabled(realm),
        'dev_auth_enabled': dev_auth_enabled(realm),
        'google_auth_enabled': google_auth_enabled(realm),
        'github_auth_enabled': github_auth_enabled(realm),
        'email_auth_enabled': email_auth_enabled(realm),
        'require_email_format_usernames': require_email_format_usernames(realm),
        'any_oauth_backend_enabled': any_oauth_backend_enabled(realm),
        'no_auth_enabled': not auth_enabled_helper(list(AUTH_BACKEND_NAME_MAP.keys()), realm),
        'development_environment': settings.DEVELOPMENT,
        'support_email': FromAddress.SUPPORT,
        'find_team_link_disabled': find_team_link_disabled,
        'password_min_length': settings.PASSWORD_MIN_LENGTH,
        'password_min_quality': settings.PASSWORD_MIN_ZXCVBN_QUALITY,
        'zulip_version': ZULIP_VERSION,
        'user_is_authenticated': user_is_authenticated,
        'settings_path': settings_path,
        'secrets_path': secrets_path,
        'settings_comments_path': settings_comments_path,
    }


def add_metrics(request):
    # type: (HttpRequest) -> Dict[str, str]
    return {
        'dropboxAppKey': settings.DROPBOX_APP_KEY
    }
