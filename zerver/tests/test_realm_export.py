import os
from unittest.mock import patch

import botocore.exceptions
import orjson
from django.conf import settings
from django.utils.timezone import now as timezone_now

from analytics.models import RealmCount
from zerver.lib.exceptions import JsonableError
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import (
    create_dummy_file,
    create_s3_buckets,
    stdout_suppressed,
    use_s3_backend,
)
from zerver.models import RealmAuditLog
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
        user = self.example_user('hamlet')
        self.login_user(user)
        with self.assertRaises(JsonableError):
            export_realm(self.client_post, user)

    @use_s3_backend
    def test_endpoint_s3(self) -> None:
        admin = self.example_user('iago')
        self.login_user(admin)
        bucket = create_s3_buckets(settings.S3_AVATAR_BUCKET)[0]
        tarball_path = create_dummy_file('test-export.tar.gz')

        # Test the export logic.
        with patch('zerver.lib.export.do_export_realm',
                   return_value=tarball_path) as mock_export:
            with self.settings(LOCAL_UPLOADS_DIR=None), stdout_suppressed(), \
                    self.assertLogs(level='INFO') as info_logs:
                result = self.client_post('/json/export/realm')
            self.assertTrue('INFO:root:Completed data export for zulip in ' in info_logs.output[0])
        self.assert_json_success(result)
        self.assertFalse(os.path.exists(tarball_path))
        args = mock_export.call_args_list[0][1]
        self.assertEqual(args['realm'], admin.realm)
        self.assertEqual(args['public_only'], True)
        self.assertIn('/tmp/zulip-export-', args['output_dir'])
        self.assertEqual(args['threads'], 6)

        # Get the entry and test that iago initiated it.
        audit_log_entry = RealmAuditLog.objects.filter(
            event_type=RealmAuditLog.REALM_EXPORTED).first()
        self.assertEqual(audit_log_entry.acting_user_id, admin.id)

        # Test that the file is hosted, and the contents are as expected.
        export_path = orjson.loads(audit_log_entry.extra_data)['export_path']
        assert export_path.startswith('/')
        path_id = export_path[1:]
        self.assertEqual(bucket.Object(path_id).get()['Body'].read(), b'zulip!')

        result = self.client_get('/json/export/realm')
        self.assert_json_success(result)

        # Test that the export we have is the export we created.
        export_dict = result.json()['exports']
        self.assertEqual(export_dict[0]['id'], audit_log_entry.id)
        self.assertEqual(export_dict[0]['export_url'],
                         'https://test-avatar-bucket.s3.amazonaws.com' + export_path)
        self.assertEqual(export_dict[0]['acting_user_id'], admin.id)
        self.assert_length(export_dict,
                           RealmAuditLog.objects.filter(
                               realm=admin.realm,
                               event_type=RealmAuditLog.REALM_EXPORTED).count())

        # Finally, delete the file.
        result = self.client_delete(f'/json/export/realm/{audit_log_entry.id}')
        self.assert_json_success(result)
        with self.assertRaises(botocore.exceptions.ClientError):
            bucket.Object(path_id).load()

        # Try to delete an export with a `deleted_timestamp` key.
        audit_log_entry.refresh_from_db()
        export_data = orjson.loads(audit_log_entry.extra_data)
        self.assertIn('deleted_timestamp', export_data)
        result = self.client_delete(f'/json/export/realm/{audit_log_entry.id}')
        self.assert_json_error(result, "Export already deleted")

        # Now try to delete a non-existent export.
        result = self.client_delete('/json/export/realm/0')
        self.assert_json_error(result, "Invalid data export ID")

    def test_endpoint_local_uploads(self) -> None:
        admin = self.example_user('iago')
        self.login_user(admin)
        tarball_path = create_dummy_file('test-export.tar.gz')

        # Test the export logic.
        with patch('zerver.lib.export.do_export_realm',
                   return_value=tarball_path) as mock_export:
            with stdout_suppressed(), self.assertLogs(level='INFO') as info_logs:
                result = self.client_post('/json/export/realm')
            self.assertTrue('INFO:root:Completed data export for zulip in ' in info_logs.output[0])
        self.assert_json_success(result)
        self.assertFalse(os.path.exists(tarball_path))
        args = mock_export.call_args_list[0][1]
        self.assertEqual(args['realm'], admin.realm)
        self.assertEqual(args['public_only'], True)
        self.assertIn('/tmp/zulip-export-', args['output_dir'])
        self.assertEqual(args['threads'], 6)

        # Get the entry and test that iago initiated it.
        audit_log_entry = RealmAuditLog.objects.filter(
            event_type=RealmAuditLog.REALM_EXPORTED).first()
        self.assertEqual(audit_log_entry.acting_user_id, admin.id)

        # Test that the file is hosted, and the contents are as expected.
        export_path = orjson.loads(audit_log_entry.extra_data).get('export_path')
        response = self.client_get(export_path)
        self.assertEqual(response.status_code, 200)
        self.assert_url_serves_contents_of_file(export_path, b'zulip!')

        result = self.client_get('/json/export/realm')
        self.assert_json_success(result)

        # Test that the export we have is the export we created.
        export_dict = result.json()['exports']
        self.assertEqual(export_dict[0]['id'], audit_log_entry.id)
        self.assertEqual(export_dict[0]['export_url'], admin.realm.uri + export_path)
        self.assertEqual(export_dict[0]['acting_user_id'], admin.id)
        self.assert_length(export_dict,
                           RealmAuditLog.objects.filter(
                               realm=admin.realm,
                               event_type=RealmAuditLog.REALM_EXPORTED).count())

        # Finally, delete the file.
        result = self.client_delete(f'/json/export/realm/{audit_log_entry.id}')
        self.assert_json_success(result)
        response = self.client_get(export_path)
        self.assertEqual(response.status_code, 404)

        # Try to delete an export with a `deleted_timestamp` key.
        audit_log_entry.refresh_from_db()
        export_data = orjson.loads(audit_log_entry.extra_data)
        self.assertIn('deleted_timestamp', export_data)
        result = self.client_delete(f'/json/export/realm/{audit_log_entry.id}')
        self.assert_json_error(result, "Export already deleted")

        # Now try to delete a non-existent export.
        result = self.client_delete('/json/export/realm/0')
        self.assert_json_error(result, "Invalid data export ID")

    def test_realm_export_rate_limited(self) -> None:
        admin = self.example_user('iago')
        self.login_user(admin)

        current_log = RealmAuditLog.objects.filter(
            event_type=RealmAuditLog.REALM_EXPORTED)
        self.assertEqual(len(current_log), 0)

        exports = []
        for i in range(0, 5):
            exports.append(RealmAuditLog(realm=admin.realm,
                                         event_type=RealmAuditLog.REALM_EXPORTED,
                                         event_time=timezone_now()))
        RealmAuditLog.objects.bulk_create(exports)

        result = export_realm(self.client_post, admin)
        self.assert_json_error(result, 'Exceeded rate limit.')

    def test_upload_and_message_limit(self) -> None:
        admin = self.example_user('iago')
        self.login_user(admin)
        realm_count = RealmCount.objects.create(realm_id=admin.realm.id,
                                                end_time=timezone_now(),
                                                subgroup=1,
                                                value=0,
                                                property='messages_sent:client:day')

        # Space limit is set as 10 GiB
        with patch('zerver.models.Realm.currently_used_upload_space_bytes',
                   return_value=11 * 1024 * 1024 * 1024):
            result = self.client_post('/json/export/realm')
        self.assert_json_error(
            result,
            f'Please request a manual export from {settings.ZULIP_ADMINISTRATOR}.',
        )

        # Message limit is set as 250000
        realm_count.value = 250001
        realm_count.save(update_fields=['value'])
        result = self.client_post('/json/export/realm')
        self.assert_json_error(
            result,
            f'Please request a manual export from {settings.ZULIP_ADMINISTRATOR}.',
        )
