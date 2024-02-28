# These are tests for Zulip's database migrations.  System documented at:
#   https://zulip.readthedocs.io/en/latest/subsystems/schema-migrations.html
#
# You can also read
#   https://www.caktusgroup.com/blog/2016/02/02/writing-unit-tests-django-migrations/
# to get a tutorial on the framework that inspired this feature.
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
