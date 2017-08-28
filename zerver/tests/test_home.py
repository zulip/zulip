from __future__ import absolute_import
from __future__ import print_function

import datetime
import os
import ujson

from django.http import HttpResponse
from mock import MagicMock, patch
from six.moves import urllib
from typing import Any, Dict, List

from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import (
    HostRequestMock, queries_captured, get_user_messages
)
from zerver.lib.soft_deactivation import do_soft_deactivate_users
from zerver.lib.test_runner import slow
from zerver.models import (
    get_realm, get_stream, get_user, UserProfile, UserMessage, Recipient
)
from zerver.views.home import home, sent_time_in_epoch_seconds

class HomeTest(ZulipTestCase):
    @slow('big method')
    def test_home(self):
        # type: () -> None

        # Keep this list sorted!!!
        html_bits = [
            'Compose your message here...',
            'Exclude messages with topic',
            'Keyboard shortcuts',
            'Loading...',
            'Manage streams',
            'Narrow by topic',
            'Next message',
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
            "can_create_streams",
            "cross_realm_bots",
            "custom_profile_fields",
            "debug_mode",
            "default_desktop_notifications",
            "default_language",
            "default_language_name",
            "development_environment",
            "email",
            "emoji_alt_code",
            "emojiset",
            "emojiset_choices",
            "enable_desktop_notifications",
            "enable_digest_emails",
            "enable_offline_email_notifications",
            "enable_offline_push_notifications",
            "enable_online_push_notifications",
            "enable_sounds",
            "enable_stream_desktop_notifications",
            "enable_stream_sounds",
            "enter_sends",
            "first_in_realm",
            "full_name",
            "furthest_read_time",
            "has_mobile_devices",
            "have_initial_messages",
            "high_contrast_mode",
            "hotspots",
            "initial_servertime",
            "is_admin",
            "language_list",
            "language_list_dbl_col",
            "last_event_id",
            "left_side_userlist",
            "login_page",
            "max_avatar_file_size",
            "max_icon_file_size",
            "max_message_id",
            "maxfilesize",
            "muted_topics",
            "narrow",
            "narrow_stream",
            "needs_tutorial",
            "never_subscribed",
            "password_min_length",
            "password_min_quality",
            "pm_content_in_desktop_notifications",
            "pointer",
            "poll_timeout",
            "presences",
            "prompt_for_invites",
            "queue_id",
            "realm_add_emoji_by_admins_only",
            "realm_allow_edit_history",
            "realm_allow_message_editing",
            "realm_authentication_methods",
            "realm_bot_domain",
            "realm_bots",
            "realm_create_stream_by_admins_only",
            "realm_default_language",
            "realm_default_streams",
            "realm_description",
            "realm_domains",
            "realm_email_changes_disabled",
            "realm_emoji",
            "realm_filters",
            "realm_icon_source",
            "realm_icon_url",
            "realm_inline_image_preview",
            "realm_inline_url_embed_preview",
            "realm_invite_by_admins_only",
            "realm_invite_required",
            "realm_is_zephyr_mirror_realm",
            "realm_mandatory_topics",
            "realm_message_content_edit_limit_seconds",
            "realm_message_retention_days",
            "realm_name",
            "realm_name_changes_disabled",
            "realm_notifications_stream_id",
            "realm_password_auth_enabled",
            "realm_presence_disabled",
            "realm_restricted_to_domain",
            "realm_show_digest_email",
            "realm_uri",
            "realm_users",
            "realm_waiting_period_threshold",
            "root_domain_uri",
            "save_stacktraces",
            "server_generation",
            "server_inline_image_preview",
            "server_inline_url_embed_preview",
            "subscriptions",
            "test_suite",
            "timezone",
            "twenty_four_hour_time",
            "unread_msgs",
            "unsubscribed",
            "use_websockets",
            "user_id",
            "zulip_version",
        ]

        email = self.example_email("hamlet")

        # Verify fails if logged-out
        result = self.client_get('/')
        self.assertEqual(result.status_code, 302)

        self.login(email)

        # Create bot for realm_bots testing. Must be done before fetching home_page.
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
        realm_bots_expected_keys = [
            'api_key',
            'avatar_url',
            'bot_type',
            'default_all_public_streams',
            'default_events_register_stream',
            'default_sending_stream',
            'email',
            'full_name',
            'is_active',
            'owner',
            'user_id',
        ]

        realm_bots_actual_keys = sorted([str(key) for key in page_params['realm_bots'][0].keys()])
        self.assertEqual(realm_bots_actual_keys, realm_bots_expected_keys)

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
        user = self.example_user('hamlet')
        email = user.email
        self.login(email)

        for user_tos_version in [None, '1.1', '2.0.3.4']:
            user.tos_version = user_tos_version
            user.save()

            with \
                    self.settings(TERMS_OF_SERVICE='whatever'), \
                    self.settings(TOS_VERSION='99.99'):

                result = self.client_get('/', dict(stream='Denmark'))

            html = result.content.decode('utf-8')
            self.assertIn('There are new Terms of Service', html)

    def test_terms_of_service_first_time_template(self):
        # type: () -> None
        user = self.example_user('hamlet')
        email = user.email
        self.login(email)

        user.tos_version = None
        user.save()

        with \
                self.settings(FIRST_TIME_TOS_TEMPLATE='hello.html'), \
                self.settings(TOS_VERSION='99.99'):
            result = self.client_post('/accounts/accept_terms/')
            self.assertEqual(result.status_code, 200)
            self.assert_in_response("I agree to the", result)
            self.assert_in_response("most productive group chat", result)

    def test_accept_terms_of_service(self):
        # type: () -> None
        email = self.example_email("hamlet")
        self.login(email)

        result = self.client_post('/accounts/accept_terms/')
        self.assertEqual(result.status_code, 200)
        self.assert_in_response("I agree to the", result)

        result = self.client_post('/accounts/accept_terms/', {'terms': True})
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result['Location'], '/')

    def test_bad_narrow(self):
        # type: () -> None
        email = self.example_email("hamlet")
        self.login(email)
        with patch('logging.exception') as mock:
            result = self._get_home_page(stream='Invalid Stream')
        mock.assert_called_once_with('Narrow parsing')
        self._sanity_check(result)

    def test_bad_pointer(self):
        # type: () -> None
        user_profile = self.example_user('hamlet')
        email = user_profile.email
        user_profile.pointer = 999999
        user_profile.save()

        self.login(email)
        with patch('logging.warning') as mock:
            result = self._get_home_page()
        mock.assert_called_once_with('hamlet@zulip.com has invalid pointer 999999')
        self._sanity_check(result)

    def test_topic_narrow(self):
        # type: () -> None
        email = self.example_email("hamlet")
        self.login(email)
        result = self._get_home_page(stream='Denmark', topic='lunch')
        self._sanity_check(result)
        html = result.content.decode('utf-8')
        self.assertIn('lunch', html)

    def test_notifications_stream(self):
        # type: () -> None
        email = self.example_email("hamlet")
        realm = get_realm('zulip')
        realm.notifications_stream = get_stream('Denmark', realm)
        realm.save()
        self.login(email)
        result = self._get_home_page()
        page_params = self._get_page_params(result)
        self.assertEqual(page_params['realm_notifications_stream_id'], get_stream('Denmark', realm).id)

    def test_people(self):
        # type: () -> None
        email = self.example_email('hamlet')
        realm = get_realm('zulip')
        self.login(email)
        result = self._get_home_page()
        page_params = self._get_page_params(result)
        for params in ['realm_users', 'realm_bots']:
            users = page_params['realm_users']
            self.assertTrue(len(users) >= 3)
            for user in users:
                self.assertEqual(user['user_id'],
                                 get_user(user['email'], realm).id)

        cross_bots = page_params['cross_realm_bots']
        self.assertEqual(len(cross_bots), 3)
        cross_bots.sort(key=lambda d: d['email'])

        notification_bot = self.notification_bot()

        self.assertEqual(cross_bots, [
            dict(
                user_id=get_user('feedback@zulip.com', get_realm('zulip')).id,
                is_admin=False,
                email='feedback@zulip.com',
                full_name='Zulip Feedback Bot',
                is_bot=True
            ),
            dict(
                user_id=notification_bot.id,
                is_admin=False,
                email=notification_bot.email,
                full_name='Notification Bot',
                is_bot=True
            ),
            dict(
                user_id=get_user('welcome-bot@zulip.com', get_realm('zulip')).id,
                is_admin=False,
                email='welcome-bot@zulip.com',
                full_name='Welcome Bot',
                is_bot=True
            ),
        ])

    def test_new_stream(self):
        # type: () -> None
        user_profile = self.example_user("hamlet")
        stream_name = 'New stream'
        self.subscribe(user_profile, stream_name)
        self.login(user_profile.email)
        result = self._get_home_page(stream=stream_name)
        page_params = self._get_page_params(result)
        self.assertEqual(page_params['narrow_stream'], stream_name)
        self.assertEqual(page_params['narrow'], [dict(operator='stream', operand=stream_name)])
        self.assertEqual(page_params['pointer'], -1)
        self.assertEqual(page_params['max_message_id'], -1)
        self.assertEqual(page_params['have_initial_messages'], False)

    def test_invites_by_admins_only(self):
        # type: () -> None
        user_profile = self.example_user('hamlet')
        email = user_profile.email

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
        email = self.example_email("hamlet")
        self.login(email)
        result = self.client_get("/desktop_home")
        self.assertEqual(result.status_code, 301)
        self.assertTrue(result["Location"].endswith("/desktop_home/"))
        result = self.client_get("/desktop_home/")
        self.assertEqual(result.status_code, 302)
        path = urllib.parse.urlparse(result['Location']).path
        self.assertEqual(path, "/")

    def test_apps_view(self):
        # type: () -> None
        result = self.client_get('/apps')
        self.assertEqual(result.status_code, 301)
        self.assertTrue(result['Location'].endswith('/apps/'))

        with self.settings(ZILENCER_ENABLED=False):
            result = self.client_get('/apps/')
        self.assertEqual(result.status_code, 301)
        self.assertTrue(result['Location'] == 'https://zulipchat.com/apps/')

        with self.settings(ZILENCER_ENABLED=True):
            result = self.client_get('/apps/')
        self.assertEqual(result.status_code, 200)
        html = result.content.decode('utf-8')
        self.assertIn('Apps for every platform.', html)

    def test_generate_204(self):
        # type: () -> None
        email = self.example_email("hamlet")
        self.login(email)
        result = self.client_get("/api/v1/generate_204")
        self.assertEqual(result.status_code, 204)

    def test_message_sent_time(self):
        # type: () -> None
        epoch_seconds = 1490472096
        pub_date = datetime.datetime.fromtimestamp(epoch_seconds)
        user_message = MagicMock()
        user_message.message.pub_date = pub_date
        self.assertEqual(sent_time_in_epoch_seconds(user_message), epoch_seconds)

    def test_handlebars_compile_error(self):
        # type: () -> None
        request = HostRequestMock()
        with self.settings(DEVELOPMENT=True):
            with patch('os.path.exists', return_value=True):
                result = home(request)
        self.assertEqual(result.status_code, 500)
        self.assert_in_response('Error compiling handlebars templates.', result)

    def test_subdomain_homepage(self):
        # type: () -> None
        email = self.example_email("hamlet")
        self.login(email)
        with self.settings(ROOT_DOMAIN_LANDING_PAGE=True):
            with patch('zerver.views.home.get_subdomain', return_value=""):
                result = self._get_home_page()
            self.assertEqual(result.status_code, 200)
            self.assert_in_response('most productive group chat', result)

            with patch('zerver.views.home.get_subdomain', return_value="subdomain"):
                result = self._get_home_page()
            self._sanity_check(result)

    def send_stream_message(self, content, sender_name='iago',
                            stream_name='Denmark', subject='foo'):
        # type: (str, str, str, str) -> None
        sender = self.example_email(sender_name)
        self.send_message(sender, stream_name, Recipient.STREAM,
                          content, subject)

    def soft_activate_and_get_unread_count(self, stream='Denmark', topic='foo'):
        # type: (str, str) -> int
        stream_narrow = self._get_home_page(stream=stream, topic=topic)
        page_params = self._get_page_params(stream_narrow)
        return page_params['unread_msgs']['count']

    def test_unread_count_user_soft_deactivation(self):
        # type: () -> None
        # In this test we make sure if a soft deactivated user had unread
        # messages before deactivation they remain same way after activation.
        long_term_idle_user = self.example_user('hamlet')
        self.login(long_term_idle_user.email)
        message = 'Test Message 1'
        self.send_stream_message(message)
        with queries_captured() as queries:
            self.assertEqual(self.soft_activate_and_get_unread_count(), 1)
        query_count = len(queries)
        user_msg_list = get_user_messages(long_term_idle_user)
        self.assertEqual(user_msg_list[-1].content, message)
        self.logout()

        do_soft_deactivate_users([long_term_idle_user])

        self.login(long_term_idle_user.email)
        message = 'Test Message 2'
        self.send_stream_message(message)
        idle_user_msg_list = get_user_messages(long_term_idle_user)
        self.assertNotEqual(idle_user_msg_list[-1].content, message)
        with queries_captured() as queries:
            self.assertEqual(self.soft_activate_and_get_unread_count(), 2)
        # Test here for query count to be at least 5 greater than previous count
        # This will assure indirectly that add_missing_messages() was called.
        self.assertGreaterEqual(len(queries) - query_count, 5)
        idle_user_msg_list = get_user_messages(long_term_idle_user)
        self.assertEqual(idle_user_msg_list[-1].content, message)

    def test_multiple_user_soft_deactivations(self):
        # type: () -> None
        long_term_idle_user = self.example_user('hamlet')
        # We are sending this message to ensure that long_term_idle_user has
        # at least one UserMessage row.
        self.send_stream_message('Testing', sender_name='hamlet')
        do_soft_deactivate_users([long_term_idle_user])

        message = 'Test Message 1'
        self.send_stream_message(message)
        self.login(long_term_idle_user.email)
        with queries_captured() as queries:
            self.assertEqual(self.soft_activate_and_get_unread_count(), 2)
        query_count = len(queries)
        long_term_idle_user.refresh_from_db()
        self.assertFalse(long_term_idle_user.long_term_idle)
        idle_user_msg_list = get_user_messages(long_term_idle_user)
        self.assertEqual(idle_user_msg_list[-1].content, message)

        message = 'Test Message 2'
        self.send_stream_message(message)
        with queries_captured() as queries:
            self.assertEqual(self.soft_activate_and_get_unread_count(), 3)
        # Test here for query count to be at least 5 less than previous count.
        # This will assure add_missing_messages() isn't repeatedly called.
        self.assertGreaterEqual(query_count - len(queries), 5)
        idle_user_msg_list = get_user_messages(long_term_idle_user)
        self.assertEqual(idle_user_msg_list[-1].content, message)
        self.logout()

        do_soft_deactivate_users([long_term_idle_user])

        message = 'Test Message 3'
        self.send_stream_message(message)
        self.login(long_term_idle_user.email)
        with queries_captured() as queries:
            self.assertEqual(self.soft_activate_and_get_unread_count(), 4)
        query_count = len(queries)
        long_term_idle_user.refresh_from_db()
        self.assertFalse(long_term_idle_user.long_term_idle)
        idle_user_msg_list = get_user_messages(long_term_idle_user)
        self.assertEqual(idle_user_msg_list[-1].content, message)

        message = 'Test Message 4'
        self.send_stream_message(message)
        with queries_captured() as queries:
            self.assertEqual(self.soft_activate_and_get_unread_count(), 5)
        self.assertGreaterEqual(query_count - len(queries), 5)
        idle_user_msg_list = get_user_messages(long_term_idle_user)
        self.assertEqual(idle_user_msg_list[-1].content, message)
        self.logout()
