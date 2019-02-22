
import filecmp
import os
import ujson

from django.core import mail
from django.test import override_settings
from mock import patch, MagicMock
from typing import Any, Dict, List, Mapping

from zerver.lib.actions import do_change_stream_invite_only, do_deactivate_user
from zerver.lib.bot_config import get_bot_config
from zerver.models import get_realm, get_stream, \
    Realm, UserProfile, get_user, get_bot_services, Service, \
    is_cross_realm_bot_email
from zerver.lib.test_classes import ZulipTestCase, UploadSerializeMixin
from zerver.lib.test_helpers import (
    avatar_disk_path,
    get_test_image_file,
    queries_captured,
    tornado_redirected_to_list,
)
from zerver.lib.integrations import EMBEDDED_BOTS
from zerver.lib.bot_lib import get_bot_handler

from zulip_bots.custom_exceptions import ConfigValidationError

class BotTest(ZulipTestCase, UploadSerializeMixin):
    def get_bot_user(self, email: str) -> UserProfile:
        realm = get_realm("zulip")
        bot = get_user(email, realm)
        return bot

    def assert_num_bots_equal(self, count: int) -> None:
        result = self.client_get("/json/bots")
        self.assert_json_success(result)
        self.assertEqual(count, len(result.json()['bots']))

    def create_bot(self, **extras: Any) -> Dict[str, Any]:
        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
            'bot_type': '1',
        }
        bot_info.update(extras)
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_success(result)
        return result.json()

    def test_bot_domain(self) -> None:
        self.login(self.example_email('hamlet'))
        self.create_bot()
        self.assertTrue(UserProfile.objects.filter(email='hambot-bot@zulip.testserver').exists())
        # The other cases are hard to test directly, since we don't allow creating bots from
        # the wrong subdomain, and because 'testserver.example.com' is not a valid domain for the bot's email.
        # So we just test the Raelm.get_bot_domain function.
        realm = get_realm('zulip')
        self.assertEqual(realm.get_bot_domain(), 'zulip.testserver')

    def deactivate_bot(self) -> None:
        email = 'hambot-bot@zulip.testserver'
        result = self.client_delete("/json/bots/{}".format(self.get_bot_user(email).id))
        self.assert_json_success(result)

    def test_add_bot_with_bad_username(self) -> None:
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

    def test_add_bot_with_no_name(self) -> None:
        self.login(self.example_email('hamlet'))
        self.assert_num_bots_equal(0)
        bot_info = dict(
            full_name='a',
            short_name='bot',
        )
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_error(result, 'Name too short!')
        self.assert_num_bots_equal(0)

    def test_json_users_with_bots(self) -> None:
        hamlet = self.example_user('hamlet')
        self.login(hamlet.email)
        self.assert_num_bots_equal(0)

        num_bots = 3
        for i in range(num_bots):
            full_name = 'Bot %d' % (i,)
            short_name = 'bot-%d' % (i,)
            bot_info = dict(
                full_name=full_name,
                short_name=short_name,
                bot_type=1
            )
            result = self.client_post("/json/bots", bot_info)
            self.assert_json_success(result)

        self.assert_num_bots_equal(num_bots)

        with queries_captured() as queries:
            users_result = self.client_get('/json/users')

        self.assert_json_success(users_result)

        self.assert_length(queries, 3)

    def test_add_bot(self) -> None:
        self.login(self.example_email('hamlet'))
        self.assert_num_bots_equal(0)
        events = []  # type: List[Mapping[str, Any]]
        with tornado_redirected_to_list(events):
            result = self.create_bot()
        self.assert_num_bots_equal(1)

        email = 'hambot-bot@zulip.testserver'
        bot = self.get_bot_user(email)

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
                         services=[],
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
        self.assertEqual(bot['user_id'], self.get_bot_user(email).id)

    def test_add_bot_with_username_in_use(self) -> None:
        self.login(self.example_email('hamlet'))
        self.assert_num_bots_equal(0)
        result = self.create_bot()
        self.assert_num_bots_equal(1)

        # The short_name is used in the email, which we call
        # "Username" for legacy reasons.
        bot_info = dict(
            full_name='whatever',
            short_name='hambot',
        )
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_error(result, 'Username already in use')

        dup_full_name = 'The Bot of Hamlet'

        bot_info = dict(
            full_name=dup_full_name,
            short_name='whatever',
        )
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_error(result, 'Name is already in use!')

    def test_add_bot_with_user_avatar(self) -> None:
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

    def test_add_bot_with_too_many_files(self) -> None:
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

    def test_add_bot_with_default_sending_stream(self) -> None:
        email = 'hambot-bot@zulip.testserver'
        realm = get_realm('zulip')
        self.login(self.example_email('hamlet'))
        self.assert_num_bots_equal(0)
        result = self.create_bot(default_sending_stream='Denmark')
        self.assert_num_bots_equal(1)
        self.assertEqual(result['default_sending_stream'], 'Denmark')

        profile = get_user(email, realm)
        assert(profile.default_sending_stream is not None)
        self.assertEqual(profile.default_sending_stream.name, 'Denmark')

    def test_add_bot_with_default_sending_stream_not_subscribed(self) -> None:
        email = 'hambot-bot@zulip.testserver'
        realm = get_realm('zulip')
        self.login(self.example_email('hamlet'))
        self.assert_num_bots_equal(0)
        result = self.create_bot(default_sending_stream='Rome')
        self.assert_num_bots_equal(1)
        self.assertEqual(result['default_sending_stream'], 'Rome')

        profile = get_user(email, realm)
        assert(profile.default_sending_stream is not None)
        self.assertEqual(profile.default_sending_stream.name, 'Rome')

    def test_bot_add_subscription(self) -> None:
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

    def test_add_bot_with_default_sending_stream_private_allowed(self) -> None:
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
        assert(profile.default_sending_stream is not None)
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
                         services=[],
                         owner=self.example_email('hamlet'))
            ),
            event['event']
        )
        self.assertEqual(event['users'], {user_profile.id, })

    def test_add_bot_with_default_sending_stream_private_denied(self) -> None:
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

    def test_add_bot_with_default_events_register_stream(self) -> None:
        bot_email = 'hambot-bot@zulip.testserver'
        bot_realm = get_realm('zulip')

        self.login(self.example_email('hamlet'))
        self.assert_num_bots_equal(0)
        result = self.create_bot(default_events_register_stream='Denmark')
        self.assert_num_bots_equal(1)
        self.assertEqual(result['default_events_register_stream'], 'Denmark')

        profile = get_user(bot_email, bot_realm)
        assert(profile.default_events_register_stream is not None)
        self.assertEqual(profile.default_events_register_stream.name, 'Denmark')

    def test_add_bot_with_default_events_register_stream_private_allowed(self) -> None:
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
        assert(bot_profile.default_events_register_stream is not None)
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
                         services=[],
                         owner=self.example_email('hamlet'))
            ),
            event['event']
        )
        self.assertEqual(event['users'], {user_profile.id, })

    def test_add_bot_with_default_events_register_stream_private_denied(self) -> None:
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

    def test_add_bot_with_default_all_public_streams(self) -> None:
        self.login(self.example_email('hamlet'))
        self.assert_num_bots_equal(0)
        result = self.create_bot(default_all_public_streams=ujson.dumps(True))
        self.assert_num_bots_equal(1)
        self.assertTrue(result['default_all_public_streams'])

        bot_email = 'hambot-bot@zulip.testserver'
        bot_realm = get_realm('zulip')
        profile = get_user(bot_email, bot_realm)
        self.assertEqual(profile.default_all_public_streams, True)

    def test_deactivate_bot(self) -> None:
        self.login(self.example_email('hamlet'))
        self.assert_num_bots_equal(0)
        self.create_bot()
        self.assert_num_bots_equal(1)
        self.deactivate_bot()
        # You can deactivate the same bot twice.
        self.deactivate_bot()
        self.assert_num_bots_equal(0)

    def test_deactivate_bogus_bot(self) -> None:
        """Deleting a bogus bot will succeed silently."""
        self.login(self.example_email('hamlet'))
        self.assert_num_bots_equal(0)
        self.create_bot()
        self.assert_num_bots_equal(1)
        invalid_user_id = 1000
        result = self.client_delete("/json/bots/{}".format(invalid_user_id))
        self.assert_json_error(result, 'No such bot')
        self.assert_num_bots_equal(1)

    def test_deactivate_bot_with_owner_deactivation(self) -> None:
        email = self.example_email("hamlet")
        user = self.example_user('hamlet')
        self.login(email)

        bot_info = {
            'full_name': u'The Bot of Hamlet',
            'short_name': u'hambot',
        }
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_success(result)

        bot_info = {
            'full_name': u'The Another Bot of Hamlet',
            'short_name': u'hambot-another',
        }
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_success(result)

        all_bots = UserProfile.objects.filter(is_bot=True, bot_owner=user, is_active=True)
        bots = [bot for bot in all_bots]
        self.assertEqual(len(bots), 2)

        result = self.client_delete('/json/users/me')
        self.assert_json_success(result)
        user = self.example_user('hamlet')
        self.assertFalse(user.is_active)

        self.login(self.example_email("iago"))
        all_bots = UserProfile.objects.filter(is_bot=True, bot_owner=user, is_active=True)
        bots = [bot for bot in all_bots]
        self.assertEqual(len(bots), 0)

    def test_cannot_deactivate_other_realm_bot(self) -> None:
        realm = get_realm("zephyr")
        self.login(self.mit_email("starnine"), realm=realm)
        bot_info = {
            'full_name': 'The Bot in zephyr',
            'short_name': 'starn-bot',
            'bot_type': '1',
        }
        result = self.client_post("/json/bots", bot_info, subdomain="zephyr")
        self.assert_json_success(result)
        result = self.client_get("/json/bots", subdomain="zephyr")
        bot_email = result.json()['bots'][0]['username']
        bot = get_user(bot_email, realm)
        self.login(self.example_email("iago"))
        result = self.client_delete("/json/bots/{}".format(bot.id))
        self.assert_json_error(result, 'No such bot')

    def test_bot_deactivation_attacks(self) -> None:
        """You cannot deactivate somebody else's bot."""
        self.login(self.example_email('hamlet'))
        self.assert_num_bots_equal(0)
        self.create_bot()
        self.assert_num_bots_equal(1)

        # Have Othello try to deactivate both Hamlet and
        # Hamlet's bot.
        self.login(self.example_email('othello'))

        # Cannot deactivate a user as a bot
        result = self.client_delete("/json/bots/{}".format(self.example_user("hamlet").id))
        self.assert_json_error(result, 'No such bot')

        email = 'hambot-bot@zulip.testserver'
        result = self.client_delete("/json/bots/{}".format(self.get_bot_user(email).id))
        self.assert_json_error(result, 'Insufficient permission')

        # But we don't actually deactivate the other person's bot.
        self.login(self.example_email('hamlet'))
        self.assert_num_bots_equal(1)

        # Cannot deactivate a bot as a user
        result = self.client_delete("/json/users/{}".format(self.get_bot_user(email).id))
        self.assert_json_error(result, 'No such user')
        self.assert_num_bots_equal(1)

    def test_bot_permissions(self) -> None:
        self.login(self.example_email('hamlet'))
        self.assert_num_bots_equal(0)
        self.create_bot()
        self.assert_num_bots_equal(1)

        # Have Othello try to mess with Hamlet's bots.
        self.login(self.example_email('othello'))
        email = 'hambot-bot@zulip.testserver'

        result = self.client_post("/json/bots/{}/api_key/regenerate".format(self.get_bot_user(email).id))
        self.assert_json_error(result, 'Insufficient permission')

        bot_info = {
            'full_name': 'Fred',
        }
        result = self.client_patch("/json/bots/{}".format(self.get_bot_user(email).id), bot_info)
        self.assert_json_error(result, 'Insufficient permission')

    def get_bot(self) -> Dict[str, Any]:
        result = self.client_get("/json/bots")
        bots = result.json()['bots']
        return bots[0]

    def test_update_api_key(self) -> None:
        self.login(self.example_email('hamlet'))
        self.create_bot()
        bot = self.get_bot()
        old_api_key = bot['api_key']
        email = 'hambot-bot@zulip.testserver'
        result = self.client_post('/json/bots/{}/api_key/regenerate'.format(self.get_bot_user(email).id))
        self.assert_json_success(result)
        new_api_key = result.json()['api_key']
        self.assertNotEqual(old_api_key, new_api_key)
        bot = self.get_bot()
        self.assertEqual(new_api_key, bot['api_key'])

    def test_update_api_key_for_invalid_user(self) -> None:
        self.login(self.example_email('hamlet'))
        invalid_user_id = 1000
        result = self.client_post('/json/bots/{}/api_key/regenerate'.format(invalid_user_id))
        self.assert_json_error(result, 'No such bot')

    def test_add_bot_with_bot_type_default(self) -> None:
        bot_email = 'hambot-bot@zulip.testserver'
        bot_realm = get_realm('zulip')

        self.login(self.example_email('hamlet'))
        self.assert_num_bots_equal(0)
        self.create_bot(bot_type=UserProfile.DEFAULT_BOT)
        self.assert_num_bots_equal(1)

        profile = get_user(bot_email, bot_realm)
        self.assertEqual(profile.bot_type, UserProfile.DEFAULT_BOT)

    def test_add_bot_with_bot_type_incoming_webhook(self) -> None:
        bot_email = 'hambot-bot@zulip.testserver'
        bot_realm = get_realm('zulip')

        self.login(self.example_email('hamlet'))
        self.assert_num_bots_equal(0)
        self.create_bot(bot_type=UserProfile.INCOMING_WEBHOOK_BOT)
        self.assert_num_bots_equal(1)

        profile = get_user(bot_email, bot_realm)
        self.assertEqual(profile.bot_type, UserProfile.INCOMING_WEBHOOK_BOT)

    def test_add_bot_with_bot_type_invalid(self) -> None:
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

    def test_no_generic_bots_allowed_for_non_admins(self) -> None:
        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
            'bot_type': 1,
        }
        bot_email = 'hambot-bot@zulip.testserver'
        bot_realm = get_realm('zulip')
        bot_realm.bot_creation_policy = Realm.BOT_CREATION_LIMIT_GENERIC_BOTS
        bot_realm.save(update_fields=['bot_creation_policy'])

        # A regular user cannot create a generic bot
        self.login(self.example_email('hamlet'))
        self.assert_num_bots_equal(0)
        result = self.client_post("/json/bots", bot_info)
        self.assert_num_bots_equal(0)
        self.assert_json_error(result, 'Must be an organization administrator')

        # But can create an incoming webhook
        self.assert_num_bots_equal(0)
        self.create_bot(bot_type=UserProfile.INCOMING_WEBHOOK_BOT)
        self.assert_num_bots_equal(1)
        profile = get_user(bot_email, bot_realm)
        self.assertEqual(profile.bot_type, UserProfile.INCOMING_WEBHOOK_BOT)

    def test_no_generic_bot_reactivation_allowed_for_non_admins(self) -> None:
        self.login(self.example_email('hamlet'))
        self.create_bot(bot_type=UserProfile.DEFAULT_BOT)

        bot_realm = get_realm('zulip')
        bot_realm.bot_creation_policy = Realm.BOT_CREATION_LIMIT_GENERIC_BOTS
        bot_realm.save(update_fields=['bot_creation_policy'])

        bot_email = 'hambot-bot@zulip.testserver'
        bot_user = get_user(bot_email, bot_realm)
        do_deactivate_user(bot_user)

        # A regular user cannot reactivate a generic bot
        self.assert_num_bots_equal(0)
        result = self.client_post("/json/users/%s/reactivate" % (bot_user.id,))
        self.assert_json_error(result, 'Must be an organization administrator')
        self.assert_num_bots_equal(0)

    def test_no_generic_bots_allowed_for_admins(self) -> None:
        bot_email = 'hambot-bot@zulip.testserver'
        bot_realm = get_realm('zulip')
        bot_realm.bot_creation_policy = Realm.BOT_CREATION_LIMIT_GENERIC_BOTS
        bot_realm.save(update_fields=['bot_creation_policy'])

        # An administrator can create any type of bot
        self.login(self.example_email('iago'))
        self.assert_num_bots_equal(0)
        self.create_bot(bot_type=UserProfile.DEFAULT_BOT)
        self.assert_num_bots_equal(1)
        profile = get_user(bot_email, bot_realm)
        self.assertEqual(profile.bot_type, UserProfile.DEFAULT_BOT)

    def test_no_bots_allowed_for_non_admins(self) -> None:
        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
            'bot_type': 1,
        }
        bot_realm = get_realm('zulip')
        bot_realm.bot_creation_policy = Realm.BOT_CREATION_ADMINS_ONLY
        bot_realm.save(update_fields=['bot_creation_policy'])

        # A regular user cannot create a generic bot
        self.login(self.example_email('hamlet'))
        self.assert_num_bots_equal(0)
        result = self.client_post("/json/bots", bot_info)
        self.assert_num_bots_equal(0)
        self.assert_json_error(result, 'Must be an organization administrator')

        # Also, a regular user cannot create a incoming bot
        bot_info['bot_type'] = 2
        self.login(self.example_email('hamlet'))
        self.assert_num_bots_equal(0)
        result = self.client_post("/json/bots", bot_info)
        self.assert_num_bots_equal(0)
        self.assert_json_error(result, 'Must be an organization administrator')

    def test_no_bots_allowed_for_admins(self) -> None:
        bot_email = 'hambot-bot@zulip.testserver'
        bot_realm = get_realm('zulip')
        bot_realm.bot_creation_policy = Realm.BOT_CREATION_ADMINS_ONLY
        bot_realm.save(update_fields=['bot_creation_policy'])

        # An administrator can create any type of bot
        self.login(self.example_email('iago'))
        self.assert_num_bots_equal(0)
        self.create_bot(bot_type=UserProfile.DEFAULT_BOT)
        self.assert_num_bots_equal(1)
        profile = get_user(bot_email, bot_realm)
        self.assertEqual(profile.bot_type, UserProfile.DEFAULT_BOT)

    def test_patch_bot_full_name(self) -> None:
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
        email = 'hambot-bot@zulip.testserver'
        result = self.client_patch("/json/bots/{}".format(self.get_bot_user(email).id), bot_info)
        self.assert_json_success(result)

        self.assertEqual('Fred', result.json()['full_name'])

        bot = self.get_bot()
        self.assertEqual('Fred', bot['full_name'])

    def test_patch_bot_full_name_in_use(self) -> None:
        self.login(self.example_email('hamlet'))

        original_name = 'The Bot of Hamlet'

        bot_info = {
            'full_name': original_name,
            'short_name': 'hambot',
        }
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_success(result)

        bot_email = 'hambot-bot@zulip.testserver'
        bot = self.get_bot_user(bot_email)
        url = "/json/bots/{}".format(bot.id)

        # It doesn't matter whether a name is taken by a human
        # or a bot, we can't use it.
        already_taken_name = self.example_user('cordelia').full_name

        bot_info = {
            'full_name': already_taken_name,
        }
        result = self.client_patch(url, bot_info)
        self.assert_json_error(result, "Name is already in use!")

        # We can use our own name (with extra whitespace), and the
        # server should silently do nothing.
        original_name_with_padding = '   ' + original_name + ' '
        bot_info = {
            'full_name': original_name_with_padding,
        }
        result = self.client_patch(url, bot_info)
        self.assert_json_success(result)

        bot = self.get_bot_user(bot_email)
        self.assertEqual(bot.full_name, original_name)

        # And let's do a sanity check with an actual name change
        # after our various attempts that either failed or did
        # nothing.
        bot_info = {
            'full_name': 'Hal',
        }
        result = self.client_patch(url, bot_info)
        self.assert_json_success(result)

        bot = self.get_bot_user(bot_email)
        self.assertEqual(bot.full_name, 'Hal')

    def test_patch_bot_full_name_non_bot(self) -> None:
        self.login(self.example_email('iago'))
        bot_info = {
            'full_name': 'Fred',
        }
        result = self.client_patch("/json/bots/{}".format(self.example_user("hamlet").id), bot_info)
        self.assert_json_error(result, "No such bot")

    def test_patch_bot_owner(self) -> None:
        self.login(self.example_email('hamlet'))
        bot_info = {
            'full_name': u'The Bot of Hamlet',
            'short_name': u'hambot',
        }
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_success(result)
        bot_info = {
            'bot_owner_id': self.example_user('othello').id,
        }
        email = 'hambot-bot@zulip.testserver'
        result = self.client_patch("/json/bots/{}".format(self.get_bot_user(email).id), bot_info)
        self.assert_json_success(result)

        # Test bot's owner has been changed successfully.
        self.assertEqual(result.json()['bot_owner'], self.example_email('othello'))

        self.login(self.example_email('othello'))
        bot = self.get_bot()
        self.assertEqual('The Bot of Hamlet', bot['full_name'])

    def test_patch_bot_owner_bad_user_id(self) -> None:
        self.login(self.example_email('hamlet'))
        self.create_bot()
        self.assert_num_bots_equal(1)

        email = 'hambot-bot@zulip.testserver'
        profile = get_user('hambot-bot@zulip.testserver', get_realm('zulip'))

        bad_bot_owner_id = 999999
        bot_info = {
            'bot_owner_id': bad_bot_owner_id,
        }
        result = self.client_patch("/json/bots/{}".format(self.get_bot_user(email).id), bot_info)
        self.assert_json_error(result, "Failed to change owner, no such user")
        profile = get_user('hambot-bot@zulip.testserver', get_realm('zulip'))
        self.assertEqual(profile.bot_owner, self.example_user("hamlet"))

    def test_patch_bot_owner_deactivated(self) -> None:
        self.login(self.example_email('hamlet'))
        self.create_bot()
        self.assert_num_bots_equal(1)

        target_user_profile = self.example_user("othello")
        do_deactivate_user(target_user_profile)
        target_user_profile = self.example_user('othello')
        self.assertFalse(target_user_profile.is_active)
        bot_info = {
            'bot_owner_id': self.example_user('othello').id,
        }

        email = 'hambot-bot@zulip.testserver'
        result = self.client_patch("/json/bots/{}".format(self.get_bot_user(email).id), bot_info)
        self.assert_json_error(result, "Failed to change owner, user is deactivated")
        profile = self.get_bot_user(email)
        self.assertEqual(profile.bot_owner, self.example_user("hamlet"))

    def test_patch_bot_owner_must_be_in_same_realm(self) -> None:
        self.login(self.example_email('hamlet'))
        self.create_bot()
        self.assert_num_bots_equal(1)

        bot_info = {
            'bot_owner_id': self.mit_user("starnine").id,
        }

        email = 'hambot-bot@zulip.testserver'
        result = self.client_patch("/json/bots/{}".format(self.get_bot_user(email).id), bot_info)
        self.assert_json_error(result, "Failed to change owner, no such user")
        profile = self.get_bot_user(email)
        self.assertEqual(profile.bot_owner, self.example_user("hamlet"))

    def test_patch_bot_owner_noop(self) -> None:
        self.login(self.example_email('hamlet'))
        self.create_bot()
        self.assert_num_bots_equal(1)

        bot_info = {
            'bot_owner_id': self.example_user('hamlet').id,
        }

        email = 'hambot-bot@zulip.testserver'
        result = self.client_patch("/json/bots/{}".format(self.get_bot_user(email).id), bot_info)

        # Check that we're still the owner
        self.assert_json_success(result)
        profile = self.get_bot_user(email)
        self.assertEqual(profile.bot_owner, self.example_user("hamlet"))

    def test_patch_bot_owner_a_bot(self) -> None:
        self.login(self.example_email('hamlet'))
        self.create_bot()
        self.assert_num_bots_equal(1)

        bot_info = {
            'full_name': u'Another Bot of Hamlet',
            'short_name': u'hamelbot',
        }
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_success(result)

        bot_info = {
            'bot_owner_id': self.get_bot_user('hamelbot-bot@zulip.testserver').id,
        }
        email = 'hambot-bot@zulip.testserver'
        result = self.client_patch("/json/bots/{}".format(self.get_bot_user(email).id), bot_info)
        self.assert_json_error(result, "Failed to change owner, bots can't own other bots")
        profile = get_user(email, get_realm('zulip'))
        self.assertEqual(profile.bot_owner, self.example_user("hamlet"))

    @override_settings(LOCAL_UPLOADS_DIR='var/bot_avatar')
    def test_patch_bot_avatar(self) -> None:
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

        email = 'hambot-bot@zulip.testserver'
        # Try error case first (too many files):
        with get_test_image_file('img.png') as fp1, \
                get_test_image_file('img.gif') as fp2:
            result = self.client_patch_multipart(
                '/json/bots/{}'.format(self.get_bot_user(email).id),
                dict(file1=fp1, file2=fp2))
        self.assert_json_error(result, 'You may only upload one file at a time')

        profile = get_user(bot_email, bot_realm)
        self.assertEqual(profile.avatar_version, 1)

        # HAPPY PATH
        with get_test_image_file('img.png') as fp:
            result = self.client_patch_multipart(
                '/json/bots/{}'.format(self.get_bot_user(email).id),
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

    def test_patch_bot_to_stream(self) -> None:
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
        email = 'hambot-bot@zulip.testserver'
        result = self.client_patch("/json/bots/{}".format(self.get_bot_user(email).id), bot_info)
        self.assert_json_success(result)

        self.assertEqual('Denmark', result.json()['default_sending_stream'])

        bot = self.get_bot()
        self.assertEqual('Denmark', bot['default_sending_stream'])

    def test_patch_bot_to_stream_not_subscribed(self) -> None:
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
        email = 'hambot-bot@zulip.testserver'
        result = self.client_patch("/json/bots/{}".format(self.get_bot_user(email).id), bot_info)
        self.assert_json_success(result)

        self.assertEqual('Rome', result.json()['default_sending_stream'])

        bot = self.get_bot()
        self.assertEqual('Rome', bot['default_sending_stream'])

    def test_patch_bot_to_stream_none(self) -> None:
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
        email = 'hambot-bot@zulip.testserver'
        result = self.client_patch("/json/bots/{}".format(self.get_bot_user(email).id), bot_info)
        self.assert_json_success(result)

        bot_email = "hambot-bot@zulip.testserver"
        bot_realm = get_realm('zulip')
        default_sending_stream = get_user(bot_email, bot_realm).default_sending_stream
        self.assertEqual(None, default_sending_stream)

        bot = self.get_bot()
        self.assertEqual(None, bot['default_sending_stream'])

    def test_patch_bot_to_stream_private_allowed(self) -> None:
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
        email = 'hambot-bot@zulip.testserver'
        result = self.client_patch("/json/bots/{}".format(self.get_bot_user(email).id), bot_info)
        self.assert_json_success(result)

        self.assertEqual('Denmark', result.json()['default_sending_stream'])

        bot = self.get_bot()
        self.assertEqual('Denmark', bot['default_sending_stream'])

    def test_patch_bot_to_stream_private_denied(self) -> None:
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
        email = 'hambot-bot@zulip.testserver'
        result = self.client_patch("/json/bots/{}".format(self.get_bot_user(email).id), bot_info)
        self.assert_json_error(result, "Invalid stream name 'Denmark'")

    def test_patch_bot_to_stream_not_found(self) -> None:
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
        email = 'hambot-bot@zulip.testserver'
        result = self.client_patch("/json/bots/{}".format(self.get_bot_user(email).id), bot_info)
        self.assert_json_error(result, "Invalid stream name 'missing'")

    def test_patch_bot_events_register_stream(self) -> None:
        hamlet = self.example_user('hamlet')
        self.login(hamlet.email)
        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
        }
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_success(result)

        email = 'hambot-bot@zulip.testserver'
        bot_user = self.get_bot_user(email)
        url = "/json/bots/{}".format(bot_user.id)

        # Successfully give the bot a default stream.
        stream_name = 'Denmark'
        bot_info = dict(default_events_register_stream=stream_name)
        result = self.client_patch(url, bot_info)
        self.assert_json_success(result)

        self.assertEqual(stream_name, result.json()['default_events_register_stream'])

        bot = self.get_bot()
        self.assertEqual(stream_name, bot['default_events_register_stream'])

        # Make sure we are locked out of an unsubscribed private stream.
        # We'll subscribe the bot but not the owner (since the check is
        # on owner).
        stream_name = 'private_stream'
        self.make_stream(stream_name, hamlet.realm, invite_only=True)
        self.subscribe(bot_user, stream_name)
        bot_info = dict(default_events_register_stream=stream_name)
        result = self.client_patch(url, bot_info)
        self.assert_json_error_contains(result, 'Invalid stream name')

        # Subscribing the owner allows us to patch the stream.
        self.subscribe(hamlet, stream_name)
        bot_info = dict(default_events_register_stream=stream_name)
        result = self.client_patch(url, bot_info)
        self.assert_json_success(result)

        # Make sure the bot cannot create their own default stream.
        url = "/api/v1/bots/{}".format(bot_user.id)
        result = self.api_patch(bot_user.email, url, bot_info)
        self.assert_json_error_contains(result, 'endpoint does not accept')

    def test_patch_bot_events_register_stream_allowed(self) -> None:
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
        email = 'hambot-bot@zulip.testserver'
        result = self.client_patch("/json/bots/{}".format(self.get_bot_user(email).id), bot_info)
        self.assert_json_success(result)

        self.assertEqual('Denmark', result.json()['default_events_register_stream'])

        bot = self.get_bot()
        self.assertEqual('Denmark', bot['default_events_register_stream'])

    def test_patch_bot_events_register_stream_denied(self) -> None:
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
        email = 'hambot-bot@zulip.testserver'
        result = self.client_patch("/json/bots/{}".format(self.get_bot_user(email).id), bot_info)
        self.assert_json_error(result, "Invalid stream name 'Denmark'")

    def test_patch_bot_events_register_stream_none(self) -> None:
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
        email = 'hambot-bot@zulip.testserver'
        result = self.client_patch("/json/bots/{}".format(self.get_bot_user(email).id), bot_info)
        self.assert_json_success(result)

        bot_email = "hambot-bot@zulip.testserver"
        bot_realm = get_realm('zulip')
        default_events_register_stream = get_user(bot_email, bot_realm).default_events_register_stream
        self.assertEqual(None, default_events_register_stream)

        bot = self.get_bot()
        self.assertEqual(None, bot['default_events_register_stream'])

    def test_patch_bot_events_register_stream_not_found(self) -> None:
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
        email = 'hambot-bot@zulip.testserver'
        result = self.client_patch("/json/bots/{}".format(self.get_bot_user(email).id), bot_info)
        self.assert_json_error(result, "Invalid stream name 'missing'")

    def test_patch_bot_default_all_public_streams_true(self) -> None:
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
        email = 'hambot-bot@zulip.testserver'
        result = self.client_patch("/json/bots/{}".format(self.get_bot_user(email).id), bot_info)
        self.assert_json_success(result)

        self.assertEqual(result.json()['default_all_public_streams'], True)

        bot = self.get_bot()
        self.assertEqual(bot['default_all_public_streams'], True)

    def test_patch_bot_default_all_public_streams_false(self) -> None:
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
        email = 'hambot-bot@zulip.testserver'
        result = self.client_patch("/json/bots/{}".format(self.get_bot_user(email).id), bot_info)
        self.assert_json_success(result)

        self.assertEqual(result.json()['default_all_public_streams'], False)

        bot = self.get_bot()
        self.assertEqual(bot['default_all_public_streams'], False)

    def test_patch_bot_via_post(self) -> None:
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
        email = 'hambot-bot@zulip.testserver'
        # Important: We intentionally use the wrong method, post, here.
        result = self.client_post("/json/bots/{}".format(self.get_bot_user(email).id),
                                  bot_info)
        self.assert_json_success(result)

        self.assertEqual('Fred', result.json()['full_name'])

        bot = self.get_bot()
        self.assertEqual('Fred', bot['full_name'])

    def test_patch_bogus_bot(self) -> None:
        """Deleting a bogus bot will succeed silently."""
        self.login(self.example_email('hamlet'))
        self.create_bot()
        bot_info = {
            'full_name': 'Fred',
        }
        invalid_user_id = 1000
        result = self.client_patch("/json/bots/{}".format(invalid_user_id), bot_info)
        self.assert_json_error(result, 'No such bot')
        self.assert_num_bots_equal(1)

    def test_patch_outgoing_webhook_bot(self) -> None:
        self.login(self.example_email('hamlet'))
        bot_info = {
            'full_name': u'The Bot of Hamlet',
            'short_name': u'hambot',
            'bot_type': UserProfile.OUTGOING_WEBHOOK_BOT,
            'payload_url': ujson.dumps("http://foo.bar.com"),
            'service_interface': Service.GENERIC,
        }
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_success(result)
        bot_info = {
            'service_payload_url': ujson.dumps("http://foo.bar2.com"),
            'service_interface': Service.SLACK,
        }
        email = 'hambot-bot@zulip.testserver'
        result = self.client_patch("/json/bots/{}".format(self.get_bot_user(email).id), bot_info)
        self.assert_json_success(result)

        service_interface = ujson.loads(result.content)['service_interface']
        self.assertEqual(service_interface, Service.SLACK)

        service_payload_url = ujson.loads(result.content)['service_payload_url']
        self.assertEqual(service_payload_url, "http://foo.bar2.com")

    @patch('zulip_bots.bots.giphy.giphy.GiphyHandler.validate_config')
    def test_patch_bot_config_data(self, mock_validate_config: MagicMock) -> None:
        self.create_test_bot('test', self.example_user("hamlet"),
                             full_name=u'Bot with config data',
                             bot_type=UserProfile.EMBEDDED_BOT,
                             service_name='giphy',
                             config_data=ujson.dumps({'key': '12345678'}))
        bot_info = {'config_data': ujson.dumps({'key': '87654321'})}
        email = 'test-bot@zulip.testserver'
        result = self.client_patch("/json/bots/{}".format(self.get_bot_user(email).id), bot_info)
        self.assert_json_success(result)
        config_data = ujson.loads(result.content)['config_data']
        self.assertEqual(config_data, ujson.loads(bot_info['config_data']))

    def test_outgoing_webhook_invalid_interface(self):
        # type: () -> None
        self.login(self.example_email('hamlet'))
        bot_info = {
            'full_name': 'Outgoing Webhook test bot',
            'short_name': 'outgoingservicebot',
            'bot_type': UserProfile.OUTGOING_WEBHOOK_BOT,
            'payload_url': ujson.dumps('http://127.0.0.1:5002'),
            'interface_type': -1,
        }
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_error(result, 'Invalid interface type')

        bot_info['interface_type'] = Service.GENERIC
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_success(result)

    def test_create_outgoing_webhook_bot(self, **extras: Any) -> None:
        self.login(self.example_email('hamlet'))
        bot_info = {
            'full_name': 'Outgoing Webhook test bot',
            'short_name': 'outgoingservicebot',
            'bot_type': UserProfile.OUTGOING_WEBHOOK_BOT,
            'payload_url': ujson.dumps('http://127.0.0.1:5002'),
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
        self.assertEqual(service.base_url, "http://127.0.0.1:5002")
        self.assertEqual(service.user_profile, bot)

        # invalid URL test case.
        bot_info['payload_url'] = ujson.dumps('http://127.0.0.:5002')
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_error(result, "payload_url is not a URL")

    def test_get_bot_handler(self) -> None:
        # Test for valid service.
        test_service_name = 'converter'
        test_bot_handler = get_bot_handler(test_service_name)
        self.assertEqual(str(type(test_bot_handler)), "<class 'zulip_bots.bots.converter.converter.ConverterHandler'>")

        # Test for invalid service.
        test_service_name = "incorrect_bot_service_foo"
        test_bot_handler = get_bot_handler(test_service_name)
        self.assertEqual(test_bot_handler, None)

    def test_if_each_embedded_bot_service_exists(self) -> None:
        for embedded_bot in EMBEDDED_BOTS:
            self.assertIsNotNone(get_bot_handler(embedded_bot.name))

    def test_outgoing_webhook_interface_type(self) -> None:
        self.login(self.example_email('hamlet'))
        bot_info = {
            'full_name': 'Outgoing Webhook test bot',
            'short_name': 'outgoingservicebot',
            'bot_type': UserProfile.OUTGOING_WEBHOOK_BOT,
            'payload_url': ujson.dumps('http://127.0.0.1:5002'),
            'interface_type': -1,
        }
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_error(result, 'Invalid interface type')

        bot_info['interface_type'] = Service.GENERIC
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_success(result)

    def test_create_embedded_bot_with_disabled_embedded_bots(self, **extras: Any) -> None:
        with self.settings(EMBEDDED_BOTS_ENABLED=False):
            self.create_test_bot(short_name='embeddedservicebot',
                                 user_profile=self.example_user("hamlet"),
                                 bot_type=UserProfile.EMBEDDED_BOT,
                                 service_name='followup',
                                 config_data=ujson.dumps({'key': 'value'}),
                                 assert_json_error_msg='Embedded bots are not enabled.',
                                 **extras)

    def test_create_embedded_bot(self, **extras: Any) -> None:
        bot_config_info = {'key': 'value'}
        self.create_test_bot(short_name='embeddedservicebot',
                             user_profile=self.example_user("hamlet"),
                             bot_type=UserProfile.EMBEDDED_BOT,
                             service_name='followup',
                             config_data=ujson.dumps(bot_config_info),
                             **extras)
        bot_email = "embeddedservicebot-bot@zulip.testserver"
        bot_realm = get_realm('zulip')
        bot = get_user(bot_email, bot_realm)
        services = get_bot_services(bot.id)
        service = services[0]
        bot_config = get_bot_config(bot)
        self.assertEqual(bot_config, bot_config_info)
        self.assertEqual(len(services), 1)
        self.assertEqual(service.name, "followup")
        self.assertEqual(service.user_profile, bot)

    def test_create_embedded_bot_with_incorrect_service_name(self, **extras: Any) -> None:
        self.create_test_bot(short_name='embeddedservicebot',
                             user_profile=self.example_user("hamlet"),
                             bot_type=UserProfile.EMBEDDED_BOT,
                             service_name='not_existing_service',
                             assert_json_error_msg='Invalid embedded bot name.',
                             **extras)

    def test_create_embedded_bot_with_invalid_config_value(self, **extras: Any) -> None:
        self.create_test_bot(short_name='embeddedservicebot',
                             user_profile=self.example_user("hamlet"),
                             service_name='followup',
                             config_data=ujson.dumps({'invalid': ['config', 'value']}),
                             assert_json_error_msg='config_data contains a value that is not a string',
                             **extras)

        # Test to create embedded bot with an incorrect config value
        incorrect_bot_config_info = {'key': 'incorrect key'}
        bot_info = {
            'full_name': 'Embedded test bot',
            'short_name': 'embeddedservicebot3',
            'bot_type': UserProfile.EMBEDDED_BOT,
            'service_name': 'giphy',
            'config_data': ujson.dumps(incorrect_bot_config_info)
        }
        bot_info.update(extras)
        with patch('zulip_bots.bots.giphy.giphy.GiphyHandler.validate_config', side_effect=ConfigValidationError):
            result = self.client_post("/json/bots", bot_info)
        self.assert_json_error(result, 'Invalid configuration data!')

    def test_is_cross_realm_bot_email(self) -> None:
        self.assertTrue(is_cross_realm_bot_email("notification-bot@zulip.com"))
        self.assertTrue(is_cross_realm_bot_email("notification-BOT@zulip.com"))
        self.assertFalse(is_cross_realm_bot_email("random-bot@zulip.com"))

        with self.settings(CROSS_REALM_BOT_EMAILS={"random-bot@zulip.com"}):
            self.assertTrue(is_cross_realm_bot_email("random-bot@zulip.com"))
            self.assertFalse(is_cross_realm_bot_email("notification-bot@zulip.com"))
