# -*- coding: utf-8 -*-
from __future__ import absolute_import
from django.conf import settings
from django.test import TestCase
from unittest import skip

from zerver.lib.test_helpers import AuthedTestCase
from zerver.lib.test_runner import slow
from zerver.lib.upload import sanitize_name

import ujson
from six.moves import urllib

from boto.s3.connection import S3Connection
from boto.s3.key import Key
from six.moves import StringIO
import os
import shutil

TEST_AVATAR_DIR = os.path.join(os.path.dirname(__file__), 'images')

def destroy_uploads():
    if os.path.exists(settings.LOCAL_UPLOADS_DIR):
        shutil.rmtree(settings.LOCAL_UPLOADS_DIR)

class FileUploadTest(AuthedTestCase):
    def test_multiple_upload_failure(self):
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
        """
        Calling this endpoint with no files should fail.
        """
        self.login("hamlet@zulip.com")

        result = self.client.post("/json/upload_file")
        self.assert_json_error(result, "You must specify a file to upload")

    def test_file_upload_authed(self):
        """
        A call to /json/upload_file should return a uri and actually create an object.
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

        response = self.client.get(uri)
        data = "".join(response.streaming_content)
        self.assertEquals("zulip!", data)

    def tearDown(self):
        destroy_uploads()

class SetAvatarTest(AuthedTestCase):

    def test_multiple_upload_failure(self):
        """
        Attempting to upload two files should fail.
        """
        self.login("hamlet@zulip.com")
        fp1 = open(os.path.join(TEST_AVATAR_DIR, 'img.png'), 'rb')
        fp2 = open(os.path.join(TEST_AVATAR_DIR, 'img.png'), 'rb')

        result = self.client.post("/json/set_avatar", {'f1': fp1, 'f2': fp2})
        self.assert_json_error(result, "You must upload exactly one avatar.")

    def test_no_file_upload_failure(self):
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
        destroy_uploads()

class S3Test(AuthedTestCase):
    # full URIs in public bucket
    test_uris = [] # type: List[str]
    # keys in authed bucket
    test_keys = [] # type: List[str]

    @slow(2.6, "has to contact external S3 service")
    @skip("Need S3 mock")
    def test_file_upload_authed(self):
        """
        A call to /json/upload_file should return a uri and actually create an object.
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
        self.test_keys.append(uri[len(base):])

        response = self.client.get(uri)
        redirect_url = response['Location']

        self.assertEquals("zulip!", urllib.request.urlopen(redirect_url).read().strip())

    def tearDown(self):
        # clean up
        return
        # TODO: un-deadden this code when we have proper S3 mocking.
        conn = S3Connection(settings.S3_KEY, settings.S3_SECRET_KEY)
        for uri in self.test_uris:
            key = Key(conn.get_bucket(settings.S3_BUCKET))
            key.name = urllib.parse.urlparse(uri).path[1:]
            key.delete()
            self.test_uris.remove(uri)

        for path in self.test_keys:
            key = Key(conn.get_bucket(settings.S3_AUTH_UPLOADS_BUCKET))
            key.name = path
            key.delete()
            self.test_keys.remove(path)

class SanitizeNameTests(TestCase):
    def test_file_name(self):
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
