# These are tests for Zulip's database migrations.  System documented at:
#   https://zulip.readthedocs.io/en/latest/subsystems/schema-migrations.html
#
# You can also read
#   https://www.caktusgroup.com/blog/2016/02/02/writing-unit-tests-django-migrations/
# to get a tutorial on the framework that inspired this feature.
from django.db import connections
from django.db.migrations.state import StateApps
from typing_extensions import override

from zerver.lib.test_classes import MigrationsTestCase
from zerver.lib.test_helpers import use_db_models

# Important note: These tests are very expensive, and details of
# Django's database transaction model mean it does not super work to
# have a lot of migrations tested in this file at once; so we usually
# delete the old migration tests when adding a new one, so this file
# always has a single migration test in it as an example.
#
# The error you get with multiple similar tests doing migrations on
# the same table is this (table name may vary):
#
#   django.db.utils.OperationalError: cannot ALTER TABLE
#   "zerver_subscription" because it has pending trigger events
#
# As a result, we generally mark these tests as skipped once they have
# been tested for a migration being merged.


class UserMessageIndex(MigrationsTestCase):
    migrate_from = "0484_preregistrationrealm_default_language"
    migrate_to = "0485_alter_usermessage_flags_and_add_index"

    def index_exists(self, index_name: str) -> bool:
        table_name = "zerver_usermessage"
        connection = connections["default"]

        with connection.cursor() as cursor:
            # We use parameterized query to prevent SQL injection vulnerabilities
            query = "SELECT indexname FROM pg_indexes WHERE tablename = %s AND indexname = %s"
            cursor.execute(query, [table_name, index_name])
            return cursor.fetchone() is not None

    @use_db_models
    @override
    def setUpBeforeMigration(self, apps: StateApps) -> None:
        self.assertTrue(self.index_exists("zerver_usermessage_wildcard_mentioned_message_id"))
        self.assertFalse(self.index_exists("zerver_usermessage_any_mentioned_message_id"))

    def test_new_index_created_old_index_not_removed(self) -> None:
        self.assertTrue(self.index_exists("zerver_usermessage_wildcard_mentioned_message_id"))
        self.assertTrue(self.index_exists("zerver_usermessage_any_mentioned_message_id"))
