import calendar
from datetime import timedelta
import lxml.html
import ujson

from django.conf import settings
from django.http import HttpResponse
from django.utils.timezone import now as timezone_now
from unittest.mock import patch
import urllib
from typing import Any, Dict
from zerver.lib.actions import (
    do_create_user, do_change_logo_source
)
from zerver.lib.events import add_realm_logo_fields
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import (
    queries_captured, get_user_messages
)
from zerver.lib.soft_deactivation import do_soft_deactivate_users
from zerver.lib.test_runner import slow
from zerver.lib.users import compute_show_invites_and_add_streams
from zerver.models import (
    get_realm, get_stream, get_user, UserProfile,
    flush_per_request_caches, DefaultStream, Realm,
    get_system_bot, UserActivity
)
from zerver.views.home import compute_navbar_logo_url, get_furthest_read_time
from corporate.models import Customer, CustomerPlan
from zerver.worker.queue_processors import UserActivityWorker

class HomeTest(ZulipTestCase):
    def test_home(self) -> None:

        # Keep this list sorted!!!
        html_bits = [
            'Compose your message here...',
            'Exclude messages with topic',
            'Keyboard shortcuts',
            'Loading...',
            'Manage streams',
            'Narrow to topic',
            'Next message',
            'Search streams',
            'Welcome to Zulip',
            # Verify that the app styles get included
            'app-stubentry.js',
            'data-params',
        ]

        # Keep this list sorted!!!
        expected_keys = [
            "alert_words",
            "available_notification_sounds",
            "avatar_source",
            "avatar_url",
            "avatar_url_medium",
            "bot_types",
            "buddy_list_mode",
            "can_create_streams",
            "can_subscribe_other_users",
            "cross_realm_bots",
            "custom_profile_field_types",
            "custom_profile_fields",
            "debug_mode",
            "default_language",
            "default_language_name",
            "delivery_email",
            "demote_inactive_streams",
            "dense_mode",
            "desktop_icon_count_display",
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
            "enable_stream_audible_notifications",
            "enable_stream_desktop_notifications",
            "enable_stream_email_notifications",
            "enable_stream_push_notifications",
            "enter_sends",
            "first_in_realm",
            "fluid_layout_width",
            "full_name",
            "furthest_read_time",
            "has_mobile_devices",
            "have_initial_messages",
            "high_contrast_mode",
            "hotspots",
            "initial_servertime",
            "insecure_desktop_app",
            "is_admin",
            "is_guest",
            "jitsi_server_url",
            "language_list",
            "language_list_dbl_col",
            "last_event_id",
            "left_side_userlist",
            "login_page",
            "max_avatar_file_size_mib",
            "max_file_upload_size_mib",
            "max_icon_file_size",
            "max_logo_file_size",
            "max_message_id",
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
            "presence_enabled",
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
            "realm_avatar_changes_disabled",
            "realm_bot_creation_policy",
            "realm_bot_domain",
            "realm_bots",
            "realm_create_stream_policy",
            "realm_default_code_block_language",
            "realm_default_external_accounts",
            "realm_default_language",
            "realm_default_stream_groups",
            "realm_default_streams",
            "realm_default_twenty_four_hour_time",
            "realm_description",
            "realm_digest_emails_enabled",
            "realm_digest_weekday",
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
            "realm_incoming_webhook_bots",
            "realm_inline_image_preview",
            "realm_inline_url_embed_preview",
            "realm_invite_by_admins_only",
            "realm_invite_required",
            "realm_invite_to_stream_policy",
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
            "realm_private_message_policy",
            "realm_push_notifications_enabled",
            "realm_send_welcome_emails",
            "realm_signup_notifications_stream_id",
            "realm_upload_quota",
            "realm_uri",
            "realm_user_group_edit_policy",
            "realm_user_groups",
            "realm_users",
            "realm_video_chat_provider",
            "realm_waiting_period_threshold",
            "realm_zoom_api_key",
            "realm_zoom_api_secret",
            "realm_zoom_user_id",
            "recent_private_conversations",
            "root_domain_uri",
            "save_stacktraces",
            "search_pills_enabled",
            "server_avatar_changes_disabled",
            "server_generation",
            "server_inline_image_preview",
            "server_inline_url_embed_preview",
            "server_name_changes_disabled",
            "settings_send_digest_emails",
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
            "upgrade_text_for_wide_organization_logo",
            "user_id",
            "user_status",
            "warn_no_email",
            "webpack_public_path",
            "wildcard_mentions_notify",
            "zulip_feature_level",
            "zulip_plan_is_not_limited",
            "zulip_version",
        ]

        # Verify fails if logged-out
        result = self.client_get('/')
        self.assertEqual(result.status_code, 302)

        self.login('hamlet')

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
        self.assertEqual(set(result["Cache-Control"].split(", ")),
                         {"must-revalidate", "no-store", "no-cache"})

        self.assert_length(queries, 42)
        self.assert_length(cache_mock.call_args_list, 5)

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
            'owner_id',
            'services',
            'user_id',
        ]

        realm_bots_actual_keys = sorted([str(key) for key in page_params['realm_bots'][0].keys()])
        self.assertEqual(realm_bots_actual_keys, realm_bots_expected_keys)

    def test_home_under_2fa_without_otp_device(self) -> None:
        with self.settings(TWO_FACTOR_AUTHENTICATION_ENABLED=True):
            self.login('iago')
            result = self._get_home_page()
            # Should be successful because otp device is not configured.
            self.assertEqual(result.status_code, 200)

    def test_home_under_2fa_with_otp_device(self) -> None:
        with self.settings(TWO_FACTOR_AUTHENTICATION_ENABLED=True):
            user_profile = self.example_user('iago')
            self.create_default_device(user_profile)
            self.login_user(user_profile)
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
        self.login('iago')
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

        self.login_user(main_user)

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
        doc = lxml.html.document_fromstring(result.content)
        [div] = doc.xpath("//div[@id='page-params']")
        page_params_json = div.get("data-params")
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
        self.login_user(user)

        for user_tos_version in [None, '1.1', '2.0.3.4']:
            user.tos_version = user_tos_version
            user.save()

            with \
                    self.settings(TERMS_OF_SERVICE='whatever'), \
                    self.settings(TOS_VERSION='99.99'):

                result = self.client_get('/', dict(stream='Denmark'))

            html = result.content.decode('utf-8')
            self.assertIn('Accept the new Terms of Service', html)

    def test_banned_desktop_app_versions(self) -> None:
        user = self.example_user('hamlet')
        self.login_user(user)

        result = self.client_get('/',
                                 HTTP_USER_AGENT="ZulipElectron/2.3.82")
        html = result.content.decode('utf-8')
        self.assertIn('You are using old version of the Zulip desktop', html)

    def test_unsupported_browser(self) -> None:
        user = self.example_user('hamlet')
        self.login_user(user)

        # currently we don't support IE, so some of IE's user agents are added.
        unsupported_user_agents = [
            "Mozilla/5.0 (compatible; MSIE 10.0; Windows NT 6.2)",
            "Mozilla/5.0 (Windows NT 10.0; Trident/7.0; rv:11.0) like Gecko",
            "Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 6.1; Trident/4.0)"
        ]
        for user_agent in unsupported_user_agents:
            result = self.client_get('/',
                                     HTTP_USER_AGENT=user_agent)
            html = result.content.decode('utf-8')
            self.assertIn('Internet Explorer is not supported by Zulip.', html)

    def test_terms_of_service_first_time_template(self) -> None:
        user = self.example_user('hamlet')
        self.login_user(user)

        user.tos_version = None
        user.save()

        with \
                self.settings(FIRST_TIME_TOS_TEMPLATE='hello.html'), \
                self.settings(TOS_VERSION='99.99'):
            result = self.client_post('/accounts/accept_terms/')
            self.assertEqual(result.status_code, 200)
            self.assert_in_response("I agree to the", result)
            self.assert_in_response("Chat for distributed teams", result)

    def test_accept_terms_of_service(self) -> None:
        self.login('hamlet')

        result = self.client_post('/accounts/accept_terms/')
        self.assertEqual(result.status_code, 200)
        self.assert_in_response("I agree to the", result)

        result = self.client_post('/accounts/accept_terms/', {'terms': True})
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result['Location'], '/')

    def test_bad_narrow(self) -> None:
        self.login('hamlet')
        with patch('logging.warning') as mock:
            result = self._get_home_page(stream='Invalid Stream')
        mock.assert_called_once()
        self.assertEqual(mock.call_args_list[0][0][0], "Invalid narrow requested, ignoring")
        self._sanity_check(result)

    def test_bad_pointer(self) -> None:
        user_profile = self.example_user('hamlet')
        user_profile.pointer = 999999
        user_profile.save()

        self.login_user(user_profile)
        result = self._get_home_page()
        self._sanity_check(result)

    def test_topic_narrow(self) -> None:
        self.login('hamlet')
        result = self._get_home_page(stream='Denmark', topic='lunch')
        self._sanity_check(result)
        html = result.content.decode('utf-8')
        self.assertIn('lunch', html)
        self.assertEqual(set(result["Cache-Control"].split(", ")),
                         {"must-revalidate", "no-store", "no-cache"})

    def test_notifications_stream(self) -> None:
        realm = get_realm('zulip')
        realm.notifications_stream_id = get_stream('Denmark', realm).id
        realm.save()
        self.login('hamlet')
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
        realm = get_realm('zulip')
        realm.signup_notifications_stream = get_stream('Denmark', realm)
        realm.save()
        self.login('hamlet')
        result = self._get_home_page()
        page_params = self._get_page_params(result)
        self.assertEqual(page_params['realm_signup_notifications_stream_id'], get_stream('Denmark', realm).id)

    @slow('creating users and loading home page')
    def test_people(self) -> None:
        hamlet = self.example_user('hamlet')
        realm = get_realm('zulip')
        self.login_user(hamlet)

        bots = {}
        for i in range(3):
            bots[i] = self.create_bot(
                owner=hamlet,
                bot_email='bot-%d@zulip.com' % (i,),
                bot_name='Bot %d' % (i,),
            )

        for i in range(3):
            defunct_user = self.create_non_active_user(
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
                    self.assertIn('owner_id', rec)
                else:
                    self.assertIn('is_bot', rec)
                    self.assertNotIn('is_active', rec)

        active_ids = {p['user_id'] for p in page_params['realm_users']}
        non_active_ids = {p['user_id'] for p in page_params['realm_non_active_users']}
        bot_ids = {p['user_id'] for p in page_params['realm_bots']}

        self.assertIn(hamlet.id, active_ids)
        self.assertIn(defunct_user.id, non_active_ids)

        # Bots can show up in multiple buckets.
        self.assertIn(bots[2].id, bot_ids)
        self.assertIn(bots[2].id, active_ids)

        # Make sure nobody got mis-bucketed.
        self.assertNotIn(hamlet.id, non_active_ids)
        self.assertNotIn(defunct_user.id, active_ids)

        cross_bots = page_params['cross_realm_bots']
        self.assertEqual(len(cross_bots), 3)
        cross_bots.sort(key=lambda d: d['email'])
        for cross_bot in cross_bots:
            # These are either nondeterministic or boring
            del cross_bot['timezone']
            del cross_bot['avatar_url']
            del cross_bot['date_joined']

        notification_bot = self.notification_bot()
        email_gateway_bot = get_system_bot(settings.EMAIL_GATEWAY_BOT)
        welcome_bot = get_system_bot(settings.WELCOME_BOT)

        by_email = lambda d: d['email']

        self.assertEqual(sorted(cross_bots, key=by_email), sorted([
            dict(
                avatar_version=email_gateway_bot.avatar_version,
                bot_owner_id=None,
                bot_type=1,
                email=email_gateway_bot.email,
                user_id=email_gateway_bot.id,
                full_name=email_gateway_bot.full_name,
                is_active=True,
                is_bot=True,
                is_admin=False,
                is_cross_realm_bot=True,
                is_guest=False
            ),
            dict(
                avatar_version=email_gateway_bot.avatar_version,
                bot_owner_id=None,
                bot_type=1,
                email=notification_bot.email,
                user_id=notification_bot.id,
                full_name=notification_bot.full_name,
                is_active=True,
                is_bot=True,
                is_admin=False,
                is_cross_realm_bot=True,
                is_guest=False
            ),
            dict(
                avatar_version=email_gateway_bot.avatar_version,
                bot_owner_id=None,
                bot_type=1,
                email=welcome_bot.email,
                user_id=welcome_bot.id,
                full_name=welcome_bot.full_name,
                is_active=True,
                is_bot=True,
                is_admin=False,
                is_cross_realm_bot=True,
                is_guest=False
            ),
        ], key=by_email))

    def test_new_stream(self) -> None:
        user_profile = self.example_user("hamlet")
        stream_name = 'New stream'
        self.subscribe(user_profile, stream_name)
        self.login_user(user_profile)
        result = self._get_home_page(stream=stream_name)
        page_params = self._get_page_params(result)
        self.assertEqual(page_params['narrow_stream'], stream_name)
        self.assertEqual(page_params['narrow'], [dict(operator='stream', operand=stream_name)])
        self.assertEqual(page_params['pointer'], -1)
        self.assertEqual(page_params['max_message_id'], -1)
        self.assertEqual(page_params['have_initial_messages'], False)

    def test_invites_by_admins_only(self) -> None:
        user_profile = self.example_user('hamlet')

        realm = user_profile.realm
        realm.invite_by_admins_only = True
        realm.save()

        self.login_user(user_profile)
        self.assertFalse(user_profile.is_realm_admin)
        result = self._get_home_page()
        html = result.content.decode('utf-8')
        self.assertNotIn('Invite more users', html)

        user_profile.role = UserProfile.ROLE_REALM_ADMINISTRATOR
        user_profile.save()
        result = self._get_home_page()
        html = result.content.decode('utf-8')
        self.assertIn('Invite more users', html)

    def test_show_invites_for_guest_users(self) -> None:
        user_profile = self.example_user('polonius')

        realm = user_profile.realm
        realm.invite_by_admins_only = False
        realm.save()

        self.login_user(user_profile)
        self.assertFalse(user_profile.is_realm_admin)
        self.assertFalse(get_realm('zulip').invite_by_admins_only)
        result = self._get_home_page()
        html = result.content.decode('utf-8')
        self.assertNotIn('Invite more users', html)

    def test_show_billing(self) -> None:
        customer = Customer.objects.create(realm=get_realm("zulip"), stripe_customer_id="cus_id")

        # realm admin, but no CustomerPlan -> no billing link
        user = self.example_user('iago')
        self.login_user(user)
        result_html = self._get_home_page().content.decode('utf-8')
        self.assertNotIn('Billing', result_html)

        # realm admin, with inactive CustomerPlan -> show billing link
        CustomerPlan.objects.create(customer=customer, billing_cycle_anchor=timezone_now(),
                                    billing_schedule=CustomerPlan.ANNUAL, next_invoice_date=timezone_now(),
                                    tier=CustomerPlan.STANDARD, status=CustomerPlan.ENDED)
        result_html = self._get_home_page().content.decode('utf-8')
        self.assertIn('Billing', result_html)

        # billing admin, with CustomerPlan -> show billing link
        user.role = UserProfile.ROLE_REALM_ADMINISTRATOR
        user.is_billing_admin = True
        user.save(update_fields=['role', 'is_billing_admin'])
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
        self.login('hamlet')

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
        self.login('hamlet')
        result = self.client_get("/desktop_home")
        self.assertEqual(result.status_code, 301)
        self.assertTrue(result["Location"].endswith("/desktop_home/"))
        result = self.client_get("/desktop_home/")
        self.assertEqual(result.status_code, 302)
        path = urllib.parse.urlparse(result['Location']).path
        self.assertEqual(path, "/")

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
                         "/user_avatars/%s/realm/logo.png?version=2" % (user_profile.realm_id,))

        page_params = {"night_mode": False}
        add_realm_logo_fields(page_params, user_profile.realm)
        self.assertEqual(compute_navbar_logo_url(page_params),
                         "/user_avatars/%s/realm/logo.png?version=2" % (user_profile.realm_id,))

        do_change_logo_source(user_profile.realm, Realm.LOGO_UPLOADED, night=True)
        page_params = {"night_mode": True}
        add_realm_logo_fields(page_params, user_profile.realm)
        self.assertEqual(compute_navbar_logo_url(page_params),
                         "/user_avatars/%s/realm/night_logo.png?version=2" % (user_profile.realm_id,))

        page_params = {"night_mode": False}
        add_realm_logo_fields(page_params, user_profile.realm)
        self.assertEqual(compute_navbar_logo_url(page_params),
                         "/user_avatars/%s/realm/logo.png?version=2" % (user_profile.realm_id,))

        # This configuration isn't super supported in the UI and is a
        # weird choice, but we have a test for it anyway.
        do_change_logo_source(user_profile.realm, Realm.LOGO_DEFAULT, night=False)
        page_params = {"night_mode": True}
        add_realm_logo_fields(page_params, user_profile.realm)
        self.assertEqual(compute_navbar_logo_url(page_params),
                         "/user_avatars/%s/realm/night_logo.png?version=2" % (user_profile.realm_id,))

        page_params = {"night_mode": False}
        add_realm_logo_fields(page_params, user_profile.realm)
        self.assertEqual(compute_navbar_logo_url(page_params),
                         "/static/images/logo/zulip-org-logo.png?version=0")

    def test_generate_204(self) -> None:
        self.login('hamlet')
        result = self.client_get("/api/v1/generate_204")
        self.assertEqual(result.status_code, 204)

    def test_furthest_read_time(self) -> None:
        msg_id = self.send_test_message("hello!", sender_name="iago")

        hamlet = self.example_user('hamlet')
        self.login_user(hamlet)
        self.client_post("/json/messages/flags",
                         {"messages": ujson.dumps([msg_id]),
                          "op": "add",
                          "flag": "read"})

        # Manually process the UserActivity
        now = timezone_now()
        activity_time = calendar.timegm(now.timetuple())
        user_activity_event = {'user_profile_id': hamlet.id,
                               'client': 'test-client',
                               'query': 'update_message_flags',
                               'time': activity_time}

        yesterday = now - timedelta(days=1)
        activity_time_2 = calendar.timegm(yesterday.timetuple())
        user_activity_event_2 = {'user_profile_id': hamlet.id,
                                 'client': 'test-client-2',
                                 'query': 'update_message_flags',
                                 'time': activity_time_2}
        UserActivityWorker().consume_batch([user_activity_event, user_activity_event_2])

        # verify furthest_read_time is last activity time, irrespective of client
        furthest_read_time = get_furthest_read_time(hamlet)
        self.assertGreaterEqual(furthest_read_time, activity_time)

        # Check when user has no activity
        UserActivity.objects.filter(user_profile=hamlet).delete()
        furthest_read_time = get_furthest_read_time(hamlet)
        self.assertIsNone(furthest_read_time)

        # Check no user profile handling
        furthest_read_time = get_furthest_read_time(None)
        self.assertIsNotNone(furthest_read_time)

    def test_subdomain_homepage(self) -> None:
        self.login('hamlet')
        with self.settings(ROOT_DOMAIN_LANDING_PAGE=True):
            with patch('zerver.views.home.get_subdomain', return_value=""):
                result = self._get_home_page()
            self.assertEqual(result.status_code, 200)
            self.assert_in_response('Chat for distributed teams', result)

            with patch('zerver.views.home.get_subdomain', return_value="subdomain"):
                result = self._get_home_page()
            self._sanity_check(result)

    def send_test_message(self, content: str, sender_name: str='iago',
                          stream_name: str='Denmark', topic_name: str='foo') -> int:
        sender = self.example_user(sender_name)
        return self.send_stream_message(sender, stream_name,
                                        content=content, topic_name=topic_name)

    def soft_activate_and_get_unread_count(self, stream: str='Denmark', topic: str='foo') -> int:
        stream_narrow = self._get_home_page(stream=stream, topic=topic)
        page_params = self._get_page_params(stream_narrow)
        return page_params['unread_msgs']['count']

    def test_unread_count_user_soft_deactivation(self) -> None:
        # In this test we make sure if a soft deactivated user had unread
        # messages before deactivation they remain same way after activation.
        long_term_idle_user = self.example_user('hamlet')
        self.login_user(long_term_idle_user)
        message = 'Test Message 1'
        self.send_test_message(message)
        with queries_captured() as queries:
            self.assertEqual(self.soft_activate_and_get_unread_count(), 1)
        query_count = len(queries)
        user_msg_list = get_user_messages(long_term_idle_user)
        self.assertEqual(user_msg_list[-1].content, message)
        self.logout()

        do_soft_deactivate_users([long_term_idle_user])

        self.login_user(long_term_idle_user)
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
        self.login_user(long_term_idle_user)
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
        self.login_user(long_term_idle_user)
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
        self.login_user(user)
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
        self.login_user(user)
        result = self._get_home_page()
        self.assertEqual(result.status_code, 200)

        page_params = self._get_page_params(result)
        self.assertEqual(page_params['default_language'], 'es')

    def test_compute_show_invites_and_add_streams_admin(self) -> None:
        user = self.example_user("iago")

        realm = user.realm
        realm.invite_by_admins_only = True
        realm.save()

        show_invites, show_add_streams = compute_show_invites_and_add_streams(user)
        self.assertEqual(show_invites, True)
        self.assertEqual(show_add_streams, True)

    def test_compute_show_invites_and_add_streams_require_admin(self) -> None:
        user = self.example_user("hamlet")

        realm = user.realm
        realm.invite_by_admins_only = True
        realm.save()

        show_invites, show_add_streams = compute_show_invites_and_add_streams(user)
        self.assertEqual(show_invites, False)
        self.assertEqual(show_add_streams, True)

    def test_compute_show_invites_and_add_streams_guest(self) -> None:
        user = self.example_user("polonius")

        show_invites, show_add_streams = compute_show_invites_and_add_streams(user)
        self.assertEqual(show_invites, False)
        self.assertEqual(show_add_streams, False)

    def test_compute_show_invites_and_add_streams_unauthenticated(self) -> None:
        show_invites, show_add_streams = compute_show_invites_and_add_streams(None)
        self.assertEqual(show_invites, False)
        self.assertEqual(show_add_streams, False)
