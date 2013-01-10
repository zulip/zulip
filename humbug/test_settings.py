from settings import *
import os

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

# Disable desktop notifications because CasperJS can't handle them;
# window.webkitNotifications.requestPermission() throws a type error
ENABLE_NOTIFICATIONS = False

# Don't use the real message log for tests
MESSAGE_LOG = "/tmp/test-message-log"

# Print our emails rather than sending them
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
