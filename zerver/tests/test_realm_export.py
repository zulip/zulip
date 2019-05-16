from mock import patch

from django.test import override_settings
from django.utils.timezone import now as timezone_now

from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.exceptions import JsonableError
from zerver.lib.test_helpers import use_s3_backend

from zerver.models import RealmAuditLog
from zerver.views.public_export import public_only_realm_export
from zerver.worker.queue_processors import DeferredWorker

class RealmExportTest(ZulipTestCase):
    def test_export_as_not_admin(self) -> None:
        user = self.example_user('hamlet')
        self.login(user.email)
        with self.assertRaises(JsonableError):
            public_only_realm_export(self.client_post, user)

    @use_s3_backend
    def test_endpoint_s3(self) -> None:
        admin = self.example_user('iago')
        self.login(admin.email)

        with patch('zerver.views.public_export.queue_json_publish') as mock_publish:
            result = self.client_post('/json/export/realm')
        self.assert_json_success(result)
        mock_publish.assert_called_once()
        event = mock_publish.call_args_list[0][0][1]
        self.assertEqual(mock_publish.call_args_list[0][0][0], 'deferred_work')
        self.assertEqual(event['realm_id'], 1)
        self.assertEqual(event['user_profile_id'], 5)
        self.assertEqual(event['type'], 'realm_exported')
        self.assertTrue(type(event['id']), int)

        with patch('zerver.lib.export.do_export_realm',
                   side_effect=FileNotFoundError) as mock_export:
            with self.assertRaises(FileNotFoundError):
                DeferredWorker().consume(event)
            args = mock_export.call_args_list[0][1]
            self.assertEqual(args['realm'], admin.realm)
            self.assertEqual(args['public_only'], True)
            self.assertIn('/tmp/zulip-export-', args['output_dir'])
            self.assertEqual(args['threads'], 6)

    @override_settings(LOCAL_UPLOADS_DIR='/var/uploads')
    def test_endpoint_local_uploads(self) -> None:
        admin = self.example_user('iago')
        self.login(admin.email)

        with patch('zerver.views.public_export.queue_json_publish') as mock_publish:
            result = self.client_post('/json/export/realm')
        self.assert_json_success(result)
        mock_publish.assert_called_once()
        event = mock_publish.call_args_list[0][0][1]
        self.assertEqual(mock_publish.call_args_list[0][0][0], 'deferred_work')
        self.assertEqual(event['realm_id'], 1)
        self.assertEqual(event['user_profile_id'], 5)
        self.assertEqual(event['type'], 'realm_exported')
        self.assertEqual(type(event['id']), int)

        with patch('zerver.lib.export.do_export_realm',
                   side_effect=FileNotFoundError) as mock_export:
            with self.assertRaises(FileNotFoundError):
                DeferredWorker().consume(event)
            args = mock_export.call_args_list[0][1]
            self.assertEqual(args['realm'], admin.realm)
            self.assertEqual(args['public_only'], True)
            self.assertIn('/tmp/zulip-export-', args['output_dir'])
            self.assertEqual(args['threads'], 6)

    def test_realm_export_rate_limited(self) -> None:
        admin = self.example_user('iago')
        self.login(admin.email)

        current_log = RealmAuditLog.objects.filter(
            event_type=RealmAuditLog.REALM_EXPORTED)
        self.assertEqual(len(current_log), 0)

        exports = []
        for i in range(0, 5):
            exports.append(RealmAuditLog(realm=admin.realm,
                                         event_type=RealmAuditLog.REALM_EXPORTED,
                                         event_time=timezone_now()))
        RealmAuditLog.objects.bulk_create(exports)

        result = public_only_realm_export(self.client_post, admin)
        self.assert_json_error(result, 'Exceeded rate limit.')
