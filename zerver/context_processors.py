
from typing import Any, Dict, Optional
from django.http import HttpRequest
from django.conf import settings
from django.urls import reverse

from zerver.models import UserProfile, get_realm, Realm
from zproject.backends import (
    any_oauth_backend_enabled,
    password_auth_enabled,
    require_email_format_usernames,
    auth_enabled_helper,
    AUTH_BACKEND_NAME_MAP,
    SOCIAL_AUTH_BACKENDS,
)
from zerver.lib.bugdown import convert as bugdown_convert
from zerver.lib.send_email import FromAddress
from zerver.lib.subdomains import get_subdomain
from zerver.lib.realm_icon import get_realm_icon_url

from version import ZULIP_VERSION, LATEST_RELEASE_VERSION, \
    LATEST_RELEASE_ANNOUNCEMENT, LATEST_MAJOR_VERSION

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
    subdomain = get_subdomain(request)
    return get_realm(subdomain)

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
        realm_description = None
        realm_invite_required = False
        realm_plan_type = 0
    else:
        realm_uri = realm.uri
        realm_name = realm.name
        realm_icon = get_realm_icon_url(realm)
        realm_description_raw = realm.description or "The coolest place in the universe."
        realm_description = bugdown_convert(realm_description_raw, message_realm=realm)
        realm_invite_required = realm.invite_required
        realm_plan_type = realm.plan_type

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

    if hasattr(request, "client") and request.client.name == "ZulipElectron":
        platform = "ZulipElectron"  # nocoverage
    else:
        platform = "ZulipWeb"

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
        'realm_invite_required': realm_invite_required,
        'realm_uri': realm_uri,
        'realm_name': realm_name,
        'realm_icon': realm_icon,
        'realm_description': realm_description,
        'realm_plan_type': realm_plan_type,
        'root_domain_uri': settings.ROOT_DOMAIN_URI,
        'apps_page_url': apps_page_url,
        'open_realm_creation': settings.OPEN_REALM_CREATION,
        'password_auth_enabled': password_auth_enabled(realm),
        'require_email_format_usernames': require_email_format_usernames(realm),
        'any_oauth_backend_enabled': any_oauth_backend_enabled(realm),
        'no_auth_enabled': not auth_enabled_helper(list(AUTH_BACKEND_NAME_MAP.keys()), realm),
        'development_environment': settings.DEVELOPMENT,
        'support_email': FromAddress.SUPPORT,
        'find_team_link_disabled': find_team_link_disabled,
        'password_min_length': settings.PASSWORD_MIN_LENGTH,
        'password_min_guesses': settings.PASSWORD_MIN_GUESSES,
        'jitsi_server_url': settings.JITSI_SERVER_URL,
        'two_factor_authentication_enabled': settings.TWO_FACTOR_AUTHENTICATION_ENABLED,
        'zulip_version': ZULIP_VERSION,
        'latest_release_version': LATEST_RELEASE_VERSION,
        'latest_major_version': LATEST_MAJOR_VERSION,
        'latest_release_announcement': LATEST_RELEASE_ANNOUNCEMENT,
        'user_is_authenticated': user_is_authenticated,
        'settings_path': settings_path,
        'secrets_path': secrets_path,
        'settings_comments_path': settings_comments_path,
        'platform': platform,
        'allow_search_engine_indexing': allow_search_engine_indexing,
    }

    # Add the keys for our standard authentication backends.
    for auth_backend_name in AUTH_BACKEND_NAME_MAP:
        name_lower = auth_backend_name.lower()
        key = "%s_auth_enabled" % (name_lower,)
        context[key] = auth_enabled_helper([auth_backend_name], realm)

    social_backends = []
    for backend in SOCIAL_AUTH_BACKENDS:
        if not auth_enabled_helper([backend.auth_backend_name], realm):
            continue
        social_backends.append({
            'name': backend.name,
            'display_name': backend.auth_backend_name,
            'login_url': reverse('login-social', args=(backend.name,)),
            'signup_url': reverse('signup-social', args=(backend.name,)),
            'sort_order': backend.sort_order,
        })
    context['social_backends'] = sorted(social_backends, key=lambda x: x['sort_order'])

    return context
