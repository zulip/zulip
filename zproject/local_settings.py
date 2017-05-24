# This file is the Zulip local_settings.py configuration for the
# zulip.com installation of Zulip.  It shouldn't be used in other
# environments, but you may find it to be a a helpful reference when
# setting up your own Zulip installation to see how Zulip can be
# configured.
#
# On a normal Zulip production server, zproject/local_settings.py is a
# symlink to /etc/zulip/settings.py (based off prod_settings_template.py).
import platform
import six.moves.configparser
from base64 import b64decode
from typing import Optional, Set

config_file = six.moves.configparser.RawConfigParser()  # type: ignore # https://github.com/python/typeshed/pull/206
config_file.read("/etc/zulip/zulip.conf")

# Whether we're running in a production environment. Note that PRODUCTION does
# **not** mean hosted on Zulip.com; customer sites are PRODUCTION and VOYAGER
# and as such should not assume they are the main Zulip site.
PRODUCTION = config_file.has_option('machine', 'deploy_type')

# The following flags are left over from the various configurations of
# Zulip run by Zulip, Inc.  We will eventually be able to get rid of
# them and just have the PRODUCTION flag, but we need them for now.
ZULIP_COM_STAGING = PRODUCTION and config_file.get('machine', 'deploy_type') == 'zulip.com-staging'
ZULIP_COM = ((PRODUCTION and config_file.get('machine', 'deploy_type') == 'zulip.com-prod') or
             ZULIP_COM_STAGING)
if not ZULIP_COM:
    raise Exception("You should create your own local settings from prod_settings_template.")

ZULIP_FRIENDS_LIST_ID = '84b2f3da6b'
SHARE_THE_LOVE = True
SHOW_OSS_ANNOUNCEMENT = True
REGISTER_LINK_DISABLED = True
CUSTOM_LOGO_URL = "/static/images/logo/zulip-dropbox.png"
VERBOSE_SUPPORT_OFFERS = True

# This can be filled in automatically from the database, maybe
DEPLOYMENT_ROLE_NAME = 'zulip.com'

# XXX: replace me
CAMO_URI = 'https://external-content.zulipcdn.net/'

# Leave EMAIL_HOST unset or empty if you do not wish for emails to be sent
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_HOST_USER = 'zulip@zulip.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True

DEFAULT_FROM_EMAIL = "Zulip <zulip@zulip.com>"
# The noreply address to be used as Reply-To for certain generated emails.
NOREPLY_EMAIL_ADDRESS = "Zulip <noreply@zulip.com>"
WELCOME_EMAIL_SENDER = {'email': 'wdaher@zulip.com', 'name': 'Waseem Daher'}

SESSION_SERIALIZER = "django.contrib.sessions.serializers.PickleSerializer"

REMOTE_POSTGRES_HOST = "postgres.zulip.net"
STATSD_HOST = 'stats.zulip.net'

if ZULIP_COM_STAGING:
    EXTERNAL_HOST = 'staging.zulip.com'
    STATSD_PREFIX = 'staging'
    STAGING_ERROR_NOTIFICATIONS = True
    SAVE_FRONTEND_STACKTRACES = True
else:
    EXTERNAL_HOST = 'zulip.com'
    EXTERNAL_API_PATH = 'api.zulip.com'
    STATSD_PREFIX = 'app'

# Terms of Service
TERMS_OF_SERVICE = 'corporate/terms.md'
# Major version number (the stuff before the first '.') has to be an integer.
# Users will be asked to re-sign the TOS only when the major version number increases.
# A TOS_VERSION of None has a major version number of -1.
# TOS_VERSION = '1.0'
# FIRST_TIME_TOS_TEMPLATE = 'zulipchat_migration_tos.html'

# Buckets used for Amazon S3 integration for storing files and user avatars.
S3_AUTH_UPLOADS_BUCKET = "zulip-user-uploads"
S3_AVATAR_BUCKET = "humbug-user-avatars"

APNS_SANDBOX = False
APNS_FEEDBACK = "feedback_production"
APNS_CERT_FILE = "/etc/ssl/django-private/apns-dist.pem"
DBX_APNS_CERT_FILE = "/etc/ssl/django-private/dbx-apns-dist.pem"

GOOGLE_OAUTH2_CLIENT_ID = '835904834568-ag4p18v0sd9a0tero14r3gekn6shoen3.apps.googleusercontent.com'

# The email address pattern to use for auto-generated stream emails
# The %s will be replaced with a unique token.
if ZULIP_COM_STAGING:
    EMAIL_GATEWAY_PATTERN = "%s@streams.staging.zulip.com"
else:
    EMAIL_GATEWAY_PATTERN = "%s@streams.zulip.com"
EMAIL_GATEWAY_EXTRA_PATTERN_HACK = r'@[\w-]*\.zulip\.net'

# Email mirror configuration
# The email of the Zulip bot that the email gateway should post as.
EMAIL_GATEWAY_BOT = "emailgateway@zulip.com"


SSO_APPEND_DOMAIN = None  # type: Optional[str]

AUTHENTICATION_BACKENDS = ('zproject.backends.EmailAuthBackend',
                           'zproject.backends.GoogleMobileOauth2Backend')

# ALLOWED_HOSTS is used by django to determine which addresses
# Zulip can serve. This is a security measure.
# The following are the zulip.com hosts
ALLOWED_HOSTS = ['localhost', '.humbughq.com', '54.214.48.144', '54.213.44.54',
                 '54.213.41.54', '54.213.44.58', '54.213.44.73',
                 '54.200.19.65', '54.201.95.104', '54.201.95.206',
                 '54.201.186.29', '54.200.111.22',
                 '54.245.120.64', '54.213.44.83', '.zulip.com', '.zulip.net',
                 '54.244.50.66', '54.244.50.67', '54.244.50.68', '54.244.50.69', '54.244.50.70',
                 '54.244.50.64', '54.244.50.65', '54.244.50.74',
                 'chat.dropboxer.net']

NOTIFICATION_BOT = "notification-bot@zulip.com"
ERROR_BOT = "error-bot@zulip.com"
NEW_USER_BOT = "new-user-bot@zulip.com"

NAGIOS_SEND_BOT = 'iago@zulip.com'
NAGIOS_RECEIVE_BOT = 'othello@zulip.com'

# Our internal deployment has nagios checks for both staging and prod
NAGIOS_STAGING_SEND_BOT = 'iago@zulip.com'
NAGIOS_STAGING_RECEIVE_BOT = 'cordelia@zulip.com'

# Also used for support email in emails templates
ZULIP_ADMINISTRATOR = 'support@zulip.com'

ADMINS = (
    ('Zulip Error Reports', 'errors@zulip.com'),
)

EXTRA_INSTALLED_APPS = [
    'analytics',
    'zilencer',
    'corporate',
]

EVENT_LOGS_ENABLED = True
SYSTEM_ONLY_REALMS = set()  # type: Set[str]
