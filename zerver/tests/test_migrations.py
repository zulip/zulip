# These are tests for Zulip's database migrations.  System documented at:
#   https://zulip.readthedocs.io/en/latest/subsystems/schema-migrations.html
#
# You can also read
#   https://www.caktusgroup.com/blog/2016/02/02/writing-unit-tests-django-migrations/
# to get a tutorial on the framework that inspired this feature.

from zerver.lib.test_classes import MigrationsTestCase
from zerver.lib.test_helpers import use_db_models, make_client
from django.utils.timezone import now as timezone_now
from django.db.migrations.state import StateApps
from django.db.models.base import ModelBase

from zerver.models import get_stream
