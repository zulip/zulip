
# For the Dev VM environment, we use the same settings as the
# sample prod_settings.py file, with a few exceptions.
from .prod_settings_template import *
import os
from typing import Set

LOCAL_UPLOADS_DIR = 'var/uploads'
# Default to subdomains disabled in development until we can update
# the development documentation to make sense with subdomains.
REALMS_HAVE_SUBDOMAINS = False
# Check if test_settings.py set EXTERNAL_HOST.
EXTERNAL_HOST = os.getenv('EXTERNAL_HOST')
if EXTERNAL_HOST is None:
    if REALMS_HAVE_SUBDOMAINS:
        EXTERNAL_HOST = 'zulipdev.com:9991'
    else:
        EXTERNAL_HOST = 'localhost:9991'
ALLOWED_HOSTS = ['*']

# Uncomment extra backends if you want to test with them.  Note that
# for Google and GitHub auth you'll need to do some pre-setup.
AUTHENTICATION_BACKENDS = (
    'zproject.backends.DevAuthBackend',
    'zproject.backends.EmailAuthBackend',
    'zproject.backends.GitHubAuthBackend',
    'zproject.backends.GoogleMobileOauth2Backend',
)

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

SAVE_FRONTEND_STACKTRACES = True
EVENT_LOGS_ENABLED = True
SYSTEM_ONLY_REALMS = set()  # type: Set[str]
USING_PGROONGA = True
# Flush cache after migration.
POST_MIGRATION_CACHE_FLUSHING = True  # type: bool

# Enable inline open graph preview in development for now
INLINE_URL_EMBED_PREVIEW = True
ANALYTICS_LOCK_DIR = "var/analytics-lock-dir"

# Don't require anything about password strength in development
PASSWORD_MIN_LENGTH = 0
PASSWORD_MIN_ZXCVBN_QUALITY = 0
