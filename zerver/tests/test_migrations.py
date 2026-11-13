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


class SetDefaultValueForCanChangeNameGroup(MigrationsTestCase):
    migrate_from = "0819_realm_can_change_name_group"
    migrate_to = "0820_set_default_value_for_can_change_name_group"

    @override
    def setUpBeforeMigration(self, apps: StateApps) -> None:
        Realm = apps.get_model("zerver", "Realm")
        NamedUserGroup = apps.get_model("zerver", "NamedUserGroup")

        # Reversing to 0819 leaves the backfilled values in place, so
        # clear them to simulate a server upgrading from before 0819.
        Realm.objects.update(can_change_name_group=None)

        Realm.objects.filter(string_id="zulip").update(name_changes_disabled=True)
        Realm.objects.filter(string_id="lear").update(name_changes_disabled=False)

        # A realm whose setting was already backfilled should be left
        # alone if the migration is re-run.
        zephyr = Realm.objects.get(string_id="zephyr")
        self.zephyr_moderators_group_id = NamedUserGroup.objects.get(
            name="role:moderators", realm_for_sharding=zephyr, is_system_group=True
        ).id
        Realm.objects.filter(id=zephyr.id).update(
            name_changes_disabled=False,
            can_change_name_group_id=self.zephyr_moderators_group_id,
        )

    def test_can_change_name_group_backfilled(self) -> None:
        Realm = self.apps.get_model("zerver", "Realm")
        NamedUserGroup = self.apps.get_model("zerver", "NamedUserGroup")

        def group_name(string_id: str) -> str:
            realm = Realm.objects.get(string_id=string_id)
            return NamedUserGroup.objects.get(id=realm.can_change_name_group_id).name

        self.assertEqual(group_name("zulip"), "role:administrators")
        self.assertEqual(group_name("lear"), "role:everyone")

        zephyr = Realm.objects.get(string_id="zephyr")
        self.assertEqual(zephyr.can_change_name_group_id, self.zephyr_moderators_group_id)
