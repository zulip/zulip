from mock import patch

from django.test import override_settings
from django.conf import settings
from django.utils.timezone import now as timezone_now

from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.exceptions import JsonableError
from zerver.lib.test_helpers import use_s3_backend, create_s3_buckets
from zerver.views.public_export import public_only_realm_export
from zerver.models import RealmAuditLog

# TODO: Mock export_realm_wrapper to test for s3 or local
class RealmExportTest(ZulipTestCase):
    def setUp(self) -> None:
        # TODO: Just inline this 2 lines of basic code in the
        # individual test functions, since that's our standard style
        # in Zulip's unit tests
        self.admin = self.example_user('iago')
        self.login(self.admin.email)

    def test_export_as_not_admin(self) -> None:
        user = self.example_user('hamlet')
        self.login(user.email)
        with self.assertRaises(JsonableError):
            public_only_realm_export(self.client_post, user)

    @use_s3_backend
    def test_endpoint_s3(self) -> None:
        create_s3_buckets(
            settings.S3_AUTH_UPLOADS_BUCKET,
            settings.S3_AVATAR_BUCKET)

        with patch('zerver.views.public_export.queue_json_publish') as mock_publish:
            result = self.client_post('/json/export/realm')
            queue_data = mock_publish.call_args_list[0][0]
            worker = mock_publish.call_args_list[0][0][0]
        self.assert_json_success(result)

        mock_publish.assert_called_once()
        event = queue_data[1]
        self.assertEqual(worker, 'deferred_work')
        self.assertEqual(event['realm_id'], 1)
        self.assertEqual(event['user_profile_id'], 5)
        self.assertEqual(event['type'], 'realm_exported')

        with patch('zerver.lib.export.do_export_realm') as mock_export:
            result = self.client_post('/json/export/realm')
            args = mock_export.call_args_list[0][1]
            # TODO: Clean up the way we do the mocking here; we will
            # want to mock do_export_realm in a way that captures its
            # arguments but doesn't lead to (silent) error spam from
            # do_write_stats_file_for_realm_export.
            #
            # Probably setting a `side_effect` makes sense?
        self.assert_json_success(result)
        self.assertEqual(args['realm'], self.admin.realm)
        self.assertEqual(args['public_only'], True)
        self.assertEqual(args['output_dir'].startswith('/tmp/zulip-export-'), True)
        self.assertEqual(args['threads'], 6)

    @override_settings(LOCAL_UPLOADS_DIR='/var/uploads')
    def test_endpoint_local_uploads(self) -> None:
        with patch('zerver.lib.export.do_export_realm'):
            with patch('zerver.views.public_export.queue_json_publish') as mock_publish:
                result = self.client_post('/json/export/realm')
                queue_data = mock_publish.call_args_list[0][0]
                worker = mock_publish.call_args_list[0][0][0]
        self.assert_json_success(result)

        mock_publish.assert_called_once()
        event = queue_data[1]
        self.assertEqual(worker, 'deferred_work')
        self.assertEqual(event['realm_id'], 1)
        self.assertEqual(event['user_profile_id'], 5)
        self.assertEqual(event['type'], 'realm_exported')

        # Rest of test should match the previous test, but we're
        # blocked on support for public export in LOCAL_UPLOADS_DIR
        # backend.

    def test_realm_export_rate_limited(self) -> None:
        current_log = RealmAuditLog.objects.filter(
            event_type=RealmAuditLog.REALM_EXPORTED)
        self.assertEqual(len(current_log), 0)

        exports = []
        for i in range(0, 5):
            exports.append(RealmAuditLog(realm=self.admin.realm,
                                         event_type=RealmAuditLog.REALM_EXPORTED,
                                         event_time=timezone_now()))
        RealmAuditLog.objects.bulk_create(exports)

        result = public_only_realm_export(self.client_post, self.admin)
        self.assert_json_error(result, 'Exceeded rate limit.')
