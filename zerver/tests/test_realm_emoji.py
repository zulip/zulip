# -*- coding: utf-8 -*-
from __future__ import absolute_import

from zerver.lib.actions import get_realm, check_add_realm_emoji
from zerver.lib.test_helpers import ZulipTestCase
import ujson

class RealmEmojiTest(ZulipTestCase):

    def test_list(self):
        # type: () -> None
        self.login("iago@zulip.com")
        realm = get_realm('zulip.com')
        check_add_realm_emoji(realm, "my_emoji", "https://example.com/my_emoji")
        result = self.client_get("/json/realm/emoji")
        self.assert_json_success(result)
        self.assertEqual(200, result.status_code)
        content = ujson.loads(result.content)
        self.assertEqual(len(content["emoji"]), 1)

    def test_upload(self):
        # type: () -> None
        self.login("iago@zulip.com")
        data = {"name": "my_emoji", "url": "https://example.com/my_emoji"}
        result = self.client_put("/json/realm/emoji", info=data)
        self.assert_json_success(result)
        self.assertEqual(200, result.status_code)

        result = self.client_get("/json/realm/emoji")
        content = ujson.loads(result.content)
        self.assert_json_success(result)
        self.assertEqual(len(content["emoji"]), 1)

    def test_upload_exception(self):
        # type: () -> None
        self.login("iago@zulip.com")
        data = {"name": "my_em*/oji", "url": "https://example.com/my_emoji"}
        result = self.client_put("/json/realm/emoji", info=data)
        self.assert_json_error(result, 'Invalid characters in Emoji name')

    def test_delete(self):
        # type: () -> None
        self.login("iago@zulip.com")
        realm = get_realm('zulip.com')
        check_add_realm_emoji(realm, "my_emoji", "https://example.com/my_emoji")
        result = self.client_delete("/json/realm/emoji/my_emoji")
        self.assert_json_success(result)

        result = self.client_get("/json/realm/emoji")
        content = ujson.loads(result.content)
        self.assert_json_success(result)
        self.assertEqual(len(content["emoji"]), 0)
