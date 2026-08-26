from datetime import timedelta
from unittest.mock import Mock

import responses
import time_machine
from django.conf import settings
from django.utils.timezone import now as timezone_now
from typing_extensions import override

from corporate.lib.stripe import RemoteRealmBillingSession, RemoteServerBillingSession
from corporate.lib.test_stripe_class import StripeTestCase, mock_stripe
from corporate.models.customers import get_customer_by_realm
from corporate.models.plans import CustomerPlan
from corporate.models.sponsorships import ZulipSponsorshipRequest
from corporate.tests.test_remote_billing import RemoteRealmBillingTestCase, RemoteServerTestCase
from zerver.lib.remote_server import send_server_data_to_push_bouncer
from zerver.lib.test_helpers import activate_push_notification_service
from zerver.models import Realm
from zerver.models.realms import get_realm
from zilencer.models import RemoteRealm, RemoteZulipServer


class TestRealmSponsorship(StripeTestCase):
    def test_request_sponsorship_form_with_invalid_url(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        data = {
            "organization_type": Realm.ORG_TYPES["opensource"]["id"],
            "website": "invalid-url",
            "description": "Infinispan is a distributed in-memory key/value data store with optional schema.",
            "expected_total_users": "10 users",
            "plan_to_use_zulip": "For communication on moon.",
            "paid_users_count": "1 user",
            "paid_users_description": "We have 1 paid user.",
        }

        response = self.client_billing_post("/billing/sponsorship", data)

        self.assert_json_error(response, "Enter a valid URL.")

    def test_request_sponsorship_form_with_blank_url(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        data = {
            "organization_type": Realm.ORG_TYPES["opensource"]["id"],
            "website": "",
            "description": "Infinispan is a distributed in-memory key/value data store with optional schema.",
            "expected_total_users": "10 users",
            "plan_to_use_zulip": "For communication on moon.",
            "paid_users_count": "1 user",
            "paid_users_description": "We have 1 paid user.",
        }

        response = self.client_billing_post("/billing/sponsorship", data)

        self.assert_json_success(response)

    @mock_stripe()
    def test_sponsorship_access_for_realms_on_paid_plan(self, *mocks: Mock) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        self.add_card_and_upgrade(user)
        response = self.client_get("/sponsorship/")
        self.assert_in_success_response(
            [
                "How many paid staff does your organization have?",
            ],
            response,
        )

    def test_request_sponsorship(self) -> None:
        user = self.example_user("hamlet")
        self.assertIsNone(get_customer_by_realm(user.realm))

        self.login_user(user)

        data = {
            "organization_type": Realm.ORG_TYPES["opensource"]["id"],
            "website": "https://infinispan.org/",
            "description": "Infinispan is a distributed in-memory key/value data store with optional schema.",
            "expected_total_users": "10 users",
            "plan_to_use_zulip": "For communication on moon.",
            "paid_users_count": "1 user",
            "paid_users_description": "We have 1 paid user.",
        }
        response = self.client_billing_post("/billing/sponsorship", data)
        self.assert_json_success(response)

        customer = get_customer_by_realm(user.realm)
        assert customer is not None
        sponsorship_request = ZulipSponsorshipRequest.objects.filter(
            customer=customer, requested_by=user
        ).first()
        assert sponsorship_request is not None
        self.assertEqual(sponsorship_request.org_website, data["website"])
        self.assertEqual(sponsorship_request.org_description, data["description"])
        self.assertEqual(
            sponsorship_request.org_type,
            Realm.ORG_TYPES["opensource"]["id"],
        )

        customer = get_customer_by_realm(user.realm)
        assert customer is not None
        self.assertEqual(customer.sponsorship_pending, True)
        from django.core.mail import outbox

        self.assert_length(outbox, 1)

        for message in outbox:
            self.assert_length(message.to, 1)
            self.assertEqual(message.to[0], "sales@zulip.com")
            self.assertEqual(message.subject, "Sponsorship request for zulip")
            self.assertEqual(message.reply_to, ["hamlet@zulip.com"])
            self.assertEqual(self.email_envelope_from(message), settings.NOREPLY_EMAIL_ADDRESS)
            self.assertIn("Zulip sponsorship request <noreply-", self.email_display_from(message))
            self.assertIn("Requested by: King Hamlet (Organization owner)", message.body)
            self.assertIn(
                "Support URL: http://zulip.testserver/activity/support?q=zulip", message.body
            )
            self.assertIn("Website: https://infinispan.org", message.body)
            self.assertIn("Organization type: Open-source", message.body)
            self.assertIn("Description:\nInfinispan is a distributed in-memory", message.body)

        response = self.client_get("/upgrade/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "http://zulip.testserver/sponsorship")

        response = self.client_get("/billing/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/sponsorship/")

        response = self.client_get("/sponsorship/")
        self.assert_in_success_response(
            [
                "This organization has requested sponsorship for a",
                '<a href="/plans/">Zulip Cloud Standard</a>',
                'plan.<br/><a href="mailto:support@zulip.com">Contact Zulip support</a> with any questions or updates.',
            ],
            response,
        )

        self.login_user(self.example_user("othello"))
        response = self.client_get("/billing/")
        self.assert_in_success_response(
            ["You do not have permission to view this page."],
            response,
        )

        response = self.client_get("/invoices/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/billing/")

        response = self.client_get("/customer_portal/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/billing/")

        user.realm.plan_type = Realm.PLAN_TYPE_PLUS
        user.realm.save()
        response = self.client_get("/sponsorship/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/billing/")

        user.realm.plan_type = Realm.PLAN_TYPE_STANDARD_FREE
        user.realm.save()
        self.login_user(self.example_user("hamlet"))
        response = self.client_get("/sponsorship/")
        self.assert_in_success_response(
            [
                'Zulip is sponsoring a free <a href="/plans/">Zulip Cloud Standard</a> plan for this organization. 🎉'
            ],
            response,
        )

    def test_sponsorship_page_for_demo_organizations(self) -> None:
        user = self.example_user("hamlet")
        user.realm.demo_organization_scheduled_deletion_date = timezone_now() + timedelta(days=30)
        user.realm.save()
        self.login_user(user)

        response = self.client_get("/sponsorship/", follow=True)
        self.assert_in_success_response(
            ["Demo organizations cannot apply for sponsorship."], response
        )


@activate_push_notification_service()
class TestRemoteRealmSponsorship(StripeTestCase, RemoteRealmBillingTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        self.remote_realm = RemoteRealm.objects.get(uuid=get_realm("zulip").uuid)
        self.billing_session = RemoteRealmBillingSession(remote_realm=self.remote_realm)

    @responses.activate
    def test_request_sponsorship(self) -> None:
        self.login("hamlet")
        hamlet = self.example_user("hamlet")
        realm = hamlet.realm

        self.add_mock_response()
        send_server_data_to_push_bouncer(consider_usage_statistics=False)
        remote_realm = RemoteRealm.objects.get(uuid=hamlet.realm.uuid)
        billing_base_url = self.billing_session.billing_base_url

        self.assertEqual(remote_realm.plan_type, RemoteRealm.PLAN_TYPE_SELF_MANAGED)
        self.assertIsNone(self.billing_session.get_customer())
        result = self.execute_remote_billing_authentication_flow(hamlet)

        # User has no plan, so we redirect to /plans by default.
        self.assertEqual(result["Location"], f"/realm/{realm.uuid!s}/plans/")

        # Check strings on plans page.
        result = self.client_get(result["Location"], subdomain="selfhosting")
        self.assert_not_in_success_response(["Sponsorship pending"], result)

        # Navigate to request sponsorship page.
        result = self.client_get(f"{billing_base_url}/sponsorship/", subdomain="selfhosting")
        self.assert_in_success_response(
            ["Description of your organization", "Requested plan"], result
        )

        # Submit form data.
        data = {
            "organization_type": Realm.ORG_TYPES["opensource"]["id"],
            "website": "https://infinispan.org/",
            "description": "Infinispan is a distributed in-memory key/value data store with optional schema.",
            "expected_total_users": "10 users",
            "plan_to_use_zulip": "For communication on moon.",
            "paid_users_count": "1 user",
            "paid_users_description": "We have 1 paid user.",
            "requested_plan": "Community",
        }
        response = self.client_billing_post("/billing/sponsorship", data)
        self.assert_json_success(response)

        customer = self.billing_session.get_customer()
        assert customer is not None

        sponsorship_request = ZulipSponsorshipRequest.objects.get(customer=customer)
        self.assertEqual(sponsorship_request.requested_plan, data["requested_plan"])
        self.assertEqual(sponsorship_request.org_website, data["website"])
        self.assertEqual(sponsorship_request.org_description, data["description"])
        self.assertEqual(
            sponsorship_request.org_type,
            Realm.ORG_TYPES["opensource"]["id"],
        )

        from django.core.mail import outbox

        # First email is remote user email confirmation, second email is for sponsorship
        message = outbox[1]
        self.assert_length(outbox, 2)
        self.assert_length(message.to, 1)
        self.assertEqual(message.to[0], "sales@zulip.com")
        self.assertEqual(message.subject, "Sponsorship request for Zulip Dev")
        self.assertEqual(message.reply_to, ["hamlet@zulip.com"])
        self.assertEqual(self.email_envelope_from(message), settings.NOREPLY_EMAIL_ADDRESS)
        self.assertIn("Zulip sponsorship request <noreply-", self.email_display_from(message))
        self.assertIn(
            f"Support URL: http://zulip.testserver/activity/remote/support?q={remote_realm.uuid!s}",
            message.body,
        )
        self.assertIn("Website: https://infinispan.org", message.body)
        self.assertIn("Organization type: Open-source", message.body)
        self.assertIn("Description:\nInfinispan is a distributed in-memory", message.body)

        # Check /billing redirects you to sponsorship page.
        response = self.client_get(f"{billing_base_url}/billing/", subdomain="selfhosting")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], f"/realm/{realm.uuid!s}/sponsorship/")

        # Check sponsorship page shows sponsorship pending banner.
        result = self.client_get(f"{billing_base_url}/sponsorship/", subdomain="selfhosting")
        self.assert_in_success_response(
            ["This organization has requested sponsorship for a", "Community"], result
        )

        # Approve sponsorship
        billing_session = RemoteRealmBillingSession(
            remote_realm=remote_realm, support_staff=self.example_user("iago")
        )
        billing_session.approve_sponsorship()
        remote_realm.refresh_from_db()
        self.assertEqual(remote_realm.plan_type, RemoteRealm.PLAN_TYPE_COMMUNITY)
        # Assert such a plan exists
        CustomerPlan.objects.get(
            customer=customer,
            tier=CustomerPlan.TIER_SELF_HOSTED_COMMUNITY,
            status=CustomerPlan.ACTIVE,
            next_invoice_date=None,
            price_per_license=0,
        )

        # Check email sent.
        expected_message = (
            "Your request for Zulip sponsorship has been approved! Your organization has been upgraded to the Zulip Community plan."
            "\n\nIf you could list Zulip as a sponsor on your website, we would really appreciate it!"
        )
        self.assert_length(outbox, 3)
        message = outbox[2]
        self.assert_length(message.to, 1)
        self.assertEqual(message.to[0], "hamlet@zulip.com")
        self.assertEqual(message.subject, "Community plan sponsorship approved for Zulip Dev!")
        self.assertEqual(message.from_email, "noreply@testserver")
        self.assertIn(expected_message[0], message.body)
        self.assertIn(expected_message[1], message.body)

        # Check sponsorship approved banner.
        result = self.client_get(f"{billing_base_url}/sponsorship/", subdomain="selfhosting")
        self.assert_in_success_response(["Zulip is sponsoring a free", "Community"], result)


@activate_push_notification_service()
class TestRemoteServerSponsorship(StripeTestCase, RemoteServerTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        self.remote_server = RemoteZulipServer.objects.get(hostname="demo.example.com")
        self.billing_session = RemoteServerBillingSession(remote_server=self.remote_server)

    @responses.activate
    def test_request_sponsorship(self) -> None:
        hamlet = self.example_user("hamlet")
        now = timezone_now()
        with time_machine.travel(now, tick=False):
            result = self.execute_remote_billing_authentication_flow(
                hamlet.delivery_email, hamlet.full_name, expect_tos=True, confirm_tos=True
            )

        self.add_mock_response()
        send_server_data_to_push_bouncer(consider_usage_statistics=False)
        billing_base_url = self.billing_session.billing_base_url

        self.assertEqual(self.remote_server.plan_type, RemoteZulipServer.PLAN_TYPE_SELF_MANAGED)
        self.assertIsNone(self.billing_session.get_customer())

        # User has no plan, so we redirect to /plans by default.
        self.assertEqual(result["Location"], f"/server/{self.remote_server.uuid!s}/plans/")

        # Check strings on plans page.
        result = self.client_get(result["Location"], subdomain="selfhosting")
        self.assert_not_in_success_response(["Sponsorship pending"], result)

        # Navigate to request sponsorship page.
        result = self.client_get(f"{billing_base_url}/sponsorship/", subdomain="selfhosting")
        self.assert_in_success_response(
            ["Description of your organization", "Requested plan"], result
        )

        # Submit form data.
        data = {
            "organization_type": Realm.ORG_TYPES["opensource"]["id"],
            "website": "https://infinispan.org/",
            "description": "Infinispan is a distributed in-memory key/value data store with optional schema.",
            "expected_total_users": "10 users",
            "plan_to_use_zulip": "For communication on moon.",
            "paid_users_count": "1 user",
            "paid_users_description": "We have 1 paid user.",
            "requested_plan": "Community",
        }
        response = self.client_billing_post("/billing/sponsorship", data)
        self.assert_json_success(response)

        customer = self.billing_session.get_customer()
        assert customer is not None

        sponsorship_request = ZulipSponsorshipRequest.objects.get(customer=customer)
        self.assertEqual(sponsorship_request.requested_plan, data["requested_plan"])
        self.assertEqual(sponsorship_request.org_website, data["website"])
        self.assertEqual(sponsorship_request.org_description, data["description"])
        self.assertEqual(
            sponsorship_request.org_type,
            Realm.ORG_TYPES["opensource"]["id"],
        )

        from django.core.mail import outbox

        # First email is remote user email confirmation, second email is for sponsorship
        message = outbox[1]
        self.assert_length(outbox, 2)
        self.assert_length(message.to, 1)
        self.assertEqual(message.to[0], "sales@zulip.com")
        self.assertEqual(message.subject, "Sponsorship request for demo.example.com")
        self.assertEqual(message.reply_to, ["hamlet@zulip.com"])
        self.assertEqual(self.email_envelope_from(message), settings.NOREPLY_EMAIL_ADDRESS)
        self.assertIn("Zulip sponsorship request <noreply-", self.email_display_from(message))
        self.assertIn(
            f"Support URL: http://zulip.testserver/activity/remote/support?q={self.remote_server.uuid!s}",
            message.body,
        )
        self.assertIn("Website: https://infinispan.org", message.body)
        self.assertIn("Organization type: Open-source", message.body)
        self.assertIn("Description:\nInfinispan is a distributed in-memory", message.body)

        # Check /billing redirects you to sponsorship page.
        response = self.client_get(f"{billing_base_url}/billing/", subdomain="selfhosting")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], f"/server/{self.remote_server.uuid!s}/sponsorship/")

        # Check sponsorship page shows sponsorship pending banner.
        result = self.client_get(f"{billing_base_url}/sponsorship/", subdomain="selfhosting")
        self.assert_in_success_response(
            ["This organization has requested sponsorship for a", "Community"], result
        )

        # Approve sponsorship
        billing_session = RemoteServerBillingSession(
            remote_server=self.remote_server, support_staff=self.example_user("iago")
        )
        billing_session.approve_sponsorship()
        self.remote_server.refresh_from_db()
        self.assertEqual(self.remote_server.plan_type, RemoteZulipServer.PLAN_TYPE_COMMUNITY)
        # Assert such a plan exists
        CustomerPlan.objects.get(
            customer=customer,
            tier=CustomerPlan.TIER_SELF_HOSTED_COMMUNITY,
            status=CustomerPlan.ACTIVE,
            next_invoice_date=None,
            price_per_license=0,
        )

        # Check email sent.
        expected_message = (
            "Your request for Zulip sponsorship has been approved! Your organization has been upgraded to the Zulip Community plan."
            "\n\nIf you could list Zulip as a sponsor on your website, we would really appreciate it!"
        )
        self.assert_length(outbox, 3)
        message = outbox[2]
        self.assert_length(message.to, 1)
        self.assertEqual(message.to[0], "hamlet@zulip.com")
        self.assertEqual(
            message.subject, "Community plan sponsorship approved for demo.example.com!"
        )
        self.assertEqual(message.from_email, "noreply@testserver")
        self.assertIn(expected_message[0], message.body)
        self.assertIn(expected_message[1], message.body)

        # Check sponsorship approved banner.
        result = self.client_get(f"{billing_base_url}/sponsorship/", subdomain="selfhosting")
        self.assert_in_success_response(["Zulip is sponsoring a free", "Community"], result)
