# Non-secret secret Django settings for the Zulip project
import platform
import ConfigParser
from base64 import b64decode

config_file = ConfigParser.RawConfigParser()
config_file.read("/etc/zulip/zulip.conf")

# Whether we're running in a production environment. Note that DEPLOYED does
# **not** mean hosted by us; customer sites are DEPLOYED and ENTERPRISE
# and as such should not for example assume they are the main Zulip site.
DEPLOYED = config_file.has_option('machine', 'deploy_type')
STAGING_DEPLOYED = DEPLOYED and config_file.get('machine', 'deploy_type') == 'staging'
TESTING_DEPLOYED = DEPLOYED and config_file.get('machine', 'deploy_type') == 'test'

ENTERPRISE = DEPLOYED and config_file.get('machine', 'deploy_type') == 'enterprise'

secrets_file = ConfigParser.RawConfigParser()
if DEPLOYED:
    secrets_file.read("/etc/zulip/zulip-secrets.conf")
else:
    secrets_file.read("zproject/dev-secrets.conf")

def get_secret(key):
    if secrets_file.has_option('secrets', key):
        return secrets_file.get('secrets', key)
    return None

MAILCHIMP_API_KEY = get_secret("mailchimp_api_key")
ZULIP_FRIENDS_LIST_ID = '84b2f3da6b'

# This can be filled in automatically from the database, maybe
DEPLOYMENT_ROLE_NAME = 'zulip.com'
DEPLOYMENT_ROLE_KEY = get_secret("deployment_role_key")

# This comes from our mandrill accounts page
MANDRILL_API_KEY = get_secret("mandrill_api_key")

# XXX: replace me
CAMO_URI = 'https://external-content.zulipcdn.net/'

# Leave EMAIL_HOST unset or empty if you do not wish for emails to be sent
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_HOST_USER = 'zulip@zulip.com'
EMAIL_HOST_PASSWORD = get_secret('email_password')
EMAIL_PORT = 587
EMAIL_USE_TLS = True

# We use mandrill, so this doesn't actually get used on our hosted deployment
DEFAULT_FROM_EMAIL = "Zulip <zulip@zulip.com>"
# The noreply address to be used as Reply-To for certain generated emails.
NOREPLY_EMAIL_ADDRESS = "noreply@zulip.com"

SESSION_SERIALIZER = "django.contrib.sessions.serializers.PickleSerializer"

if DEPLOYED:
    EXTERNAL_URI_SCHEME = "https://"
else:
    EXTERNAL_URI_SCHEME = "http://"

if TESTING_DEPLOYED:
    EXTERNAL_HOST = platform.node()
elif STAGING_DEPLOYED:
    EXTERNAL_HOST = 'staging.zulip.com'
elif DEPLOYED:
    EXTERNAL_HOST = 'zulip.com'
    EXTERNAL_API_PATH = 'api.zulip.com'
else:
    EXTERNAL_HOST = 'localhost:9991'

# For now, ENTERPRISE is only testing, so write to our test buckets
if DEPLOYED and not ENTERPRISE:
    S3_BUCKET="humbug-user-uploads"
    S3_AUTH_UPLOADS_BUCKET = "zulip-user-uploads"
    S3_AVATAR_BUCKET="humbug-user-avatars"
else:
    S3_BUCKET="humbug-user-uploads-test"
    S3_AUTH_UPLOADS_BUCKET = "zulip-user-uploads-test"
    S3_AVATAR_BUCKET="humbug-user-avatars-test"

# Twitter API credentials
# Secrecy not required because its only used for R/O requests.
# Please don't make us go over our rate limit.
if STAGING_DEPLOYED or TESTING_DEPLOYED:
    # Application: "Humbug HQ"
    TWITTER_CONSUMER_KEY = "xxxxxxxxxxxxxxxxxxxxxx"
    TWITTER_CONSUMER_SECRET = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    TWITTER_ACCESS_TOKEN_KEY = "xxxxxxxxx-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    TWITTER_ACCESS_TOKEN_SECRET = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
elif DEPLOYED and not ENTERPRISE:
    # This is the real set of API credentials used by our real server,
    # and we probably shouldn't test with it just so we don't waste its requests
    # Application: "Humbug HQ - Production"
    TWITTER_CONSUMER_KEY = "xxxxxxxxxxxxxxxxxxxxx"
    TWITTER_CONSUMER_SECRET = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    TWITTER_ACCESS_TOKEN_KEY = "xxxxxxxxx-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    TWITTER_ACCESS_TOKEN_SECRET = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
else:
    # Application: "Humbug HQ Test"
    TWITTER_CONSUMER_KEY = "xxxxxxxxxxxxxxxxxxxxxx"
    TWITTER_CONSUMER_SECRET = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    TWITTER_ACCESS_TOKEN_KEY = "xxxxxxxxx-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    TWITTER_ACCESS_TOKEN_SECRET = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

if DEPLOYED or STAGING_DEPLOYED:
    APNS_SANDBOX = "push_production"
    APNS_FEEDBACK = "feedback_production"
    APNS_CERT_FILE = "/etc/ssl/django-private/apns-dist.pem"
    DBX_APNS_CERT_FILE = "/etc/ssl/django-private/dbx-apns-dist.pem"
else:
    APNS_SANDBOX = "push_sandbox"
    APNS_FEEDBACK = "feedback_sandbox"
    APNS_CERT_FILE = "/etc/ssl/django-private/apns-dev.pem"
    DBX_APNS_CERT_FILE = "/etc/ssl/django-private/dbx-apns-dev.pem"

GOOGLE_CLIENT_ID = "835904834568-77mtr5mtmpgspj9b051del9i9r5t4g4n.apps.googleusercontent.com"

if DEPLOYED:
    GOOGLE_OAUTH2_CLIENT_ID = '835904834568-ag4p18v0sd9a0tero14r3gekn6shoen3.apps.googleusercontent.com'
    GOOGLE_OAUTH2_CLIENT_SECRET  = get_secret('google_oauth2_client_secret')
else:
    # Google OAUTH2 for dev with the redirect uri set to http://localhost:9991/accounts/login/google/done/
    GOOGLE_OAUTH2_CLIENT_ID = '607830223128-4qgthc7ofdqce232dk690t5jgkm1ce33.apps.googleusercontent.com'
    GOOGLE_OAUTH2_CLIENT_SECRET  = get_secret('dev_google_oauth2_client_secret')

# Administrator domain for this install
ADMIN_DOMAIN = "zulip.com"

# The email address pattern to use for auto-generated stream emails
# The %s will be replaced with a unique token.
if STAGING_DEPLOYED:
    EMAIL_GATEWAY_PATTERN = "%s@streams.staging.zulip.com"
elif DEPLOYED:
    EMAIL_GATEWAY_PATTERN = "%s@streams.zulip.com"
else:
    EMAIL_GATEWAY_PATTERN = "%s@" + EXTERNAL_HOST

# Email mirror configuration
# The email of the Zulip bot that the email gateway should post as.
EMAIL_GATEWAY_BOT = "emailgateway@zulip.com"


SSO_APPEND_DOMAIN = None

if DEPLOYED:
    AUTHENTICATION_BACKENDS = ('zproject.backends.EmailAuthBackend',
                               'zproject.backends.GoogleMobileOauth2Backend',
                               'zproject.backends.GoogleBackend')
else:
    ## WARNING: ENABLING DevAuthBackend WILL ENABLE
    ## ANYONE TO LOG IN AS ANY USER.
    AUTHENTICATION_BACKENDS = ('zproject.backends.DevAuthBackend',)



DROPBOX_APP_KEY = "xxxxxxxxxxxxxxx"

JWT_AUTH_KEYS = {}

# Redis authentication
if STAGING_DEPLOYED or TESTING_DEPLOYED:
    REDIS_PASSWORD = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
else:
    REDIS_PASSWORD = None

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

# TODO: Store this info in the database
# Also note -- the email gateway bot is automatically added.
API_SUPER_USERS = set(["tabbott/extra@mit.edu",
                       "irc-bot@zulip.com",
                       "bot1@customer35.invalid",
                       "bot1@customer36.invalid",
                       "hipchat-bot@zulip.com",])

ADMINS = (
    ('Zulip Error Reports', 'errors@zulip.com'),
)
