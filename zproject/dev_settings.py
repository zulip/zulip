
# For the Dev VM environment, we use the same settings as the
# sample prod_settings.py file, with a few exceptions.
from .prod_settings_template import *
import os
import pwd
from typing import Set

# We want LOCAL_UPLOADS_DIR to be an absolute path so that code can
# chdir without having problems accessing it.  Unfortunately, this
# means we need a duplicate definition of DEPLOY_ROOT with the one in
# settings.py.
DEPLOY_ROOT = os.path.realpath(os.path.dirname(os.path.dirname(__file__)))
LOCAL_UPLOADS_DIR = os.path.join(DEPLOY_ROOT, 'var/uploads')

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
    # 'zproject.backends.AzureADAuthBackend',
)

EXTERNAL_URI_SCHEME = "http://"
EMAIL_GATEWAY_PATTERN = "%s@" + EXTERNAL_HOST.split(':')[0]
NOTIFICATION_BOT = "notification-bot@zulip.com"
ERROR_BOT = "error-bot@zulip.com"
# SLOW_QUERY_LOGS_STREAM = "errors"
EMAIL_GATEWAY_BOT = "emailgateway@zulip.com"
PHYSICAL_ADDRESS = "Zulip Headquarters, 123 Octo Stream, South Pacific Ocean"
EXTRA_INSTALLED_APPS = ["zilencer", "analytics", "corporate"]
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

# FAKE_LDAP_MODE supports using a fake LDAP database in the
# development environment, without needing an LDAP server!
#
# Three modes are allowed, and each will setup Zulip and the fake LDAP
# database in a way appropriate for the corresponding mode described
# in https://zulip.readthedocs.io/en/latest/production/authentication-methods.html#ldap-including-active-directory
#   (A) If users' email addresses are in LDAP and used as username.
#   (B) If LDAP only has usernames but email addresses are of the form
#       username@example.com
#   (C) If LDAP usernames are completely unrelated to email addresses.
#
# Fake LDAP data has e.g. ("ldapuser1", "ldapuser1@zulip.com") for username/email.
FAKE_LDAP_MODE = None  # type: Optional[str]
# FAKE_LDAP_NUM_USERS = 8

if FAKE_LDAP_MODE:
    LDAP_APPEND_DOMAIN = None
    AUTH_LDAP_USER_DN_TEMPLATE = 'uid=%(user)s,ou=users,dc=zulip,dc=com'

    if FAKE_LDAP_MODE == 'a':
        import ldap
        from django_auth_ldap.config import LDAPSearch
        AUTH_LDAP_USER_SEARCH = LDAPSearch("ou=users,dc=zulip,dc=com",
                                           ldap.SCOPE_SUBTREE, "(email=%(user)s)")
    elif FAKE_LDAP_MODE == 'b':
        LDAP_APPEND_DOMAIN = 'zulip.com'
    elif FAKE_LDAP_MODE == 'c':
        LDAP_EMAIL_ATTR = 'email'  # type: Optional[str]
    AUTHENTICATION_BACKENDS += ('zproject.backends.ZulipLDAPAuthBackend',)  # type: ignore # tuple hackery

THUMBOR_URL = 'http://127.0.0.1:9995'
THUMBNAIL_IMAGES = True

SEARCH_PILLS_ENABLED = os.getenv('SEARCH_PILLS_ENABLED', False)

BILLING_ENABLED = True
