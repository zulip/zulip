from settings import *

DATABASES["default"] = {"NAME": "zephyr/tests/zephyrdb.test",
                        "ENGINE": "django.db.backends.sqlite3",
                        "OPTIONS": { "timeout": 20, },}

