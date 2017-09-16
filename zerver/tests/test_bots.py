from __future__ import absolute_import
from __future__ import print_function

import filecmp
import os
import ujson

from django.core import mail
from django.http import HttpResponse
from django.test import override_settings
from mock import patch
from typing import Any, Dict, List, Mapping

from zerver.lib.actions import do_change_stream_invite_only
from zerver.models import get_realm, get_stream, \
    Realm, Stream, UserProfile, get_user, get_bot_services, Service
from zerver.lib.test_classes import ZulipTestCase, UploadSerializeMixin
from zerver.lib.test_helpers import (
    avatar_disk_path, get_test_image_file, tornado_redirected_to_list,
)
from zerver.lib.integrations import EMBEDDED_BOTS
from zerver.lib.bot_lib import get_bot_handler

class BotTest(ZulipTestCase, UploadSerializeMixin):
    def assert_num_bots_equal(self, count):
        # type: (int) -> None
        result = self.client_get("/json/bots")
        self.assert_json_success(result)
        self.assertEqual(count, len(result.json()['bots']))

    @override_settings(REALMS_HAVE_SUBDOMAINS=True)
    def create_bot(self, **extras):
        # type: (**Any) -> Dict[str, Any]
        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
            'bot_type': '1',
        }
        bot_info.update(extras)
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_success(result)
        return result.json()

    def test_bot_domain(self):
        # type: () -> None
        self.login(self.example_email('hamlet'))
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
        self.login(self.example_email('hamlet'))
        self.assert_num_bots_equal(0)

        # Invalid username
        bot_info = dict(
            full_name='My bot name',
            short_name='@',
        )
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_error(result, 'Bad name or username')
        self.assert_num_bots_equal(0)

        # Empty username
        bot_info = dict(
            full_name='My bot name',
            short_name='',
        )
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_error(result, 'Bad name or username')
        self.assert_num_bots_equal(0)

    def test_add_bot_with_no_name(self):
        # type: () -> None
        self.login(self.example_email('hamlet'))
        self.assert_num_bots_equal(0)
        bot_info = dict(
            full_name='a',
            short_name='bot',
        )
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_error(result, 'Name too short!')
        self.assert_num_bots_equal(0)

    def test_add_bot(self):
        # type: () -> None
        self.login(self.example_email('hamlet'))
        self.assert_num_bots_equal(0)
        events = []  # type: List[Mapping[str, Any]]
        with tornado_redirected_to_list(events):
            result = self.create_bot()
        self.assert_num_bots_equal(1)

        email = 'hambot-bot@zulip.testserver'
        realm = get_realm('zulip')
        bot = get_user(email, realm)

        event = [e for e in events if e['event']['type'] == 'realm_bot'][0]
        self.assertEqual(
            dict(
                type='realm_bot',
                op='add',
                bot=dict(email='hambot-bot@zulip.testserver',
                         user_id=bot.id,
                         bot_type=bot.bot_type,
                         full_name='The Bot of Hamlet',
                         is_active=True,
                         api_key=result['api_key'],
                         avatar_url=result['avatar_url'],
                         default_sending_stream=None,
                         default_events_register_stream=None,
                         default_all_public_streams=False,
                         owner=self.example_email('hamlet'))
            ),
            event['event']
        )

        users_result = self.client_get('/json/users')
        members = ujson.loads(users_result.content)['members']
        bots = [m for m in members if m['email'] == 'hambot-bot@zulip.testserver']
        self.assertEqual(len(bots), 1)
        bot = bots[0]
        self.assertEqual(bot['bot_owner'], self.example_email('hamlet'))
        self.assertEqual(bot['user_id'], get_user(email, realm).id)

    @override_settings(REALMS_HAVE_SUBDOMAINS=True)
    def test_add_bot_with_username_in_use(self):
        # type: () -> None
        self.login(self.example_email('hamlet'))
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
        email = 'hambot-bot@zulip.testserver'
        realm = get_realm('zulip')
        self.login(self.example_email('hamlet'))
        self.assert_num_bots_equal(0)
        with get_test_image_file('img.png') as fp:
            self.create_bot(file=fp)
            profile = get_user(email, realm)
            # Make sure that avatar image that we've uploaded is same with avatar image in the server
            self.assertTrue(filecmp.cmp(fp.name,
                                        os.path.splitext(avatar_disk_path(profile))[0] +
                                        ".original"))
        self.assert_num_bots_equal(1)

        self.assertEqual(profile.avatar_source, UserProfile.AVATAR_FROM_USER)
        self.assertTrue(os.path.exists(avatar_disk_path(profile)))

    @override_settings(REALMS_HAVE_SUBDOMAINS=True)
    def test_add_bot_with_too_many_files(self):
        # type: () -> None
        self.login(self.example_email('hamlet'))
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
        email = 'hambot-bot@zulip.testserver'
        realm = get_realm('zulip')
        self.login(self.example_email('hamlet'))
        self.assert_num_bots_equal(0)
        result = self.create_bot(default_sending_stream='Denmark')
        self.assert_num_bots_equal(1)
        self.assertEqual(result['default_sending_stream'], 'Denmark')

        profile = get_user(email, realm)
        self.assertEqual(profile.default_sending_stream.name, 'Denmark')

    def test_add_bot_with_default_sending_stream_not_subscribed(self):
        # type: () -> None
        email = 'hambot-bot@zulip.testserver'
        realm = get_realm('zulip')
        self.login(self.example_email('hamlet'))
        self.assert_num_bots_equal(0)
        result = self.create_bot(default_sending_stream='Rome')
        self.assert_num_bots_equal(1)
        self.assertEqual(result['default_sending_stream'], 'Rome')

        profile = get_user(email, realm)
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
        self.login(self.example_email('hamlet'))

        # Normal user i.e. not a bot.
        request_data = {
            'principals': '["' + self.example_email('iago') + '"]'
        }
        events = []  # type: List[Mapping[str, Any]]
        with tornado_redirected_to_list(events):
            result = self.common_subscribe_to_streams(self.example_email('hamlet'), ['Rome'], request_data)
            self.assert_json_success(result)

        msg_event = [e for e in events if e['event']['type'] == 'message']
        self.assert_length(msg_event, 1)  # Notification message event is sent.

        # Create a bot.
        self.assert_num_bots_equal(0)
        result = self.create_bot()
        self.assert_num_bots_equal(1)

        # A bot
        bot_request_data = {
            'principals': '["hambot-bot@zulip.testserver"]'
        }
        events_bot = []  # type: List[Mapping[str, Any]]
        with tornado_redirected_to_list(events_bot):
            result = self.common_subscribe_to_streams(self.example_email('hamlet'), ['Rome'], bot_request_data)
            self.assert_json_success(result)

        # No notification message event or invitation email is sent because of bot.
        msg_event = [e for e in events_bot if e['event']['type'] == 'message']
        self.assert_length(msg_event, 0)
        self.assertEqual(len(events_bot), len(events) - 1)

        # Test runner automatically redirects all sent email to a dummy 'outbox'.
        self.assertEqual(len(mail.outbox), 0)

    def test_add_bot_with_default_sending_stream_private_allowed(self):
        # type: () -> None
        self.login(self.example_email('hamlet'))
        user_profile = self.example_user('hamlet')
        stream = get_stream("Denmark", user_profile.realm)
        self.subscribe(user_profile, stream.name)
        do_change_stream_invite_only(stream, True)

        self.assert_num_bots_equal(0)
        events = []  # type: List[Mapping[str, Any]]
        with tornado_redirected_to_list(events):
            result = self.create_bot(default_sending_stream='Denmark')
        self.assert_num_bots_equal(1)
        self.assertEqual(result['default_sending_stream'], 'Denmark')

        email = 'hambot-bot@zulip.testserver'
        realm = get_realm('zulip')
        profile = get_user(email, realm)
        self.assertEqual(profile.default_sending_stream.name, 'Denmark')

        event = [e for e in events if e['event']['type'] == 'realm_bot'][0]
        self.assertEqual(
            dict(
                type='realm_bot',
                op='add',
                bot=dict(email='hambot-bot@zulip.testserver',
                         user_id=profile.id,
                         full_name='The Bot of Hamlet',
                         bot_type=profile.bot_type,
                         is_active=True,
                         api_key=result['api_key'],
                         avatar_url=result['avatar_url'],
                         default_sending_stream='Denmark',
                         default_events_register_stream=None,
                         default_all_public_streams=False,
                         owner=self.example_email('hamlet'))
            ),
            event['event']
        )
        self.assertEqual(event['users'], {user_profile.id, })

    @override_settings(REALMS_HAVE_SUBDOMAINS=True)
    def test_add_bot_with_default_sending_stream_private_denied(self):
        # type: () -> None
        self.login(self.example_email('hamlet'))
        realm = self.example_user('hamlet').realm
        stream = get_stream("Denmark", realm)
        self.unsubscribe(self.example_user('hamlet'), "Denmark")
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
        bot_email = 'hambot-bot@zulip.testserver'
        bot_realm = get_realm('zulip')

        self.login(self.example_email('hamlet'))
        self.assert_num_bots_equal(0)
        result = self.create_bot(default_events_register_stream='Denmark')
        self.assert_num_bots_equal(1)
        self.assertEqual(result['default_events_register_stream'], 'Denmark')

        profile = get_user(bot_email, bot_realm)
        self.assertEqual(profile.default_events_register_stream.name, 'Denmark')

    def test_add_bot_with_default_events_register_stream_private_allowed(self):
        # type: () -> None
        self.login(self.example_email('hamlet'))
        user_profile = self.example_user('hamlet')
        stream = self.subscribe(user_profile, 'Denmark')
        do_change_stream_invite_only(stream, True)

        self.assert_num_bots_equal(0)
        events = []  # type: List[Mapping[str, Any]]
        with tornado_redirected_to_list(events):
            result = self.create_bot(default_events_register_stream='Denmark')
        self.assert_num_bots_equal(1)
        self.assertEqual(result['default_events_register_stream'], 'Denmark')

        bot_email = 'hambot-bot@zulip.testserver'
        bot_realm = get_realm('zulip')
        bot_profile = get_user(bot_email, bot_realm)
        self.assertEqual(bot_profile.default_events_register_stream.name, 'Denmark')

        event = [e for e in events if e['event']['type'] == 'realm_bot'][0]
        self.assertEqual(
            dict(
                type='realm_bot',
                op='add',
                bot=dict(email='hambot-bot@zulip.testserver',
                         full_name='The Bot of Hamlet',
                         user_id=bot_profile.id,
                         bot_type=bot_profile.bot_type,
                         is_active=True,
                         api_key=result['api_key'],
                         avatar_url=result['avatar_url'],
                         default_sending_stream=None,
                         default_events_register_stream='Denmark',
                         default_all_public_streams=False,
                         owner=self.example_email('hamlet'))
            ),
            event['event']
        )
        self.assertEqual(event['users'], {user_profile.id, })

    @override_settings(REALMS_HAVE_SUBDOMAINS=True)
    def test_add_bot_with_default_events_register_stream_private_denied(self):
        # type: () -> None
        self.login(self.example_email('hamlet'))
        realm = self.example_user('hamlet').realm
        stream = get_stream("Denmark", realm)
        self.unsubscribe(self.example_user('hamlet'), "Denmark")
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
        self.login(self.example_email('hamlet'))
        self.assert_num_bots_equal(0)
        result = self.create_bot(default_all_public_streams=ujson.dumps(True))
        self.assert_num_bots_equal(1)
        self.assertTrue(result['default_all_public_streams'])

        bot_email = 'hambot-bot@zulip.testserver'
        bot_realm = get_realm('zulip')
        profile = get_user(bot_email, bot_realm)
        self.assertEqual(profile.default_all_public_streams, True)

    def test_deactivate_bot(self):
        # type: () -> None
        self.login(self.example_email('hamlet'))
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
        self.login(self.example_email('hamlet'))
        self.assert_num_bots_equal(0)
        self.create_bot()
        self.assert_num_bots_equal(1)
        result = self.client_delete("/json/bots/bogus-bot@zulip.com")
        self.assert_json_error(result, 'No such bot')
        self.assert_num_bots_equal(1)

    def test_bot_deactivation_attacks(self):
        # type: () -> None
        """You cannot deactivate somebody else's bot."""
        self.login(self.example_email('hamlet'))
        self.assert_num_bots_equal(0)
        self.create_bot()
        self.assert_num_bots_equal(1)

        # Have Othello try to deactivate both Hamlet and
        # Hamlet's bot.
        self.login(self.example_email('othello'))

        # Can not deactivate a user as a bot
        result = self.client_delete("/json/bots/" + self.example_email("hamlet"))
        self.assert_json_error(result, 'No such bot')

        result = self.client_delete("/json/bots/hambot-bot@zulip.testserver")
        self.assert_json_error(result, 'Insufficient permission')

        # But we don't actually deactivate the other person's bot.
        self.login(self.example_email('hamlet'))
        self.assert_num_bots_equal(1)

        # Can not deactivate a bot as a user
        result = self.client_delete("/json/users/hambot-bot@zulip.testserver")
        self.assert_json_error(result, 'No such user')
        self.assert_num_bots_equal(1)

    def test_bot_permissions(self):
        # type: () -> None
        self.login(self.example_email('hamlet'))
        self.assert_num_bots_equal(0)
        self.create_bot()
        self.assert_num_bots_equal(1)

        # Have Othello try to mess with Hamlet's bots.
        self.login(self.example_email('othello'))

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
        bots = result.json()['bots']
        return bots[0]

    def test_update_api_key(self):
        # type: () -> None
        self.login(self.example_email('hamlet'))
        self.create_bot()
        bot = self.get_bot()
        old_api_key = bot['api_key']
        result = self.client_post('/json/bots/hambot-bot@zulip.testserver/api_key/regenerate')
        self.assert_json_success(result)
        new_api_key = result.json()['api_key']
        self.assertNotEqual(old_api_key, new_api_key)
        bot = self.get_bot()
        self.assertEqual(new_api_key, bot['api_key'])

    def test_update_api_key_for_invalid_user(self):
        # type: () -> None
        self.login(self.example_email('hamlet'))
        result = self.client_post('/json/bots/nonexistentuser@zulip.com/api_key/regenerate')
        self.assert_json_error(result, 'No such user')

    def test_add_bot_with_bot_type_default(self):
        # type: () -> None
        bot_email = 'hambot-bot@zulip.testserver'
        bot_realm = get_realm('zulip')

        self.login(self.example_email('hamlet'))
        self.assert_num_bots_equal(0)
        self.create_bot(bot_type=UserProfile.DEFAULT_BOT)
        self.assert_num_bots_equal(1)

        profile = get_user(bot_email, bot_realm)
        self.assertEqual(profile.bot_type, UserProfile.DEFAULT_BOT)

    def test_add_bot_with_bot_type_incoming_webhook(self):
        # type: () -> None
        bot_email = 'hambot-bot@zulip.testserver'
        bot_realm = get_realm('zulip')

        self.login(self.example_email('hamlet'))
        self.assert_num_bots_equal(0)
        self.create_bot(bot_type=UserProfile.INCOMING_WEBHOOK_BOT)
        self.assert_num_bots_equal(1)

        profile = get_user(bot_email, bot_realm)
        self.assertEqual(profile.bot_type, UserProfile.INCOMING_WEBHOOK_BOT)

    @override_settings(REALMS_HAVE_SUBDOMAINS=True)
    def test_add_bot_with_bot_type_invalid(self):
        # type: () -> None
        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
            'bot_type': 7,
        }

        self.login(self.example_email('hamlet'))
        self.assert_num_bots_equal(0)
        result = self.client_post("/json/bots", bot_info)
        self.assert_num_bots_equal(0)
        self.assert_json_error(result, 'Invalid bot type')

    @override_settings(REALMS_HAVE_SUBDOMAINS=True)
    def test_patch_bot_full_name(self):
        # type: () -> None
        self.login(self.example_email('hamlet'))
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

        self.assertEqual('Fred', result.json()['full_name'])

        bot = self.get_bot()
        self.assertEqual('Fred', bot['full_name'])

    @override_settings(REALMS_HAVE_SUBDOMAINS=True)
    def test_patch_bot_owner(self):
        # type: () -> None
        self.login(self.example_email('hamlet'))
        bot_info = {
            'full_name': u'The Bot of Hamlet',
            'short_name': u'hambot',
        }
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_success(result)
        bot_info = {
            'bot_owner': self.example_email('othello'),
        }
        result = self.client_patch("/json/bots/hambot-bot@zulip.testserver", bot_info)
        self.assert_json_success(result)

        # Test bot's owner has been changed successfully.
        self.assertEqual(result.json()['bot_owner'], self.example_email('othello'))

        self.login(self.example_email('othello'))
        bot = self.get_bot()
        self.assertEqual('The Bot of Hamlet', bot['full_name'])

    @override_settings(REALMS_HAVE_SUBDOMAINS=True)
    @override_settings(LOCAL_UPLOADS_DIR='var/bot_avatar')
    def test_patch_bot_avatar(self):
        # type: () -> None
        self.login(self.example_email('hamlet'))
        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
        }
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_success(result)

        bot_email = 'hambot-bot@zulip.testserver'
        bot_realm = get_realm('zulip')
        profile = get_user(bot_email, bot_realm)
        self.assertEqual(profile.avatar_source, UserProfile.AVATAR_FROM_GRAVATAR)

        # Try error case first (too many files):
        with get_test_image_file('img.png') as fp1, \
                get_test_image_file('img.gif') as fp2:
            result = self.client_patch_multipart(
                '/json/bots/hambot-bot@zulip.testserver',
                dict(file1=fp1, file2=fp2))
        self.assert_json_error(result, 'You may only upload one file at a time')

        profile = get_user(bot_email, bot_realm)
        self.assertEqual(profile.avatar_version, 1)

        # HAPPY PATH
        with get_test_image_file('img.png') as fp:
            result = self.client_patch_multipart(
                '/json/bots/hambot-bot@zulip.testserver',
                dict(file=fp))
            profile = get_user(bot_email, bot_realm)
            self.assertEqual(profile.avatar_version, 2)
            # Make sure that avatar image that we've uploaded is same with avatar image in the server
            self.assertTrue(filecmp.cmp(fp.name,
                                        os.path.splitext(avatar_disk_path(profile))[0] +
                                        ".original"))
        self.assert_json_success(result)

        self.assertEqual(profile.avatar_source, UserProfile.AVATAR_FROM_USER)
        self.assertTrue(os.path.exists(avatar_disk_path(profile)))

    @override_settings(REALMS_HAVE_SUBDOMAINS=True)
    def test_patch_bot_to_stream(self):
        # type: () -> None
        self.login(self.example_email('hamlet'))
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

        self.assertEqual('Denmark', result.json()['default_sending_stream'])

        bot = self.get_bot()
        self.assertEqual('Denmark', bot['default_sending_stream'])

    @override_settings(REALMS_HAVE_SUBDOMAINS=True)
    def test_patch_bot_to_stream_not_subscribed(self):
        # type: () -> None
        self.login(self.example_email('hamlet'))
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

        self.assertEqual('Rome', result.json()['default_sending_stream'])

        bot = self.get_bot()
        self.assertEqual('Rome', bot['default_sending_stream'])

    @override_settings(REALMS_HAVE_SUBDOMAINS=True)
    def test_patch_bot_to_stream_none(self):
        # type: () -> None
        self.login(self.example_email('hamlet'))
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

        bot_email = "hambot-bot@zulip.testserver"
        bot_realm = get_realm('zulip')
        default_sending_stream = get_user(bot_email, bot_realm).default_sending_stream
        self.assertEqual(None, default_sending_stream)

        bot = self.get_bot()
        self.assertEqual(None, bot['default_sending_stream'])

    @override_settings(REALMS_HAVE_SUBDOMAINS=True)
    def test_patch_bot_to_stream_private_allowed(self):
        # type: () -> None
        self.login(self.example_email('hamlet'))
        user_profile = self.example_user('hamlet')
        stream = self.subscribe(user_profile, "Denmark")
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

        self.assertEqual('Denmark', result.json()['default_sending_stream'])

        bot = self.get_bot()
        self.assertEqual('Denmark', bot['default_sending_stream'])

    @override_settings(REALMS_HAVE_SUBDOMAINS=True)
    def test_patch_bot_to_stream_private_denied(self):
        # type: () -> None
        self.login(self.example_email('hamlet'))
        realm = self.example_user('hamlet').realm
        stream = get_stream("Denmark", realm)
        self.unsubscribe(self.example_user('hamlet'), "Denmark")
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

    @override_settings(REALMS_HAVE_SUBDOMAINS=True)
    def test_patch_bot_to_stream_not_found(self):
        # type: () -> None
        self.login(self.example_email('hamlet'))
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

    @override_settings(REALMS_HAVE_SUBDOMAINS=True)
    def test_patch_bot_events_register_stream(self):
        # type: () -> None
        self.login(self.example_email('hamlet'))
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

        self.assertEqual('Denmark', result.json()['default_events_register_stream'])

        bot = self.get_bot()
        self.assertEqual('Denmark', bot['default_events_register_stream'])

    @override_settings(REALMS_HAVE_SUBDOMAINS=True)
    def test_patch_bot_events_register_stream_allowed(self):
        # type: () -> None
        self.login(self.example_email('hamlet'))
        user_profile = self.example_user('hamlet')
        stream = self.subscribe(user_profile, "Denmark")
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

        self.assertEqual('Denmark', result.json()['default_events_register_stream'])

        bot = self.get_bot()
        self.assertEqual('Denmark', bot['default_events_register_stream'])

    @override_settings(REALMS_HAVE_SUBDOMAINS=True)
    def test_patch_bot_events_register_stream_denied(self):
        # type: () -> None
        self.login(self.example_email('hamlet'))
        realm = self.example_user('hamlet').realm
        stream = get_stream("Denmark", realm)
        self.unsubscribe(self.example_user('hamlet'), "Denmark")
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

    @override_settings(REALMS_HAVE_SUBDOMAINS=True)
    def test_patch_bot_events_register_stream_none(self):
        # type: () -> None
        self.login(self.example_email('hamlet'))
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

        bot_email = "hambot-bot@zulip.testserver"
        bot_realm = get_realm('zulip')
        default_events_register_stream = get_user(bot_email, bot_realm).default_events_register_stream
        self.assertEqual(None, default_events_register_stream)

        bot = self.get_bot()
        self.assertEqual(None, bot['default_events_register_stream'])

    @override_settings(REALMS_HAVE_SUBDOMAINS=True)
    def test_patch_bot_events_register_stream_not_found(self):
        # type: () -> None
        self.login(self.example_email('hamlet'))
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

    @override_settings(REALMS_HAVE_SUBDOMAINS=True)
    def test_patch_bot_default_all_public_streams_true(self):
        # type: () -> None
        self.login(self.example_email('hamlet'))
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

        self.assertEqual(result.json()['default_all_public_streams'], True)

        bot = self.get_bot()
        self.assertEqual(bot['default_all_public_streams'], True)

    @override_settings(REALMS_HAVE_SUBDOMAINS=True)
    def test_patch_bot_default_all_public_streams_false(self):
        # type: () -> None
        self.login(self.example_email('hamlet'))
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

        self.assertEqual(result.json()['default_all_public_streams'], False)

        bot = self.get_bot()
        self.assertEqual(bot['default_all_public_streams'], False)

    @override_settings(REALMS_HAVE_SUBDOMAINS=True)
    def test_patch_bot_via_post(self):
        # type: () -> None
        self.login(self.example_email('hamlet'))
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

        self.assertEqual('Fred', result.json()['full_name'])

        bot = self.get_bot()
        self.assertEqual('Fred', bot['full_name'])

    @override_settings(REALMS_HAVE_SUBDOMAINS=True)
    def test_patch_bogus_bot(self):
        # type: () -> None
        """Deleting a bogus bot will succeed silently."""
        self.login(self.example_email('hamlet'))
        self.create_bot()
        bot_info = {
            'full_name': 'Fred',
        }
        result = self.client_patch("/json/bots/nonexistent-bot@zulip.com", bot_info)
        self.assert_json_error(result, 'No such user')
        self.assert_num_bots_equal(1)

    @override_settings(REALMS_HAVE_SUBDOMAINS=True)
    def test_create_outgoing_webhook_bot(self, **extras):
        # type: (**Any) -> None
        self.login(self.example_email('hamlet'))
        bot_info = {
            'full_name': 'Outgoing Webhook test bot',
            'short_name': 'outgoingservicebot',
            'bot_type': UserProfile.OUTGOING_WEBHOOK_BOT,
            'payload_url': ujson.dumps('http://127.0.0.1:5002/bots/followup'),
        }
        bot_info.update(extras)
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_success(result)

        bot_email = "outgoingservicebot-bot@zulip.testserver"
        bot_realm = get_realm('zulip')
        bot = get_user(bot_email, bot_realm)
        services = get_bot_services(bot.id)
        service = services[0]

        self.assertEqual(len(services), 1)
        self.assertEqual(service.name, "outgoingservicebot")
        self.assertEqual(service.base_url, "http://127.0.0.1:5002/bots/followup")
        self.assertEqual(service.user_profile, bot)

        # invalid URL test case.
        bot_info['payload_url'] = ujson.dumps('http://127.0.0.:5002/bots/followup')
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_error(result, "Enter a valid URL.")

    @override_settings(REALMS_HAVE_SUBDOMAINS=True)
    def test_get_bot_handler(self):
        # type: () -> None
        # Test for valid service.
        test_service_name = 'converter'
        test_bot_handler = get_bot_handler(test_service_name)
        self.assertEqual(str(type(test_bot_handler)), "<class 'zulip_bots.bots.converter.converter.ConverterHandler'>")

        # Test for invalid service.
        test_service_name = "incorrect_bot_service_foo"
        test_bot_handler = get_bot_handler(test_service_name)
        self.assertEqual(test_bot_handler, None)

    def test_if_each_embedded_bot_service_exists(self):
        # type: () -> None
        # Each bot has its bot handler class name as Bot_nameHandler. For instance encrypt bot has
        # its class name as EncryptHandler.
        class_bot_handler = "<class 'zulip_bots.bots.{name}.{name}.{Name}Handler'>"
        for embedded_bot in EMBEDDED_BOTS:
            embedded_bot_handler = get_bot_handler(embedded_bot.name)
            bot_name = embedded_bot.name
            bot_handler_class_name = class_bot_handler.format(name=bot_name, Name=bot_name.title())
            self.assertEqual(str(type(embedded_bot_handler)), bot_handler_class_name)

    @override_settings(REALMS_HAVE_SUBDOMAINS=True)
    def test_outgoing_webhook_interface_type(self):
        # type: () -> None
        self.login(self.example_email('hamlet'))
        bot_info = {
            'full_name': 'Outgoing Webhook test bot',
            'short_name': 'outgoingservicebot',
            'bot_type': UserProfile.OUTGOING_WEBHOOK_BOT,
            'payload_url': ujson.dumps('http://127.0.0.1:5002/bots/followup'),
            'interface_type': -1,
        }
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_error(result, 'Invalid interface type')

        bot_info['interface_type'] = Service.GENERIC
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_success(result)
