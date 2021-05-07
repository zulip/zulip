# These are tests for Zulip's database migrations.  System documented at:
#   https://zulip.readthedocs.io/en/latest/subsystems/schema-migrations.html
#
# You can also read
#   https://www.caktusgroup.com/blog/2016/02/02/writing-unit-tests-django-migrations/
# to get a tutorial on the framework that inspired this feature.
from typing import Optional

import orjson
from django.db.migrations.state import StateApps
from django.utils.timezone import now as timezone_now

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

USER_ACTIVATED = 102
USER_FULL_NAME_CHANGED = 124
OLD_VALUE = "1"
NEW_VALUE = "2"


class RealmAuditLogExtraData(MigrationsTestCase):
    migrate_from = "0452_realmauditlog_extra_data_json"
    migrate_to = "0453_backfill_remote_realmauditlog_extradata_to_json_field"

    full_name_change_log_id: Optional[int] = None
    valid_json_log_id: Optional[int] = None
    str_json_log_id: Optional[int] = None
    # The BATCH_SIZE is defined as 5000 in 0424_backfill_remote_realmauditlog_extradata_to_json_field,
    # this later is used to test if batching works properly
    DATA_SIZE = 10005

    @use_db_models
    def setUpBeforeMigration(self, apps: StateApps) -> None:
        Realm = apps.get_model("zerver", "Realm")
        RealmAuditLog = apps.get_model("zerver", "RealmAuditLog")
        event_time = timezone_now()
        realm = Realm.objects.get(string_id="zulip")

        full_name_change_log = RealmAuditLog(
            realm=realm,
            event_type=USER_FULL_NAME_CHANGED,
            event_time=event_time,
            extra_data="foo",
        )

        new_full_name_change_log = RealmAuditLog(
            realm=realm,
            event_type=USER_FULL_NAME_CHANGED,
            event_time=event_time,
            extra_data="foo",
            extra_data_json={OLD_VALUE: "foo", NEW_VALUE: "bar"},
        )

        valid_json_log = RealmAuditLog(
            realm=realm,
            event_type=USER_ACTIVATED,
            event_time=event_time,
            extra_data=orjson.dumps({"key": "value"}).decode(),
        )

        str_json_log = RealmAuditLog(
            realm=realm,
            event_type=USER_ACTIVATED,
            event_time=event_time,
            extra_data=str({"key": "value"}),
        )

        RealmAuditLog.objects.bulk_create(
            [full_name_change_log, new_full_name_change_log, valid_json_log, str_json_log]
        )
        self.full_name_change_log_id = full_name_change_log.id
        self.new_full_name_change_log_id = new_full_name_change_log.id
        self.valid_json_log_id = valid_json_log.id
        self.str_json_log_id = str_json_log.id

        other_logs = []
        for i in range(self.DATA_SIZE):
            other_logs.append(
                RealmAuditLog(
                    realm=realm,
                    event_type=USER_ACTIVATED,
                    event_time=event_time,
                    extra_data=orjson.dumps({"data": i}).decode(),
                )
            )
        self.other_logs_id = [
            audit_log.id for audit_log in RealmAuditLog.objects.bulk_create(other_logs)
        ]

        # No new audit log entry should have extra_data_json populated as of now
        self.assert_length(
            RealmAuditLog.objects.filter(
                event_time__gte=event_time,
            )
            .exclude(
                extra_data_json={},
            )
            .exclude(id=self.new_full_name_change_log_id),
            0,
        )

    def test_realmaudit_log_extra_data_to_json(self) -> None:
        RealmAuditLog = self.apps.get_model("zerver", "RealmAuditLog")

        self.assertIsNotNone(self.full_name_change_log_id)
        self.assertIsNotNone(self.valid_json_log_id)
        self.assertIsNotNone(self.str_json_log_id)

        full_name_change_log = RealmAuditLog.objects.filter(id=self.full_name_change_log_id).first()
        new_full_name_change_log = RealmAuditLog.objects.filter(
            id=self.new_full_name_change_log_id
        ).first()
        valid_json_log = RealmAuditLog.objects.filter(id=self.valid_json_log_id).first()
        str_json_log = RealmAuditLog.objects.filter(id=self.str_json_log_id).first()

        self.assertIsNotNone(full_name_change_log)
        self.assertEqual(full_name_change_log.extra_data_json, {"1": "foo", "2": None})

        self.assertIsNotNone(new_full_name_change_log)
        self.assertEqual(new_full_name_change_log.extra_data_json, {"1": "foo", "2": "bar"})

        self.assertIsNotNone(valid_json_log)
        self.assertEqual(valid_json_log.extra_data_json, {"key": "value"})

        self.assertIsNotNone(str_json_log)
        self.assertEqual(str_json_log.extra_data_json, {"key": "value"})

        other_logs = RealmAuditLog.objects.filter(id__in=self.other_logs_id).order_by("id")
        self.assertIsNotNone(other_logs)
        self.assert_length(other_logs, self.DATA_SIZE)
        for index, audit_log in enumerate(other_logs):
            self.assertEqual(audit_log.extra_data_json, {"data": index})
