# -*- coding: utf-8 -*-
from __future__ import absolute_import

from django.test import TestCase
from django.conf import settings
from zerver.views import realm_emoji
from zerver.lib.actions import get_realm, get_user_profile_by_email, check_add_realm_emoji
from zerver.lib.test_helpers import POSTRequestMock
from zerver.lib.response import json_success
import ujson

class RealmEmojiTest(TestCase):

    def test_list(self):
        realm = get_realm('zulip.com')
        user_profile = get_user_profile_by_email("hamlet@zulip.com")
        check_add_realm_emoji(realm, "my_emoji", "https://realm.com/my_emoji")
        result = realm_emoji.list_emoji(None, user_profile)
        content = ujson.loads(result.content)
        self.assertEqual(200, result.status_code)
        self.assertEqual(len(content["emoji"]), 1)

    def test_upload(self):
        user_profile = get_user_profile_by_email("hamlet@zulip.com")
        post_data = {"name": "my_emoji", "url": "https://realm.com/my_emoji" }
        request = POSTRequestMock(post_data, user_profile, None)
        result = realm_emoji.upload_emoji(request, user_profile)
        self.assertEqual(200, result.status_code)

    def test_upload_exception(self):
        user_profile = get_user_profile_by_email("hamlet@zulip.com")
        post_data = {"name": "my_em*/oji", "url": "https://realm.com/my_emoji" }
        request = POSTRequestMock(post_data, user_profile, None)
        result = realm_emoji.upload_emoji(request, user_profile)
        self.assertEqual(400, result.status_code)

    def test_delete(self):
        realm = get_realm('zulip.com')
        user_profile = get_user_profile_by_email("hamlet@zulip.com")
        check_add_realm_emoji(realm, "my_emoji", "https://realm.com/my_emoji")
        result = realm_emoji.delete_emoji(None, user_profile, "my_emoji")
        list_emoji = realm_emoji.list_emoji(None, user_profile)
        content = ujson.loads(list_emoji.content)
        self.assertEqual(200, result.status_code)
        self.assertEqual(len(content["emoji"]), 0)
