import calendar
from datetime import timedelta, timezone
from typing import TYPE_CHECKING, Any
from unittest.mock import patch
from urllib.parse import urlsplit

import orjson
import time_machine
from django.test import override_settings
from django.utils.timezone import now as timezone_now

from corporate.models.customers import Customer
from corporate.models.plans import CustomerPlan
from version import ZULIP_VERSION
from zerver.actions.realm_settings import do_change_realm_plan_type, do_set_realm_property
from zerver.lib.compatibility import LAST_SERVER_UPGRADE_TIME, is_outdated_server
from zerver.lib.events import has_pending_sponsorship_request
from zerver.lib.home import get_furthest_read_time, promote_sponsoring_zulip_in_realm
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import activate_push_notification_service
from zerver.lib.users import max_message_id_for_user
from zerver.models import Realm, UserActivity, UserProfile
from zerver.models.realms import get_realm
from zerver.tornado.django_api import EventQueueData
from zerver.worker.user_activity import UserActivityWorker

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as TestHttpResponse


class HomeTest(ZulipTestCase):
    # Keep this list sorted!!!
    expected_page_params_keys = [
        "apps_page_url",
        "corporate_enabled",
        "development_environment",
        "embedded_bots_enabled",
        "furthest_read_time",
        "insecure_desktop_app",
        "is_cloud_realm_with_discounted_plan",
        "is_spectator",
        "language_list",
        "login_page",
        "narrow",
        "narrow_stream",
        "no_event_queue",
        "non_workplace_pricing_eligible",
        "page_type",
        "presence_history_limit_days_for_web_app",
        "promote_sponsoring_zulip",
        "realm_rendered_description",
        "request_language",
        "show_try_zulip_modal",
        "state_data",
        "test_suite",
        "translation_data",
        "two_fa_enabled",
        "two_fa_enabled_user",
        "warn_no_email",
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

        # Verify succeeds once logged-in
        with (
            self.assert_database_query_count(55),
            patch("zerver.lib.cache.cache_set") as cache_mock,
        ):
            result = self._get_home_page(stream="Denmark")
            self.check_rendered_logged_in_app(result)
        self.assertEqual(
            set(result["Cache-Control"].split(", ")), {"must-revalidate", "no-store", "no-cache"}
        )

        self.assert_length(cache_mock.call_args_list, 7)

        html = result.content.decode()

        for html_bit in html_bits:
            if html_bit not in html:
                raise AssertionError(f"{html_bit} not in result")

        page_params = self._get_page_params(result)

        self.assertCountEqual(page_params, self.expected_page_params_keys)

    def test_home_demo_organization(self) -> None:
        demo_organization_owner = self.create_demo_organization_owner()
        realm = demo_organization_owner.realm

        result = self._get_home_page(subdomain=realm.subdomain, stream="Zulip")
        self.check_rendered_logged_in_app(result)

        page_params = self._get_page_params(result)
        self.assertCountEqual(page_params, self.expected_page_params_keys)

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
            "corporate_enabled",
            "development_environment",
            "embedded_bots_enabled",
            "furthest_read_time",
            "insecure_desktop_app",
            "is_cloud_realm_with_discounted_plan",
            "is_spectator",
            "language_cookie_name",
            "language_list",
            "login_page",
            "no_event_queue",
            "non_workplace_pricing_eligible",
            "page_type",
            "presence_history_limit_days_for_web_app",
            "promote_sponsoring_zulip",
            "realm_rendered_description",
            "request_language",
            "show_try_zulip_modal",
            "state_data",
            "test_suite",
            "translation_data",
            "two_fa_enabled",
            "two_fa_enabled_user",
            "warn_no_email",
        ]
        self.assertCountEqual(page_params, expected_keys)
        self.assertIsNone(page_params["state_data"])

        with self.settings(DEVELOPMENT=True):
            result = self.client_get("/?show_try_zulip_modal")
        self.assertEqual(result.status_code, 200)
        page_params = self._get_page_params(result)
        self.assertEqual(page_params["show_try_zulip_modal"], True)

    def test_home_has_llms_comment_when_web_public(self) -> None:
        """
        The homepage HTML includes a comment pointing LLMs to /llms.txt
        when the realm has web-public streams enabled.
        """
        realm = get_realm("zulip")
        do_set_realm_property(realm, "enable_spectator_access", True, acting_user=None)
        # Use spectator (logged-out) view to ensure the comment renders in that path.
        result = self.client_get("/")
        self.assertEqual(result.status_code, 200)
        html = result.content.decode()
        self.assertIn("AI assistant:", html)
        self.assertIn("/llms.txt", html)

    def test_home_fallback_llms_comment_when_not_web_public(self) -> None:
        """
        The homepage HTML includes a fallback comment informing LLMs that
        web-public channels are disabled when the realm does not allow
        web-public stream access.
        """
        realm = get_realm("zulip")
        do_set_realm_property(realm, "enable_spectator_access", False, acting_user=None)
        # Login as a regular user to get a 200 even without spectator access.
        self.login("hamlet")
        result = self._get_home_page()
        self.assertEqual(result.status_code, 200)
        html = result.content.decode()
        self.assertIn("AI assistant:", html)
        self.assertNotIn("/llms.txt", html)
        self.assertIn("does not have web-public channels", html)

    def test_sentry_keys(self) -> None:
        def sentry_params() -> dict[str, Any] | None:
            result = self._get_home_page()
            self.assertEqual(result.status_code, 200)
            return self._get_sentry_params(result)

        user = self.example_user("hamlet")
        self.login_user(user)
        self.assertIsNone(sentry_params())

        with self.settings(SENTRY_FRONTEND_DSN="https://aaa@bbb.ingest.sentry.io/1234"):
            self.assertEqual(
                sentry_params(),
                {
                    "dsn": "https://aaa@bbb.ingest.sentry.io/1234",
                    "environment": "development",
                    "realm_key": "zulip",
                    "sample_rate": 1.0,
                    "server_version": ZULIP_VERSION,
                    "trace_rate": 0.1,
                    "user": {"id": user.id, "role": "Member"},
                },
            )

        # Make sure these still exist for logged-out users as well
        realm = get_realm("zulip")
        do_set_realm_property(realm, "enable_spectator_access", True, acting_user=None)
        self.logout()
        self.assertIsNone(sentry_params())

        with self.settings(SENTRY_FRONTEND_DSN="https://aaa@bbb.ingest.sentry.io/1234"):
            self.assertEqual(
                sentry_params(),
                {
                    "dsn": "https://aaa@bbb.ingest.sentry.io/1234",
                    "environment": "development",
                    "realm_key": "zulip",
                    "sample_rate": 1.0,
                    "server_version": ZULIP_VERSION,
                    "trace_rate": 0.1,
                },
            )

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
    def test_home_reload(self) -> None:
        # When the client triggers a reload via ?state_data=deferred,
        # the server should skip the expensive do_events_register()
        # call and return state_data=None so the client fetches it
        # via /json/register instead. See #36094.
        self.login("hamlet")
        result = self.client_get("/", {"state_data": "deferred"})
        self.check_rendered_logged_in_app(result)

        page_params = self._get_page_params(result)
        self.assertIsNone(page_params["state_data"])
        self.assertTrue(page_params["no_event_queue"])
        self.assertFalse(page_params["is_spectator"])

    def _get_home_page(self, subdomain: str | None = None, **kwargs: Any) -> "TestHttpResponse":
        queue_data = EventQueueData(queue_id="test-queue-id", idle_queue_timeout_secs=600)
        with (
            patch("zerver.lib.events.request_event_queue", return_value=queue_data),
            patch("zerver.lib.events.get_user_events", return_value=[]),
        ):
            if subdomain:
                return self.client_get("/", dict(**kwargs), subdomain=subdomain)
            return self.client_get("/", dict(**kwargs))

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

        with (
            self.settings(FIRST_TIME_TERMS_OF_SERVICE_TEMPLATE="corporate/hello.html"),
            self.settings(TERMS_OF_SERVICE_VERSION="99.99"),
        ):
            result = self.client_post("/accounts/accept_terms/")
            self.assertEqual(result.status_code, 200)
            self.assert_in_response("I agree to the", result)
            self.assert_in_response("remote and flexible work", result)

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

        # Test is_imported_stub is set to False when user accepts terms of service.
        user.tos_version = "-1"
        user.is_imported_stub = True
        user.save()

        result = self.client_post("/accounts/accept_terms/", {"terms": True})
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], "/")

        user = self.example_user("hamlet")
        self.assertFalse(user.is_imported_stub)

        # Test date_joined is set to the current time when user logs in for the
        # first time.
        user.tos_version = UserProfile.TOS_VERSION_BEFORE_FIRST_LOGIN
        user.save()

        now = timezone_now()
        with time_machine.travel(now, tick=False):
            result = self.client_post("/accounts/accept_terms/", {"terms": True})
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], "/")

        user = self.example_user("hamlet")
        # Check that date_joined is updated to the time when user accepts ToS
        # when logging in for the first time.
        self.assertEqual(user.date_joined, now)

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

    def test_new_stream(self) -> None:
        user_profile = self.example_user("hamlet")
        stream_name = "New stream"
        self.subscribe(user_profile, stream_name)
        self.login_user(user_profile)
        result = self._get_home_page(stream=stream_name)
        page_params = self._get_page_params(result)
        self.assertEqual(page_params["narrow_stream"], stream_name)
        self.assertEqual(page_params["narrow"], [dict(operator="stream", operand=stream_name)])
        # max_message_id is the user's global latest message id, not
        # the narrow's; see local_message.ts for how it's consumed.
        self.assertEqual(
            page_params["state_data"]["max_message_id"],
            max_message_id_for_user(user_profile),
        )
        # The mini-window's desktop-notification suppression is now
        # applied client-side; the server returns the user's actual
        # setting unchanged.
        self.assertEqual(
            page_params["state_data"]["user_settings"]["enable_desktop_notifications"],
            user_profile.enable_desktop_notifications,
        )

    @activate_push_notification_service()
    def test_has_pending_sponsorship_request(self) -> None:
        user = self.example_user("desdemona")
        shiva = self.example_user("shiva")
        # realm owner, but no CustomerPlan and realm plan_type SELF_HOSTED -> don't show any links
        with self.settings(CORPORATE_ENABLED=True):
            sponsorship_pending = has_pending_sponsorship_request(user)
        self.assertFalse(sponsorship_pending)

        customer = Customer.objects.create(realm=get_realm("zulip"), stripe_customer_id="cus_id")
        CustomerPlan.objects.create(
            customer=customer,
            billing_cycle_anchor=timezone_now(),
            billing_schedule=CustomerPlan.BILLING_SCHEDULE_ANNUAL,
            next_invoice_date=timezone_now(),
            tier=CustomerPlan.TIER_CLOUD_STANDARD,
            status=CustomerPlan.ENDED,
        )
        # realm admin, with sponsorship pending and realm plan_type SELF_HOSTED -> show sponsorship pending link
        customer.sponsorship_pending = True
        customer.save(update_fields=["sponsorship_pending"])
        with self.settings(CORPORATE_ENABLED=True):
            sponsorship_pending = has_pending_sponsorship_request(user)
        self.assertTrue(sponsorship_pending)

        # Always false without CORPORATE_ENABLED
        with self.settings(CORPORATE_ENABLED=False):
            sponsorship_pending = has_pending_sponsorship_request(user)
        self.assertFalse(sponsorship_pending)

        # Always false without a UserProfile
        with self.settings(CORPORATE_ENABLED=True):
            sponsorship_pending = has_pending_sponsorship_request(None)
        self.assertFalse(sponsorship_pending)

        # realm moderator, with CustomerPlan and realm plan_type LIMITED -> don't show any links
        # Only realm admin and realm owner have access to billing.
        with self.settings(CORPORATE_ENABLED=True):
            sponsorship_pending = has_pending_sponsorship_request(shiva)
        self.assertFalse(sponsorship_pending)

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
        msg_id = self.send_stream_message(self.example_user("iago"), "Denmark", content="hello!")

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
            self.assert_in_response("remote and flexible work", result)

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

    def test_url_language(self) -> None:
        user = self.example_user("hamlet")
        user.default_language = "es"
        user.save()
        self.login_user(user)
        result = self._get_home_page()
        self.check_rendered_logged_in_app(result)
        queue_data = EventQueueData(queue_id="test-queue-id", idle_queue_timeout_secs=600)
        with (
            patch("zerver.lib.events.request_event_queue", return_value=queue_data),
            patch("zerver.lib.events.get_user_events", return_value=[]),
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


class TestDocRedirectView(ZulipTestCase):
    def test_doc_permalink_view(self) -> None:
        result = self.client_get("/doc-permalinks/usage-statistics")
        self.assertEqual(result.status_code, 302)
        self.assertEqual(
            result["Location"],
            "https://zulip.readthedocs.io/en/stable/production/mobile-push-notifications.html#uploading-usage-statistics",
        )

        result = self.client_get("/doc-permalinks/basic-metadata")
        self.assertEqual(result.status_code, 302)
        self.assertEqual(
            result["Location"],
            "https://zulip.readthedocs.io/en/stable/production/mobile-push-notifications.html#uploading-basic-metadata",
        )

        result = self.client_get("/doc-permalinks/why-service")
        self.assertEqual(result.status_code, 302)
        self.assertEqual(
            result["Location"],
            "https://zulip.readthedocs.io/en/stable/production/mobile-push-notifications.html#why-a-push-notification-service-is-necessary",
        )

        result = self.client_get("/doc-permalinks/registration-transfer")
        self.assertEqual(result.status_code, 302)
        self.assertEqual(
            result["Location"],
            "https://zulip.readthedocs.io/en/latest/production/mobile-push-notifications.html#moving-your-registration-to-a-new-server",
        )

        result = self.client_get("/doc-permalinks/invalid-doc-id")
        self.assertEqual(result.status_code, 404)
