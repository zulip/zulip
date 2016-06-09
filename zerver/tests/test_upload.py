# -*- coding: utf-8 -*-
from __future__ import absolute_import
from django.conf import settings
from django.test import TestCase, override_settings
from unittest import skip

from zerver.lib.test_helpers import AuthedTestCase
from zerver.lib.test_runner import slow
from zerver.lib.upload import sanitize_name, S3UploadBackend, \
    upload_message_image, delete_message_image, LocalUploadBackend
import zerver.lib.upload
from zerver.models import Attachment, Recipient, get_user_profile_by_email, \
    get_old_unclaimed_attachments
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
from datetime import timedelta
from django.utils import timezone

from moto import mock_s3

TEST_AVATAR_DIR = os.path.join(os.path.dirname(__file__), 'images')

def destroy_uploads():
    # type: () -> None
    if os.path.exists(settings.LOCAL_UPLOADS_DIR):
        shutil.rmtree(settings.LOCAL_UPLOADS_DIR)

class FileUploadTest(AuthedTestCase):
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

        result = self.client.post("/json/upload_file", {'f1': fp, 'f2': fp2})
        self.assert_json_error(result, "You may only upload one file at a time")

    def test_no_file_upload_failure(self):
        # type: () -> None
        """
        Calling this endpoint with no files should fail.
        """
        self.login("hamlet@zulip.com")

        result = self.client.post("/json/upload_file")
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

        result = self.client.post("/json/upload_file", {'file': fp})
        self.assert_json_success(result)
        json = ujson.loads(result.content)
        self.assertIn("uri", json)
        uri = json["uri"]
        base = '/user_uploads/'
        self.assertEquals(base, uri[:len(base)])

        # In the future, local file requests will follow the same style as S3
        # requests; they will be first authenthicated and redirected
        response = self.client.get(uri)
        data = "".join(response.streaming_content)
        self.assertEquals("zulip!", data)

        # check if DB has attachment marked as unclaimed
        entry = Attachment.objects.get(file_name='zulip.txt')
        self.assertEquals(entry.is_claimed(), False)

    def test_delete_old_unclaimed_attachments(self):
        # type: () -> None

        # Upload some files and make them older than a weeek
        self.login("hamlet@zulip.com")
        d1 = StringIO("zulip!")
        d1.name = "dummy_1.txt"
        result = self.client.post("/json/upload_file", {'file': d1})
        json = ujson.loads(result.content)
        uri = json["uri"]
        d1_path_id = re.sub('/user_uploads/', '', uri)

        d2 = StringIO("zulip!")
        d2.name = "dummy_2.txt"
        result = self.client.post("/json/upload_file", {'file': d2})
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
        result = self.client.post("/json/upload_file", {'file': d1})
        json = ujson.loads(result.content)
        uri = json["uri"]
        d1_path_id = re.sub('/user_uploads/', '', uri)

        self.subscribe_to_stream("hamlet@zulip.com", "Denmark")
        body = "First message ...[zulip.txt](http://localhost:9991/user_uploads/" + d1_path_id + ")"
        self.send_message("hamlet@zulip.com", "Denmark", Recipient.STREAM, body, "test")
        body = "Second message ...[zulip.txt](http://localhost:9991/user_uploads/" + d1_path_id + ")"
        self.send_message("hamlet@zulip.com", "Denmark", Recipient.STREAM, body, "test")

        self.assertEquals(Attachment.objects.get(path_id=d1_path_id).messages.count(), 2)

    def tearDown(self):
        # type: () -> None
        destroy_uploads()

class SetAvatarTest(AuthedTestCase):

    def test_multiple_upload_failure(self):
        # type: () -> None
        """
        Attempting to upload two files should fail.
        """
        self.login("hamlet@zulip.com")
        fp1 = open(os.path.join(TEST_AVATAR_DIR, 'img.png'), 'rb')
        fp2 = open(os.path.join(TEST_AVATAR_DIR, 'img.png'), 'rb')

        result = self.client.post("/json/set_avatar", {'f1': fp1, 'f2': fp2})
        self.assert_json_error(result, "You must upload exactly one avatar.")

    def test_no_file_upload_failure(self):
        # type: () -> None
        """
        Calling this endpoint with no files should fail.
        """
        self.login("hamlet@zulip.com")

        result = self.client.post("/json/set_avatar")
        self.assert_json_error(result, "You must upload exactly one avatar.")

    correct_files = [
        ('img.png', 'png_resized.png'),
        ('img.gif', 'gif_resized.png'),
        ('img.tif', 'tif_resized.png')
    ]
    corrupt_files = ['text.txt', 'corrupt.png', 'corrupt.gif']

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

            result = self.client.post("/json/set_avatar", {'file': fp})
            self.assert_json_success(result)
            json = ujson.loads(result.content)
            self.assertIn("avatar_url", json)
            url = json["avatar_url"]
            base = '/user_avatars/'
            self.assertEquals(base, url[:len(base)])

            rfp = open(os.path.join(TEST_AVATAR_DIR, rfname), 'rb')
            response = self.client.get(url)
            data = "".join(response.streaming_content)
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

            result = self.client.post("/json/set_avatar", {'file': fp})
            self.assert_json_error(result, "Could not decode avatar image; did you upload an image file?")

    def tearDown(self):
        # type: () -> None
        destroy_uploads()

class LocalStorageTest(AuthedTestCase):

    def test_file_upload_local(self):
        # type: () -> None
        sender_email = "hamlet@zulip.com"
        user_profile = get_user_profile_by_email(sender_email)
        uri = upload_message_image('dummy.txt', 'text/plain', 'zulip!', user_profile)

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
        result = self.client.post("/json/upload_file", {'file': fp})

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

class S3Test(AuthedTestCase):

    @use_s3_backend
    def test_file_upload_s3(self):
        # type: () -> None
        conn = S3Connection(settings.S3_KEY, settings.S3_SECRET_KEY)
        bucket = conn.create_bucket(settings.S3_AUTH_UPLOADS_BUCKET)

        sender_email = "hamlet@zulip.com"
        user_profile = get_user_profile_by_email(sender_email)
        uri = upload_message_image('dummy.txt', 'text/plain', 'zulip!', user_profile)

        base = '/user_uploads/'
        self.assertEquals(base, uri[:len(base)])
        path_id = re.sub('/user_uploads/', '', uri)
        self.assertEquals("zulip!", bucket.get_key(path_id).get_contents_as_string())

    @use_s3_backend
    def test_message_image_delete_s3(self):
        # type: () -> None
        conn = S3Connection(settings.S3_KEY, settings.S3_SECRET_KEY)
        conn.create_bucket(settings.S3_AUTH_UPLOADS_BUCKET)

        sender_email = "hamlet@zulip.com"
        user_profile = get_user_profile_by_email(sender_email)
        uri = upload_message_image('dummy.txt', 'text/plain', 'zulip!', user_profile)

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

        result = self.client.post("/json/upload_file", {'file': fp})
        self.assert_json_success(result)
        json = ujson.loads(result.content)
        self.assertIn("uri", json)
        uri = json["uri"]
        base = '/user_uploads/'
        self.assertEquals(base, uri[:len(base)])

        response = self.client.get(uri)
        redirect_url = response['Location']

        self.assertEquals("zulip!", urllib.request.urlopen(redirect_url).read().strip())

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
