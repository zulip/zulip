from __future__ import absolute_import

from django.conf import settings
import ujson
from zproject.backends import password_auth_enabled

def add_settings(request):
    return {
        'full_navbar':   settings.FULL_NAVBAR,
        # We use the not_enterprise variable name so that templates
        # will render even if the appropriate context is not provided
        # to the template
        'not_enterprise':    not settings.ENTERPRISE,
        'zulip_admin':   settings.ZULIP_ADMINISTRATOR,
        'password_auth_enabled': password_auth_enabled(),
        'login_url':     settings.HOME_NOT_LOGGED_IN,
        'only_sso':     settings.ONLY_SSO,
    }

def add_metrics(request):
    return {
        'mixpanel_token': settings.MIXPANEL_TOKEN,
        'enable_metrics': ujson.dumps(settings.DEPLOYED),
        'dropboxAppKey': settings.DROPBOX_APP_KEY
    }
