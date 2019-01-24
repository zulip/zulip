import os
# test_settings.py works differently from
# dev_settings.py/prod_settings.py; it actually is directly referenced
# by the test suite as DJANGO_SETTINGS_MODULE and imports settings.py
# directly and then hacks up the values that are different for the
# test suite.  As will be explained, this is kinda messy and probably
# we'd be better off switching it to work more like dev_settings.py,
# but for now, this is what we have.
#
# An important downside of the test_settings.py approach is that if we
# want to change any settings that settings.py then computes
# additional settings from (e.g. EXTERNAL_HOST), we need to do a hack
# like the below line(s) before we import from settings, for
# transmitting the value of EXTERNAL_HOST to dev_settings.py so that
# it can be set there, at the right place in the settings.py flow.
# Ick.
if os.getenv("EXTERNAL_HOST") is None:
    os.environ["EXTERNAL_HOST"] = "testserver"
from .settings import *

# Clear out the REALM_HOSTS set in dev_settings.py
REALM_HOSTS = {}

# Used to clone DBs in backend tests.
BACKEND_DATABASE_TEMPLATE = 'zulip_test_template'

DATABASES["default"] = {
    "NAME": os.getenv("ZULIP_DB_NAME", "zulip_test"),
    "USER": "zulip_test",
    "PASSWORD": LOCAL_DATABASE_PASSWORD,
    "HOST": "localhost",
    "SCHEMA": "zulip",
    "ENGINE": "django.db.backends.postgresql",
    "TEST_NAME": "django_zulip_tests",
    "OPTIONS": {"connection_factory": TimeTrackingConnection},
}

if "TORNADO_SERVER" in os.environ:
    # This covers the Casper test suite case
    TORNADO_SERVER = os.environ["TORNADO_SERVER"]
else:
    # This covers the backend test suite case
    TORNADO_SERVER = None
    CAMO_URI = 'https://external-content.zulipcdn.net/external_content/'
    CAMO_KEY = 'dummy'

if "CASPER_TESTS" in os.environ:
    CASPER_TESTS = True
    # Disable search pills prototype for production use
    SEARCH_PILLS_ENABLED = False

# Decrease the get_updates timeout to 1 second.
# This allows CasperJS to proceed quickly to the next test step.
POLL_TIMEOUT = 1000

# Don't use the real message log for tests
EVENT_LOG_DIR = '/tmp/zulip-test-event-log'

# Stores the messages in `django.core.mail.outbox` rather than sending them.
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

# The test suite uses EmailAuthBackend
AUTHENTICATION_BACKENDS += ('zproject.backends.EmailAuthBackend',)

# Configure Google Oauth2
GOOGLE_OAUTH2_CLIENT_ID = "test_client_id"

# Makes testing LDAP backend require less mocking
AUTH_LDAP_ALWAYS_UPDATE_USER = False

TEST_SUITE = True
RATE_LIMITING = False
# Don't use rabbitmq from the test suite -- the user_profile_ids for
# any generated queue elements won't match those being used by the
# real app.
USING_RABBITMQ = False

# Disable the tutorial because it confuses the client tests.
TUTORIAL_ENABLED = False

# Disable use of memcached for caching
CACHES['database'] = {
    'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
    'LOCATION': 'zulip-database-test-cache',
    'TIMEOUT': 3600,
    'CONN_MAX_AGE': 600,
    'OPTIONS': {
        'MAX_ENTRIES': 100000
    }
}

# Disable caching on sessions to make query counts consistent
SESSION_ENGINE = "django.contrib.sessions.backends.db"

# Use production config from Webpack in tests
if CASPER_TESTS:
    WEBPACK_FILE = 'webpack-stats-production.json'
else:
    WEBPACK_FILE = os.path.join('var', 'webpack-stats-test.json')
WEBPACK_LOADER['DEFAULT']['STATS_FILE'] = os.path.join(DEPLOY_ROOT, WEBPACK_FILE)

# Don't auto-restart Tornado server during automated tests
AUTORELOAD = False

if not CASPER_TESTS:
    # Use local memory cache for backend tests.
    CACHES['default'] = {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'
    }

    def set_loglevel(logger_name, level) -> None:
        LOGGING['loggers'].setdefault(logger_name, {})['level'] = level
    set_loglevel('zulip.requests', 'CRITICAL')
    set_loglevel('zulip.management', 'CRITICAL')
    set_loglevel('django.request', 'ERROR')
    set_loglevel('fakeldap', 'ERROR')
    set_loglevel('zulip.send_email', 'ERROR')
    set_loglevel('zerver.lib.push_notifications', 'WARNING')
    set_loglevel('zerver.lib.digest', 'ERROR')
    set_loglevel('zerver.lib.email_mirror', 'ERROR')
    set_loglevel('zerver.worker.queue_processors', 'WARNING')
    set_loglevel('stripe', 'WARNING')

# Enable file:/// hyperlink support by default in tests
ENABLE_FILE_LINKS = True


LOCAL_UPLOADS_DIR = 'var/test_uploads'

S3_KEY = 'test-key'
S3_SECRET_KEY = 'test-secret-key'
S3_AUTH_UPLOADS_BUCKET = 'test-authed-bucket'
S3_AVATAR_BUCKET = 'test-avatar-bucket'

# Test Custom TOS template rendering
TERMS_OF_SERVICE = 'corporate/terms.md'

INLINE_URL_EMBED_PREVIEW = False

HOME_NOT_LOGGED_IN = '/login/'
LOGIN_URL = '/accounts/login/'

# By default will not send emails when login occurs.
# Explicity set this to True within tests that must have this on.
SEND_LOGIN_EMAILS = False

GOOGLE_OAUTH2_CLIENT_ID = "id"
GOOGLE_OAUTH2_CLIENT_SECRET = "secret"

SOCIAL_AUTH_GITHUB_KEY = "key"
SOCIAL_AUTH_GITHUB_SECRET = "secret"
SOCIAL_AUTH_SUBDOMAIN = 'www'

# By default two factor authentication is disabled in tests.
# Explicitly set this to True within tests that must have this on.
TWO_FACTOR_AUTHENTICATION_ENABLED = False
PUSH_NOTIFICATION_BOUNCER_URL = None

# Disable messages from slow queries as they affect backend tests.
SLOW_QUERY_LOGS_STREAM = None

THUMBOR_URL = 'http://127.0.0.1:9995'
THUMBNAIL_IMAGES = True
THUMBOR_SERVES_CAMO = True

# Logging the emails while running the tests adds them
# to /emails page.
DEVELOPMENT_LOG_EMAILS = False
