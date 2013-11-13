# Secret Django settings for the Zulip project
import platform
import ConfigParser

config_file = ConfigParser.RawConfigParser()
config_file.read("/etc/zulip/zulip.conf")

# Whether we're running in a production environment. Note that DEPLOYED does
# **not** mean hosted by us; customer sites are DEPLOYED and ENTERPRISE
# and as such should not for example assume they are the main Zulip site.
DEPLOYED = config_file.has_option('machine', 'deploy_type')
STAGING_DEPLOYED = DEPLOYED and config_file.get('machine', 'deploy_type') == 'staging'
TESTING_DEPLOYED = DEPLOYED and config_file.get('machine', 'deploy_type') == 'test'

ENTERPRISE = DEPLOYED and config_file.get('machine', 'deploy_type') == 'enterprise'

# Make this unique, and don't share it with anybody.
SECRET_KEY = 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'

# A fixed salt used for hashing in certain places, e.g. email-based
# username generation.
HASH_SALT = 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'

# Use this salt to hash a user's email into a filename for their user-uploaded
# avatar.  If this salt is discovered, attackers will only be able to determine
# that the owner of an email account has uploaded an avatar to Zulip, which isn't
# the end of the world.  Don't use the salt where there is more security exposure.
AVATAR_SALT = 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'

# Used just for generating initial passwords (only used in testing environments).
if not DEPLOYED:
    INITIAL_PASSWORD_SALT = 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'

# A shared secret, used to authenticate different parts of the app to each other.
# FIXME: store this password more securely
SHARED_SECRET = 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'

RABBITMQ_PASSWORD = 'xxxxxxxxxxxxxxxx'

MAILCHIMP_API_KEY = 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx-us4'
ZULIP_FRIENDS_LIST_ID = '84b2f3da6b'

# This can be filled in automatically from the database, maybe
DEPLOYMENT_ROLE_NAME = 'zulip.com'
DEPLOYMENT_ROLE_KEY = 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'

# This comes from our mandrill accounts page
MANDRILL_API_KEY = 'xxxxxxxxxxxxxxxxxxxxxx'

# This should be synced with our camo installation
CAMO_KEY = 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'

# Leave EMAIL_HOST unset or empty if you do not wish for emails to be sent
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_HOST_USER = 'zulip@zulip.com'
EMAIL_HOST_PASSWORD = 'xxxxxxxxxxxxxxxx'
EMAIL_PORT = 587
EMAIL_USE_TLS = True

SESSION_SERIALIZER = "django.contrib.sessions.serializers.PickleSerializer"

if TESTING_DEPLOYED:
    EXTERNAL_HOST = platform.node()
    EXTERNAL_API_HOST = 'https://%s/api' % (platform.node())
elif STAGING_DEPLOYED:
    EXTERNAL_HOST = 'staging.zulip.com'
    EXTERNAL_API_HOST = 'https://staging.zulip.com/api'
elif DEPLOYED:
    EXTERNAL_HOST = 'zulip.com'
    EXTERNAL_API_HOST = 'https://api.zulip.com'
else:
    EXTERNAL_HOST = 'localhost:9991'
    EXTERNAL_API_HOST = 'http://localhost:9991/api'

EMBEDLY_KEY="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

# For now, ENTERPRISE is only testing, so write to our test buckets
if DEPLOYED and not ENTERPRISE:
    S3_KEY="xxxxxxxxxxxxxxxxxxxx"
    S3_SECRET_KEY="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    S3_BUCKET="humbug-user-uploads"
    S3_AUTH_UPLOADS_BUCKET = "zulip-user-uploads"
    S3_AVATAR_BUCKET="humbug-user-avatars"

    MIXPANEL_TOKEN="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
else:
    S3_KEY="xxxxxxxxxxxxxxxxxxxx"
    S3_SECRET_KEY="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    S3_BUCKET="humbug-user-uploads-test"
    S3_AUTH_UPLOADS_BUCKET = "zulip-user-uploads-test"
    S3_AVATAR_BUCKET="humbug-user-avatars-test"

    MIXPANEL_TOKEN="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    LOCAL_DATABASE_PASSWORD="xxxxxxxxxxxx"

# Twitter API credentials
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

if STAGING_DEPLOYED:
    APNS_SANDBOX = "push_sandbox"
    APNS_FEEDBACK = "feedback_sandbox"
    APNS_CERT_FILE = "/etc/ssl/django-private/apns-dev.pem"
elif DEPLOYED:
    APNS_SANDBOX = "push_production"
    APNS_FEEDBACK = "feedback_production"
    APNS_CERT_FILE = "/etc/ssl/django-private/apns-dist.pem"
else:
    APNS_SANDBOX = "push_sandbox"
    APNS_FEEDBACK = "feedback_sandbox"
    APNS_CERT_FILE = "/etc/ssl/django-private/apns-dev.pem"

# Administrator domain for this install
ADMIN_DOMAIN = "zulip.com"

# Email mirror configuration
# The email of the Zulip bot that the email gateway
# should post as
EMAIL_GATEWAY_BOT = "emailgateway@zulip.com"

EMAIL_GATEWAY_LOGIN = "emailgateway@zulip.com"
EMAIL_GATEWAY_PASSWORD = "xxxxxxxxxxxxxxxx"
EMAIL_GATEWAY_IMAP_SERVER = "imap.gmail.com"
EMAIL_GATEWAY_IMAP_PORT = 993
EMAIL_GATEWAY_IMAP_FOLDER = "INBOX"

# The email address pattern to use for auto-generated stream emails
# The %s will be replaced with a unique token, and the resulting email
# must be delivered to the Inbox of the EMAIL_GATEWAY_LOGIN account above
EMAIL_GATEWAY_PATTERN = "%s@streams.zulip.com"

SSO_APPEND_DOMAIN = None

AUTHENTICATION_BACKENDS = ('zproject.backends.EmailAuthBackend',
                           'zproject.backends.GoogleBackend')


DROPBOX_APP_KEY = "xxxxxxxxxxxxxxx"

NOTIFICATION_BOT = "notification-bot@zulip.com"
ERROR_BOT = "error-bot@zulip.com"
NEW_USER_BOT = "new-user-bot@zulip.com"

NAGIOS_SEND_BOT = 'iago@zulip.com'
NAGIOS_RECEIVE_BOT = 'othello@zulip.com'

# Our internal deployment has nagios checks for both staging and prod
NAGIOS_STAGING_SEND_BOT = 'iago@zulip.com'
NAGIOS_STAGING_RECEIVE_BOT = 'cordelia@zulip.com'

ZULIP_ADMINISTRATOR = 'support@zulip.com'

# TODO: Store this info in the database
# Also note -- the email gateway bot is automatically added.
API_SUPER_USERS = set(["tabbott/extra@mit.edu",
                       "irc-bot@zulip.com",
                       "bot1@customer35.invalid"])

ADMINS = (
    ('Zulip Error Reports', 'errors@zulip.com'),
)
