import os
from typing import Optional, Set
from unittest.mock import patch

import botocore.exceptions
from django.conf import settings
from django.utils.timezone import now as timezone_now

from analytics.models import RealmCount
from zerver.lib.exceptions import JsonableError
from zerver.lib.queue import queue_json_publish
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import (
    HostRequestMock,
    create_dummy_file,
    create_s3_buckets,
    stdout_suppressed,
    use_s3_backend,
)
from zerver.models import Realm, RealmAuditLog
from zerver.views.realm_export import export_realm


class RealmExportTest(ZulipTestCase):
    """
    API endpoint testing covers the full end-to-end flow
    from both the S3 and local uploads perspective.

    `test_endpoint_s3` and `test_endpoint_local_uploads` follow
    an identical pattern, which is documented in both test
    functions.
    """

    def test_export_as_not_admin(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        with self.assertRaises(JsonableError):
            export_realm(HostRequestMock(), user)

    @use_s3_backend
    def test_endpoint_s3(self) -> None:
        admin = self.example_user("iago")
        self.login_user(admin)
        bucket = create_s3_buckets(settings.S3_AVATAR_BUCKET)[0]
        tarball_path = create_dummy_file("test-export.tar.gz")

        # Test the export logic.
        with patch("zerver.lib.export.do_export_realm", return_value=tarball_path) as mock_export:
            with self.settings(LOCAL_UPLOADS_DIR=None), stdout_suppressed(), self.assertLogs(
                level="INFO"
            ) as info_logs:
                with self.captureOnCommitCallbacks(execute=True):
                    result = self.client_post("/json/export/realm")
            self.assertTrue("INFO:root:Completed data export for zulip in " in info_logs.output[0])
        self.assert_json_success(result)
        self.assertFalse(os.path.exists(tarball_path))
        args = mock_export.call_args_list[0][1]
        self.assertEqual(args["realm"], admin.realm)
        self.assertEqual(args["public_only"], True)
        self.assertTrue(os.path.basename(args["output_dir"]).startswith("zulip-export-"))
        self.assertEqual(args["threads"], 6)

        # Get the entry and test that iago initiated it.
        audit_log_entry = RealmAuditLog.objects.filter(
            event_type=RealmAuditLog.REALM_EXPORTED
        ).first()
        assert audit_log_entry is not None
        self.assertEqual(audit_log_entry.acting_user_id, admin.id)

        # Test that the file is hosted, and the contents are as expected.
        export_path = audit_log_entry.extra_data["export_path"]
        assert export_path.startswith("/")
        path_id = export_path[1:]
        self.assertEqual(bucket.Object(path_id).get()["Body"].read(), b"zulip!")

        result = self.client_get("/json/export/realm")
        response_dict = self.assert_json_success(result)

        # Test that the export we have is the export we created.
        export_dict = response_dict["exports"]
        self.assertEqual(export_dict[0]["id"], audit_log_entry.id)
        self.assertEqual(
            export_dict[0]["export_url"],
            "https://test-avatar-bucket.s3.amazonaws.com" + export_path,
        )
        self.assertEqual(export_dict[0]["acting_user_id"], admin.id)
        self.assert_length(
            export_dict,
            RealmAuditLog.objects.filter(
                realm=admin.realm, event_type=RealmAuditLog.REALM_EXPORTED
            ).count(),
        )

        # Finally, delete the file.
        result = self.client_delete(f"/json/export/realm/{audit_log_entry.id}")
        self.assert_json_success(result)
        with self.assertRaises(botocore.exceptions.ClientError):
            bucket.Object(path_id).load()

        # Try to delete an export with a `deleted_timestamp` key.
        audit_log_entry.refresh_from_db()
        export_data = audit_log_entry.extra_data
        self.assertIn("deleted_timestamp", export_data)
        result = self.client_delete(f"/json/export/realm/{audit_log_entry.id}")
        self.assert_json_error(result, "Export already deleted")

        # Now try to delete a non-existent export.
        result = self.client_delete("/json/export/realm/0")
        self.assert_json_error(result, "Invalid data export ID")

    def test_endpoint_local_uploads(self) -> None:
        admin = self.example_user("iago")
        self.login_user(admin)
        tarball_path = create_dummy_file("test-export.tar.gz")

        # Test the export logic.
        def fake_export_realm(
            realm: Realm,
            output_dir: str,
            threads: int,
            exportable_user_ids: Optional[Set[int]] = None,
            public_only: bool = False,
            consent_message_id: Optional[int] = None,
            export_as_active: Optional[bool] = None,
        ) -> str:
            self.assertEqual(realm, admin.realm)
            self.assertEqual(public_only, True)
            self.assertTrue(os.path.basename(output_dir).startswith("zulip-export-"))
            self.assertEqual(threads, 6)

            # Check that the export shows up as in progress
            result = self.client_get("/json/export/realm")
            response_dict = self.assert_json_success(result)
            export_dict = response_dict["exports"]
            self.assert_length(export_dict, 1)
            id = export_dict[0]["id"]
            self.assertEqual(export_dict[0]["pending"], True)
            self.assertIsNone(export_dict[0]["export_url"])
            self.assertIsNone(export_dict[0]["deleted_timestamp"])
            self.assertIsNone(export_dict[0]["failed_timestamp"])
            self.assertEqual(export_dict[0]["acting_user_id"], admin.id)

            # While the export is in progress, we can't delete it
            result = self.client_delete(f"/json/export/realm/{id}")
            self.assert_json_error(result, "Export still in progress")

            return tarball_path

        with patch(
            "zerver.lib.export.do_export_realm", side_effect=fake_export_realm
        ) as mock_export:
            with stdout_suppressed(), self.assertLogs(level="INFO") as info_logs:
                with self.captureOnCommitCallbacks(execute=True):
                    result = self.client_post("/json/export/realm")
            self.assertTrue("INFO:root:Completed data export for zulip in " in info_logs.output[0])
        mock_export.assert_called_once()
        data = self.assert_json_success(result)
        self.assertFalse(os.path.exists(tarball_path))

        # Get the entry and test that iago initiated it.
        audit_log_entry = RealmAuditLog.objects.filter(
            event_type=RealmAuditLog.REALM_EXPORTED
        ).first()
        assert audit_log_entry is not None
        self.assertEqual(audit_log_entry.id, data["id"])
        self.assertEqual(audit_log_entry.acting_user_id, admin.id)

        # Test that the file is hosted, and the contents are as expected.
        export_path = audit_log_entry.extra_data.get("export_path")
        response = self.client_get(export_path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.getvalue(), b"zulip!")

        result = self.client_get("/json/export/realm")
        response_dict = self.assert_json_success(result)

        # Test that the export we have is the export we created.
        export_dict = response_dict["exports"]
        self.assertEqual(export_dict[0]["id"], audit_log_entry.id)
        self.assertEqual(export_dict[0]["export_url"], admin.realm.uri + export_path)
        self.assertEqual(export_dict[0]["acting_user_id"], admin.id)
        self.assert_length(
            export_dict,
            RealmAuditLog.objects.filter(
                realm=admin.realm, event_type=RealmAuditLog.REALM_EXPORTED
            ).count(),
        )

        # Finally, delete the file.
        result = self.client_delete(f"/json/export/realm/{audit_log_entry.id}")
        self.assert_json_success(result)
        response = self.client_get(export_path)
        self.assertEqual(response.status_code, 404)

        # Try to delete an export with a `deleted_timestamp` key.
        audit_log_entry.refresh_from_db()
        export_data = audit_log_entry.extra_data
        self.assertIn("deleted_timestamp", export_data)
        result = self.client_delete(f"/json/export/realm/{audit_log_entry.id}")
        self.assert_json_error(result, "Export already deleted")

        # Now try to delete a non-existent export.
        result = self.client_delete("/json/export/realm/0")
        self.assert_json_error(result, "Invalid data export ID")

    def test_export_failure(self) -> None:
        admin = self.example_user("iago")
        self.login_user(admin)

        with patch(
            "zerver.lib.export.do_export_realm", side_effect=Exception("failure")
        ) as mock_export:
            with stdout_suppressed(), self.assertLogs(level="INFO") as info_logs:
                with self.captureOnCommitCallbacks(execute=True):
                    result = self.client_post("/json/export/realm")
        self.assertTrue(
            info_logs.output[0].startswith("ERROR:root:Data export for zulip failed after ")
        )
        mock_export.assert_called_once()
        # This is a success because the failure is swallowed in the queue worker
        data = self.assert_json_success(result)
        export_id = data["id"]

        # Check that the export shows up as failed
        result = self.client_get("/json/export/realm")
        response_dict = self.assert_json_success(result)
        export_dict = response_dict["exports"]
        self.assert_length(export_dict, 1)
        self.assertEqual(export_dict[0]["id"], export_id)
        self.assertEqual(export_dict[0]["pending"], False)
        self.assertIsNone(export_dict[0]["export_url"])
        self.assertIsNone(export_dict[0]["deleted_timestamp"])
        self.assertIsNotNone(export_dict[0]["failed_timestamp"])
        self.assertEqual(export_dict[0]["acting_user_id"], admin.id)

        # Check that we can't delete it
        result = self.client_delete(f"/json/export/realm/{export_id}")
        self.assert_json_error(result, "Export failed, nothing to delete")

        # If the queue worker sees the same export-id again, it aborts
        # instead of retrying
        with patch("zerver.lib.export.do_export_realm") as mock_export:
            with self.assertLogs(level="INFO") as info_logs:
                queue_json_publish(
                    "deferred_work",
                    {
                        "type": "realm_export",
                        "time": 42,
                        "realm_id": admin.realm.id,
                        "user_profile_id": admin.id,
                        "id": export_id,
                    },
                )
        mock_export.assert_not_called()
        self.assertEqual(
            info_logs.output,
            [
                (
                    "ERROR:zerver.worker.deferred_work:Marking export for realm zulip "
                    "as failed due to retry -- possible OOM during export?"
                )
            ],
        )

    def test_realm_export_rate_limited(self) -> None:
        admin = self.example_user("iago")
        self.login_user(admin)

        current_log = RealmAuditLog.objects.filter(event_type=RealmAuditLog.REALM_EXPORTED)
        self.assert_length(current_log, 0)

        exports = [
            RealmAuditLog(
                realm=admin.realm,
                event_type=RealmAuditLog.REALM_EXPORTED,
                event_time=timezone_now(),
            )
            for i in range(5)
        ]
        RealmAuditLog.objects.bulk_create(exports)

        with self.assertRaises(JsonableError) as error:
            export_realm(HostRequestMock(), admin)
        self.assertEqual(str(error.exception), "Exceeded rate limit.")

    def test_upload_and_message_limit(self) -> None:
        admin = self.example_user("iago")
        self.login_user(admin)
        realm_count = RealmCount.objects.create(
            realm_id=admin.realm.id,
            end_time=timezone_now(),
            value=0,
            property="messages_sent:message_type:day",
            subgroup="public_stream",
        )

        # Space limit is set as 10 GiB
        with patch(
            "zerver.models.Realm.currently_used_upload_space_bytes",
            return_value=11 * 1024 * 1024 * 1024,
        ):
            result = self.client_post("/json/export/realm")
        self.assert_json_error(
            result,
            f"Please request a manual export from {settings.ZULIP_ADMINISTRATOR}.",
        )

        # Message limit is set as 250000
        realm_count.value = 250001
        realm_count.save(update_fields=["value"])
        result = self.client_post("/json/export/realm")
        self.assert_json_error(
            result,
            f"Please request a manual export from {settings.ZULIP_ADMINISTRATOR}.",
        )
