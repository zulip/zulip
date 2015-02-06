from __future__ import absolute_import

from django.conf import settings
import ujson
from zproject.backends import password_auth_enabled

def add_settings(request):
    if hasattr(request.user, "realm"):
        is_pw_auth_enabled = password_auth_enabled(request.user.realm)
    else:
        is_pw_auth_enabled = True
    return {
        'full_navbar':   settings.FULL_NAVBAR,
        # We use the not_enterprise variable name so that templates
        # will render even if the appropriate context is not provided
        # to the template
        'not_enterprise':    not settings.ENTERPRISE,
        'zulip_admin':   settings.ZULIP_ADMINISTRATOR,
        'password_auth_enabled': is_pw_auth_enabled,
        'login_url':     settings.HOME_NOT_LOGGED_IN,
        'only_sso':     settings.ONLY_SSO,
        'external_api_path': settings.EXTERNAL_API_PATH,
        'external_api_uri': settings.EXTERNAL_API_URI,
        'external_uri_scheme': settings.EXTERNAL_URI_SCHEME,
        'api_site_required': settings.EXTERNAL_API_PATH != "api.zulip.com",
        'email_integration_enabled': settings.EMAIL_GATEWAY_BOT != "",
        'email_gateway_example': settings.EMAIL_GATEWAY_EXAMPLE,
    }

def add_metrics(request):
    return {
        'dropboxAppKey': settings.DROPBOX_APP_KEY
    }
