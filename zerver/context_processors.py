from __future__ import absolute_import

from typing import Dict, Any
from django.http import HttpRequest
from django.conf import settings
import ujson
from zproject.backends import (password_auth_enabled, dev_auth_enabled,
                               google_auth_enabled, github_auth_enabled)

def add_settings(request):
    # type: (HttpRequest) -> Dict[str, Any]
    if hasattr(request.user, "realm"):
        realm = request.user.realm
        realm_uri = realm.uri
    else:
        realm = None
        # TODO: Figure out how to add an assertion that this is not used
        realm_uri = settings.SERVER_URI

    return {
        'custom_logo_url':           settings.CUSTOM_LOGO_URL,
        'register_link_disabled':    settings.REGISTER_LINK_DISABLED,
        'show_oss_announcement':     settings.SHOW_OSS_ANNOUNCEMENT,
        'zulip_admin':               settings.ZULIP_ADMINISTRATOR,
        'terms_of_service':          settings.TERMS_OF_SERVICE,
        'login_url':                 settings.HOME_NOT_LOGGED_IN,
        'only_sso':                  settings.ONLY_SSO,
        'external_api_path':         settings.EXTERNAL_API_PATH,
        'external_api_uri':          settings.EXTERNAL_API_URI,
        'external_host':             settings.EXTERNAL_HOST,
        'external_uri_scheme':       settings.EXTERNAL_URI_SCHEME,
        'realm_uri':                 realm_uri,
        'server_uri':                settings.SERVER_URI,
        'api_site_required':         settings.EXTERNAL_API_PATH != "api.zulip.com",
        'email_integration_enabled': settings.EMAIL_GATEWAY_BOT != "",
        'email_gateway_example':     settings.EMAIL_GATEWAY_EXAMPLE,
        'open_realm_creation':       settings.OPEN_REALM_CREATION,
        'password_auth_enabled':     password_auth_enabled(realm),
        'dev_auth_enabled':          dev_auth_enabled(),
        'google_auth_enabled':       google_auth_enabled(),
        'github_auth_enabled':       github_auth_enabled(),
        'development_environment':   settings.DEVELOPMENT,
        'support_email':             settings.ZULIP_ADMINISTRATOR,
    }

def add_metrics(request):
    # type: (HttpRequest) -> Dict[str, str]
    return {
        'dropboxAppKey': settings.DROPBOX_APP_KEY
    }
