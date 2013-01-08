from settings import *

DATABASES["default"] = {"NAME": "zephyr/tests/zephyrdb.test",
                        "ENGINE": "django.db.backends.sqlite3",
                        "OPTIONS": { "timeout": 20, },}

TORNADO_SERVER = 'http://localhost:9983'

# Decrease the get_updates timeout to 1 second.
# This allows CasperJS to proceed quickly to the next test step.
POLL_TIMEOUT = 1000

# Disable desktop notifications because CasperJS can't handle them;
# window.webkitNotifications.requestPermission() throws a type error
ENABLE_NOTIFICATIONS = False
