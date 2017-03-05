from __future__ import absolute_import
from __future__ import print_function

import filecmp
import os
import ujson

from django.core import mail
from django.http import HttpResponse
from django.test import override_settings
from mock import patch
from typing import Any, Dict, List

from zerver.lib.actions import do_change_stream_invite_only
from zerver.models import get_realm, get_stream, get_user_profile_by_email, \
    Realm, Stream, UserProfile
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import (
    avatar_disk_path, get_test_image_file, tornado_redirected_to_list,
)

class BotTest(ZulipTestCase):
    def assert_num_bots_equal(self, count):
        # type: (int) -> None
        result = self.client_get("/json/bots")
        self.assert_json_success(result)
        json = ujson.loads(result.content)
        self.assertEqual(count, len(json['bots']))

    def create_bot(self, **extras):
        # type: (**Any) -> Dict[str, Any]
        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
        }
        bot_info.update(extras)
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_success(result)
        return ujson.loads(result.content)

    def test_bot_domain(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        self.create_bot()
        self.assertTrue(UserProfile.objects.filter(email='hambot-bot@zulip.testserver').exists())
        # The other cases are hard to test directly, since we don't allow creating bots from
        # the wrong subdomain, and because 'testserver.example.com' is not a valid domain for the bot's email.
        # So we just test the Raelm.get_bot_domain function.
        realm = get_realm('zulip')
        with self.settings(REALMS_HAVE_SUBDOMAINS=True):
            self.assertEqual(realm.get_bot_domain(), 'zulip.testserver')
        Realm.objects.exclude(string_id='zulip').update(deactivated=True)
        self.assertEqual(realm.get_bot_domain(), 'testserver')

    def deactivate_bot(self):
        # type: () -> None
        result = self.client_delete("/json/bots/hambot-bot@zulip.testserver")
        self.assert_json_success(result)

    def test_add_bot_with_bad_username(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        self.assert_num_bots_equal(0)
        bot_info = dict(
            full_name='',
            short_name='',
        )
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_error(result, 'Bad name or username')
        self.assert_num_bots_equal(0)

    def test_add_bot(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        self.assert_num_bots_equal(0)
        events = [] # type: List[Dict[str, Any]]
        with tornado_redirected_to_list(events):
            result = self.create_bot()
        self.assert_num_bots_equal(1)

        bot = get_user_profile_by_email('hambot-bot@zulip.testserver')

        event = [e for e in events if e['event']['type'] == 'realm_bot'][0]
        self.assertEqual(
            dict(
                type='realm_bot',
                op='add',
                bot=dict(email='hambot-bot@zulip.testserver',
                         user_id=bot.id,
                         full_name='The Bot of Hamlet',
                         is_active=True,
                         api_key=result['api_key'],
                         avatar_url=result['avatar_url'],
                         default_sending_stream=None,
                         default_events_register_stream=None,
                         default_all_public_streams=False,
                         owner='hamlet@zulip.com')
            ),
            event['event']
        )

        users_result = self.client_get('/json/users')
        members = ujson.loads(users_result.content)['members']
        bots = [m for m in members if m['email'] == 'hambot-bot@zulip.testserver']
        self.assertEqual(len(bots), 1)
        bot = bots[0]
        self.assertEqual(bot['bot_owner'], 'hamlet@zulip.com')
        self.assertEqual(bot['user_id'], get_user_profile_by_email('hambot-bot@zulip.testserver').id)

    def test_add_bot_with_username_in_use(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        self.assert_num_bots_equal(0)
        result = self.create_bot()
        self.assert_num_bots_equal(1)

        bot_info = dict(
            full_name='Duplicate',
            short_name='hambot',
        )
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_error(result, 'Username already in use')

    def test_add_bot_with_user_avatar(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        self.assert_num_bots_equal(0)
        with get_test_image_file('img.png') as fp:
            self.create_bot(file=fp)
            profile = get_user_profile_by_email('hambot-bot@zulip.testserver')
            # Make sure that avatar image that we've uploaded is same with avatar image in the server
            self.assertTrue(filecmp.cmp(fp.name,
                                        os.path.splitext(avatar_disk_path(profile))[0] +
                                        ".original"))
        self.assert_num_bots_equal(1)

        self.assertEqual(profile.avatar_source, UserProfile.AVATAR_FROM_USER)
        self.assertTrue(os.path.exists(avatar_disk_path(profile)))

    def test_add_bot_with_too_many_files(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        self.assert_num_bots_equal(0)
        with get_test_image_file('img.png') as fp1, \
                get_test_image_file('img.gif') as fp2:
            bot_info = dict(
                full_name='whatever',
                short_name='whatever',
                file1=fp1,
                file2=fp2,
            )
            result = self.client_post("/json/bots", bot_info)
        self.assert_json_error(result, 'You may only upload one file at a time')
        self.assert_num_bots_equal(0)

    def test_add_bot_with_default_sending_stream(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        self.assert_num_bots_equal(0)
        result = self.create_bot(default_sending_stream='Denmark')
        self.assert_num_bots_equal(1)
        self.assertEqual(result['default_sending_stream'], 'Denmark')

        profile = get_user_profile_by_email('hambot-bot@zulip.testserver')
        self.assertEqual(profile.default_sending_stream.name, 'Denmark')

    def test_add_bot_with_default_sending_stream_not_subscribed(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        self.assert_num_bots_equal(0)
        result = self.create_bot(default_sending_stream='Rome')
        self.assert_num_bots_equal(1)
        self.assertEqual(result['default_sending_stream'], 'Rome')

        profile = get_user_profile_by_email('hambot-bot@zulip.testserver')
        self.assertEqual(profile.default_sending_stream.name, 'Rome')

    def test_bot_add_subscription(self):
        # type: () -> None
        """
        Calling POST /json/users/me/subscriptions should successfully add
        streams, and a stream to the
        list of subscriptions and confirm the right number of events
        are generated.
        When 'principals' has a bot, no notification message event or invitation email
        is sent when add_subscriptions_backend is called in the above api call.
        """
        self.login("hamlet@zulip.com")

        # Normal user i.e. not a bot.
        request_data = {
            'principals': '["iago@zulip.com"]'
        }
        events = [] # type: List[Dict[str, Any]]
        with tornado_redirected_to_list(events):
            result = self.common_subscribe_to_streams("hamlet@zulip.com", ['Rome'], request_data)
            self.assert_json_success(result)

        msg_event = [e for e in events if e['event']['type'] == 'message']
        self.assert_length(msg_event, 1) # Notification message event is sent.

        # Create a bot.
        self.assert_num_bots_equal(0)
        result = self.create_bot()
        self.assert_num_bots_equal(1)

        # A bot
        bot_request_data = {
            'principals': '["hambot-bot@zulip.testserver"]'
        }
        events_bot = [] # type: List[Dict[str, Any]]
        with tornado_redirected_to_list(events_bot):
            result = self.common_subscribe_to_streams("hamlet@zulip.com", ['Rome'], bot_request_data)
            self.assert_json_success(result)

        # No notification message event or invitation email is sent because of bot.
        msg_event = [e for e in events_bot if e['event']['type'] == 'message']
        self.assert_length(msg_event, 0)
        self.assertEqual(len(events_bot), len(events) - 1)

        # Test runner automatically redirects all sent email to a dummy 'outbox'.
        self.assertEqual(len(mail.outbox), 0)

    def test_add_bot_with_default_sending_stream_private_allowed(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        user_profile = get_user_profile_by_email("hamlet@zulip.com")
        stream = get_stream("Denmark", user_profile.realm)
        self.subscribe_to_stream(user_profile.email, stream.name)
        do_change_stream_invite_only(stream, True)

        self.assert_num_bots_equal(0)
        events = [] # type: List[Dict[str, Any]]
        with tornado_redirected_to_list(events):
            result = self.create_bot(default_sending_stream='Denmark')
        self.assert_num_bots_equal(1)
        self.assertEqual(result['default_sending_stream'], 'Denmark')

        profile = get_user_profile_by_email('hambot-bot@zulip.testserver')
        self.assertEqual(profile.default_sending_stream.name, 'Denmark')

        event = [e for e in events if e['event']['type'] == 'realm_bot'][0]
        self.assertEqual(
            dict(
                type='realm_bot',
                op='add',
                bot=dict(email='hambot-bot@zulip.testserver',
                         user_id=profile.id,
                         full_name='The Bot of Hamlet',
                         is_active=True,
                         api_key=result['api_key'],
                         avatar_url=result['avatar_url'],
                         default_sending_stream='Denmark',
                         default_events_register_stream=None,
                         default_all_public_streams=False,
                         owner='hamlet@zulip.com')
            ),
            event['event']
        )
        self.assertEqual(event['users'], (user_profile.id,))

    def test_add_bot_with_default_sending_stream_private_denied(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        user_profile = get_user_profile_by_email("hamlet@zulip.com")
        stream = get_stream("Denmark", user_profile.realm)
        self.unsubscribe_from_stream("hamlet@zulip.com", "Denmark")
        do_change_stream_invite_only(stream, True)

        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
            'default_sending_stream': 'Denmark',
        }
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_error(result, "Invalid stream name 'Denmark'")

    def test_add_bot_with_default_events_register_stream(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        self.assert_num_bots_equal(0)
        result = self.create_bot(default_events_register_stream='Denmark')
        self.assert_num_bots_equal(1)
        self.assertEqual(result['default_events_register_stream'], 'Denmark')

        profile = get_user_profile_by_email('hambot-bot@zulip.testserver')
        self.assertEqual(profile.default_events_register_stream.name, 'Denmark')

    def test_add_bot_with_default_events_register_stream_private_allowed(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        user_profile = get_user_profile_by_email("hamlet@zulip.com")
        stream = self.subscribe_to_stream(user_profile.email, 'Denmark')
        do_change_stream_invite_only(stream, True)

        self.assert_num_bots_equal(0)
        events = [] # type: List[Dict[str, Any]]
        with tornado_redirected_to_list(events):
            result = self.create_bot(default_events_register_stream='Denmark')
        self.assert_num_bots_equal(1)
        self.assertEqual(result['default_events_register_stream'], 'Denmark')

        bot_profile = get_user_profile_by_email('hambot-bot@zulip.testserver')
        self.assertEqual(bot_profile.default_events_register_stream.name, 'Denmark')

        event = [e for e in events if e['event']['type'] == 'realm_bot'][0]
        self.assertEqual(
            dict(
                type='realm_bot',
                op='add',
                bot=dict(email='hambot-bot@zulip.testserver',
                         full_name='The Bot of Hamlet',
                         user_id=bot_profile.id,
                         is_active=True,
                         api_key=result['api_key'],
                         avatar_url=result['avatar_url'],
                         default_sending_stream=None,
                         default_events_register_stream='Denmark',
                         default_all_public_streams=False,
                         owner='hamlet@zulip.com')
            ),
            event['event']
        )
        self.assertEqual(event['users'], (user_profile.id,))

    def test_add_bot_with_default_events_register_stream_private_denied(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        user_profile = get_user_profile_by_email("hamlet@zulip.com")
        stream = get_stream("Denmark", user_profile.realm)
        self.unsubscribe_from_stream("hamlet@zulip.com", "Denmark")
        do_change_stream_invite_only(stream, True)

        self.assert_num_bots_equal(0)
        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
            'default_events_register_stream': 'Denmark',
        }
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_error(result, "Invalid stream name 'Denmark'")

    def test_add_bot_with_default_all_public_streams(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        self.assert_num_bots_equal(0)
        result = self.create_bot(default_all_public_streams=ujson.dumps(True))
        self.assert_num_bots_equal(1)
        self.assertTrue(result['default_all_public_streams'])

        profile = get_user_profile_by_email('hambot-bot@zulip.testserver')
        self.assertEqual(profile.default_all_public_streams, True)

    def test_deactivate_bot(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        self.assert_num_bots_equal(0)
        self.create_bot()
        self.assert_num_bots_equal(1)
        self.deactivate_bot()
        # You can deactivate the same bot twice.
        self.deactivate_bot()
        self.assert_num_bots_equal(0)

    def test_deactivate_bogus_bot(self):
        # type: () -> None
        """Deleting a bogus bot will succeed silently."""
        self.login("hamlet@zulip.com")
        self.assert_num_bots_equal(0)
        self.create_bot()
        self.assert_num_bots_equal(1)
        result = self.client_delete("/json/bots/bogus-bot@zulip.com")
        self.assert_json_error(result, 'No such bot')
        self.assert_num_bots_equal(1)

    def test_bot_deactivation_attacks(self):
        # type: () -> None
        """You cannot deactivate somebody else's bot."""
        self.login("hamlet@zulip.com")
        self.assert_num_bots_equal(0)
        self.create_bot()
        self.assert_num_bots_equal(1)

        # Have Othello try to deactivate both Hamlet and
        # Hamlet's bot.
        self.login("othello@zulip.com")

        # Can not deactivate a user as a bot
        result = self.client_delete("/json/bots/hamlet@zulip.com")
        self.assert_json_error(result, 'No such bot')

        result = self.client_delete("/json/bots/hambot-bot@zulip.testserver")
        self.assert_json_error(result, 'Insufficient permission')

        # But we don't actually deactivate the other person's bot.
        self.login("hamlet@zulip.com")
        self.assert_num_bots_equal(1)

        # Can not deactivate a bot as a user
        result = self.client_delete("/json/users/hambot-bot@zulip.testserver")
        self.assert_json_error(result, 'No such user')
        self.assert_num_bots_equal(1)

    def test_bot_permissions(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        self.assert_num_bots_equal(0)
        self.create_bot()
        self.assert_num_bots_equal(1)

        # Have Othello try to mess with Hamlet's bots.
        self.login("othello@zulip.com")

        result = self.client_post("/json/bots/hambot-bot@zulip.testserver/api_key/regenerate")
        self.assert_json_error(result, 'Insufficient permission')

        bot_info = {
            'full_name': 'Fred',
        }
        result = self.client_patch("/json/bots/hambot-bot@zulip.testserver", bot_info)
        self.assert_json_error(result, 'Insufficient permission')

    def get_bot(self):
        # type: () -> Dict[str, Any]
        result = self.client_get("/json/bots")
        bots = ujson.loads(result.content)['bots']
        return bots[0]

    def test_update_api_key(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        self.create_bot()
        bot = self.get_bot()
        old_api_key = bot['api_key']
        result = self.client_post('/json/bots/hambot-bot@zulip.testserver/api_key/regenerate')
        self.assert_json_success(result)
        new_api_key = ujson.loads(result.content)['api_key']
        self.assertNotEqual(old_api_key, new_api_key)
        bot = self.get_bot()
        self.assertEqual(new_api_key, bot['api_key'])

    def test_update_api_key_for_invalid_user(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        result = self.client_post('/json/bots/nonexistentuser@zulip.com/api_key/regenerate')
        self.assert_json_error(result, 'No such user')

    def test_patch_bot_full_name(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
        }
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_success(result)
        bot_info = {
            'full_name': 'Fred',
        }
        result = self.client_patch("/json/bots/hambot-bot@zulip.testserver", bot_info)
        self.assert_json_success(result)

        full_name = ujson.loads(result.content)['full_name']
        self.assertEqual('Fred', full_name)

        bot = self.get_bot()
        self.assertEqual('Fred', bot['full_name'])

    def test_patch_bot_owner(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
        }
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_success(result)
        bot_info = {
            'bot_owner': 'othello@zulip.com',
        }
        result = self.client_patch("/json/bots/hambot-bot@zulip.testserver", bot_info)
        self.assert_json_success(result)

        # Test bot's owner has been changed successfully.
        bot_owner = ujson.loads(result.content)['bot_owner']
        self.assertEqual(bot_owner, 'othello@zulip.com')

        self.login('othello@zulip.com')
        bot = self.get_bot()
        self.assertEqual('The Bot of Hamlet', bot['full_name'])

    @override_settings(LOCAL_UPLOADS_DIR='var/bot_avatar')
    def test_patch_bot_avatar(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
        }
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_success(result)

        profile = get_user_profile_by_email('hambot-bot@zulip.testserver')
        self.assertEqual(profile.avatar_source, UserProfile.AVATAR_FROM_GRAVATAR)

        # Try error case first (too many files):
        with get_test_image_file('img.png') as fp1, \
                get_test_image_file('img.gif') as fp2:
            result = self.client_patch_multipart(
                '/json/bots/hambot-bot@zulip.testserver',
                dict(file1=fp1, file2=fp2))
        self.assert_json_error(result, 'You may only upload one file at a time')

        profile = get_user_profile_by_email("hambot-bot@zulip.testserver")
        self.assertEqual(profile.avatar_version, 1)

        # HAPPY PATH
        with get_test_image_file('img.png') as fp:
            result = self.client_patch_multipart(
                '/json/bots/hambot-bot@zulip.testserver',
                dict(file=fp))
            profile = get_user_profile_by_email('hambot-bot@zulip.testserver')
            self.assertEqual(profile.avatar_version, 2)
            # Make sure that avatar image that we've uploaded is same with avatar image in the server
            self.assertTrue(filecmp.cmp(fp.name,
                                        os.path.splitext(avatar_disk_path(profile))[0] +
                                        ".original"))
        self.assert_json_success(result)

        self.assertEqual(profile.avatar_source, UserProfile.AVATAR_FROM_USER)
        self.assertTrue(os.path.exists(avatar_disk_path(profile)))

    def test_patch_bot_to_stream(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
        }
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_success(result)
        bot_info = {
            'default_sending_stream': 'Denmark',
        }
        result = self.client_patch("/json/bots/hambot-bot@zulip.testserver", bot_info)
        self.assert_json_success(result)

        default_sending_stream = ujson.loads(result.content)['default_sending_stream']
        self.assertEqual('Denmark', default_sending_stream)

        bot = self.get_bot()
        self.assertEqual('Denmark', bot['default_sending_stream'])

    def test_patch_bot_to_stream_not_subscribed(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
        }
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_success(result)
        bot_info = {
            'default_sending_stream': 'Rome',
        }
        result = self.client_patch("/json/bots/hambot-bot@zulip.testserver", bot_info)
        self.assert_json_success(result)

        default_sending_stream = ujson.loads(result.content)['default_sending_stream']
        self.assertEqual('Rome', default_sending_stream)

        bot = self.get_bot()
        self.assertEqual('Rome', bot['default_sending_stream'])

    def test_patch_bot_to_stream_none(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
        }
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_success(result)
        bot_info = {
            'default_sending_stream': '',
        }
        result = self.client_patch("/json/bots/hambot-bot@zulip.testserver", bot_info)
        self.assert_json_success(result)

        default_sending_stream = get_user_profile_by_email(
            "hambot-bot@zulip.testserver").default_sending_stream
        self.assertEqual(None, default_sending_stream)

        bot = self.get_bot()
        self.assertEqual(None, bot['default_sending_stream'])

    def test_patch_bot_to_stream_private_allowed(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        user_profile = get_user_profile_by_email("hamlet@zulip.com")
        stream = self.subscribe_to_stream(user_profile.email, "Denmark")
        do_change_stream_invite_only(stream, True)

        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
        }
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_success(result)

        bot_info = {
            'default_sending_stream': 'Denmark',
        }
        result = self.client_patch("/json/bots/hambot-bot@zulip.testserver", bot_info)
        self.assert_json_success(result)

        default_sending_stream = ujson.loads(result.content)['default_sending_stream']
        self.assertEqual('Denmark', default_sending_stream)

        bot = self.get_bot()
        self.assertEqual('Denmark', bot['default_sending_stream'])

    def test_patch_bot_to_stream_private_denied(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        user_profile = get_user_profile_by_email("hamlet@zulip.com")
        stream = get_stream("Denmark", user_profile.realm)
        self.unsubscribe_from_stream("hamlet@zulip.com", "Denmark")
        do_change_stream_invite_only(stream, True)

        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
        }
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_success(result)

        bot_info = {
            'default_sending_stream': 'Denmark',
        }
        result = self.client_patch("/json/bots/hambot-bot@zulip.testserver", bot_info)
        self.assert_json_error(result, "Invalid stream name 'Denmark'")

    def test_patch_bot_to_stream_not_found(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
        }
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_success(result)
        bot_info = {
            'default_sending_stream': 'missing',
        }
        result = self.client_patch("/json/bots/hambot-bot@zulip.testserver", bot_info)
        self.assert_json_error(result, "Invalid stream name 'missing'")

    def test_patch_bot_events_register_stream(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
        }
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_success(result)
        bot_info = {
            'default_events_register_stream': 'Denmark',
        }
        result = self.client_patch("/json/bots/hambot-bot@zulip.testserver", bot_info)
        self.assert_json_success(result)

        default_events_register_stream = ujson.loads(result.content)['default_events_register_stream']
        self.assertEqual('Denmark', default_events_register_stream)

        bot = self.get_bot()
        self.assertEqual('Denmark', bot['default_events_register_stream'])

    def test_patch_bot_events_register_stream_allowed(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        user_profile = get_user_profile_by_email("hamlet@zulip.com")
        stream = self.subscribe_to_stream(user_profile.email, "Denmark")
        do_change_stream_invite_only(stream, True)

        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
        }
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_success(result)
        bot_info = {
            'default_events_register_stream': 'Denmark',
        }
        result = self.client_patch("/json/bots/hambot-bot@zulip.testserver", bot_info)
        self.assert_json_success(result)

        default_events_register_stream = ujson.loads(result.content)['default_events_register_stream']
        self.assertEqual('Denmark', default_events_register_stream)

        bot = self.get_bot()
        self.assertEqual('Denmark', bot['default_events_register_stream'])

    def test_patch_bot_events_register_stream_denied(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        user_profile = get_user_profile_by_email("hamlet@zulip.com")
        stream = get_stream("Denmark", user_profile.realm)
        self.unsubscribe_from_stream("hamlet@zulip.com", "Denmark")
        do_change_stream_invite_only(stream, True)

        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
        }
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_success(result)
        bot_info = {
            'default_events_register_stream': 'Denmark',
        }
        result = self.client_patch("/json/bots/hambot-bot@zulip.testserver", bot_info)
        self.assert_json_error(result, "Invalid stream name 'Denmark'")

    def test_patch_bot_events_register_stream_none(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
        }
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_success(result)
        bot_info = {
            'default_events_register_stream': '',
        }
        result = self.client_patch("/json/bots/hambot-bot@zulip.testserver", bot_info)
        self.assert_json_success(result)

        default_events_register_stream = get_user_profile_by_email(
            "hambot-bot@zulip.testserver").default_events_register_stream
        self.assertEqual(None, default_events_register_stream)

        bot = self.get_bot()
        self.assertEqual(None, bot['default_events_register_stream'])

    def test_patch_bot_events_register_stream_not_found(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
        }
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_success(result)
        bot_info = {
            'default_events_register_stream': 'missing',
        }
        result = self.client_patch("/json/bots/hambot-bot@zulip.testserver", bot_info)
        self.assert_json_error(result, "Invalid stream name 'missing'")

    def test_patch_bot_default_all_public_streams_true(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
        }
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_success(result)
        bot_info = {
            'default_all_public_streams': ujson.dumps(True),
        }
        result = self.client_patch("/json/bots/hambot-bot@zulip.testserver", bot_info)
        self.assert_json_success(result)

        default_events_register_stream = ujson.loads(result.content)['default_all_public_streams']
        self.assertEqual(default_events_register_stream, True)

        bot = self.get_bot()
        self.assertEqual(bot['default_all_public_streams'], True)

    def test_patch_bot_default_all_public_streams_false(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
        }
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_success(result)
        bot_info = {
            'default_all_public_streams': ujson.dumps(False),
        }
        result = self.client_patch("/json/bots/hambot-bot@zulip.testserver", bot_info)
        self.assert_json_success(result)

        default_events_register_stream = ujson.loads(result.content)['default_all_public_streams']
        self.assertEqual(default_events_register_stream, False)

        bot = self.get_bot()
        self.assertEqual(bot['default_all_public_streams'], False)

    def test_patch_bot_via_post(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
        }
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_success(result)
        bot_info = {
            'full_name': 'Fred',
            'method': 'PATCH'
        }
        result = self.client_post("/json/bots/hambot-bot@zulip.testserver", bot_info)
        self.assert_json_success(result)

        full_name = ujson.loads(result.content)['full_name']
        self.assertEqual('Fred', full_name)

        bot = self.get_bot()
        self.assertEqual('Fred', bot['full_name'])

    def test_patch_bogus_bot(self):
        # type: () -> None
        """Deleting a bogus bot will succeed silently."""
        self.login("hamlet@zulip.com")
        self.create_bot()
        bot_info = {
            'full_name': 'Fred',
        }
        result = self.client_patch("/json/bots/nonexistent-bot@zulip.com", bot_info)
        self.assert_json_error(result, 'No such user')
        self.assert_num_bots_equal(1)
