# -*- coding: utf-8 -*-
from __future__ import absolute_import

from zerver.lib.actions import get_realm_by_string_id, check_add_realm_emoji
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import RealmEmoji
import ujson

class RealmEmojiTest(ZulipTestCase):

    def test_list(self):
        # type: () -> None
        self.login("iago@zulip.com")
        realm = get_realm_by_string_id('zulip')
        check_add_realm_emoji(realm, "my_emoji", "https://example.com/my_emoji")
        result = self.client_get("/json/realm/emoji")
        self.assert_json_success(result)
        self.assertEqual(200, result.status_code)
        content = ujson.loads(result.content)
        self.assertEqual(len(content["emoji"]), 1)

    def test_list_no_author(self):
        # type: () -> None
        self.login("iago@zulip.com")
        realm = get_realm_by_string_id('zulip')
        RealmEmoji.objects.create(realm=realm, name='my_emojy', img_url='https://example.com/my_emoji')
        result = self.client_get("/json/realm/emoji")
        self.assert_json_success(result)
        content = ujson.loads(result.content)
        self.assertEqual(len(content["emoji"]), 1)
        self.assertIsNone(content["emoji"]['my_emojy']['author'])

    def test_list_admins_only(self):
        # type: () -> None
        self.login('othello@zulip.com')
        realm = get_realm_by_string_id('zulip')
        realm.add_emoji_by_admins_only = True
        realm.save()
        check_add_realm_emoji(realm, "my_emoji", "https://example.com/my_emoji")
        result = self.client_get("/json/realm/emoji")
        self.assert_json_success(result)
        content = ujson.loads(result.content)
        self.assertEqual(len(content["emoji"]), 1)
        self.assertIsNone(content["emoji"]['my_emoji']['author'])

    def test_upload(self):
        # type: () -> None
        email = "iago@zulip.com"
        self.login(email)
        data = {"name": "my_emoji", "url": "https://example.com/my_emoji"}
        result = self.client_put("/json/realm/emoji", info=data)
        self.assert_json_success(result)
        self.assertEqual(200, result.status_code)
        emoji = RealmEmoji.objects.get(name=data['name'])
        self.assertEqual(emoji.author.email, email)

        result = self.client_get("/json/realm/emoji")
        content = ujson.loads(result.content)
        self.assert_json_success(result)
        self.assertEqual(len(content["emoji"]), 1)
        self.assertIn('author', content["emoji"]['my_emoji'])
        self.assertEqual(
            content["emoji"]['my_emoji']['author']['email'], email)

        realm_emoji = RealmEmoji.objects.get(realm=get_realm_by_string_id('zulip'))
        self.assertEqual(
            str(realm_emoji),
            '<RealmEmoji(zulip.com): my_emoji https://example.com/my_emoji>'
        )

    def test_upload_exception(self):
        # type: () -> None
        self.login("iago@zulip.com")
        data = {"name": "my_em*/oji", "url": "https://example.com/my_emoji"}
        result = self.client_put("/json/realm/emoji", info=data)
        self.assert_json_error(result, 'Invalid characters in Emoji name')

    def test_upload_admins_only(self):
        # type: () -> None
        self.login('othello@zulip.com')
        realm = get_realm_by_string_id('zulip')
        realm.add_emoji_by_admins_only = True
        realm.save()
        data = {"name": "my_emoji", "url": "https://example.com/my_emoji"}
        result = self.client_put("/json/realm/emoji", info=data)
        self.assert_json_error(result, 'Must be a realm administrator')

    def test_delete(self):
        # type: () -> None
        self.login("iago@zulip.com")
        realm = get_realm_by_string_id('zulip')
        check_add_realm_emoji(realm, "my_emoji", "https://example.com/my_emoji")
        result = self.client_delete("/json/realm/emoji/my_emoji")
        self.assert_json_success(result)

        result = self.client_get("/json/realm/emoji")
        content = ujson.loads(result.content)
        self.assert_json_success(result)
        self.assertEqual(len(content["emoji"]), 0)

    def test_delete_admins_only(self):
        # type: () -> None
        self.login('othello@zulip.com')
        realm = get_realm_by_string_id('zulip')
        realm.add_emoji_by_admins_only = True
        realm.save()
        check_add_realm_emoji(realm, "my_emoji", "https://example.com/my_emoji")
        result = self.client_delete("/json/realm/emoji/my_emoji")
        self.assert_json_error(result, 'Must be a realm administrator')
