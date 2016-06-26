
# For the Dev VM environment, we use the same settings as the
# sample prod_settings.py file, with a few exceptions.
from .prod_settings_template import *

LOCAL_UPLOADS_DIR = 'var/uploads'
EXTERNAL_HOST = 'localhost:9991'
ALLOWED_HOSTS = ['localhost']
AUTHENTICATION_BACKENDS = ('zproject.backends.DevAuthBackend',)
# Add some of the below if you're testing other backends
# AUTHENTICATION_BACKENDS = ('zproject.backends.EmailAuthBackend',
#                            'zproject.backends.GoogleMobileOauth2Backend',)
EXTERNAL_URI_SCHEME = "http://"
EMAIL_GATEWAY_PATTERN = "%s@" + EXTERNAL_HOST
NOTIFICATION_BOT = "notification-bot@zulip.com"
ERROR_BOT = "error-bot@zulip.com"
NEW_USER_BOT = "new-user-bot@zulip.com"
EMAIL_GATEWAY_BOT = "emailgateway@zulip.com"
EXTRA_INSTALLED_APPS = ["zilencer", "analytics"]
# Disable Camo in development
CAMO_URI = ''
OPEN_REALM_CREATION = True
TERMS_OF_SERVICE = 'zproject/terms.md.template'

SAVE_FRONTEND_STACKTRACES = True
EVENT_LOGS_ENABLED = True
SYSTEM_ONLY_REALMS = set() # type: Set[str]
