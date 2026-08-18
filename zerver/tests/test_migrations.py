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


class ReactionNotificationSettingsDefault(MigrationsTestCase):
    migrate_from = "0806_stream_default_push_notifications"
    migrate_to = "0807_realmuserdefault_enable_reaction_audible_notifications_and_more"

    @override
    def setUpBeforeMigration(self, apps: StateApps) -> None:
        # The migration only adds boolean columns with a database
        # default, so there is nothing to set up here; the test verifies
        # that rows predating the migration are backfilled to the enabled
        # default.
        pass

    def test_reaction_notification_settings_default_to_true(self) -> None:
        UserProfile = self.apps.get_model("zerver", "UserProfile")
        RealmUserDefault = self.apps.get_model("zerver", "RealmUserDefault")

        self.assertGreater(UserProfile.objects.count(), 0)
        for user in UserProfile.objects.all().iterator():
            self.assertTrue(user.enable_reaction_desktop_notifications)
            self.assertTrue(user.enable_reaction_audible_notifications)

        self.assertGreater(RealmUserDefault.objects.count(), 0)
        for realm_default in RealmUserDefault.objects.all().iterator():
            self.assertTrue(realm_default.enable_reaction_desktop_notifications)
            self.assertTrue(realm_default.enable_reaction_audible_notifications)
