# -*- coding: utf-8 -*-

import mock

from typing import Any

from zerver.lib.attachments import user_attachments
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import Attachment


class AttachmentsTests(ZulipTestCase):
    def setUp(self) -> None:
        user_profile = self.example_user('cordelia')
        self.attachment = Attachment.objects.create(
            file_name='test.txt', path_id='foo/bar/test.txt', owner=user_profile)

    def test_list_by_user(self) -> None:
        user_profile = self.example_user('cordelia')
        self.login(user_profile.email)
        result = self.client_get('/json/attachments')
        self.assert_json_success(result)
        attachments = user_attachments(user_profile)
        self.assertEqual(result.json()['attachments'], attachments)

    def test_remove_attachment_exception(self) -> None:
        user_profile = self.example_user('cordelia')
        self.login(user_profile.email)
        with mock.patch('zerver.lib.attachments.delete_message_image', side_effect=Exception()):
            result = self.client_delete('/json/attachments/{id}'.format(id=self.attachment.id))
        self.assert_json_error(result, "An error occurred while deleting the attachment. Please try again later.")

    @mock.patch('zerver.lib.attachments.delete_message_image')
    def test_remove_attachment(self, ignored: Any) -> None:
        user_profile = self.example_user('cordelia')
        self.login(user_profile.email)
        result = self.client_delete('/json/attachments/{id}'.format(id=self.attachment.id))
        self.assert_json_success(result)
        attachments = user_attachments(user_profile)
        self.assertEqual(attachments, [])

    def test_list_another_user(self) -> None:
        user_profile = self.example_user('iago')
        self.login(user_profile.email)
        result = self.client_get('/json/attachments')
        self.assert_json_success(result)
        self.assertEqual(result.json()['attachments'], [])

    def test_remove_another_user(self) -> None:
        user_profile = self.example_user('iago')
        self.login(user_profile.email)
        result = self.client_delete('/json/attachments/{id}'.format(id=self.attachment.id))
        self.assert_json_error(result, 'Invalid attachment')
        user_profile_to_remove = self.example_user('cordelia')
        attachments = user_attachments(user_profile_to_remove)
        self.assertEqual(attachments, [self.attachment.to_dict()])

    def test_list_unauthenticated(self) -> None:
        result = self.client_get('/json/attachments')
        self.assert_json_error(result, 'Not logged in: API authentication or user session required', status_code=401)

    def test_delete_unauthenticated(self) -> None:
        result = self.client_delete('/json/attachments/{id}'.format(id=self.attachment.id))
        self.assert_json_error(result, 'Not logged in: API authentication or user session required', status_code=401)
