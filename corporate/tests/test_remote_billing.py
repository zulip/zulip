from datetime import timedelta
from typing import TYPE_CHECKING
from unittest import mock

import responses
import time_machine
from django.conf import settings
from django.utils.timezone import now as timezone_now
from typing_extensions import override

from corporate.lib.remote_billing_util import (
    REMOTE_BILLING_SESSION_VALIDITY_SECONDS,
    LegacyServerIdentityDict,
    RemoteBillingIdentityDict,
    RemoteBillingUserDict,
)
from corporate.lib.stripe import RemoteRealmBillingSession, RemoteServerBillingSession, add_months
from corporate.models.customers import get_customer_by_remote_realm, get_customer_by_remote_server
from corporate.models.licenses import LicenseLedger
from corporate.models.plans import CustomerPlan, get_current_plan_by_customer
from corporate.views.remote_billing_page import generate_confirmation_link_for_server_deactivation
from zerver.lib.exceptions import RemoteRealmServerMismatchError
from zerver.lib.rate_limiter import RateLimitedIPAddr
from zerver.lib.remote_server import send_server_data_to_push_bouncer
from zerver.lib.send_email import FromAddress
from zerver.lib.test_classes import BouncerTestCase
from zerver.lib.test_helpers import activate_push_notification_service, ratelimit_rule
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.models import Realm, UserProfile
from zerver.models.realms import get_realm
from zilencer.models import (
    PreregistrationRemoteRealmBillingUser,
    PreregistrationRemoteServerBillingUser,
    RateLimitedRemoteZulipServer,
    RemoteRealm,
    RemoteRealmBillingUser,
    RemoteServerBillingUser,
    RemoteZulipServer,
)

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as TestHttpResponse


class RemoteRealmBillingTestCase(BouncerTestCase):
    def execute_remote_billing_authentication_flow(
        self,
        user: UserProfile,
        next_page: str | None = None,
        expect_tos: bool = True,
        confirm_tos: bool = True,
        first_time_login: bool = True,
        # This only matters if first_time_login is True, since otherwise
        # there's no confirmation link to be clicked:
        return_without_clicking_confirmation_link: bool = False,
        # This is in order to return the response early, right after accessing the
        # authentication url for the user. This is useful for tests who expect an
        # an error there.
        return_from_auth_url: bool = False,
    ) -> "TestHttpResponse":
        now = timezone_now()

        self_hosted_billing_url = "/self-hosted-billing/"
        if next_page is not None:
            self_hosted_billing_url += f"?next_page={next_page}"
        with time_machine.travel(now, tick=False):
            result = self.client_get(self_hosted_billing_url)

        self.assertEqual(result.status_code, 302)
        self.assertIn("http://selfhosting.testserver/remote-billing-login/", result["Location"])

        signed_auth_url = result["Location"]
        signed_access_token = signed_auth_url.split("/")[-1]
        with time_machine.travel(now, tick=False):
            result = self.client_get(signed_auth_url, subdomain="selfhosting")

        if return_from_auth_url:
            return result

        if first_time_login:
            self.assertFalse(RemoteRealmBillingUser.objects.filter(user_uuid=user.uuid).exists())
            # When logging in for the first time some extra steps are needed
            # to confirm and verify the email address.
            self.assertEqual(result.status_code, 200)
            self.assert_in_success_response(["Enter email"], result)
            self.assert_in_success_response([user.realm.host], result)
            self.assert_in_success_response(
                [f'action="/remote-billing-login/{signed_access_token}/confirm/"'], result
            )

            with time_machine.travel(now, tick=False):
                result = self.client_post(
                    f"/remote-billing-login/{signed_access_token}/confirm/",
                    {"email": user.delivery_email},
                    subdomain="selfhosting",
                )
            if result.status_code == 429:
                # Return rate limit errors early, since they occur in rate limiting tests
                # that want to verify them.
                return result

            self.assertEqual(result.status_code, 200)
            self.assert_in_success_response(
                [
                    "To finish logging in, check your email account (",
                    ") for a confirmation email from Zulip.",
                    user.delivery_email,
                ],
                result,
            )
            confirmation_url = self.get_confirmation_url_from_outbox(
                user.delivery_email,
                url_pattern=(
                    f"{settings.SELF_HOSTING_MANAGEMENT_SUBDOMAIN}.{settings.EXTERNAL_HOST}"
                    r"(\S+)"
                ),
                email_body_contains="confirm your email and log in to Zulip plan management",
            )
            if return_without_clicking_confirmation_link:
                return result

            with time_machine.travel(now, tick=False):
                result = self.client_get(confirmation_url, subdomain="selfhosting")

            remote_billing_user = RemoteRealmBillingUser.objects.latest("id")
            self.assertEqual(remote_billing_user.user_uuid, user.uuid)
            self.assertEqual(remote_billing_user.email, user.delivery_email)

            prereg_user = PreregistrationRemoteRealmBillingUser.objects.latest("id")
            self.assertEqual(prereg_user.created_user, remote_billing_user)
            self.assertEqual(remote_billing_user.date_joined, now)

            # Now we should be redirected again to the /remote-billing-login/ endpoint
            # with a new signed_access_token. Now that the email has been confirmed,
            # and we have a RemoteRealmBillingUser entry, we'll be in the same position
            # as the case where first_time_login=False.
            self.assertEqual(result.status_code, 302)
            self.assertTrue(result["Location"].startswith("/remote-billing-login/"))
            result = self.client_get(result["Location"], subdomain="selfhosting")

        # Final confirmation page - just confirm your details, possibly
        # agreeing to ToS if needed and an authenticated session will be granted:
        self.assertEqual(result.status_code, 200)
        self.assert_in_success_response(["Log in to Zulip plan management"], result)
        self.assert_in_success_response([user.realm.host], result)

        params = {}
        if expect_tos:
            self.assert_in_success_response(["I agree", "Terms of Service"], result)
        if confirm_tos:
            params = {"tos_consent": "true"}

        with time_machine.travel(now, tick=False):
            result = self.client_post(signed_auth_url, params, subdomain="selfhosting")
        if result.status_code >= 400:
            # Failures should be returned early so the caller can assert about them.
            return result

        # Verify the authed data that should have been stored in the session.
        remote_billing_user = RemoteRealmBillingUser.objects.get(user_uuid=user.uuid)
        identity_dict = RemoteBillingIdentityDict(
            user=RemoteBillingUserDict(
                user_email=user.delivery_email,
                user_uuid=str(user.uuid),
                user_full_name=user.full_name,
            ),
            remote_server_uuid=str(self.server.uuid),
            remote_realm_uuid=str(user.realm.uuid),
            remote_billing_user_id=remote_billing_user.id,
            authenticated_at=datetime_to_timestamp(now),
            uri_scheme="http://",
            next_page=next_page,
        )
        self.assertEqual(
            self.client.session["remote_billing_identities"][f"remote_realm:{user.realm.uuid!s}"],
            identity_dict,
        )

        self.assertEqual(remote_billing_user.last_login, now)

        # It's up to the caller to verify further details, such as the exact redirect URL,
        # depending on the set up and intent of the test.
        return result


@activate_push_notification_service()
class SelfHostedBillingEndpointBasicTest(RemoteRealmBillingTestCase):
    @responses.activate
    def test_self_hosted_billing_endpoints(self) -> None:
        # An ordinary user doesn't have access to these endpoints.
        self.login("hamlet")
        for url in [
            "/self-hosted-billing/",
            "/json/self-hosted-billing",
            "/self-hosted-billing/not-configured/",
        ]:
            result = self.client_get(url)
            self.assert_json_error(result, "Must be an organization owner")

        # Login as an organization owner to gain access.
        self.login("desdemona")

        self.add_mock_response()

        self_hosted_billing_url = "/self-hosted-billing/"
        self_hosted_billing_json_url = "/json/self-hosted-billing"

        with self.settings(ZULIP_SERVICE_PUSH_NOTIFICATIONS=False):
            with self.settings(CORPORATE_ENABLED=True):
                result = self.client_get(self_hosted_billing_url)
                self.assertEqual(result.status_code, 404)
                self.assert_in_response("Page not found (404)", result)

            with self.settings(CORPORATE_ENABLED=False):
                result = self.client_get(self_hosted_billing_url)
                self.assertEqual(result.status_code, 302)
                redirect_url = result["Location"]
                self.assertEqual(redirect_url, "/self-hosted-billing/not-configured/")

                with self.assertLogs("django.request"):
                    result = self.client_get(redirect_url)
                    self.assert_in_response(
                        "This server is not configured to use push notifications.", result
                    )

            with self.settings(CORPORATE_ENABLED=True):
                result = self.client_get(self_hosted_billing_json_url)
                self.assert_json_error(
                    result, "Server doesn't use the push notification service", 404
                )

            with self.settings(CORPORATE_ENABLED=False):
                result = self.client_get(self_hosted_billing_json_url)
                self.assert_json_success(result)

                redirect_url = result.json()["billing_access_url"]
                self.assertEqual(redirect_url, "/self-hosted-billing/not-configured/")

                with self.assertLogs("django.request"):
                    result = self.client_get(redirect_url)
                    self.assert_in_response(
                        "This server is not configured to use push notifications.", result
                    )

        with mock.patch(
            "zerver.views.push_notifications.send_to_push_bouncer",
            side_effect=RemoteRealmServerMismatchError,
        ):
            result = self.client_get(self_hosted_billing_url)
            self.assertEqual(result.status_code, 403)
            self.assert_in_response("Unexpected Zulip server registration", result)

            result = self.client_get(self_hosted_billing_json_url)
            self.assert_json_error(
                result,
                "Your organization is registered to a different Zulip server. Please contact Zulip support for assistance in resolving this issue.",
                403,
            )

        # Now test successes. We only check that an url for accessing the remote billing system
        # is returned (in the appropriate format - redirect or json data, depending on the endpoint).
        # We don't need to test that returned URL beyond that, because that's just the full auth flow,
        # which gets tested properly in other tests.
        result = self.client_get(self_hosted_billing_url)
        self.assertEqual(result.status_code, 302)
        self.assertIn("http://selfhosting.testserver/remote-billing-login/", result["Location"])

        result = self.client_get(self_hosted_billing_json_url)
        self.assert_json_success(result)
        data = result.json()
        self.assertEqual(sorted(data.keys()), ["billing_access_url", "msg", "result"])
        self.assertIn(
            "http://selfhosting.testserver/remote-billing-login/", data["billing_access_url"]
        )


@activate_push_notification_service()
class RemoteBillingAuthenticationTest(RemoteRealmBillingTestCase):
    def test_self_hosted_config_error_page(self) -> None:
        self.login("desdemona")

        with (
            self.settings(CORPORATE_ENABLED=False, ZULIP_SERVICE_PUSH_NOTIFICATIONS=False),
            self.assertLogs("django.request"),
        ):
            result = self.client_get("/self-hosted-billing/not-configured/")
            self.assertEqual(result.status_code, 500)
            self.assert_in_response(
                "This server is not configured to use push notifications.", result
            )

        # The page doesn't make sense if PUSH_NOTIFICATION_BOUNCER_URL is configured.
        with self.settings(CORPORATE_ENABLED=False):
            result = self.client_get("/self-hosted-billing/not-configured/")
            self.assertEqual(result.status_code, 404)

        # Also doesn't make sense on zulipchat.com (where CORPORATE_ENABLED is True).
        with self.settings(CORPORATE_ENABLED=True, ZULIP_SERVICE_PUSH_NOTIFICATIONS=False):
            result = self.client_get("/self-hosted-billing/not-configured/")
            self.assertEqual(result.status_code, 404)

    @responses.activate
    def test_remote_billing_authentication_flow(self) -> None:
        self.login("desdemona")
        desdemona = self.example_user("desdemona")
        realm = desdemona.realm

        self.add_mock_response()
        send_server_data_to_push_bouncer(consider_usage_statistics=False)

        result = self.execute_remote_billing_authentication_flow(desdemona)

        # TODO: The redirect URL will vary depending on the billing state of the user's
        # realm/server when we implement proper logic for that. For now, we can simply
        # hard-code an assert about the endpoint.
        self.assertEqual(result["Location"], f"/realm/{realm.uuid!s}/plans/")

        # Go to the URL we're redirected to after authentication and assert
        # some basic expected content.
        result = self.client_get(result["Location"], subdomain="selfhosting")
        self.assert_in_success_response(["showing-self-hosted", "Retain full control"], result)

    @ratelimit_rule(10, 3, domain="sends_email_by_remote_server")
    @ratelimit_rule(10, 2, domain="sends_email_by_ip")
    @responses.activate
    def test_remote_billing_authentication_flow_rate_limited(self) -> None:
        RateLimitedIPAddr("127.0.0.1", domain="sends_email_by_ip").clear_history()
        RateLimitedRemoteZulipServer(
            self.server, domain="sends_email_by_remote_server"
        ).clear_history()

        self.login("desdemona")
        desdemona = self.example_user("desdemona")

        self.add_mock_response()
        send_server_data_to_push_bouncer(consider_usage_statistics=False)

        for i in range(2):
            result = self.execute_remote_billing_authentication_flow(
                desdemona, return_without_clicking_confirmation_link=True
            )
            self.assertEqual(result.status_code, 200)

        result = self.execute_remote_billing_authentication_flow(
            desdemona, return_without_clicking_confirmation_link=True
        )
        self.assertEqual(result.status_code, 429)
        self.assert_in_response("You have exceeded the limit", result)

        # Reset the IP rate limit so that we trigger the server-based one.
        RateLimitedIPAddr("127.0.0.1", domain="sends_email_by_ip").clear_history()

        result = self.execute_remote_billing_authentication_flow(
            desdemona, return_without_clicking_confirmation_link=True
        )
        self.assertEqual(result.status_code, 200)

        with self.assertLogs("zilencer.auth", "WARN") as mock_log:
            result = self.execute_remote_billing_authentication_flow(
                desdemona, return_without_clicking_confirmation_link=True
            )
            self.assertEqual(result.status_code, 429)
            self.assert_in_response("Your server has exceeded the limit", result)
        self.assertEqual(
            mock_log.output,
            [
                f"WARNING:zilencer.auth:Remote server {self.server.hostname} {str(self.server.uuid)[:12]} exceeded "
                "rate limits on domain sends_email_by_remote_server"
            ],
        )

    @responses.activate
    def test_remote_billing_authentication_flow_realm_not_registered(self) -> None:
        RemoteRealm.objects.all().delete()

        self.login("desdemona")
        desdemona = self.example_user("desdemona")
        realm = desdemona.realm

        self.add_mock_response()

        # We do the flow without having the realm registered with the push bouncer.
        # In such a case, the local /self-hosted-billing/ endpoint should error-handle
        # properly and end up registering the server's realms with the bouncer,
        # and successfully completing the flow - transparently to the user.
        self.assertFalse(RemoteRealm.objects.filter(uuid=realm.uuid).exists())

        # send_server_data_to_push_bouncer will be called within the endpoint's
        # error handling to register realms with the bouncer. We mock.patch it
        # to be able to assert that it was called - but also use side_effect
        # to maintain the original behavior of the function, instead of
        # replacing it with a Mock.
        with mock.patch(
            "zerver.views.push_notifications.send_server_data_to_push_bouncer",
            side_effect=send_server_data_to_push_bouncer,
        ) as m:
            result = self.execute_remote_billing_authentication_flow(desdemona)

        m.assert_called_once()
        # The user's realm should now be registered:
        self.assertTrue(RemoteRealm.objects.filter(uuid=realm.uuid).exists())

        self.assertEqual(result["Location"], f"/realm/{realm.uuid!s}/plans/")

        result = self.client_get(result["Location"], subdomain="selfhosting")
        self.assert_in_success_response(["showing-self-hosted", "Retain full control"], result)

    @responses.activate
    def test_remote_billing_authentication_flow_tos_consent_failure(self) -> None:
        self.login("desdemona")
        desdemona = self.example_user("desdemona")

        self.add_mock_response()
        send_server_data_to_push_bouncer(consider_usage_statistics=False)

        result = self.execute_remote_billing_authentication_flow(
            desdemona,
            expect_tos=True,
            confirm_tos=False,
        )

        self.assert_json_error(result, "You must accept the Terms of Service to proceed.")

    @responses.activate
    def test_remote_billing_authentication_flow_tos_consent_update(self) -> None:
        self.login("desdemona")
        desdemona = self.example_user("desdemona")

        self.add_mock_response()
        send_server_data_to_push_bouncer(consider_usage_statistics=False)

        with self.settings(TERMS_OF_SERVICE_VERSION="1.0"):
            result = self.execute_remote_billing_authentication_flow(
                desdemona,
                expect_tos=True,
                confirm_tos=True,
            )

        self.assertEqual(result.status_code, 302)

        remote_billing_user = RemoteRealmBillingUser.objects.last()
        assert remote_billing_user is not None
        self.assertEqual(remote_billing_user.user_uuid, desdemona.uuid)
        self.assertEqual(remote_billing_user.tos_version, "1.0")

        # Now bump the ToS version. They need to agree again.
        with self.settings(TERMS_OF_SERVICE_VERSION="2.0"):
            result = self.execute_remote_billing_authentication_flow(
                desdemona,
                expect_tos=True,
                confirm_tos=False,
                first_time_login=False,
            )
            self.assert_json_error(result, "You must accept the Terms of Service to proceed.")

            result = self.execute_remote_billing_authentication_flow(
                desdemona,
                expect_tos=True,
                confirm_tos=True,
                first_time_login=False,
            )
        remote_billing_user.refresh_from_db()
        self.assertEqual(remote_billing_user.user_uuid, desdemona.uuid)
        self.assertEqual(remote_billing_user.tos_version, "2.0")

    @responses.activate
    def test_remote_billing_authentication_flow_expired_session(self) -> None:
        now = timezone_now()

        self.login("desdemona")
        desdemona = self.example_user("desdemona")
        realm = desdemona.realm

        self.add_mock_response()
        send_server_data_to_push_bouncer(consider_usage_statistics=False)

        with time_machine.travel(now, tick=False):
            result = self.execute_remote_billing_authentication_flow(desdemona)

        self.assertEqual(result["Location"], f"/realm/{realm.uuid!s}/plans/")

        final_url = result["Location"]

        # Go to the URL we're redirected to after authentication and make sure
        # we're granted access.
        with time_machine.travel(
            now + timedelta(seconds=1),
            tick=False,
        ):
            result = self.client_get(final_url, subdomain="selfhosting")
        self.assert_in_success_response(["showing-self-hosted", "Retain full control"], result)

        # Now go there again, simulating doing this after the session has expired.
        # We should be denied access and redirected to re-auth.
        with time_machine.travel(
            now + timedelta(seconds=REMOTE_BILLING_SESSION_VALIDITY_SECONDS + 1),
            tick=False,
        ):
            result = self.client_get(
                final_url, subdomain="selfhosting", HTTP_ACCEPT="text/html, */*;q=0.8"
            )

            self.assertEqual(result.status_code, 302)
            self.assertEqual(
                result["Location"],
                f"http://{desdemona.realm.host}/self-hosted-billing/?next_page=plans",
            )

            # Opening this re-auth URL in result["Location"] is same as re-doing the auth
            # flow via execute_remote_billing_authentication_flow with next_page="plans".
            # So let's test that and assert that we end up successfully re-authed on the /plans
            # page.
            result = self.execute_remote_billing_authentication_flow(
                desdemona,
                next_page="plans",
                # ToS has already been confirmed earlier.
                expect_tos=False,
                confirm_tos=False,
                first_time_login=False,
            )
            self.assertEqual(result["Location"], f"/realm/{realm.uuid!s}/plans/")
            result = self.client_get(result["Location"], subdomain="selfhosting")
            self.assert_in_success_response(["showing-self-hosted", "Retain full control"], result)

    @responses.activate
    def test_remote_billing_unauthed_access(self) -> None:
        now = timezone_now()
        self.login("desdemona")
        desdemona = self.example_user("desdemona")
        realm = desdemona.realm

        self.add_mock_response()
        send_server_data_to_push_bouncer(consider_usage_statistics=False)

        # Straight-up access without authing at all:
        result = self.client_get(f"/realm/{realm.uuid!s}/plans/", subdomain="selfhosting")
        self.assert_json_error(result, "User not authenticated", 401)

        result = self.execute_remote_billing_authentication_flow(desdemona)
        self.assertEqual(result["Location"], f"/realm/{realm.uuid!s}/plans/")

        final_url = result["Location"]

        # Sanity check - access is granted after authing:
        result = self.client_get(final_url, subdomain="selfhosting")
        self.assertEqual(result.status_code, 200)

        # Now mess with the identity dict in the session in unlikely ways so that it should
        # not grant access.
        # First delete the RemoteRealm entry for this session.
        RemoteRealm.objects.filter(uuid=realm.uuid).delete()

        with self.assertLogs("django.request", "ERROR") as m, self.assertRaises(AssertionError):
            self.client_get(final_url, subdomain="selfhosting")
        self.assertIn(
            "The remote realm is missing despite being in the RemoteBillingIdentityDict",
            m.output[0],
        )

        # Try the case where the identity dict is simultaneously expired.
        with (
            time_machine.travel(
                now + timedelta(seconds=REMOTE_BILLING_SESSION_VALIDITY_SECONDS + 30),
                tick=False,
            ),
            self.assertLogs("django.request", "ERROR") as m,
            self.assertRaises(AssertionError),
        ):
            self.client_get(final_url, subdomain="selfhosting")
        # The django.request log should be a traceback, mentioning the relevant
        # exceptions that occurred.
        self.assertIn(
            "RemoteBillingIdentityExpiredError",
            m.output[0],
        )
        self.assertIn(
            "AssertionError",
            m.output[0],
        )

    @responses.activate
    def test_remote_billing_authentication_flow_to_sponsorship_page(self) -> None:
        self.login("desdemona")
        desdemona = self.example_user("desdemona")
        realm = desdemona.realm

        self.add_mock_response()
        send_server_data_to_push_bouncer(consider_usage_statistics=False)

        result = self.execute_remote_billing_authentication_flow(desdemona, "sponsorship")

        self.assertEqual(result["Location"], f"/realm/{realm.uuid!s}/sponsorship/")

        # Go to the URL we're redirected to after authentication and assert
        # some basic expected content.
        result = self.client_get(result["Location"], subdomain="selfhosting")
        self.assert_in_success_response(
            ["Request Zulip", "sponsorship", "Description of your organization"], result
        )

    @responses.activate
    def test_remote_billing_authentication_flow_to_upgrade_page(self) -> None:
        self.login("desdemona")
        desdemona = self.example_user("desdemona")
        realm = desdemona.realm

        self.add_mock_response()
        send_server_data_to_push_bouncer(consider_usage_statistics=False)

        result = self.execute_remote_billing_authentication_flow(desdemona, "upgrade")

        self.assertEqual(result["Location"], f"/realm/{realm.uuid!s}/upgrade/")

        # Go to the URL we're redirected to after authentication and assert
        # some basic expected content.
        # TODO: Add test for the case when redirected to error page (not yet implemented)
        # due to MissingDataError ('has_stale_audit_log' is True).
        with mock.patch("corporate.lib.stripe.has_stale_audit_log", return_value=False):
            result = self.client_get(result["Location"], subdomain="selfhosting")
            self.assert_in_success_response(
                ["Upgrade", "Purchase Zulip", "Your subscription will renew automatically."], result
            )

    @responses.activate
    def test_remote_billing_authentication_flow_cant_access_billing_without_finishing_confirmation(
        self,
    ) -> None:
        self.login("desdemona")
        desdemona = self.example_user("desdemona")
        realm = desdemona.realm

        self.add_mock_response()

        result = self.execute_remote_billing_authentication_flow(
            desdemona,
            expect_tos=True,
            confirm_tos=False,
            first_time_login=True,
            return_without_clicking_confirmation_link=True,
        )
        result = self.client_get(f"/realm/{realm.uuid!s}/billing/", subdomain="selfhosting")
        # Access is not allowed. The user doesn't have an IdentityDict in the session, so
        # we can't do a nice redirect back to their original server.
        self.assertEqual(result.status_code, 401)

    @responses.activate
    def test_remote_billing_authentication_flow_generate_two_confirmation_links_before_confirming(
        self,
    ) -> None:
        self.login("desdemona")
        desdemona = self.example_user("desdemona")

        self.add_mock_response()

        result = self.execute_remote_billing_authentication_flow(
            desdemona,
            expect_tos=True,
            confirm_tos=False,
            first_time_login=True,
            return_without_clicking_confirmation_link=True,
        )
        self.assertEqual(result.status_code, 200)
        first_confirmation_url = self.get_confirmation_url_from_outbox(
            desdemona.delivery_email,
            url_pattern=(
                f"{settings.SELF_HOSTING_MANAGEMENT_SUBDOMAIN}.{settings.EXTERNAL_HOST}" + r"(\S+)"
            ),
        )
        first_prereg_user = PreregistrationRemoteRealmBillingUser.objects.latest("id")

        result = self.execute_remote_billing_authentication_flow(
            desdemona,
            expect_tos=True,
            confirm_tos=False,
            first_time_login=True,
            return_without_clicking_confirmation_link=True,
        )
        self.assertEqual(result.status_code, 200)
        second_confirmation_url = self.get_confirmation_url_from_outbox(
            desdemona.delivery_email,
            url_pattern=(
                f"{settings.SELF_HOSTING_MANAGEMENT_SUBDOMAIN}.{settings.EXTERNAL_HOST}" + r"(\S+)"
            ),
        )
        second_prereg_user = PreregistrationRemoteRealmBillingUser.objects.latest("id")

        self.assertNotEqual(first_confirmation_url, second_confirmation_url)
        self.assertNotEqual(first_prereg_user.id, second_prereg_user.id)

        now = timezone_now()
        # Click the first confirmation link.
        with time_machine.travel(now, tick=False):
            result = self.client_get(first_confirmation_url, subdomain="selfhosting")
        self.assertEqual(result.status_code, 302)
        self.assertTrue(result["Location"].startswith("/remote-billing-login/"))

        # This created the RemoteRealmBillingUser entry.
        remote_billing_user = RemoteRealmBillingUser.objects.latest("id")
        self.assertEqual(remote_billing_user.user_uuid, desdemona.uuid)
        self.assertEqual(remote_billing_user.email, desdemona.delivery_email)

        first_prereg_user.refresh_from_db()
        self.assertEqual(first_prereg_user.created_user, remote_billing_user)

        # Now click the second confirmation link. The RemoteRealmBillingUser entry
        # stays the same, since it's already been created, and the user is redirected
        # normally further through the flow, while we log this event.
        with (
            time_machine.travel(now + timedelta(seconds=1), tick=False),
            self.assertLogs("corporate.stripe", "INFO") as mock_logger,
        ):
            result = self.client_get(second_confirmation_url, subdomain="selfhosting")
        self.assertEqual(result.status_code, 302)
        self.assertTrue(result["Location"].startswith("/remote-billing-login/"))

        # The RemoteRealmBillingUser entry stays the same.
        self.assertEqual(RemoteRealmBillingUser.objects.latest("id"), remote_billing_user)
        # The second prereg user is unused, since it wasn't needed.
        self.assertEqual(second_prereg_user.created_user, None)

        self.assertEqual(
            mock_logger.output,
            [
                "INFO:corporate.stripe:Matching RemoteRealmBillingUser already exists for "
                f"PreregistrationRemoteRealmBillingUser {second_prereg_user.id}"
            ],
        )

    @responses.activate
    def test_transfer_complimentary_access_plan_scheduled_for_upgrade_from_server_to_realm(
        self,
    ) -> None:
        self.login("desdemona")
        desdemona = self.example_user("desdemona")

        # Assert current server is not on any plan.
        self.assertIsNone(get_customer_by_remote_server(self.server))

        start_date = timezone_now()
        end_date = add_months(timezone_now(), 10)

        # Migrate server to complimentary access plan.
        server_billing_session = RemoteServerBillingSession(self.server)
        server_billing_session.create_complimentary_access_plan(start_date, end_date)

        server_customer = server_billing_session.get_customer()
        assert server_customer is not None
        server_plan = get_current_plan_by_customer(server_customer)
        assert server_plan is not None
        self.assertEqual(self.server.plan_type, RemoteZulipServer.PLAN_TYPE_SELF_MANAGED_LEGACY)
        self.assertEqual(server_plan.tier, CustomerPlan.TIER_SELF_HOSTED_LEGACY)
        self.assertEqual(server_plan.status, CustomerPlan.ACTIVE)

        # Schedule upgrade for plan.
        server_plan.status = CustomerPlan.SWITCH_PLAN_TIER_AT_PLAN_END
        server_plan.save(update_fields=["status"])

        # Just create a temporary plan and check if gets transferred or not.
        server_next_plan = CustomerPlan.objects.create(
            customer=server_customer,
            billing_cycle_anchor=end_date,
            billing_schedule=CustomerPlan.BILLING_SCHEDULE_ANNUAL,
            tier=CustomerPlan.TIER_SELF_HOSTED_BUSINESS,
            status=CustomerPlan.NEVER_STARTED,
        )

        # There are four test realms on this server:
        # <Realm: zulipinternal 1>, <Realm: zephyr 3>, <Realm: lear 4>, <Realm: zulip 2>
        self.assert_length(Realm.objects.all(), 4)

        # Delete any existing remote realms.
        RemoteRealm.objects.all().delete()

        # Send server data to push bouncer.
        self.add_mock_response()
        send_server_data_to_push_bouncer(consider_usage_statistics=False)

        # Login to plan management.
        result = self.execute_remote_billing_authentication_flow(
            desdemona, return_from_auth_url=True
        )
        self.assertEqual(result.status_code, 200)
        self.assert_in_response("Plan management not available", result)

        # Server plan status stayed the same.
        self.server.refresh_from_db()
        self.assertEqual(self.server.plan_type, RemoteZulipServer.PLAN_TYPE_SELF_MANAGED_LEGACY)

        # RemoteRealm objects should be created for all realms on the server but no customer plans.
        self.assert_length(RemoteRealm.objects.all(), 4)
        for remote_realm in RemoteRealm.objects.all():
            self.assertIsNone(get_customer_by_remote_realm(remote_realm))

        # Same customer plan exists for server since there are multiple realms to manage here.
        server_plan.refresh_from_db()
        self.assertEqual(get_current_plan_by_customer(server_customer), server_plan)
        self.assertEqual(server_plan.customer, server_customer)

        # Deactivate realms other than bot realm and zulip realm then try the migration again.
        Realm.objects.exclude(string_id__in=["zulip", "zulipinternal"]).update(deactivated=True)

        # Send server data to push bouncer.
        send_server_data_to_push_bouncer(consider_usage_statistics=False)

        # Login to plan management. Performs customer migration from server to realms.
        result = self.execute_remote_billing_authentication_flow(
            desdemona, return_from_auth_url=False
        )
        self.assertEqual(result.status_code, 302)

        # Server plan status was reset
        self.server.refresh_from_db()
        self.assertEqual(self.server.plan_type, RemoteZulipServer.PLAN_TYPE_SELF_MANAGED)
        # Check if zephyr and lear were deactivated
        self.assertCountEqual(
            RemoteRealm.objects.filter(realm_deactivated=True).values_list("host", flat=True),
            ["zephyr.testserver", "lear.testserver"],
        )

        # Check complimentary access CustomerPlan exists for the one non-deactivated
        # "real" realm and does not for the bot realm.

        # Sanity check that the setup for this test is the way we think it is.
        self.assertEqual(RemoteRealm.objects.filter(realm_deactivated=False).count(), 2)
        # These queries have a unique result, so we can use .get().
        remote_realm_with_plan = RemoteRealm.objects.get(
            realm_deactivated=False, is_system_bot_realm=False
        )
        system_bot_remote_realm = RemoteRealm.objects.get(
            realm_deactivated=False, is_system_bot_realm=True
        )

        self.assertIsNone(get_customer_by_remote_realm(system_bot_remote_realm))

        self.assertEqual(remote_realm_with_plan.host, "zulip.testserver")
        customer = get_customer_by_remote_realm(remote_realm_with_plan)
        assert customer is not None
        # Customer got transferred from server to realm.
        self.assertEqual(customer, server_customer)
        plan = get_current_plan_by_customer(customer)
        assert plan is not None
        self.assertEqual(
            remote_realm_with_plan.plan_type, RemoteRealm.PLAN_TYPE_SELF_MANAGED_LEGACY
        )
        self.assertEqual(plan.tier, CustomerPlan.TIER_SELF_HOSTED_LEGACY)
        self.assertEqual(plan.status, CustomerPlan.SWITCH_PLAN_TIER_AT_PLAN_END)
        self.assertEqual(plan.billing_cycle_anchor, start_date)
        self.assertEqual(plan.end_date, end_date)
        self.assertEqual(
            RemoteRealmBillingSession(remote_realm_with_plan).get_next_plan(plan), server_next_plan
        )

    @responses.activate
    def test_transfer_plan_from_server_to_realm_when_realm_has_customer(
        self,
    ) -> None:
        self.login("desdemona")
        desdemona = self.example_user("desdemona")
        zulip_realm = get_realm("zulip")

        server_billing_session = RemoteServerBillingSession(self.server)
        server_customer = server_billing_session.update_or_create_customer(
            stripe_customer_id="cus_123server"
        )
        server_plan = CustomerPlan.objects.create(
            customer=server_customer,
            billing_cycle_anchor=timezone_now(),
            billing_schedule=CustomerPlan.BILLING_SCHEDULE_ANNUAL,
            tier=CustomerPlan.TIER_SELF_HOSTED_COMMUNITY,
            status=CustomerPlan.ACTIVE,
        )
        self.server.plan_type = RemoteZulipServer.PLAN_TYPE_COMMUNITY
        self.server.save(update_fields=["plan_type"])

        # Delete any existing remote realms.
        RemoteRealm.objects.all().delete()

        # We want there to be only a single (non-system bot) realm on the server for our setup.
        Realm.objects.exclude(string_id__in=["zulip", "zulipinternal"]).update(deactivated=True)

        # Send server data to push bouncer.
        self.add_mock_response()
        send_server_data_to_push_bouncer(consider_usage_statistics=False)

        # Let's create a plan for the realm. This will conflict with the server plan.
        remote_realm = RemoteRealm.objects.get(uuid=zulip_realm.uuid)
        realm_billing_session = RemoteRealmBillingSession(remote_realm)
        realm_customer = realm_billing_session.update_or_create_customer(
            stripe_customer_id="cus_123realm"
        )
        realm_plan = CustomerPlan.objects.create(
            customer=realm_customer,
            billing_cycle_anchor=timezone_now(),
            billing_schedule=CustomerPlan.BILLING_SCHEDULE_ANNUAL,
            tier=CustomerPlan.TIER_SELF_HOSTED_LEGACY,
            status=CustomerPlan.ACTIVE,
        )
        remote_realm.plan_type = RemoteRealm.PLAN_TYPE_SELF_MANAGED_LEGACY
        remote_realm.save(update_fields=["plan_type"])

        with self.assertLogs("zilencer.views", "WARN") as mock_warn:
            result = self.execute_remote_billing_authentication_flow(
                desdemona, return_from_auth_url=True
            )
        self.assertEqual(
            mock_warn.output,
            [
                f"WARNING:zilencer.views:Failed to migrate customer from server (id: {remote_realm.server.id}) to realm (id: {remote_realm.id}): "
                "RemoteRealm customer already exists and plans can't be migrated automatically."
            ],
        )
        self.assert_json_error(
            result,
            f"Couldn't reconcile billing data between server and realm. Please contact {FromAddress.SUPPORT}",
        )

        # If the realm's plan is ENDED, it's safe to move the server plan over.
        realm_plan.status = CustomerPlan.ENDED
        realm_plan.save(update_fields=["status"])
        # However, not if the server's status indicates that there's some kind
        # of plan change queued up after the plan, since that state would be
        # harder and more risky to try to migrate.
        server_plan.status = CustomerPlan.SWITCH_PLAN_TIER_AT_PLAN_END
        server_plan.save(update_fields=["status"])

        with self.assertLogs("zilencer.views", "WARN") as mock_warn:
            result = self.execute_remote_billing_authentication_flow(
                desdemona, return_from_auth_url=True
            )
        self.assertEqual(
            mock_warn.output,
            [
                f"WARNING:zilencer.views:Failed to migrate customer from server (id: {remote_realm.server.id}) to realm (id: {remote_realm.id}): "
                "RemoteRealm customer already exists and plans can't be migrated automatically."
            ],
        )
        self.assert_json_error(
            result,
            f"Couldn't reconcile billing data between server and realm. Please contact {FromAddress.SUPPORT}",
        )

        # Now we simulate a regular, ACTIVE plan for the server again. Such a plan can be
        # migrated, but we run into the last issue: the realm's customer already has a
        # stripe_customer_id. We wouldn't want to overwrite it, so we error out.
        server_plan.status = CustomerPlan.ACTIVE
        server_plan.save(update_fields=["status"])
        # Sanity check the assumption that stripe_customer_id is as expected for realm_customer.
        realm_customer.refresh_from_db()
        self.assertEqual(realm_customer.stripe_customer_id, "cus_123realm")

        with self.assertLogs("zilencer.views", "WARN") as mock_warn:
            result = self.execute_remote_billing_authentication_flow(
                desdemona, return_from_auth_url=True
            )
        self.assertEqual(
            mock_warn.output,
            [
                f"WARNING:zilencer.views:Failed to migrate customer from server (id: {remote_realm.server.id}) to realm (id: {remote_realm.id}): "
                "RemoteRealm customer already exists and plans can't be migrated automatically."
            ],
        )
        self.assert_json_error(
            result,
            f"Couldn't reconcile billing data between server and realm. Please contact {FromAddress.SUPPORT}",
        )

        # Finally, set the stripe_customer_id to None for the realm's customer.
        # Having an ACTIVE plan for the server and an ENDED plan for the realm, we now have
        # a simple case, where the migration should proceed.
        realm_customer.stripe_customer_id = None
        realm_customer.save(update_fields=["stripe_customer_id"])
        result = self.execute_remote_billing_authentication_flow(
            desdemona, return_from_auth_url=False
        )
        self.assertEqual(result.status_code, 302)

        # Server plan status was reset
        self.server.refresh_from_db()
        self.assertEqual(self.server.plan_type, RemoteZulipServer.PLAN_TYPE_SELF_MANAGED)

        # The Customer objects remain as they were.
        self.assertEqual(get_customer_by_remote_realm(remote_realm), realm_customer)
        self.assertEqual(get_customer_by_remote_server(self.server), server_customer)

        # The plan that used to be for the server, has been migrated to the realm customer:
        self.assertEqual(get_current_plan_by_customer(server_customer), None)
        self.assertEqual(get_current_plan_by_customer(realm_customer), server_plan)

        remote_realm.refresh_from_db()
        self.assertEqual(remote_realm.plan_type, RemoteRealm.PLAN_TYPE_COMMUNITY)

        realm_customer.refresh_from_db()
        self.assertEqual(realm_customer.stripe_customer_id, "cus_123server")

        server_customer.refresh_from_db()
        self.assertEqual(server_customer.stripe_customer_id, None)

    @responses.activate
    def test_transfer_business_plan_from_server_to_realm(
        self,
    ) -> None:
        self.login("desdemona")
        desdemona = self.example_user("desdemona")

        # Assert current server is not on any plan.
        self.assertIsNone(get_customer_by_remote_server(self.server))
        self.assertEqual(self.server.plan_type, RemoteZulipServer.PLAN_TYPE_SELF_MANAGED)

        # Add server to business plan.
        server_billing_session = RemoteServerBillingSession(self.server)
        server_customer = server_billing_session.update_or_create_customer(stripe_customer_id=None)
        assert server_customer is not None

        # Just create a temporary plan and check if gets transferred or not.
        server_plan = CustomerPlan.objects.create(
            customer=server_customer,
            billing_cycle_anchor=timezone_now(),
            billing_schedule=CustomerPlan.BILLING_SCHEDULE_ANNUAL,
            tier=CustomerPlan.TIER_SELF_HOSTED_BUSINESS,
            status=CustomerPlan.ACTIVE,
            automanage_licenses=True,
        )
        initial_license_count = 100
        LicenseLedger.objects.create(
            plan=server_plan,
            is_renewal=True,
            event_time=timezone_now(),
            licenses=initial_license_count,
            licenses_at_next_renewal=initial_license_count,
        )
        self.server.plan_type = RemoteZulipServer.PLAN_TYPE_BUSINESS
        self.server.save(update_fields=["plan_type"])

        # There are four test realms on this server:
        # <Realm: zulipinternal 1>, <Realm: zephyr 3>, <Realm: lear 4>, <Realm: zulip 2>
        self.assert_length(Realm.objects.all(), 4)

        # Delete any existing remote realms.
        RemoteRealm.objects.all().delete()

        # Send server data to push bouncer.
        self.add_mock_response()
        send_server_data_to_push_bouncer(consider_usage_statistics=False)

        # Login to plan management.
        result = self.execute_remote_billing_authentication_flow(
            desdemona, return_from_auth_url=True
        )
        self.assertEqual(result.status_code, 200)
        self.assert_in_response("Plan management not available", result)

        # Server plan status stayed the same.
        self.server.refresh_from_db()
        self.assertEqual(self.server.plan_type, RemoteZulipServer.PLAN_TYPE_BUSINESS)

        # RemoteRealm objects should be created for all realms on the server but no customer plans.
        self.assert_length(RemoteRealm.objects.all(), 4)
        for remote_realm in RemoteRealm.objects.all():
            self.assertIsNone(get_customer_by_remote_realm(remote_realm))

        # Same customer plan exists for server since there are multiple realms to manage here.
        server_plan.refresh_from_db()
        self.assertEqual(get_current_plan_by_customer(server_customer), server_plan)
        self.assertEqual(server_plan.customer, server_customer)

        # Deactivate realms other than bot realm and zulip realm then try the migration again.
        Realm.objects.exclude(string_id__in=["zulip", "zulipinternal"]).update(deactivated=True)

        # Send server data to push bouncer.
        send_server_data_to_push_bouncer(consider_usage_statistics=False)

        # Login to plan management. Performs customer migration from server to realms.
        result = self.execute_remote_billing_authentication_flow(
            desdemona, return_from_auth_url=False
        )
        self.assertEqual(result.status_code, 302)

        # Server plan status was reset
        self.server.refresh_from_db()
        self.assertEqual(self.server.plan_type, RemoteZulipServer.PLAN_TYPE_SELF_MANAGED)

        # Check business CustomerPlan exists for all realms except bot realm.

        # Sanity check that the setup for this test is the way we think it is.
        self.assertEqual(RemoteRealm.objects.filter(realm_deactivated=False).count(), 2)
        # These queries have a unique result, so we can use .get().
        remote_realm_with_plan = RemoteRealm.objects.get(
            realm_deactivated=False, is_system_bot_realm=False
        )
        system_bot_remote_realm = RemoteRealm.objects.get(
            realm_deactivated=False, is_system_bot_realm=True
        )

        self.assertIsNone(get_customer_by_remote_realm(system_bot_remote_realm))

        self.assertEqual(remote_realm_with_plan.host, "zulip.testserver")
        customer = get_customer_by_remote_realm(remote_realm_with_plan)
        assert customer is not None
        # Customer got transferred from server to realm.
        self.assertEqual(customer, server_customer)
        plan = get_current_plan_by_customer(customer)
        assert plan is not None
        self.assertEqual(remote_realm_with_plan.plan_type, RemoteRealm.PLAN_TYPE_BUSINESS)
        self.assertEqual(plan.tier, CustomerPlan.TIER_SELF_HOSTED_BUSINESS)
        self.assertEqual(plan.status, CustomerPlan.ACTIVE)

        # Check that an updated license ledger entry was created.
        billing_session = RemoteRealmBillingSession(remote_realm=remote_realm_with_plan)
        license_ledger = billing_session.get_last_ledger_for_automanaged_plan_if_exists()
        billable_licenses = billing_session.get_billable_licenses_for_customer(customer, plan.tier)
        assert license_ledger is not None
        self.assertNotEqual(initial_license_count, billable_licenses)
        self.assertEqual(license_ledger.licenses, initial_license_count)
        self.assertEqual(license_ledger.licenses_at_next_renewal, billable_licenses)
        self.assertFalse(license_ledger.is_renewal)

    @responses.activate
    def test_transfer_plan_from_server_to_realm_edge_cases(self) -> None:
        self.login("desdemona")
        desdemona = self.example_user("desdemona")

        # CASE: Server has no customer
        self.assertIsNone(get_customer_by_remote_server(self.server))

        # Send server data to push bouncer.
        self.add_mock_response()
        send_server_data_to_push_bouncer(consider_usage_statistics=False)

        # Login to plan management.
        result = self.execute_remote_billing_authentication_flow(desdemona)
        self.assertEqual(result.status_code, 302)

        # Still no customer.
        self.assertIsNone(get_customer_by_remote_server(self.server))

        # CASE: Server has customer but no plan.
        server_billing_session = RemoteServerBillingSession(self.server)
        server_customer = server_billing_session.update_or_create_customer(stripe_customer_id=None)

        # Send server data to push bouncer.
        send_server_data_to_push_bouncer(consider_usage_statistics=False)

        # Login to plan management.
        result = self.execute_remote_billing_authentication_flow(
            desdemona, first_time_login=False, expect_tos=False
        )
        self.assertEqual(result.status_code, 302)

        # Server still has no plan.
        self.assertIsNone(get_current_plan_by_customer(server_customer))

        # CASE: Server has complimentary access plan but all realms are deactivated.
        start_date = timezone_now()
        end_date = add_months(timezone_now(), 10)
        server_billing_session = RemoteServerBillingSession(self.server)
        server_billing_session.create_complimentary_access_plan(start_date, end_date)
        # All realms are deactivated.
        Realm.objects.all().update(deactivated=True)

        # Send server data to push bouncer.
        send_server_data_to_push_bouncer(consider_usage_statistics=False)

        # Login to plan management.
        result = self.execute_remote_billing_authentication_flow(
            desdemona, return_from_auth_url=True
        )
        self.assertEqual(result.status_code, 200)
        self.assert_in_response("Plan management not available", result)

        # Server stays on the same plan.
        server_plan = get_current_plan_by_customer(server_customer)
        assert server_plan is not None
        self.assertEqual(self.server.plan_type, RemoteZulipServer.PLAN_TYPE_SELF_MANAGED_LEGACY)
        self.assertEqual(server_plan.tier, CustomerPlan.TIER_SELF_HOSTED_LEGACY)
        self.assertEqual(server_plan.status, CustomerPlan.ACTIVE)

        # CASE: Server has business plan but all realms are deactivated.
        server_plan.tier = CustomerPlan.TIER_SELF_HOSTED_BUSINESS
        server_plan.save(update_fields=["tier"])
        self.server.plan_type = RemoteZulipServer.PLAN_TYPE_BUSINESS
        self.server.save(update_fields=["plan_type"])

        # Login to plan management.
        result = self.execute_remote_billing_authentication_flow(
            desdemona, return_from_auth_url=True
        )
        self.assertEqual(result.status_code, 200)
        self.assert_in_response("Plan management not available", result)

        # Server stays on the same plan.
        server_customer.refresh_from_db()
        server_plan.refresh_from_db()
        self.assertEqual(self.server.plan_type, RemoteZulipServer.PLAN_TYPE_BUSINESS)
        self.assertEqual(server_plan.tier, CustomerPlan.TIER_SELF_HOSTED_BUSINESS)

        # CASE: Server has business plan but there are no realms.
        Realm.objects.all().delete()

        # Send server data to push bouncer.
        send_server_data_to_push_bouncer(consider_usage_statistics=False)
        server_customer.refresh_from_db()
        server_plan.refresh_from_db()
        # Server stays on same plan.
        self.assertEqual(self.server.plan_type, RemoteZulipServer.PLAN_TYPE_BUSINESS)
        self.assertEqual(server_plan.tier, CustomerPlan.TIER_SELF_HOSTED_BUSINESS)
        self.assertEqual(server_plan.status, CustomerPlan.ACTIVE)


class RemoteServerTestCase(BouncerTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        self.uuid = self.server.uuid
        self.secret = self.server.api_key

    def execute_remote_billing_authentication_flow(
        self,
        email: str,
        full_name: str,
        next_page: str | None = None,
        expect_tos: bool = True,
        confirm_tos: bool = True,
        return_without_clicking_confirmation_link: bool = False,
    ) -> "TestHttpResponse":
        now = timezone_now()
        with time_machine.travel(now, tick=False):
            payload = {"zulip_org_id": self.uuid, "zulip_org_key": self.secret}
            if next_page is not None:
                payload["next_page"] = next_page
            result = self.client_post(
                "/serverlogin/",
                payload,
                subdomain="selfhosting",
            )

        self.assertEqual(result.status_code, 200)
        self.assert_in_success_response(["Enter log in email"], result)
        if next_page is not None:
            self.assert_in_success_response(
                [f'<input type="hidden" name="next_page" value="{next_page}" />'], result
            )
        self.assert_in_success_response([f'action="/serverlogin/{self.uuid!s}/confirm/"'], result)

        # Verify the partially-authed data that should have been stored in the session. The flow
        # isn't complete yet however, and this won't give the user access to authenticated endpoints,
        # only allow them to proceed with confirmation.
        identity_dict = LegacyServerIdentityDict(
            remote_server_uuid=str(self.server.uuid),
            authenticated_at=datetime_to_timestamp(now),
            remote_billing_user_id=None,
        )
        self.assertEqual(
            self.client.session["remote_billing_identities"][f"remote_server:{self.uuid!s}"],
            identity_dict,
        )

        payload = {"email": email}
        if next_page is not None:
            payload["next_page"] = next_page
        with time_machine.travel(now, tick=False):
            result = self.client_post(
                f"/serverlogin/{self.uuid!s}/confirm/",
                payload,
                subdomain="selfhosting",
            )
        if result.status_code == 429:
            # Return rate limit errors early, since they occur in rate limiting tests
            # that want to verify them.
            return result

        self.assertEqual(result.status_code, 200)
        self.assert_in_success_response(
            ["We have sent", "a log in", "link will expire in", email],
            result,
        )

        confirmation_url = self.get_confirmation_url_from_outbox(
            email,
            url_pattern=(
                f"{settings.SELF_HOSTING_MANAGEMENT_SUBDOMAIN}.{settings.EXTERNAL_HOST}" + r"(\S+)"
            ),
            email_body_contains="This link will expire in 24 hours",
        )
        if return_without_clicking_confirmation_link:
            return result

        with time_machine.travel(now, tick=False):
            result = self.client_get(confirmation_url, subdomain="selfhosting")
        self.assertEqual(result.status_code, 200)
        self.assert_in_success_response(
            [f"Log in to Zulip plan management for {self.server.hostname}", email], result
        )
        self.assert_in_success_response([f'action="{confirmation_url}"'], result)
        if expect_tos:
            self.assert_in_success_response(["I agree", "Terms of Service"], result)

        payload = {"full_name": full_name}
        if confirm_tos:
            payload["tos_consent"] = "true"
        with time_machine.travel(now, tick=False):
            result = self.client_post(confirmation_url, payload, subdomain="selfhosting")
        if result.status_code >= 400:
            # Early return for the caller to assert about the error.
            return result

        # The user should now be fully authenticated.

        # This should have been created in the process:
        remote_billing_user = RemoteServerBillingUser.objects.get(
            remote_server=self.server, email=email
        )

        # Verify the session looks as it should:
        identity_dict = LegacyServerIdentityDict(
            remote_server_uuid=str(self.server.uuid),
            authenticated_at=datetime_to_timestamp(now),
            remote_billing_user_id=remote_billing_user.id,
        )
        self.assertEqual(
            self.client.session["remote_billing_identities"][f"remote_server:{self.uuid!s}"],
            identity_dict,
        )

        self.assertEqual(remote_billing_user.last_login, now)

        return result


class LegacyServerLoginTest(RemoteServerTestCase):
    @ratelimit_rule(10, 3, domain="sends_email_by_remote_server")
    @ratelimit_rule(10, 2, domain="sends_email_by_ip")
    def test_remote_billing_authentication_flow_rate_limited(self) -> None:
        RateLimitedIPAddr("127.0.0.1", domain="sends_email_by_ip").clear_history()
        RateLimitedRemoteZulipServer(
            self.server, domain="sends_email_by_remote_server"
        ).clear_history()

        self.login("desdemona")
        desdemona = self.example_user("desdemona")

        for i in range(2):
            result = self.execute_remote_billing_authentication_flow(
                desdemona.delivery_email,
                desdemona.full_name,
                return_without_clicking_confirmation_link=True,
            )
            self.assertEqual(result.status_code, 200)

        result = self.execute_remote_billing_authentication_flow(
            desdemona.delivery_email,
            desdemona.full_name,
            return_without_clicking_confirmation_link=True,
        )
        self.assertEqual(result.status_code, 429)
        self.assert_in_response("You have exceeded the limit", result)

        # Reset the IP rate limit so that we trigger the server-based one.
        RateLimitedIPAddr("127.0.0.1", domain="sends_email_by_ip").clear_history()

        result = self.execute_remote_billing_authentication_flow(
            desdemona.delivery_email,
            desdemona.full_name,
            return_without_clicking_confirmation_link=True,
        )
        self.assertEqual(result.status_code, 200)

        with self.assertLogs("zilencer.auth", "WARN") as mock_log:
            result = self.execute_remote_billing_authentication_flow(
                desdemona.delivery_email,
                desdemona.full_name,
                return_without_clicking_confirmation_link=True,
            )
            self.assertEqual(result.status_code, 429)
            self.assert_in_response("Your server has exceeded the limit", result)
        self.assertEqual(
            mock_log.output,
            [
                f"WARNING:zilencer.auth:Remote server {self.server.hostname} {str(self.server.uuid)[:12]} exceeded "
                "rate limits on domain sends_email_by_remote_server"
            ],
        )

    def test_server_login_get(self) -> None:
        result = self.client_get("/serverlogin/", subdomain="selfhosting")
        self.assertEqual(result.status_code, 200)
        self.assert_in_success_response(["Authenticate server for Zulip plan management"], result)

    def test_server_login_invalid_zulip_org_id(self) -> None:
        result = self.client_post(
            "/serverlogin/",
            {"zulip_org_id": "invalid", "zulip_org_key": "secret"},
            subdomain="selfhosting",
        )
        self.assertEqual(result.status_code, 200)
        self.assert_in_success_response(
            ["This zulip_org_id is not registered with Zulip&#39;s billing management system."],
            result,
        )

    def test_server_login_invalid_zulip_org_key(self) -> None:
        result = self.client_post(
            "/serverlogin/",
            {"zulip_org_id": self.uuid, "zulip_org_key": "invalid"},
            subdomain="selfhosting",
        )
        self.assertEqual(result.status_code, 200)
        self.assert_in_success_response(["Invalid zulip_org_key for this zulip_org_id."], result)

    def test_server_login_deactivated_server(self) -> None:
        self.server.deactivated = True
        self.server.save(update_fields=["deactivated"])

        result = self.client_post(
            "/serverlogin/",
            {"zulip_org_id": self.uuid, "zulip_org_key": self.secret},
            subdomain="selfhosting",
        )
        self.assertEqual(result.status_code, 200)
        self.assert_in_success_response(["Your server registration has been deactivated."], result)

    def test_server_login_success_with_no_plan(self) -> None:
        hamlet = self.example_user("hamlet")
        now = timezone_now()
        with time_machine.travel(now, tick=False):
            result = self.execute_remote_billing_authentication_flow(
                hamlet.delivery_email, hamlet.full_name, expect_tos=True, confirm_tos=True
            )
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], f"/server/{self.uuid}/plans/")

        result = self.client_get(f"/server/{self.uuid}/billing/", subdomain="selfhosting")
        # The server has no plan, so the /billing page redirects to /upgrade
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], f"/server/{self.uuid}/upgrade/")

        # Access on the upgrade page is granted, assert a basic string proving that.
        # TODO: Add test for the case when redirected to error page (not yet implemented)
        # due to MissingDataError ('has_stale_audit_log' is True).
        with mock.patch("corporate.lib.stripe.has_stale_audit_log", return_value=False):
            result = self.client_get(result["Location"], subdomain="selfhosting")
            self.assert_in_success_response([f"Upgrade {self.server.hostname}"], result)

        # Verify the RemoteServerBillingUser and PreRegistrationRemoteServerBillingUser
        # objects created in the process.
        remote_billing_user = RemoteServerBillingUser.objects.latest("id")
        self.assertEqual(remote_billing_user.email, hamlet.delivery_email)

        prereg_user = PreregistrationRemoteServerBillingUser.objects.latest("id")
        self.assertEqual(prereg_user.created_user, remote_billing_user)
        self.assertEqual(remote_billing_user.date_joined, now)

    def test_server_login_success_consent_is_not_re_asked(self) -> None:
        hamlet = self.example_user("hamlet")
        result = self.execute_remote_billing_authentication_flow(
            hamlet.delivery_email, hamlet.full_name, expect_tos=True, confirm_tos=True
        )
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], f"/server/{self.uuid}/plans/")

        # Now go through the flow again, but this time we should not be asked to re-confirm ToS.
        result = self.execute_remote_billing_authentication_flow(
            hamlet.delivery_email, hamlet.full_name, expect_tos=False, confirm_tos=False
        )
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], f"/server/{self.uuid}/plans/")

    def test_server_login_success_with_next_page(self) -> None:
        hamlet = self.example_user("hamlet")

        # First test an invalid next_page value.
        result = self.client_post(
            "/serverlogin/",
            {"zulip_org_id": self.uuid, "zulip_org_key": self.secret, "next_page": "invalid"},
            subdomain="selfhosting",
        )
        self.assert_json_error(result, "Invalid next_page", 400)

        result = self.execute_remote_billing_authentication_flow(
            hamlet.delivery_email, hamlet.full_name, next_page="sponsorship"
        )

        # We should be redirected to the page dictated by the next_page param.
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], f"/server/{self.uuid}/sponsorship/")

        result = self.client_get(result["Location"], subdomain="selfhosting")
        self.assert_in_success_response(["Request Zulip", "sponsorship", "Community"], result)

    def test_server_login_next_page_in_form_persists(self) -> None:
        result = self.client_get("/serverlogin/?next_page=billing", subdomain="selfhosting")
        self.assert_in_success_response(
            ['<input type="hidden" name="next_page" value="billing" />'], result
        )

        result = self.client_post(
            "/serverlogin/",
            {"zulip_org_id": self.uuid, "zulip_org_key": "invalid", "next_page": "billing"},
            subdomain="selfhosting",
        )
        self.assertEqual(result.status_code, 200)
        self.assert_in_success_response(["Invalid zulip_org_key for this zulip_org_id."], result)
        # The next_page param should be preserved in the form.
        self.assert_in_success_response(
            ['<input type="hidden" name="next_page" value="billing" />'], result
        )

    def test_server_billing_unauthed(self) -> None:
        hamlet = self.example_user("hamlet")
        now = timezone_now()
        # Try to open a page with no auth at all.
        result = self.client_get(
            f"/server/{self.uuid}/billing/",
            subdomain="selfhosting",
            HTTP_ACCEPT="text/html, */*;q=0.8",
        )
        self.assertEqual(result.status_code, 302)
        # Redirects to the login form with appropriate next_page value.
        self.assertEqual(result["Location"], "/serverlogin/?next_page=billing")

        result = self.client_get(result["Location"], subdomain="selfhosting")
        self.assert_in_success_response(
            ['<input type="hidden" name="next_page" value="billing" />'], result
        )

        # The full auth flow involves clicking a confirmation link, upon which the user is
        # granted an authenticated session. However, in the first part of the process,
        # an intermittent session state is created to transition between endpoints.
        # The bottom line is that this session state should *not* grant the user actual
        # access to the billing management endpoints.
        # We verify that here by simulating the user *not* clicking the confirmation link,
        # and then trying to access billing management with the intermittent session state.
        with time_machine.travel(now, tick=False):
            self.execute_remote_billing_authentication_flow(
                hamlet.delivery_email,
                hamlet.full_name,
                next_page="upgrade",
                return_without_clicking_confirmation_link=True,
            )
        result = self.client_get(
            f"/server/{self.uuid}/billing/",
            subdomain="selfhosting",
            HTTP_ACCEPT="text/html, */*;q=0.8",
        )
        self.assertEqual(result.status_code, 302)
        # Redirects to the login form with appropriate next_page value.
        self.assertEqual(result["Location"], "/serverlogin/?next_page=billing")

        # Now authenticate, going to the /upgrade page since we'll be able to access
        # it directly without annoying extra redirects.
        with time_machine.travel(now, tick=False):
            result = self.execute_remote_billing_authentication_flow(
                hamlet.delivery_email, hamlet.full_name, next_page="upgrade"
            )

        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], f"/server/{self.uuid}/upgrade/")

        # Sanity check: access on the upgrade page is granted.
        # TODO: Add test for the case when redirected to error page (Not yet implemented)
        # due to MissingDataError i.e., when 'has_stale_audit_log' is True.
        with mock.patch("corporate.lib.stripe.has_stale_audit_log", return_value=False):
            result = self.client_get(result["Location"], subdomain="selfhosting")
            self.assert_in_success_response([f"Upgrade {self.server.hostname}"], result)

        # Now we can simulate an expired identity dict in the session.
        with time_machine.travel(
            now + timedelta(seconds=REMOTE_BILLING_SESSION_VALIDITY_SECONDS + 30),
            tick=False,
        ):
            result = self.client_get(
                f"/server/{self.uuid}/upgrade/",
                subdomain="selfhosting",
                HTTP_ACCEPT="text/html, */*;q=0.8",
            )
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], "/serverlogin/?next_page=upgrade")

    def test_remote_billing_authentication_flow_tos_consent_failure(self) -> None:
        hamlet = self.example_user("hamlet")

        result = self.execute_remote_billing_authentication_flow(
            hamlet.email, hamlet.full_name, expect_tos=True, confirm_tos=False
        )

        self.assert_json_error(result, "You must accept the Terms of Service to proceed.")


class TestGenerateDeactivationLink(BouncerTestCase):
    def test_generate_deactivation_link(self) -> None:
        server = self.server
        confirmation_url = generate_confirmation_link_for_server_deactivation(
            server, validity_in_minutes=60
        )

        result = self.client_get(confirmation_url, subdomain="selfhosting")
        self.assert_in_success_response(
            ["Log in to deactivate registration for", server.contact_email], result
        )
        payload = {"full_name": "test", "tos_consent": "true"}
        result = self.client_post(confirmation_url, payload, subdomain="selfhosting")
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], f"/server/{server.uuid!s}/deactivate/")

        result = self.client_get(result["Location"], subdomain="selfhosting")
        self.assert_in_success_response(
            [
                "You are about to deactivate this server's",
                server.hostname,
                f'action="/server/{server.uuid!s}/deactivate/"',
            ],
            result,
        )
        result = self.client_post(
            f"/server/{server.uuid!s}/deactivate/", {"confirmed": "true"}, subdomain="selfhosting"
        )
        self.assert_in_success_response(
            [f"Registration deactivated for<br />{server.hostname}"], result
        )

        server.refresh_from_db()
        self.assertEqual(server.deactivated, True)
