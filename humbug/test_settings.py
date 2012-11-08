from settings import *

DATABASES["default"] = {"NAME": "zephyr/tests/zephyrdb.test",
                        "ENGINE": "django.db.backends.sqlite3",
                        "OPTIONS": { "timeout": 20, },}

TORNADO_SERVER = 'http://localhost:9983'
