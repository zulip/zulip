from mock import patch

from django.utils.timezone import now as timezone_now
from django.conf import settings

from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.exceptions import JsonableError
from zerver.lib.test_helpers import use_s3_backend, create_s3_buckets

from zerver.models import RealmAuditLog
from zerver.views.public_export import public_only_realm_export
import zerver.lib.upload

import os

def create_tarball_path() -> str:
    tarball_path = os.path.join(settings.TEST_WORKER_DIR, 'test-export.tar.gz')
    with open(tarball_path, 'w') as f:
        f.write('zulip!')
    return tarball_path

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
        bucket = create_s3_buckets(settings.S3_AVATAR_BUCKET)[0]
        tarball_path = create_tarball_path()

        with patch('zerver.lib.export.do_export_realm',
                   return_value=tarball_path) as mock_export:
            with self.settings(LOCAL_UPLOADS_DIR=None):
                result = self.client_post('/json/export/realm')
            self.assert_json_success(result)
            self.assertFalse(os.path.exists(tarball_path))

        args = mock_export.call_args_list[0][1]
        self.assertEqual(args['realm'], admin.realm)
        self.assertEqual(args['public_only'], True)
        self.assertIn('/tmp/zulip-export-', args['output_dir'])
        self.assertEqual(args['threads'], 6)

        export_object = RealmAuditLog.objects.filter(
            event_type='realm_exported').first()
        path_id = getattr(export_object, 'extra_data')
        self.assertIsNotNone(path_id)

        self.assertEqual(bucket.get_key(path_id).get_contents_as_string(),
                         b'zulip!')

        result = self.client_get('/json/export/realm')
        self.assert_json_success(result)

        export_dict = result.json()['public_exports']
        self.assertEqual(export_dict[0]['path'], path_id)
        self.assertEqual(export_dict[0]['acting_user_id'], admin.id)
        self.assert_length(export_dict,
                           RealmAuditLog.objects.filter(
                               realm=admin.realm,
                               event_type=RealmAuditLog.REALM_EXPORTED).count())

        result = zerver.lib.upload.upload_backend.delete_export_tarball(path_id)
        self.assertEqual(result, path_id)
        self.assertIsNone(bucket.get_key(path_id))

    def test_endpoint_local_uploads(self) -> None:
        admin = self.example_user('iago')
        self.login(admin.email)
        tarball_path = create_tarball_path()

        with patch('zerver.lib.export.do_export_realm',
                   return_value=tarball_path) as mock_export:
            result = self.client_post('/json/export/realm')
        self.assert_json_success(result)
        self.assertFalse(os.path.exists(tarball_path))

        args = mock_export.call_args_list[0][1]
        self.assertEqual(args['realm'], admin.realm)
        self.assertEqual(args['public_only'], True)
        self.assertIn('/tmp/zulip-export-', args['output_dir'])
        self.assertEqual(args['threads'], 6)

        export_object = RealmAuditLog.objects.filter(
            event_type='realm_exported').first()
        self.assertEqual(export_object.acting_user_id, admin.id)

        path_id = getattr(export_object, 'extra_data')
        response = self.client_get(path_id)
        self.assertEqual(response.status_code, 200)
        self.assert_url_serves_contents_of_file(path_id, b'zulip!')

        result = self.client_get('/json/export/realm')
        self.assert_json_success(result)

        export_dict = result.json()['public_exports']
        self.assertEqual(export_dict[0]['path'], path_id)
        self.assertEqual(export_dict[0]['acting_user_id'], admin.id)
        self.assert_length(export_dict,
                           RealmAuditLog.objects.filter(
                               realm=admin.realm,
                               event_type=RealmAuditLog.REALM_EXPORTED).count())

        result = zerver.lib.upload.upload_backend.delete_export_tarball(path_id)
        self.assertEqual(result, path_id)
        response = self.client_get(path_id)
        self.assertEqual(response.status_code, 404)

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
