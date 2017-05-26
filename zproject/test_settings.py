from __future__ import absolute_import
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

# Used to clone DBs in backend tests.
BACKEND_DATABASE_TEMPLATE = 'zulip_test_template'

DATABASES["default"] = {
    "NAME": "zulip_test",
    "USER": "zulip_test",
    "PASSWORD": LOCAL_DATABASE_PASSWORD,
    "HOST": "localhost",
    "SCHEMA": "zulip",
    "ENGINE": "django.db.backends.postgresql_psycopg2",
    "TEST_NAME": "django_zulip_tests",
    "OPTIONS": {"connection_factory": TimeTrackingConnection},
}
if USING_PGROONGA:
    # We need to have "pgroonga" schema before "pg_catalog" schema in
    # the PostgreSQL search path, because "pgroonga" schema overrides
    # the "@@" operator from "pg_catalog" schema, and "pg_catalog"
    # schema is searched first if not specified in the search path.
    # See also: http://www.postgresql.org/docs/current/static/runtime-config-client.html
    pg_options = '-c search_path=%(SCHEMA)s,zulip,public,pgroonga,pg_catalog' % \
        DATABASES['default']
    DATABASES['default']['OPTIONS']['options'] = pg_options

if "TORNADO_SERVER" in os.environ:
    # This covers the Casper test suite case
    TORNADO_SERVER = os.environ["TORNADO_SERVER"]
else:
    # This covers the backend test suite case
    TORNADO_SERVER = None
    CAMO_URI = 'https://external-content.zulipcdn.net/'
    CAMO_KEY = 'dummy'

if "CASPER_TESTS" in os.environ:
    CASPER_TESTS = True

# Decrease the get_updates timeout to 1 second.
# This allows CasperJS to proceed quickly to the next test step.
POLL_TIMEOUT = 1000

# Don't use the real message log for tests
EVENT_LOG_DIR = '/tmp/zulip-test-event-log'

# Print our emails rather than sending them
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

# Use production config from Webpack in tests
if CASPER_TESTS:
    WEBPACK_FILE = 'webpack-stats-production.json'
else:
    WEBPACK_FILE = 'webpack-stats-test.json'
WEBPACK_LOADER['DEFAULT']['STATS_FILE'] = os.path.join(STATIC_ROOT, 'webpack-bundles', WEBPACK_FILE)

if CASPER_TESTS:
    # Don't auto-restart Tornado server during casper tests
    AUTORELOAD = False
else:
    # Use local memory cache for backend tests.
    CACHES['default'] = {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'
    }
    LOGGING['loggers']['zulip.requests']['level'] = 'CRITICAL'
    LOGGING['loggers']['zulip.management']['level'] = 'CRITICAL'
    LOGGING['loggers']['django.request'] = {'level': 'ERROR'}
    LOGGING['loggers']['fakeldap'] = {'level': 'ERROR'}

# Enable file:/// hyperlink support by default in tests
ENABLE_FILE_LINKS = True


LOCAL_UPLOADS_DIR = 'var/test_uploads'

S3_KEY = 'test-key'
S3_SECRET_KEY = 'test-secret-key'
S3_AUTH_UPLOADS_BUCKET = 'test-authed-bucket'
REALMS_HAVE_SUBDOMAINS = bool(os.getenv('REALMS_HAVE_SUBDOMAINS', False))

# Test Custom TOS template rendering
TERMS_OF_SERVICE = 'corporate/terms.md'

INLINE_URL_EMBED_PREVIEW = False

HOME_NOT_LOGGED_IN = '/login'
LOGIN_URL = '/accounts/login'

# By default will not send emails when login occurs.
# Explicity set this to True within tests that must have this on.
SEND_LOGIN_EMAILS = False
