from datetime import timedelta
from typing import TYPE_CHECKING, Optional
from unittest import mock

import responses
import time_machine
from django.conf import settings
from django.test import override_settings
from django.utils.timezone import now as timezone_now
from typing_extensions import override

from corporate.lib.remote_billing_util import (
    REMOTE_BILLING_SESSION_VALIDITY_SECONDS,
    LegacyServerIdentityDict,
    RemoteBillingIdentityDict,
    RemoteBillingUserDict,
)
from corporate.views.remote_billing_page import generate_confirmation_link_for_server_deactivation
from zerver.lib.remote_server import send_server_data_to_push_bouncer
from zerver.lib.test_classes import BouncerTestCase
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.models import UserProfile
from zilencer.models import (
    PreregistrationRemoteRealmBillingUser,
    PreregistrationRemoteServerBillingUser,
    RemoteRealm,
    RemoteRealmBillingUser,
    RemoteServerBillingUser,
)

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as TestHttpResponse


@override_settings(PUSH_NOTIFICATION_BOUNCER_URL="https://push.zulip.org.example.com")
class RemoteBillingAuthenticationTest(BouncerTestCase):
    def execute_remote_billing_authentication_flow(
        self,
        user: UserProfile,
        next_page: Optional[str] = None,
        expect_tos: bool = True,
        confirm_tos: bool = True,
        first_time_login: bool = True,
        # This only matters if first_time_login is True, since otherwise
        # there's no confirmation link to be clicked:
        return_without_clicking_confirmation_link: bool = False,
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

        if first_time_login:
            self.assertFalse(RemoteRealmBillingUser.objects.filter(user_uuid=user.uuid).exists())
            # When logging in for the first time some extra steps are needed
            # to confirm and verify the email address.
            self.assertEqual(result.status_code, 200)
            self.assert_in_success_response(["Enter log in email"], result)
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
            self.assertEqual(result.status_code, 200)
            self.assert_in_success_response(
                ["We have sent a log in link", "link will expire in", user.delivery_email],
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
            result = self.client_get(final_url, subdomain="selfhosting")

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
        with time_machine.travel(
            now + timedelta(seconds=REMOTE_BILLING_SESSION_VALIDITY_SECONDS + 30),
            tick=False,
        ):
            with self.assertLogs("django.request", "ERROR") as m, self.assertRaises(AssertionError):
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


class LegacyServerLoginTest(BouncerTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        self.uuid = self.server.uuid
        self.secret = self.server.api_key

    def execute_remote_billing_authentication_flow(
        self,
        email: str,
        full_name: str,
        next_page: Optional[str] = None,
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
        self.assertEqual(result.status_code, 200)
        self.assert_in_success_response(
            ["We have sent a log in link", "link will expire in", email],
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

    def test_server_login_get(self) -> None:
        result = self.client_get("/serverlogin/", subdomain="selfhosting")
        self.assertEqual(result.status_code, 200)
        self.assert_in_success_response(
            ["Authenticate server for Zulip billing management"], result
        )

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
        # TODO Update the string when we have a complete sponsorship page for legacy servers.
        self.assert_in_success_response(["Request Zulip", "sponsorship"], result)

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
        result = self.client_get(f"/server/{self.uuid}/billing/", subdomain="selfhosting")
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
        result = self.client_get(f"/server/{self.uuid}/billing/", subdomain="selfhosting")
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
            result = self.client_get(f"/server/{self.uuid}/upgrade/", subdomain="selfhosting")
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
            ["Log in to Zulip plan management", server.contact_email], result
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
        self.assert_in_success_response([f"Registration deactivated for {server.hostname}"], result)

        server.refresh_from_db()
        self.assertEqual(server.deactivated, True)
