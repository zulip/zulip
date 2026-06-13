# These are tests for Zulip's database migrations.  System documented at:
#   https://zulip.readthedocs.io/en/latest/subsystems/schema-migrations.html
#
# You can also read
#   https://www.caktusgroup.com/blog/2016/02/02/writing-unit-tests-django-migrations/
# to get a tutorial on the framework that inspired this feature.
from datetime import timedelta
from unittest.mock import patch

from django.db.migrations.state import StateApps
from django.utils.timezone import now as timezone_now
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


class BackfillRealmEmojiCreationDates(MigrationsTestCase):
    migrate_from = "0800_cleanup_case_mismatched_legacy_apns_tokens"
    migrate_to = "0801_realmemoji_date_created"

    @override
    def setUp(self) -> None:
        with patch("builtins.print") as _:
            super().setUp()

    @override
    def setUpBeforeMigration(self, apps: StateApps) -> None:
        self.apps = apps
        Realm = apps.get_model("zerver", "Realm")
        RealmEmoji = apps.get_model("zerver", "RealmEmoji")
        RealmAuditLog = apps.get_model("zerver", "RealmAuditLog")
        UserProfile = apps.get_model("zerver", "UserProfile")

        test_user = UserProfile.objects.first()

        # Set up distinct timestamps to easily assert which fallback was used
        self.realm_creation_time = timezone_now() - timedelta(days=30)
        self.oldest_log_time = self.realm_creation_time + timedelta(days=5)
        self.exact_match_log_time = self.realm_creation_time + timedelta(days=10)

        EVENT_TYPE = 226

        realms = list(Realm.objects.order_by("id")[:3])
        self.realm_with_exact_match = realms[0]
        self.realm_with_atleast_one_emoji_add_log = realms[1]
        self.realm_with_no_emoji_add_logs = realms[2]

        # Override creation dates for realms.
        self.original_realm_dates = {}
        for realm in [
            self.realm_with_exact_match,
            self.realm_with_atleast_one_emoji_add_log,
            self.realm_with_no_emoji_add_logs,
        ]:
            self.original_realm_dates[realm.id] = realm.date_created
            realm.date_created = self.realm_creation_time
            realm.save(update_fields=["date_created"])

        self.emoji_exact = RealmEmoji.objects.create(
            realm_id=self.realm_with_exact_match.id,
            file_name="exact",
            name="exact",
            author=test_user,
        )
        log1 = RealmAuditLog.objects.create(
            realm=self.realm_with_exact_match,
            event_type=EVENT_TYPE,
            event_time=self.oldest_log_time,
            extra_data={"added_emoji": {"id": 99999}},
        )
        log2 = RealmAuditLog.objects.create(
            realm=self.realm_with_exact_match,
            event_type=EVENT_TYPE,
            event_time=self.exact_match_log_time,
            extra_data={"added_emoji": {"id": self.emoji_exact.id}},
        )

        self.emoji_earliest = RealmEmoji.objects.create(
            realm_id=self.realm_with_atleast_one_emoji_add_log.id,
            file_name="earliest",
            name="earliest",
            author=test_user,
        )
        log3 = RealmAuditLog.objects.create(
            realm=self.realm_with_atleast_one_emoji_add_log,
            event_type=EVENT_TYPE,
            event_time=self.oldest_log_time,
            extra_data={"added_emoji": {"id": 88888}},
        )
        log4 = RealmAuditLog.objects.create(
            realm=self.realm_with_atleast_one_emoji_add_log,
            event_type=EVENT_TYPE,
            event_time=self.exact_match_log_time,
            extra_data={"added_emoji": {"id": 77777}},
        )

        self.emoji_fallback = RealmEmoji.objects.create(
            realm_id=self.realm_with_no_emoji_add_logs.id,
            file_name="fallback",
            name="fallback",
            author=test_user,
        )

        self.created_log_ids = [log1.id, log2.id, log3.id, log4.id]
        self.created_emoji_ids = [
            self.emoji_exact.id,
            self.emoji_earliest.id,
            self.emoji_fallback.id,
        ]

    def test_backfill_emoji_creation_dates(self) -> None:
        RealmEmoji = self.apps.get_model("zerver", "RealmEmoji")

        # Fetch the updated emojis from the database post-migration
        emoji_exact = RealmEmoji.objects.get(id=self.emoji_exact.id)
        emoji_earliest = RealmEmoji.objects.get(id=self.emoji_earliest.id)
        emoji_fallback = RealmEmoji.objects.get(id=self.emoji_fallback.id)

        # Emoji having a EMOJI_ADDED_EVENT log should use the event_date.
        self.assertEqual(emoji_exact.date_created, self.exact_match_log_time)

        # Emoji not having a corresponding EMOJI_ADDED_EVENT log should fall back to
        # using the event_date of the earliest emoji created in the realm.
        self.assertEqual(emoji_earliest.date_created, self.oldest_log_time)

        # Emoji belonging to a realm that doesn't have EMOJI_ADDED_EVENT logs
        # should fallback to using the realm creation date for the backfill.
        self.assertEqual(emoji_fallback.date_created, self.realm_creation_time)

    @override
    def tearDown(self) -> None:
        Realm = self.apps.get_model("zerver", "Realm")
        RealmEmoji = self.apps.get_model("zerver", "RealmEmoji")
        RealmAuditLog = self.apps.get_model("zerver", "RealmAuditLog")

        for realm_id, original_date in self.original_realm_dates.items():
            Realm.objects.filter(id=realm_id).update(date_created=original_date)

        RealmAuditLog.objects.filter(id__in=self.created_log_ids).delete()
        RealmEmoji.objects.filter(id__in=self.created_emoji_ids).delete()
