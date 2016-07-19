
# For the Dev VM environment, we use the same settings as the
# sample prod_settings.py file, with a few exceptions.
from .prod_settings_template import *

LOCAL_UPLOADS_DIR = 'var/uploads'
EXTERNAL_HOST = 'zulipdev.com:9991'
ALLOWED_HOSTS = ['*']
AUTHENTICATION_BACKENDS = ('zproject.backends.DevAuthBackend',)
# Add some of the below if you're testing other backends
# AUTHENTICATION_BACKENDS = ('zproject.backends.EmailAuthBackend',
#                            'zproject.backends.GoogleMobileOauth2Backend',)
EXTERNAL_URI_SCHEME = "http://"
EMAIL_GATEWAY_PATTERN = "%s@" + EXTERNAL_HOST
ADMIN_DOMAIN = "zulip.com"
NOTIFICATION_BOT = "notification-bot@zulip.com"
ERROR_BOT = "error-bot@zulip.com"
NEW_USER_BOT = "new-user-bot@zulip.com"
EMAIL_GATEWAY_BOT = "emailgateway@zulip.com"
EXTRA_INSTALLED_APPS = ["zilencer", "analytics"]
# Disable Camo in development
CAMO_URI = ''
OPEN_REALM_CREATION = True
REALMS_HAVE_SUBDOMAINS = True
SESSION_COOKIE_DOMAIN = ".zulipdev.com"
TERMS_OF_SERVICE = 'zproject/terms.md.template'

SAVE_FRONTEND_STACKTRACES = True
