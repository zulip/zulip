# These are tests for Zulip's database migrations.  System documented at:
#   https://zulip.readthedocs.io/en/latest/subsystems/schema-migrations.html
#
# You can also read
#   https://www.caktusgroup.com/blog/2016/02/02/writing-unit-tests-django-migrations/
# to get a tutorial on the framework that inspired this feature.

from typing import List

import orjson
from django.db.migrations.state import StateApps
from django.utils.timezone import now as timezone_now

from zerver.lib.test_classes import MigrationsTestCase
from zerver.lib.test_helpers import use_db_models

USER_GROUP_CREATED = 701
USER_GROUP_DIRECT_USER_MEMBERSHIP_ADDED = 703
USER_GROUP_DIRECT_SUBGROUP_MEMBERSHIP_ADDED = 705
USER_GROUP_DIRECT_SUPERGROUP_MEMBERSHIP_ADDED = 707

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


class UserGroupRealmAuditLogs(MigrationsTestCase):
    migrate_from = "0478_usergroup_deactivated"
    migrate_to = "0479_backfill_usergroup_realmauditlogs"

    @use_db_models
    def setUpBeforeMigration(self, apps: StateApps) -> None:
        UserGroup = apps.get_model("zerver", "UserGroup")
        RealmAuditLog = apps.get_model("zerver", "RealmAuditLog")

        iago = self.example_user("iago")
        hamlet = self.example_user("hamlet")

        can_mention_group = UserGroup.objects.get(
            name="role:everyone", realm=iago.realm, is_system_group=True
        )
        group1 = UserGroup.objects.create(
            name="test_group1", realm=iago.realm, can_mention_group=can_mention_group
        )
        group1.direct_members.set([hamlet, iago])
        group2 = UserGroup.objects.create(
            name="test_group2", realm=iago.realm, can_mention_group=can_mention_group
        )
        group2.direct_members.set([hamlet])
        group3 = UserGroup.objects.create(
            name="test_group3", realm=iago.realm, can_mention_group=can_mention_group
        )
        group3.direct_subgroups.set([group1, group2])

        now = timezone_now()
        group4 = UserGroup.objects.create(
            name="test_group4", realm=iago.realm, can_mention_group=can_mention_group
        )
        group4.direct_members.set([hamlet, iago])
        group4.direct_subgroups.set([group1, group2, group3])
        # Generate audit log entries for group4 with USER_GROUP_CREATED event type.
        # and only one user for the USER_GROUP_MEMBERSHIP_ADDED event and two
        # user group for the USER_GROUP_SUBGROUP_MEMBERSHIP_ADDED event to check if
        # the backfilling migration skips backfilling existing audit log entries.
        RealmAuditLog.objects.create(
            realm=iago.realm,
            modified_user_group=group4,
            event_type=USER_GROUP_CREATED,
            event_time=now,
        )
        RealmAuditLog.objects.create(
            realm=iago.realm,
            modified_user=hamlet,
            modified_user_group=group4,
            event_type=USER_GROUP_DIRECT_USER_MEMBERSHIP_ADDED,
            event_time=now,
        )
        # It is impossible to have USER_GROUP_DIRECT_SUBGROUP_MEMBERSHIP_ADDED populated
        # without the corresponding USER_GROUP_DIRECT_SUPERGROUP_MEMBERSHIP_ADDED audit log
        RealmAuditLog.objects.bulk_create(
            [
                RealmAuditLog(
                    realm=iago.realm,
                    modified_user_group=group4,
                    event_type=USER_GROUP_DIRECT_SUBGROUP_MEMBERSHIP_ADDED,
                    event_time=now,
                    extra_data=orjson.dumps({"subgroup_ids": [group1.id]}).decode(),
                ),
                RealmAuditLog(
                    realm=iago.realm,
                    modified_user_group=group1,
                    event_type=USER_GROUP_DIRECT_SUPERGROUP_MEMBERSHIP_ADDED,
                    event_time=now,
                    extra_data=orjson.dumps({"supergroup_ids": [group4.id]}).decode(),
                ),
                RealmAuditLog(
                    realm=iago.realm,
                    modified_user_group=group4,
                    event_type=USER_GROUP_DIRECT_SUBGROUP_MEMBERSHIP_ADDED,
                    event_time=now,
                    extra_data=orjson.dumps({"subgroup_ids": [group3.id]}).decode(),
                ),
                RealmAuditLog(
                    realm=iago.realm,
                    modified_user_group=group3,
                    event_type=USER_GROUP_DIRECT_SUPERGROUP_MEMBERSHIP_ADDED,
                    event_time=now,
                    extra_data=orjson.dumps({"supergroup_ids": [group4.id]}).decode(),
                ),
            ]
        )

        self.group_ids = [group1.id, group2.id, group3.id, group4.id]

    def test_backfilled_auditlogs(self) -> None:
        RealmAuditLog = self.apps.get_model("zerver", "RealmAuditLog")
        iago = self.example_user("iago")
        hamlet = self.example_user("hamlet")

        # No non-backfilled entries are expected other than the 6 we populated
        # manually during setup.
        self.assert_length(
            RealmAuditLog.objects.filter(
                backfilled=False, modified_user_group_id__in=self.group_ids
            ),
            6,
        )

        expected_creation_event_counts = [1, 1, 1, 0]
        # Type annotation needed to get a narrower type than List[List[object]]
        expected_user_ids: List[List[int]] = [[hamlet.id, iago.id], [hamlet.id], [], [iago.id]]
        expected_subgroup_ids = [[], [], self.group_ids[:2], self.group_ids[:3]]
        expected_supergroup_ids = [self.group_ids[2:], self.group_ids[2:], [self.group_ids[3]], []]

        for idx, group_id in enumerate(self.group_ids):
            self.assert_length(
                RealmAuditLog.objects.filter(
                    backfilled=True,
                    realm_id=iago.realm.id,
                    modified_user_group_id=group_id,
                    event_type=USER_GROUP_CREATED,
                ),
                expected_creation_event_counts[idx],
            )

            user_ids = RealmAuditLog.objects.filter(
                backfilled=True,
                realm_id=iago.realm.id,
                modified_user_group_id=group_id,
                event_type=USER_GROUP_DIRECT_USER_MEMBERSHIP_ADDED,
            ).values_list("modified_user_id", flat=True)
            supergroup_extra_data_entries = RealmAuditLog.objects.filter(
                backfilled=True,
                realm_id=iago.realm.id,
                modified_user_group_id=group_id,
                event_type=USER_GROUP_DIRECT_SUBGROUP_MEMBERSHIP_ADDED,
            ).values_list("extra_data", flat=True)
            subgroup_extra_data_entries = RealmAuditLog.objects.filter(
                backfilled=True,
                realm_id=iago.realm.id,
                modified_user_group_id=group_id,
                event_type=USER_GROUP_DIRECT_SUPERGROUP_MEMBERSHIP_ADDED,
            ).values_list("extra_data", flat=True)

            self.assertListEqual(list(user_ids), expected_user_ids[idx])
            self.assertListEqual(
                [
                    orjson.loads(extra_data)["subgroup_ids"]
                    for extra_data in supergroup_extra_data_entries
                ],
                expected_subgroup_ids[idx],
            )
            self.assertListEqual(
                [
                    orjson.loads(extra_data)["supergroup_ids"]
                    for extra_data in subgroup_extra_data_entries
                ],
                expected_supergroup_ids[idx],
            )
