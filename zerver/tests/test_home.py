
import datetime
import re
import ujson

from django.http import HttpResponse
from django.utils.timezone import now as timezone_now
from mock import MagicMock, patch
import urllib
from typing import Any, Dict

from zerver.lib.actions import do_create_user
from zerver.lib.actions import do_change_logo_source
from zerver.lib.events import add_realm_logo_fields
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import (
    HostRequestMock, queries_captured, get_user_messages
)
from zerver.lib.soft_deactivation import do_soft_deactivate_users
from zerver.lib.test_runner import slow
from zerver.models import (
    get_realm, get_stream, get_user, UserProfile,
    flush_per_request_caches, DefaultStream, Realm,
)
from zerver.views.home import home, sent_time_in_epoch_seconds, compute_navbar_logo_url
from corporate.models import Customer, CustomerPlan

class HomeTest(ZulipTestCase):
    def test_home(self) -> None:

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
            # Verify that the app styles get included
            'app-stubentry.js',
            'var page_params',
        ]

        # Keep this list sorted!!!
        expected_keys = [
            "alert_words",
            "available_notification_sounds",
            "avatar_source",
            "avatar_url",
            "avatar_url_medium",
            "bot_types",
            "can_create_streams",
            "can_subscribe_other_users",
            "cross_realm_bots",
            "custom_profile_field_types",
            "custom_profile_fields",
            "debug_mode",
            "default_language",
            "default_language_name",
            "delivery_email",
            "dense_mode",
            "development_environment",
            "email",
            "emojiset",
            "emojiset_choices",
            "enable_desktop_notifications",
            "enable_digest_emails",
            "enable_login_emails",
            "enable_offline_email_notifications",
            "enable_offline_push_notifications",
            "enable_online_push_notifications",
            "enable_sounds",
            "enable_stream_desktop_notifications",
            "enable_stream_email_notifications",
            "enable_stream_push_notifications",
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
            "is_guest",
            "jitsi_server_url",
            "language_list",
            "language_list_dbl_col",
            "last_event_id",
            "left_side_userlist",
            "login_page",
            "max_avatar_file_size",
            "max_icon_file_size",
            "max_logo_file_size",
            "max_message_id",
            "maxfilesize",
            "message_content_in_email_notifications",
            "muted_topics",
            "narrow",
            "narrow_stream",
            "needs_tutorial",
            "never_subscribed",
            "night_mode",
            "notification_sound",
            "password_min_guesses",
            "password_min_length",
            "pm_content_in_desktop_notifications",
            "pointer",
            "poll_timeout",
            "presences",
            "prompt_for_invites",
            "queue_id",
            "realm_add_emoji_by_admins_only",
            "realm_allow_community_topic_editing",
            "realm_allow_edit_history",
            "realm_allow_message_deleting",
            "realm_allow_message_editing",
            "realm_authentication_methods",
            "realm_available_video_chat_providers",
            "realm_bot_creation_policy",
            "realm_bot_domain",
            "realm_bots",
            "realm_create_stream_by_admins_only",
            "realm_default_language",
            "realm_default_stream_groups",
            "realm_default_streams",
            "realm_default_twenty_four_hour_time",
            "realm_description",
            "realm_digest_emails_enabled",
            "realm_disallow_disposable_email_addresses",
            "realm_domains",
            "realm_email_address_visibility",
            "realm_email_auth_enabled",
            "realm_email_changes_disabled",
            "realm_emails_restricted_to_domains",
            "realm_embedded_bots",
            "realm_emoji",
            "realm_filters",
            "realm_google_hangouts_domain",
            "realm_icon_source",
            "realm_icon_url",
            "realm_inline_image_preview",
            "realm_inline_url_embed_preview",
            "realm_invite_by_admins_only",
            "realm_invite_required",
            "realm_is_zephyr_mirror_realm",
            "realm_logo_source",
            "realm_logo_url",
            "realm_mandatory_topics",
            "realm_message_content_allowed_in_email_notifications",
            "realm_message_content_delete_limit_seconds",
            "realm_message_content_edit_limit_seconds",
            "realm_message_retention_days",
            "realm_name",
            "realm_name_changes_disabled",
            "realm_name_in_notifications",
            "realm_night_logo_source",
            "realm_night_logo_url",
            "realm_non_active_users",
            "realm_notifications_stream_id",
            "realm_password_auth_enabled",
            "realm_plan_type",
            "realm_presence_disabled",
            "realm_push_notifications_enabled",
            "realm_send_welcome_emails",
            "realm_signup_notifications_stream_id",
            "realm_upload_quota",
            "realm_uri",
            "realm_user_groups",
            "realm_users",
            "realm_video_chat_provider",
            "realm_waiting_period_threshold",
            "realm_zoom_api_key",
            "realm_zoom_api_secret",
            "realm_zoom_user_id",
            "root_domain_uri",
            "save_stacktraces",
            "search_pills_enabled",
            "server_generation",
            "server_inline_image_preview",
            "server_inline_url_embed_preview",
            "starred_message_counts",
            "starred_messages",
            "stop_words",
            "stream_description_max_length",
            "stream_name_max_length",
            "subscriptions",
            "test_suite",
            "timezone",
            "translate_emoticons",
            "translation_data",
            "twenty_four_hour_time",
            "two_fa_enabled",
            "two_fa_enabled_user",
            "unread_msgs",
            "unsubscribed",
            "use_websockets",
            "user_id",
            "user_status",
            "warn_no_email",
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
        flush_per_request_caches()
        with queries_captured() as queries:
            with patch('zerver.lib.cache.cache_set') as cache_mock:
                result = self._get_home_page(stream='Denmark')

        self.assert_length(queries, 43)
        self.assert_length(cache_mock.call_args_list, 7)

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
            'services',
            'user_id',
        ]

        realm_bots_actual_keys = sorted([str(key) for key in page_params['realm_bots'][0].keys()])
        self.assertEqual(realm_bots_actual_keys, realm_bots_expected_keys)

    def test_home_under_2fa_without_otp_device(self) -> None:
        with self.settings(TWO_FACTOR_AUTHENTICATION_ENABLED=True):
            self.login(self.example_email("iago"))
            result = self._get_home_page()
            # Should be successful because otp device is not configured.
            self.assertEqual(result.status_code, 200)

    def test_home_under_2fa_with_otp_device(self) -> None:
        with self.settings(TWO_FACTOR_AUTHENTICATION_ENABLED=True):
            user_profile = self.example_user('iago')
            self.create_default_device(user_profile)
            self.login(user_profile.email)
            result = self._get_home_page()
            # User should not log in because otp device is configured but
            # 2fa login function was not called.
            self.assertEqual(result.status_code, 302)

            self.login_2fa(user_profile)
            result = self._get_home_page()
            # Should be successful after calling 2fa login function.
            self.assertEqual(result.status_code, 200)

    def test_num_queries_for_realm_admin(self) -> None:
        # Verify number of queries for Realm admin isn't much higher than for normal users.
        self.login(self.example_email("iago"))
        flush_per_request_caches()
        with queries_captured() as queries:
            with patch('zerver.lib.cache.cache_set') as cache_mock:
                result = self._get_home_page()
                self.assertEqual(result.status_code, 200)
                self.assert_length(cache_mock.call_args_list, 6)
            self.assert_length(queries, 40)

    @slow("Creates and subscribes 10 users in a loop.  Should use bulk queries.")
    def test_num_queries_with_streams(self) -> None:
        main_user = self.example_user('hamlet')
        other_user = self.example_user('cordelia')

        realm_id = main_user.realm_id

        self.login(main_user.email)

        # Try to make page-load do extra work for various subscribed
        # streams.
        for i in range(10):
            stream_name = 'test_stream_' + str(i)
            stream = self.make_stream(stream_name)
            DefaultStream.objects.create(
                realm_id=realm_id,
                stream_id=stream.id
            )
            for user in [main_user, other_user]:
                self.subscribe(user, stream_name)

        # Simulate hitting the page the first time to avoid some noise
        # related to initial logins.
        self._get_home_page()

        # Then for the second page load, measure the number of queries.
        flush_per_request_caches()
        with queries_captured() as queries2:
            result = self._get_home_page()

        self.assert_length(queries2, 37)

        # Do a sanity check that our new streams were in the payload.
        html = result.content.decode('utf-8')
        self.assertIn('test_stream_7', html)

    def _get_home_page(self, **kwargs: Any) -> HttpResponse:
        with \
                patch('zerver.lib.events.request_event_queue', return_value=42), \
                patch('zerver.lib.events.get_user_events', return_value=[]):
            result = self.client_get('/', dict(**kwargs))
        return result

    def _get_page_params(self, result: HttpResponse) -> Dict[str, Any]:
        html = result.content.decode('utf-8')
        lines = html.split('\n')
        page_params_line = [l for l in lines if re.match(r'^\s*var page_params', l)][0]
        page_params_json = page_params_line.split(' = ')[1].rstrip(';')
        page_params = ujson.loads(page_params_json)
        return page_params

    def _sanity_check(self, result: HttpResponse) -> None:
        '''
        Use this for tests that are geared toward specific edge cases, but
        which still want the home page to load properly.
        '''
        html = result.content.decode('utf-8')
        if 'Compose your message' not in html:
            raise AssertionError('Home page probably did not load.')

    def test_terms_of_service(self) -> None:
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
            self.assertIn('Accept the new Terms of Service', html)

    def test_terms_of_service_first_time_template(self) -> None:
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
            self.assert_in_response("most productive team chat", result)

    def test_accept_terms_of_service(self) -> None:
        email = self.example_email("hamlet")
        self.login(email)

        result = self.client_post('/accounts/accept_terms/')
        self.assertEqual(result.status_code, 200)
        self.assert_in_response("I agree to the", result)

        result = self.client_post('/accounts/accept_terms/', {'terms': True})
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result['Location'], '/')

    def test_bad_narrow(self) -> None:
        email = self.example_email("hamlet")
        self.login(email)
        with patch('logging.exception') as mock:
            result = self._get_home_page(stream='Invalid Stream')
        mock.assert_called_once()
        self.assertEqual(mock.call_args_list[0][0][0], "Narrow parsing exception")
        self._sanity_check(result)

    def test_bad_pointer(self) -> None:
        user_profile = self.example_user('hamlet')
        email = user_profile.email
        user_profile.pointer = 999999
        user_profile.save()

        self.login(email)
        with patch('logging.warning') as mock:
            result = self._get_home_page()
        mock.assert_called_once_with('hamlet@zulip.com has invalid pointer 999999')
        self._sanity_check(result)

    def test_topic_narrow(self) -> None:
        email = self.example_email("hamlet")
        self.login(email)
        result = self._get_home_page(stream='Denmark', topic='lunch')
        self._sanity_check(result)
        html = result.content.decode('utf-8')
        self.assertIn('lunch', html)

    def test_notifications_stream(self) -> None:
        email = self.example_email("hamlet")
        realm = get_realm('zulip')
        realm.notifications_stream_id = get_stream('Denmark', realm).id
        realm.save()
        self.login(email)
        result = self._get_home_page()
        page_params = self._get_page_params(result)
        self.assertEqual(page_params['realm_notifications_stream_id'], get_stream('Denmark', realm).id)

    def create_bot(self, owner: UserProfile, bot_email: str, bot_name: str) -> UserProfile:
        user = do_create_user(
            email=bot_email,
            password='123',
            realm=owner.realm,
            full_name=bot_name,
            short_name=bot_name,
            bot_type=UserProfile.DEFAULT_BOT,
            bot_owner=owner
        )
        return user

    def create_non_active_user(self, realm: Realm, email: str, name: str) -> UserProfile:
        user = do_create_user(
            email=email,
            password='123',
            realm=realm,
            full_name=name,
            short_name=name,
        )

        # Doing a full-stack deactivation would be expensive here,
        # and we really only need to flip the flag to get a valid
        # test.
        user.is_active = False
        user.save()
        return user

    def test_signup_notifications_stream(self) -> None:
        email = self.example_email("hamlet")
        realm = get_realm('zulip')
        realm.signup_notifications_stream = get_stream('Denmark', realm)
        realm.save()
        self.login(email)
        result = self._get_home_page()
        page_params = self._get_page_params(result)
        self.assertEqual(page_params['realm_signup_notifications_stream_id'], get_stream('Denmark', realm).id)

    @slow('creating users and loading home page')
    def test_people(self) -> None:
        hamlet = self.example_user('hamlet')
        realm = get_realm('zulip')
        self.login(hamlet.email)

        for i in range(3):
            self.create_bot(
                owner=hamlet,
                bot_email='bot-%d@zulip.com' % (i,),
                bot_name='Bot %d' % (i,),
            )

        for i in range(3):
            self.create_non_active_user(
                realm=realm,
                email='defunct-%d@zulip.com' % (i,),
                name='Defunct User %d' % (i,),
            )

        result = self._get_home_page()
        page_params = self._get_page_params(result)

        '''
        We send three lists of users.  The first two below are disjoint
        lists of users, and the records we send for them have identical
        structure.

        The realm_bots bucket is somewhat redundant, since all bots will
        be in one of the first two buckets.  They do include fields, however,
        that normal users don't care about, such as default_sending_stream.
        '''

        buckets = [
            'realm_users',
            'realm_non_active_users',
            'realm_bots',
        ]

        for field in buckets:
            users = page_params[field]
            self.assertTrue(len(users) >= 3, field)
            for rec in users:
                self.assertEqual(rec['user_id'],
                                 get_user(rec['email'], realm).id)
                if field == 'realm_bots':
                    self.assertNotIn('is_bot', rec)
                    self.assertIn('is_active', rec)
                    self.assertIn('owner', rec)
                else:
                    self.assertIn('is_bot', rec)
                    self.assertNotIn('is_active', rec)

        active_emails = {p['email'] for p in page_params['realm_users']}
        non_active_emails = {p['email'] for p in page_params['realm_non_active_users']}
        bot_emails = {p['email'] for p in page_params['realm_bots']}

        self.assertIn(hamlet.email, active_emails)
        self.assertIn('defunct-1@zulip.com', non_active_emails)

        # Bots can show up in multiple buckets.
        self.assertIn('bot-2@zulip.com', bot_emails)
        self.assertIn('bot-2@zulip.com', active_emails)

        # Make sure nobody got mis-bucketed.
        self.assertNotIn(hamlet.email, non_active_emails)
        self.assertNotIn('defunct-1@zulip.com', active_emails)

        cross_bots = page_params['cross_realm_bots']
        self.assertEqual(len(cross_bots), 5)
        cross_bots.sort(key=lambda d: d['email'])
        for cross_bot in cross_bots:
            # These are either nondeterministic or boring
            del cross_bot['timezone']
            del cross_bot['avatar_url']
            del cross_bot['date_joined']

        notification_bot = self.notification_bot()

        by_email = lambda d: d['email']

        self.assertEqual(sorted(cross_bots, key=by_email), sorted([
            dict(
                user_id=get_user('new-user-bot@zulip.com', get_realm('zulip')).id,
                is_admin=False,
                email='new-user-bot@zulip.com',
                full_name='Zulip New User Bot',
                is_bot=True
            ),
            dict(
                user_id=get_user('emailgateway@zulip.com', get_realm('zulip')).id,
                is_admin=False,
                email='emailgateway@zulip.com',
                full_name='Email Gateway',
                is_bot=True
            ),
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
        ], key=by_email))

    def test_new_stream(self) -> None:
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

    def test_invites_by_admins_only(self) -> None:
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

    def test_show_invites_for_guest_users(self) -> None:
        user_profile = self.example_user('polonius')
        email = user_profile.email

        realm = user_profile.realm
        realm.invite_by_admins_only = False
        realm.save()

        self.login(email)
        self.assertFalse(user_profile.is_realm_admin)
        self.assertFalse(get_realm('zulip').invite_by_admins_only)
        result = self._get_home_page()
        html = result.content.decode('utf-8')
        self.assertNotIn('Invite more users', html)

    def test_show_billing(self) -> None:
        customer = Customer.objects.create(realm=get_realm("zulip"), stripe_customer_id="cus_id")

        # realm admin, but no CustomerPlan -> no billing link
        user = self.example_user('iago')
        self.login(user.email)
        result_html = self._get_home_page().content.decode('utf-8')
        self.assertNotIn('Billing', result_html)

        # realm admin, with inactive CustomerPlan -> show billing link
        CustomerPlan.objects.create(customer=customer, billing_cycle_anchor=timezone_now(),
                                    billing_schedule=CustomerPlan.ANNUAL, next_invoice_date=timezone_now(),
                                    tier=CustomerPlan.STANDARD, status=CustomerPlan.ENDED)
        result_html = self._get_home_page().content.decode('utf-8')
        self.assertIn('Billing', result_html)

        # billing admin, with CustomerPlan -> show billing link
        user.is_realm_admin = False
        user.is_billing_admin = True
        user.save(update_fields=['is_realm_admin', 'is_billing_admin'])
        result_html = self._get_home_page().content.decode('utf-8')
        self.assertIn('Billing', result_html)

        # billing admin, but no CustomerPlan -> no billing link
        CustomerPlan.objects.all().delete()
        result_html = self._get_home_page().content.decode('utf-8')
        self.assertNotIn('Billing', result_html)

        # billing admin, no customer object -> make sure it doesn't crash
        customer.delete()
        result = self._get_home_page()
        self.assertEqual(result.status_code, 200)

    def test_show_plans(self) -> None:
        realm = get_realm("zulip")
        self.login(self.example_email('hamlet'))

        # Show plans link to all users if plan_type is LIMITED
        realm.plan_type = Realm.LIMITED
        realm.save(update_fields=["plan_type"])
        result_html = self._get_home_page().content.decode('utf-8')
        self.assertIn('Plans', result_html)

        # Show plans link to no one, including admins, if SELF_HOSTED or STANDARD
        realm.plan_type = Realm.SELF_HOSTED
        realm.save(update_fields=["plan_type"])
        result_html = self._get_home_page().content.decode('utf-8')
        self.assertNotIn('Plans', result_html)

        realm.plan_type = Realm.STANDARD
        realm.save(update_fields=["plan_type"])
        result_html = self._get_home_page().content.decode('utf-8')
        self.assertNotIn('Plans', result_html)

    def test_desktop_home(self) -> None:
        email = self.example_email("hamlet")
        self.login(email)
        result = self.client_get("/desktop_home")
        self.assertEqual(result.status_code, 301)
        self.assertTrue(result["Location"].endswith("/desktop_home/"))
        result = self.client_get("/desktop_home/")
        self.assertEqual(result.status_code, 302)
        path = urllib.parse.urlparse(result['Location']).path
        self.assertEqual(path, "/")

    def test_apps_view(self) -> None:
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

    def test_compute_navbar_logo_url(self) -> None:
        user_profile = self.example_user("hamlet")

        page_params = {"night_mode": True}
        add_realm_logo_fields(page_params, user_profile.realm)
        self.assertEqual(compute_navbar_logo_url(page_params),
                         "/static/images/logo/zulip-org-logo.png?version=0")

        page_params = {"night_mode": False}
        add_realm_logo_fields(page_params, user_profile.realm)
        self.assertEqual(compute_navbar_logo_url(page_params),
                         "/static/images/logo/zulip-org-logo.png?version=0")

        do_change_logo_source(user_profile.realm, Realm.LOGO_UPLOADED, night=False)
        page_params = {"night_mode": True}
        add_realm_logo_fields(page_params, user_profile.realm)
        self.assertEqual(compute_navbar_logo_url(page_params),
                         "/user_avatars/1/realm/logo.png?version=2")

        page_params = {"night_mode": False}
        add_realm_logo_fields(page_params, user_profile.realm)
        self.assertEqual(compute_navbar_logo_url(page_params),
                         "/user_avatars/1/realm/logo.png?version=2")

        do_change_logo_source(user_profile.realm, Realm.LOGO_UPLOADED, night=True)
        page_params = {"night_mode": True}
        add_realm_logo_fields(page_params, user_profile.realm)
        self.assertEqual(compute_navbar_logo_url(page_params),
                         "/user_avatars/1/realm/night_logo.png?version=2")

        page_params = {"night_mode": False}
        add_realm_logo_fields(page_params, user_profile.realm)
        self.assertEqual(compute_navbar_logo_url(page_params),
                         "/user_avatars/1/realm/logo.png?version=2")

        # This configuration isn't super supported in the UI and is a
        # weird choice, but we have a test for it anyway.
        do_change_logo_source(user_profile.realm, Realm.LOGO_DEFAULT, night=False)
        page_params = {"night_mode": True}
        add_realm_logo_fields(page_params, user_profile.realm)
        self.assertEqual(compute_navbar_logo_url(page_params),
                         "/user_avatars/1/realm/night_logo.png?version=2")

        page_params = {"night_mode": False}
        add_realm_logo_fields(page_params, user_profile.realm)
        self.assertEqual(compute_navbar_logo_url(page_params),
                         "/static/images/logo/zulip-org-logo.png?version=0")

    def test_generate_204(self) -> None:
        email = self.example_email("hamlet")
        self.login(email)
        result = self.client_get("/api/v1/generate_204")
        self.assertEqual(result.status_code, 204)

    def test_message_sent_time(self) -> None:
        epoch_seconds = 1490472096
        pub_date = datetime.datetime.fromtimestamp(epoch_seconds)
        user_message = MagicMock()
        user_message.message.pub_date = pub_date
        self.assertEqual(sent_time_in_epoch_seconds(user_message), epoch_seconds)

    def test_handlebars_compile_error(self) -> None:
        request = HostRequestMock()
        with self.settings(DEVELOPMENT=True, TEST_SUITE=False):
            with patch('os.path.exists', return_value=True):
                result = home(request)
        self.assertEqual(result.status_code, 500)
        self.assert_in_response('Error compiling handlebars templates.', result)

    def test_subdomain_homepage(self) -> None:
        email = self.example_email("hamlet")
        self.login(email)
        with self.settings(ROOT_DOMAIN_LANDING_PAGE=True):
            with patch('zerver.views.home.get_subdomain', return_value=""):
                result = self._get_home_page()
            self.assertEqual(result.status_code, 200)
            self.assert_in_response('most productive team chat', result)

            with patch('zerver.views.home.get_subdomain', return_value="subdomain"):
                result = self._get_home_page()
            self._sanity_check(result)

    def send_test_message(self, content: str, sender_name: str='iago',
                          stream_name: str='Denmark', topic_name: str='foo') -> None:
        sender = self.example_email(sender_name)
        self.send_stream_message(sender, stream_name,
                                 content=content, topic_name=topic_name)

    def soft_activate_and_get_unread_count(self, stream: str='Denmark', topic: str='foo') -> int:
        stream_narrow = self._get_home_page(stream=stream, topic=topic)
        page_params = self._get_page_params(stream_narrow)
        return page_params['unread_msgs']['count']

    def test_unread_count_user_soft_deactivation(self) -> None:
        # In this test we make sure if a soft deactivated user had unread
        # messages before deactivation they remain same way after activation.
        long_term_idle_user = self.example_user('hamlet')
        self.login(long_term_idle_user.email)
        message = 'Test Message 1'
        self.send_test_message(message)
        with queries_captured() as queries:
            self.assertEqual(self.soft_activate_and_get_unread_count(), 1)
        query_count = len(queries)
        user_msg_list = get_user_messages(long_term_idle_user)
        self.assertEqual(user_msg_list[-1].content, message)
        self.logout()

        do_soft_deactivate_users([long_term_idle_user])

        self.login(long_term_idle_user.email)
        message = 'Test Message 2'
        self.send_test_message(message)
        idle_user_msg_list = get_user_messages(long_term_idle_user)
        self.assertNotEqual(idle_user_msg_list[-1].content, message)
        with queries_captured() as queries:
            self.assertEqual(self.soft_activate_and_get_unread_count(), 2)
        # Test here for query count to be at least 5 greater than previous count
        # This will assure indirectly that add_missing_messages() was called.
        self.assertGreaterEqual(len(queries) - query_count, 5)
        idle_user_msg_list = get_user_messages(long_term_idle_user)
        self.assertEqual(idle_user_msg_list[-1].content, message)

    @slow("Loads home page data several times testing different cases")
    def test_multiple_user_soft_deactivations(self) -> None:
        long_term_idle_user = self.example_user('hamlet')
        # We are sending this message to ensure that long_term_idle_user has
        # at least one UserMessage row.
        self.send_test_message('Testing', sender_name='hamlet')
        do_soft_deactivate_users([long_term_idle_user])

        message = 'Test Message 1'
        self.send_test_message(message)
        self.login(long_term_idle_user.email)
        with queries_captured() as queries:
            self.assertEqual(self.soft_activate_and_get_unread_count(), 2)
        query_count = len(queries)
        long_term_idle_user.refresh_from_db()
        self.assertFalse(long_term_idle_user.long_term_idle)
        idle_user_msg_list = get_user_messages(long_term_idle_user)
        self.assertEqual(idle_user_msg_list[-1].content, message)

        message = 'Test Message 2'
        self.send_test_message(message)
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
        self.send_test_message(message)
        self.login(long_term_idle_user.email)
        with queries_captured() as queries:
            self.assertEqual(self.soft_activate_and_get_unread_count(), 4)
        query_count = len(queries)
        long_term_idle_user.refresh_from_db()
        self.assertFalse(long_term_idle_user.long_term_idle)
        idle_user_msg_list = get_user_messages(long_term_idle_user)
        self.assertEqual(idle_user_msg_list[-1].content, message)

        message = 'Test Message 4'
        self.send_test_message(message)
        with queries_captured() as queries:
            self.assertEqual(self.soft_activate_and_get_unread_count(), 5)
        self.assertGreaterEqual(query_count - len(queries), 5)
        idle_user_msg_list = get_user_messages(long_term_idle_user)
        self.assertEqual(idle_user_msg_list[-1].content, message)
        self.logout()

    def test_url_language(self) -> None:
        user = self.example_user("hamlet")
        user.default_language = 'es'
        user.save()
        self.login(user.email)
        result = self._get_home_page()
        self.assertEqual(result.status_code, 200)
        with \
                patch('zerver.lib.events.request_event_queue', return_value=42), \
                patch('zerver.lib.events.get_user_events', return_value=[]):
            result = self.client_get('/de/')
        page_params = self._get_page_params(result)
        self.assertEqual(page_params['default_language'], 'es')
        # TODO: Verify that the actual language we're using in the
        # translation data is German.

    def test_translation_data(self) -> None:
        user = self.example_user("hamlet")
        user.default_language = 'es'
        user.save()
        self.login(user.email)
        result = self._get_home_page()
        self.assertEqual(result.status_code, 200)

        page_params = self._get_page_params(result)
        self.assertEqual(page_params['default_language'], 'es')

    def test_emojiset(self) -> None:
        user = self.example_user("hamlet")
        user.emojiset = 'text'
        user.save()
        self.login(user.email)
        result = self._get_home_page()
        self.assertEqual(result.status_code, 200)

        html = result.content.decode('utf-8')
        self.assertIn('google-blob-sprite.css', html)
        self.assertNotIn('text-sprite.css', html)
