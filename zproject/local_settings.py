# This file is the Zulip local_settings.py configuration for the
# zulip.com installation of Zulip.  It shouldn't be used in other
# environments, but you may find it to be a a helpful reference when
# setting up your own Zulip installation to see how Zulip can be
# configured.
#
# On a normal Zulip production server, zproject/local_settings.py is a
# symlink to /etc/zulip/settings.py (based off local_settings_template.py).
import platform
import six.moves.configparser
from base64 import b64decode

config_file = six.moves.configparser.RawConfigParser()
config_file.read("/etc/zulip/zulip.conf")

# Whether we're running in a production environment. Note that PRODUCTION does
# **not** mean hosted on Zulip.com; customer sites are PRODUCTION and VOYAGER
# and as such should not assume they are the main Zulip site.
PRODUCTION = config_file.has_option('machine', 'deploy_type')

# The following flags are left over from the various configurations of
# Zulip run by Zulip, Inc.  We will eventually be able to get rid of
# them and just have the PRODUCTION flag, but we need them for now.
ZULIP_COM_STAGING = PRODUCTION and config_file.get('machine', 'deploy_type') == 'zulip.com-staging'
ZULIP_COM = ((PRODUCTION and config_file.get('machine', 'deploy_type') == 'zulip.com-prod')
             or ZULIP_COM_STAGING)
if not ZULIP_COM:
    raise Exception("You should create your own local settings from local_settings_template.")

ZULIP_FRIENDS_LIST_ID = '84b2f3da6b'

# This can be filled in automatically from the database, maybe
DEPLOYMENT_ROLE_NAME = 'zulip.com'

# XXX: replace me
CAMO_URI = 'https://external-content.zulipcdn.net/'

# Leave EMAIL_HOST unset or empty if you do not wish for emails to be sent
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_HOST_USER = 'zulip@zulip.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True

# We use mandrill, so this doesn't actually get used on our hosted deployment
DEFAULT_FROM_EMAIL = "Zulip <zulip@zulip.com>"
# The noreply address to be used as Reply-To for certain generated emails.
NOREPLY_EMAIL_ADDRESS = "noreply@zulip.com"

SESSION_SERIALIZER = "django.contrib.sessions.serializers.PickleSerializer"

REMOTE_POSTGRES_HOST = "postgres.zulip.net"
STATSD_HOST = 'stats.zulip.net'

if ZULIP_COM_STAGING:
    EXTERNAL_HOST = 'staging.zulip.com'
    STATSD_PREFIX = 'staging'
else:
    EXTERNAL_HOST = 'zulip.com'
    EXTERNAL_API_PATH = 'api.zulip.com'
    STATSD_PREFIX = 'app'

# Legacy zulip.com bucket used for old-style S3 uploads.
S3_BUCKET="humbug-user-uploads"
# Buckets used for Amazon S3 integration for storing files and user avatars.
S3_AUTH_UPLOADS_BUCKET = "zulip-user-uploads"
S3_AVATAR_BUCKET="humbug-user-avatars"

APNS_SANDBOX = "push_production"
APNS_FEEDBACK = "feedback_production"
APNS_CERT_FILE = "/etc/ssl/django-private/apns-dist.pem"
DBX_APNS_CERT_FILE = "/etc/ssl/django-private/dbx-apns-dist.pem"

GOOGLE_CLIENT_ID = "835904834568-77mtr5mtmpgspj9b051del9i9r5t4g4n.apps.googleusercontent.com"

GOOGLE_OAUTH2_CLIENT_ID = '835904834568-ag4p18v0sd9a0tero14r3gekn6shoen3.apps.googleusercontent.com'

# Administrator domain for this install
ADMIN_DOMAIN = "zulip.com"

# The email address pattern to use for auto-generated stream emails
# The %s will be replaced with a unique token.
if ZULIP_COM_STAGING:
    EMAIL_GATEWAY_PATTERN = "%s@streams.staging.zulip.com"
else:
    EMAIL_GATEWAY_PATTERN = "%s@streams.zulip.com"

# Email mirror configuration
# The email of the Zulip bot that the email gateway should post as.
EMAIL_GATEWAY_BOT = "emailgateway@zulip.com"


SSO_APPEND_DOMAIN = None

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
