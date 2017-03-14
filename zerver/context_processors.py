from __future__ import absolute_import

from typing import Dict, Any
from django.http import HttpRequest
from django.conf import settings

from zerver.models import UserProfile, get_realm
from zproject.backends import (password_auth_enabled, dev_auth_enabled,
                               google_auth_enabled, github_auth_enabled)
from zerver.lib.utils import get_subdomain
from version import ZULIP_VERSION

def common_context(user):
    # type: (UserProfile) -> Dict[str, Any]
    return {
        'realm_uri': user.realm.uri,
        'server_uri': settings.SERVER_URI,
        'external_uri_scheme': settings.EXTERNAL_URI_SCHEME,
        'external_host': settings.EXTERNAL_HOST,
    }


def add_settings(request):
    # type: (HttpRequest) -> Dict[str, Any]
    realm = None
    if hasattr(request.user, "realm"):
        realm = request.user.realm
    elif settings.REALMS_HAVE_SUBDOMAINS:
        subdomain = get_subdomain(request)
        realm = get_realm(subdomain)

    if realm is not None:
        realm_uri = realm.uri
    else:
        realm_uri = settings.SERVER_URI

    return {
        'custom_logo_url': settings.CUSTOM_LOGO_URL,
        'register_link_disabled': settings.REGISTER_LINK_DISABLED,
        'login_link_disabled': settings.LOGIN_LINK_DISABLED,
        'about_link_disabled': settings.ABOUT_LINK_DISABLED,
        'show_oss_announcement': settings.SHOW_OSS_ANNOUNCEMENT,
        'zulip_admin': settings.ZULIP_ADMINISTRATOR,
        'terms_of_service': settings.TERMS_OF_SERVICE,
        'login_url': settings.HOME_NOT_LOGGED_IN,
        'only_sso': settings.ONLY_SSO,
        'external_api_path': settings.EXTERNAL_API_PATH,
        'external_api_uri': settings.EXTERNAL_API_URI,
        'external_host': settings.EXTERNAL_HOST,
        'external_uri_scheme': settings.EXTERNAL_URI_SCHEME,
        'realm_uri': realm_uri,
        'server_uri': settings.SERVER_URI,
        'api_site_required': settings.EXTERNAL_API_PATH != "api.zulip.com",
        'email_integration_enabled': settings.EMAIL_GATEWAY_BOT != "",
        'email_gateway_example': settings.EMAIL_GATEWAY_EXAMPLE,
        'open_realm_creation': settings.OPEN_REALM_CREATION,
        'password_auth_enabled': password_auth_enabled(realm),
        'dev_auth_enabled': dev_auth_enabled(realm),
        'google_auth_enabled': google_auth_enabled(realm),
        'github_auth_enabled': github_auth_enabled(realm),
        'development_environment': settings.DEVELOPMENT,
        'support_email': settings.ZULIP_ADMINISTRATOR,
        'find_team_link_disabled': settings.FIND_TEAM_LINK_DISABLED,
        'password_min_length': settings.PASSWORD_MIN_LENGTH,
        'password_min_quality': settings.PASSWORD_MIN_ZXCVBN_QUALITY,
        'zulip_version': ZULIP_VERSION,
    }


def add_metrics(request):
    # type: (HttpRequest) -> Dict[str, str]
    return {
        'dropboxAppKey': settings.DROPBOX_APP_KEY
    }
