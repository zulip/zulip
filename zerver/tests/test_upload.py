# -*- coding: utf-8 -*-
from __future__ import absolute_import
from django.conf import settings
from django.test import TestCase, override_settings
from unittest import skip

from zerver.lib.avatar import avatar_url
from zerver.lib.bugdown import url_filename
from zerver.lib.test_helpers import ZulipTestCase
from zerver.lib.test_runner import slow
from zerver.lib.upload import sanitize_name, S3UploadBackend, \
    upload_message_image, delete_message_image, LocalUploadBackend
import zerver.lib.upload
from zerver.models import Attachment, Recipient, get_user_profile_by_email, \
    get_old_unclaimed_attachments, Message, UserProfile
from zerver.lib.actions import do_delete_old_unclaimed_attachments

import ujson
from six.moves import urllib

from boto.s3.connection import S3Connection
from boto.s3.key import Key
from six.moves import StringIO
import os
import shutil
import re
import datetime
import requests
import base64
from datetime import timedelta
from django.utils import timezone

from moto import mock_s3

TEST_AVATAR_DIR = os.path.join(os.path.dirname(__file__), 'images')

def destroy_uploads():
    # type: () -> None
    if os.path.exists(settings.LOCAL_UPLOADS_DIR):
        shutil.rmtree(settings.LOCAL_UPLOADS_DIR)

class FileUploadTest(ZulipTestCase):

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
        self.assertEquals(base, uri[:len(base)])

        # Download file via API
        self.client_post('/accounts/logout/')
        response = self.client_get(uri, **auth_headers)
        data = b"".join(response.streaming_content)
        self.assertEquals(b"zulip!", data)

        # Files uploaded through the API should be accesible via the web client
        self.login("hamlet@zulip.com")
        response = self.client_get(uri)
        data = b"".join(response.streaming_content)
        self.assertEquals(b"zulip!", data)

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
        self.assertEquals(base, uri[:len(base)])

        # In the future, local file requests will follow the same style as S3
        # requests; they will be first authenthicated and redirected
        response = self.client_get(uri)
        data = b"".join(response.streaming_content)
        self.assertEquals(b"zulip!", data)

        # check if DB has attachment marked as unclaimed
        entry = Attachment.objects.get(file_name='zulip.txt')
        self.assertEquals(entry.is_claimed(), False)

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

        self.assertEquals(Attachment.objects.get(path_id=d1_path_id).messages.count(), 2)

    def test_check_attachment_reference_update(self):
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
        result = self.client_post("/json/update_message", {
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
        result = self.client_post("/json/update_message", {
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

    def tearDown(self):
        # type: () -> None
        destroy_uploads()

class AvatarTest(ZulipTestCase):

    def test_multiple_upload_failure(self):
        # type: () -> None
        """
        Attempting to upload two files should fail.
        """
        self.login("hamlet@zulip.com")
        fp1 = open(os.path.join(TEST_AVATAR_DIR, 'img.png'), 'rb')
        fp2 = open(os.path.join(TEST_AVATAR_DIR, 'img.png'), 'rb')

        result = self.client_post("/json/set_avatar", {'f1': fp1, 'f2': fp2})
        self.assert_json_error(result, "You must upload exactly one avatar.")

    def test_no_file_upload_failure(self):
        # type: () -> None
        """
        Calling this endpoint with no files should fail.
        """
        self.login("hamlet@zulip.com")

        result = self.client_post("/json/set_avatar")
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

    def test_get_system_generated_avatar(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        cordelia = get_user_profile_by_email('cordelia@zulip.com')

        cordelia.avatar_source = UserProfile.AVATAR_FROM_SYSTEM
        cordelia.save()
        response = self.client_get("/avatar/cordelia@zulip.com?foo=bar")
        redirect_url = response['Location']
        self.assertTrue(redirect_url.endswith(avatar_url(cordelia) + '&foo=bar'))

    def test_non_valid_user_avatar(self):
        # type: () -> None

        # It's debatable whether we should generate avatars for non-users,
        # but this test just validates the current code's behavior.
        self.login("hamlet@zulip.com")

        response = self.client_get("/avatar/nonexistent_user@zulip.com?foo=bar")
        redirect_url = response['Location']
        actual_url = 'https://secure.gravatar.com/avatar/444258b521f152129eb0c162996e572d?d=identicon&foo=bar'
        self.assertEqual(redirect_url, actual_url)

    def test_valid_avatars(self):
        # type: () -> None
        """
        A call to /json/set_avatar with a valid file should return a url and actually create an avatar.
        """
        for fname, rfname in self.correct_files:
            # TODO: use self.subTest once we're exclusively on python 3 by uncommenting the line below.
            # with self.subTest(fname=fname):
            self.login("hamlet@zulip.com")
            fp = open(os.path.join(TEST_AVATAR_DIR, fname), 'rb')

            result = self.client_post("/json/set_avatar", {'file': fp})
            self.assert_json_success(result)
            json = ujson.loads(result.content)
            self.assertIn("avatar_url", json)
            url = json["avatar_url"]
            base = '/user_avatars/'
            self.assertEquals(base, url[:len(base)])

            if rfname is not None:
                rfp = open(os.path.join(TEST_AVATAR_DIR, rfname), 'rb')
                response = self.client_get(url)
                data = b"".join(response.streaming_content)
                self.assertEquals(rfp.read(), data)

    def test_invalid_avatars(self):
        # type: () -> None
        """
        A call to /json/set_avatar with an invalid file should fail.
        """
        for fname in self.corrupt_files:
            # with self.subTest(fname=fname):
            self.login("hamlet@zulip.com")
            fp = open(os.path.join(TEST_AVATAR_DIR, fname), 'rb')

            result = self.client_post("/json/set_avatar", {'file': fp})
            self.assert_json_error(result, "Could not decode avatar image; did you upload an image file?")

    def tearDown(self):
        # type: () -> None
        destroy_uploads()

class LocalStorageTest(ZulipTestCase):

    def test_file_upload_local(self):
        # type: () -> None
        sender_email = "hamlet@zulip.com"
        user_profile = get_user_profile_by_email(sender_email)
        uri = upload_message_image(u'dummy.txt', u'text/plain', b'zulip!', user_profile)

        base = '/user_uploads/'
        self.assertEquals(base, uri[:len(base)])
        path_id = re.sub('/user_uploads/', '', uri)
        file_path = os.path.join(settings.LOCAL_UPLOADS_DIR, 'files', path_id)
        self.assertTrue(os.path.isfile(file_path))

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

def use_s3_backend(method):
    @mock_s3
    @override_settings(LOCAL_UPLOADS_DIR=None)
    def new_method(*args, **kwargs):
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
        uri = upload_message_image(u'dummy.txt', u'text/plain', b'zulip!', user_profile)

        base = '/user_uploads/'
        self.assertEquals(base, uri[:len(base)])
        path_id = re.sub('/user_uploads/', '', uri)
        self.assertEquals(b"zulip!", bucket.get_key(path_id).get_contents_as_string())

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
        uri = upload_message_image(u'dummy.txt', u'text/plain', b'zulip!', user_profile)

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
        self.assertEquals(base, uri[:len(base)])

        response = self.client_get(uri)
        redirect_url = response['Location']

        self.assertEquals(b"zulip!", urllib.request.urlopen(redirect_url).read().strip())

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
        self.assertEquals(sanitize_name(u'test.txt'), u'test.txt')
        self.assertEquals(sanitize_name(u'.hidden'), u'.hidden')
        self.assertEquals(sanitize_name(u'.hidden.txt'), u'.hidden.txt')
        self.assertEquals(sanitize_name(u'tarball.tar.gz'), u'tarball.tar.gz')
        self.assertEquals(sanitize_name(u'.hidden_tarball.tar.gz'), u'.hidden_tarball.tar.gz')
        self.assertEquals(sanitize_name(u'Testing{}*&*#().ta&&%$##&&r.gz'), u'Testing.tar.gz')
        self.assertEquals(sanitize_name(u'*testingfile?*.txt'), u'testingfile.txt')
        self.assertEquals(sanitize_name(u'snowman☃.txt'), u'snowman.txt')
        self.assertEquals(sanitize_name(u'테스트.txt'), u'테스트.txt')
        self.assertEquals(sanitize_name(u'~/."\`\?*"u0`000ssh/test.t**{}ar.gz'), u'.u0000sshtest.tar.gz')
