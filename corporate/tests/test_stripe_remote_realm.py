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
    RemoteRealmBillingSession,
    RemoteServerBillingSession,
    SupportType,
    SupportViewRequest,
    add_months,
    invoice_plans_as_needed,
)
from corporate.lib.test_stripe_class import StripeTestCase, mock_stripe
from corporate.models.customers import Customer, get_customer_by_remote_realm
from corporate.models.licenses import LicenseLedger
from corporate.models.plans import CustomerPlan, CustomerPlanOffer, get_current_plan_by_customer
from corporate.models.stripe_state import Invoice
from corporate.tests.test_remote_billing import RemoteRealmBillingTestCase
from zerver.actions.create_user import do_create_user
from zerver.lib.remote_server import send_server_data_to_push_bouncer
from zerver.lib.test_helpers import activate_push_notification_service
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.models import Realm, RealmAuditLog, UserProfile
from zerver.models.realm_audit_logs import AuditLogEventType
from zerver.models.realms import get_realm
from zilencer.lib.remote_counts import MissingDataError
from zilencer.models import RemoteRealm, RemoteRealmAuditLog, RemoteZulipServer


class TestRemoteRealmBillingSession(StripeTestCase):
    def test_current_counts_for_billed_users(self) -> None:
        server_uuid = str(uuid.uuid4())
        remote_server = RemoteZulipServer.objects.create(
            uuid=server_uuid,
            api_key="magic_secret_api_key",
            hostname="demo.example.com",
            contact_email="email@example.com",
        )
        realm_uuid = str(uuid.uuid4())
        remote_realm = RemoteRealm.objects.create(
            server=remote_server,
            uuid=realm_uuid,
            uuid_owner_secret="dummy-owner-secret",
            host="dummy-hostname",
            realm_date_created=timezone_now(),
        )
        billing_session = RemoteRealmBillingSession(remote_realm=remote_realm)

        # remote server never uploaded statistics. 'last_audit_log_update' is None.
        with self.assertRaises(MissingDataError):
            billing_session.current_counts_for_billed_users()

        # Available statistics is stale.
        remote_server.last_audit_log_update = timezone_now() - timedelta(days=5)
        remote_server.save()
        with self.assertRaises(MissingDataError):
            billing_session.current_counts_for_billed_users()

        # Available statistics is not stale.
        event_time = timezone_now() - timedelta(days=1)
        data_list = [
            {
                "server": remote_server,
                "remote_realm": remote_realm,
                "event_type": AuditLogEventType.USER_CREATED,
                "event_time": event_time,
                "extra_data": {
                    RemoteRealmAuditLog.ROLE_COUNT: {
                        RemoteRealmAuditLog.ROLE_COUNT_HUMANS: {
                            UserProfile.ROLE_REALM_ADMINISTRATOR: 10,
                            UserProfile.ROLE_REALM_OWNER: 10,
                            UserProfile.ROLE_MODERATOR: 10,
                            UserProfile.ROLE_MEMBER: 10,
                            UserProfile.ROLE_GUEST: 10,
                        }
                    }
                },
            },
            {
                "server": remote_server,
                "remote_realm": remote_realm,
                "event_type": AuditLogEventType.USER_ROLE_CHANGED,
                "event_time": event_time,
                "extra_data": {
                    RemoteRealmAuditLog.ROLE_COUNT: {
                        RemoteRealmAuditLog.ROLE_COUNT_HUMANS: {
                            UserProfile.ROLE_REALM_ADMINISTRATOR: 20,
                            UserProfile.ROLE_REALM_OWNER: 10,
                            UserProfile.ROLE_MODERATOR: 0,
                            UserProfile.ROLE_MEMBER: 30,
                            UserProfile.ROLE_GUEST: 10,
                        }
                    }
                },
            },
        ]
        RemoteRealmAuditLog.objects.bulk_create([RemoteRealmAuditLog(**data) for data in data_list])
        remote_server.last_audit_log_update = timezone_now() - timedelta(days=1)
        remote_server.save()

        current_billed_user_counts = billing_session.current_counts_for_billed_users()
        self.assertEqual(current_billed_user_counts.workplace_users, 70)
        self.assertEqual(current_billed_user_counts.non_workplace_users, 0)


@activate_push_notification_service()
class TestRemoteRealmBillingFlow(StripeTestCase, RemoteRealmBillingTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()

        # Reset already created audit logs for this test as they have
        # event_time=timezone_now() that will affects the LicenseLedger
        # queries as their event_time would be more recent than other
        # operations we perform in this test.
        zulip_realm = get_realm("zulip")
        RealmAuditLog.objects.filter(
            realm=zulip_realm, event_type__in=RealmAuditLog.SYNCED_BILLING_EVENTS
        ).delete()
        with time_machine.travel(self.now, tick=False):
            for count in range(4):
                do_create_user(
                    f"email {count}",
                    f"password {count}",
                    zulip_realm,
                    "name",
                    acting_user=None,
                )

        self.remote_realm = RemoteRealm.objects.get(uuid=zulip_realm.uuid)
        self.billing_session = RemoteRealmBillingSession(remote_realm=self.remote_realm)

    @responses.activate
    @mock_stripe()
    def test_upgrade_user_to_business_plan(self, *mocks: Mock) -> None:
        self.login("hamlet")
        hamlet = self.example_user("hamlet")

        self.add_mock_response()
        realm_user_count = UserProfile.objects.filter(
            realm=hamlet.realm, is_bot=False, is_active=True
        ).count()
        self.assertEqual(realm_user_count, 11)

        with time_machine.travel(self.now, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)

        result = self.execute_remote_billing_authentication_flow(hamlet)
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], f"{self.billing_session.billing_base_url}/plans/")

        # upgrade to business plan
        with time_machine.travel(self.now, tick=False):
            result = self.client_get(
                f"{self.billing_session.billing_base_url}/upgrade/", subdomain="selfhosting"
            )
        self.assertEqual(result.status_code, 200)

        # Min licenses used since org has less users.
        min_licenses = self.billing_session.min_licenses_for_plan(
            CustomerPlan.TIER_SELF_HOSTED_BUSINESS
        )
        self.assertEqual(min_licenses, 25)
        _flat_discount, flat_discounted_months = self.billing_session.get_flat_discount_info()
        self.assertEqual(flat_discounted_months, 12)

        self.assert_in_success_response(
            [
                "Minimum purchase for",
                f"{min_licenses} licenses",
                "Add card",
                "Purchase Zulip Business",
            ],
            result,
        )

        # Same result even with free trial enabled for self hosted customers since we don't
        # offer free trial for business plan.
        with (
            self.settings(SELF_HOSTING_FREE_TRIAL_DAYS=30),
            time_machine.travel(self.now, tick=False),
        ):
            result = self.client_get(
                f"{self.billing_session.billing_base_url}/upgrade/", subdomain="selfhosting"
            )

        self.assert_in_success_response(
            [
                "Minimum purchase for",
                f"{min_licenses} licenses",
                "Add card",
                "Purchase Zulip Business",
            ],
            result,
        )

        # Check that cloud free trials don't affect self hosted customers.
        with self.settings(CLOUD_FREE_TRIAL_DAYS=30), time_machine.travel(self.now, tick=False):
            result = self.client_get(
                f"{self.billing_session.billing_base_url}/upgrade/", subdomain="selfhosting"
            )

        self.assert_in_success_response(
            [
                "Minimum purchase for",
                f"{min_licenses} licenses",
                "Add card",
                "Purchase Zulip Business",
            ],
            result,
        )

        self.assertFalse(Customer.objects.exists())
        self.assertFalse(CustomerPlan.objects.exists())
        self.assertFalse(LicenseLedger.objects.exists())

        with time_machine.travel(self.now, tick=False):
            stripe_customer = self.add_card_and_upgrade()

        customer = Customer.objects.get(stripe_customer_id=stripe_customer.id)
        plan = CustomerPlan.objects.get(customer=customer)
        LicenseLedger.objects.get(plan=plan)

        with time_machine.travel(self.now + timedelta(days=1), tick=False):
            response = self.client_get(
                f"{self.billing_session.billing_base_url}/billing/", subdomain="selfhosting"
            )
        for substring in [
            "Zulip Business",
            "Number of licenses",
            f"{min_licenses}",
            "January 2, 2013",
            "Your plan will automatically renew on",
            f"${80 * min_licenses:,.2f}",
            "Visa ending in 4242",
            "Update card",
        ]:
            self.assert_in_response(substring, response)

        # Verify that change in user count updates LicenseLedger.
        audit_log_count = RemoteRealmAuditLog.objects.count()
        self.assertEqual(LicenseLedger.objects.count(), 1)

        with time_machine.travel(self.now + timedelta(days=2), tick=False):
            for count in range(realm_user_count, min_licenses + 10):
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
            min_licenses + 10 - realm_user_count + audit_log_count,
        )
        paid_license_count = min_licenses + 10
        self.check_last_ledger_entry_license_counts(plan, paid_license_count, paid_license_count)

        with time_machine.travel(self.now + timedelta(days=3), tick=False):
            response = self.client_get(
                f"{self.billing_session.billing_base_url}/billing/", subdomain="selfhosting"
            )

        for substring in [
            "Zulip Business",
            "Number of licenses",
            f"{paid_license_count}",
            "January 2, 2013",
            "Your plan will automatically renew on",
            f"${80 * paid_license_count:,.2f}",
            "Visa ending in 4242",
            "Update card",
        ]:
            self.assert_in_response(substring, response)

    @responses.activate
    @mock_stripe()
    def test_stripe_billing_portal_urls_for_remote_realm(self, *mocks: Mock) -> None:
        self.login("hamlet")
        hamlet = self.example_user("hamlet")

        self.add_mock_response()
        with time_machine.travel(self.now, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)

        self.execute_remote_billing_authentication_flow(hamlet)
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
    def test_upgrade_user_to_basic_plan_free_trial_fails_special_case(self, *mocks: Mock) -> None:
        # Here we test if server had a complimentary access plan that ended before we could migrate
        # it to a remote realm resulting in the upgrade for remote realm creating a new customer which
        # doesn't have any complimentary access plan associated with it. In this case, a free trial
        # should not be offered.
        with self.settings(SELF_HOSTING_FREE_TRIAL_DAYS=30):
            self.login("hamlet")
            hamlet = self.example_user("hamlet")

            self.add_mock_response()
            with time_machine.travel(self.now, tick=False):
                send_server_data_to_push_bouncer(consider_usage_statistics=False)

            result = self.execute_remote_billing_authentication_flow(hamlet)
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result["Location"], f"{self.billing_session.billing_base_url}/plans/")

            # Test under normal circumstances it will show free trial.
            with time_machine.travel(self.now, tick=False):
                result = self.client_get(
                    f"{self.billing_session.billing_base_url}/upgrade/?tier={CustomerPlan.TIER_SELF_HOSTED_BASIC}",
                    subdomain="selfhosting",
                )

            self.assert_in_success_response(
                [
                    "Start free trial",
                    "Zulip Basic",
                    "Start 30-day free trial",
                ],
                result,
            )

            # Add ended complimentary access plan for remote realm server.
            new_server_customer = Customer.objects.create(remote_server=self.remote_realm.server)
            CustomerPlan.objects.create(
                customer=new_server_customer,
                status=CustomerPlan.ENDED,
                tier=CustomerPlan.TIER_SELF_HOSTED_LEGACY,
                billing_cycle_anchor=timezone_now(),
                billing_schedule=CustomerPlan.BILLING_SCHEDULE_ANNUAL,
            )

            # No longer eligible for free trial
            with time_machine.travel(self.now, tick=False):
                result = self.client_get(
                    f"{self.billing_session.billing_base_url}/upgrade/?tier={CustomerPlan.TIER_SELF_HOSTED_BASIC}",
                    subdomain="selfhosting",
                )

            self.assert_not_in_success_response(
                [
                    "Start free trial",
                    "Start 30-day free trial",
                ],
                result,
            )

            self.assert_in_success_response(
                [
                    "Purchase Zulip Basic",
                ],
                result,
            )

            result = self.client_get(
                f"{self.billing_session.billing_base_url}/plans/",
                subdomain="selfhosting",
            )

            self.assert_not_in_success_response(
                [
                    "Start 30-day free trial",
                ],
                result,
            )

    @responses.activate
    @mock_stripe()
    def test_upgrade_user_to_basic_plan_free_trial(self, *mocks: Mock) -> None:
        with self.settings(SELF_HOSTING_FREE_TRIAL_DAYS=30):
            self.login("hamlet")
            hamlet = self.example_user("hamlet")

            self.add_mock_response()
            realm_user_count = UserProfile.objects.filter(
                realm=hamlet.realm, is_bot=False, is_active=True
            ).count()
            self.assertEqual(realm_user_count, 11)

            with time_machine.travel(self.now, tick=False):
                send_server_data_to_push_bouncer(consider_usage_statistics=False)

            result = self.execute_remote_billing_authentication_flow(hamlet)
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
                for count in range(realm_user_count, min_licenses + 10):
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
                min_licenses + 10 - realm_user_count + audit_log_count,
            )
            paid_license_count = min_licenses + 10
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
    def test_redirect_for_remote_realm_billing_page_downgrade_at_free_trial_end(
        self, *mocks: Mock
    ) -> None:
        with self.settings(SELF_HOSTING_FREE_TRIAL_DAYS=30):
            self.login("hamlet")
            hamlet = self.example_user("hamlet")

            self.add_mock_response()
            with time_machine.travel(self.now, tick=False):
                send_server_data_to_push_bouncer(consider_usage_statistics=False)

            result = self.execute_remote_billing_authentication_flow(hamlet)
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
    def test_upgrade_remote_realm_user_to_monthly_basic_plan(self, *mocks: Mock) -> None:
        self.login("hamlet")
        hamlet = self.example_user("hamlet")

        self.add_mock_response()
        realm_user_count = UserProfile.objects.filter(
            realm=hamlet.realm, is_bot=False, is_active=True
        ).count()
        self.assertEqual(realm_user_count, 11)

        with time_machine.travel(self.now, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)

        result = self.execute_remote_billing_authentication_flow(hamlet)
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
            [f"{realm_user_count}", "Add card", "Purchase Zulip Basic"], result
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
            f"{realm_user_count}",
            "February 2, 2012",
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
            for count in range(realm_user_count, min_licenses + 10):
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
            min_licenses + 10 - realm_user_count + audit_log_count,
        )
        paid_license_count = min_licenses + 10
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
    def test_upgrade_user_to_fixed_price_monthly_basic_plan(self, *mocks: Mock) -> None:
        self.login("iago")

        self.add_mock_response()
        with time_machine.travel(self.now, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)

        self.assertFalse(CustomerPlanOffer.objects.exists())

        # Set fixed_price without configuring required_plan_tier.
        annual_fixed_price = 1200
        result = self.client_post(
            "/activity/remote/support",
            {"remote_realm_id": f"{self.remote_realm.id}", "fixed_price": annual_fixed_price},
        )
        self.assert_in_success_response(["Required plan tier should not be set to None"], result)

        # Configure required_plan_tier and fixed_price.
        result = self.client_post(
            "/activity/remote/support",
            {
                "remote_realm_id": f"{self.remote_realm.id}",
                "required_plan_tier": CustomerPlan.TIER_SELF_HOSTED_BASIC,
            },
        )
        self.assert_in_success_response(
            ["Required plan tier for Zulip Dev set to Zulip Basic."], result
        )

        result = self.client_post(
            "/activity/remote/support",
            {"remote_realm_id": f"{self.remote_realm.id}", "fixed_price": annual_fixed_price},
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
        self.assertEqual(fixed_price_plan_offer.get_plan_status_as_text(), "Configured")

        result = self.client_get("/activity/remote/support", {"q": "example.com"})
        self.assert_in_success_response(
            ["Next plan information:", "Zulip Basic", "Configured", "Plan has a fixed price."],
            result,
        )

        self.logout()
        self.login("hamlet")
        hamlet = self.example_user("hamlet")

        # Visit /upgrade
        self.execute_remote_billing_authentication_flow(hamlet)
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

    @responses.activate
    def test_delete_configured_fixed_price_plan_offer_no_active_plan(self) -> None:
        self.login("iago")

        self.add_mock_response()
        with time_machine.travel(self.now, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)

        self.assertFalse(CustomerPlanOffer.objects.exists())

        annual_fixed_price = 1200
        # Configure required_plan_tier and fixed_price.
        result = self.client_post(
            "/activity/remote/support",
            {
                "remote_realm_id": f"{self.remote_realm.id}",
                "required_plan_tier": CustomerPlan.TIER_SELF_HOSTED_BASIC,
            },
        )
        self.assert_in_success_response(
            ["Required plan tier for Zulip Dev set to Zulip Basic."], result
        )

        result = self.client_post(
            "/activity/remote/support",
            {"remote_realm_id": f"{self.remote_realm.id}", "fixed_price": annual_fixed_price},
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
        self.assertEqual(fixed_price_plan_offer.get_plan_status_as_text(), "Configured")

        result = self.client_get("/activity/remote/support", {"q": "example.com"})
        self.assert_in_success_response(
            ["Next plan information:", "Zulip Basic", "Configured", "Plan has a fixed price."],
            result,
        )

        billing_session = RemoteRealmBillingSession(remote_realm=self.remote_realm)
        support_request = SupportViewRequest(
            support_type=SupportType.delete_fixed_price_next_plan,
        )
        success_message = billing_session.process_support_view_request(support_request)
        self.assertEqual(success_message, "Fixed-price plan offer deleted")
        result = self.client_get("/activity/remote/support", {"q": "example.com"})
        self.assert_not_in_success_response(["Next plan information:"], result)
        self.assert_in_success_response(
            ["Configure fixed price plan", "Annual amount in dollars"], result
        )

    @responses.activate
    def test_delete_configured_fixed_price_plan_offer_on_complimentary_access_plan(self) -> None:
        self.login("iago")

        self.add_mock_response()
        with time_machine.travel(self.now, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)

        self.assertFalse(CustomerPlanOffer.objects.exists())
        annual_fixed_price = 1200

        # Configure complimentary access plan
        complimentary_access_plan_end = self.next_year.date().isoformat()
        billing_session = RemoteRealmBillingSession(remote_realm=self.remote_realm)
        support_request = SupportViewRequest(
            support_type=SupportType.configure_complimentary_access_plan,
            plan_end_date=complimentary_access_plan_end,
        )

        with time_machine.travel(self.now, tick=False):
            success_message = billing_session.process_support_view_request(support_request)
        self.assertEqual(
            success_message,
            f"Complimentary access plan for Zulip Dev configured to end on {complimentary_access_plan_end}.",
        )

        # Configure required_plan_tier and fixed_price.
        result = self.client_post(
            "/activity/remote/support",
            {
                "remote_realm_id": f"{self.remote_realm.id}",
                "required_plan_tier": CustomerPlan.TIER_SELF_HOSTED_BASIC,
            },
        )
        self.assert_in_success_response(
            ["Required plan tier for Zulip Dev set to Zulip Basic."], result
        )

        result = self.client_post(
            "/activity/remote/support",
            {"remote_realm_id": f"{self.remote_realm.id}", "fixed_price": annual_fixed_price},
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
        self.assertEqual(fixed_price_plan_offer.get_plan_status_as_text(), "Configured")

        result = self.client_get("/activity/remote/support", {"q": "example.com"})
        self.assert_in_success_response(
            [
                "Next plan information:",
                "Zulip Basic",
                "Configured",
                "Plan has a fixed price.",
                "Zulip Basic (complimentary)",
            ],
            result,
        )

        # Delete configured fixed price plan.
        billing_session = RemoteRealmBillingSession(remote_realm=self.remote_realm)
        support_request = SupportViewRequest(
            support_type=SupportType.delete_fixed_price_next_plan,
        )
        success_message = billing_session.process_support_view_request(support_request)
        self.assertEqual(success_message, "Fixed-price plan offer deleted")
        result = self.client_get("/activity/remote/support", {"q": "example.com"})
        self.assert_not_in_success_response(["Next plan information:"], result)
        self.assert_in_success_response(
            [
                "Configure fixed price plan",
                "Annual amount in dollars",
                "Zulip Basic (complimentary)",
            ],
            result,
        )
        self.assertFalse(CustomerPlanOffer.objects.exists())

    @responses.activate
    @mock_stripe()
    def test_upgrade_user_to_fixed_price_plan_pay_by_invoice(self, *mocks: Mock) -> None:
        self.login("iago")

        self.add_mock_response()
        with time_machine.travel(self.now, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)

        self.assertFalse(CustomerPlanOffer.objects.exists())

        # Configure required_plan_tier.
        result = self.client_post(
            "/activity/remote/support",
            {
                "remote_realm_id": f"{self.remote_realm.id}",
                "required_plan_tier": CustomerPlan.TIER_SELF_HOSTED_BASIC,
            },
        )
        self.assert_in_success_response(
            ["Required plan tier for Zulip Dev set to Zulip Basic."], result
        )

        # Configure fixed-price plan with ID of manually sent invoice.
        # Invalid 'sent_invoice_id' entered.
        annual_fixed_price = 1200
        with mock.patch("stripe.Invoice.retrieve", side_effect=Exception):
            result = self.client_post(
                "/activity/remote/support",
                {
                    "remote_realm_id": f"{self.remote_realm.id}",
                    "fixed_price": annual_fixed_price,
                    "sent_invoice_id": "invalid_sent_invoice_id",
                },
            )
        self.assert_not_in_success_response(
            ["Customer can now buy a fixed price Zulip Basic plan."], result
        )

        # Invoice status is not 'open'.
        mock_invoice = MagicMock()
        mock_invoice.status = "paid"
        mock_invoice.sent_invoice_id = "paid_invoice_id"
        with mock.patch("stripe.Invoice.retrieve", return_value=mock_invoice):
            result = self.client_post(
                "/activity/remote/support",
                {
                    "remote_realm_id": f"{self.remote_realm.id}",
                    "fixed_price": annual_fixed_price,
                    "sent_invoice_id": mock_invoice.sent_invoice_id,
                },
            )
        self.assert_in_success_response(
            ["Invoice status should be open. Please verify sent_invoice_id."], result
        )

        hamlet = self.example_user("hamlet")
        sent_invoice_id = "test_sent_invoice_id"
        stripe_customer_id = "cus_123"
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
                    "remote_realm_id": f"{self.remote_realm.id}",
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

        audit_log = RemoteRealmAuditLog.objects.filter(
            remote_realm=self.remote_realm,
            event_type=AuditLogEventType.CUSTOMER_PROPERTY_CHANGED,
        ).last()
        assert audit_log is not None
        self.assertEqual(audit_log.remote_realm, self.remote_realm)
        self.assertIsNone(audit_log.extra_data["old_value"])
        self.assertEqual(audit_log.extra_data["property"], "stripe_customer_id")

        invoice = Invoice.objects.get(stripe_invoice_id=sent_invoice_id)
        self.assertEqual(invoice.status, Invoice.SENT)

        self.logout()
        self.login("hamlet")

        # Customer don't need to visit /upgrade to buy plan.
        # In case they visit, we inform them about the mail to which
        # invoice was sent and also display the link for payment.
        self.execute_remote_billing_authentication_flow(hamlet)
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
            hamlet, expect_tos=False, first_time_login=False
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
    def test_schedule_upgrade_to_fixed_price_annual_business_plan(self, *mocks: Mock) -> None:
        self.login("hamlet")
        hamlet = self.example_user("hamlet")

        self.add_mock_response()
        with time_machine.travel(self.now, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)

        # Upgrade to fixed-price Zulip Basic plan.
        self.execute_remote_billing_authentication_flow(hamlet)
        with time_machine.travel(self.now, tick=False):
            stripe_customer = self.add_card_and_upgrade(
                tier=CustomerPlan.TIER_SELF_HOSTED_BASIC,
            )

        customer = Customer.objects.get(stripe_customer_id=stripe_customer.id)
        assert customer.remote_realm is not None
        self.assertEqual(customer.remote_realm.plan_type, RemoteRealm.PLAN_TYPE_BASIC)
        current_plan = CustomerPlan.objects.get(customer=customer, status=CustomerPlan.ACTIVE)
        self.assertEqual(current_plan.tier, CustomerPlan.TIER_SELF_HOSTED_BASIC)
        self.assertIsNone(current_plan.fixed_price)
        self.assertIsNotNone(current_plan.price_per_license)

        self.logout()
        self.login("iago")

        # Schedule a fixed-price business plan at current plan end_date.
        result = self.client_post(
            "/activity/remote/support",
            {
                "remote_realm_id": f"{self.remote_realm.id}",
                "required_plan_tier": CustomerPlan.TIER_SELF_HOSTED_BUSINESS,
            },
        )
        self.assert_in_success_response(
            ["Required plan tier for Zulip Dev set to Zulip Business."], result
        )

        annual_fixed_price = 1200
        result = self.client_post(
            "/activity/remote/support",
            {"remote_realm_id": f"{self.remote_realm.id}", "fixed_price": annual_fixed_price},
        )
        self.assert_in_success_response(
            [
                f"Configure {self.billing_session.billing_entity_display_name} current plan end-date, before scheduling a new plan."
            ],
            result,
        )

        current_plan_end_date = add_months(self.now, 2)
        current_plan.end_date = current_plan_end_date
        current_plan.save(update_fields=["end_date"])

        self.assertFalse(CustomerPlan.objects.filter(fixed_price__isnull=False).exists())

        result = self.client_post(
            "/activity/remote/support",
            {"remote_realm_id": f"{self.remote_realm.id}", "fixed_price": annual_fixed_price},
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
        self.assertEqual(customer.remote_realm.plan_type, RemoteRealm.PLAN_TYPE_BUSINESS)

        self.logout()
        self.login("hamlet")
        hamlet = self.example_user("hamlet")

        # Visit /billing
        self.execute_remote_billing_authentication_flow(
            hamlet, expect_tos=False, first_time_login=False
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
    def test_schedule_complimentary_access_plan_upgrade_to_fixed_price_plan(
        self, *mocks: Mock
    ) -> None:
        hamlet = self.example_user("hamlet")

        remote_realm = RemoteRealm.objects.get(uuid=hamlet.realm.uuid)
        remote_realm_billing_session = RemoteRealmBillingSession(remote_realm=remote_realm)

        # Create complimentary access plan for realm.
        with time_machine.travel(self.now, tick=False):
            start_date = timezone_now()
            end_date = add_months(start_date, months=3)
            remote_realm_billing_session.create_complimentary_access_plan(start_date, end_date)

        self.add_mock_response()
        with time_machine.travel(self.now, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)

        customer = Customer.objects.get(remote_realm=self.remote_realm)
        complimentary_access_plan = get_current_plan_by_customer(customer)
        assert complimentary_access_plan is not None
        self.assertEqual(complimentary_access_plan.tier, CustomerPlan.TIER_SELF_HOSTED_LEGACY)
        self.assertEqual(complimentary_access_plan.next_invoice_date, end_date)

        self.login("iago")

        # Schedule a fixed-price business plan at current plan end_date.
        self.assertFalse(CustomerPlanOffer.objects.exists())

        # Configure required_plan_tier and fixed_price.
        annual_fixed_price = 1200
        result = self.client_post(
            "/activity/remote/support",
            {
                "remote_realm_id": f"{self.remote_realm.id}",
                "required_plan_tier": CustomerPlan.TIER_SELF_HOSTED_BUSINESS,
            },
        )
        self.assert_in_success_response(
            ["Required plan tier for Zulip Dev set to Zulip Business."], result
        )

        result = self.client_post(
            "/activity/remote/support",
            {"remote_realm_id": f"{self.remote_realm.id}", "fixed_price": annual_fixed_price},
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
        self.execute_remote_billing_authentication_flow(
            hamlet, expect_tos=False, confirm_tos=True, first_time_login=True
        )

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

    @responses.activate
    @mock_stripe()
    def test_delete_scheduled_fixed_price_plan_on_complimentary_access_plan(
        self, *mocks: Mock
    ) -> None:
        hamlet = self.example_user("hamlet")

        remote_realm = RemoteRealm.objects.get(uuid=hamlet.realm.uuid)
        remote_realm_billing_session = RemoteRealmBillingSession(remote_realm=remote_realm)

        # Create complimentary access plan for realm.
        with time_machine.travel(self.now, tick=False):
            start_date = timezone_now()
            end_date = add_months(start_date, months=3)
            remote_realm_billing_session.create_complimentary_access_plan(start_date, end_date)

        customer = Customer.objects.get(remote_realm=self.remote_realm)
        complimentary_access_plan = get_current_plan_by_customer(customer)
        assert complimentary_access_plan is not None
        self.assertEqual(complimentary_access_plan.tier, CustomerPlan.TIER_SELF_HOSTED_LEGACY)
        self.assertEqual(complimentary_access_plan.next_invoice_date, end_date)

        # Upload data.
        self.add_mock_response()
        with time_machine.travel(self.now, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)

        self.login("iago")

        # Schedule a fixed-price business plan at current plan end_date.
        self.assertFalse(CustomerPlanOffer.objects.exists())

        # Configure required_plan_tier and fixed_price.
        annual_fixed_price = 1200
        result = self.client_post(
            "/activity/remote/support",
            {
                "remote_realm_id": f"{self.remote_realm.id}",
                "required_plan_tier": CustomerPlan.TIER_SELF_HOSTED_BUSINESS,
            },
        )
        self.assert_in_success_response(
            ["Required plan tier for Zulip Dev set to Zulip Business."], result
        )

        result = self.client_post(
            "/activity/remote/support",
            {"remote_realm_id": f"{self.remote_realm.id}", "fixed_price": annual_fixed_price},
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

        # Login.
        self.execute_remote_billing_authentication_flow(hamlet)

        # Schedule upgrade to business plan
        with time_machine.travel(self.now, tick=False):
            stripe_customer = self.add_card_and_upgrade(
                remote_server_plan_start_date="billing_cycle_end_date", talk_to_stripe=False
            )

        zulip_realm_customer = Customer.objects.get(stripe_customer_id=stripe_customer.id)
        assert zulip_realm_customer is not None
        realm_complimentary_access_plan = get_current_plan_by_customer(zulip_realm_customer)
        assert realm_complimentary_access_plan is not None
        self.assertEqual(realm_complimentary_access_plan.tier, CustomerPlan.TIER_SELF_HOSTED_LEGACY)
        self.assertEqual(
            realm_complimentary_access_plan.status, CustomerPlan.SWITCH_PLAN_TIER_AT_PLAN_END
        )
        self.assertEqual(realm_complimentary_access_plan.next_invoice_date, end_date)

        new_plan = self.billing_session.get_next_plan(realm_complimentary_access_plan)
        assert new_plan is not None
        self.assertEqual(new_plan.tier, CustomerPlan.TIER_SELF_HOSTED_BUSINESS)
        self.assertEqual(new_plan.status, CustomerPlan.NEVER_STARTED)
        self.assertEqual(
            new_plan.invoicing_status, CustomerPlan.INVOICING_STATUS_INITIAL_INVOICE_TO_BE_SENT
        )
        self.assertEqual(new_plan.next_invoice_date, end_date)
        self.assertEqual(new_plan.billing_cycle_anchor, end_date)

        support_request = SupportViewRequest(
            support_type=SupportType.delete_fixed_price_next_plan,
        )
        with (
            self.assertLogs("corporate.stripe", "INFO") as m,
        ):
            success_message = self.billing_session.process_support_view_request(support_request)
            expected_log = f"INFO:corporate.stripe:Change plan status: Customer.id: {customer.id}, CustomerPlan.id: {realm_complimentary_access_plan.id}, status: {CustomerPlan.ACTIVE}"
            self.assertEqual(m.output[0], expected_log)
        self.assertEqual(success_message, "Fixed-price scheduled plan deleted")

        self.assertFalse(
            CustomerPlan.objects.filter(
                customer=zulip_realm_customer, status=CustomerPlan.NEVER_STARTED
            ).exists()
        )
        realm_complimentary_access_plan.refresh_from_db()
        self.assertEqual(realm_complimentary_access_plan.status, CustomerPlan.ACTIVE)

    @responses.activate
    def test_delete_configured_fixed_price_plan_offer_with_sent_invoice(self) -> None:
        self.login("iago")
        self.add_mock_response()
        with time_machine.travel(self.now, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)

        self.client_post(
            "/activity/remote/support",
            {
                "remote_realm_id": f"{self.remote_realm.id}",
                "required_plan_tier": CustomerPlan.TIER_SELF_HOSTED_BASIC,
            },
        )

        annual_fixed_price = 1200
        sent_invoice_id = "test_sent_invoice_id"
        stripe_customer_id = "cus_123"
        hamlet = self.example_user("hamlet")
        mock_invoice = MagicMock()
        mock_invoice.status = "open"
        with (
            patch(
                "stripe.Customer.retrieve",
                return_value=Mock(id=stripe_customer_id, email=hamlet.delivery_email),
            ),
            patch("stripe.Invoice.retrieve", return_value=mock_invoice),
        ):
            self.client_post(
                "/activity/remote/support",
                {
                    "remote_realm_id": f"{self.remote_realm.id}",
                    "fixed_price": annual_fixed_price,
                    "sent_invoice_id": sent_invoice_id,
                },
            )

        customer = Customer.objects.get(remote_realm=self.remote_realm)
        fixed_price_plan_offer = CustomerPlanOffer.objects.get(customer=customer)
        self.assertEqual(fixed_price_plan_offer.status, CustomerPlanOffer.CONFIGURED)
        self.assertEqual(fixed_price_plan_offer.sent_invoice_id, sent_invoice_id)
        local_invoice = Invoice.objects.get(stripe_invoice_id=sent_invoice_id)
        self.assertEqual(local_invoice.status, Invoice.SENT)

        with (
            patch("stripe.Invoice.retrieve", return_value=mock_invoice),
            patch("stripe.Invoice.void_invoice") as mock_void,
        ):
            support_request = SupportViewRequest(
                support_type=SupportType.delete_fixed_price_next_plan,
            )
            success_message = self.billing_session.process_support_view_request(support_request)
        self.assertEqual(success_message, "Fixed-price plan offer deleted")
        mock_void.assert_called_once_with(sent_invoice_id)

        self.assertFalse(CustomerPlanOffer.objects.exists())
        local_invoice.refresh_from_db()
        self.assertEqual(local_invoice.status, Invoice.VOID)

    @responses.activate
    @mock_stripe()
    def test_schedule_fixed_price_plan_upgrade_to_another_fixed_price_plan(
        self, *mocks: Mock
    ) -> None:
        self.login("iago")

        self.add_mock_response()
        with time_machine.travel(self.now, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)

        # Configure required_plan_tier and fixed_price.
        annual_fixed_price = 1200
        result = self.client_post(
            "/activity/remote/support",
            {
                "remote_realm_id": f"{self.remote_realm.id}",
                "required_plan_tier": CustomerPlan.TIER_SELF_HOSTED_BASIC,
            },
        )
        result = self.client_post(
            "/activity/remote/support",
            {"remote_realm_id": f"{self.remote_realm.id}", "fixed_price": annual_fixed_price},
        )
        self.assert_in_success_response(
            ["Customer can now buy a fixed price Zulip Basic plan."], result
        )

        self.logout()
        self.login("hamlet")
        hamlet = self.example_user("hamlet")

        # Upgrade to fixed-price Zulip Basic plan with monthly billing_schedule.
        self.execute_remote_billing_authentication_flow(hamlet)
        with time_machine.travel(self.now, tick=False):
            stripe_customer = self.add_card_and_upgrade(
                tier=CustomerPlan.TIER_SELF_HOSTED_BASIC, schedule="monthly"
            )

        customer = Customer.objects.get(stripe_customer_id=stripe_customer.id)
        current_plan = CustomerPlan.objects.get(customer=customer, status=CustomerPlan.ACTIVE)
        end_date = add_months(self.now, 12)
        self.assertIsNotNone(current_plan.fixed_price)
        self.assertEqual(current_plan.billing_schedule, CustomerPlan.BILLING_SCHEDULE_MONTHLY)
        self.assertEqual(current_plan.end_date, end_date)

        # Invoice for february to october
        for invoice_count in range(1, 10):
            with time_machine.travel(add_months(self.now, invoice_count), tick=False):
                send_server_data_to_push_bouncer(consider_usage_statistics=False)
                invoice_plans_as_needed()

        billing_entity = self.billing_session.billing_entity_display_name

        # Cron runs 60 days before the end date (november) & sends a reminder email.
        self.assertFalse(current_plan.reminder_to_review_plan_email_sent)
        with time_machine.travel(add_months(self.now, 10), tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)
            invoice_plans_as_needed()
        current_plan.refresh_from_db()
        self.assertTrue(current_plan.reminder_to_review_plan_email_sent)

        from django.core.mail import outbox

        messages_count = len(outbox)
        message = outbox[-1]
        self.assert_length(message.to, 1)
        self.assertEqual(message.to[0], "sales@zulip.com")
        self.assertIn(
            f"Support URL: {self.billing_session.support_url()}",
            message.body,
        )
        self.assertIn(
            f"Internal billing notice for {self.billing_session.billing_entity_display_name}.",
            message.body,
        )
        self.assertIn(
            "Reminder to re-evaluate the pricing and configure a new fixed-price plan accordingly.",
            message.body,
        )
        self.assertEqual(
            f"Fixed-price plan for {billing_entity} ends on {end_date.date().isoformat()}",
            message.subject,
        )

        self.logout()
        self.login("iago")

        # Verify that we can't schedule a new fixed-price plan until invoice for 12th month is processed.
        result = self.client_post(
            "/activity/remote/support",
            {"remote_realm_id": f"{self.remote_realm.id}", "fixed_price": annual_fixed_price + 200},
        )
        self.assert_in_success_response(
            [
                f"New plan for {billing_entity} cannot be scheduled until all the invoices of the current plan are processed."
            ],
            result,
        )

        # Customer is charged for the last month of current plan.
        with time_machine.travel(add_months(self.now, 11), tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)
            invoice_plans_as_needed()

        # Verify that we don't send another email to Zulip team.
        self.assert_length(outbox, messages_count)

        # All the monthly invoices are processed, now we can schedule a plan.
        updated_annual_fixed_price = annual_fixed_price + 500
        result = self.client_post(
            "/activity/remote/support",
            {
                "remote_realm_id": f"{self.remote_realm.id}",
                "fixed_price": updated_annual_fixed_price,
            },
        )
        self.assert_in_success_response(
            [f"Fixed price Zulip Basic plan scheduled to start on {end_date.date()}."],
            result,
        )

        # Cron runs on end_date and customer switches to the new plan
        with time_machine.travel(end_date, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)
            invoice_plans_as_needed()
        current_plan.refresh_from_db()
        self.assertEqual(current_plan.status, CustomerPlan.ENDED)
        new_plan = get_current_plan_by_customer(customer)
        assert new_plan is not None
        self.assertEqual(new_plan.status, CustomerPlan.ACTIVE)
        self.assertEqual(new_plan.fixed_price, updated_annual_fixed_price * 100)

    @responses.activate
    @mock_stripe()
    def test_migrate_customer_server_to_realms_and_upgrade(self, *mocks: Mock) -> None:
        remote_server = RemoteZulipServer.objects.get(hostname="demo.example.com")
        server_billing_session = RemoteServerBillingSession(remote_server=remote_server)

        # Create complimentary access plan for server.
        with time_machine.travel(self.now, tick=False):
            start_date = timezone_now()
            end_date = add_months(start_date, months=3)
            server_billing_session.create_complimentary_access_plan(start_date, end_date)

        server_customer = server_billing_session.get_customer()
        assert server_customer is not None
        server_customer_plan = get_current_plan_by_customer(server_customer)
        assert server_customer_plan is not None
        self.assertEqual(server_customer_plan.tier, CustomerPlan.TIER_SELF_HOSTED_LEGACY)
        self.assertEqual(server_customer_plan.status, CustomerPlan.ACTIVE)
        self.assertEqual(remote_server.plan_type, RemoteZulipServer.PLAN_TYPE_SELF_MANAGED_LEGACY)

        # The plan gets migrated if there's only a single human realm.
        Realm.objects.exclude(string_id__in=["zulip", "zulipinternal"]).delete()

        # First, set a sponsorship as pending.
        # TODO: Ideally, we'd submit a proper sponsorship request.
        server_customer.sponsorship_pending = True
        server_customer.save()

        # Upload data.
        with time_machine.travel(self.now, tick=False):
            self.add_mock_response()
            send_server_data_to_push_bouncer(consider_usage_statistics=False)

        self.login("hamlet")
        hamlet = self.example_user("hamlet")
        billing_base_url = self.billing_session.billing_base_url

        # Login. The server has a pending sponsorship, in which case migrating
        # can't be done, as that'd be a fairly confusing process.
        result = self.execute_remote_billing_authentication_flow(hamlet, return_from_auth_url=True)

        self.assertEqual(result.status_code, 200)
        self.assert_in_response("Plan management not available", result)
        # Server's plan should not have been migrated yet.
        self.server.refresh_from_db()
        self.assertEqual(self.server.plan_type, RemoteZulipServer.PLAN_TYPE_SELF_MANAGED_LEGACY)

        # Now clear the pending sponsorship state, which will allow login
        # and migration to proceed.
        # TODO: Ideally, this would approve the sponsorship and then be testing
        # the migration of the Community plan.
        server_customer.sponsorship_pending = False
        server_customer.save()

        # Login. Performs customer migration from server to realm.
        result = self.execute_remote_billing_authentication_flow(hamlet)

        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], f"{billing_base_url}/plans/")

        remote_server.refresh_from_db()
        remote_realm = RemoteRealm.objects.get(uuid=hamlet.realm.uuid)
        # The customer object was moved, together with the plan, from server to realm.
        customer = get_customer_by_remote_realm(remote_realm)
        assert customer is not None
        self.assertEqual(server_customer, customer)
        self.assertEqual(remote_server.plan_type, RemoteZulipServer.PLAN_TYPE_SELF_MANAGED)
        self.assertEqual(remote_realm.plan_type, RemoteRealm.PLAN_TYPE_SELF_MANAGED_LEGACY)

        customer_plan = get_current_plan_by_customer(customer)
        assert customer_plan is not None
        self.assertEqual(customer_plan.tier, CustomerPlan.TIER_SELF_HOSTED_LEGACY)
        self.assertEqual(customer_plan.status, CustomerPlan.ACTIVE)

        # upgrade to business plan
        with time_machine.travel(self.now, tick=False):
            result = self.client_get(f"{billing_base_url}/upgrade/", subdomain="selfhosting")
        self.assertEqual(result.status_code, 200)
        self.assert_in_success_response(["Add card", "Purchase Zulip Business"], result)

        with time_machine.travel(self.now, tick=False):
            stripe_customer = self.add_card_and_upgrade()

        self.assertEqual(customer, Customer.objects.get(stripe_customer_id=stripe_customer.id))
        business_plan = CustomerPlan.objects.get(customer=customer, status=CustomerPlan.ACTIVE)
        self.assertEqual(business_plan.tier, CustomerPlan.TIER_SELF_HOSTED_BUSINESS)

        realm_user_count = UserProfile.objects.filter(
            realm=hamlet.realm, is_bot=False, is_active=True
        ).count()
        licenses = max(
            realm_user_count, self.billing_session.min_licenses_for_plan(business_plan.tier)
        )
        with time_machine.travel(self.now + timedelta(days=1), tick=False):
            response = self.client_get(f"{billing_base_url}/billing/", subdomain="selfhosting")
        for substring in [
            "Zulip Business",
            "Number of licenses",
            f"{licenses}",
            "Your plan will automatically renew on",
            "January 2, 2013",
            f"${80 * licenses:,.2f}",
            "Visa ending in 4242",
            "Update card",
        ]:
            self.assert_in_response(substring, response)

        # Login again
        result = self.execute_remote_billing_authentication_flow(
            hamlet, first_time_login=False, expect_tos=False, confirm_tos=False
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
            expected_log = f"INFO:corporate.stripe:Change plan status: Customer.id: {customer.id}, CustomerPlan.id: {business_plan.id}, status: {CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE}"
            self.assertEqual(m.output[0], expected_log)
            self.assert_json_success(response)
        business_plan.refresh_from_db()
        self.assertEqual(business_plan.licenses_at_next_renewal(), None)

    @responses.activate
    @mock_stripe()
    def test_invoice_initial_remote_realm_upgrade(self, *mocks: Mock) -> None:
        self.login("hamlet")
        hamlet = self.example_user("hamlet")

        realm_user_count = UserProfile.objects.filter(
            realm=hamlet.realm, is_bot=False, is_active=True
        ).count()

        self.add_mock_response()
        with time_machine.travel(self.now, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)

        self.execute_remote_billing_authentication_flow(hamlet)
        with time_machine.travel(self.now, tick=False):
            stripe_customer = self.add_card_and_upgrade(
                tier=CustomerPlan.TIER_SELF_HOSTED_BASIC, schedule="monthly"
            )

        [invoice0] = iter(stripe.Invoice.list(customer=stripe_customer.id))

        [invoice_item0, invoice_item1] = iter(invoice0.lines)
        self.assertEqual(invoice_item0.amount, -2000)
        self.assertEqual(invoice_item0.description, "$20.00/month new customer discount")
        self.assertEqual(invoice_item0.quantity, 1)

        self.assertEqual(invoice_item1.amount, realm_user_count * 3.5 * 100)
        self.assertEqual(invoice_item1.description, "Zulip Basic")
        self.assertEqual(invoice_item1.quantity, realm_user_count)

    @responses.activate
    @mock_stripe()
    def test_invoice_plans_as_needed(self, *mocks: Mock) -> None:
        self.login("hamlet")
        hamlet = self.example_user("hamlet")

        self.add_mock_response()
        with time_machine.travel(self.now, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)

        self.execute_remote_billing_authentication_flow(hamlet)
        with time_machine.travel(self.now, tick=False):
            stripe_customer = self.add_card_and_upgrade(
                tier=CustomerPlan.TIER_SELF_HOSTED_BASIC, schedule="monthly"
            )

        customer = Customer.objects.get(stripe_customer_id=stripe_customer.id)
        plan = CustomerPlan.objects.get(customer=customer)
        assert plan.customer.remote_realm is not None
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

        # Data upload was 25 days before the invoice date.
        last_audit_log_update = self.now + timedelta(days=5)
        with time_machine.travel(last_audit_log_update, tick=False):
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
        self.assertIn(f"Last data upload: {last_audit_log_update.date().isoformat()}", message.body)

        # Cron runs again, don't send another email to Zulip team.
        invoice_plans_as_needed(self.next_month + timedelta(days=1))
        self.assert_length(outbox, messages_count)

        # Ledger is up-to-date. Plan invoiced.
        with time_machine.travel(self.next_month, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)
        invoice_plans_as_needed(self.next_month)
        plan.refresh_from_db()
        self.assertEqual(plan.next_invoice_date, add_months(self.next_month, 1))
        self.assertFalse(plan.stale_audit_log_data_email_sent)

        assert customer.stripe_customer_id
        [invoice0, _invoice1] = iter(stripe.Invoice.list(customer=customer.stripe_customer_id))

        [_invoice_item0, invoice_item1, invoice_item2] = iter(invoice0.lines)
        self.assertEqual(invoice_item2.amount, 16 * 3.5 * 100)
        self.assertEqual(invoice_item2.description, "Zulip Basic - renewal")
        self.assertEqual(invoice_item2.quantity, 16)
        self.assertEqual(invoice_item2.period["start"], datetime_to_timestamp(self.next_month))
        self.assertEqual(
            invoice_item2.period["end"], datetime_to_timestamp(add_months(self.next_month, 1))
        )

        self.assertEqual(invoice_item1.description, "Additional Zulip Basic license")
        self.assertEqual(invoice_item1.quantity, 5)
        self.assertEqual(
            invoice_item1.period["start"], datetime_to_timestamp(self.now + timedelta(days=2))
        )
        self.assertEqual(invoice_item1.period["end"], datetime_to_timestamp(self.next_month))

        # Verify Zulip team receives mail for the next cycle.
        invoice_plans_as_needed(add_months(self.next_month, 1))
        self.assert_length(outbox, messages_count + 1)

    @responses.activate
    @mock_stripe()
    def test_invoice_scheduled_upgrade_realm_complimentary_access_plan(self, *mocks: Mock) -> None:
        hamlet = self.example_user("hamlet")

        remote_realm = RemoteRealm.objects.get(uuid=hamlet.realm.uuid)
        remote_realm_billing_session = RemoteRealmBillingSession(remote_realm=remote_realm)

        # Create complimentary access plan for realm.
        with time_machine.travel(self.now, tick=False):
            start_date = timezone_now()
            end_date = add_months(start_date, months=3)
            remote_realm_billing_session.create_complimentary_access_plan(start_date, end_date)

        # Upload data.
        self.add_mock_response()
        with time_machine.travel(self.now, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)

        self.login("hamlet")

        # Login.
        self.execute_remote_billing_authentication_flow(hamlet)

        # Schedule upgrade to business plan
        with time_machine.travel(self.now, tick=False):
            stripe_customer = self.add_card_and_upgrade(
                remote_server_plan_start_date="billing_cycle_end_date", talk_to_stripe=False
            )

        zulip_realm_customer = Customer.objects.get(stripe_customer_id=stripe_customer.id)
        assert zulip_realm_customer is not None
        realm_complimentary_access_plan = get_current_plan_by_customer(zulip_realm_customer)
        assert realm_complimentary_access_plan is not None
        self.assertEqual(realm_complimentary_access_plan.tier, CustomerPlan.TIER_SELF_HOSTED_LEGACY)
        self.assertEqual(
            realm_complimentary_access_plan.status, CustomerPlan.SWITCH_PLAN_TIER_AT_PLAN_END
        )
        self.assertEqual(realm_complimentary_access_plan.next_invoice_date, end_date)

        new_plan = self.billing_session.get_next_plan(realm_complimentary_access_plan)
        assert new_plan is not None
        self.assertEqual(new_plan.tier, CustomerPlan.TIER_SELF_HOSTED_BUSINESS)
        self.assertEqual(new_plan.status, CustomerPlan.NEVER_STARTED)
        self.assertEqual(
            new_plan.invoicing_status, CustomerPlan.INVOICING_STATUS_INITIAL_INVOICE_TO_BE_SENT
        )
        self.assertEqual(new_plan.next_invoice_date, end_date)
        self.assertEqual(new_plan.billing_cycle_anchor, end_date)

        realm_user_count = UserProfile.objects.filter(
            realm=hamlet.realm, is_bot=False, is_active=True
        ).count()
        licenses = max(
            realm_user_count,
            self.billing_session.min_licenses_for_plan(CustomerPlan.TIER_SELF_HOSTED_BUSINESS),
        )

        with time_machine.travel(end_date, tick=False):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)
            invoice_plans_as_needed()
            # 'invoice_plan()' is called with both complimentary access & new plan, but
            # invoice is created only for new plan. The complimentary access plan only goes
            # through the end of cycle updates.

        realm_complimentary_access_plan.refresh_from_db()
        new_plan.refresh_from_db()
        self.assertEqual(realm_complimentary_access_plan.status, CustomerPlan.ENDED)
        self.assertEqual(realm_complimentary_access_plan.next_invoice_date, None)
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
