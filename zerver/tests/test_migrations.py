# These are tests for Zulip's database migrations.  System documented at:
#   https://zulip.readthedocs.io/en/latest/subsystems/schema-migrations.html
#
# You can also read
#   https://www.caktusgroup.com/blog/2016/02/02/writing-unit-tests-django-migrations/
# to get a tutorial on the framework that inspired this feature.
from django.db.migrations.state import StateApps
from typing_extensions import override

from zerver.lib.test_classes import MigrationsTestCase

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


class FixDeletedUserEmail(MigrationsTestCase):
    migrate_from = "0804_backfill_user_created_audit_logs"
    migrate_to = "0805_fix_deleteduser_email"

    @override
    def setUpBeforeMigration(self, apps: StateApps) -> None:
        UserProfile = apps.get_model("zerver", "UserProfile")

        # Simulate a user deleted before the fix in 208c0c303405,
        # after 0439_fix_deleteduser_email repaired delivery_email.
        deleted_user = self.example_user("hamlet")
        UserProfile.objects.filter(id=deleted_user.id).update(
            is_active=False,
            email=f"deleteduser{deleted_user.id}@https://zulip.testserver",
            delivery_email=f"deleteduser{deleted_user.id}@zulip.testserver",
        )
        self.deleted_user_id = deleted_user.id

        # A normal active user, as a control.
        control_user = self.example_user("cordelia")
        self.control_user_id = control_user.id
        self.control_user_email = control_user.email

        # A deactivated user with a valid email, as a control for the
        # is_active=False part of the migration's filter.
        deactivated_user = self.example_user("othello")
        UserProfile.objects.filter(id=deactivated_user.id).update(is_active=False)
        self.deactivated_user_id = deactivated_user.id
        self.deactivated_user_email = deactivated_user.email

    def test_deleted_user_email_fixed(self) -> None:
        UserProfile = self.apps.get_model("zerver", "UserProfile")

        deleted_user = UserProfile.objects.get(id=self.deleted_user_id)
        self.assertEqual(deleted_user.email, f"deleteduser{deleted_user.id}@zulip.testserver")
        self.assertEqual(deleted_user.email, deleted_user.delivery_email)

        control_user = UserProfile.objects.get(id=self.control_user_id)
        self.assertEqual(control_user.email, self.control_user_email)

        deactivated_user = UserProfile.objects.get(id=self.deactivated_user_id)
        self.assertEqual(deactivated_user.email, self.deactivated_user_email)
