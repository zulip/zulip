# -*- coding: utf-8 -*-
from __future__ import absolute_import
from django.conf import settings
from django.test import TestCase, override_settings
from unittest import skip

from zerver.lib.avatar import avatar_url
from zerver.lib.bugdown import url_filename
from zerver.lib.realm_icon import realm_icon_url
from zerver.lib.test_classes import ZulipTestCase, UploadSerializeMixin
from zerver.lib.test_helpers import (
    avatar_disk_path,
    get_test_image_file,
    POSTRequestMock,
)
from zerver.lib.test_runner import slow
from zerver.lib.upload import sanitize_name, S3UploadBackend, \
    upload_message_image, delete_message_image, LocalUploadBackend, \
    ZulipUploadBackend
import zerver.lib.upload
from zerver.models import Attachment, Recipient, get_user, \
    get_old_unclaimed_attachments, Message, UserProfile, Stream, Realm, \
    RealmDomain, get_realm, get_system_bot
from zerver.lib.actions import (
    do_delete_old_unclaimed_attachments,
    internal_send_private_message,
)
from zilencer.models import Deployment

from zerver.views.upload import upload_file_backend

from six.moves import urllib
from PIL import Image

from boto.s3.connection import S3Connection
from boto.s3.key import Key
from six.moves import StringIO as _StringIO
import mock
import os
import io
import shutil
import re
import datetime
import requests
import base64
from datetime import timedelta
from django.utils.timezone import now as timezone_now

from moto import mock_s3_deprecated

from typing import Any, Callable, TypeVar, Text

def destroy_uploads():
    # type: () -> None
    if os.path.exists(settings.LOCAL_UPLOADS_DIR):
        shutil.rmtree(settings.LOCAL_UPLOADS_DIR)

class StringIO(_StringIO):
    name = ''  # https://github.com/python/typeshed/issues/598

class FileUploadTest(UploadSerializeMixin, ZulipTestCase):

    def test_rest_endpoint(self):
        # type: () -> None
        """
        Tests the /api/v1/user_uploads api endpoint. Here a single file is uploaded
        and downloaded using a username and api_key
        """
        fp = StringIO("zulip!")
        fp.name = "zulip.txt"

        # Upload file via API
        auth_headers = self.api_auth(self.example_email("hamlet"))
        result = self.client_post('/api/v1/user_uploads', {'file': fp}, **auth_headers)
        self.assertIn("uri", result.json())
        uri = result.json()['uri']
        base = '/user_uploads/'
        self.assertEqual(base, uri[:len(base)])

        # Download file via API
        self.logout()
        response = self.client_get(uri, **auth_headers)
        data = b"".join(response.streaming_content)
        self.assertEqual(b"zulip!", data)

        # Files uploaded through the API should be accesible via the web client
        self.login(self.example_email("hamlet"))
        self.assert_url_serves_contents_of_file(uri, b"zulip!")

    def test_filename_encoding(self):
        # type: () -> None
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

    def test_file_too_big_failure(self):
        # type: () -> None
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

    def test_multiple_upload_failure(self):
        # type: () -> None
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

    def test_no_file_upload_failure(self):
        # type: () -> None
        """
        Calling this endpoint with no files should fail.
        """
        self.login(self.example_email("hamlet"))

        result = self.client_post("/json/user_uploads")
        self.assert_json_error(result, "You must specify a file to upload")

    def test_download_non_existent_file(self):
        # type: () -> None
        self.login(self.example_email("hamlet"))
        response = self.client_get('/user_uploads/unk/nonexistent_file')
        self.assertEqual(response.status_code, 404)
        self.assertIn('File not found', str(response.content))

    # This test will go through the code path for uploading files onto LOCAL storage
    # when zulip is in DEVELOPMENT mode.
    def test_file_upload_authed(self):
        # type: () -> None
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
        self.send_message(self.example_email("hamlet"), "Denmark", Recipient.STREAM, body, "test")
        self.assertIn('title="zulip.txt"', self.get_last_message().rendered_content)

    def test_file_download_unauthed(self):
        # type: () -> None
        self.login(self.example_email("hamlet"))
        fp = StringIO("zulip!")
        fp.name = "zulip.txt"
        result = self.client_post("/json/user_uploads", {'file': fp})
        uri = result.json()["uri"]

        self.logout()
        response = self.client_get(uri)
        self.assert_json_error(response, "Not logged in: API authentication or user session required",
                               status_code=401)

    def test_removed_file_download(self):
        # type: () -> None
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

    def test_non_existing_file_download(self):
        # type: () -> None
        '''
        Trying to download a file that was never uploaded will return a json_error
        '''
        self.login(self.example_email("hamlet"))
        response = self.client_get("http://localhost:9991/user_uploads/1/ff/gg/abc.py")
        self.assertEqual(response.status_code, 404)
        self.assert_in_response('File not found.', response)

    def test_delete_old_unclaimed_attachments(self):
        # type: () -> None
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

        # Send message refering only dummy_1
        self.subscribe(self.example_user("hamlet"), "Denmark")
        body = "Some files here ...[zulip.txt](http://localhost:9991/user_uploads/" + d1_path_id + ")"
        self.send_message(self.example_email("hamlet"), "Denmark", Recipient.STREAM, body, "test")

        # dummy_2 should not exist in database or the uploads folder
        do_delete_old_unclaimed_attachments(2)
        self.assertTrue(not Attachment.objects.filter(path_id = d2_path_id).exists())
        self.assertTrue(not delete_message_image(d2_path_id))

    def test_attachment_url_without_upload(self):
        # type: () -> None
        self.login(self.example_email("hamlet"))
        body = "Test message ...[zulip.txt](http://localhost:9991/user_uploads/1/64/fake_path_id.txt)"
        self.send_message(self.example_email("hamlet"), "Denmark", Recipient.STREAM, body, "test")
        self.assertFalse(Attachment.objects.filter(path_id = "1/64/fake_path_id.txt").exists())

    def test_multiple_claim_attachments(self):
        # type: () -> None
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
        self.send_message(self.example_email("hamlet"), "Denmark", Recipient.STREAM, body, "test")
        body = "Second message ...[zulip.txt](http://localhost:9991/user_uploads/" + d1_path_id + ")"
        self.send_message(self.example_email("hamlet"), "Denmark", Recipient.STREAM, body, "test")

        self.assertEqual(Attachment.objects.get(path_id=d1_path_id).messages.count(), 2)

    def test_multiple_claim_attachments_different_owners(self):
        # type: () -> None
        """This test tries to claim the same attachment more than once, first
        with a private stream and then with differnet recipients."""
        self.login(self.example_email("hamlet"))
        d1 = StringIO("zulip!")
        d1.name = "dummy_1.txt"
        result = self.client_post("/json/user_uploads", {'file': d1})
        d1_path_id = re.sub('/user_uploads/', '', result.json()['uri'])

        self.make_stream("private_stream", invite_only=True)
        self.subscribe(self.example_user("hamlet"), "private_stream")

        # First, send the mesasge to the new private stream.
        body = "First message ...[zulip.txt](http://localhost:9991/user_uploads/" + d1_path_id + ")"
        self.send_message(self.example_email("hamlet"), "private_stream", Recipient.STREAM, body, "test")
        self.assertFalse(Attachment.objects.get(path_id=d1_path_id).is_realm_public)
        self.assertEqual(Attachment.objects.get(path_id=d1_path_id).messages.count(), 1)

        # Then, try having a user who didn't receive the message try to publish it, and fail
        body = "Illegal message ...[zulip.txt](http://localhost:9991/user_uploads/" + d1_path_id + ")"
        self.send_message(self.example_email("cordelia"), "Denmark", Recipient.STREAM, body, "test")
        self.assertEqual(Attachment.objects.get(path_id=d1_path_id).messages.count(), 1)
        self.assertFalse(Attachment.objects.get(path_id=d1_path_id).is_realm_public)

        # Then, have the owner PM it to another user, giving that other user access.
        body = "Second message ...[zulip.txt](http://localhost:9991/user_uploads/" + d1_path_id + ")"
        self.send_message(self.example_email("hamlet"), self.example_email("othello"), Recipient.PERSONAL, body, "test")
        self.assertEqual(Attachment.objects.get(path_id=d1_path_id).messages.count(), 2)
        self.assertFalse(Attachment.objects.get(path_id=d1_path_id).is_realm_public)

        # Then, have that new recipient user publish it.
        body = "Third message ...[zulip.txt](http://localhost:9991/user_uploads/" + d1_path_id + ")"
        self.send_message(self.example_email("othello"), "Denmark", Recipient.STREAM, body, "test")
        self.assertEqual(Attachment.objects.get(path_id=d1_path_id).messages.count(), 3)
        self.assertTrue(Attachment.objects.get(path_id=d1_path_id).is_realm_public)

    def test_check_attachment_reference_update(self):
        # type: () -> None
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
        msg_id = self.send_message(self.example_email("hamlet"), "test", Recipient.STREAM, body, "test")

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

    def test_file_name(self):
        # type: () -> None
        """
        Unicode filenames should be processed correctly.
        """
        self.login(self.example_email("hamlet"))
        for expected in ["Здравейте.txt", "test"]:
            fp = StringIO("bah!")
            fp.name = urllib.parse.quote(expected)

            result = self.client_post("/json/user_uploads", {'f1': fp})
            assert sanitize_name(expected) in result.json()['uri']

    def test_upload_size_quote(self):
        # type: () -> None
        """
        User quote for uploading should not be exceeded
        """
        self.login(self.example_email("hamlet"))

        d1 = StringIO("zulip!")
        d1.name = "dummy_1.txt"
        result = self.client_post("/json/user_uploads", {'file': d1})
        d1_path_id = re.sub('/user_uploads/', '', result.json()['uri'])
        d1_attachment = Attachment.objects.get(path_id = d1_path_id)
        self.assert_json_success(result)

        """
        Below we set size quota to the limit without 1 upload(1GB - 11 bytes).
        """
        d1_attachment.size = UserProfile.DEFAULT_UPLOADS_QUOTA - 11
        d1_attachment.save()

        d2 = StringIO("zulip!")
        d2.name = "dummy_2.txt"
        result = self.client_post("/json/user_uploads", {'file': d2})
        self.assert_json_success(result)

        d3 = StringIO("zulip!")
        d3.name = "dummy_3.txt"
        result = self.client_post("/json/user_uploads", {'file': d3})
        self.assert_json_error(result, "Upload would exceed your maximum quota.")

    def test_cross_realm_file_access(self):
        # type: () -> None

        def create_user(email, realm_id):
            # type: (Text, Text) -> UserProfile
            self.register(email, 'test', subdomain=realm_id)
            return get_user(email, get_realm(realm_id))

        test_subdomain = "uploadtest.example.com"
        user1_email = 'user1@uploadtest.example.com'
        user2_email = 'test-og-bot@zulip.com'
        user3_email = 'other-user@uploadtest.example.com'

        dep = Deployment()
        dep.base_api_url = "https://zulip.com/api/"
        dep.base_site_url = "https://zulip.com/"
        # We need to save the object before we can access
        # the many-to-many relationship 'realms'
        dep.save()
        dep.realms = [get_realm("zulip")]
        dep.save()

        r1 = Realm.objects.create(string_id=test_subdomain, invite_required=False)
        RealmDomain.objects.create(realm=r1, domain=test_subdomain)
        deployment = Deployment.objects.filter()[0]
        deployment.realms.add(r1)

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

        self.login(user1_email, 'test')
        response = self.client_get(uri, subdomain=test_subdomain)
        self.assertEqual(response.status_code, 200)
        data = b"".join(response.streaming_content)
        self.assertEqual(b"zulip!", data)
        self.logout()

        # Confirm other cross-realm users can't read it.
        self.login(user3_email, 'test')
        response = self.client_get(uri, subdomain=test_subdomain)
        self.assertEqual(response.status_code, 403)
        self.assert_in_response("You are not authorized to view this file.", response)

    def test_file_download_authorization_invite_only(self):
        # type: () -> None
        subscribed_users = [self.example_email("hamlet"), self.example_email("iago")]
        unsubscribed_users = [self.example_email("othello"), self.example_email("prospero")]
        realm = get_realm("zulip")
        for email in subscribed_users:
            self.subscribe(get_user(email, realm), "test-subscribe")

        # Make the stream private
        stream = Stream.objects.get(name='test-subscribe')
        stream.invite_only = True
        stream.save()

        self.login(self.example_email("hamlet"))
        fp = StringIO("zulip!")
        fp.name = "zulip.txt"
        result = self.client_post("/json/user_uploads", {'file': fp})
        uri = result.json()['uri']
        fp_path_id = re.sub('/user_uploads/', '', uri)
        body = "First message ...[zulip.txt](http://localhost:9991/user_uploads/" + fp_path_id + ")"
        self.send_message(self.example_email("hamlet"), "test-subscribe", Recipient.STREAM, body, "test")
        self.logout()

        # Subscribed user should be able to view file
        for user in subscribed_users:
            self.login(user)
            response = self.client_get(uri)
            self.assertEqual(response.status_code, 200)
            data = b"".join(response.streaming_content)
            self.assertEqual(b"zulip!", data)
            self.logout()

        # Unsubscribed user should not be able to view file
        for user in unsubscribed_users:
            self.login(user)
            response = self.client_get(uri)
            self.assertEqual(response.status_code, 403)
            self.assert_in_response("You are not authorized to view this file.", response)
            self.logout()

    def test_file_download_authorization_public(self):
        # type: () -> None
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
        self.send_message(self.example_email("hamlet"), "test-subscribe", Recipient.STREAM, body, "test")
        self.logout()

        # Now all users should be able to access the files
        for user in subscribed_users + unsubscribed_users:
            self.login(user)
            response = self.client_get(uri)
            data = b"".join(response.streaming_content)
            self.assertEqual(b"zulip!", data)
            self.logout()

    def tearDown(self):
        # type: () -> None
        destroy_uploads()

class AvatarTest(UploadSerializeMixin, ZulipTestCase):

    def test_avatar_url(self):
        # type: () -> None
        """Verifies URL schemes for avatars and realm icons."""
        backend = LocalUploadBackend()  # type: ZulipUploadBackend
        self.assertEqual(backend.get_avatar_url("hash", False),
                         "/user_avatars/hash.png?x=x")
        self.assertEqual(backend.get_avatar_url("hash", True),
                         "/user_avatars/hash-medium.png?x=x")
        self.assertEqual(backend.get_realm_icon_url(15, 1),
                         "/user_avatars/15/realm/icon.png?version=1")

        with self.settings(S3_AVATAR_BUCKET="bucket"):
            backend = S3UploadBackend()
            self.assertEqual(backend.get_avatar_url("hash", False),
                             "https://bucket.s3.amazonaws.com/hash?x=x")
            self.assertEqual(backend.get_avatar_url("hash", True),
                             "https://bucket.s3.amazonaws.com/hash-medium.png?x=x")
            self.assertEqual(backend.get_realm_icon_url(15, 1),
                             "https://bucket.s3.amazonaws.com/15/realm/icon.png?version=1")

    def test_multiple_upload_failure(self):
        # type: () -> None
        """
        Attempting to upload two files should fail.
        """
        self.login(self.example_email("hamlet"))
        with get_test_image_file('img.png') as fp1, \
                get_test_image_file('img.png') as fp2:
            result = self.client_post("/json/users/me/avatar", {'f1': fp1, 'f2': fp2})
        self.assert_json_error(result, "You must upload exactly one avatar.")

    def test_no_file_upload_failure(self):
        # type: () -> None
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
        ('img.tif', 'tif_resized.png')
    ]
    corrupt_files = ['text.txt', 'corrupt.png', 'corrupt.gif']

    def test_get_gravatar_avatar(self):
        # type: () -> None
        self.login(self.example_email("hamlet"))
        cordelia = self.example_user('cordelia')

        cordelia.avatar_source = UserProfile.AVATAR_FROM_GRAVATAR
        cordelia.save()
        with self.settings(ENABLE_GRAVATAR=True):
            response = self.client_get("/avatar/cordelia@zulip.com?foo=bar")
            redirect_url = response['Location']
            self.assertEqual(redirect_url, avatar_url(cordelia) + '&foo=bar')

        with self.settings(ENABLE_GRAVATAR=False):
            response = self.client_get("/avatar/cordelia@zulip.com?foo=bar")
            redirect_url = response['Location']
            self.assertTrue(redirect_url.endswith(avatar_url(cordelia) + '&foo=bar'))

    def test_get_user_avatar(self):
        # type: () -> None
        self.login(self.example_email("hamlet"))
        cordelia = self.example_user('cordelia')

        cordelia.avatar_source = UserProfile.AVATAR_FROM_USER
        cordelia.save()
        response = self.client_get("/avatar/cordelia@zulip.com?foo=bar")
        redirect_url = response['Location']
        self.assertTrue(redirect_url.endswith(avatar_url(cordelia) + '&foo=bar'))

        response = self.client_get("/avatar/%s?foo=bar" % (cordelia.id))
        redirect_url = response['Location']
        self.assertTrue(redirect_url.endswith(avatar_url(cordelia) + '&foo=bar'))

    def test_get_user_avatar_medium(self):
        # type: () -> None
        self.login(self.example_email("hamlet"))
        cordelia = self.example_user('cordelia')

        cordelia.avatar_source = UserProfile.AVATAR_FROM_USER
        cordelia.save()
        response = self.client_get("/avatar/cordelia@zulip.com/medium?foo=bar")
        redirect_url = response['Location']
        self.assertTrue(redirect_url.endswith(avatar_url(cordelia, True) + '&foo=bar'))

        response = self.client_get("/avatar/%s/medium?foo=bar" % (cordelia.id,))
        redirect_url = response['Location']
        self.assertTrue(redirect_url.endswith(avatar_url(cordelia, True) + '&foo=bar'))

    def test_non_valid_user_avatar(self):
        # type: () -> None

        # It's debatable whether we should generate avatars for non-users,
        # but this test just validates the current code's behavior.
        self.login(self.example_email("hamlet"))

        response = self.client_get("/avatar/nonexistent_user@zulip.com?foo=bar")
        redirect_url = response['Location']
        actual_url = 'https://secure.gravatar.com/avatar/444258b521f152129eb0c162996e572d?d=identicon&version=1&foo=bar'
        self.assertEqual(redirect_url, actual_url)

    def test_valid_avatars(self):
        # type: () -> None
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

            # Confirm that ensure_medium_avatar_url works to recreate
            # medium size avatars from the original if needed
            os.remove(medium_avatar_disk_path)
            self.assertFalse(os.path.exists(medium_avatar_disk_path))
            zerver.lib.upload.upload_backend.ensure_medium_avatar_image(user_profile)
            self.assertTrue(os.path.exists(medium_avatar_disk_path))

            # Verify whether the avatar_version gets incremented with every new upload
            self.assertEqual(user_profile.avatar_version, version)
            version += 1

    def test_invalid_avatars(self):
        # type: () -> None
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

    def test_delete_avatar(self):
        # type: () -> None
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

    def test_avatar_upload_file_size_error(self):
        # type: () -> None
        self.login(self.example_email("hamlet"))
        with get_test_image_file(self.correct_files[0][0]) as fp:
            with self.settings(MAX_AVATAR_FILE_SIZE=0):
                result = self.client_post("/json/users/me/avatar", {'file': fp})
        self.assert_json_error(result, "Uploaded file is larger than the allowed limit of 0 MB")

    def tearDown(self):
        # type: () -> None
        destroy_uploads()

class RealmIconTest(UploadSerializeMixin, ZulipTestCase):

    def test_multiple_upload_failure(self):
        # type: () -> None
        """
        Attempting to upload two files should fail.
        """
        # Log in as admin
        self.login(self.example_email("iago"))
        with get_test_image_file('img.png') as fp1, \
                get_test_image_file('img.png') as fp2:
            result = self.client_post("/json/realm/icon", {'f1': fp1, 'f2': fp2})
        self.assert_json_error(result, "You must upload exactly one icon.")

    def test_no_file_upload_failure(self):
        # type: () -> None
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
        ('img.tif', 'tif_resized.png')
    ]
    corrupt_files = ['text.txt', 'corrupt.png', 'corrupt.gif']

    def test_no_admin_user_upload(self):
        # type: () -> None
        self.login(self.example_email("hamlet"))
        with get_test_image_file(self.correct_files[0][0]) as fp:
            result = self.client_post("/json/realm/icon", {'file': fp})
        self.assert_json_error(result, 'Must be a realm administrator')

    def test_get_gravatar_icon(self):
        # type: () -> None
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

    def test_get_realm_icon(self):
        # type: () -> None
        self.login(self.example_email("hamlet"))

        realm = get_realm('zulip')
        realm.icon_source = Realm.ICON_UPLOADED
        realm.save()
        response = self.client_get("/json/realm/icon?foo=bar")
        redirect_url = response['Location']
        self.assertTrue(redirect_url.endswith(realm_icon_url(realm) + '&foo=bar'))

    def test_valid_icons(self):
        # type: () -> None
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

    def test_invalid_icons(self):
        # type: () -> None
        """
        A PUT request to /json/realm/icon with an invalid file should fail.
        """
        for fname in self.corrupt_files:
            # with self.subTest(fname=fname):
            self.login(self.example_email("iago"))
            with get_test_image_file(fname) as fp:
                result = self.client_post("/json/realm/icon", {'file': fp})

            self.assert_json_error(result, "Could not decode image; did you upload an image file?")

    def test_delete_icon(self):
        # type: () -> None
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

    def test_realm_icon_version(self):
        # type: () -> None
        self.login(self.example_email("iago"))
        realm = get_realm('zulip')
        icon_version = realm.icon_version
        self.assertEqual(icon_version, 1)
        with get_test_image_file(self.correct_files[0][0]) as fp:
            self.client_post("/json/realm/icon", {'file': fp})
        realm = get_realm('zulip')
        self.assertEqual(realm.icon_version, icon_version + 1)

    def test_realm_icon_upload_file_size_error(self):
        # type: () -> None
        self.login(self.example_email("iago"))
        with get_test_image_file(self.correct_files[0][0]) as fp:
            with self.settings(MAX_ICON_FILE_SIZE=0):
                result = self.client_post("/json/realm/icon", {'file': fp})
        self.assert_json_error(result, "Uploaded file is larger than the allowed limit of 0 MB")

    def tearDown(self):
        # type: () -> None
        destroy_uploads()

class LocalStorageTest(UploadSerializeMixin, ZulipTestCase):

    def test_file_upload_local(self):
        # type: () -> None
        user_profile = self.example_user('hamlet')
        uri = upload_message_image(u'dummy.txt', len(b'zulip!'), u'text/plain', b'zulip!', user_profile)

        base = '/user_uploads/'
        self.assertEqual(base, uri[:len(base)])
        path_id = re.sub('/user_uploads/', '', uri)
        file_path = os.path.join(settings.LOCAL_UPLOADS_DIR, 'files', path_id)
        self.assertTrue(os.path.isfile(file_path))

        uploaded_file = Attachment.objects.get(owner=user_profile, path_id=path_id)
        self.assertEqual(len(b'zulip!'), uploaded_file.size)

    def test_delete_message_image_local(self):
        # type: () -> None
        self.login(self.example_email("hamlet"))
        fp = StringIO("zulip!")
        fp.name = "zulip.txt"
        result = self.client_post("/json/user_uploads", {'file': fp})

        path_id = re.sub('/user_uploads/', '', result.json()['uri'])
        self.assertTrue(delete_message_image(path_id))

    def tearDown(self):
        # type: () -> None
        destroy_uploads()

FuncT = TypeVar('FuncT', bound=Callable[..., None])

def use_s3_backend(method):
    # type: (FuncT) -> FuncT
    @mock_s3_deprecated
    @override_settings(LOCAL_UPLOADS_DIR=None)
    def new_method(*args, **kwargs):
        # type: (*Any, **Any) -> Any
        zerver.lib.upload.upload_backend = S3UploadBackend()
        try:
            return method(*args, **kwargs)
        finally:
            zerver.lib.upload.upload_backend = LocalUploadBackend()
    return new_method

class S3Test(ZulipTestCase):

    @use_s3_backend
    def test_file_upload_s3(self):
        # type: () -> None
        conn = S3Connection(settings.S3_KEY, settings.S3_SECRET_KEY)
        bucket = conn.create_bucket(settings.S3_AUTH_UPLOADS_BUCKET)

        user_profile = self.example_user('hamlet')
        uri = upload_message_image(u'dummy.txt', len(b'zulip!'), u'text/plain', b'zulip!', user_profile)

        base = '/user_uploads/'
        self.assertEqual(base, uri[:len(base)])
        path_id = re.sub('/user_uploads/', '', uri)
        content = bucket.get_key(path_id).get_contents_as_string()
        self.assertEqual(b"zulip!", content)

        uploaded_file = Attachment.objects.get(owner=user_profile, path_id=path_id)
        self.assertEqual(len(b"zulip!"), uploaded_file.size)

        self.subscribe(self.example_user("hamlet"), "Denmark")
        body = "First message ...[zulip.txt](http://localhost:9991" + uri + ")"
        self.send_message(self.example_email("hamlet"), "Denmark", Recipient.STREAM, body, "test")
        self.assertIn('title="dummy.txt"', self.get_last_message().rendered_content)

    @use_s3_backend
    def test_message_image_delete_s3(self):
        # type: () -> None
        conn = S3Connection(settings.S3_KEY, settings.S3_SECRET_KEY)
        conn.create_bucket(settings.S3_AUTH_UPLOADS_BUCKET)

        user_profile = self.example_user('hamlet')
        uri = upload_message_image(u'dummy.txt', len(b'zulip!'), u'text/plain', b'zulip!', user_profile)

        path_id = re.sub('/user_uploads/', '', uri)
        self.assertTrue(delete_message_image(path_id))

    @use_s3_backend
    def test_file_upload_authed(self):
        # type: () -> None
        """
        A call to /json/user_uploads should return a uri and actually create an object.
        """
        conn = S3Connection(settings.S3_KEY, settings.S3_SECRET_KEY)
        conn.create_bucket(settings.S3_AUTH_UPLOADS_BUCKET)

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
        self.send_message(self.example_email("hamlet"), "Denmark", Recipient.STREAM, body, "test")
        self.assertIn('title="zulip.txt"', self.get_last_message().rendered_content)

class UploadTitleTests(TestCase):
    def test_upload_titles(self):
        # type: () -> None
        self.assertEqual(url_filename("http://localhost:9991/user_uploads/1/LUeQZUG5jxkagzVzp1Ox_amr/dummy.txt"), "dummy.txt")
        self.assertEqual(url_filename("http://localhost:9991/user_uploads/1/94/SzGYe0RFT-tEcOhQ6n-ZblFZ/zulip.txt"), "zulip.txt")
        self.assertEqual(url_filename("https://zulip.com/user_uploads/4142/LUeQZUG5jxkagzVzp1Ox_amr/pasted_image.png"), "pasted_image.png")
        self.assertEqual(url_filename("https://zulipchat.com/integrations"), "https://zulipchat.com/integrations")
        self.assertEqual(url_filename("https://example.com"), "https://example.com")

class SanitizeNameTests(TestCase):
    def test_file_name(self):
        # type: () -> None
        self.assertEqual(sanitize_name(u'test.txt'), u'test.txt')
        self.assertEqual(sanitize_name(u'.hidden'), u'.hidden')
        self.assertEqual(sanitize_name(u'.hidden.txt'), u'.hidden.txt')
        self.assertEqual(sanitize_name(u'tarball.tar.gz'), u'tarball.tar.gz')
        self.assertEqual(sanitize_name(u'.hidden_tarball.tar.gz'), u'.hidden_tarball.tar.gz')
        self.assertEqual(sanitize_name(u'Testing{}*&*#().ta&&%$##&&r.gz'), u'Testing.tar.gz')
        self.assertEqual(sanitize_name(u'*testingfile?*.txt'), u'testingfile.txt')
        self.assertEqual(sanitize_name(u'snowman☃.txt'), u'snowman.txt')
        self.assertEqual(sanitize_name(u'테스트.txt'), u'테스트.txt')
        self.assertEqual(sanitize_name(u'~/."\`\?*"u0`000ssh/test.t**{}ar.gz'), u'.u0000sshtest.tar.gz')
