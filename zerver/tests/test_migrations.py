# These are tests for Zulip's database migrations.  System documented at:
#   https://zulip.readthedocs.io/en/latest/subsystems/schema-migrations.html
#
# You can also read
#   https://www.caktusgroup.com/blog/2016/02/02/writing-unit-tests-django-migrations/
# to get a tutorial on the framework that inspired this feature.
from datetime import datetime, timezone
from unittest import skip

import orjson
from django.db.migrations.state import StateApps

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


@skip("Cannot be run because there is a non-atomic migration that has been merged after it")
class ScheduledEmailData(MigrationsTestCase):
    migrate_from = "0467_rename_extradata_realmauditlog_extra_data_json"
    migrate_to = "0468_rename_followup_day_email_templates"

    @use_db_models
    def setUpBeforeMigration(self, apps: StateApps) -> None:
        iago = self.example_user("iago")
        ScheduledEmail = apps.get_model("zerver", "ScheduledEmail")
        send_date = datetime(2025, 1, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

        templates = [
            ["zerver/emails/followup_day1", "a", True, 10],
            ["zerver/emails/followup_day2", "b", False, 20],
            ["zerver/emails/onboarding_zulip_guide", "c", True, 30],
        ]

        for template in templates:
            email_fields = {
                "template_prefix": template[0],
                "string_context": template[1],
                "boolean_context": template[2],
                "integer_context": template[3],
            }

            email = ScheduledEmail.objects.create(
                type=1,
                realm=iago.realm,
                scheduled_timestamp=send_date,
                data=orjson.dumps(email_fields).decode(),
            )
            email.users.add(iago.id)

    def test_updated_email_templates(self) -> None:
        ScheduledEmail = self.apps.get_model("zerver", "ScheduledEmail")
        send_date = datetime(2025, 1, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

        old_templates = [
            "zerver/emails/followup_day1",
            "zerver/emails/followup_day2",
        ]

        current_templates = [
            "zerver/emails/account_registered",
            "zerver/emails/onboarding_zulip_guide",
            "zerver/emails/onboarding_zulip_topics",
        ]

        email_data = [
            ["zerver/emails/account_registered", "a", True, 10],
            ["zerver/emails/onboarding_zulip_topics", "b", False, 20],
            ["zerver/emails/onboarding_zulip_guide", "c", True, 30],
        ]

        scheduled_emails = ScheduledEmail.objects.all()
        self.assert_length(scheduled_emails, 3)

        checked_emails = []
        for email in scheduled_emails:
            self.assertEqual(email.type, 1)
            self.assertEqual(email.scheduled_timestamp, send_date)

            updated_data = orjson.loads(email.data)
            template_prefix = updated_data["template_prefix"]
            self.assertFalse(template_prefix in old_templates)
            for data in email_data:
                if template_prefix == data[0]:
                    self.assertEqual(updated_data["string_context"], data[1])
                    self.assertEqual(updated_data["boolean_context"], data[2])
                    self.assertEqual(updated_data["integer_context"], data[3])
                    checked_emails.append(template_prefix)

        self.assertEqual(current_templates, sorted(checked_emails))
