from typing import TYPE_CHECKING, Optional
from unittest import mock

import responses
from django.test import override_settings

from corporate.lib.remote_billing_util import RemoteBillingIdentityDict
from zerver.lib.remote_server import send_realms_only_to_push_bouncer
from zerver.lib.test_classes import BouncerTestCase
from zerver.models import UserProfile
from zilencer.models import RemoteRealm

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as TestHttpResponse


@override_settings(PUSH_NOTIFICATION_BOUNCER_URL="https://push.zulip.org.example.com")
class RemoteBillingAuthenticationTest(BouncerTestCase):
    def execute_remote_billing_authentication_flow(
        self, user: UserProfile, next_page: Optional[str] = None
    ) -> "TestHttpResponse":
        self_hosted_billing_url = "/self-hosted-billing/"
        if next_page is not None:
            self_hosted_billing_url += f"?next_page={next_page}"
        result = self.client_get(self_hosted_billing_url)
        self.assertEqual(result.status_code, 302)
        self.assertIn("http://selfhosting.testserver/remote-billing-login/", result["Location"])

        # We've received a redirect to an URL that will grant us an authenticated
        # session for remote billing.
        result = self.client_get(result["Location"], subdomain="selfhosting")
        # When successful, we receive a final redirect.
        self.assertEqual(result.status_code, 302)

        # Verify the authed data that should have been stored in the session.
        identity_dict = RemoteBillingIdentityDict(
            user_email=user.delivery_email,
            user_uuid=str(user.uuid),
            user_full_name=user.full_name,
            remote_server_uuid=str(self.server.uuid),
            remote_realm_uuid=str(user.realm.uuid),
            next_page=next_page,
        )
        self.assertEqual(
            self.client.session["remote_billing_identities"][f"remote_realm:{user.realm.uuid!s}"],
            identity_dict,
        )

        # It's up to the caller to verify further details, such as the exact redirect URL,
        # depending on the set up and intent of the test.
        return result

    @responses.activate
    def test_remote_billing_authentication_flow(self) -> None:
        self.login("desdemona")
        desdemona = self.example_user("desdemona")
        realm = desdemona.realm

        self.add_mock_response()
        send_realms_only_to_push_bouncer()

        result = self.execute_remote_billing_authentication_flow(desdemona)

        # TODO: The redirect URL will vary depending on the billing state of the user's
        # realm/server when we implement proper logic for that. For now, we can simply
        # hard-code an assert about the endpoint.
        self.assertEqual(result["Location"], f"/realm/{realm.uuid!s}/plans")

        # Go to the URL we're redirected to after authentication and assert
        # some basic expected content.
        result = self.client_get(result["Location"], subdomain="selfhosting")
        self.assert_in_success_response(["Your remote user info:"], result)
        self.assert_in_success_response([desdemona.delivery_email], result)

    @responses.activate
    def test_remote_billing_authentication_flow_realm_not_registered(self) -> None:
        self.login("desdemona")
        desdemona = self.example_user("desdemona")
        realm = desdemona.realm

        self.add_mock_response()

        # We do the flow without having the realm registered with the push bouncer.
        # In such a case, the local /self-hosted-billing/ endpoint should error-handle
        # properly and end up registering the server's realms with the bouncer,
        # and successfully completing the flow - transparently to the user.
        self.assertFalse(RemoteRealm.objects.filter(uuid=realm.uuid).exists())

        # send_realms_only_to_push_bouncer will be called within the endpoint's
        # error handling to register realms with the bouncer. We mock.patch it
        # to be able to assert that it was called - but also use side_effect
        # to maintain the original behavior of the function, instead of
        # replacing it with a Mock.
        with mock.patch(
            "zerver.views.push_notifications.send_realms_only_to_push_bouncer",
            side_effect=send_realms_only_to_push_bouncer,
        ) as m:
            result = self.execute_remote_billing_authentication_flow(desdemona)

        m.assert_called_once()
        # The user's realm should now be registered:
        self.assertTrue(RemoteRealm.objects.filter(uuid=realm.uuid).exists())

        self.assertEqual(result["Location"], f"/realm/{realm.uuid!s}/plans")

        result = self.client_get(result["Location"], subdomain="selfhosting")
        self.assert_in_success_response(["Your remote user info:"], result)
        self.assert_in_success_response([desdemona.delivery_email], result)

    @responses.activate
    def test_remote_billing_authentication_flow_to_sponsorship_page(self) -> None:
        self.login("desdemona")
        desdemona = self.example_user("desdemona")
        realm = desdemona.realm

        self.add_mock_response()
        send_realms_only_to_push_bouncer()

        result = self.execute_remote_billing_authentication_flow(desdemona, "sponsorship")

        self.assertEqual(result["Location"], f"/realm/{realm.uuid!s}/sponsorship")

        # Go to the URL we're redirected to after authentication and assert
        # some basic expected content.
        result = self.client_get(result["Location"], subdomain="selfhosting")
        self.assert_in_success_response(
            ["Request Zulip Cloud sponsorship", "Description of your organization"], result
        )

    @responses.activate
    def test_remote_billing_authentication_flow_to_upgrade_page(self) -> None:
        self.login("desdemona")
        desdemona = self.example_user("desdemona")
        realm = desdemona.realm

        self.add_mock_response()
        send_realms_only_to_push_bouncer()

        result = self.execute_remote_billing_authentication_flow(desdemona, "upgrade")

        self.assertEqual(result["Location"], f"/realm/{realm.uuid!s}/upgrade")

        # Go to the URL we're redirected to after authentication and assert
        # some basic expected content.
        result = self.client_get(result["Location"], subdomain="selfhosting")
        self.assert_in_success_response(
            ["Upgrade", "Purchase Zulip", "Your subscription will renew automatically."], result
        )
