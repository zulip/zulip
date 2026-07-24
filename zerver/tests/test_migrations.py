# These are tests for Zulip's database migrations.  System documented at:
#   https://zulip.readthedocs.io/en/latest/subsystems/schema-migrations.html
#
# You can also read
#   https://www.caktusgroup.com/blog/2016/02/02/writing-unit-tests-django-migrations/
# to get a tutorial on the framework that inspired this feature.
from datetime import timedelta

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

ROLE_GUEST = 600
FULL_MEMBERS_GROUP_NAME = "role:fullmembers"
MEMBERS_GROUP_NAME = "role:members"


class BackfillBotFullMemberStatusFromOwner(MigrationsTestCase):
    migrate_from = "0805_fix_deleteduser_email"
    migrate_to = "0806_backfill_bot_full_member_status_from_owner"

    @override
    def setUpBeforeMigration(self, apps: StateApps) -> None:
        Realm = apps.get_model("zerver", "Realm")
        UserProfile = apps.get_model("zerver", "UserProfile")
        NamedUserGroup = apps.get_model("zerver", "NamedUserGroup")
        UserGroupMembership = apps.get_model("zerver", "UserGroupMembership")

        realm = Realm.objects.get(string_id="zulip")
        realm.waiting_period_threshold = 10
        realm.save(update_fields=["waiting_period_threshold"])

        full_members_group = NamedUserGroup.objects.get(
            name=FULL_MEMBERS_GROUP_NAME, realm_id=realm.id, is_system_group=True
        )
        members_group = NamedUserGroup.objects.get(
            name=MEMBERS_GROUP_NAME, realm_id=realm.id, is_system_group=True
        )

        # Stale full member: a member-role bot left in FULL_MEMBERS under the
        # old rule, but whose owner is a guest -- must be removed.
        guest = UserProfile.objects.get(delivery_email="polonius@zulip.com", realm_id=realm.id)
        self.assertEqual(guest.role, ROLE_GUEST)
        self.guest_owned_bot = UserProfile.objects.get(
            delivery_email="default-bot@zulip.com", realm_id=realm.id
        )
        self.guest_owned_bot.bot_owner_id = guest.id
        self.guest_owned_bot.save(update_fields=["bot_owner"])
        UserGroupMembership.objects.get_or_create(
            user_profile_id=self.guest_owned_bot.id, user_group=full_members_group
        )

        # Missing full member: a member-role bot whose owner is a member past
        # the waiting period, but which was never added to FULL_MEMBERS -- must
        # be added.
        member_owner = UserProfile.objects.get(delivery_email="hamlet@zulip.com", realm_id=realm.id)
        member_owner.date_joined = timezone_now() - timedelta(days=30)
        member_owner.save(update_fields=["date_joined"])
        self.member_owned_bot = UserProfile.objects.get(
            delivery_email="webhook-bot@zulip.com", realm_id=realm.id
        )
        self.member_owned_bot.bot_owner_id = member_owner.id
        self.member_owned_bot.save(update_fields=["bot_owner"])
        UserGroupMembership.objects.get_or_create(
            user_profile_id=self.member_owned_bot.id, user_group=members_group
        )
        UserGroupMembership.objects.filter(
            user_profile_id=self.member_owned_bot.id, user_group=full_members_group
        ).delete()

    @override
    def tearDown(self) -> None:
        # A data migration necessarily changes the set of rows in the database
        # (adding/removing FULL_MEMBERS memberships and audit logs), which
        # ZulipTransactionTestCase.tearDown would flag as an unexpected side
        # effect. Deleted rows cannot be restored to their original primary
        # keys, so skip that check; the migration-test database is rebuilt for
        # each run, so the reconciled rows do not leak across runs.
        pass

    def test_bot_full_member_status_reconciled_with_owner(self) -> None:
        NamedUserGroup = self.apps.get_model("zerver", "NamedUserGroup")
        UserGroupMembership = self.apps.get_model("zerver", "UserGroupMembership")
        RealmAuditLog = self.apps.get_model("zerver", "RealmAuditLog")

        full_members_group = NamedUserGroup.objects.get(
            name=FULL_MEMBERS_GROUP_NAME, realm__string_id="zulip", is_system_group=True
        )

        def in_full_members(bot_id: int) -> bool:
            return UserGroupMembership.objects.filter(
                user_profile_id=bot_id, user_group=full_members_group
            ).exists()

        self.assertFalse(in_full_members(self.guest_owned_bot.id))
        self.assertTrue(in_full_members(self.member_owned_bot.id))

        # Each membership change leaves a backfilled audit-log entry.
        self.assertTrue(
            RealmAuditLog.objects.filter(
                modified_user_id=self.guest_owned_bot.id,
                modified_user_group=full_members_group,
                event_type=704,
                backfilled=True,
            ).exists()
        )
        self.assertTrue(
            RealmAuditLog.objects.filter(
                modified_user_id=self.member_owned_bot.id,
                modified_user_group=full_members_group,
                event_type=703,
                backfilled=True,
            ).exists()
        )
