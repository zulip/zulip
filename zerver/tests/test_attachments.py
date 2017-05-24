# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import print_function

import mock
import ujson

from typing import Any

from zerver.lib.attachments import user_attachments
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import Attachment


class AttachmentsTests(ZulipTestCase):
    def setUp(self):
        # type: () -> None
        user_profile = self.example_user('cordelia')
        self.attachment = Attachment.objects.create(
            file_name='test.txt', path_id='foo/bar/test.txt', owner=user_profile)

    def test_list_by_user(self):
        # type: () -> None
        user_profile = self.example_user('cordelia')
        self.login(user_profile.email)
        result = self.client_get('/json/attachments')
        self.assert_json_success(result)
        attachments = user_attachments(user_profile)
        data = ujson.loads(result.content)
        self.assertEqual(data['attachments'], attachments)

    @mock.patch('zerver.lib.attachments.delete_message_image')
    def test_remove_attachment(self, ignored):
        # type: (Any) -> None
        user_profile = self.example_user('cordelia')
        self.login(user_profile.email)
        result = self.client_delete('/json/attachments/{pk}'.format(pk=self.attachment.pk))
        self.assert_json_success(result)
        attachments = user_attachments(user_profile)
        self.assertEqual(attachments, [])

    def test_list_another_user(self):
        # type: () -> None
        user_profile = self.example_user('iago')
        self.login(user_profile.email)
        result = self.client_get('/json/attachments')
        self.assert_json_success(result)
        data = ujson.loads(result.content)
        self.assertEqual(data['attachments'], [])

    def test_remove_another_user(self):
        # type: () -> None
        user_profile = self.example_user('iago')
        self.login(user_profile.email)
        result = self.client_delete('/json/attachments/{pk}'.format(pk=self.attachment.pk))
        self.assert_json_error(result, 'Invalid attachment')
        user_profile_to_remove = self.example_user('cordelia')
        attachments = user_attachments(user_profile_to_remove)
        self.assertEqual(attachments, [self.attachment.to_dict()])

    def test_list_unauthenticated(self):
        # type: () -> None
        result = self.client_get('/json/attachments')
        self.assert_json_error(result, 'Not logged in: API authentication or user session required', status_code=401)

    def test_delete_unauthenticated(self):
        # type: () -> None
        result = self.client_delete('/json/attachments/{pk}'.format(pk=self.attachment.pk))
        self.assert_json_error(result, 'Not logged in: API authentication or user session required', status_code=401)
