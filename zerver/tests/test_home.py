from __future__ import absolute_import
from __future__ import print_function

import ujson

from django.http import HttpResponse
from mock import patch
from six.moves import urllib
from typing import Any, Dict

from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_runner import slow
from zerver.models import get_realm, get_stream, get_user_profile_by_email

class HomeTest(ZulipTestCase):
    @slow('big method')
    def test_home(self):
        # type: () -> None

        # Keep this list sorted!!!
        html_bits = [
            'Compose your message here...',
            'Exclude messages with topic',
            'Get started',
            'Keyboard shortcuts',
            'Loading...',
            'Manage streams',
            'Narrow by topic',
            'Next message',
            'SHARE THE LOVE',
            'Search streams',
            'Welcome to Zulip',
            'pygments.css',
            'var page_params',
        ]

        # Keep this list sorted!!!
        expected_keys = [
            "alert_words",
            "attachments",
            "autoscroll_forever",
            "avatar_source",
            "avatar_url",
            "avatar_url_medium",
            "bot_list",
            "can_create_streams",
            "cross_realm_bots",
            "debug_mode",
            "default_desktop_notifications",
            "default_language",
            "default_language_name",
            "desktop_notifications_enabled",
            "development_environment",
            "domains",
            "email",
            "emoji_alt_code",
            "enable_digest_emails",
            "enable_offline_email_notifications",
            "enable_offline_push_notifications",
            "enable_online_push_notifications",
            "enter_sends",
            "event_queue_id",
            "first_in_realm",
            "fullname",
            "furthest_read_time",
            "has_mobile_devices",
            "have_initial_messages",
            "initial_pointer",
            "initial_presences",
            "initial_servertime",
            "is_admin",
            "is_zephyr_mirror_realm",
            "language_list",
            "language_list_dbl_col",
            "last_event_id",
            "left_side_userlist",
            "login_page",
            "mandatory_topics",
            "max_avatar_file_size",
            "max_icon_file_size",
            "max_message_id",
            "maxfilesize",
            "muted_topics",
            "name_changes_disabled",
            "narrow",
            "narrow_stream",
            "needs_tutorial",
            "neversubbed_info",
            "notifications_stream",
            "password_auth_enabled",
            "people_list",
            "pm_content_in_desktop_notifications",
            "poll_timeout",
            "prompt_for_invites",
            "realm_add_emoji_by_admins_only",
            "realm_allow_message_editing",
            "realm_authentication_methods",
            "realm_bot_domain",
            "realm_create_stream_by_admins_only",
            "realm_default_language",
            "realm_default_streams",
            "realm_email_changes_disabled",
            "realm_emoji",
            "realm_filters",
            "realm_icon_source",
            "realm_icon_url",
            "realm_invite_by_admins_only",
            "realm_invite_required",
            "realm_message_content_edit_limit_seconds",
            "realm_name",
            "realm_name_changes_disabled",
            "realm_presence_disabled",
            "realm_restricted_to_domain",
            "realm_uri",
            "realm_waiting_period_threshold",
            "referrals",
            "save_stacktraces",
            "server_generation",
            "server_uri",
            "share_the_love",
            "show_digest_email",
            "sounds_enabled",
            "stream_desktop_notifications_enabled",
            "stream_sounds_enabled",
            "subbed_info",
            "test_suite",
            "twenty_four_hour_time",
            "unread_count",
            "unsubbed_info",
            "use_websockets",
            "user_id",
            "zulip_version",
        ]

        email = "hamlet@zulip.com"

        # Verify fails if logged-out
        result = self.client_get('/')
        self.assertEqual(result.status_code, 302)

        self.login(email)

        # Create bot for bot_list testing. Must be done before fetching home_page.
        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
        }
        self.client_post("/json/bots", bot_info)

        # Verify succeeds once logged-in
        result = self._get_home_page(stream='Denmark')
        html = result.content.decode('utf-8')

        for html_bit in html_bits:
            if html_bit not in html:
                raise AssertionError('%s not in result' % (html_bit,))

        page_params = self._get_page_params(result)

        actual_keys = sorted([str(k) for k in page_params.keys()])

        self.assertEqual(actual_keys, expected_keys)

        # TODO: Inspect the page_params data further.
        # print(ujson.dumps(page_params, indent=2))
        bot_list_expected_keys = [
            'api_key',
            'avatar_url',
            'default_all_public_streams',
            'default_events_register_stream',
            'default_sending_stream',
            'email',
            'full_name',
            'is_active',
            'owner',
            'user_id',
        ]

        bot_list_actual_keys = sorted([str(key) for key in page_params['bot_list'][0].keys()])
        self.assertEqual(bot_list_actual_keys, bot_list_expected_keys)

    def _get_home_page(self, **kwargs):
        # type: (**Any) -> HttpResponse
        with \
                patch('zerver.lib.events.request_event_queue', return_value=42), \
                patch('zerver.lib.events.get_user_events', return_value=[]):
            result = self.client_get('/', dict(**kwargs))
        return result

    def _get_page_params(self, result):
        # type: (HttpResponse) -> Dict[str, Any]
        html = result.content.decode('utf-8')
        lines = html.split('\n')
        page_params_line = [l for l in lines if l.startswith('var page_params')][0]
        page_params_json = page_params_line.split(' = ')[1].rstrip(';')
        page_params = ujson.loads(page_params_json)
        return page_params

    def _sanity_check(self, result):
        # type: (HttpResponse) -> None
        '''
        Use this for tests that are geared toward specific edge cases, but
        which still want the home page to load properly.
        '''
        html = result.content.decode('utf-8')
        if 'Compose your message' not in html:
            raise AssertionError('Home page probably did not load.')

    def test_terms_of_service(self):
        # type: () -> None
        email = 'hamlet@zulip.com'
        self.login(email)

        for user_tos_version in [None, '1.1', '2.0.3.4']:
            user = get_user_profile_by_email(email)
            user.tos_version = user_tos_version
            user.save()

            with \
                    self.settings(TERMS_OF_SERVICE='whatever'), \
                    self.settings(TOS_VERSION='99.99'):

                result = self.client_get('/', dict(stream='Denmark'))

            html = result.content.decode('utf-8')
            self.assertIn('There are new Terms of Service', html)

    def test_bad_narrow(self):
        # type: () -> None
        email = 'hamlet@zulip.com'
        self.login(email)
        with patch('logging.exception') as mock:
            result = self._get_home_page(stream='Invalid Stream')
        mock.assert_called_once_with('Narrow parsing')
        self._sanity_check(result)

    def test_bad_pointer(self):
        # type: () -> None
        email = 'hamlet@zulip.com'
        user_profile = get_user_profile_by_email(email)
        user_profile.pointer = 999999
        user_profile.save()

        self.login(email)
        with patch('logging.warning') as mock:
            result = self._get_home_page()
        mock.assert_called_once_with('hamlet@zulip.com has invalid pointer 999999')
        self._sanity_check(result)

    def test_topic_narrow(self):
        # type: () -> None
        email = 'hamlet@zulip.com'
        self.login(email)
        result = self._get_home_page(stream='Denmark', topic='lunch')
        self._sanity_check(result)
        html = result.content.decode('utf-8')
        self.assertIn('lunch', html)

    def test_notifications_stream(self):
        # type: () -> None
        email = 'hamlet@zulip.com'
        realm = get_realm('zulip')
        realm.notifications_stream = get_stream('Denmark', realm)
        realm.save()
        self.login(email)
        result = self._get_home_page()
        page_params = self._get_page_params(result)
        self.assertEqual(page_params['notifications_stream'], 'Denmark')

    def test_people(self):
        # type: () -> None
        email = 'hamlet@zulip.com'
        self.login(email)
        result = self._get_home_page()
        page_params = self._get_page_params(result)
        for params in ['people_list', 'bot_list']:
            users = page_params['people_list']
            self.assertTrue(len(users) >= 3)
            for user in users:
                self.assertEqual(user['user_id'],
                                 get_user_profile_by_email(user['email']).id)

        cross_bots = page_params['cross_realm_bots']
        self.assertEqual(len(cross_bots), 2)
        cross_bots.sort(key=lambda d: d['email'])
        self.assertEqual(cross_bots, [
            dict(
                user_id=get_user_profile_by_email('feedback@zulip.com').id,
                is_admin=False,
                email='feedback@zulip.com',
                full_name='Zulip Feedback Bot',
                is_bot=True
            ),
            dict(
                user_id=get_user_profile_by_email('notification-bot@zulip.com').id,
                is_admin=False,
                email='notification-bot@zulip.com',
                full_name='Notification Bot',
                is_bot=True
            ),
        ])

    def test_new_stream(self):
        # type: () -> None
        email = 'hamlet@zulip.com'
        stream_name = 'New stream'
        self.subscribe_to_stream(email, stream_name)
        self.login(email)
        result = self._get_home_page(stream=stream_name)
        page_params = self._get_page_params(result)
        self.assertEqual(page_params['narrow_stream'], stream_name)
        self.assertEqual(page_params['narrow'], [dict(operator='stream', operand=stream_name)])
        self.assertEqual(page_params['initial_pointer'], -1)
        self.assertEqual(page_params['max_message_id'], -1)
        self.assertEqual(page_params['have_initial_messages'], False)

    def test_invites_by_admins_only(self):
        # type: () -> None
        email = 'hamlet@zulip.com'
        user_profile = get_user_profile_by_email(email)

        realm = user_profile.realm
        realm.invite_by_admins_only = True
        realm.save()

        self.login(email)
        self.assertFalse(user_profile.is_realm_admin)
        result = self._get_home_page()
        html = result.content.decode('utf-8')
        self.assertNotIn('Invite more users', html)

        user_profile.is_realm_admin = True
        user_profile.save()
        result = self._get_home_page()
        html = result.content.decode('utf-8')
        self.assertIn('Invite more users', html)

    def test_desktop_home(self):
        # type: () -> None
        email = 'hamlet@zulip.com'
        self.login(email)
        result = self.client_get("/desktop_home")
        self.assertEqual(result.status_code, 301)
        self.assertTrue(result["Location"].endswith("/desktop_home/"))
        result = self.client_get("/desktop_home/")
        self.assertEqual(result.status_code, 302)
        path = urllib.parse.urlparse(result['Location']).path
        self.assertEqual(path, "/")

    def test_generate_204(self):
        # type: () -> None
        email = 'hamlet@zulip.com'
        self.login(email)
        result = self.client_get("/api/v1/generate_204")
        self.assertEqual(result.status_code, 204)
