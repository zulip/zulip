import typing
import uuid
from datetime import timedelta
from unittest import mock
from unittest.mock import MagicMock, Mock, patch

import responses
import stripe
import time_machine
from django.utils.timezone import now as timezone_now
from typing_extensions import override

from corporate.lib.stripe import (
    STRIPE_API_VERSION,
    BillingSessionAuditLogEventError,
    BillingSessionEventType,
    RemoteServerBillingSession,
    add_months,
    check_remote_server_audit_log_data,
    invoice_plans_as_needed,
)
from corporate.lib.test_stripe_class import StripeTestCase, mock_stripe
from corporate.models.customers import Customer
from corporate.models.licenses import LicenseLedger
from corporate.models.plans import CustomerPlan, CustomerPlanOffer, get_current_plan_by_customer
from corporate.models.stripe_state import Invoice
from corporate.tests.test_remote_billing import RemoteServerTestCase
from corporate.views.remote_billing_page import generate_confirmation_link_for_server_deactivation
from zerver.actions.create_user import do_create_user
from zerver.lib.remote_server import send_server_data_to_push_bouncer
from zerver.lib.test_helpers import activate_push_notification_service
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.models import RealmAuditLog, UserProfile
from zerver.models.realm_audit_logs import AuditLogEventType
from zerver.models.realms import get_realm
from zilencer.models import RemoteRealmAuditLog, RemoteZulipServer, RemoteZulipServerAuditLog


class TestRemoteServerBillingSession(StripeTestCase):
    def test_get_audit_log_error(self) -> None:
        server_uuid = str(uuid.uuid4())
        remote_server = RemoteZulipServer.objects.create(
            uuid=server_uuid,
            api_key="magic_secret_api_key",
            hostname="demo.example.com",
            contact_email="email@example.com",
        )
        billing_session = RemoteServerBillingSession(remote_server)
        fake_audit_log = typing.cast(BillingSessionEventType, 0)
        with self.assertRaisesRegex(
            BillingSessionAuditLogEventError, "Unknown audit log event type: 0"
        ):
            billing_session.get_audit_log_event(event_type=fake_audit_log)

    def test_get_customer(self) -> None:
        server_uuid = str(uuid.uuid4())
        remote_server = RemoteZulipServer.objects.create(
            uuid=server_uuid,
            api_key="magic_secret_api_key",
            hostname="demo.example.com",
            contact_email="email@example.com",
        )
        billing_session = RemoteServerBillingSession(remote_server)
        customer = billing_session.get_customer()
        self.assertEqual(customer, None)

        customer = Customer.objects.create(
            remote_server=remote_server, stripe_customer_id="cus_12345"
        )
        self.assertEqual(billing_session.get_customer(), customer)

    # @mock_stripe
    # def test_update_or_create_stripe_customer(self) -> None:
    #     server_uuid = str(uuid.uuid4())
    #     remote_server = RemoteZulipServer.objects.create(
    #         uuid=server_uuid,
    #         api_key="magic_secret_api_key",
    #         hostname="demo.example.com",
    #         contact_email="email@example.com",
    #     )
    #     billing_session = RemoteServerBillingSession(remote_server)
    #     # We need to generate stripe fixture for this type of test.
    #     customer = billing_session.update_or_create_stripe_customer()
    #     assert customer.stripe_customer_id
    #     # Confirm audit log, etc.

    def test_check_audit_log_data_for_free_trial_billed_by_invoice(self) -> None:
        remote_server = RemoteZulipServer.objects.create(
            uuid=str(uuid.uuid4()),
            api_key="magic_secret_api_key",
            hostname="demo.example.com",
            contact_email="email@example.com",
            last_audit_log_update=timezone_now() - timedelta(days=5),
        )
        billing_session = RemoteServerBillingSession(remote_server)
        customer = Customer.objects.create(
            remote_server=remote_server, stripe_customer_id="cus_12345"
        )
        plan = CustomerPlan.objects.create(
            customer=customer,
            tier=CustomerPlan.TIER_SELF_HOSTED_BASIC,
            status=CustomerPlan.FREE_TRIAL,
            # Billed by invoice rather than charged automatically.
            charge_automatically=False,
            billing_cycle_anchor=timezone_now() - timedelta(days=30),
            billing_schedule=CustomerPlan.BILLING_SCHEDULE_MONTHLY,
            price_per_license=350,
            # Audit log data above is stale relative to this date.
            next_invoice_date=timezone_now(),
        )

        from django.core.mail import outbox

        # Unpaid free trial: notify Zulip support, and return true to
        # not defer invoicing the plan so that it can be downgraded.
        Invoice.objects.create(
            customer=customer,
            plan=plan,
            stripe_invoice_id="stripe_invoice_id_unpaid",
            status=Invoice.SENT,
        )
        self.assertTrue(check_remote_server_audit_log_data(remote_server, plan, billing_session))
        plan.refresh_from_db()
        self.assertTrue(plan.stale_audit_log_data_email_sent)
        self.assert_length(outbox, 1)
        message = outbox[-1]
        self.assertEqual(message.to, ["sales@zulip.com"])
        self.assertEqual(
            message.subject,
            f"Stale audit log data for {billing_session.billing_entity_display_name}'s plan",
        )

        plan.stale_audit_log_data_email_sent = False
        plan.save(update_fields=["stale_audit_log_data_email_sent"])

        # Paid free trial: notify Zulip support, and return false to
        # defer invoicing the plan until audit log data is fresh.
        Invoice.objects.create(
            customer=customer,
            plan=plan,
            stripe_invoice_id="stripe_invoice_id_paid",
            status=Invoice.PAID,
        )
        self.assertFalse(check_remote_server_audit_log_data(remote_server, plan, billing_session))
        plan.refresh_from_db()
        self.assertTrue(plan.stale_audit_log_data_email_sent)
        self.assert_length(outbox, 2)
        message = outbox[-1]
        self.assertEqual(message.to, ["sales@zulip.com"])
        self.assertEqual(
            message.subject,
            f"Stale audit log data for {billing_session.billing_entity_display_name}'s plan",
        )


@activate_push_notification_service()
class TestRemoteServerBillingFlow(StripeTestCase, RemoteServerTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()

        # Reset already created audit logs for this test as they have
        # event_time=timezone_now() that will affects the LicenseLedger
        # queries as their event_time would be more recent than other
        # operations we perform in this test.
        RealmAuditLog.objects.filter(event_type__in=RealmAuditLog.SYNCED_BILLING_EVENTS).delete()
        zulip_realm = get_realm("zulip")
        lear_realm = get_realm("lear")
        zephyr_realm = get_realm("zephyr")
        with time_machine.travel(self.now, tick=False):
            for count in range(2):
                for realm in [zulip_realm, zephyr_realm, lear_realm]:
                    do_create_user(
                        f"email {count}",
                        f"password {count}",
                        realm,
                        "name",
                        acting_user=None,
                    )

        self.remote_server = RemoteZulipServer.objects.get(hostname="demo.example.com")
        self.billing_session = RemoteServerBillingSession(remote_server=self.remote_server)

    @responses.activate
    @mock_stripe()
    def test_non_sponsorship_billing(self, *mocks: Mock) -> None:
        server_user_count = UserProfile.objects.filter(is_bot=False, is_active=True).count()

        # Upload data
        self.add_mock_response()
        with time_machine.travel(self.now, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)

        self.login("hamlet")
        hamlet = self.example_user("hamlet")
        billing_base_url = self.billing_session.billing_base_url

        result = self.execute_remote_billing_authentication_flow(
            hamlet.delivery_email, hamlet.full_name, expect_tos=True, confirm_tos=True
        )
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], f"{billing_base_url}/plans/")

        # upgrade to business plan
        with time_machine.travel(self.now, tick=False):
            result = self.client_get(f"{billing_base_url}/upgrade/", subdomain="selfhosting")
        self.assertEqual(result.status_code, 200)
        self.assert_in_success_response(["Add card", "Purchase Zulip Business"], result)

        # Same result even with free trial enabled for self hosted customers since we don't
        # offer free trial for business plan.
        with (
            self.settings(SELF_HOSTING_FREE_TRIAL_DAYS=30),
            time_machine.travel(self.now, tick=False),
        ):
            result = self.client_get(f"{billing_base_url}/upgrade/", subdomain="selfhosting")

        self.assert_in_success_response(["Add card", "Purchase Zulip Business"], result)

        self.assertFalse(Customer.objects.exists())
        self.assertFalse(CustomerPlan.objects.exists())
        self.assertFalse(LicenseLedger.objects.exists())

        with time_machine.travel(self.now, tick=False):
            stripe_customer = self.add_card_and_upgrade()

        customer = Customer.objects.get(stripe_customer_id=stripe_customer.id)
        plan = CustomerPlan.objects.get(customer=customer)
        LicenseLedger.objects.get(plan=plan)

        # Visit billing page
        with time_machine.travel(self.now + timedelta(days=1), tick=False):
            response = self.client_get(f"{billing_base_url}/billing/", subdomain="selfhosting")
        for substring in [
            "Zulip Business",
            "Number of licenses",
            f"{25}",
            "Your plan will automatically renew on",
            "January 2, 2013",
            f"${80 * 25:,.2f}",
            "Visa ending in 4242",
            "Update card",
        ]:
            self.assert_in_response(substring, response)

        # Verify that change in user count of any realm collectively updates LicenseLedger.
        audit_log_count = RemoteRealmAuditLog.objects.count()
        self.assertEqual(LicenseLedger.objects.count(), 1)

        with time_machine.travel(self.now + timedelta(days=2), tick=False):
            # Create 4 new users in each lear and zulip realm.
            for count in range(2, 6):
                for realm in [get_realm("lear"), get_realm("zulip")]:
                    do_create_user(
                        f"email {count}",
                        f"password {count}",
                        realm,
                        "name",
                        acting_user=None,
                    )

        with time_machine.travel(self.now + timedelta(days=3), tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)

        self.assertEqual(
            RemoteRealmAuditLog.objects.count(),
            audit_log_count + 8,
        )
        paid_license_count = server_user_count + 8
        self.check_last_ledger_entry_license_counts(plan, paid_license_count, paid_license_count)

        # Login again
        result = self.execute_remote_billing_authentication_flow(
            hamlet.delivery_email, hamlet.full_name, expect_tos=False, confirm_tos=False
        )
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], f"{billing_base_url}/billing/")

        # Downgrade
        with (
            self.assertLogs("corporate.stripe", "INFO") as m,
            time_machine.travel(self.now + timedelta(days=7), tick=False),
        ):
            response = self.client_billing_patch(
                "/billing/plan",
                {"status": CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE},
            )
            expected_log = f"INFO:corporate.stripe:Change plan status: Customer.id: {customer.id}, CustomerPlan.id: {plan.id}, status: {CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE}"
            self.assertEqual(m.output[0], expected_log)
            self.assert_json_success(response)
        plan.refresh_from_db()
        self.assertEqual(plan.licenses_at_next_renewal(), None)

    @responses.activate
    @mock_stripe()
    def test_upgrade_complimentary_access_plan(self, *mocks: Mock) -> None:
        # Upload data
        with time_machine.travel(self.now, tick=False):
            self.add_mock_response()
            send_server_data_to_push_bouncer(consider_usage_statistics=False)

        # Create complimentary access plan for server.
        with time_machine.travel(self.now, tick=False):
            start_date = timezone_now()
            end_date = add_months(start_date, months=3)
            self.billing_session.create_complimentary_access_plan(start_date, end_date)

        customer = self.billing_session.get_customer()
        assert customer is not None
        customer_plan = get_current_plan_by_customer(customer)
        assert customer_plan is not None
        self.assertEqual(customer_plan.tier, CustomerPlan.TIER_SELF_HOSTED_LEGACY)
        self.assertEqual(customer_plan.status, CustomerPlan.ACTIVE)

        self.login("hamlet")
        hamlet = self.example_user("hamlet")
        billing_base_url = self.billing_session.billing_base_url

        # Login
        with time_machine.travel(self.now, tick=False):
            result = self.execute_remote_billing_authentication_flow(
                hamlet.delivery_email, hamlet.full_name, expect_tos=True, confirm_tos=True
            )
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], f"{billing_base_url}/plans/")

        # Visit '/upgrade'
        with time_machine.travel(self.now, tick=False):
            result = self.client_get(f"{billing_base_url}/upgrade/", subdomain="selfhosting")
        self.assertEqual(result.status_code, 200)
        self.assert_in_success_response(["Add card", "Schedule upgrade to Zulip Business"], result)

        # Add card and schedule upgrade
        with time_machine.travel(self.now, tick=False):
            self.add_card_and_upgrade(
                remote_server_plan_start_date="billing_cycle_end_date", talk_to_stripe=False
            )
        customer_plan.refresh_from_db()
        self.assertEqual(customer_plan.status, CustomerPlan.SWITCH_PLAN_TIER_AT_PLAN_END)
        self.assertEqual(customer_plan.end_date, end_date)
        new_customer_plan = self.billing_session.get_next_plan(customer_plan)
        assert new_customer_plan is not None
        self.assertEqual(new_customer_plan.tier, CustomerPlan.TIER_SELF_HOSTED_BUSINESS)
        self.assertEqual(new_customer_plan.status, CustomerPlan.NEVER_STARTED)
        self.assertEqual(new_customer_plan.billing_cycle_anchor, end_date)

        # Visit billing page
        with time_machine.travel(self.now, tick=False):
            response = self.client_get(f"{billing_base_url}/billing/", subdomain="selfhosting")
        for substring in [
            "(complimentary access)",
            f"Your complimentary access to Zulip Basic ends on {end_date.strftime('%B %d, %Y')}",
            f"Your plan will automatically upgrade to Zulip Business on {end_date.strftime('%B %d, %Y')}",
            "Expected next charge",
            f"${80 * 25 - 20 * 12:,.2f}",
            "Visa ending in 4242",
            "Update card",
        ]:
            self.assert_in_response(substring, response)

        # Login again
        result = self.execute_remote_billing_authentication_flow(
            hamlet.delivery_email, hamlet.full_name, expect_tos=False, confirm_tos=False
        )
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], f"{billing_base_url}/billing/")

        # Downgrade
        with (
            self.assertLogs("corporate.stripe", "INFO") as m,
            time_machine.travel(self.now + timedelta(days=7), tick=False),
        ):
            response = self.client_billing_patch(
                "/billing/plan",
                {"status": CustomerPlan.ACTIVE},
            )
            self.assert_json_success(response)
            self.assertEqual(
                m.output[0],
                f"INFO:corporate.stripe:Change plan status: Customer.id: {customer.id}, CustomerPlan.id: {new_customer_plan.id}, status: {CustomerPlan.ENDED}",
            )
            self.assertEqual(
                m.output[1],
                f"INFO:corporate.stripe:Change plan status: Customer.id: {customer.id}, CustomerPlan.id: {customer_plan.id}, status: {CustomerPlan.ACTIVE}",
            )

    @responses.activate
    @mock_stripe()
    def test_free_trial_not_available_for_complimentary_access_customer(self, *mocks: Mock) -> None:
        with self.settings(SELF_HOSTING_FREE_TRIAL_DAYS=30):
            self.login("hamlet")
            hamlet = self.example_user("hamlet")

            self.add_mock_response()

            with time_machine.travel(self.now, tick=False):
                send_server_data_to_push_bouncer(consider_usage_statistics=False)
                # Free trial is not available for customers with active complimentary access plan.
                end_date = add_months(self.now, months=3)
                self.billing_session.create_complimentary_access_plan(self.now, end_date)

            result = self.execute_remote_billing_authentication_flow(
                hamlet.delivery_email, hamlet.full_name
            )
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result["Location"], f"{self.billing_session.billing_base_url}/plans/")
            with time_machine.travel(self.now, tick=False):
                response = self.client_get(
                    f"{self.billing_session.billing_base_url}/plans/", subdomain="selfhosting"
                )
                self.assert_not_in_success_response(["free trial"], response)

            with time_machine.travel(self.now, tick=False):
                result = self.client_get(
                    f"{self.billing_session.billing_base_url}/upgrade/?tier={CustomerPlan.TIER_SELF_HOSTED_BASIC}",
                    subdomain="selfhosting",
                )
                self.assert_not_in_success_response(["free trial"], response)

            with time_machine.travel(self.now, tick=False):
                self.add_card_and_upgrade(
                    tier=CustomerPlan.TIER_SELF_HOSTED_BASIC, schedule="monthly"
                )

            with time_machine.travel(self.now + timedelta(days=1), tick=False):
                response = self.client_get(
                    f"{self.billing_session.billing_base_url}/billing/", subdomain="selfhosting"
                )
                self.assert_not_in_success_response(["(free trial)"], response)

    @responses.activate
    @mock_stripe()
    def test_free_trial_not_available_for_previous_complimentary_access_customer(
        self, *mocks: Mock
    ) -> None:
        with self.settings(SELF_HOSTING_FREE_TRIAL_DAYS=30):
            self.login("hamlet")
            hamlet = self.example_user("hamlet")

            self.add_mock_response()

            with time_machine.travel(self.now, tick=False):
                send_server_data_to_push_bouncer(consider_usage_statistics=False)
                # Free trial is not available for customers with active complimentary access plan.
                end_date = add_months(self.now, months=3)
                self.billing_session.create_complimentary_access_plan(self.now, end_date)
                CustomerPlan.objects.filter(customer__remote_server=self.remote_server).update(
                    status=CustomerPlan.ENDED
                )

            result = self.execute_remote_billing_authentication_flow(
                hamlet.delivery_email, hamlet.full_name
            )
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result["Location"], f"{self.billing_session.billing_base_url}/plans/")
            with time_machine.travel(self.now, tick=False):
                response = self.client_get(
                    f"{self.billing_session.billing_base_url}/plans/", subdomain="selfhosting"
                )
                self.assert_not_in_success_response(["free trial"], response)

            with time_machine.travel(self.now, tick=False):
                result = self.client_get(
                    f"{self.billing_session.billing_base_url}/upgrade/?tier={CustomerPlan.TIER_SELF_HOSTED_BASIC}",
                    subdomain="selfhosting",
                )
                self.assert_not_in_success_response(["free trial"], response)

            with time_machine.travel(self.now, tick=False):
                self.add_card_and_upgrade(
                    tier=CustomerPlan.TIER_SELF_HOSTED_BASIC, schedule="monthly"
                )

            with time_machine.travel(self.now + timedelta(days=1), tick=False):
                response = self.client_get(
                    f"{self.billing_session.billing_base_url}/billing/", subdomain="selfhosting"
                )
                self.assert_not_in_success_response(["(free trial)"], response)

    @responses.activate
    @mock_stripe()
    def test_upgrade_user_to_basic_plan_free_trial_remote_server(self, *mocks: Mock) -> None:
        with self.settings(SELF_HOSTING_FREE_TRIAL_DAYS=30):
            self.login("hamlet")
            hamlet = self.example_user("hamlet")

            self.add_mock_response()
            realm_user_count = UserProfile.objects.filter(is_bot=False, is_active=True).count()
            self.assertEqual(realm_user_count, 18)

            with time_machine.travel(self.now, tick=False):
                send_server_data_to_push_bouncer(consider_usage_statistics=False)

            result = self.execute_remote_billing_authentication_flow(
                hamlet.delivery_email, hamlet.full_name
            )
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result["Location"], f"{self.billing_session.billing_base_url}/plans/")

            # upgrade to basic plan
            with time_machine.travel(self.now, tick=False):
                result = self.client_get(
                    f"{self.billing_session.billing_base_url}/upgrade/?tier={CustomerPlan.TIER_SELF_HOSTED_BASIC}",
                    subdomain="selfhosting",
                )
            self.assertEqual(result.status_code, 200)

            min_licenses = self.billing_session.min_licenses_for_plan(
                CustomerPlan.TIER_SELF_HOSTED_BASIC
            )
            self.assertEqual(min_licenses, 6)
            flat_discount, flat_discounted_months = self.billing_session.get_flat_discount_info()
            self.assertEqual(flat_discounted_months, 12)

            self.assert_in_success_response(
                [
                    "Start free trial",
                    "Zulip Basic",
                    "Due",
                    "on February 1, 2012",
                    f"{min_licenses}",
                    "Add card",
                    "Start 30-day free trial",
                ],
                result,
            )

            self.assertFalse(Customer.objects.exists())
            self.assertFalse(CustomerPlan.objects.exists())
            self.assertFalse(LicenseLedger.objects.exists())

            with time_machine.travel(self.now, tick=False):
                stripe_customer = self.add_card_and_upgrade(
                    tier=CustomerPlan.TIER_SELF_HOSTED_BASIC, schedule="monthly"
                )
            self.assertEqual(Invoice.objects.count(), 0)

            customer = Customer.objects.get(stripe_customer_id=stripe_customer.id)
            plan = CustomerPlan.objects.get(customer=customer)
            LicenseLedger.objects.get(plan=plan)

            with time_machine.travel(self.now + timedelta(days=1), tick=False):
                response = self.client_get(
                    f"{self.billing_session.billing_base_url}/billing/", subdomain="selfhosting"
                )
            for substring in [
                "Zulip Basic",
                "(free trial)",
                "Number of licenses",
                f"{realm_user_count}",
                "February 1, 2012",
                "Your plan will automatically renew on",
                f"${3.5 * realm_user_count - flat_discount // 100 * 1:,.2f}",
                "Visa ending in 4242",
                "Update card",
            ]:
                self.assert_in_response(substring, response)

            # Verify that change in user count updates LicenseLedger.
            audit_log_count = RemoteRealmAuditLog.objects.count()
            self.assertEqual(LicenseLedger.objects.count(), 1)

            with time_machine.travel(self.now + timedelta(days=2), tick=False):
                for count in range(realm_user_count, realm_user_count + 10):
                    do_create_user(
                        f"email {count}",
                        f"password {count}",
                        hamlet.realm,
                        "name",
                        role=UserProfile.ROLE_MEMBER,
                        acting_user=None,
                    )

            with time_machine.travel(self.now + timedelta(days=3), tick=False):
                send_server_data_to_push_bouncer(consider_usage_statistics=False)

            self.assertEqual(
                RemoteRealmAuditLog.objects.count(),
                audit_log_count + 10,
            )
            paid_license_count = realm_user_count + 10
            self.check_last_ledger_entry_license_counts(
                plan, paid_license_count, paid_license_count
            )

            with time_machine.travel(self.now + timedelta(days=3), tick=False):
                response = self.client_get(
                    f"{self.billing_session.billing_base_url}/billing/", subdomain="selfhosting"
                )

            for substring in [
                "Zulip Basic",
                "Number of licenses",
                f"{paid_license_count}",
                "February 1, 2012",
                "Your plan will automatically renew on",
                f"${3.5 * paid_license_count - flat_discount // 100 * 1:,.2f}",
                "Visa ending in 4242",
                "Update card",
            ]:
                self.assert_in_response(substring, response)

            # Check minimum licenses is 0 after flat discounted months is over.
            customer.flat_discounted_months = 0
            customer.save(update_fields=["flat_discounted_months"])
            self.assertEqual(
                self.billing_session.min_licenses_for_plan(CustomerPlan.TIER_SELF_HOSTED_BASIC), 1
            )

            # TODO: Add test for invoice generation once that's implemented.

    @responses.activate
    @mock_stripe()
    def test_redirect_for_remote_server_billing_page_downgrade_at_free_trial_end(
        self, *mocks: Mock
    ) -> None:
        with self.settings(SELF_HOSTING_FREE_TRIAL_DAYS=30):
            self.login("hamlet")
            hamlet = self.example_user("hamlet")

            self.add_mock_response()
            with time_machine.travel(self.now, tick=False):
                send_server_data_to_push_bouncer(consider_usage_statistics=False)

            result = self.execute_remote_billing_authentication_flow(
                hamlet.delivery_email, hamlet.full_name
            )
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result["Location"], f"{self.billing_session.billing_base_url}/plans/")

            # upgrade to basic plan
            with time_machine.travel(self.now, tick=False):
                result = self.client_get(
                    f"{self.billing_session.billing_base_url}/upgrade/?tier={CustomerPlan.TIER_SELF_HOSTED_BASIC}",
                    subdomain="selfhosting",
                )
            self.assertEqual(result.status_code, 200)

            self.assert_in_success_response(
                [
                    "Start free trial",
                    "Zulip Basic",
                    "Due",
                    "on February 1, 2012",
                    "Add card",
                    "Start 30-day free trial",
                ],
                result,
            )

            self.assertFalse(Customer.objects.exists())
            self.assertFalse(CustomerPlan.objects.exists())
            self.assertFalse(LicenseLedger.objects.exists())

            with time_machine.travel(self.now, tick=False):
                stripe_customer = self.add_card_and_upgrade(
                    tier=CustomerPlan.TIER_SELF_HOSTED_BASIC, schedule="monthly"
                )

            self.assertEqual(Invoice.objects.count(), 0)
            customer = Customer.objects.get(stripe_customer_id=stripe_customer.id)
            plan = CustomerPlan.objects.get(customer=customer)
            LicenseLedger.objects.get(plan=plan)

            with time_machine.travel(self.now + timedelta(days=1), tick=False):
                response = self.client_get(
                    f"{self.billing_session.billing_base_url}/billing/", subdomain="selfhosting"
                )
            for substring in [
                "Zulip Basic",
                "(free trial)",
                "Your plan will automatically renew on",
                "February 1, 2012",
            ]:
                self.assert_in_response(substring, response)

            # schedule downgrade
            with (
                time_machine.travel(self.now + timedelta(days=3), tick=False),
                self.assertLogs("corporate.stripe", "INFO") as m,
            ):
                response = self.client_billing_patch(
                    "/billing/plan",
                    {"status": CustomerPlan.DOWNGRADE_AT_END_OF_FREE_TRIAL},
                )
                self.assert_json_success(response)
                plan.refresh_from_db()
                self.assertEqual(plan.status, CustomerPlan.DOWNGRADE_AT_END_OF_FREE_TRIAL)
                expected_log = f"INFO:corporate.stripe:Change plan status: Customer.id: {customer.id}, CustomerPlan.id: {plan.id}, status: {CustomerPlan.DOWNGRADE_AT_END_OF_FREE_TRIAL}"
                self.assertEqual(m.output[0], expected_log)

            # Visit /billing on free-trial end date before the invoice cron runs.
            with time_machine.travel(self.now + timedelta(days=30), tick=False):
                response = self.client_get(
                    f"{self.billing_session.billing_base_url}/billing/", subdomain="selfhosting"
                )
                self.assertEqual(response.status_code, 302)
                self.assertEqual(
                    f"{self.billing_session.billing_base_url}/plans/", response["Location"]
                )

    @responses.activate
    @mock_stripe()
    def test_upgrade_server_user_to_monthly_basic_plan(self, *mocks: Mock) -> None:
        self.login("hamlet")
        hamlet = self.example_user("hamlet")

        self.add_mock_response()
        server_user_count = UserProfile.objects.filter(is_bot=False, is_active=True).count()
        self.assertEqual(server_user_count, 18)

        with time_machine.travel(self.now, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)

        result = self.execute_remote_billing_authentication_flow(
            hamlet.delivery_email, hamlet.full_name
        )
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], f"{self.billing_session.billing_base_url}/plans/")

        # upgrade to basic plan
        with time_machine.travel(self.now, tick=False):
            result = self.client_get(
                f"{self.billing_session.billing_base_url}/upgrade/?tier={CustomerPlan.TIER_SELF_HOSTED_BASIC}",
                subdomain="selfhosting",
            )
        self.assertEqual(result.status_code, 200)

        min_licenses = self.billing_session.min_licenses_for_plan(
            CustomerPlan.TIER_SELF_HOSTED_BASIC
        )
        self.assertEqual(min_licenses, 6)
        flat_discount, flat_discounted_months = self.billing_session.get_flat_discount_info()
        self.assertEqual(flat_discounted_months, 12)

        self.assert_in_success_response(
            [f"{min_licenses}", "Add card", "Purchase Zulip Basic"], result
        )

        self.assertFalse(Customer.objects.exists())
        self.assertFalse(CustomerPlan.objects.exists())
        self.assertFalse(LicenseLedger.objects.exists())

        with time_machine.travel(self.now, tick=False):
            stripe_customer = self.add_card_and_upgrade(
                tier=CustomerPlan.TIER_SELF_HOSTED_BASIC, schedule="monthly"
            )

        customer = Customer.objects.get(stripe_customer_id=stripe_customer.id)
        plan = CustomerPlan.objects.get(customer=customer)
        LicenseLedger.objects.get(plan=plan)

        with time_machine.travel(self.now + timedelta(days=1), tick=False):
            response = self.client_get(
                f"{self.billing_session.billing_base_url}/billing/", subdomain="selfhosting"
            )
        for substring in [
            "Zulip Basic",
            "Number of licenses",
            f"{server_user_count}",
            "February 2, 2012",
            "Your plan will automatically renew on",
            f"${3.5 * server_user_count - flat_discount // 100 * 1:,.2f}",
            "Visa ending in 4242",
            "Update card",
        ]:
            self.assert_in_response(substring, response)

        # Verify that change in user count updates LicenseLedger.
        audit_log_count = RemoteRealmAuditLog.objects.count()
        self.assertEqual(LicenseLedger.objects.count(), 1)

        with time_machine.travel(self.now + timedelta(days=2), tick=False):
            for count in range(server_user_count, server_user_count + 10):
                do_create_user(
                    f"email {count}",
                    f"password {count}",
                    hamlet.realm,
                    "name",
                    role=UserProfile.ROLE_MEMBER,
                    acting_user=None,
                )

        with time_machine.travel(self.now + timedelta(days=3), tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)

        self.assertEqual(
            RemoteRealmAuditLog.objects.count(),
            audit_log_count + 10,
        )
        paid_license_count = server_user_count + 10
        self.check_last_ledger_entry_license_counts(plan, paid_license_count, paid_license_count)

        with time_machine.travel(self.now + timedelta(days=3), tick=False):
            response = self.client_get(
                f"{self.billing_session.billing_base_url}/billing/", subdomain="selfhosting"
            )

        for substring in [
            "Zulip Basic",
            "Number of licenses",
            f"{paid_license_count}",
            "February 2, 2012",
            "Your plan will automatically renew on",
            f"${3.5 * paid_license_count - flat_discount // 100 * 1:,.2f}",
            "Visa ending in 4242",
            "Update card",
        ]:
            self.assert_in_response(substring, response)

        # Check minimum licenses is 0 after flat discounted months is over.
        customer.flat_discounted_months = 0
        customer.save(update_fields=["flat_discounted_months"])
        self.assertEqual(
            self.billing_session.min_licenses_for_plan(CustomerPlan.TIER_SELF_HOSTED_BASIC), 1
        )

    @responses.activate
    @mock_stripe()
    def test_stripe_billing_portal_urls_for_remote_server(self, *mocks: Mock) -> None:
        self.login("hamlet")
        hamlet = self.example_user("hamlet")

        self.add_mock_response()
        with time_machine.travel(self.now, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)

        self.execute_remote_billing_authentication_flow(hamlet.delivery_email, hamlet.full_name)
        self.add_card_and_upgrade()

        response = self.client_get(
            f"{self.billing_session.billing_base_url}/invoices/", subdomain="selfhosting"
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith("https://billing.stripe.com/"))

        response = self.client_get(
            f"{self.billing_session.billing_base_url}/customer_portal/?return_to_billing_page=true",
            subdomain="selfhosting",
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith("https://billing.stripe.com/"))

    @responses.activate
    @mock_stripe()
    def test_upgrade_server_to_fixed_price_monthly_basic_plan(self, *mocks: Mock) -> None:
        self.login("iago")

        self.add_mock_response()
        with time_machine.travel(self.now, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)

        self.assertFalse(CustomerPlanOffer.objects.exists())

        # Configure required_plan_tier and fixed_price.
        annual_fixed_price = 1200
        result = self.client_post(
            "/activity/remote/support",
            {
                "remote_server_id": f"{self.remote_server.id}",
                "required_plan_tier": CustomerPlan.TIER_SELF_HOSTED_BASIC,
            },
        )
        self.assert_in_success_response(
            ["Required plan tier for demo.example.com set to Zulip Basic."], result
        )

        result = self.client_post(
            "/activity/remote/support",
            {"remote_server_id": f"{self.remote_server.id}", "fixed_price": annual_fixed_price},
        )
        self.assert_in_success_response(
            ["Customer can now buy a fixed price Zulip Basic plan."], result
        )
        fixed_price_plan_offer = CustomerPlanOffer.objects.filter(
            status=CustomerPlanOffer.CONFIGURED
        ).first()
        assert fixed_price_plan_offer is not None
        self.assertEqual(fixed_price_plan_offer.tier, CustomerPlanOffer.TIER_SELF_HOSTED_BASIC)
        self.assertEqual(fixed_price_plan_offer.fixed_price, annual_fixed_price * 100)

        self.logout()
        self.login("hamlet")
        hamlet = self.example_user("hamlet")

        # Visit /upgrade
        self.execute_remote_billing_authentication_flow(hamlet.delivery_email, hamlet.full_name)
        with time_machine.travel(self.now, tick=False):
            result = self.client_get(
                f"{self.billing_session.billing_base_url}/upgrade/?tier={CustomerPlan.TIER_SELF_HOSTED_BASIC}",
                subdomain="selfhosting",
            )
        self.assertEqual(result.status_code, 200)
        self.assert_in_success_response(
            ["Add card", "Purchase Zulip Basic", "This is a fixed-price plan."], result
        )

        self.assertFalse(CustomerPlan.objects.filter(status=CustomerPlan.ACTIVE).exists())

        # Upgrade to fixed-price Zulip Basic plan.
        with time_machine.travel(self.now, tick=False):
            stripe_customer = self.add_card_and_upgrade(
                tier=CustomerPlan.TIER_SELF_HOSTED_BASIC, schedule="monthly"
            )

        customer = Customer.objects.get(stripe_customer_id=stripe_customer.id)
        current_plan = CustomerPlan.objects.get(customer=customer, status=CustomerPlan.ACTIVE)
        self.assertIsNotNone(current_plan.fixed_price)
        self.assertIsNone(current_plan.price_per_license)
        fixed_price_plan_offer.refresh_from_db()
        self.assertEqual(fixed_price_plan_offer.status, CustomerPlanOffer.PROCESSED)

        # Visit /billing
        with time_machine.travel(self.now + timedelta(days=1), tick=False):
            response = self.client_get(
                f"{self.billing_session.billing_base_url}/billing/", subdomain="selfhosting"
            )
        for substring in [
            "Zulip Basic",
            "Monthly",
            "February 2, 2012",
            "This is a fixed-price plan",
            "Your plan will automatically renew on",
            f"${int(annual_fixed_price / 12)}",
            "Visa ending in 4242",
            "Update card",
        ]:
            self.assert_in_response(substring, response)

        # Since fixed-price plans do not depend on license counts for the
        # amount due, we invoice them even if the audit log data is stale
        # from the server.
        last_audit_log_update = self.now + timedelta(days=5)
        with time_machine.travel(last_audit_log_update, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)
        invoice_plans_as_needed(self.next_month)
        current_plan.refresh_from_db()
        updated_invoice_date = self.next_month + timedelta(days=29)
        self.assertEqual(current_plan.next_invoice_date, updated_invoice_date)
        self.assertFalse(current_plan.stale_audit_log_data_email_sent)

        from django.core.mail import outbox

        message = outbox[-1]
        self.assert_length(message.to, 1)
        self.assertEqual(message.to[0], "sales@zulip.com")
        self.assertEqual(
            message.subject,
            f"Stale audit log data for {self.billing_session.billing_entity_display_name}'s plan",
        )
        self.assertIn(
            f"Support URL: {self.billing_session.support_url()}",
            message.body,
        )
        self.assertIn(
            f"Internal billing notice for {self.billing_session.billing_entity_display_name}.",
            message.body,
        )
        self.assertIn(
            "Unable to verify current licenses in use, but invoicing not delayed because customer has a fixed-price plan.",
            message.body,
        )
        self.assertIn(f"Last data upload: {last_audit_log_update.date().isoformat()}", message.body)

        # Audit log data is up-to-date when the plan is next invoiced.
        with time_machine.travel(updated_invoice_date, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)
        invoice_plans_as_needed(updated_invoice_date)
        current_plan.refresh_from_db()
        final_invoice_date = updated_invoice_date + timedelta(days=31)
        self.assertEqual(current_plan.next_invoice_date, final_invoice_date)
        self.assertFalse(current_plan.stale_audit_log_data_email_sent)

    @responses.activate
    @mock_stripe()
    def test_upgrade_server_to_fixed_price_plan_pay_by_invoice(self, *mocks: Mock) -> None:
        self.login("iago")

        self.add_mock_response()
        with time_machine.travel(self.now, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)

        self.assertFalse(CustomerPlanOffer.objects.exists())

        # Configure required_plan_tier.
        result = self.client_post(
            "/activity/remote/support",
            {
                "remote_server_id": f"{self.remote_server.id}",
                "required_plan_tier": CustomerPlan.TIER_SELF_HOSTED_BASIC,
            },
        )
        self.assert_in_success_response(
            ["Required plan tier for demo.example.com set to Zulip Basic."], result
        )

        # Configure fixed-price plan with ID of manually sent invoice.
        hamlet = self.example_user("hamlet")
        sent_invoice_id = "test_sent_invoice_id"
        stripe_customer_id = "cus_123"
        annual_fixed_price = 1200
        mock_invoice = MagicMock()
        mock_invoice.status = "open"
        mock_invoice.sent_invoice_id = sent_invoice_id
        with (
            patch(
                "stripe.Customer.retrieve",
                return_value=Mock(id=stripe_customer_id, email=hamlet.delivery_email),
            ),
            patch("stripe.Invoice.retrieve", return_value=mock_invoice),
        ):
            result = self.client_post(
                "/activity/remote/support",
                {
                    "remote_server_id": f"{self.remote_server.id}",
                    "fixed_price": annual_fixed_price,
                    "sent_invoice_id": sent_invoice_id,
                },
            )
        self.assert_in_success_response(
            ["Customer can now buy a fixed price Zulip Basic plan."], result
        )
        fixed_price_plan_offer = CustomerPlanOffer.objects.filter(
            status=CustomerPlanOffer.CONFIGURED
        ).first()
        assert fixed_price_plan_offer is not None
        self.assertEqual(fixed_price_plan_offer.tier, CustomerPlanOffer.TIER_SELF_HOSTED_BASIC)
        self.assertEqual(fixed_price_plan_offer.fixed_price, annual_fixed_price * 100)
        self.assertEqual(fixed_price_plan_offer.sent_invoice_id, sent_invoice_id)
        self.assertEqual(fixed_price_plan_offer.get_plan_status_as_text(), "Configured")

        audit_log = RemoteZulipServerAuditLog.objects.filter(
            server=self.server,
            event_type=AuditLogEventType.CUSTOMER_PROPERTY_CHANGED,
        ).last()
        assert audit_log is not None
        self.assertEqual(audit_log.server, self.server)
        self.assertIsNone(audit_log.extra_data["old_value"])
        self.assertEqual(audit_log.extra_data["property"], "stripe_customer_id")

        invoice = Invoice.objects.get(stripe_invoice_id=sent_invoice_id)
        self.assertEqual(invoice.status, Invoice.SENT)

        self.logout()
        self.login("hamlet")

        # Customer don't need to visit /upgrade to buy plan.
        # In case they visit, we inform them about the mail to which
        # invoice was sent and also display the link for payment.
        self.execute_remote_billing_authentication_flow(hamlet.delivery_email, hamlet.full_name)
        mock_invoice = MagicMock()
        mock_invoice.hosted_invoice_url = "payments_page_url"
        with (
            time_machine.travel(self.now, tick=False),
            patch(
                "corporate.lib.stripe.customer_has_credit_card_as_default_payment_method",
                return_value=False,
            ),
            patch(
                "stripe.Customer.retrieve",
                return_value=Mock(id=stripe_customer_id, email=hamlet.delivery_email),
            ),
            patch("stripe.Invoice.retrieve", return_value=mock_invoice),
        ):
            result = self.client_get(
                f"{self.billing_session.billing_base_url}/upgrade/?tier={CustomerPlan.TIER_SELF_HOSTED_BASIC}",
                subdomain="selfhosting",
            )
        self.assertEqual(result.status_code, 200)
        self.assert_in_success_response(["payments_page_url", hamlet.delivery_email], result)

        # When customer makes a payment, 'stripe_webhook' handles 'invoice.paid' event.
        stripe_event_id = "stripe_event_id"
        valid_invoice_paid_event_data = {
            "id": stripe_event_id,
            "type": "invoice.paid",
            "api_version": STRIPE_API_VERSION,
            "data": {
                "object": {
                    "object": "invoice",
                    "id": sent_invoice_id,
                    "collection_method": "send_invoice",
                }
            },
        }
        with time_machine.travel(self.now, tick=False):
            result = self.client_post(
                "/stripe/webhook/",
                valid_invoice_paid_event_data,
                content_type="application/json",
            )
            self.assertEqual(result.status_code, 200)

        # Verify that the customer is upgraded after payment.
        customer = self.billing_session.get_customer()
        current_plan = CustomerPlan.objects.get(customer=customer, status=CustomerPlan.ACTIVE)
        self.assertEqual(current_plan.fixed_price, annual_fixed_price * 100)
        self.assertIsNone(current_plan.price_per_license)

        invoice.refresh_from_db()
        fixed_price_plan_offer.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.PAID)
        self.assertEqual(fixed_price_plan_offer.status, CustomerPlanOffer.PROCESSED)

        # Visit /billing
        self.execute_remote_billing_authentication_flow(
            hamlet.delivery_email, hamlet.full_name, expect_tos=False
        )
        with (
            time_machine.travel(self.now + timedelta(days=1), tick=False),
            patch(
                "corporate.lib.stripe.customer_has_credit_card_as_default_payment_method",
                return_value=False,
            ),
            patch(
                "stripe.Customer.retrieve",
                return_value=Mock(id=stripe_customer_id, email=hamlet.delivery_email),
            ),
            patch("stripe.Invoice.retrieve", return_value=mock_invoice),
        ):
            response = self.client_get(
                f"{self.billing_session.billing_base_url}/billing/", subdomain="selfhosting"
            )
        for substring in [
            "Zulip Basic",
            hamlet.delivery_email,
            "Annual",
            "This is a fixed-price plan",
            "You will be contacted by Zulip Sales",
        ]:
            self.assert_in_response(substring, response)

    @responses.activate
    @mock_stripe()
    def test_schedule_server_upgrade_to_fixed_price_business_plan(self, *mocks: Mock) -> None:
        self.login("hamlet")
        hamlet = self.example_user("hamlet")

        self.add_mock_response()
        with time_machine.travel(self.now, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)

        # Upgrade to fixed-price Zulip Basic plan.
        self.execute_remote_billing_authentication_flow(hamlet.delivery_email, hamlet.full_name)
        with time_machine.travel(self.now, tick=False):
            stripe_customer = self.add_card_and_upgrade(
                tier=CustomerPlan.TIER_SELF_HOSTED_BASIC,
            )

        customer = Customer.objects.get(stripe_customer_id=stripe_customer.id)
        assert customer.remote_server is not None
        self.assertEqual(customer.remote_server.plan_type, RemoteZulipServer.PLAN_TYPE_BASIC)
        current_plan = CustomerPlan.objects.get(customer=customer, status=CustomerPlan.ACTIVE)
        self.assertEqual(current_plan.tier, CustomerPlan.TIER_SELF_HOSTED_BASIC)
        self.assertIsNone(current_plan.fixed_price)
        self.assertIsNotNone(current_plan.price_per_license)

        self.logout()
        self.login("iago")

        # Schedule a fixed-price business plan at current plan end_date.
        current_plan_end_date = add_months(self.now, 2)
        current_plan.end_date = current_plan_end_date
        current_plan.save(update_fields=["end_date"])

        self.assertFalse(CustomerPlan.objects.filter(fixed_price__isnull=False).exists())

        # Configure required_plan_tier and fixed_price.
        annual_fixed_price = 1200
        result = self.client_post(
            "/activity/remote/support",
            {
                "remote_server_id": f"{self.remote_server.id}",
                "required_plan_tier": CustomerPlan.TIER_SELF_HOSTED_BUSINESS,
            },
        )
        self.assert_in_success_response(
            ["Required plan tier for demo.example.com set to Zulip Business."], result
        )

        result = self.client_post(
            "/activity/remote/support",
            {"remote_server_id": f"{self.remote_server.id}", "fixed_price": annual_fixed_price},
        )
        self.assert_in_success_response(
            [
                f"Fixed price Zulip Business plan scheduled to start on {current_plan_end_date.date()}."
            ],
            result,
        )
        current_plan.refresh_from_db()
        self.assertEqual(current_plan.status, CustomerPlan.SWITCH_PLAN_TIER_AT_PLAN_END)
        self.assertEqual(current_plan.next_invoice_date, current_plan_end_date)
        new_plan = CustomerPlan.objects.filter(fixed_price__isnull=False).first()
        assert new_plan is not None
        self.assertEqual(new_plan.next_invoice_date, current_plan_end_date)
        self.assertEqual(
            new_plan.invoicing_status, CustomerPlan.INVOICING_STATUS_INITIAL_INVOICE_TO_BE_SENT
        )

        # Invoice cron runs and switches plan to BUSINESS
        with time_machine.travel(current_plan_end_date, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)
            invoice_plans_as_needed()

        current_plan.refresh_from_db()
        self.assertEqual(current_plan.status, CustomerPlan.ENDED)
        self.assertEqual(current_plan.next_invoice_date, None)

        new_plan.refresh_from_db()
        self.assertEqual(new_plan.tier, CustomerPlan.TIER_SELF_HOSTED_BUSINESS)
        self.assertIsNotNone(new_plan.fixed_price)
        self.assertIsNone(new_plan.price_per_license)

        customer.refresh_from_db()
        self.assertEqual(customer.remote_server.plan_type, RemoteZulipServer.PLAN_TYPE_BUSINESS)

        self.logout()
        self.login("hamlet")
        hamlet = self.example_user("hamlet")

        # Visit /billing
        self.execute_remote_billing_authentication_flow(
            hamlet.delivery_email, hamlet.full_name, expect_tos=False, confirm_tos=False
        )
        with time_machine.travel(current_plan_end_date + timedelta(days=1), tick=False):
            response = self.client_get(
                f"{self.billing_session.billing_base_url}/billing/", subdomain="selfhosting"
            )
        for substring in [
            "Zulip Business",
            "Annual",
            "March 2, 2013",
            "This is a fixed-price plan",
            "Your plan ends on <strong>March 2, 2013</strong>",
            "You will be contacted by Zulip Sales",
            "Visa ending in 4242",
            "Update card",
        ]:
            self.assert_in_response(substring, response)

    @responses.activate
    @mock_stripe()
    def test_schedule_server_complimentary_access_plan_upgrade_to_fixed_price_plan(
        self, *mocks: Mock
    ) -> None:
        self.login("hamlet")
        hamlet = self.example_user("hamlet")

        # Create complimentary access plan for server.
        end_date = add_months(self.now, months=3)
        self.billing_session.create_complimentary_access_plan(self.now, end_date)

        self.add_mock_response()
        with time_machine.travel(self.now, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)

        customer = self.billing_session.get_customer()
        assert customer is not None
        complimentary_access_plan = get_current_plan_by_customer(customer)
        assert complimentary_access_plan is not None
        self.assertEqual(complimentary_access_plan.tier, CustomerPlan.TIER_SELF_HOSTED_LEGACY)
        self.assertEqual(complimentary_access_plan.next_invoice_date, end_date)

        self.logout()
        self.login("iago")

        # Schedule a fixed-price business plan at current plan end_date.
        self.assertFalse(CustomerPlanOffer.objects.exists())

        # Configure required_plan_tier and fixed_price.
        annual_fixed_price = 1200
        result = self.client_post(
            "/activity/remote/support",
            {
                "remote_server_id": f"{self.remote_server.id}",
                "required_plan_tier": CustomerPlan.TIER_SELF_HOSTED_BUSINESS,
            },
        )
        self.assert_in_success_response(
            ["Required plan tier for demo.example.com set to Zulip Business."], result
        )

        result = self.client_post(
            "/activity/remote/support",
            {"remote_server_id": f"{self.remote_server.id}", "fixed_price": annual_fixed_price},
        )
        self.assert_in_success_response(
            ["Customer can now buy a fixed price Zulip Business plan."],
            result,
        )
        fixed_price_plan_offer = CustomerPlanOffer.objects.get(customer=customer)
        self.assertEqual(fixed_price_plan_offer.status, CustomerPlanOffer.CONFIGURED)
        self.assertEqual(fixed_price_plan_offer.tier, CustomerPlanOffer.TIER_SELF_HOSTED_BUSINESS)

        self.logout()
        self.login("hamlet")
        self.execute_remote_billing_authentication_flow(hamlet.delivery_email, hamlet.full_name)

        # Schedule upgrade to business plan
        with time_machine.travel(self.now, tick=False):
            self.add_card_and_upgrade(
                remote_server_plan_start_date="billing_cycle_end_date", talk_to_stripe=False
            )

        complimentary_access_plan.refresh_from_db()
        self.assertEqual(
            complimentary_access_plan.status, CustomerPlan.SWITCH_PLAN_TIER_AT_PLAN_END
        )
        fixed_price_plan_offer.refresh_from_db()
        self.assertEqual(fixed_price_plan_offer.status, CustomerPlanOffer.PROCESSED)

        # Invoice cron runs and switches plan to BUSINESS
        with time_machine.travel(end_date, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)
            invoice_plans_as_needed()

        complimentary_access_plan.refresh_from_db()
        current_plan = get_current_plan_by_customer(customer)
        assert current_plan is not None
        self.assertEqual(current_plan.tier, CustomerPlan.TIER_SELF_HOSTED_BUSINESS)
        self.assertIsNotNone(current_plan.fixed_price)
        self.assertIsNone(current_plan.price_per_license)
        self.assertEqual(current_plan.next_invoice_date, add_months(end_date, 1))
        self.assertEqual(complimentary_access_plan.status, CustomerPlan.ENDED)
        self.assertEqual(complimentary_access_plan.next_invoice_date, None)

    def test_deactivate_registration_with_push_notification_service(self) -> None:
        self.login("hamlet")
        hamlet = self.example_user("hamlet")
        billing_base_url = self.billing_session.billing_base_url

        # Get server deactivation confirmation link
        with self.settings(EXTERNAL_HOST="zulipdev.com:9991"):
            confirmation_link = generate_confirmation_link_for_server_deactivation(
                self.remote_server, 10
            )

        # confirmation link takes user to login page
        result = self.client_get(confirmation_link, subdomain="selfhosting")
        self.assertEqual(result.status_code, 200)
        self.assert_in_success_response(["Log in to deactivate registration for"], result)

        # Login redirects to '/deactivate'
        result = self.client_post(
            confirmation_link,
            {"full_name": hamlet.full_name, "tos_consent": "true"},
            subdomain="selfhosting",
        )
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], f"{billing_base_url}/deactivate/")

        # Deactivate via UI
        result = self.client_get(f"{billing_base_url}/deactivate/", subdomain="selfhosting")
        self.assertEqual(result.status_code, 200)
        self.assert_in_success_response(
            ["Deactivate registration for", "Deactivate registration"], result
        )

        result = self.client_post(
            f"{billing_base_url}/deactivate/", {"confirmed": "true"}, subdomain="selfhosting"
        )
        self.assertEqual(result.status_code, 200)
        self.assert_in_success_response(
            ["Registration deactivated for", "Your server's registration has been deactivated."],
            result,
        )

        # Verify login fails
        payload = {
            "zulip_org_id": self.remote_server.uuid,
            "zulip_org_key": self.remote_server.api_key,
        }
        result = self.client_post("/serverlogin/", payload, subdomain="selfhosting")
        self.assertEqual(result.status_code, 200)
        self.assert_in_success_response(["Your server registration has been deactivated."], result)

    @responses.activate
    @mock_stripe()
    def test_invoice_initial_remote_server_upgrade(self, *mocks: Mock) -> None:
        self.login("hamlet")
        hamlet = self.example_user("hamlet")

        server_user_count = UserProfile.objects.filter(is_bot=False, is_active=True).count()

        self.add_mock_response()
        with time_machine.travel(self.now, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)

        self.execute_remote_billing_authentication_flow(hamlet.delivery_email, hamlet.full_name)
        with time_machine.travel(self.now, tick=False):
            stripe_customer = self.add_card_and_upgrade(
                tier=CustomerPlan.TIER_SELF_HOSTED_BASIC, schedule="monthly"
            )

        [invoice0] = iter(stripe.Invoice.list(customer=stripe_customer.id))

        [invoice_item0, invoice_item1] = iter(invoice0.lines)
        self.assertEqual(invoice_item0.amount, -2000)
        self.assertEqual(invoice_item0.description, "$20.00/month new customer discount")
        self.assertEqual(invoice_item0.quantity, 1)

        self.assertEqual(invoice_item1.amount, server_user_count * 3.5 * 100)
        self.assertEqual(invoice_item1.description, "Zulip Basic")
        self.assertEqual(invoice_item1.quantity, server_user_count)

        self.assertEqual(invoice0.amount_due, server_user_count * 3.5 * 100 - 2000)
        self.assertEqual(invoice0.status, "paid")

    @responses.activate
    @mock_stripe()
    def test_invoice_plans_as_needed_server(self, *mocks: Mock) -> None:
        self.login("hamlet")
        hamlet = self.example_user("hamlet")

        server_user_count = UserProfile.objects.filter(is_bot=False, is_active=True).count()

        self.add_mock_response()
        with time_machine.travel(self.now, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)

        self.execute_remote_billing_authentication_flow(hamlet.delivery_email, hamlet.full_name)
        with time_machine.travel(self.now, tick=False):
            stripe_customer = self.add_card_and_upgrade(
                tier=CustomerPlan.TIER_SELF_HOSTED_BASIC, schedule="monthly"
            )

        customer = Customer.objects.get(stripe_customer_id=stripe_customer.id)
        plan = CustomerPlan.objects.get(customer=customer)
        assert plan.customer.remote_server is not None
        self.assertEqual(plan.next_invoice_date, self.next_month)

        with time_machine.travel(self.now + timedelta(days=2), tick=False):
            for count in range(5):
                do_create_user(
                    f"email - {count}",
                    f"password {count}",
                    hamlet.realm,
                    "name",
                    role=UserProfile.ROLE_MEMBER,
                    acting_user=None,
                )
            server_user_count += 5

        # Data upload was 25 days before the invoice date.
        last_audit_log_upload = self.now + timedelta(days=5)
        with time_machine.travel(last_audit_log_upload, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)
        invoice_plans_as_needed(self.next_month)
        plan.refresh_from_db()
        self.assertEqual(plan.next_invoice_date, self.next_month)
        self.assertTrue(plan.stale_audit_log_data_email_sent)

        from django.core.mail import outbox

        messages_count = len(outbox)
        message = outbox[-1]
        self.assert_length(message.to, 1)
        self.assertEqual(message.to[0], "sales@zulip.com")
        self.assertEqual(
            message.subject,
            f"Stale audit log data for {self.billing_session.billing_entity_display_name}'s plan",
        )
        self.assertIn(
            f"Support URL: {self.billing_session.support_url()}",
            message.body,
        )
        self.assertIn(
            f"Internal billing notice for {self.billing_session.billing_entity_display_name}.",
            message.body,
        )
        self.assertIn(
            "Unable to verify current licenses in use, which delays invoicing for this customer.",
            message.body,
        )
        self.assertIn(f"Last data upload: {last_audit_log_upload.date().isoformat()}", message.body)

        # Cron runs again, don't send another email to Zulip team.
        invoice_plans_as_needed(self.next_month + timedelta(days=1))
        self.assert_length(outbox, messages_count)

        # Ledger is up-to-date
        with time_machine.travel(self.next_month, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)
        invoice_plans_as_needed(self.next_month)
        plan.refresh_from_db()
        self.assertEqual(plan.next_invoice_date, add_months(self.next_month, 1))
        self.assertFalse(plan.stale_audit_log_data_email_sent)

        assert customer.stripe_customer_id
        [invoice0, _invoice1] = iter(stripe.Invoice.list(customer=customer.stripe_customer_id))

        [_invoice_item0, invoice_item1, invoice_item2] = iter(invoice0.lines)
        self.assertEqual(invoice_item2.amount, server_user_count * 3.5 * 100)
        self.assertEqual(invoice_item2.description, "Zulip Basic - renewal")
        self.assertEqual(invoice_item2.quantity, server_user_count)
        self.assertEqual(invoice_item2.period.start, datetime_to_timestamp(self.next_month))
        self.assertEqual(
            invoice_item2.period.end, datetime_to_timestamp(add_months(self.next_month, 1))
        )

        self.assertEqual(invoice_item1.description, "Additional Zulip Basic license")
        self.assertEqual(invoice_item1.quantity, 5)
        self.assertEqual(
            invoice_item1.period.start, datetime_to_timestamp(self.now + timedelta(days=2))
        )
        self.assertEqual(invoice_item1.period.end, datetime_to_timestamp(self.next_month))

        # Verify Zulip team receives mail for the next cycle.
        invoice_plans_as_needed(add_months(self.next_month, 1))
        self.assert_length(outbox, messages_count + 1)

    @responses.activate
    def test_complimentary_access_plan_ends_on_plan_end_date(self, *mocks: Mock) -> None:
        self.login("hamlet")

        self.add_mock_response()
        with time_machine.travel(self.now, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)

        plan_end_date = add_months(self.now, 3)
        self.billing_session.create_complimentary_access_plan(self.now, plan_end_date)

        # Complimentary access plan ends on plan end date.
        customer = self.billing_session.get_customer()
        assert customer is not None
        plan = get_current_plan_by_customer(customer)
        assert plan is not None
        self.assertEqual(plan.end_date, plan_end_date)
        self.assertEqual(plan.next_invoice_date, plan_end_date)
        self.assertEqual(plan.status, CustomerPlan.ACTIVE)
        self.assertEqual(
            self.remote_server.plan_type, RemoteZulipServer.PLAN_TYPE_SELF_MANAGED_LEGACY
        )

        with (
            mock.patch("stripe.Invoice.create") as invoice_create,
            mock.patch("corporate.lib.stripe.send_email") as send_email,
            time_machine.travel(plan_end_date, tick=False),
        ):
            invoice_plans_as_needed()
            # Verify that for complimentary access plan with no next plan scheduled,
            # invoice overdue email is not sent even if the last audit log update was
            # 3 months ago.
            send_email.assert_not_called()
            # The complimentary access plan is downgraded, no invoice created.
            invoice_create.assert_not_called()

        plan.refresh_from_db()
        self.remote_server.refresh_from_db()
        self.assertEqual(self.remote_server.plan_type, RemoteZulipServer.PLAN_TYPE_SELF_MANAGED)
        self.assertEqual(plan.next_invoice_date, None)
        self.assertEqual(plan.status, CustomerPlan.ENDED)

    @responses.activate
    @mock_stripe()
    def test_invoice_scheduled_upgrade_server_complimentary_access_plan(self, *mocks: Mock) -> None:
        # Upload data
        self.add_mock_response()
        with time_machine.travel(self.now, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)

        # Create complimentary access plan for server.
        with time_machine.travel(self.now, tick=False):
            start_date = timezone_now()
            end_date = add_months(start_date, months=3)
            self.billing_session.create_complimentary_access_plan(start_date, end_date)

        customer = self.billing_session.get_customer()
        assert customer is not None
        complimentary_access_plan = get_current_plan_by_customer(customer)
        assert complimentary_access_plan is not None
        self.assertEqual(complimentary_access_plan.tier, CustomerPlan.TIER_SELF_HOSTED_LEGACY)
        self.assertEqual(complimentary_access_plan.status, CustomerPlan.ACTIVE)
        self.assertEqual(complimentary_access_plan.next_invoice_date, end_date)

        self.login("hamlet")
        hamlet = self.example_user("hamlet")

        self.execute_remote_billing_authentication_flow(hamlet.delivery_email, hamlet.full_name)
        # Add card and schedule upgrade
        with time_machine.travel(self.now, tick=False):
            stripe_customer = self.add_card_and_upgrade(
                remote_server_plan_start_date="billing_cycle_end_date", talk_to_stripe=False
            )
        complimentary_access_plan.refresh_from_db()
        self.assertEqual(
            complimentary_access_plan.status, CustomerPlan.SWITCH_PLAN_TIER_AT_PLAN_END
        )
        new_plan = self.billing_session.get_next_plan(complimentary_access_plan)
        assert new_plan is not None
        self.assertEqual(new_plan.tier, CustomerPlan.TIER_SELF_HOSTED_BUSINESS)
        self.assertEqual(new_plan.status, CustomerPlan.NEVER_STARTED)
        self.assertEqual(
            new_plan.invoicing_status,
            CustomerPlan.INVOICING_STATUS_INITIAL_INVOICE_TO_BE_SENT,
        )
        self.assertEqual(new_plan.next_invoice_date, end_date)
        self.assertEqual(new_plan.billing_cycle_anchor, end_date)

        server_user_count = UserProfile.objects.filter(is_bot=False, is_active=True).count()
        min_licenses = self.billing_session.min_licenses_for_plan(
            CustomerPlan.TIER_SELF_HOSTED_BUSINESS
        )
        licenses = max(min_licenses, server_user_count)

        with (
            mock.patch("stripe.Invoice.finalize_invoice") as invoice_create,
            mock.patch("corporate.lib.stripe.send_email") as send_email,
            time_machine.travel(end_date, tick=False),
        ):
            invoice_plans_as_needed()
            # Verify that for complimentary access plan with next plan scheduled,
            # invoice overdue email is sent if the last audit log is stale.
            send_email.assert_called()
            invoice_create.assert_not_called()

        with time_machine.travel(end_date, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)
            invoice_plans_as_needed()
            # 'invoice_plan()' is called with both complimentary access & new plan, but
            # invoice is created only for new plan. The complimentary access plan only
            # goes through the end of cycle updates.

        complimentary_access_plan.refresh_from_db()
        new_plan.refresh_from_db()
        self.assertEqual(complimentary_access_plan.status, CustomerPlan.ENDED)
        self.assertEqual(complimentary_access_plan.next_invoice_date, None)
        self.assertEqual(new_plan.status, CustomerPlan.ACTIVE)
        self.assertEqual(new_plan.invoicing_status, CustomerPlan.INVOICING_STATUS_DONE)
        self.assertEqual(new_plan.next_invoice_date, add_months(end_date, 1))

        [invoice0] = iter(stripe.Invoice.list(customer=stripe_customer.id))

        [invoice_item0, invoice_item1] = iter(invoice0.lines)
        self.assertEqual(invoice_item0.amount, -2000 * 12)
        self.assertEqual(invoice_item0.description, "$20.00/month new customer discount")
        self.assertEqual(invoice_item0.quantity, 1)

        self.assertEqual(invoice_item1.amount, licenses * 80 * 100)
        self.assertEqual(invoice_item1.description, "Zulip Business - renewal")
        self.assertEqual(invoice_item1.quantity, licenses)
