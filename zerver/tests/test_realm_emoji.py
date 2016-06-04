# -*- coding: utf-8 -*-
from __future__ import absolute_import

from django.test import TestCase
from django.conf import settings
from zerver.views import realm_emoji
from zerver.lib.actions import get_realm, get_user_profile_by_email, check_add_realm_emoji
from zerver.lib.test_helpers import POSTRequestMock, AuthedTestCase
from zerver.lib.response import json_success
import ujson

class RealmEmojiTest(AuthedTestCase):

    def test_list(self):
        self.login("iago@zulip.com")
        realm = get_realm('zulip.com')
        check_add_realm_emoji(realm, "my_emoji", "https://realm.com/my_emoji")
        result = self.client.get("/json/realm/emoji")
        self.assert_json_success(result)
        self.assertEqual(200, result.status_code)

    def test_upload(self):
        self.login("iago@zulip.com")
        data = { "name": "my_emoji", "url": "https://realm.com/my_emoji" }
        result = self.client_put("/json/realm/emoji", info=data)
        self.assert_json_success(result)
        self.assertEqual(200, result.status_code)

    def test_upload_exception(self):
        self.login("iago@zulip.com")
        data = { "name": "my_em*/oji", "url": "https://realm.com/my_emoji" }
        result = self.client_put("/json/realm/emoji", info=data)
        self.assert_json_error(result, u'Invalid Emoji Name: Names must only contain numbers and letters')

    def test_delete(self):
        self.login("iago@zulip.com")
        realm = get_realm('zulip.com')
        user_profile = get_user_profile_by_email("hamlet@zulip.com")
        check_add_realm_emoji(realm, "my_emoji", "https://realm.com/my_emoji")
        result = self.client_delete("/json/realm/emoji/my_emoji")
        list_emoji = realm_emoji.list_emoji(None, user_profile)
        content = ujson.loads(list_emoji.content)
        self.assert_json_success(result)
        self.assertEqual(len(content["emoji"]), 0)
