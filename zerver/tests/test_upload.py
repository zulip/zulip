# -*- coding: utf-8 -*-
from django.conf import settings
from django.test import TestCase
from unittest.mock import patch

from zerver.lib.avatar import (
    avatar_url,
    get_avatar_field,
)
from zerver.lib.avatar_hash import user_avatar_path
from zerver.lib.bugdown import url_filename
from zerver.lib.realm_icon import realm_icon_url
from zerver.lib.realm_logo import realm_logo_url
from zerver.lib.test_classes import ZulipTestCase, UploadSerializeMixin
from zerver.lib.test_helpers import (
    avatar_disk_path,
    get_test_image_file,
    use_s3_backend,
    create_s3_buckets,
    queries_captured,
)
from zerver.lib.upload import sanitize_name, S3UploadBackend, \
    upload_message_file, upload_emoji_image, delete_message_image, LocalUploadBackend, \
    ZulipUploadBackend, MEDIUM_AVATAR_SIZE, resize_avatar, \
    resize_emoji, BadImageError, get_realm_for_filename, \
    DEFAULT_AVATAR_SIZE, DEFAULT_EMOJI_SIZE, exif_rotate
import zerver.lib.upload
from zerver.models import Attachment, get_user, \
    Message, UserProfile, Realm, \
    RealmDomain, RealmEmoji, get_realm, get_system_bot, \
    validate_attachment_request
from zerver.lib.actions import (
    do_change_plan_type,
    do_delete_old_unclaimed_attachments,
    internal_send_private_message,
)
from zerver.lib.cache import get_realm_used_upload_space_cache_key, cache_get
from zerver.lib.create_user import copy_user_settings
from zerver.lib.users import get_api_key
from zerver.views.upload import upload_file_backend

import urllib
import ujson
from PIL import Image

from io import StringIO
import mock
import os
import io
import shutil
import re
import datetime
from django.utils.timezone import now as timezone_now
from sendfile import _get_sendfile

def destroy_uploads() -> None:
    if os.path.exists(settings.LOCAL_UPLOADS_DIR):
        shutil.rmtree(settings.LOCAL_UPLOADS_DIR)

class FileUploadTest(UploadSerializeMixin, ZulipTestCase):

    def test_rest_endpoint(self) -> None:
        """
        Tests the /api/v1/user_uploads api endpoint. Here a single file is uploaded
        and downloaded using a username and api_key
        """
        fp = StringIO("zulip!")
        fp.name = "zulip.txt"

        # Upload file via API
        result = self.api_post(self.example_email("hamlet"), '/api/v1/user_uploads', {'file': fp})
        self.assertIn("uri", result.json())
        uri = result.json()['uri']
        base = '/user_uploads/'
        self.assertEqual(base, uri[:len(base)])

        # Download file via API
        self.logout()
        response = self.api_get(self.example_email("hamlet"), uri)
        self.assertEqual(response.status_code, 200)
        data = b"".join(response.streaming_content)
        self.assertEqual(b"zulip!", data)

        # Files uploaded through the API should be accesible via the web client
        self.login(self.example_email("hamlet"))
        self.assert_url_serves_contents_of_file(uri, b"zulip!")

    def test_mobile_api_endpoint(self) -> None:
        """
        Tests the /api/v1/user_uploads api endpoint with ?api_key
        auth. Here a single file is uploaded and downloaded using a
        username and api_key
        """
        fp = StringIO("zulip!")
        fp.name = "zulip.txt"

        # Upload file via API
        result = self.api_post(self.example_email("hamlet"), '/api/v1/user_uploads', {'file': fp})
        self.assertIn("uri", result.json())
        uri = result.json()['uri']
        base = '/user_uploads/'
        self.assertEqual(base, uri[:len(base)])

        self.logout()

        # Try to download file via API, passing URL and invalid API key
        user_profile = self.example_user("hamlet")

        response = self.client_get(uri + "?api_key=" + "invalid")
        self.assertEqual(response.status_code, 401)

        response = self.client_get(uri + "?api_key=" + get_api_key(user_profile))
        self.assertEqual(response.status_code, 200)
        data = b"".join(response.streaming_content)
        self.assertEqual(b"zulip!", data)

    def test_upload_file_with_supplied_mimetype(self) -> None:
        """
        When files are copied into the system clipboard and pasted for upload
        the filename may not be supplied so the extension is determined from a
        query string parameter.
        """
        fp = StringIO("zulip!")
        fp.name = "pasted_file"
        result = self.api_post(self.example_email("hamlet"),
                               "/api/v1/user_uploads?mimetype=image/png",
                               {"file": fp})
        self.assertEqual(result.status_code, 200)
        uri = result.json()["uri"]
        self.assertTrue(uri.endswith("pasted_file.png"))

    def test_filename_encoding(self) -> None:
        """
        In Python 2, we need to encode unicode filenames (which converts them to
        str) before they can be rendered correctly.  However, in Python 3, the
        separate unicode type does not exist, and we don't need to perform this
        encoding.  This test ensures that we handle filename encodings properly,
        and does so in a way that preserves 100% test coverage for Python 3.
        """

        user_profile = self.example_user('hamlet')

        mock_file = mock.Mock()
        mock_file._get_size = mock.Mock(return_value=1024)

        mock_files = mock.Mock()
        mock_files.__len__ = mock.Mock(return_value=1)
        mock_files.values = mock.Mock(return_value=[mock_file])

        mock_request = mock.Mock()
        mock_request.FILES = mock_files

        # str filenames should not be encoded.
        mock_filename = mock.Mock(spec=str)
        mock_file.name = mock_filename
        with mock.patch('zerver.views.upload.upload_message_image_from_request'):
            result = upload_file_backend(mock_request, user_profile)
        self.assert_json_success(result)
        mock_filename.encode.assert_not_called()

        # Non-str filenames should be encoded.
        mock_filename = mock.Mock(spec=None)  # None is not str
        mock_file.name = mock_filename
        with mock.patch('zerver.views.upload.upload_message_image_from_request'):
            result = upload_file_backend(mock_request, user_profile)
        self.assert_json_success(result)
        mock_filename.encode.assert_called_once_with('ascii')

    def test_file_too_big_failure(self) -> None:
        """
        Attempting to upload big files should fail.
        """
        self.login(self.example_email("hamlet"))
        fp = StringIO("bah!")
        fp.name = "a.txt"

        # Use MAX_FILE_UPLOAD_SIZE of 0, because the next increment
        # would be 1MB.
        with self.settings(MAX_FILE_UPLOAD_SIZE=0):
            result = self.client_post("/json/user_uploads", {'f1': fp})
        self.assert_json_error(result, 'Uploaded file is larger than the allowed limit of 0 MB')

    def test_multiple_upload_failure(self) -> None:
        """
        Attempting to upload two files should fail.
        """
        self.login(self.example_email("hamlet"))
        fp = StringIO("bah!")
        fp.name = "a.txt"
        fp2 = StringIO("pshaw!")
        fp2.name = "b.txt"

        result = self.client_post("/json/user_uploads", {'f1': fp, 'f2': fp2})
        self.assert_json_error(result, "You may only upload one file at a time")

    def test_no_file_upload_failure(self) -> None:
        """
        Calling this endpoint with no files should fail.
        """
        self.login(self.example_email("hamlet"))

        result = self.client_post("/json/user_uploads")
        self.assert_json_error(result, "You must specify a file to upload")

    # This test will go through the code path for uploading files onto LOCAL storage
    # when zulip is in DEVELOPMENT mode.
    def test_file_upload_authed(self) -> None:
        """
        A call to /json/user_uploads should return a uri and actually create an
        entry in the database. This entry will be marked unclaimed till a message
        refers it.
        """
        self.login(self.example_email("hamlet"))
        fp = StringIO("zulip!")
        fp.name = "zulip.txt"

        result = self.client_post("/json/user_uploads", {'file': fp})
        self.assert_json_success(result)
        self.assertIn("uri", result.json())
        uri = result.json()["uri"]
        base = '/user_uploads/'
        self.assertEqual(base, uri[:len(base)])

        # In the future, local file requests will follow the same style as S3
        # requests; they will be first authenthicated and redirected
        self.assert_url_serves_contents_of_file(uri, b"zulip!")

        # check if DB has attachment marked as unclaimed
        entry = Attachment.objects.get(file_name='zulip.txt')
        self.assertEqual(entry.is_claimed(), False)

        self.subscribe(self.example_user("hamlet"), "Denmark")
        body = "First message ...[zulip.txt](http://localhost:9991" + uri + ")"
        self.send_stream_message(self.example_email("hamlet"), "Denmark", body, "test")
        self.assertIn('title="zulip.txt"', self.get_last_message().rendered_content)

    def test_file_download_unauthed(self) -> None:
        self.login(self.example_email("hamlet"))
        fp = StringIO("zulip!")
        fp.name = "zulip.txt"
        result = self.client_post("/json/user_uploads", {'file': fp})
        uri = result.json()["uri"]

        self.logout()
        response = self.client_get(uri)
        self.assert_json_error(response, "Not logged in: API authentication or user session required",
                               status_code=401)

    def test_removed_file_download(self) -> None:
        '''
        Trying to download deleted files should return 404 error
        '''
        self.login(self.example_email("hamlet"))
        fp = StringIO("zulip!")
        fp.name = "zulip.txt"
        result = self.client_post("/json/user_uploads", {'file': fp})

        destroy_uploads()

        response = self.client_get(result.json()["uri"])
        self.assertEqual(response.status_code, 404)

    def test_non_existing_file_download(self) -> None:
        '''
        Trying to download a file that was never uploaded will return a json_error
        '''
        self.login(self.example_email("hamlet"))
        response = self.client_get("http://localhost:9991/user_uploads/1/ff/gg/abc.py")
        self.assertEqual(response.status_code, 404)
        self.assert_in_response('File not found.', response)

    def test_delete_old_unclaimed_attachments(self) -> None:
        # Upload some files and make them older than a weeek
        self.login(self.example_email("hamlet"))
        d1 = StringIO("zulip!")
        d1.name = "dummy_1.txt"
        result = self.client_post("/json/user_uploads", {'file': d1})
        d1_path_id = re.sub('/user_uploads/', '', result.json()['uri'])

        d2 = StringIO("zulip!")
        d2.name = "dummy_2.txt"
        result = self.client_post("/json/user_uploads", {'file': d2})
        d2_path_id = re.sub('/user_uploads/', '', result.json()['uri'])

        two_week_ago = timezone_now() - datetime.timedelta(weeks=2)
        d1_attachment = Attachment.objects.get(path_id = d1_path_id)
        d1_attachment.create_time = two_week_ago
        d1_attachment.save()
        self.assertEqual(str(d1_attachment), u'<Attachment: dummy_1.txt>')
        d2_attachment = Attachment.objects.get(path_id = d2_path_id)
        d2_attachment.create_time = two_week_ago
        d2_attachment.save()

        # Send message referring only dummy_1
        self.subscribe(self.example_user("hamlet"), "Denmark")
        body = "Some files here ...[zulip.txt](http://localhost:9991/user_uploads/" + d1_path_id + ")"
        self.send_stream_message(self.example_email("hamlet"), "Denmark", body, "test")

        # dummy_2 should not exist in database or the uploads folder
        do_delete_old_unclaimed_attachments(2)
        self.assertTrue(not Attachment.objects.filter(path_id = d2_path_id).exists())
        self.assertTrue(not delete_message_image(d2_path_id))

    def test_attachment_url_without_upload(self) -> None:
        self.login(self.example_email("hamlet"))
        body = "Test message ...[zulip.txt](http://localhost:9991/user_uploads/1/64/fake_path_id.txt)"
        self.send_stream_message(self.example_email("hamlet"), "Denmark", body, "test")
        self.assertFalse(Attachment.objects.filter(path_id = "1/64/fake_path_id.txt").exists())

    def test_multiple_claim_attachments(self) -> None:
        """
        This test tries to claim the same attachment twice. The messages field in
        the Attachment model should have both the messages in its entry.
        """
        self.login(self.example_email("hamlet"))
        d1 = StringIO("zulip!")
        d1.name = "dummy_1.txt"
        result = self.client_post("/json/user_uploads", {'file': d1})
        d1_path_id = re.sub('/user_uploads/', '', result.json()['uri'])

        self.subscribe(self.example_user("hamlet"), "Denmark")
        body = "First message ...[zulip.txt](http://localhost:9991/user_uploads/" + d1_path_id + ")"
        self.send_stream_message(self.example_email("hamlet"), "Denmark", body, "test")
        body = "Second message ...[zulip.txt](http://localhost:9991/user_uploads/" + d1_path_id + ")"
        self.send_stream_message(self.example_email("hamlet"), "Denmark", body, "test")

        self.assertEqual(Attachment.objects.get(path_id=d1_path_id).messages.count(), 2)

    def test_multiple_claim_attachments_different_owners(self) -> None:
        """This test tries to claim the same attachment more than once, first
        with a private stream and then with different recipients."""
        self.login(self.example_email("hamlet"))
        d1 = StringIO("zulip!")
        d1.name = "dummy_1.txt"
        result = self.client_post("/json/user_uploads", {'file': d1})
        d1_path_id = re.sub('/user_uploads/', '', result.json()['uri'])

        self.make_stream("private_stream", invite_only=True)
        self.subscribe(self.example_user("hamlet"), "private_stream")

        # First, send the mesasge to the new private stream.
        body = "First message ...[zulip.txt](http://localhost:9991/user_uploads/" + d1_path_id + ")"
        self.send_stream_message(self.example_email("hamlet"), "private_stream", body, "test")
        self.assertFalse(Attachment.objects.get(path_id=d1_path_id).is_realm_public)
        self.assertEqual(Attachment.objects.get(path_id=d1_path_id).messages.count(), 1)

        # Then, try having a user who didn't receive the message try to publish it, and fail
        body = "Illegal message ...[zulip.txt](http://localhost:9991/user_uploads/" + d1_path_id + ")"
        self.send_stream_message(self.example_email("cordelia"), "Denmark", body, "test")
        self.assertEqual(Attachment.objects.get(path_id=d1_path_id).messages.count(), 1)
        self.assertFalse(Attachment.objects.get(path_id=d1_path_id).is_realm_public)

        # Then, have the owner PM it to another user, giving that other user access.
        body = "Second message ...[zulip.txt](http://localhost:9991/user_uploads/" + d1_path_id + ")"
        self.send_personal_message(self.example_email("hamlet"), self.example_email("othello"), body)
        self.assertEqual(Attachment.objects.get(path_id=d1_path_id).messages.count(), 2)
        self.assertFalse(Attachment.objects.get(path_id=d1_path_id).is_realm_public)

        # Then, have that new recipient user publish it.
        body = "Third message ...[zulip.txt](http://localhost:9991/user_uploads/" + d1_path_id + ")"
        self.send_stream_message(self.example_email("othello"), "Denmark", body, "test")
        self.assertEqual(Attachment.objects.get(path_id=d1_path_id).messages.count(), 3)
        self.assertTrue(Attachment.objects.get(path_id=d1_path_id).is_realm_public)

    def test_check_attachment_reference_update(self) -> None:
        f1 = StringIO("file1")
        f1.name = "file1.txt"
        f2 = StringIO("file2")
        f2.name = "file2.txt"
        f3 = StringIO("file3")
        f3.name = "file3.txt"

        self.login(self.example_email("hamlet"))
        result = self.client_post("/json/user_uploads", {'file': f1})
        f1_path_id = re.sub('/user_uploads/', '', result.json()['uri'])

        result = self.client_post("/json/user_uploads", {'file': f2})
        f2_path_id = re.sub('/user_uploads/', '', result.json()['uri'])

        self.subscribe(self.example_user("hamlet"), "test")
        body = ("[f1.txt](http://localhost:9991/user_uploads/" + f1_path_id + ")"
                "[f2.txt](http://localhost:9991/user_uploads/" + f2_path_id + ")")
        msg_id = self.send_stream_message(self.example_email("hamlet"), "test", body, "test")

        result = self.client_post("/json/user_uploads", {'file': f3})
        f3_path_id = re.sub('/user_uploads/', '', result.json()['uri'])

        new_body = ("[f3.txt](http://localhost:9991/user_uploads/" + f3_path_id + ")"
                    "[f2.txt](http://localhost:9991/user_uploads/" + f2_path_id + ")")
        result = self.client_patch("/json/messages/" + str(msg_id), {
            'message_id': msg_id,
            'content': new_body
        })
        self.assert_json_success(result)

        message = Message.objects.get(id=msg_id)
        f1_attachment = Attachment.objects.get(path_id=f1_path_id)
        f2_attachment = Attachment.objects.get(path_id=f2_path_id)
        f3_attachment = Attachment.objects.get(path_id=f3_path_id)

        self.assertTrue(message not in f1_attachment.messages.all())
        self.assertTrue(message in f2_attachment.messages.all())
        self.assertTrue(message in f3_attachment.messages.all())

        # Delete all the attachments from the message
        new_body = "(deleted)"
        result = self.client_patch("/json/messages/" + str(msg_id), {
            'message_id': msg_id,
            'content': new_body
        })
        self.assert_json_success(result)

        message = Message.objects.get(id=msg_id)
        f1_attachment = Attachment.objects.get(path_id=f1_path_id)
        f2_attachment = Attachment.objects.get(path_id=f2_path_id)
        f3_attachment = Attachment.objects.get(path_id=f3_path_id)
        self.assertTrue(message not in f1_attachment.messages.all())
        self.assertTrue(message not in f2_attachment.messages.all())
        self.assertTrue(message not in f3_attachment.messages.all())

    def test_file_name(self) -> None:
        """
        Unicode filenames should be processed correctly.
        """
        self.login(self.example_email("hamlet"))
        for expected in ["Здравейте.txt", "test"]:
            fp = StringIO("bah!")
            fp.name = urllib.parse.quote(expected)

            result = self.client_post("/json/user_uploads", {'f1': fp})
            assert sanitize_name(expected) in result.json()['uri']

    def test_realm_quota(self) -> None:
        """
        Realm quota for uploading should not be exceeded.
        """
        self.login(self.example_email("hamlet"))

        d1 = StringIO("zulip!")
        d1.name = "dummy_1.txt"
        result = self.client_post("/json/user_uploads", {'file': d1})
        d1_path_id = re.sub('/user_uploads/', '', result.json()['uri'])
        d1_attachment = Attachment.objects.get(path_id = d1_path_id)
        self.assert_json_success(result)

        realm = get_realm("zulip")
        realm.upload_quota_gb = 1
        realm.save(update_fields=['upload_quota_gb'])

        # The size of StringIO("zulip!") is 6 bytes. Setting the size of
        # d1_attachment to realm.upload_quota_bytes() - 11 should allow
        # us to upload only one more attachment.
        quota = realm.upload_quota_bytes()
        assert(quota is not None)
        d1_attachment.size = quota - 11
        d1_attachment.save(update_fields=['size'])

        d2 = StringIO("zulip!")
        d2.name = "dummy_2.txt"
        result = self.client_post("/json/user_uploads", {'file': d2})
        self.assert_json_success(result)

        d3 = StringIO("zulip!")
        d3.name = "dummy_3.txt"
        result = self.client_post("/json/user_uploads", {'file': d3})
        self.assert_json_error(result, "Upload would exceed your organization's upload quota.")

        realm.upload_quota_gb = None
        realm.save(update_fields=['upload_quota_gb'])
        result = self.client_post("/json/user_uploads", {'file': d3})
        self.assert_json_success(result)

    def test_cross_realm_file_access(self) -> None:

        def create_user(email: str, realm_id: str) -> UserProfile:
            self.register(email, 'test', subdomain=realm_id)
            return get_user(email, get_realm(realm_id))

        test_subdomain = "uploadtest.example.com"
        user1_email = 'user1@uploadtest.example.com'
        user2_email = 'test-og-bot@zulip.com'
        user3_email = 'other-user@uploadtest.example.com'

        r1 = Realm.objects.create(string_id=test_subdomain, invite_required=False)
        RealmDomain.objects.create(realm=r1, domain=test_subdomain)

        create_user(user1_email, test_subdomain)
        create_user(user2_email, 'zulip')
        create_user(user3_email, test_subdomain)

        # Send a message from @zulip.com -> @uploadtest.example.com
        self.login(user2_email, 'test')
        fp = StringIO("zulip!")
        fp.name = "zulip.txt"
        result = self.client_post("/json/user_uploads", {'file': fp})
        uri = result.json()['uri']
        fp_path_id = re.sub('/user_uploads/', '', uri)
        body = "First message ...[zulip.txt](http://localhost:9991/user_uploads/" + fp_path_id + ")"
        with self.settings(CROSS_REALM_BOT_EMAILS = set((user2_email, user3_email))):
            internal_send_private_message(
                realm=r1,
                sender=get_system_bot(user2_email),
                recipient_user=get_user(user1_email, r1),
                content=body,
            )

        self.login(user1_email, 'test', realm=r1)
        response = self.client_get(uri, subdomain=test_subdomain)
        self.assertEqual(response.status_code, 200)
        data = b"".join(response.streaming_content)
        self.assertEqual(b"zulip!", data)
        self.logout()

        # Confirm other cross-realm users can't read it.
        self.login(user3_email, 'test', realm=r1)
        response = self.client_get(uri, subdomain=test_subdomain)
        self.assertEqual(response.status_code, 403)
        self.assert_in_response("You are not authorized to view this file.", response)

    def test_file_download_authorization_invite_only(self) -> None:
        user = self.example_user("hamlet")
        subscribed_emails = [user.email, self.example_email("cordelia")]
        unsubscribed_emails = [self.example_email("othello"), self.example_email("prospero")]
        stream_name = "test-subscribe"
        self.make_stream(stream_name, realm=user.realm, invite_only=True, history_public_to_subscribers=False)

        for email in subscribed_emails:
            self.subscribe(get_user(email, user.realm), stream_name)

        self.login(user.email)
        fp = StringIO("zulip!")
        fp.name = "zulip.txt"
        result = self.client_post("/json/user_uploads", {'file': fp})
        uri = result.json()['uri']
        fp_path_id = re.sub('/user_uploads/', '', uri)
        body = "First message ...[zulip.txt](http://localhost:9991/user_uploads/" + fp_path_id + ")"
        self.send_stream_message(user.email, stream_name, body, "test")
        self.logout()

        # Owner user should be able to view file
        self.login(user.email)
        with queries_captured() as queries:
            response = self.client_get(uri)
            self.assertEqual(response.status_code, 200)
            data = b"".join(response.streaming_content)
            self.assertEqual(b"zulip!", data)
        self.logout()
        self.assertEqual(len(queries), 5)

        # Subscribed user who recieved the message should be able to view file
        self.login(subscribed_emails[1])
        with queries_captured() as queries:
            response = self.client_get(uri)
            self.assertEqual(response.status_code, 200)
            data = b"".join(response.streaming_content)
            self.assertEqual(b"zulip!", data)
        self.logout()
        self.assertEqual(len(queries), 6)

        def assert_cannot_access_file(user_email: str) -> None:
            response = self.api_get(user_email, uri)
            self.assertEqual(response.status_code, 403)
            self.assert_in_response("You are not authorized to view this file.", response)

        late_subscribed_user = self.example_user("aaron")
        self.subscribe(late_subscribed_user, stream_name)
        assert_cannot_access_file(late_subscribed_user.email)

        # Unsubscribed user should not be able to view file
        for unsubscribed_user in unsubscribed_emails:
            assert_cannot_access_file(unsubscribed_user)

    def test_file_download_authorization_invite_only_with_shared_history(self) -> None:
        user = self.example_user("hamlet")
        subscribed_emails = [user.email, self.example_email("polonius")]
        unsubscribed_emails = [self.example_email("othello"), self.example_email("prospero")]
        stream_name = "test-subscribe"
        self.make_stream(stream_name, realm=user.realm, invite_only=True, history_public_to_subscribers=True)

        for email in subscribed_emails:
            self.subscribe(get_user(email, user.realm), stream_name)

        self.login(user.email)
        fp = StringIO("zulip!")
        fp.name = "zulip.txt"
        result = self.client_post("/json/user_uploads", {'file': fp})
        uri = result.json()['uri']
        fp_path_id = re.sub('/user_uploads/', '', uri)
        body = "First message ...[zulip.txt](http://localhost:9991/user_uploads/" + fp_path_id + ")"
        self.send_stream_message(user.email, stream_name, body, "test")
        self.logout()

        # Add aaron as a subscribed after the message was sent
        late_subscribed_user = self.example_user("aaron")
        self.subscribe(late_subscribed_user, stream_name)
        subscribed_emails.append(late_subscribed_user.email)

        # Owner user should be able to view file
        self.login(user.email)
        with queries_captured() as queries:
            response = self.client_get(uri)
            self.assertEqual(response.status_code, 200)
            data = b"".join(response.streaming_content)
            self.assertEqual(b"zulip!", data)
        self.logout()
        self.assertEqual(len(queries), 5)

        # Originally subscribed user should be able to view file
        self.login(subscribed_emails[1])
        with queries_captured() as queries:
            response = self.client_get(uri)
            self.assertEqual(response.status_code, 200)
            data = b"".join(response.streaming_content)
            self.assertEqual(b"zulip!", data)
        self.logout()
        self.assertEqual(len(queries), 6)

        # Subscribed user who did not receive the message should also be able to view file
        self.login(late_subscribed_user.email)
        with queries_captured() as queries:
            response = self.client_get(uri)
            self.assertEqual(response.status_code, 200)
            data = b"".join(response.streaming_content)
            self.assertEqual(b"zulip!", data)
        self.logout()
        # It takes a few extra queries to verify access because of shared history.
        self.assertEqual(len(queries), 9)

        def assert_cannot_access_file(user_email: str) -> None:
            self.login(user_email)
            with queries_captured() as queries:
                response = self.client_get(uri)
            self.assertEqual(response.status_code, 403)
            # It takes a few extra queries to verify lack of access with shared history.
            self.assertEqual(len(queries), 8)
            self.assert_in_response("You are not authorized to view this file.", response)
            self.logout()

        # Unsubscribed user should not be able to view file
        for unsubscribed_user in unsubscribed_emails:
            assert_cannot_access_file(unsubscribed_user)

    def test_multiple_message_attachment_file_download(self) -> None:
        hamlet = self.example_user("hamlet")
        for i in range(0, 5):
            stream_name = "test-subscribe %s" % (i,)
            self.make_stream(stream_name, realm=hamlet.realm, invite_only=True, history_public_to_subscribers=True)
            self.subscribe(hamlet, stream_name)

        self.login(hamlet.email)
        fp = StringIO("zulip!")
        fp.name = "zulip.txt"
        result = self.client_post("/json/user_uploads", {'file': fp})
        uri = result.json()['uri']
        fp_path_id = re.sub('/user_uploads/', '', uri)
        for i in range(20):
            body = "First message ...[zulip.txt](http://localhost:9991/user_uploads/" + fp_path_id + ")"
            self.send_stream_message(self.example_email("hamlet"), "test-subscribe %s" % (i % 5,), body, "test")
        self.logout()

        user = self.example_user("aaron")
        self.login(user.email)
        with queries_captured() as queries:
            response = self.client_get(uri)
            self.assertEqual(response.status_code, 403)
            self.assert_in_response("You are not authorized to view this file.", response)
        self.assertEqual(len(queries), 8)

        self.subscribe(user, "test-subscribe 1")
        self.subscribe(user, "test-subscribe 2")

        with queries_captured() as queries:
            response = self.client_get(uri)
            self.assertEqual(response.status_code, 200)
            data = b"".join(response.streaming_content)
            self.assertEqual(b"zulip!", data)
        # If we were accidentally one query per message, this would be 20+
        self.assertEqual(len(queries), 9)

        with queries_captured() as queries:
            self.assertTrue(validate_attachment_request(user, fp_path_id))
        self.assertEqual(len(queries), 6)

        self.logout()

    def test_file_download_authorization_public(self) -> None:
        subscribed_users = [self.example_email("hamlet"), self.example_email("iago")]
        unsubscribed_users = [self.example_email("othello"), self.example_email("prospero")]
        realm = get_realm("zulip")
        for email in subscribed_users:
            self.subscribe(get_user(email, realm), "test-subscribe")

        self.login(self.example_email("hamlet"))
        fp = StringIO("zulip!")
        fp.name = "zulip.txt"
        result = self.client_post("/json/user_uploads", {'file': fp})
        uri = result.json()['uri']
        fp_path_id = re.sub('/user_uploads/', '', uri)
        body = "First message ...[zulip.txt](http://localhost:9991/user_uploads/" + fp_path_id + ")"
        self.send_stream_message(self.example_email("hamlet"), "test-subscribe", body, "test")
        self.logout()

        # Now all users should be able to access the files
        for user in subscribed_users + unsubscribed_users:
            self.login(user)
            response = self.client_get(uri)
            data = b"".join(response.streaming_content)
            self.assertEqual(b"zulip!", data)
            self.logout()

    def test_serve_local(self) -> None:
        def check_xsend_links(name: str, name_str_for_test: str,
                              content_disposition: str='') -> None:
            with self.settings(SENDFILE_BACKEND='sendfile.backends.nginx'):
                _get_sendfile.clear()  # To clearout cached version of backend from djangosendfile
                self.login(self.example_email("hamlet"))
                fp = StringIO("zulip!")
                fp.name = name
                result = self.client_post("/json/user_uploads", {'file': fp})
                uri = result.json()['uri']
                fp_path_id = re.sub('/user_uploads/', '', uri)
                fp_path = os.path.split(fp_path_id)[0]
                response = self.client_get(uri)
                _get_sendfile.clear()
                test_upload_dir = os.path.split(settings.LOCAL_UPLOADS_DIR)[1]
                self.assertEqual(response['X-Accel-Redirect'],
                                 '/serve_uploads/../../'  + test_upload_dir +
                                 '/files/' + fp_path + '/' + name_str_for_test)
                if content_disposition != '':
                    self.assertIn('attachment;', response['Content-disposition'])
                    self.assertIn(content_disposition, response['Content-disposition'])
                else:
                    self.assertEqual(response.get('Content-disposition'), None)

        check_xsend_links('zulip.txt', 'zulip.txt', "filename*=UTF-8''zulip.txt")
        check_xsend_links('áéБД.txt', '%C3%A1%C3%A9%D0%91%D0%94.txt',
                          "filename*=UTF-8''%C3%A1%C3%A9%D0%91%D0%94.txt")
        check_xsend_links('zulip.html', 'zulip.html', "filename*=UTF-8''zulip.html")
        check_xsend_links('zulip.sh', 'zulip.sh', "filename*=UTF-8''zulip.sh")
        check_xsend_links('zulip.jpeg', 'zulip.jpeg')
        check_xsend_links('áéБД.pdf', '%C3%A1%C3%A9%D0%91%D0%94.pdf')
        check_xsend_links('zulip', 'zulip', "filename*=UTF-8''zulip")

    def tearDown(self) -> None:
        destroy_uploads()


class AvatarTest(UploadSerializeMixin, ZulipTestCase):

    def test_get_avatar_field(self) -> None:
        with self.settings(AVATAR_SALT="salt"):
            url = get_avatar_field(
                user_id=17,
                realm_id=5,
                email='foo@example.com',
                avatar_source=UserProfile.AVATAR_FROM_USER,
                avatar_version=2,
                medium=True,
                client_gravatar=False,
            )

        self.assertEqual(
            url,
            '/user_avatars/5/fc2b9f1a81f4508a4df2d95451a2a77e0524ca0e-medium.png?x=x&version=2'
        )

        url = get_avatar_field(
            user_id=9999,
            realm_id=9999,
            email='foo@example.com',
            avatar_source=UserProfile.AVATAR_FROM_GRAVATAR,
            avatar_version=2,
            medium=True,
            client_gravatar=False,
        )

        self.assertEqual(
            url,
            'https://secure.gravatar.com/avatar/b48def645758b95537d4424c84d1a9ff?d=identicon&s=500&version=2'
        )

        url = get_avatar_field(
            user_id=9999,
            realm_id=9999,
            email='foo@example.com',
            avatar_source=UserProfile.AVATAR_FROM_GRAVATAR,
            avatar_version=2,
            medium=True,
            client_gravatar=True,
        )

        self.assertEqual(url, None)

    def test_avatar_url(self) -> None:
        """Verifies URL schemes for avatars and realm icons."""
        backend = LocalUploadBackend()  # type: ZulipUploadBackend
        self.assertEqual(backend.get_avatar_url("hash", False),
                         "/user_avatars/hash.png?x=x")
        self.assertEqual(backend.get_avatar_url("hash", True),
                         "/user_avatars/hash-medium.png?x=x")
        self.assertEqual(backend.get_realm_icon_url(15, 1),
                         "/user_avatars/15/realm/icon.png?version=1")
        self.assertEqual(backend.get_realm_logo_url(15, 1, False),
                         "/user_avatars/15/realm/logo.png?version=1")
        self.assertEqual(backend.get_realm_logo_url(15, 1, True),
                         "/user_avatars/15/realm/night_logo.png?version=1")

        with self.settings(S3_AVATAR_BUCKET="bucket"):
            backend = S3UploadBackend()
            self.assertEqual(backend.get_avatar_url("hash", False),
                             "https://bucket.s3.amazonaws.com/hash?x=x")
            self.assertEqual(backend.get_avatar_url("hash", True),
                             "https://bucket.s3.amazonaws.com/hash-medium.png?x=x")
            self.assertEqual(backend.get_realm_icon_url(15, 1),
                             "https://bucket.s3.amazonaws.com/15/realm/icon.png?version=1")
            self.assertEqual(backend.get_realm_logo_url(15, 1, False),
                             "https://bucket.s3.amazonaws.com/15/realm/logo.png?version=1")
            self.assertEqual(backend.get_realm_logo_url(15, 1, True),
                             "https://bucket.s3.amazonaws.com/15/realm/night_logo.png?version=1")

    def test_multiple_upload_failure(self) -> None:
        """
        Attempting to upload two files should fail.
        """
        self.login(self.example_email("hamlet"))
        with get_test_image_file('img.png') as fp1, \
                get_test_image_file('img.png') as fp2:
            result = self.client_post("/json/users/me/avatar", {'f1': fp1, 'f2': fp2})
        self.assert_json_error(result, "You must upload exactly one avatar.")

    def test_no_file_upload_failure(self) -> None:
        """
        Calling this endpoint with no files should fail.
        """
        self.login(self.example_email("hamlet"))

        result = self.client_post("/json/users/me/avatar")
        self.assert_json_error(result, "You must upload exactly one avatar.")

    correct_files = [
        ('img.png', 'png_resized.png'),
        ('img.jpg', None),  # jpeg resizing is platform-dependent
        ('img.gif', 'gif_resized.png'),
        ('img.tif', 'tif_resized.png'),
        ('cmyk.jpg', None)
    ]
    corrupt_files = ['text.txt', 'corrupt.png', 'corrupt.gif']

    def test_get_gravatar_avatar(self) -> None:
        self.login(self.example_email("hamlet"))
        cordelia = self.example_user('cordelia')

        cordelia.avatar_source = UserProfile.AVATAR_FROM_GRAVATAR
        cordelia.save()
        with self.settings(ENABLE_GRAVATAR=True):
            response = self.client_get("/avatar/cordelia@zulip.com?foo=bar")
            redirect_url = response['Location']
            self.assertEqual(redirect_url, str(avatar_url(cordelia)) + '&foo=bar')

        with self.settings(ENABLE_GRAVATAR=False):
            response = self.client_get("/avatar/cordelia@zulip.com?foo=bar")
            redirect_url = response['Location']
            self.assertTrue(redirect_url.endswith(str(avatar_url(cordelia)) + '&foo=bar'))

    def test_get_user_avatar(self) -> None:
        hamlet = self.example_email("hamlet")
        self.login(hamlet)
        cordelia = self.example_user('cordelia')
        cross_realm_bot = self.example_user('welcome_bot')

        cordelia.avatar_source = UserProfile.AVATAR_FROM_USER
        cordelia.save()
        response = self.client_get("/avatar/cordelia@zulip.com?foo=bar")
        redirect_url = response['Location']
        self.assertTrue(redirect_url.endswith(str(avatar_url(cordelia)) + '&foo=bar'))

        response = self.client_get("/avatar/%s?foo=bar" % (cordelia.id))
        redirect_url = response['Location']
        self.assertTrue(redirect_url.endswith(str(avatar_url(cordelia)) + '&foo=bar'))

        response = self.client_get("/avatar/")
        self.assertEqual(response.status_code, 404)

        self.logout()

        # Test /avatar/<email_or_id> endpoint with HTTP basic auth.
        response = self.api_get(hamlet, "/avatar/cordelia@zulip.com?foo=bar")
        redirect_url = response['Location']
        self.assertTrue(redirect_url.endswith(str(avatar_url(cordelia)) + '&foo=bar'))

        response = self.api_get(hamlet, "/avatar/%s?foo=bar" % (cordelia.id))
        redirect_url = response['Location']
        self.assertTrue(redirect_url.endswith(str(avatar_url(cordelia)) + '&foo=bar'))

        # Test cross_realm_bot avatar access using email.
        response = self.api_get(hamlet, "/avatar/welcome-bot@zulip.com?foo=bar")
        redirect_url = response['Location']
        self.assertTrue(redirect_url.endswith(str(avatar_url(cross_realm_bot)) + '&foo=bar'))

        # Test cross_realm_bot avatar access using id.
        response = self.api_get(hamlet, "/avatar/%s?foo=bar" % (cross_realm_bot.id))
        redirect_url = response['Location']
        self.assertTrue(redirect_url.endswith(str(avatar_url(cross_realm_bot)) + '&foo=bar'))

        response = self.client_get("/avatar/cordelia@zulip.com?foo=bar")
        self.assert_json_error(response, "Not logged in: API authentication or user session required",
                               status_code=401)

    def test_get_user_avatar_medium(self) -> None:
        hamlet = self.example_email("hamlet")
        self.login(hamlet)
        cordelia = self.example_user('cordelia')

        cordelia.avatar_source = UserProfile.AVATAR_FROM_USER
        cordelia.save()
        response = self.client_get("/avatar/cordelia@zulip.com/medium?foo=bar")
        redirect_url = response['Location']
        self.assertTrue(redirect_url.endswith(str(avatar_url(cordelia, True)) + '&foo=bar'))

        response = self.client_get("/avatar/%s/medium?foo=bar" % (cordelia.id,))
        redirect_url = response['Location']
        self.assertTrue(redirect_url.endswith(str(avatar_url(cordelia, True)) + '&foo=bar'))

        self.logout()

        # Test /avatar/<email_or_id>/medium endpoint with HTTP basic auth.
        response = self.api_get(hamlet, "/avatar/cordelia@zulip.com/medium?foo=bar")
        redirect_url = response['Location']
        self.assertTrue(redirect_url.endswith(str(avatar_url(cordelia, True)) + '&foo=bar'))

        response = self.api_get(hamlet, "/avatar/%s/medium?foo=bar" % (cordelia.id,))
        redirect_url = response['Location']
        self.assertTrue(redirect_url.endswith(str(avatar_url(cordelia, True)) + '&foo=bar'))

        response = self.client_get("/avatar/cordelia@zulip.com/medium?foo=bar")
        self.assert_json_error(response, "Not logged in: API authentication or user session required",
                               status_code=401)

    def test_non_valid_user_avatar(self) -> None:

        # It's debatable whether we should generate avatars for non-users,
        # but this test just validates the current code's behavior.
        self.login(self.example_email("hamlet"))

        response = self.client_get("/avatar/nonexistent_user@zulip.com?foo=bar")
        redirect_url = response['Location']
        actual_url = 'https://secure.gravatar.com/avatar/444258b521f152129eb0c162996e572d?d=identicon&version=1&foo=bar'
        self.assertEqual(redirect_url, actual_url)

    def test_valid_avatars(self) -> None:
        """
        A PUT request to /json/users/me/avatar with a valid file should return a url and actually create an avatar.
        """
        version = 2
        for fname, rfname in self.correct_files:
            # TODO: use self.subTest once we're exclusively on python 3 by uncommenting the line below.
            # with self.subTest(fname=fname):
            self.login(self.example_email("hamlet"))
            with get_test_image_file(fname) as fp:
                result = self.client_post("/json/users/me/avatar", {'file': fp})

            self.assert_json_success(result)
            self.assertIn("avatar_url", result.json())
            base = '/user_avatars/'
            url = result.json()['avatar_url']
            self.assertEqual(base, url[:len(base)])

            if rfname is not None:
                response = self.client_get(url)
                data = b"".join(response.streaming_content)
                self.assertEqual(Image.open(io.BytesIO(data)).size, (100, 100))

            # Verify that the medium-size avatar was created
            user_profile = self.example_user('hamlet')
            medium_avatar_disk_path = avatar_disk_path(user_profile, medium=True)
            self.assertTrue(os.path.exists(medium_avatar_disk_path))

            # Verify that ensure_medium_avatar_url does not overwrite this file if it exists
            with mock.patch('zerver.lib.upload.write_local_file') as mock_write_local_file:
                zerver.lib.upload.upload_backend.ensure_medium_avatar_image(user_profile)
                self.assertFalse(mock_write_local_file.called)

            # Confirm that ensure_medium_avatar_url works to recreate
            # medium size avatars from the original if needed
            os.remove(medium_avatar_disk_path)
            self.assertFalse(os.path.exists(medium_avatar_disk_path))
            zerver.lib.upload.upload_backend.ensure_medium_avatar_image(user_profile)
            self.assertTrue(os.path.exists(medium_avatar_disk_path))

            # Verify whether the avatar_version gets incremented with every new upload
            self.assertEqual(user_profile.avatar_version, version)
            version += 1

    def test_copy_avatar_image(self) -> None:
        self.login(self.example_email("hamlet"))
        with get_test_image_file('img.png') as image_file:
            self.client_post("/json/users/me/avatar", {'file': image_file})

        source_user_profile = self.example_user('hamlet')
        target_user_profile = self.example_user('iago')

        copy_user_settings(source_user_profile, target_user_profile)

        source_path_id = avatar_disk_path(source_user_profile)
        target_path_id = avatar_disk_path(target_user_profile)
        self.assertNotEqual(source_path_id, target_path_id)
        self.assertEqual(open(source_path_id, "rb").read(), open(target_path_id, "rb").read())

        source_original_path_id = avatar_disk_path(source_user_profile, original=True)
        target_original_path_id = avatar_disk_path(target_user_profile, original=True)
        self.assertEqual(open(source_original_path_id, "rb").read(), open(target_original_path_id, "rb").read())

        source_medium_path_id = avatar_disk_path(source_user_profile, medium=True)
        target_medium_path_id = avatar_disk_path(target_user_profile, medium=True)
        self.assertEqual(open(source_medium_path_id, "rb").read(), open(target_medium_path_id, "rb").read())

    def test_delete_avatar_image(self) -> None:
        self.login(self.example_email("hamlet"))
        with get_test_image_file('img.png') as image_file:
            self.client_post("/json/users/me/avatar", {'file': image_file})

        user = self.example_user('hamlet')

        avatar_path_id = avatar_disk_path(user)
        avatar_original_path_id = avatar_disk_path(user, original=True)
        avatar_medium_path_id = avatar_disk_path(user, medium=True)

        self.assertEqual(user.avatar_source, UserProfile.AVATAR_FROM_USER)
        self.assertTrue(os.path.isfile(avatar_path_id))
        self.assertTrue(os.path.isfile(avatar_original_path_id))
        self.assertTrue(os.path.isfile(avatar_medium_path_id))

        zerver.lib.actions.do_delete_avatar_image(user)

        self.assertEqual(user.avatar_source, UserProfile.AVATAR_FROM_GRAVATAR)
        self.assertFalse(os.path.isfile(avatar_path_id))
        self.assertFalse(os.path.isfile(avatar_original_path_id))
        self.assertFalse(os.path.isfile(avatar_medium_path_id))

    def test_invalid_avatars(self) -> None:
        """
        A PUT request to /json/users/me/avatar with an invalid file should fail.
        """
        for fname in self.corrupt_files:
            # with self.subTest(fname=fname):
            self.login(self.example_email("hamlet"))
            with get_test_image_file(fname) as fp:
                result = self.client_post("/json/users/me/avatar", {'file': fp})

            self.assert_json_error(result, "Could not decode image; did you upload an image file?")
            user_profile = self.example_user('hamlet')
            self.assertEqual(user_profile.avatar_version, 1)

    def test_delete_avatar(self) -> None:
        """
        A DELETE request to /json/users/me/avatar should delete the user avatar and return gravatar URL
        """
        self.login(self.example_email("hamlet"))
        hamlet = self.example_user('hamlet')
        hamlet.avatar_source = UserProfile.AVATAR_FROM_USER
        hamlet.save()

        result = self.client_delete("/json/users/me/avatar")
        user_profile = self.example_user('hamlet')

        self.assert_json_success(result)
        self.assertIn("avatar_url", result.json())
        self.assertEqual(result.json()["avatar_url"], avatar_url(user_profile))

        self.assertEqual(user_profile.avatar_source, UserProfile.AVATAR_FROM_GRAVATAR)
        self.assertEqual(user_profile.avatar_version, 2)

    def test_avatar_upload_file_size_error(self) -> None:
        self.login(self.example_email("hamlet"))
        with get_test_image_file(self.correct_files[0][0]) as fp:
            with self.settings(MAX_AVATAR_FILE_SIZE=0):
                result = self.client_post("/json/users/me/avatar", {'file': fp})
        self.assert_json_error(result, "Uploaded file is larger than the allowed limit of 0 MB")

    def tearDown(self) -> None:
        destroy_uploads()

class EmojiTest(UploadSerializeMixin, ZulipTestCase):
    # While testing GIF resizing, we can't test if the final GIF has the same
    # number of frames as the original one because PIL drops duplicate frames
    # with a corresponding increase in the duration of the previous frame.
    def test_resize_emoji(self) -> None:
        # Test unequal width and height of animated GIF image
        animated_unequal_img_data = get_test_image_file('animated_unequal_img.gif').read()
        resized_img_data = resize_emoji(animated_unequal_img_data, size=50)
        im = Image.open(io.BytesIO(resized_img_data))
        self.assertEqual((50, 50), im.size)

        # Test corrupt image exception
        corrupted_img_data = get_test_image_file('corrupt.gif').read()
        with self.assertRaises(BadImageError):
            resize_emoji(corrupted_img_data)

        # Test an image larger than max is resized
        with patch('zerver.lib.upload.MAX_EMOJI_GIF_SIZE', 128):
            animated_large_img_data = get_test_image_file('animated_large_img.gif').read()
            resized_img_data = resize_emoji(animated_large_img_data, size=50)
            im = Image.open(io.BytesIO(resized_img_data))
            self.assertEqual((50, 50), im.size)

        # Test an image file larger than max is resized
        with patch('zerver.lib.upload.MAX_EMOJI_GIF_FILE_SIZE_BYTES', 3 * 1024 * 1024):
            animated_large_img_data = get_test_image_file('animated_large_img.gif').read()
            resized_img_data = resize_emoji(animated_large_img_data, size=50)
            im = Image.open(io.BytesIO(resized_img_data))
            self.assertEqual((50, 50), im.size)

        # Test an image smaller than max and smaller than file size max is not resized
        with patch('zerver.lib.upload.MAX_EMOJI_GIF_SIZE', 512):
            animated_large_img_data = get_test_image_file('animated_large_img.gif').read()
            resized_img_data = resize_emoji(animated_large_img_data, size=50)
            im = Image.open(io.BytesIO(resized_img_data))
            self.assertEqual((256, 256), im.size)

    def tearDown(self) -> None:
        destroy_uploads()

class RealmIconTest(UploadSerializeMixin, ZulipTestCase):

    def test_multiple_upload_failure(self) -> None:
        """
        Attempting to upload two files should fail.
        """
        # Log in as admin
        self.login(self.example_email("iago"))
        with get_test_image_file('img.png') as fp1, \
                get_test_image_file('img.png') as fp2:
            result = self.client_post("/json/realm/icon", {'f1': fp1, 'f2': fp2})
        self.assert_json_error(result, "You must upload exactly one icon.")

    def test_no_file_upload_failure(self) -> None:
        """
        Calling this endpoint with no files should fail.
        """
        self.login(self.example_email("iago"))

        result = self.client_post("/json/realm/icon")
        self.assert_json_error(result, "You must upload exactly one icon.")

    correct_files = [
        ('img.png', 'png_resized.png'),
        ('img.jpg', None),  # jpeg resizing is platform-dependent
        ('img.gif', 'gif_resized.png'),
        ('img.tif', 'tif_resized.png'),
        ('cmyk.jpg', None)
    ]
    corrupt_files = ['text.txt', 'corrupt.png', 'corrupt.gif']

    def test_no_admin_user_upload(self) -> None:
        self.login(self.example_email("hamlet"))
        with get_test_image_file(self.correct_files[0][0]) as fp:
            result = self.client_post("/json/realm/icon", {'file': fp})
        self.assert_json_error(result, 'Must be an organization administrator')

    def test_get_gravatar_icon(self) -> None:
        self.login(self.example_email("hamlet"))
        realm = get_realm('zulip')
        realm.icon_source = Realm.ICON_FROM_GRAVATAR
        realm.save()
        with self.settings(ENABLE_GRAVATAR=True):
            response = self.client_get("/json/realm/icon?foo=bar")
            redirect_url = response['Location']
            self.assertEqual(redirect_url, realm_icon_url(realm) + '&foo=bar')

        with self.settings(ENABLE_GRAVATAR=False):
            response = self.client_get("/json/realm/icon?foo=bar")
            redirect_url = response['Location']
            self.assertTrue(redirect_url.endswith(realm_icon_url(realm) + '&foo=bar'))

    def test_get_realm_icon(self) -> None:
        self.login(self.example_email("hamlet"))

        realm = get_realm('zulip')
        realm.icon_source = Realm.ICON_UPLOADED
        realm.save()
        response = self.client_get("/json/realm/icon?foo=bar")
        redirect_url = response['Location']
        self.assertTrue(redirect_url.endswith(realm_icon_url(realm) + '&foo=bar'))

    def test_valid_icons(self) -> None:
        """
        A PUT request to /json/realm/icon with a valid file should return a url
        and actually create an realm icon.
        """
        for fname, rfname in self.correct_files:
            # TODO: use self.subTest once we're exclusively on python 3 by uncommenting the line below.
            # with self.subTest(fname=fname):
            self.login(self.example_email("iago"))
            with get_test_image_file(fname) as fp:
                result = self.client_post("/json/realm/icon", {'file': fp})
            realm = get_realm('zulip')
            self.assert_json_success(result)
            self.assertIn("icon_url", result.json())
            base = '/user_avatars/%s/realm/icon.png' % (realm.id,)
            url = result.json()['icon_url']
            self.assertEqual(base, url[:len(base)])

            if rfname is not None:
                response = self.client_get(url)
                data = b"".join(response.streaming_content)
                self.assertEqual(Image.open(io.BytesIO(data)).size, (100, 100))

    def test_invalid_icons(self) -> None:
        """
        A PUT request to /json/realm/icon with an invalid file should fail.
        """
        for fname in self.corrupt_files:
            # with self.subTest(fname=fname):
            self.login(self.example_email("iago"))
            with get_test_image_file(fname) as fp:
                result = self.client_post("/json/realm/icon", {'file': fp})

            self.assert_json_error(result, "Could not decode image; did you upload an image file?")

    def test_delete_icon(self) -> None:
        """
        A DELETE request to /json/realm/icon should delete the realm icon and return gravatar URL
        """
        self.login(self.example_email("iago"))
        realm = get_realm('zulip')
        realm.icon_source = Realm.ICON_UPLOADED
        realm.save()

        result = self.client_delete("/json/realm/icon")

        self.assert_json_success(result)
        self.assertIn("icon_url", result.json())
        realm = get_realm('zulip')
        self.assertEqual(result.json()["icon_url"], realm_icon_url(realm))
        self.assertEqual(realm.icon_source, Realm.ICON_FROM_GRAVATAR)

    def test_realm_icon_version(self) -> None:
        self.login(self.example_email("iago"))
        realm = get_realm('zulip')
        icon_version = realm.icon_version
        self.assertEqual(icon_version, 1)
        with get_test_image_file(self.correct_files[0][0]) as fp:
            self.client_post("/json/realm/icon", {'file': fp})
        realm = get_realm('zulip')
        self.assertEqual(realm.icon_version, icon_version + 1)

    def test_realm_icon_upload_file_size_error(self) -> None:
        self.login(self.example_email("iago"))
        with get_test_image_file(self.correct_files[0][0]) as fp:
            with self.settings(MAX_ICON_FILE_SIZE=0):
                result = self.client_post("/json/realm/icon", {'file': fp})
        self.assert_json_error(result, "Uploaded file is larger than the allowed limit of 0 MB")

    def tearDown(self) -> None:
        destroy_uploads()

class RealmLogoTest(UploadSerializeMixin, ZulipTestCase):
    night = False

    def test_multiple_upload_failure(self) -> None:
        """
        Attempting to upload two files should fail.
        """
        # Log in as admin
        self.login(self.example_email("iago"))
        with get_test_image_file('img.png') as fp1, \
                get_test_image_file('img.png') as fp2:
            result = self.client_post("/json/realm/logo", {'f1': fp1, 'f2': fp2,
                                                           'night': ujson.dumps(self.night)})
        self.assert_json_error(result, "You must upload exactly one logo.")

    def test_no_file_upload_failure(self) -> None:
        """
        Calling this endpoint with no files should fail.
        """
        self.login(self.example_email("iago"))

        result = self.client_post("/json/realm/logo", {'night': ujson.dumps(self.night)})
        self.assert_json_error(result, "You must upload exactly one logo.")

    correct_files = [
        ('img.png', 'png_resized.png'),
        ('img.jpg', None),  # jpeg resizing is platform-dependent
        ('img.gif', 'gif_resized.png'),
        ('img.tif', 'tif_resized.png'),
        ('cmyk.jpg', None)
    ]
    corrupt_files = ['text.txt', 'corrupt.png', 'corrupt.gif']

    def test_no_admin_user_upload(self) -> None:
        self.login(self.example_email("hamlet"))
        with get_test_image_file(self.correct_files[0][0]) as fp:
            result = self.client_post("/json/realm/logo", {'file': fp, 'night': ujson.dumps(self.night)})
        self.assert_json_error(result, 'Must be an organization administrator')

    def test_upload_limited_plan_type(self) -> None:
        user_profile = self.example_user("iago")
        do_change_plan_type(user_profile.realm, Realm.LIMITED)
        self.login(user_profile.email)
        with get_test_image_file(self.correct_files[0][0]) as fp:
            result = self.client_post("/json/realm/logo", {'file': fp, 'night': ujson.dumps(self.night)})
        self.assert_json_error(result, 'Feature unavailable on your current plan.')

    def test_get_default_logo(self) -> None:
        self.login(self.example_email("hamlet"))
        realm = get_realm('zulip')
        realm.logo_source = Realm.LOGO_DEFAULT
        realm.night_logo_source = Realm.LOGO_DEFAULT
        realm.save()
        response = self.client_get("/json/realm/logo", {'night': ujson.dumps(self.night)})
        redirect_url = response['Location']
        self.assertEqual(redirect_url, realm_logo_url(realm, self.night) +
                         '&night=%s' % (str(self.night).lower()))

    def test_get_realm_logo(self) -> None:
        self.login(self.example_email("hamlet"))
        realm = get_realm('zulip')
        realm.logo_source = Realm.LOGO_UPLOADED
        realm.night_logo_source = Realm.LOGO_UPLOADED
        realm.save()
        response = self.client_get("/json/realm/logo", {'night': ujson.dumps(self.night)})
        redirect_url = response['Location']
        self.assertTrue(redirect_url.endswith(realm_logo_url(realm, self.night) +
                                              '&night=%s' % (str(self.night).lower())))

    def test_valid_logos(self) -> None:
        """
        A PUT request to /json/realm/logo with a valid file should return a url
        and actually create an realm logo.
        """
        if self.night:
            field_name = 'night_logo_url'
            file_name = 'night_logo.png'
        else:
            field_name = 'logo_url'
            file_name = 'logo.png'
        for fname, rfname in self.correct_files:
            # TODO: use self.subTest once we're exclusively on python 3 by uncommenting the line below.
            # with self.subTest(fname=fname):
            self.login(self.example_email("iago"))
            with get_test_image_file(fname) as fp:
                result = self.client_post("/json/realm/logo", {'file': fp, 'night': ujson.dumps(self.night)})
            realm = get_realm('zulip')
            self.assert_json_success(result)
            self.assertIn(field_name, result.json())
            base = '/user_avatars/%s/realm/%s' % (realm.id, file_name)
            url = result.json()[field_name]
            self.assertEqual(base, url[:len(base)])

            if rfname is not None:
                response = self.client_get(url)
                data = b"".join(response.streaming_content)
                # size should be 100 x 100 because thumbnail keeps aspect ratio
                # while trying to fit in a 800 x 100 box without losing part of the image
                self.assertEqual(Image.open(io.BytesIO(data)).size, (100, 100))

    def test_invalid_logo_upload(self) -> None:
        """
        A PUT request to /json/realm/logo with an invalid file should fail.
        """
        for fname in self.corrupt_files:
            # with self.subTest(fname=fname):
            self.login(self.example_email("iago"))
            with get_test_image_file(fname) as fp:
                result = self.client_post("/json/realm/logo", {'file': fp, 'night': ujson.dumps(self.night)})

            self.assert_json_error(result, "Could not decode image; did you upload an image file?")

    def test_delete_logo(self) -> None:
        """
        A DELETE request to /json/realm/logo should delete the realm logo and return gravatar URL
        """
        if self.night:
            field_name = 'night_logo_url'
        else:
            field_name = 'logo_url'

        self.login(self.example_email("iago"))
        realm = get_realm('zulip')
        realm.logo_source = Realm.LOGO_UPLOADED
        realm.night_logo_source = Realm.LOGO_UPLOADED
        realm.save()
        result = self.client_delete("/json/realm/logo", {'night': ujson.dumps(self.night)})
        self.assert_json_success(result)
        self.assertIn(field_name, result.json())
        realm = get_realm('zulip')
        self.assertEqual(result.json()[field_name], realm_logo_url(realm, self.night))
        if self.night:
            self.assertEqual(realm.night_logo_source, Realm.LOGO_DEFAULT)
        else:
            self.assertEqual(realm.logo_source, Realm.LOGO_DEFAULT)

    def test_logo_version(self) -> None:
        self.login(self.example_email("iago"))
        realm = get_realm('zulip')
        if self.night:
            version = realm.night_logo_version
        else:
            version = realm.logo_version
        self.assertEqual(version, 1)
        with get_test_image_file(self.correct_files[0][0]) as fp:
            self.client_post("/json/realm/logo", {'file': fp, 'night': ujson.dumps(self.night)})
        realm = get_realm('zulip')
        if self.night:
            self.assertEqual(realm.night_logo_version, version + 1)
        else:
            self.assertEqual(realm.logo_version, version + 1)

    def test_logo_upload_file_size_error(self) -> None:
        self.login(self.example_email("iago"))
        with get_test_image_file(self.correct_files[0][0]) as fp:
            with self.settings(MAX_LOGO_FILE_SIZE=0):
                result = self.client_post("/json/realm/logo", {'file': fp, 'night':
                                                               ujson.dumps(self.night)})
        self.assert_json_error(result, "Uploaded file is larger than the allowed limit of 0 MB")

    def tearDown(self) -> None:
        destroy_uploads()

class RealmNightLogoTest(RealmLogoTest):
    # Run the same tests as for RealmLogoTest, just with night mode enabled
    night = True

class LocalStorageTest(UploadSerializeMixin, ZulipTestCase):

    def test_file_upload_local(self) -> None:
        user_profile = self.example_user('hamlet')
        uri = upload_message_file(u'dummy.txt', len(b'zulip!'), u'text/plain', b'zulip!', user_profile)

        base = '/user_uploads/'
        self.assertEqual(base, uri[:len(base)])
        path_id = re.sub('/user_uploads/', '', uri)
        file_path = os.path.join(settings.LOCAL_UPLOADS_DIR, 'files', path_id)
        self.assertTrue(os.path.isfile(file_path))

        uploaded_file = Attachment.objects.get(owner=user_profile, path_id=path_id)
        self.assertEqual(len(b'zulip!'), uploaded_file.size)

    def test_delete_message_image_local(self) -> None:
        self.login(self.example_email("hamlet"))
        fp = StringIO("zulip!")
        fp.name = "zulip.txt"
        result = self.client_post("/json/user_uploads", {'file': fp})

        path_id = re.sub('/user_uploads/', '', result.json()['uri'])
        self.assertTrue(delete_message_image(path_id))

    def test_emoji_upload_local(self) -> None:
        user_profile = self.example_user("hamlet")
        image_file = get_test_image_file("img.png")
        file_name = "emoji.png"

        upload_emoji_image(image_file, file_name, user_profile)

        emoji_path = RealmEmoji.PATH_ID_TEMPLATE.format(
            realm_id=user_profile.realm_id,
            emoji_file_name=file_name,
        )

        file_path = os.path.join(settings.LOCAL_UPLOADS_DIR, "avatars", emoji_path)
        image_file.seek(0)
        self.assertEqual(image_file.read(), open(file_path + ".original", "rb").read())

        resized_image = Image.open(open(file_path, "rb"))
        expected_size = (DEFAULT_EMOJI_SIZE, DEFAULT_EMOJI_SIZE)
        self.assertEqual(expected_size, resized_image.size)

    def test_get_emoji_url_local(self) -> None:
        user_profile = self.example_user("hamlet")
        image_file = get_test_image_file("img.png")
        file_name = "emoji.png"

        upload_emoji_image(image_file, file_name, user_profile)
        url = zerver.lib.upload.upload_backend.get_emoji_url(file_name, user_profile.realm_id)

        emoji_path = RealmEmoji.PATH_ID_TEMPLATE.format(
            realm_id=user_profile.realm_id,
            emoji_file_name=file_name,
        )
        expected_url = "/user_avatars/{emoji_path}".format(emoji_path=emoji_path)
        self.assertEqual(expected_url, url)

    def tearDown(self) -> None:
        destroy_uploads()


class S3Test(ZulipTestCase):

    @use_s3_backend
    def test_file_upload_s3(self) -> None:
        bucket = create_s3_buckets(settings.S3_AUTH_UPLOADS_BUCKET)[0]

        user_profile = self.example_user('hamlet')
        uri = upload_message_file(u'dummy.txt', len(b'zulip!'), u'text/plain', b'zulip!', user_profile)

        base = '/user_uploads/'
        self.assertEqual(base, uri[:len(base)])
        path_id = re.sub('/user_uploads/', '', uri)
        content = bucket.get_key(path_id).get_contents_as_string()
        self.assertEqual(b"zulip!", content)

        uploaded_file = Attachment.objects.get(owner=user_profile, path_id=path_id)
        self.assertEqual(len(b"zulip!"), uploaded_file.size)

        self.subscribe(self.example_user("hamlet"), "Denmark")
        body = "First message ...[zulip.txt](http://localhost:9991" + uri + ")"
        self.send_stream_message(self.example_email("hamlet"), "Denmark", body, "test")
        self.assertIn('title="dummy.txt"', self.get_last_message().rendered_content)

    @use_s3_backend
    def test_file_upload_s3_with_undefined_content_type(self) -> None:
        bucket = create_s3_buckets(settings.S3_AUTH_UPLOADS_BUCKET)[0]

        user_profile = self.example_user('hamlet')
        uri = upload_message_file(u'dummy.txt', len(b'zulip!'), None, b'zulip!', user_profile)

        path_id = re.sub('/user_uploads/', '', uri)
        self.assertEqual(b"zulip!", bucket.get_key(path_id).get_contents_as_string())
        uploaded_file = Attachment.objects.get(owner=user_profile, path_id=path_id)
        self.assertEqual(len(b"zulip!"), uploaded_file.size)

    @use_s3_backend
    def test_message_image_delete_s3(self) -> None:
        create_s3_buckets(settings.S3_AUTH_UPLOADS_BUCKET)

        user_profile = self.example_user('hamlet')
        uri = upload_message_file(u'dummy.txt', len(b'zulip!'), u'text/plain', b'zulip!', user_profile)

        path_id = re.sub('/user_uploads/', '', uri)
        self.assertTrue(delete_message_image(path_id))

    @use_s3_backend
    def test_message_image_delete_when_file_doesnt_exist(self) -> None:
        self.assertEqual(False, delete_message_image('non-existant-file'))

    @use_s3_backend
    def test_file_upload_authed(self) -> None:
        """
        A call to /json/user_uploads should return a uri and actually create an object.
        """
        create_s3_buckets(settings.S3_AUTH_UPLOADS_BUCKET)

        self.login(self.example_email("hamlet"))
        fp = StringIO("zulip!")
        fp.name = "zulip.txt"

        result = self.client_post("/json/user_uploads", {'file': fp})
        self.assert_json_success(result)
        self.assertIn("uri", result.json())
        base = '/user_uploads/'
        uri = result.json()['uri']
        self.assertEqual(base, uri[:len(base)])

        response = self.client_get(uri)
        redirect_url = response['Location']

        self.assertEqual(b"zulip!", urllib.request.urlopen(redirect_url).read().strip())

        self.subscribe(self.example_user("hamlet"), "Denmark")
        body = "First message ...[zulip.txt](http://localhost:9991" + uri + ")"
        self.send_stream_message(self.example_email("hamlet"), "Denmark", body, "test")
        self.assertIn('title="zulip.txt"', self.get_last_message().rendered_content)

    @use_s3_backend
    def test_upload_avatar_image(self) -> None:
        bucket = create_s3_buckets(settings.S3_AVATAR_BUCKET)[0]

        user_profile = self.example_user('hamlet')
        path_id = user_avatar_path(user_profile)
        original_image_path_id = path_id + ".original"
        medium_path_id = path_id + "-medium.png"

        with get_test_image_file('img.png') as image_file:
            zerver.lib.upload.upload_backend.upload_avatar_image(image_file, user_profile, user_profile)
        test_image_data = open(get_test_image_file('img.png').name, 'rb').read()
        test_medium_image_data = resize_avatar(test_image_data, MEDIUM_AVATAR_SIZE)

        original_image_key = bucket.get_key(original_image_path_id)
        self.assertEqual(original_image_key.key, original_image_path_id)
        image_data = original_image_key.get_contents_as_string()
        self.assertEqual(image_data, test_image_data)

        medium_image_key = bucket.get_key(medium_path_id)
        self.assertEqual(medium_image_key.key, medium_path_id)
        medium_image_data = medium_image_key.get_contents_as_string()
        self.assertEqual(medium_image_data, test_medium_image_data)
        bucket.delete_key(medium_image_key)

        zerver.lib.upload.upload_backend.ensure_medium_avatar_image(user_profile)
        medium_image_key = bucket.get_key(medium_path_id)
        self.assertEqual(medium_image_key.key, medium_path_id)

    @use_s3_backend
    def test_copy_avatar_image(self) -> None:
        bucket = create_s3_buckets(settings.S3_AVATAR_BUCKET)[0]

        self.login(self.example_email("hamlet"))
        with get_test_image_file('img.png') as image_file:
            self.client_post("/json/users/me/avatar", {'file': image_file})

        source_user_profile = self.example_user('hamlet')
        target_user_profile = self.example_user('othello')

        copy_user_settings(source_user_profile, target_user_profile)

        source_path_id = user_avatar_path(source_user_profile)
        target_path_id = user_avatar_path(target_user_profile)
        self.assertNotEqual(source_path_id, target_path_id)

        source_image_key = bucket.get_key(source_path_id)
        target_image_key = bucket.get_key(target_path_id)
        self.assertEqual(target_image_key.key, target_path_id)
        self.assertEqual(source_image_key.content_type, target_image_key.content_type)
        source_image_data = source_image_key.get_contents_as_string()
        target_image_data = target_image_key.get_contents_as_string()
        self.assertEqual(source_image_data, target_image_data)

        source_original_image_path_id = source_path_id + ".original"
        target_original_image_path_id = target_path_id + ".original"
        target_original_image_key = bucket.get_key(target_original_image_path_id)
        self.assertEqual(target_original_image_key.key, target_original_image_path_id)
        source_original_image_key = bucket.get_key(source_original_image_path_id)
        self.assertEqual(source_original_image_key.content_type, target_original_image_key.content_type)
        source_image_data = source_original_image_key.get_contents_as_string()
        target_image_data = target_original_image_key.get_contents_as_string()
        self.assertEqual(source_image_data, target_image_data)

        target_medium_path_id = target_path_id + "-medium.png"
        source_medium_path_id = source_path_id + "-medium.png"
        source_medium_image_key = bucket.get_key(source_medium_path_id)
        target_medium_image_key = bucket.get_key(target_medium_path_id)
        self.assertEqual(target_medium_image_key.key, target_medium_path_id)
        self.assertEqual(source_medium_image_key.content_type, target_medium_image_key.content_type)
        source_medium_image_data = source_medium_image_key.get_contents_as_string()
        target_medium_image_data = target_medium_image_key.get_contents_as_string()
        self.assertEqual(source_medium_image_data, target_medium_image_data)

    @use_s3_backend
    def test_delete_avatar_image(self) -> None:
        bucket = create_s3_buckets(settings.S3_AVATAR_BUCKET)[0]

        self.login(self.example_email("hamlet"))
        with get_test_image_file('img.png') as image_file:
            self.client_post("/json/users/me/avatar", {'file': image_file})

        user = self.example_user('hamlet')

        avatar_path_id = user_avatar_path(user)
        avatar_original_image_path_id = avatar_path_id + ".original"
        avatar_medium_path_id = avatar_path_id + "-medium.png"

        self.assertEqual(user.avatar_source, UserProfile.AVATAR_FROM_USER)
        self.assertIsNotNone(bucket.get_key(avatar_path_id))
        self.assertIsNotNone(bucket.get_key(avatar_original_image_path_id))
        self.assertIsNotNone(bucket.get_key(avatar_medium_path_id))

        zerver.lib.actions.do_delete_avatar_image(user)

        self.assertEqual(user.avatar_source, UserProfile.AVATAR_FROM_GRAVATAR)
        self.assertIsNone(bucket.get_key(avatar_path_id))
        self.assertIsNone(bucket.get_key(avatar_original_image_path_id))
        self.assertIsNone(bucket.get_key(avatar_medium_path_id))

    @use_s3_backend
    def test_get_realm_for_filename(self) -> None:
        create_s3_buckets(settings.S3_AUTH_UPLOADS_BUCKET)

        user_profile = self.example_user('hamlet')
        uri = upload_message_file(u'dummy.txt', len(b'zulip!'), u'text/plain', b'zulip!', user_profile)
        path_id = re.sub('/user_uploads/', '', uri)
        self.assertEqual(user_profile.realm_id, get_realm_for_filename(path_id))

    @use_s3_backend
    def test_get_realm_for_filename_when_key_doesnt_exist(self) -> None:
        self.assertEqual(None, get_realm_for_filename('non-existent-file-path'))

    @use_s3_backend
    def test_upload_realm_icon_image(self) -> None:
        bucket = create_s3_buckets(settings.S3_AVATAR_BUCKET)[0]

        user_profile = self.example_user("hamlet")
        image_file = get_test_image_file("img.png")
        zerver.lib.upload.upload_backend.upload_realm_icon_image(image_file, user_profile)

        original_path_id = os.path.join(str(user_profile.realm.id), "realm", "icon.original")
        original_key = bucket.get_key(original_path_id)
        image_file.seek(0)
        self.assertEqual(image_file.read(), original_key.get_contents_as_string())

        resized_path_id = os.path.join(str(user_profile.realm.id), "realm", "icon.png")
        resized_data = bucket.get_key(resized_path_id).read()
        # resized image size should be 100 x 100 because thumbnail keeps aspect ratio
        # while trying to fit in a 800 x 100 box without losing part of the image
        resized_image = Image.open(io.BytesIO(resized_data)).size
        self.assertEqual(resized_image, (DEFAULT_AVATAR_SIZE, DEFAULT_AVATAR_SIZE))

    @use_s3_backend
    def _test_upload_logo_image(self, night: bool, file_name: str) -> None:
        bucket = create_s3_buckets(settings.S3_AVATAR_BUCKET)[0]

        user_profile = self.example_user("hamlet")
        image_file = get_test_image_file("img.png")
        zerver.lib.upload.upload_backend.upload_realm_logo_image(image_file, user_profile, night)

        original_path_id = os.path.join(str(user_profile.realm.id), "realm", "%s.original" % (file_name))
        print(original_path_id)
        original_key = bucket.get_key(original_path_id)
        print(original_key)
        image_file.seek(0)
        self.assertEqual(image_file.read(), original_key.get_contents_as_string())

        resized_path_id = os.path.join(str(user_profile.realm.id), "realm", "%s.png" % (file_name))
        resized_data = bucket.get_key(resized_path_id).read()
        resized_image = Image.open(io.BytesIO(resized_data)).size
        self.assertEqual(resized_image, (DEFAULT_AVATAR_SIZE, DEFAULT_AVATAR_SIZE))

    def test_upload_realm_logo_image(self) -> None:
        self._test_upload_logo_image(night = False, file_name = 'logo')
        self._test_upload_logo_image(night = True, file_name = 'night_logo')

    @use_s3_backend
    def test_upload_emoji_image(self) -> None:
        bucket = create_s3_buckets(settings.S3_AVATAR_BUCKET)[0]

        user_profile = self.example_user("hamlet")
        image_file = get_test_image_file("img.png")
        emoji_name = "emoji.png"
        zerver.lib.upload.upload_backend.upload_emoji_image(image_file, emoji_name, user_profile)

        emoji_path = RealmEmoji.PATH_ID_TEMPLATE.format(
            realm_id=user_profile.realm_id,
            emoji_file_name=emoji_name,
        )
        original_key = bucket.get_key(emoji_path + ".original")
        image_file.seek(0)
        self.assertEqual(image_file.read(), original_key.get_contents_as_string())

        resized_data = bucket.get_key(emoji_path).read()
        resized_image = Image.open(io.BytesIO(resized_data))
        self.assertEqual(resized_image.size, (DEFAULT_EMOJI_SIZE, DEFAULT_EMOJI_SIZE))

    @use_s3_backend
    def test_get_emoji_url(self) -> None:
        emoji_name = "emoji.png"
        realm_id = 1
        bucket = settings.S3_AVATAR_BUCKET
        path = RealmEmoji.PATH_ID_TEMPLATE.format(realm_id=realm_id, emoji_file_name=emoji_name)

        url = zerver.lib.upload.upload_backend.get_emoji_url('emoji.png', realm_id)

        expected_url = "https://{bucket}.s3.amazonaws.com/{path}".format(bucket=bucket, path=path)
        self.assertEqual(expected_url, url)


class UploadTitleTests(TestCase):
    def test_upload_titles(self) -> None:
        self.assertEqual(url_filename("http://localhost:9991/user_uploads/1/LUeQZUG5jxkagzVzp1Ox_amr/dummy.txt"), "dummy.txt")
        self.assertEqual(url_filename("http://localhost:9991/user_uploads/1/94/SzGYe0RFT-tEcOhQ6n-ZblFZ/zulip.txt"), "zulip.txt")
        self.assertEqual(url_filename("https://zulip.com/user_uploads/4142/LUeQZUG5jxkagzVzp1Ox_amr/pasted_image.png"), "pasted_image.png")
        self.assertEqual(url_filename("https://zulipchat.com/integrations"), "https://zulipchat.com/integrations")
        self.assertEqual(url_filename("https://example.com"), "https://example.com")

class SanitizeNameTests(TestCase):
    def test_file_name(self) -> None:
        self.assertEqual(sanitize_name(u'test.txt'), u'test.txt')
        self.assertEqual(sanitize_name(u'.hidden'), u'.hidden')
        self.assertEqual(sanitize_name(u'.hidden.txt'), u'.hidden.txt')
        self.assertEqual(sanitize_name(u'tarball.tar.gz'), u'tarball.tar.gz')
        self.assertEqual(sanitize_name(u'.hidden_tarball.tar.gz'), u'.hidden_tarball.tar.gz')
        self.assertEqual(sanitize_name(u'Testing{}*&*#().ta&&%$##&&r.gz'), u'Testing.tar.gz')
        self.assertEqual(sanitize_name(u'*testingfile?*.txt'), u'testingfile.txt')
        self.assertEqual(sanitize_name(u'snowman☃.txt'), u'snowman.txt')
        self.assertEqual(sanitize_name(u'테스트.txt'), u'테스트.txt')
        self.assertEqual(sanitize_name(u'~/."\\`\\?*"u0`000ssh/test.t**{}ar.gz'), u'.u0000sshtest.tar.gz')


class UploadSpaceTests(UploadSerializeMixin, ZulipTestCase):
    def setUp(self) -> None:
        self.realm = get_realm("zulip")
        self.user_profile = self.example_user('hamlet')

    def test_currently_used_upload_space(self) -> None:
        self.assertEqual(None, cache_get(get_realm_used_upload_space_cache_key(self.realm)))
        self.assertEqual(0, self.realm.currently_used_upload_space_bytes())
        self.assertEqual(0, cache_get(get_realm_used_upload_space_cache_key(self.realm))[0])

        data = b'zulip!'
        upload_message_file(u'dummy.txt', len(data), u'text/plain', data, self.user_profile)
        self.assertEqual(None, cache_get(get_realm_used_upload_space_cache_key(self.realm)))
        self.assertEqual(len(data), self.realm.currently_used_upload_space_bytes())
        self.assertEqual(len(data), cache_get(get_realm_used_upload_space_cache_key(self.realm))[0])

        data2 = b'more-data!'
        upload_message_file(u'dummy2.txt', len(data2), u'text/plain', data2, self.user_profile)
        self.assertEqual(None, cache_get(get_realm_used_upload_space_cache_key(self.realm)))
        self.assertEqual(len(data) + len(data2), self.realm.currently_used_upload_space_bytes())
        self.assertEqual(len(data) + len(data2), cache_get(get_realm_used_upload_space_cache_key(self.realm))[0])

        attachment = Attachment.objects.get(file_name="dummy.txt")
        attachment.file_name = "dummy1.txt"
        attachment.save(update_fields=["file_name"])
        self.assertEqual(len(data) + len(data2), cache_get(get_realm_used_upload_space_cache_key(self.realm))[0])
        self.assertEqual(len(data) + len(data2), self.realm.currently_used_upload_space_bytes())

        attachment.delete()
        self.assertEqual(None, cache_get(get_realm_used_upload_space_cache_key(self.realm)))
        self.assertEqual(len(data2), self.realm.currently_used_upload_space_bytes())
        self.assertEqual(len(data2), cache_get(get_realm_used_upload_space_cache_key(self.realm))[0])

    def test_upload_space_used_api(self) -> None:
        self.login(self.user_profile.email)
        response = self.client_get("/json/realm/upload_space_used")
        self.assert_in_success_response(["0"], response)

        data = b'zulip!'
        upload_message_file(u'dummy.txt', len(data), u'text/plain', data, self.user_profile)
        response = self.client_get("/json/realm/upload_space_used")
        self.assert_in_success_response([str(len(data))], response)

class ExifRotateTests(TestCase):
    def test_image_do_not_rotate(self) -> None:
        # Image does not have _getexif method.
        img_data = get_test_image_file('img.png').read()
        img = Image.open(io.BytesIO(img_data))
        result = exif_rotate(img)
        self.assertEqual(result, img)

        # Image with no exif data.
        img_data = get_test_image_file('img_no_exif.jpg').read()
        img = Image.open(io.BytesIO(img_data))
        result = exif_rotate(img)
        self.assertEqual(result, img)

        # Orientation of the image is 1.
        img_data = get_test_image_file('img.jpg').read()
        img = Image.open(io.BytesIO(img_data))
        result = exif_rotate(img)
        self.assertEqual(result, img)

    def test_image_rotate(self) -> None:
        with mock.patch('PIL.Image.Image.rotate') as rotate:
            img_data = get_test_image_file('img_orientation_3.jpg').read()
            img = Image.open(io.BytesIO(img_data))
            exif_rotate(img)
            rotate.assert_called_with(180, expand=True)

            img_data = get_test_image_file('img_orientation_6.jpg').read()
            img = Image.open(io.BytesIO(img_data))
            exif_rotate(img)
            rotate.assert_called_with(270, expand=True)

            img_data = get_test_image_file('img_orientation_8.jpg').read()
            img = Image.open(io.BytesIO(img_data))
            exif_rotate(img)
            rotate.assert_called_with(90, expand=True)

class DecompressionBombTests(ZulipTestCase):
    def setUp(self) -> None:
        self.test_urls = {
            "/json/users/me/avatar": "Image size exceeds limit.",
            "/json/realm/logo": "Image size exceeds limit.",
            "/json/realm/icon": "Image size exceeds limit.",
            "/json/realm/emoji/bomb_emoji": "Image file upload failed.",
        }

    def test_decompression_bomb(self) -> None:
        self.login(self.example_email("iago"))
        with get_test_image_file("bomb.png") as fp:
            for url, error_string in self.test_urls.items():
                fp.seek(0, 0)
                if (url == "/json/realm/logo"):
                    result = self.client_post(url, {'f1': fp, 'night': ujson.dumps(False)})
                else:
                    result = self.client_post(url, {'f1': fp})
                self.assert_json_error(result, error_string)
