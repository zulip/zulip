from .settings import *

DATABASES["default"] = {
    "NAME": "zulip_slack_importer_test",
    "USER": "zulip_test",
    "PASSWORD": LOCAL_DATABASE_PASSWORD,
    "HOST": "localhost",
    "SCHEMA": "zulip",
    "ENGINE": "django.db.backends.postgresql_psycopg2",
}
