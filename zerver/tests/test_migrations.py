# These are tests for Zulip's database migrations.  System documented at:
#   https://zulip.readthedocs.io/en/latest/subsystems/schema-migrations.html
#
# You can also read
#   https://www.caktusgroup.com/blog/2016/02/02/writing-unit-tests-django-migrations/
# to get a tutorial on the framework that inspired this feature.
from datetime import datetime, timezone
from unittest import skip
from unittest.mock import patch

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


@skip("Fails because newer migrations have since been merged.")  # nocoverage
class RenameUserHotspot(MigrationsTestCase):
    migrate_from = "0492_realm_push_notifications_enabled_and_more"
    migrate_to = "0493_rename_userhotspot_to_onboardingstep"

    @override
    def setUp(self) -> None:
        with patch("builtins.print") as _:
            super().setUp()

    @override
    def setUpBeforeMigration(self, apps: StateApps) -> None:
        self.assertRaises(LookupError, lambda: apps.get_model("zerver", "onboardingstep"))

        UserHotspot = apps.get_model("zerver", "userhotspot")

        expected_field_names = {"id", "hotspot", "timestamp", "user"}
        fields_name = {field.name for field in UserHotspot._meta.get_fields()}

        self.assertEqual(fields_name, expected_field_names)

    def test_renamed_model_and_field(self) -> None:
        self.assertRaises(LookupError, lambda: self.apps.get_model("zerver", "userhotspot"))

        OnboardingStep = self.apps.get_model("zerver", "onboardingstep")

        expected_field_names = {"id", "onboarding_step", "timestamp", "user"}
        fields_name = {field.name for field in OnboardingStep._meta.get_fields()}

        self.assertEqual(fields_name, expected_field_names)


class RealmEmojiCreatedAtMigration(MigrationsTestCase):  # nocoverage
    """Tests for migration 0769_realmemoji_created_at.

    Verifies that the field is absent before the migration, present after,
    defaults to the epoch sentinel (not timezone_now), and that the migration
    contains both AddField and RunPython (the RealmAuditLog backfill).
    """

    migrate_from = "0768_realmauditlog_scrubbed"
    migrate_to = "0769_realmemoji_created_at"

    @override
    def setUpBeforeMigration(self, apps: StateApps) -> None:
        RealmEmoji = apps.get_model("zerver", "RealmEmoji")
        field_names = {field.name for field in RealmEmoji._meta.get_fields()}
        self.assertNotIn("created_at", field_names)

    def test_created_at_field_added_with_epoch_default(self) -> None:
        from django.db.migrations.loader import MigrationLoader

        RealmEmoji = self.apps.get_model("zerver", "RealmEmoji")

        field_names = {field.name for field in RealmEmoji._meta.get_fields()}
        self.assertIn("created_at", field_names)

        # Default must be the epoch sentinel, not a callable like timezone_now.
        created_at_field = RealmEmoji._meta.get_field("created_at")
        epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
        self.assertEqual(created_at_field.default, epoch)
        self.assertFalse(callable(created_at_field.default))

        # Both AddField and RunPython must be present — the backfill is mandatory.
        loader = MigrationLoader(None, ignore_no_migrations=True)
        migration = loader.get_migration("zerver", "0769_realmemoji_created_at")
        from django.db.migrations.operations.special import RunPython
        from django.db.migrations.operations.fields import AddField

        self.assertEqual(len(migration.operations), 2)
        self.assertIsInstance(migration.operations[0], AddField)
        self.assertIsInstance(migration.operations[1], RunPython)
