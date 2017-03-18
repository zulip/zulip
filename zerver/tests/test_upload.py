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
    upload_message_image, delete_message_image, LocalUploadBackend
import zerver.lib.upload
from zerver.models import Attachment, Recipient, get_user_profile_by_email, \
    get_old_unclaimed_attachments, Message, UserProfile, Realm, get_realm
from zerver.lib.actions import do_delete_old_unclaimed_attachments

from zerver.views.upload import upload_file_backend

import ujson
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
from django.utils import timezone

from moto import mock_s3

from typing import Any, Callable, TypeVar, Text

def destroy_uploads():
    # type: () -> None
    if os.path.exists(settings.LOCAL_UPLOADS_DIR):
        shutil.rmtree(settings.LOCAL_UPLOADS_DIR)

class StringIO(_StringIO):
    name = '' # https://github.com/python/typeshed/issues/598

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
        auth_headers = self.api_auth('hamlet@zulip.com')
        result = self.client_post('/api/v1/user_uploads', {'file': fp}, **auth_headers)
        json = ujson.loads(result.content)
        self.assertIn("uri", json)
        uri = json["uri"]
        base = '/user_uploads/'
        self.assertEqual(base, uri[:len(base)])

        # Download file via API
        self.client_post('/accounts/logout/')
        response = self.client_get(uri, **auth_headers)
        data = b"".join(response.streaming_content)
        self.assertEqual(b"zulip!", data)

        # Files uploaded through the API should be accesible via the web client
        self.login("hamlet@zulip.com")
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

        user_profile = get_user_profile_by_email('hamlet@zulip.com')

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
        mock_filename = mock.Mock(spec=None) # None is not str
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
        self.login("hamlet@zulip.com")
        fp = StringIO("bah!")
        fp.name = "a.txt"

        # Use MAX_FILE_UPLOAD_SIZE of 0, because the next increment
        # would be 1MB.
        with self.settings(MAX_FILE_UPLOAD_SIZE=0):
            result = self.client_post("/json/upload_file", {'f1': fp})
        self.assert_json_error(result, 'Uploaded file is larger than the allowed limit of 0 MB')

    def test_multiple_upload_failure(self):
        # type: () -> None
        """
        Attempting to upload two files should fail.
        """
        self.login("hamlet@zulip.com")
        fp = StringIO("bah!")
        fp.name = "a.txt"
        fp2 = StringIO("pshaw!")
        fp2.name = "b.txt"

        result = self.client_post("/json/upload_file", {'f1': fp, 'f2': fp2})
        self.assert_json_error(result, "You may only upload one file at a time")

    def test_no_file_upload_failure(self):
        # type: () -> None
        """
        Calling this endpoint with no files should fail.
        """
        self.login("hamlet@zulip.com")

        result = self.client_post("/json/upload_file")
        self.assert_json_error(result, "You must specify a file to upload")

    def test_download_non_existent_file(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        response = self.client_get('/user_uploads/unk/nonexistent_file')
        self.assertEqual(response.status_code, 404)
        self.assertIn('File not found', str(response.content))

    def test_serve_s3_error_handling(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        use_s3 = lambda: self.settings(LOCAL_UPLOADS_DIR=None)
        getting_realm_id = lambda realm_id: mock.patch(
            'zerver.views.upload.get_realm_for_filename',
            return_value=realm_id
        )

        # nonexistent_file
        with use_s3(), getting_realm_id(None):
            response = self.client_get('/user_uploads/unk/nonexistent_file')
        self.assertEqual(response.status_code, 404)
        self.assertIn('File not found', str(response.content))

        # invalid realm of 999999 (for non-zulip.com)
        user = get_user_profile_by_email('hamlet@zulip.com')
        user.realm.string_id = 'not-zulip'
        user.realm.save()

        with use_s3(), getting_realm_id(999999):
            response = self.client_get('/user_uploads/unk/whatever')
        self.assertEqual(response.status_code, 403)

    # This test will go through the code path for uploading files onto LOCAL storage
    # when zulip is in DEVELOPMENT mode.
    def test_file_upload_authed(self):
        # type: () -> None
        """
        A call to /json/upload_file should return a uri and actually create an
        entry in the database. This entry will be marked unclaimed till a message
        refers it.
        """
        self.login("hamlet@zulip.com")
        fp = StringIO("zulip!")
        fp.name = "zulip.txt"

        result = self.client_post("/json/upload_file", {'file': fp})
        self.assert_json_success(result)
        json = ujson.loads(result.content)
        self.assertIn("uri", json)
        uri = json["uri"]
        base = '/user_uploads/'
        self.assertEqual(base, uri[:len(base)])

        # In the future, local file requests will follow the same style as S3
        # requests; they will be first authenthicated and redirected
        self.assert_url_serves_contents_of_file(uri, b"zulip!")

        # check if DB has attachment marked as unclaimed
        entry = Attachment.objects.get(file_name='zulip.txt')
        self.assertEqual(entry.is_claimed(), False)

        self.subscribe_to_stream("hamlet@zulip.com", "Denmark")
        body = "First message ...[zulip.txt](http://localhost:9991" + uri + ")"
        self.send_message("hamlet@zulip.com", "Denmark", Recipient.STREAM, body, "test")
        self.assertIn('title="zulip.txt"', self.get_last_message().rendered_content)

    def test_delete_old_unclaimed_attachments(self):
        # type: () -> None

        # Upload some files and make them older than a weeek
        self.login("hamlet@zulip.com")
        d1 = StringIO("zulip!")
        d1.name = "dummy_1.txt"
        result = self.client_post("/json/upload_file", {'file': d1})
        json = ujson.loads(result.content)
        uri = json["uri"]
        d1_path_id = re.sub('/user_uploads/', '', uri)

        d2 = StringIO("zulip!")
        d2.name = "dummy_2.txt"
        result = self.client_post("/json/upload_file", {'file': d2})
        json = ujson.loads(result.content)
        uri = json["uri"]
        d2_path_id = re.sub('/user_uploads/', '', uri)

        two_week_ago = timezone.now() - datetime.timedelta(weeks=2)
        d1_attachment = Attachment.objects.get(path_id = d1_path_id)
        d1_attachment.create_time = two_week_ago
        d1_attachment.save()
        self.assertEqual(str(d1_attachment), u'<Attachment: dummy_1.txt>')
        d2_attachment = Attachment.objects.get(path_id = d2_path_id)
        d2_attachment.create_time = two_week_ago
        d2_attachment.save()

        # Send message refering only dummy_1
        self.subscribe_to_stream("hamlet@zulip.com", "Denmark")
        body = "Some files here ...[zulip.txt](http://localhost:9991/user_uploads/" + d1_path_id + ")"
        self.send_message("hamlet@zulip.com", "Denmark", Recipient.STREAM, body, "test")

        # dummy_2 should not exist in database or the uploads folder
        do_delete_old_unclaimed_attachments(2)
        self.assertTrue(not Attachment.objects.filter(path_id = d2_path_id).exists())
        self.assertTrue(not delete_message_image(d2_path_id))

    def test_multiple_claim_attachments(self):
        # type: () -> None
        """
        This test tries to claim the same attachment twice. The messages field in
        the Attachment model should have both the messages in its entry.
        """
        self.login("hamlet@zulip.com")
        d1 = StringIO("zulip!")
        d1.name = "dummy_1.txt"
        result = self.client_post("/json/upload_file", {'file': d1})
        json = ujson.loads(result.content)
        uri = json["uri"]
        d1_path_id = re.sub('/user_uploads/', '', uri)

        self.subscribe_to_stream("hamlet@zulip.com", "Denmark")
        body = "First message ...[zulip.txt](http://localhost:9991/user_uploads/" + d1_path_id + ")"
        self.send_message("hamlet@zulip.com", "Denmark", Recipient.STREAM, body, "test")
        body = "Second message ...[zulip.txt](http://localhost:9991/user_uploads/" + d1_path_id + ")"
        self.send_message("hamlet@zulip.com", "Denmark", Recipient.STREAM, body, "test")

        self.assertEqual(Attachment.objects.get(path_id=d1_path_id).messages.count(), 2)

    def test_check_attachment_reference_update(self):
        # type: () -> None
        f1 = StringIO("file1")
        f1.name = "file1.txt"
        f2 = StringIO("file2")
        f2.name = "file2.txt"
        f3 = StringIO("file3")
        f3.name = "file3.txt"

        self.login("hamlet@zulip.com")
        result = self.client_post("/json/upload_file", {'file': f1})
        json = ujson.loads(result.content)
        uri = json["uri"]
        f1_path_id = re.sub('/user_uploads/', '', uri)

        result = self.client_post("/json/upload_file", {'file': f2})
        json = ujson.loads(result.content)
        uri = json["uri"]
        f2_path_id = re.sub('/user_uploads/', '', uri)

        self.subscribe_to_stream("hamlet@zulip.com", "test")
        body = ("[f1.txt](http://localhost:9991/user_uploads/" + f1_path_id + ")"
                "[f2.txt](http://localhost:9991/user_uploads/" + f2_path_id + ")")
        msg_id = self.send_message("hamlet@zulip.com", "test", Recipient.STREAM, body, "test")

        result = self.client_post("/json/upload_file", {'file': f3})
        json = ujson.loads(result.content)
        uri = json["uri"]
        f3_path_id = re.sub('/user_uploads/', '', uri)

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
        self.login("hamlet@zulip.com")
        for expected in ["Здравейте.txt", "test"]:
            fp = StringIO("bah!")
            fp.name = urllib.parse.quote(expected)

            result = self.client_post("/json/upload_file", {'f1': fp})
            content = ujson.loads(result.content)
            assert sanitize_name(expected) in content['uri']

    def test_upload_size_quote(self):
        # type: () -> None
        """
        User quote for uploading should not be exceeded
        """
        self.login("hamlet@zulip.com")

        d1 = StringIO("zulip!")
        d1.name = "dummy_1.txt"
        result = self.client_post("/json/upload_file", {'file': d1})
        json = ujson.loads(result.content)
        uri = json["uri"]
        d1_path_id = re.sub('/user_uploads/', '', uri)
        d1_attachment = Attachment.objects.get(path_id = d1_path_id)
        self.assert_json_success(result)

        """
        Below we set size quota to the limit without 1 upload(1GB - 11 bytes).
        """
        d1_attachment.size = UserProfile.DEFAULT_UPLOADS_QUOTA - 11
        d1_attachment.save()

        d2 = StringIO("zulip!")
        d2.name = "dummy_2.txt"
        result = self.client_post("/json/upload_file", {'file': d2})
        self.assert_json_success(result)

        d3 = StringIO("zulip!")
        d3.name = "dummy_3.txt"
        result = self.client_post("/json/upload_file", {'file': d3})
        self.assert_json_error(result, "Upload would exceed your maximum quota.")

    def tearDown(self):
        # type: () -> None
        destroy_uploads()

class AvatarTest(UploadSerializeMixin, ZulipTestCase):

    def test_multiple_upload_failure(self):
        # type: () -> None
        """
        Attempting to upload two files should fail.
        """
        self.login("hamlet@zulip.com")
        with get_test_image_file('img.png') as fp1, \
                get_test_image_file('img.png') as fp2:
            result = self.client_put_multipart("/json/users/me/avatar", {'f1': fp1, 'f2': fp2})
        self.assert_json_error(result, "You must upload exactly one avatar.")

    def test_no_file_upload_failure(self):
        # type: () -> None
        """
        Calling this endpoint with no files should fail.
        """
        self.login("hamlet@zulip.com")

        result = self.client_put_multipart("/json/users/me/avatar")
        self.assert_json_error(result, "You must upload exactly one avatar.")

    correct_files = [
        ('img.png', 'png_resized.png'),
        ('img.jpg', None), # jpeg resizing is platform-dependent
        ('img.gif', 'gif_resized.png'),
        ('img.tif', 'tif_resized.png')
    ]
    corrupt_files = ['text.txt', 'corrupt.png', 'corrupt.gif']

    def test_get_gravatar_avatar(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        cordelia = get_user_profile_by_email('cordelia@zulip.com')

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
        self.login("hamlet@zulip.com")
        cordelia = get_user_profile_by_email('cordelia@zulip.com')

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
        self.login("hamlet@zulip.com")
        cordelia = get_user_profile_by_email('cordelia@zulip.com')

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
        self.login("hamlet@zulip.com")

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
            self.login("hamlet@zulip.com")
            with get_test_image_file(fname) as fp:
                result = self.client_put_multipart("/json/users/me/avatar", {'file': fp})

            self.assert_json_success(result)
            json = ujson.loads(result.content)
            self.assertIn("avatar_url", json)
            url = json["avatar_url"]
            base = '/user_avatars/'
            self.assertEqual(base, url[:len(base)])

            if rfname is not None:
                response = self.client_get(url)
                data = b"".join(response.streaming_content)
                self.assertEqual(Image.open(io.BytesIO(data)).size, (100, 100))

            # Verify that the medium-size avatar was created
            user_profile = get_user_profile_by_email('hamlet@zulip.com')
            medium_avatar_disk_path = avatar_disk_path(user_profile, medium=True)
            self.assertTrue(os.path.exists(medium_avatar_disk_path))

            # Confirm that ensure_medium_avatar_url works to recreate
            # medium size avatars from the original if needed
            os.remove(medium_avatar_disk_path)
            self.assertFalse(os.path.exists(medium_avatar_disk_path))
            zerver.lib.upload.upload_backend.ensure_medium_avatar_image(user_profile.email)
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
            self.login("hamlet@zulip.com")
            with get_test_image_file(fname) as fp:
                result = self.client_put_multipart("/json/users/me/avatar", {'file': fp})

            self.assert_json_error(result, "Could not decode image; did you upload an image file?")
            user_profile = get_user_profile_by_email("hamlet@zulip.com")
            self.assertEqual(user_profile.avatar_version, 1)

    def test_delete_avatar(self):
        # type: () -> None
        """
        A DELETE request to /json/users/me/avatar should delete the user avatar and return gravatar URL
        """
        self.login("hamlet@zulip.com")
        hamlet = get_user_profile_by_email("hamlet@zulip.com")
        hamlet.avatar_source = UserProfile.AVATAR_FROM_USER
        hamlet.save()

        result = self.client_delete("/json/users/me/avatar")
        user_profile = get_user_profile_by_email('hamlet@zulip.com')

        self.assert_json_success(result)
        json = ujson.loads(result.content)
        self.assertIn("avatar_url", json)
        self.assertEqual(json["avatar_url"], avatar_url(user_profile))

        self.assertEqual(user_profile.avatar_source, UserProfile.AVATAR_FROM_GRAVATAR)
        self.assertEqual(user_profile.avatar_version, 2)

    def test_avatar_upload_file_size_error(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        with get_test_image_file(self.correct_files[0][0]) as fp:
            with self.settings(MAX_AVATAR_FILE_SIZE=0):
                result = self.client_put_multipart("/json/users/me/avatar", {'file': fp})
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
        self.login("iago@zulip.com")
        with get_test_image_file('img.png') as fp1, \
                get_test_image_file('img.png') as fp2:
            result = self.client_put_multipart("/json/realm/icon", {'f1': fp1, 'f2': fp2})
        self.assert_json_error(result, "You must upload exactly one icon.")

    def test_no_file_upload_failure(self):
        # type: () -> None
        """
        Calling this endpoint with no files should fail.
        """
        self.login("iago@zulip.com")

        result = self.client_put_multipart("/json/realm/icon")
        self.assert_json_error(result, "You must upload exactly one icon.")

    correct_files = [
        ('img.png', 'png_resized.png'),
        ('img.jpg', None), # jpeg resizing is platform-dependent
        ('img.gif', 'gif_resized.png'),
        ('img.tif', 'tif_resized.png')
    ]
    corrupt_files = ['text.txt', 'corrupt.png', 'corrupt.gif']

    def test_no_admin_user_upload(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        with get_test_image_file(self.correct_files[0][0]) as fp:
            result = self.client_put_multipart("/json/realm/icon", {'file': fp})
        self.assert_json_error(result, 'Must be a realm administrator')

    def test_get_gravatar_icon(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
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
        self.login("hamlet@zulip.com")

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
            self.login("iago@zulip.com")
            with get_test_image_file(fname) as fp:
                result = self.client_put_multipart("/json/realm/icon", {'file': fp})
            realm = get_realm('zulip')
            self.assert_json_success(result)
            json = ujson.loads(result.content)
            self.assertIn("icon_url", json)
            url = json["icon_url"]
            base = '/user_avatars/%s/realm/icon.png' % (realm.id,)
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
            self.login("iago@zulip.com")
            with get_test_image_file(fname) as fp:
                result = self.client_put_multipart("/json/realm/icon", {'file': fp})

            self.assert_json_error(result, "Could not decode image; did you upload an image file?")

    def test_delete_icon(self):
        # type: () -> None
        """
        A DELETE request to /json/realm/icon should delete the realm icon and return gravatar URL
        """
        self.login("iago@zulip.com")
        realm = get_realm('zulip')
        realm.icon_source = Realm.ICON_UPLOADED
        realm.save()

        result = self.client_delete("/json/realm/icon")

        self.assert_json_success(result)
        json = ujson.loads(result.content)
        self.assertIn("icon_url", json)
        realm = get_realm('zulip')
        self.assertEqual(json["icon_url"], realm_icon_url(realm))
        self.assertEqual(realm.icon_source, Realm.ICON_FROM_GRAVATAR)

    def test_realm_icon_version(self):
        # type: () -> None
        self.login("iago@zulip.com")
        realm = get_realm('zulip')
        icon_version = realm.icon_version
        self.assertEqual(icon_version, 1)
        with get_test_image_file(self.correct_files[0][0]) as fp:
            self.client_put_multipart("/json/realm/icon", {'file': fp})
        realm = get_realm('zulip')
        self.assertEqual(realm.icon_version, icon_version + 1)

    def test_realm_icon_upload_file_size_error(self):
        # type: () -> None
        self.login("iago@zulip.com")
        with get_test_image_file(self.correct_files[0][0]) as fp:
            with self.settings(MAX_ICON_FILE_SIZE=0):
                result = self.client_put_multipart("/json/realm/icon", {'file': fp})
        self.assert_json_error(result, "Uploaded file is larger than the allowed limit of 0 MB")

    def tearDown(self):
        # type: () -> None
        destroy_uploads()

class LocalStorageTest(UploadSerializeMixin, ZulipTestCase):

    def test_file_upload_local(self):
        # type: () -> None
        sender_email = "hamlet@zulip.com"
        user_profile = get_user_profile_by_email(sender_email)
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
        self.login("hamlet@zulip.com")
        fp = StringIO("zulip!")
        fp.name = "zulip.txt"
        result = self.client_post("/json/upload_file", {'file': fp})

        json = ujson.loads(result.content)
        uri = json["uri"]
        path_id = re.sub('/user_uploads/', '', uri)
        self.assertTrue(delete_message_image(path_id))

    def tearDown(self):
        # type: () -> None
        destroy_uploads()

FuncT = TypeVar('FuncT', bound=Callable[..., None])

def use_s3_backend(method):
    # type: (FuncT) -> FuncT
    @mock_s3
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

        sender_email = "hamlet@zulip.com"
        user_profile = get_user_profile_by_email(sender_email)
        uri = upload_message_image(u'dummy.txt', len(b'zulip!'), u'text/plain', b'zulip!', user_profile)

        base = '/user_uploads/'
        self.assertEqual(base, uri[:len(base)])
        path_id = re.sub('/user_uploads/', '', uri)
        content = bucket.get_key(path_id).get_contents_as_string()
        self.assertEqual(b"zulip!", content)

        uploaded_file = Attachment.objects.get(owner=user_profile, path_id=path_id)
        self.assertEqual(len(b"zulip!"), uploaded_file.size)

        self.subscribe_to_stream("hamlet@zulip.com", "Denmark")
        body = "First message ...[zulip.txt](http://localhost:9991" + uri + ")"
        self.send_message("hamlet@zulip.com", "Denmark", Recipient.STREAM, body, "test")
        self.assertIn('title="dummy.txt"', self.get_last_message().rendered_content)

    @use_s3_backend
    def test_message_image_delete_s3(self):
        # type: () -> None
        conn = S3Connection(settings.S3_KEY, settings.S3_SECRET_KEY)
        conn.create_bucket(settings.S3_AUTH_UPLOADS_BUCKET)

        sender_email = "hamlet@zulip.com"
        user_profile = get_user_profile_by_email(sender_email)
        uri = upload_message_image(u'dummy.txt', len(b'zulip!'), u'text/plain', b'zulip!', user_profile)

        path_id = re.sub('/user_uploads/', '', uri)
        self.assertTrue(delete_message_image(path_id))

    @use_s3_backend
    def test_file_upload_authed(self):
        # type: () -> None
        """
        A call to /json/upload_file should return a uri and actually create an object.
        """
        conn = S3Connection(settings.S3_KEY, settings.S3_SECRET_KEY)
        conn.create_bucket(settings.S3_AUTH_UPLOADS_BUCKET)

        self.login("hamlet@zulip.com")
        fp = StringIO("zulip!")
        fp.name = "zulip.txt"

        result = self.client_post("/json/upload_file", {'file': fp})
        self.assert_json_success(result)
        json = ujson.loads(result.content)
        self.assertIn("uri", json)
        uri = json["uri"]
        base = '/user_uploads/'
        self.assertEqual(base, uri[:len(base)])

        response = self.client_get(uri)
        redirect_url = response['Location']

        self.assertEqual(b"zulip!", urllib.request.urlopen(redirect_url).read().strip()) # type: ignore # six.moves.urllib.request.urlopen is not defined in typeshed

        self.subscribe_to_stream("hamlet@zulip.com", "Denmark")
        body = "First message ...[zulip.txt](http://localhost:9991" + uri + ")"
        self.send_message("hamlet@zulip.com", "Denmark", Recipient.STREAM, body, "test")
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
