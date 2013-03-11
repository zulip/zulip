from settings import *
import os
import logging

DATABASES["default"] = {"NAME": "zephyr/tests/zephyrdb.test",
                        "ENGINE": "django.db.backends.sqlite3",
                        "OPTIONS": { "timeout": 20, },}

if "TORNADO_SERVER" in os.environ:
    TORNADO_SERVER = os.environ["TORNADO_SERVER"]
else:
    TORNADO_SERVER = None

# Decrease the get_updates timeout to 1 second.
# This allows CasperJS to proceed quickly to the next test step.
POLL_TIMEOUT = 1000

# Don't use the real message log for tests
EVENT_LOG_DIR = '/tmp/humbug-test-event-log'

# Print our emails rather than sending them
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

TEST_SUITE = True

# Don't use rabbitmq from the test suite -- the user_profile_ids for
# any generated queue elements won't match those being used by the
# real app.
USING_RABBITMQ = False

# Disable use of memcached for caching
CACHES = {
    'default': {
        'BACKEND':  'django.core.cache.backends.dummy.DummyCache',
        'LOCATION': 'humbug-default-test-cache',
        'TIMEOUT':  3600,
        'OPTIONS': {
            'MAX_ENTRIES': 100000
        },
    },
    'database': {
        'BACKEND':  'django.core.cache.backends.dummy.DummyCache',
        'LOCATION': 'humbug-database-test-cache',
        'TIMEOUT':  3600,
        'OPTIONS': {
            'MAX_ENTRIES': 100000
        },
    } }

requests_logger = logging.getLogger('humbug.requests')
requests_logger.setLevel(logging.WARNING)
