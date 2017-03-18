# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import print_function

import mock
import ujson

from typing import Any

from zerver.lib.attachments import user_attachments
from zerver.lib.test_helpers import get_user_profile_by_email
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import Attachment


class AttachmentsTests(ZulipTestCase):
    def setUp(self):
        # type: () -> None
        user = get_user_profile_by_email("cordelia@zulip.com")
        self.attachment = Attachment.objects.create(
            file_name='test.txt', path_id='foo/bar/test.txt', owner=user)

    def test_list_by_user(self):
        # type: () -> None
        self.login("cordelia@zulip.com")
        result = self.client_get('/json/attachments')
        self.assert_json_success(result)
        user = get_user_profile_by_email("cordelia@zulip.com")
        attachments = user_attachments(user)
        data = ujson.loads(result.content)
        self.assertEqual(data['attachments'], attachments)

    @mock.patch('zerver.lib.attachments.delete_message_image')
    def test_remove_attachment(self, ignored):
        # type: (Any) -> None
        self.login("cordelia@zulip.com")
        result = self.client_delete('/json/attachments/{pk}'.format(pk=self.attachment.pk))
        self.assert_json_success(result)
        user = get_user_profile_by_email("cordelia@zulip.com")
        attachments = user_attachments(user)
        self.assertEqual(attachments, [])

    def test_list_another_user(self):
        # type: () -> None
        self.login("iago@zulip.com")
        result = self.client_get('/json/attachments')
        self.assert_json_success(result)
        data = ujson.loads(result.content)
        self.assertEqual(data['attachments'], [])

    def test_remove_another_user(self):
        # type: () -> None
        self.login("iago@zulip.com")
        result = self.client_delete('/json/attachments/{pk}'.format(pk=self.attachment.pk))
        self.assert_json_error(result, 'Invalid attachment')
        user = get_user_profile_by_email("cordelia@zulip.com")
        attachments = user_attachments(user)
        self.assertEqual(attachments, [self.attachment.to_dict()])

    def test_list_unauthenticated(self):
        # type: () -> None
        result = self.client_get('/json/attachments')
        self.assert_json_error(result, 'Not logged in: API authentication or user session required', status_code=401)

    def test_delete_unauthenticated(self):
        # type: () -> None
        result = self.client_delete('/json/attachments/{pk}'.format(pk=self.attachment.pk))
        self.assert_json_error(result, 'Not logged in: API authentication or user session required', status_code=401)
