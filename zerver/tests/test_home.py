import calendar
from datetime import timedelta, timezone
from typing import TYPE_CHECKING, Any, Dict
from unittest.mock import patch
from urllib.parse import urlsplit

import orjson
import time_machine
from django.conf import settings
from django.test import override_settings
from django.utils.timezone import now as timezone_now

from corporate.models import Customer, CustomerPlan
from zerver.actions.create_user import do_create_user
from zerver.actions.realm_settings import do_change_realm_plan_type, do_set_realm_property
from zerver.actions.users import change_user_is_active
from zerver.lib.compatibility import LAST_SERVER_UPGRADE_TIME, is_outdated_server
from zerver.lib.home import (
    get_billing_info,
    get_furthest_read_time,
    promote_sponsoring_zulip_in_realm,
)
from zerver.lib.soft_deactivation import do_soft_deactivate_users
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import get_user_messages, queries_captured
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.models import DefaultStream, Draft, Realm, UserActivity, UserProfile
from zerver.models.realms import get_realm
from zerver.models.streams import get_stream
from zerver.models.users import get_system_bot, get_user
from zerver.worker.user_activity import UserActivityWorker

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as TestHttpResponse

logger_string = "zulip.soft_deactivation"


class HomeTest(ZulipTestCase):
    # Keep this list sorted!!!
    expected_page_params_keys = [
        "apps_page_url",
        "bot_types",
        "corporate_enabled",
        "development_environment",
        "furthest_read_time",
        "insecure_desktop_app",
        "is_spectator",
        "language_list",
        "login_page",
        "narrow",
        "narrow_stream",
        "needs_tutorial",
        "no_event_queue",
        "page_type",
        "promote_sponsoring_zulip",
        "request_language",
        "server_sentry_dsn",
        "show_billing",
        "show_plans",
        "show_remote_billing",
        "show_webathena",
        "sponsorship_pending",
        "state_data",
        "test_suite",
        "translation_data",
        "two_fa_enabled",
        "two_fa_enabled_user",
        "warn_no_email",
    ]
    expected_state_data_keys = [
        "alert_words",
        "avatar_source",
        "avatar_url",
        "avatar_url_medium",
        "can_create_private_streams",
        "can_create_public_streams",
        "can_create_streams",
        "can_create_web_public_streams",
        "can_invite_others_to_realm",
        "can_subscribe_other_users",
        "cross_realm_bots",
        "custom_profile_field_types",
        "custom_profile_fields",
        "delivery_email",
        "development_environment",
        "drafts",
        "email",
        "event_queue_longpoll_timeout_seconds",
        "full_name",
        "giphy_api_key",
        "giphy_rating_options",
        "has_zoom_token",
        "is_admin",
        "is_billing_admin",
        "is_guest",
        "is_moderator",
        "is_owner",
        "jitsi_server_url",
        "last_event_id",
        "max_avatar_file_size_mib",
        "max_file_upload_size_mib",
        "max_icon_file_size_mib",
        "max_logo_file_size_mib",
        "max_message_id",
        "max_message_length",
        "max_stream_description_length",
        "max_stream_name_length",
        "max_topic_length",
        "muted_topics",
        "muted_users",
        "never_subscribed",
        "onboarding_steps",
        "password_min_guesses",
        "password_min_length",
        "presences",
        "queue_id",
        "realm_add_custom_emoji_policy",
        "realm_allow_edit_history",
        "realm_allow_message_editing",
        "realm_authentication_methods",
        "realm_available_video_chat_providers",
        "realm_avatar_changes_disabled",
        "realm_bot_creation_policy",
        "realm_bot_domain",
        "realm_bots",
        "realm_can_access_all_users_group",
        "realm_create_multiuse_invite_group",
        "realm_create_private_stream_policy",
        "realm_create_public_stream_policy",
        "realm_create_web_public_stream_policy",
        "realm_date_created",
        "realm_default_code_block_language",
        "realm_default_external_accounts",
        "realm_default_language",
        "realm_default_stream_groups",
        "realm_default_streams",
        "realm_delete_own_message_policy",
        "realm_description",
        "realm_digest_emails_enabled",
        "realm_digest_weekday",
        "realm_disallow_disposable_email_addresses",
        "realm_domains",
        "realm_edit_topic_policy",
        "realm_email_auth_enabled",
        "realm_email_changes_disabled",
        "realm_emails_restricted_to_domains",
        "realm_embedded_bots",
        "realm_emoji",
        "realm_enable_guest_user_indicator",
        "realm_enable_read_receipts",
        "realm_enable_spectator_access",
        "realm_filters",
        "realm_giphy_rating",
        "realm_icon_source",
        "realm_icon_url",
        "realm_incoming_webhook_bots",
        "realm_inline_image_preview",
        "realm_inline_url_embed_preview",
        "realm_invite_required",
        "realm_invite_to_realm_policy",
        "realm_invite_to_stream_policy",
        "realm_is_zephyr_mirror_realm",
        "realm_jitsi_server_url",
        "realm_linkifiers",
        "realm_logo_source",
        "realm_logo_url",
        "realm_mandatory_topics",
        "realm_message_content_allowed_in_email_notifications",
        "realm_message_content_delete_limit_seconds",
        "realm_message_content_edit_limit_seconds",
        "realm_message_retention_days",
        "realm_move_messages_between_streams_limit_seconds",
        "realm_move_messages_between_streams_policy",
        "realm_move_messages_within_stream_limit_seconds",
        "realm_name",
        "realm_name_changes_disabled",
        "realm_new_stream_announcements_stream_id",
        "realm_night_logo_source",
        "realm_night_logo_url",
        "realm_non_active_users",
        "realm_org_type",
        "realm_password_auth_enabled",
        "realm_plan_type",
        "realm_playgrounds",
        "realm_presence_disabled",
        "realm_private_message_policy",
        "realm_push_notifications_enabled",
        "realm_push_notifications_enabled_end_timestamp",
        "realm_require_unique_names",
        "realm_send_welcome_emails",
        "realm_signup_announcements_stream_id",
        "realm_upload_quota_mib",
        "realm_uri",
        "realm_user_group_edit_policy",
        "realm_user_groups",
        "realm_user_settings_defaults",
        "realm_users",
        "realm_video_chat_provider",
        "realm_waiting_period_threshold",
        "realm_want_advertise_in_communities_directory",
        "realm_wildcard_mention_policy",
        "realm_zulip_update_announcements_stream_id",
        "recent_private_conversations",
        "scheduled_messages",
        "server_avatar_changes_disabled",
        "server_emoji_data_url",
        "server_generation",
        "server_inline_image_preview",
        "server_inline_url_embed_preview",
        "server_jitsi_server_url",
        "server_name_changes_disabled",
        "server_needs_upgrade",
        "server_presence_offline_threshold_seconds",
        "server_presence_ping_interval_seconds",
        "server_supported_permission_settings",
        "server_timestamp",
        "server_typing_started_expiry_period_milliseconds",
        "server_typing_started_wait_period_milliseconds",
        "server_typing_stopped_wait_period_milliseconds",
        "server_web_public_streams_enabled",
        "settings_send_digest_emails",
        "starred_messages",
        "stop_words",
        "subscriptions",
        "unread_msgs",
        "unsubscribed",
        "upgrade_text_for_wide_organization_logo",
        "user_id",
        "user_settings",
        "user_status",
        "user_topics",
        "zulip_feature_level",
        "zulip_merge_base",
        "zulip_plan_is_not_limited",
        "zulip_version",
    ]

    def test_home(self) -> None:
        # Keep this list sorted!!!
        html_bits = [
            "message_feed_errors_container",
            "app-loading-logo",
            # Verify that the app styles get included
            "app-stubentry.js",
            "data-params",
        ]

        self.login("hamlet")

        # Create bot for realm_bots testing. Must be done before fetching home_page.
        bot_info = {
            "full_name": "The Bot of Hamlet",
            "short_name": "hambot",
        }
        self.client_post("/json/bots", bot_info)

        # Verify succeeds once logged-in
        with self.assert_database_query_count(51):
            with patch("zerver.lib.cache.cache_set") as cache_mock:
                result = self._get_home_page(stream="Denmark")
                self.check_rendered_logged_in_app(result)
        self.assertEqual(
            set(result["Cache-Control"].split(", ")), {"must-revalidate", "no-store", "no-cache"}
        )

        self.assert_length(cache_mock.call_args_list, 6)

        html = result.content.decode()

        for html_bit in html_bits:
            if html_bit not in html:
                raise AssertionError(f"{html_bit} not in result")

        page_params = self._get_page_params(result)

        self.assertCountEqual(page_params, self.expected_page_params_keys)
        self.assertCountEqual(page_params["state_data"], self.expected_state_data_keys)

        # TODO: Inspect the page_params data further.
        # print(orjson.dumps(page_params, option=orjson.OPT_INDENT_2).decode())
        realm_bots_expected_keys = [
            "api_key",
            "avatar_url",
            "bot_type",
            "default_all_public_streams",
            "default_events_register_stream",
            "default_sending_stream",
            "email",
            "full_name",
            "is_active",
            "owner_id",
            "services",
            "user_id",
        ]

        self.assertCountEqual(page_params["state_data"]["realm_bots"][0], realm_bots_expected_keys)

    def test_home_demo_organization(self) -> None:
        realm = get_realm("zulip")

        # We construct a scheduled deletion date that's definitely in
        # the future, regardless of how long ago the Zulip realm was
        # created.
        realm.demo_organization_scheduled_deletion_date = timezone_now() + timedelta(days=1)
        realm.save()
        self.login("hamlet")

        # Verify succeeds once logged-in
        with queries_captured():
            with patch("zerver.lib.cache.cache_set"):
                result = self._get_home_page(stream="Denmark")
                self.check_rendered_logged_in_app(result)

        page_params = self._get_page_params(result)
        self.assertCountEqual(page_params, self.expected_page_params_keys)
        expected_state_data_keys = [
            *self.expected_state_data_keys,
            "demo_organization_scheduled_deletion_date",
        ]
        self.assertCountEqual(page_params["state_data"], expected_state_data_keys)

    def test_logged_out_home(self) -> None:
        realm = get_realm("zulip")
        do_set_realm_property(realm, "enable_spectator_access", False, acting_user=None)

        # Redirect to login if spectator access is disabled.
        result = self.client_get("/")
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], "/login/")

        # Load web app directly if spectator access is enabled.
        do_set_realm_property(realm, "enable_spectator_access", True, acting_user=None)
        result = self.client_get("/")
        self.assertEqual(result.status_code, 200)

        # Check no unnecessary params are passed to spectators.
        page_params = self._get_page_params(result)
        self.assertEqual(page_params["is_spectator"], True)
        expected_keys = [
            "apps_page_url",
            "bot_types",
            "corporate_enabled",
            "development_environment",
            "furthest_read_time",
            "insecure_desktop_app",
            "is_spectator",
            "language_cookie_name",
            "language_list",
            "login_page",
            "needs_tutorial",
            "no_event_queue",
            "page_type",
            "promote_sponsoring_zulip",
            "realm_rendered_description",
            "request_language",
            "server_sentry_dsn",
            "show_billing",
            "show_plans",
            "show_remote_billing",
            "show_webathena",
            "sponsorship_pending",
            "state_data",
            "test_suite",
            "translation_data",
            "two_fa_enabled",
            "two_fa_enabled_user",
            "warn_no_email",
        ]
        self.assertCountEqual(page_params, expected_keys)
        self.assertIsNone(page_params["state_data"])

    def test_realm_authentication_methods(self) -> None:
        realm = get_realm("zulip")
        self.login("desdemona")

        with self.settings(
            AUTHENTICATION_BACKENDS=(
                "zproject.backends.EmailAuthBackend",
                "zproject.backends.SAMLAuthBackend",
                "zproject.backends.AzureADAuthBackend",
            )
        ):
            result = self._get_home_page()
            state_data = self._get_page_params(result)["state_data"]

            self.assertEqual(
                state_data["realm_authentication_methods"],
                {
                    "Email": {"enabled": True, "available": True},
                    "AzureAD": {
                        "enabled": True,
                        "available": False,
                        "unavailable_reason": "You need to upgrade to the Zulip Cloud Standard plan to use this authentication method.",
                    },
                    "SAML": {
                        "enabled": True,
                        "available": False,
                        "unavailable_reason": "You need to upgrade to the Zulip Cloud Plus plan to use this authentication method.",
                    },
                },
            )

            # Now try with BILLING_ENABLED=False. This simulates a self-hosted deployment
            # instead of Zulip Cloud. In this case, all authentication methods should be available.
            with self.settings(BILLING_ENABLED=False):
                result = self._get_home_page()
                state_data = self._get_page_params(result)["state_data"]

                self.assertEqual(
                    state_data["realm_authentication_methods"],
                    {
                        "Email": {"enabled": True, "available": True},
                        "AzureAD": {
                            "enabled": True,
                            "available": True,
                        },
                        "SAML": {
                            "enabled": True,
                            "available": True,
                        },
                    },
                )

        with self.settings(
            AUTHENTICATION_BACKENDS=(
                "zproject.backends.EmailAuthBackend",
                "zproject.backends.SAMLAuthBackend",
            )
        ):
            result = self._get_home_page()
            state_data = self._get_page_params(result)["state_data"]

            self.assertEqual(
                state_data["realm_authentication_methods"],
                {
                    "Email": {"enabled": True, "available": True},
                    "SAML": {
                        "enabled": True,
                        "available": False,
                        "unavailable_reason": "You need to upgrade to the Zulip Cloud Plus plan to use this authentication method.",
                    },
                },
            )

        # Changing the plan_type to Standard grants access to AzureAD, but not SAML:
        do_change_realm_plan_type(realm, Realm.PLAN_TYPE_STANDARD, acting_user=None)

        with self.settings(
            AUTHENTICATION_BACKENDS=(
                "zproject.backends.EmailAuthBackend",
                "zproject.backends.SAMLAuthBackend",
                "zproject.backends.AzureADAuthBackend",
            )
        ):
            result = self._get_home_page()
            state_data = self._get_page_params(result)["state_data"]

            self.assertEqual(
                state_data["realm_authentication_methods"],
                {
                    "Email": {"enabled": True, "available": True},
                    "AzureAD": {
                        "enabled": True,
                        "available": True,
                    },
                    "SAML": {
                        "enabled": True,
                        "available": False,
                        "unavailable_reason": "You need to upgrade to the Zulip Cloud Plus plan to use this authentication method.",
                    },
                },
            )

            # Now upgrade to Plus and verify that both SAML and AzureAD are available.
            do_change_realm_plan_type(realm, Realm.PLAN_TYPE_PLUS, acting_user=None)
            result = self._get_home_page()
            state_data = self._get_page_params(result)["state_data"]

            self.assertEqual(
                state_data["realm_authentication_methods"],
                {
                    "Email": {"enabled": True, "available": True},
                    "AzureAD": {
                        "enabled": True,
                        "available": True,
                    },
                    "SAML": {
                        "enabled": True,
                        "available": True,
                    },
                },
            )

    def test_sentry_keys(self) -> None:
        def home_params() -> Dict[str, Any]:
            result = self._get_home_page()
            self.assertEqual(result.status_code, 200)
            return self._get_page_params(result)

        self.login("hamlet")
        page_params = home_params()
        self.assertEqual(page_params["server_sentry_dsn"], None)
        self.assertEqual(
            [], [key for key in page_params if key != "server_sentry_dsn" and "sentry" in key]
        )

        with self.settings(SENTRY_FRONTEND_DSN="https://aaa@bbb.ingest.sentry.io/1234"):
            page_params = home_params()
            self.assertEqual(
                page_params["server_sentry_dsn"], "https://aaa@bbb.ingest.sentry.io/1234"
            )
            self.assertEqual(page_params["realm_sentry_key"], "zulip")
            self.assertEqual(page_params["server_sentry_environment"], "development")
            self.assertEqual(page_params["server_sentry_sample_rate"], 1.0)
            self.assertEqual(page_params["server_sentry_trace_rate"], 0.1)

        # Make sure these still exist for logged-out users as well
        realm = get_realm("zulip")
        do_set_realm_property(realm, "enable_spectator_access", True, acting_user=None)
        self.logout()
        page_params = home_params()
        self.assertEqual(page_params["server_sentry_dsn"], None)
        self.assertEqual(
            [], [key for key in page_params if key != "server_sentry_dsn" and "sentry" in key]
        )

        with self.settings(SENTRY_FRONTEND_DSN="https://aaa@bbb.ingest.sentry.io/1234"):
            page_params = home_params()
            self.assertEqual(
                page_params["server_sentry_dsn"], "https://aaa@bbb.ingest.sentry.io/1234"
            )
            self.assertEqual(page_params["realm_sentry_key"], "zulip")
            self.assertEqual(page_params["server_sentry_environment"], "development")
            self.assertEqual(page_params["server_sentry_sample_rate"], 1.0)
            self.assertEqual(page_params["server_sentry_trace_rate"], 0.1)

    def test_home_under_2fa_without_otp_device(self) -> None:
        with self.settings(TWO_FACTOR_AUTHENTICATION_ENABLED=True):
            self.login("iago")
            result = self._get_home_page()
            # Should be successful because otp device is not configured.
            self.check_rendered_logged_in_app(result)

    def test_home_under_2fa_with_otp_device(self) -> None:
        with self.settings(TWO_FACTOR_AUTHENTICATION_ENABLED=True):
            user_profile = self.example_user("iago")
            self.create_default_device(user_profile)
            self.login_user(user_profile)
            result = self._get_home_page()
            # User should not log in because otp device is configured but
            # 2fa login function was not called.
            self.assertEqual(result.status_code, 302)

            self.login_2fa(user_profile)
            result = self._get_home_page()
            # Should be successful after calling 2fa login function.
            self.check_rendered_logged_in_app(result)

    @override_settings(TERMS_OF_SERVICE_VERSION=None)
    def test_num_queries_for_realm_admin(self) -> None:
        # Verify number of queries for Realm admin isn't much higher than for normal users.
        self.login("iago")
        with self.assert_database_query_count(51):
            with patch("zerver.lib.cache.cache_set") as cache_mock:
                result = self._get_home_page()
                self.check_rendered_logged_in_app(result)
                self.assert_length(cache_mock.call_args_list, 7)

    def test_num_queries_with_streams(self) -> None:
        main_user = self.example_user("hamlet")
        other_user = self.example_user("cordelia")

        realm_id = main_user.realm_id

        self.login_user(main_user)

        # Try to make page-load do extra work for various subscribed
        # streams.
        for i in range(10):
            stream_name = "test_stream_" + str(i)
            stream = self.make_stream(stream_name)
            DefaultStream.objects.create(
                realm_id=realm_id,
                stream_id=stream.id,
            )
            for user in [main_user, other_user]:
                self.subscribe(user, stream_name)

        # Simulate hitting the page the first time to avoid some noise
        # related to initial logins.
        self._get_home_page()

        # Then for the second page load, measure the number of queries.
        with self.assert_database_query_count(46):
            result = self._get_home_page()

        # Do a sanity check that our new streams were in the payload.
        html = result.content.decode()
        self.assertIn("test_stream_7", html)

    def _get_home_page(self, **kwargs: Any) -> "TestHttpResponse":
        with patch("zerver.lib.events.request_event_queue", return_value=42), patch(
            "zerver.lib.events.get_user_events", return_value=[]
        ):
            result = self.client_get("/", dict(**kwargs))
        return result

    def _sanity_check(self, result: "TestHttpResponse") -> None:
        """
        Use this for tests that are geared toward specific edge cases, but
        which still want the home page to load properly.
        """
        html = result.content.decode()
        if "message_feed_errors_container" not in html:
            raise AssertionError("Home page probably did not load.")

    def test_terms_of_service(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)

        for user_tos_version in [None, "-1", "1.1", "2.0.3.4"]:
            user.tos_version = user_tos_version
            user.save()

            with self.settings(TERMS_OF_SERVICE_VERSION="99.99"):
                result = self.client_get("/", dict(stream="Denmark"))

            html = result.content.decode()
            self.assertIn("Accept the Terms of Service", html)

    def test_banned_desktop_app_versions(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)

        result = self.client_get("/", HTTP_USER_AGENT="ZulipElectron/2.3.82")
        html = result.content.decode()
        self.assertIn("You are using old version of the Zulip desktop", html)

    def test_unsupported_browser(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)

        # currently we don't support IE, so some of IE's user agents are added.
        unsupported_user_agents = [
            "Mozilla/5.0 (compatible; MSIE 10.0; Windows NT 6.2)",
            "Mozilla/5.0 (Windows NT 10.0; Trident/7.0; rv:11.0) like Gecko",
            "Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 6.1; Trident/4.0)",
        ]
        for user_agent in unsupported_user_agents:
            result = self.client_get("/", HTTP_USER_AGENT=user_agent)
            html = result.content.decode()
            self.assertIn("Internet Explorer is not supported by Zulip.", html)

    def test_terms_of_service_first_time_template(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)

        user.tos_version = UserProfile.TOS_VERSION_BEFORE_FIRST_LOGIN
        user.save()

        with self.settings(
            FIRST_TIME_TERMS_OF_SERVICE_TEMPLATE="corporate/hello.html"
        ), self.settings(TERMS_OF_SERVICE_VERSION="99.99"):
            result = self.client_post("/accounts/accept_terms/")
            self.assertEqual(result.status_code, 200)
            self.assert_in_response("I agree to the", result)
            self.assert_in_response("your mission-critical communications with Zulip", result)

    def test_accept_terms_of_service(self) -> None:
        self.login("hamlet")

        result = self.client_post("/accounts/accept_terms/")
        self.assertEqual(result.status_code, 200)
        self.assert_in_response("I agree to the", result)

        result = self.client_post("/accounts/accept_terms/", {"terms": True})
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], "/")

        user = self.example_user("hamlet")
        user.tos_version = "-1"
        user.save()

        result = self.client_post("/accounts/accept_terms/")
        self.assertEqual(result.status_code, 200)
        self.assert_in_response("I agree to the", result)
        self.assert_in_response(
            "Administrators of this Zulip organization will be able to see this email address.",
            result,
        )

        result = self.client_post(
            "/accounts/accept_terms/",
            {
                "terms": True,
                "email_address_visibility": UserProfile.EMAIL_ADDRESS_VISIBILITY_MODERATORS,
            },
        )
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], "/")

        user = self.example_user("hamlet")
        self.assertEqual(
            user.email_address_visibility, UserProfile.EMAIL_ADDRESS_VISIBILITY_MODERATORS
        )

    def test_set_email_address_visibility_without_terms_of_service(self) -> None:
        self.login("hamlet")
        user = self.example_user("hamlet")
        user.tos_version = "-1"
        user.save()

        with self.settings(TERMS_OF_SERVICE_VERSION=None):
            result = self.client_get("/", dict(stream="Denmark"))
            self.assertEqual(result.status_code, 200)
            self.assert_in_response(
                "Administrators of this Zulip organization will be able to see this email address.",
                result,
            )

            result = self.client_post(
                "/accounts/accept_terms/",
                {
                    "email_address_visibility": UserProfile.EMAIL_ADDRESS_VISIBILITY_MODERATORS,
                },
            )
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result["Location"], "/")

            user = self.example_user("hamlet")
            self.assertEqual(
                user.email_address_visibility, UserProfile.EMAIL_ADDRESS_VISIBILITY_MODERATORS
            )

    def test_bad_narrow(self) -> None:
        self.login("hamlet")
        with self.assertLogs(level="WARNING") as m:
            result = self._get_home_page(stream="Invalid Stream")
            self.assertEqual(m.output, ["WARNING:root:Invalid narrow requested, ignoring"])
        self._sanity_check(result)

    def test_topic_narrow(self) -> None:
        self.login("hamlet")
        result = self._get_home_page(stream="Denmark", topic="lunch")
        self._sanity_check(result)
        html = result.content.decode()
        self.assertIn("lunch", html)
        self.assertEqual(
            set(result["Cache-Control"].split(", ")), {"must-revalidate", "no-store", "no-cache"}
        )

    def test_new_stream_announcements_stream(self) -> None:
        realm = get_realm("zulip")
        realm.new_stream_announcements_stream_id = get_stream("Denmark", realm).id
        realm.save()
        self.login("hamlet")
        result = self._get_home_page()
        page_params = self._get_page_params(result)
        self.assertEqual(
            page_params["state_data"]["realm_new_stream_announcements_stream_id"],
            get_stream("Denmark", realm).id,
        )

    def create_bot(self, owner: UserProfile, bot_email: str, bot_name: str) -> UserProfile:
        user = do_create_user(
            email=bot_email,
            password="123",
            realm=owner.realm,
            full_name=bot_name,
            bot_type=UserProfile.DEFAULT_BOT,
            bot_owner=owner,
            acting_user=None,
        )
        return user

    def create_non_active_user(self, realm: Realm, email: str, name: str) -> UserProfile:
        user = do_create_user(
            email=email, password="123", realm=realm, full_name=name, acting_user=None
        )

        # Doing a full-stack deactivation would be expensive here,
        # and we really only need to flip the flag to get a valid
        # test.
        change_user_is_active(user, False)
        return user

    def test_signup_announcements_stream(self) -> None:
        realm = get_realm("zulip")
        realm.signup_announcements_stream = get_stream("Denmark", realm)
        realm.save()
        self.login("hamlet")
        result = self._get_home_page()
        page_params = self._get_page_params(result)
        self.assertEqual(
            page_params["state_data"]["realm_signup_announcements_stream_id"],
            get_stream("Denmark", realm).id,
        )

    def test_zulip_update_announcements_stream(self) -> None:
        realm = get_realm("zulip")
        realm.zulip_update_announcements_stream = get_stream("Denmark", realm)
        realm.save()
        self.login("hamlet")
        result = self._get_home_page()
        page_params = self._get_page_params(result)
        self.assertEqual(
            page_params["state_data"]["realm_zulip_update_announcements_stream_id"],
            get_stream("Denmark", realm).id,
        )

    def test_people(self) -> None:
        hamlet = self.example_user("hamlet")
        realm = get_realm("zulip")
        self.login_user(hamlet)

        bots = {}
        for i in range(3):
            bots[i] = self.create_bot(
                owner=hamlet,
                bot_email=f"bot-{i}@zulip.com",
                bot_name=f"Bot {i}",
            )

        for i in range(3):
            defunct_user = self.create_non_active_user(
                realm=realm,
                email=f"defunct-{i}@zulip.com",
                name=f"Defunct User {i}",
            )

        result = self._get_home_page()
        page_params = self._get_page_params(result)

        """
        We send three lists of users.  The first two below are disjoint
        lists of users, and the records we send for them have identical
        structure.

        The realm_bots bucket is somewhat redundant, since all bots will
        be in one of the first two buckets.  They do include fields, however,
        that normal users don't care about, such as default_sending_stream.
        """

        buckets = [
            "realm_users",
            "realm_non_active_users",
            "realm_bots",
        ]

        for field in buckets:
            users = page_params["state_data"][field]
            self.assertGreaterEqual(len(users), 3, field)
            for rec in users:
                self.assertEqual(rec["user_id"], get_user(rec["email"], realm).id)
                if field == "realm_bots":
                    self.assertNotIn("is_bot", rec)
                    self.assertIn("is_active", rec)
                    self.assertIn("owner_id", rec)
                else:
                    self.assertIn("is_bot", rec)
                    self.assertNotIn("is_active", rec)

        active_ids = {p["user_id"] for p in page_params["state_data"]["realm_users"]}
        non_active_ids = {p["user_id"] for p in page_params["state_data"]["realm_non_active_users"]}
        bot_ids = {p["user_id"] for p in page_params["state_data"]["realm_bots"]}

        self.assertIn(hamlet.id, active_ids)
        self.assertIn(defunct_user.id, non_active_ids)

        # Bots can show up in multiple buckets.
        self.assertIn(bots[2].id, bot_ids)
        self.assertIn(bots[2].id, active_ids)

        # Make sure nobody got misbucketed.
        self.assertNotIn(hamlet.id, non_active_ids)
        self.assertNotIn(defunct_user.id, active_ids)

        cross_bots = page_params["state_data"]["cross_realm_bots"]
        self.assert_length(cross_bots, 3)
        cross_bots.sort(key=lambda d: d["email"])
        for cross_bot in cross_bots:
            # These are either nondeterministic or boring
            del cross_bot["timezone"]
            del cross_bot["avatar_url"]
            del cross_bot["date_joined"]

        admin_realm = get_realm(settings.SYSTEM_BOT_REALM)
        cross_realm_notification_bot = self.notification_bot(admin_realm)
        cross_realm_email_gateway_bot = get_system_bot(settings.EMAIL_GATEWAY_BOT, admin_realm.id)
        cross_realm_welcome_bot = get_system_bot(settings.WELCOME_BOT, admin_realm.id)

        by_email = lambda d: d["email"]

        self.assertEqual(
            sorted(cross_bots, key=by_email),
            sorted(
                [
                    dict(
                        avatar_version=cross_realm_email_gateway_bot.avatar_version,
                        bot_owner_id=None,
                        bot_type=1,
                        delivery_email=cross_realm_email_gateway_bot.delivery_email,
                        email=cross_realm_email_gateway_bot.email,
                        user_id=cross_realm_email_gateway_bot.id,
                        full_name=cross_realm_email_gateway_bot.full_name,
                        is_active=True,
                        is_bot=True,
                        is_admin=False,
                        is_owner=False,
                        is_billing_admin=False,
                        role=cross_realm_email_gateway_bot.role,
                        is_system_bot=True,
                        is_guest=False,
                    ),
                    dict(
                        avatar_version=cross_realm_notification_bot.avatar_version,
                        bot_owner_id=None,
                        bot_type=1,
                        delivery_email=cross_realm_notification_bot.delivery_email,
                        email=cross_realm_notification_bot.email,
                        user_id=cross_realm_notification_bot.id,
                        full_name=cross_realm_notification_bot.full_name,
                        is_active=True,
                        is_bot=True,
                        is_admin=False,
                        is_owner=False,
                        is_billing_admin=False,
                        role=cross_realm_notification_bot.role,
                        is_system_bot=True,
                        is_guest=False,
                    ),
                    dict(
                        avatar_version=cross_realm_welcome_bot.avatar_version,
                        bot_owner_id=None,
                        bot_type=1,
                        delivery_email=cross_realm_welcome_bot.delivery_email,
                        email=cross_realm_welcome_bot.email,
                        user_id=cross_realm_welcome_bot.id,
                        full_name=cross_realm_welcome_bot.full_name,
                        is_active=True,
                        is_bot=True,
                        is_admin=False,
                        is_owner=False,
                        is_billing_admin=False,
                        role=cross_realm_welcome_bot.role,
                        is_system_bot=True,
                        is_guest=False,
                    ),
                ],
                key=by_email,
            ),
        )

    def test_new_stream(self) -> None:
        user_profile = self.example_user("hamlet")
        stream_name = "New stream"
        self.subscribe(user_profile, stream_name)
        self.login_user(user_profile)
        result = self._get_home_page(stream=stream_name)
        page_params = self._get_page_params(result)
        self.assertEqual(page_params["narrow_stream"], stream_name)
        self.assertEqual(page_params["narrow"], [dict(operator="stream", operand=stream_name)])
        self.assertEqual(page_params["state_data"]["max_message_id"], -1)

    @override_settings(PUSH_NOTIFICATION_BOUNCER_URL="https://push.zulip.org.example.com")
    def test_get_billing_info(self) -> None:
        user = self.example_user("desdemona")
        user.role = UserProfile.ROLE_REALM_OWNER
        user.save(update_fields=["role"])
        # realm owner, but no CustomerPlan and realm plan_type SELF_HOSTED -> neither billing link or plans
        with self.settings(CORPORATE_ENABLED=True):
            billing_info = get_billing_info(user)
        self.assertFalse(billing_info.show_billing)
        self.assertFalse(billing_info.show_plans)
        self.assertFalse(billing_info.sponsorship_pending)
        self.assertFalse(billing_info.show_remote_billing)

        # realm owner, with inactive CustomerPlan and realm plan_type SELF_HOSTED -> show only billing link
        customer = Customer.objects.create(realm=get_realm("zulip"), stripe_customer_id="cus_id")
        CustomerPlan.objects.create(
            customer=customer,
            billing_cycle_anchor=timezone_now(),
            billing_schedule=CustomerPlan.BILLING_SCHEDULE_ANNUAL,
            next_invoice_date=timezone_now(),
            tier=CustomerPlan.TIER_CLOUD_STANDARD,
            status=CustomerPlan.ENDED,
        )
        with self.settings(CORPORATE_ENABLED=True):
            billing_info = get_billing_info(user)
        self.assertTrue(billing_info.show_billing)
        self.assertFalse(billing_info.show_plans)
        self.assertFalse(billing_info.sponsorship_pending)
        self.assertFalse(billing_info.show_remote_billing)

        # realm owner, with inactive CustomerPlan and realm plan_type LIMITED -> show billing link and plans
        do_change_realm_plan_type(user.realm, Realm.PLAN_TYPE_LIMITED, acting_user=None)
        with self.settings(CORPORATE_ENABLED=True):
            billing_info = get_billing_info(user)
        self.assertTrue(billing_info.show_billing)
        self.assertTrue(billing_info.show_plans)
        self.assertFalse(billing_info.sponsorship_pending)
        self.assertFalse(billing_info.show_remote_billing)

        # Always false without CORPORATE_ENABLED
        with self.settings(CORPORATE_ENABLED=False):
            billing_info = get_billing_info(user)
        self.assertFalse(billing_info.show_billing)
        self.assertFalse(billing_info.show_plans)
        self.assertFalse(billing_info.sponsorship_pending)
        # show_remote_billing is independent of CORPORATE_ENABLED
        self.assertTrue(billing_info.show_remote_billing)

        # Always false without a UserProfile
        with self.settings(CORPORATE_ENABLED=True):
            billing_info = get_billing_info(None)
        self.assertFalse(billing_info.show_billing)
        self.assertFalse(billing_info.show_plans)
        self.assertFalse(billing_info.sponsorship_pending)
        self.assertFalse(billing_info.show_remote_billing)

        # realm admin, with CustomerPlan and realm plan_type LIMITED -> don't show any links
        # Only billing admin and realm owner have access to billing.
        user.role = UserProfile.ROLE_REALM_ADMINISTRATOR
        user.save(update_fields=["role"])
        with self.settings(CORPORATE_ENABLED=True):
            billing_info = get_billing_info(user)
        self.assertFalse(billing_info.show_billing)
        self.assertFalse(billing_info.show_plans)
        self.assertFalse(billing_info.sponsorship_pending)
        self.assertFalse(billing_info.show_remote_billing)

        # Self-hosted servers show remote billing, but not for a user without
        # billing access permission.
        with self.settings(CORPORATE_ENABLED=False):
            billing_info = get_billing_info(user)
        self.assertFalse(billing_info.show_remote_billing)

        # billing admin, with CustomerPlan and realm plan_type STANDARD -> show only billing link
        user.role = UserProfile.ROLE_MEMBER
        user.is_billing_admin = True
        do_change_realm_plan_type(user.realm, Realm.PLAN_TYPE_STANDARD, acting_user=None)
        user.save(update_fields=["role", "is_billing_admin"])
        with self.settings(CORPORATE_ENABLED=True):
            billing_info = get_billing_info(user)
        self.assertTrue(billing_info.show_billing)
        self.assertFalse(billing_info.show_plans)
        self.assertFalse(billing_info.sponsorship_pending)
        self.assertFalse(billing_info.show_remote_billing)

        # Self-hosted servers show remote billing for billing admins.
        with self.settings(CORPORATE_ENABLED=False):
            billing_info = get_billing_info(user)
        self.assertTrue(billing_info.show_remote_billing)

        # billing admin, with CustomerPlan and realm plan_type PLUS -> show only billing link
        do_change_realm_plan_type(user.realm, Realm.PLAN_TYPE_PLUS, acting_user=None)
        user.save(update_fields=["role", "is_billing_admin"])
        with self.settings(CORPORATE_ENABLED=True):
            billing_info = get_billing_info(user)
        self.assertTrue(billing_info.show_billing)
        self.assertFalse(billing_info.show_plans)
        self.assertFalse(billing_info.sponsorship_pending)
        self.assertFalse(billing_info.show_remote_billing)

        # member, with CustomerPlan and realm plan_type STANDARD -> neither billing link or plans
        do_change_realm_plan_type(user.realm, Realm.PLAN_TYPE_STANDARD, acting_user=None)
        user.is_billing_admin = False
        user.save(update_fields=["is_billing_admin"])
        with self.settings(CORPORATE_ENABLED=True):
            billing_info = get_billing_info(user)
        self.assertFalse(billing_info.show_billing)
        self.assertFalse(billing_info.show_plans)
        self.assertFalse(billing_info.sponsorship_pending)
        self.assertFalse(billing_info.show_remote_billing)

        # guest, with CustomerPlan and realm plan_type SELF_HOSTED -> neither billing link or plans
        user.role = UserProfile.ROLE_GUEST
        user.save(update_fields=["role"])
        do_change_realm_plan_type(user.realm, Realm.PLAN_TYPE_SELF_HOSTED, acting_user=None)
        with self.settings(CORPORATE_ENABLED=True):
            billing_info = get_billing_info(user)
        self.assertFalse(billing_info.show_billing)
        self.assertFalse(billing_info.show_plans)
        self.assertFalse(billing_info.sponsorship_pending)
        self.assertFalse(billing_info.show_remote_billing)

        # billing admin, but no CustomerPlan and realm plan_type SELF_HOSTED -> neither billing link or plans
        user.role = UserProfile.ROLE_MEMBER
        user.is_billing_admin = True
        user.save(update_fields=["role", "is_billing_admin"])
        CustomerPlan.objects.all().delete()
        with self.settings(CORPORATE_ENABLED=True):
            billing_info = get_billing_info(user)
        self.assertFalse(billing_info.show_billing)
        self.assertFalse(billing_info.show_plans)
        self.assertFalse(billing_info.sponsorship_pending)
        self.assertFalse(billing_info.show_remote_billing)

        # billing admin, with sponsorship pending and realm plan_type SELF_HOSTED -> show only sponsorship pending link
        customer.sponsorship_pending = True
        customer.save(update_fields=["sponsorship_pending"])
        with self.settings(CORPORATE_ENABLED=True):
            billing_info = get_billing_info(user)
        self.assertFalse(billing_info.show_billing)
        self.assertFalse(billing_info.show_plans)
        self.assertTrue(billing_info.sponsorship_pending)
        self.assertFalse(billing_info.show_remote_billing)

        # billing admin, no customer object and realm plan_type SELF_HOSTED -> no links
        customer.delete()
        with self.settings(CORPORATE_ENABLED=True):
            billing_info = get_billing_info(user)
        self.assertFalse(billing_info.show_billing)
        self.assertFalse(billing_info.show_plans)
        self.assertFalse(billing_info.sponsorship_pending)
        self.assertFalse(billing_info.show_remote_billing)

        # If the server doesn't have the push bouncer configured,
        # remote billing should be shown anyway, as the billing endpoint
        # is supposed show a useful error page.
        with self.settings(PUSH_NOTIFICATION_BOUNCER_URL=None, CORPORATE_ENABLED=False):
            billing_info = get_billing_info(user)
        self.assertTrue(billing_info.show_remote_billing)

    def test_promote_sponsoring_zulip_in_realm(self) -> None:
        realm = get_realm("zulip")

        do_change_realm_plan_type(realm, Realm.PLAN_TYPE_STANDARD_FREE, acting_user=None)
        promote_zulip = promote_sponsoring_zulip_in_realm(realm)
        self.assertTrue(promote_zulip)

        with self.settings(PROMOTE_SPONSORING_ZULIP=False):
            promote_zulip = promote_sponsoring_zulip_in_realm(realm)
        self.assertFalse(promote_zulip)

        do_change_realm_plan_type(realm, Realm.PLAN_TYPE_STANDARD_FREE, acting_user=None)
        promote_zulip = promote_sponsoring_zulip_in_realm(realm)
        self.assertTrue(promote_zulip)

        do_change_realm_plan_type(realm, Realm.PLAN_TYPE_LIMITED, acting_user=None)
        promote_zulip = promote_sponsoring_zulip_in_realm(realm)
        self.assertFalse(promote_zulip)

        do_change_realm_plan_type(realm, Realm.PLAN_TYPE_STANDARD, acting_user=None)
        promote_zulip = promote_sponsoring_zulip_in_realm(realm)
        self.assertFalse(promote_zulip)

    def test_desktop_home(self) -> None:
        self.login("hamlet")
        result = self.client_get("/desktop_home")
        self.assertEqual(result.status_code, 301)
        self.assertTrue(result["Location"].endswith("/desktop_home/"))
        result = self.client_get("/desktop_home/")
        self.assertEqual(result.status_code, 302)
        path = urlsplit(result["Location"]).path
        self.assertEqual(path, "/")

    @override_settings(SERVER_UPGRADE_NAG_DEADLINE_DAYS=365)
    def test_is_outdated_server(self) -> None:
        # Check when server_upgrade_nag_deadline > last_server_upgrade_time
        hamlet = self.example_user("hamlet")
        iago = self.example_user("iago")
        now = LAST_SERVER_UPGRADE_TIME.replace(tzinfo=timezone.utc)
        with patch("os.path.getmtime", return_value=now.timestamp()):
            with time_machine.travel((now + timedelta(days=10)), tick=False):
                self.assertEqual(is_outdated_server(iago), False)
                self.assertEqual(is_outdated_server(hamlet), False)
                self.assertEqual(is_outdated_server(None), False)

            with time_machine.travel((now + timedelta(days=397)), tick=False):
                self.assertEqual(is_outdated_server(iago), True)
                self.assertEqual(is_outdated_server(hamlet), True)
                self.assertEqual(is_outdated_server(None), True)

            with time_machine.travel((now + timedelta(days=380)), tick=False):
                self.assertEqual(is_outdated_server(iago), True)
                self.assertEqual(is_outdated_server(hamlet), False)
                self.assertEqual(is_outdated_server(None), False)

    def test_furthest_read_time(self) -> None:
        msg_id = self.send_test_message("hello!", sender_name="iago")

        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)
        self.client_post(
            "/json/messages/flags",
            {"messages": orjson.dumps([msg_id]).decode(), "op": "add", "flag": "read"},
        )

        # Manually process the UserActivity
        now = timezone_now()
        activity_time = calendar.timegm(now.timetuple())
        user_activity_event = {
            "user_profile_id": hamlet.id,
            "client_id": 1,
            "query": "update_message_flags",
            "time": activity_time,
        }

        yesterday = now - timedelta(days=1)
        activity_time_2 = calendar.timegm(yesterday.timetuple())
        user_activity_event_2 = {
            "user_profile_id": hamlet.id,
            "client_id": 2,
            "query": "update_message_flags",
            "time": activity_time_2,
        }
        UserActivityWorker().consume_batch([user_activity_event, user_activity_event_2])

        # verify furthest_read_time is last activity time, irrespective of client
        furthest_read_time = get_furthest_read_time(hamlet)
        assert furthest_read_time is not None
        self.assertGreaterEqual(furthest_read_time, activity_time)

        # Check when user has no activity
        UserActivity.objects.filter(user_profile=hamlet).delete()
        furthest_read_time = get_furthest_read_time(hamlet)
        self.assertIsNone(furthest_read_time)

        # Check no user profile handling
        furthest_read_time = get_furthest_read_time(None)
        self.assertIsNotNone(furthest_read_time)

    def test_subdomain_homepage(self) -> None:
        self.login("hamlet")
        with self.settings(ROOT_DOMAIN_LANDING_PAGE=True):
            with patch("zerver.views.home.get_subdomain", return_value=""):
                result = self._get_home_page()
            self.assertEqual(result.status_code, 200)
            self.assert_in_response("your mission-critical communications with Zulip", result)

            with patch("zerver.views.home.get_subdomain", return_value="subdomain"):
                result = self._get_home_page()
            self._sanity_check(result)

    def test_special_subdomains_homepage(self) -> None:
        self.login("hamlet")
        with patch("zerver.views.home.get_subdomain", return_value="auth"):
            result = self._get_home_page()
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], "http://testserver")

        with patch("zerver.views.home.get_subdomain", return_value="selfhosting"):
            result = self._get_home_page()
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], "/serverlogin/")

    def send_test_message(
        self,
        content: str,
        sender_name: str = "iago",
        stream_name: str = "Denmark",
        topic_name: str = "foo",
    ) -> int:
        sender = self.example_user(sender_name)
        return self.send_stream_message(sender, stream_name, content=content, topic_name=topic_name)

    def soft_activate_and_get_unread_count(
        self, stream: str = "Denmark", topic_name: str = "foo"
    ) -> int:
        stream_narrow = self._get_home_page(stream=stream, topic=topic_name)
        page_params = self._get_page_params(stream_narrow)
        return page_params["state_data"]["unread_msgs"]["count"]

    def test_unread_count_user_soft_deactivation(self) -> None:
        # In this test we make sure if a soft deactivated user had unread
        # messages before deactivation they remain same way after activation.
        long_term_idle_user = self.example_user("hamlet")
        self.login_user(long_term_idle_user)
        message = "Test message 1"
        self.send_test_message(message)
        with queries_captured() as queries:
            self.assertEqual(self.soft_activate_and_get_unread_count(), 1)
        query_count = len(queries)
        user_msg_list = get_user_messages(long_term_idle_user)
        self.assertEqual(user_msg_list[-1].content, message)
        self.logout()

        with self.assertLogs(logger_string, level="INFO") as info_log:
            do_soft_deactivate_users([long_term_idle_user])
        self.assertEqual(
            info_log.output,
            [
                f"INFO:{logger_string}:Soft deactivated user {long_term_idle_user.id}",
                f"INFO:{logger_string}:Soft-deactivated batch of 1 users; 0 remain to process",
            ],
        )

        self.login_user(long_term_idle_user)
        message = "Test message 2"
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

    def test_multiple_user_soft_deactivations(self) -> None:
        long_term_idle_user = self.example_user("hamlet")
        # We are sending this message to ensure that long_term_idle_user has
        # at least one UserMessage row.
        self.send_test_message("Testing", sender_name="hamlet")
        with self.assertLogs(logger_string, level="INFO") as info_log:
            do_soft_deactivate_users([long_term_idle_user])
        self.assertEqual(
            info_log.output,
            [
                f"INFO:{logger_string}:Soft deactivated user {long_term_idle_user.id}",
                f"INFO:{logger_string}:Soft-deactivated batch of 1 users; 0 remain to process",
            ],
        )

        message = "Test message 1"
        self.send_test_message(message)
        self.login_user(long_term_idle_user)
        with queries_captured() as queries:
            self.assertEqual(self.soft_activate_and_get_unread_count(), 1)
        query_count = len(queries)
        long_term_idle_user.refresh_from_db()
        self.assertFalse(long_term_idle_user.long_term_idle)
        idle_user_msg_list = get_user_messages(long_term_idle_user)
        self.assertEqual(idle_user_msg_list[-1].content, message)

        message = "Test message 2"
        self.send_test_message(message)
        with queries_captured() as queries:
            self.assertEqual(self.soft_activate_and_get_unread_count(), 2)
        # Test here for query count to be at least 5 less than previous count.
        # This will assure add_missing_messages() isn't repeatedly called.
        self.assertGreaterEqual(query_count - len(queries), 5)
        idle_user_msg_list = get_user_messages(long_term_idle_user)
        self.assertEqual(idle_user_msg_list[-1].content, message)
        self.logout()

        with self.assertLogs(logger_string, level="INFO") as info_log:
            do_soft_deactivate_users([long_term_idle_user])
        self.assertEqual(
            info_log.output,
            [
                f"INFO:{logger_string}:Soft deactivated user {long_term_idle_user.id}",
                f"INFO:{logger_string}:Soft-deactivated batch of 1 users; 0 remain to process",
            ],
        )

        message = "Test message 3"
        self.send_test_message(message)
        self.login_user(long_term_idle_user)
        with queries_captured() as queries:
            self.assertEqual(self.soft_activate_and_get_unread_count(), 3)
        query_count = len(queries)
        long_term_idle_user.refresh_from_db()
        self.assertFalse(long_term_idle_user.long_term_idle)
        idle_user_msg_list = get_user_messages(long_term_idle_user)
        self.assertEqual(idle_user_msg_list[-1].content, message)

        message = "Test message 4"
        self.send_test_message(message)
        with queries_captured() as queries:
            self.assertEqual(self.soft_activate_and_get_unread_count(), 4)
        self.assertGreaterEqual(query_count - len(queries), 5)
        idle_user_msg_list = get_user_messages(long_term_idle_user)
        self.assertEqual(idle_user_msg_list[-1].content, message)
        self.logout()

    def test_url_language(self) -> None:
        user = self.example_user("hamlet")
        user.default_language = "es"
        user.save()
        self.login_user(user)
        result = self._get_home_page()
        self.check_rendered_logged_in_app(result)
        with patch("zerver.lib.events.request_event_queue", return_value=42), patch(
            "zerver.lib.events.get_user_events", return_value=[]
        ):
            result = self.client_get("/de/")
        page_params = self._get_page_params(result)
        self.assertEqual(page_params["state_data"]["user_settings"]["default_language"], "es")
        # TODO: Verify that the actual language we're using in the
        # translation data is German.

    def test_translation_data(self) -> None:
        user = self.example_user("hamlet")
        user.default_language = "es"
        user.save()
        self.login_user(user)
        result = self._get_home_page()
        self.check_rendered_logged_in_app(result)

        page_params = self._get_page_params(result)
        self.assertEqual(page_params["state_data"]["user_settings"]["default_language"], "es")

    # TODO: This test would likely be better written as a /register
    # API test with just the drafts event type, to avoid the
    # performance cost of fetching /.
    @override_settings(MAX_DRAFTS_IN_REGISTER_RESPONSE=5)
    def test_limit_drafts(self) -> None:
        hamlet = self.example_user("hamlet")
        base_time = timezone_now()
        initial_count = Draft.objects.count()

        step_value = timedelta(seconds=1)
        # Create 11 drafts.
        # TODO: This would be better done as an API request.
        draft_objects = [
            Draft(
                user_profile=hamlet,
                recipient=None,
                topic="",
                content="sample draft",
                last_edit_time=base_time + i * step_value,
            )
            for i in range(settings.MAX_DRAFTS_IN_REGISTER_RESPONSE + 1)
        ]
        Draft.objects.bulk_create(draft_objects)

        # Now fetch the drafts part of the initial state and make sure
        # that we only got back settings.MAX_DRAFTS_IN_REGISTER_RESPONSE.
        # No more. Also make sure that the drafts returned are the most
        # recently edited ones.
        self.login("hamlet")
        page_params = self._get_page_params(self._get_home_page())
        self.assertEqual(
            page_params["state_data"]["user_settings"]["enable_drafts_synchronization"], True
        )
        self.assert_length(
            page_params["state_data"]["drafts"], settings.MAX_DRAFTS_IN_REGISTER_RESPONSE
        )
        self.assertEqual(
            Draft.objects.count(), settings.MAX_DRAFTS_IN_REGISTER_RESPONSE + 1 + initial_count
        )
        # +2 for what's already in the test DB.
        for draft in page_params["state_data"]["drafts"]:
            self.assertNotEqual(draft["timestamp"], base_time)

    def test_realm_push_notifications_enabled_end_timestamp(self) -> None:
        self.login("hamlet")
        realm = get_realm("zulip")
        end_timestamp = timezone_now() + timedelta(days=1)
        realm.push_notifications_enabled_end_timestamp = end_timestamp
        realm.save()

        result = self._get_home_page(stream="Denmark")
        page_params = self._get_page_params(result)
        self.assertEqual(
            page_params["state_data"]["realm_push_notifications_enabled_end_timestamp"],
            datetime_to_timestamp(end_timestamp),
        )
