
# For the Dev VM environment, we use the same settings as the
# sample prod_settings.py file, with a few exceptions.
from .prod_settings_template import *
import os
import pwd
from typing import Set

LOCAL_UPLOADS_DIR = 'var/uploads'
EMAIL_LOG_DIR = "/var/log/zulip/email.log"
FORWARD_ADDRESS_CONFIG_FILE = "var/forward_address.ini"
# Check if test_settings.py set EXTERNAL_HOST.
EXTERNAL_HOST = os.getenv('EXTERNAL_HOST')
if EXTERNAL_HOST is None:
    user_id = os.getuid()
    user_name = pwd.getpwuid(user_id).pw_name
    if user_name == "zulipdev":
        # For our droplets, we use the external hostname by default.
        EXTERNAL_HOST = os.uname()[1].lower() + ":9991"
    else:
        # For local development environments, we use localhost by
        # default, via the "zulipdev.com" hostname.
        EXTERNAL_HOST = 'zulipdev.com:9991'
        # Serve the main dev realm at the literal name "localhost",
        # so it works out of the box even when not on the Internet.
        REALM_HOSTS = {
            'zulip': 'localhost:9991'
        }
else:
    REALM_HOSTS = {
        'zulip': EXTERNAL_HOST,
    }

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
EMAIL_GATEWAY_BOT = "emailgateway@zulip.com"
PHYSICAL_ADDRESS = "Zulip Headquarters, 123 Octo Stream, South Pacific Ocean"
EXTRA_INSTALLED_APPS = ["zilencer", "analytics"]
# Disable Camo in development
CAMO_URI = ''

OPEN_REALM_CREATION = True
INVITES_MIN_USER_AGE_DAYS = 0

EMBEDDED_BOTS_ENABLED = True

SAVE_FRONTEND_STACKTRACES = True
EVENT_LOGS_ENABLED = True
STAGING_ERROR_NOTIFICATIONS = True

SYSTEM_ONLY_REALMS = set()  # type: Set[str]
USING_PGROONGA = True
# Flush cache after migration.
POST_MIGRATION_CACHE_FLUSHING = True  # type: bool

# Enable inline open graph preview in development for now
INLINE_URL_EMBED_PREVIEW = True

# Don't require anything about password strength in development
PASSWORD_MIN_LENGTH = 0
PASSWORD_MIN_GUESSES = 0

# SMTP settings for forwarding emails sent in development
# environment to an email account.
EMAIL_HOST = ""
EMAIL_HOST_USER = ""

# Two factor authentication: Use the fake backend for development.
TWO_FACTOR_CALL_GATEWAY = 'two_factor.gateways.fake.Fake'
TWO_FACTOR_SMS_GATEWAY = 'two_factor.gateways.fake.Fake'

# Make sendfile use django to serve files in development
SENDFILE_BACKEND = 'sendfile.backends.development'

# Set this True to send all hotspots in development
ALWAYS_SEND_ALL_HOTSPOTS = False  # type: bool
