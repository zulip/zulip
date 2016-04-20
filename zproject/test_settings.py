from __future__ import absolute_import
from .settings import *
import os

DATABASES["default"] = {"NAME": "zulip_test",
                        "USER": "zulip_test",
                        "PASSWORD": LOCAL_DATABASE_PASSWORD,
                        "HOST": "localhost",
                        "SCHEMA": "zulip",
                        "ENGINE": "django.db.backends.postgresql_psycopg2",
                        "TEST_NAME": "django_zulip_tests",
                        "OPTIONS": {"connection_factory": TimeTrackingConnection },}


if "TORNADO_SERVER" in os.environ:
    TORNADO_SERVER = os.environ["TORNADO_SERVER"]
else:
    TORNADO_SERVER = None

# Decrease the get_updates timeout to 1 second.
# This allows CasperJS to proceed quickly to the next test step.
POLL_TIMEOUT = 1000

# Don't use the real message log for tests
EVENT_LOG_DIR = '/tmp/zulip-test-event-log'

# Print our emails rather than sending them
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

# The test suite uses EmailAuthBackend
AUTHENTICATION_BACKENDS += ('zproject.backends.EmailAuthBackend',)

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
    'BACKEND':  'django.core.cache.backends.dummy.DummyCache',
    'LOCATION': 'zulip-database-test-cache',
    'TIMEOUT':  3600,
    'CONN_MAX_AGE': 600,
    'OPTIONS': {
        'MAX_ENTRIES': 100000
    }
}

LOGGING['loggers']['zulip.requests']['level'] = 'CRITICAL'
LOGGING['loggers']['zulip.management']['level'] = 'CRITICAL'

CAMO_URI = 'https://external-content.zulipcdn.net/'
CAMO_KEY = 'dummy'

LOCAL_UPLOADS_DIR = 'test_uploads'
