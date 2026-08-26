import itertools
import typing
import uuid
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import cast
from unittest import mock
from unittest.mock import Mock, patch

import stripe
import time_machine
from django.conf import settings
from django.utils.timezone import now as timezone_now

from corporate.lib.stripe import (
    BillingError,
    BillingSessionAuditLogEventError,
    BillingSessionEventType,
    BillingUserCounts,
    InvalidBillingScheduleError,
    InvalidTierError,
    RealmBillingSession,
    RemoteRealmBillingSession,
    RemoteServerBillingSession,
    SupportRequestError,
    SupportType,
    SupportViewRequest,
    UpdatePlanRequest,
    add_months,
    compute_plan_parameters,
    get_next_billing_cycle_for_plan,
    get_plan_renewal_or_end_date,
    get_price_per_license,
    invoice_plans_as_needed,
    is_realm_on_free_trial,
    next_month,
)
from corporate.lib.test_stripe_class import StripeTestCase, mock_stripe
from corporate.models.customers import Customer, get_customer_by_realm
from corporate.models.licenses import LicenseLedger
from corporate.models.plans import (
    CustomerPlan,
    CustomerPlanOffer,
    get_current_plan_by_customer,
    get_current_plan_by_realm,
)
from zerver.actions.create_user import (
    do_activate_mirror_dummy_user,
    do_create_user,
    do_reactivate_user,
)
from zerver.actions.users import change_user_is_active, do_deactivate_user
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.lib.utils import assert_is_not_none
from zerver.models import Message, Realm, RealmAuditLog, Recipient, UserProfile
from zerver.models.realm_audit_logs import AuditLogEventType
from zerver.models.realms import get_realm
from zerver.models.users import get_system_bot
from zilencer.models import (
    RemoteRealm,
    RemoteRealmAuditLog,
    RemoteRealmBillingUser,
    RemoteServerBillingUser,
    RemoteZulipServer,
    RemoteZulipServerAuditLog,
)


class BillingHelpersTest(ZulipTestCase):
    def test_next_month(self) -> None:
        anchor = datetime(2019, 12, 31, 1, 2, 3, tzinfo=timezone.utc)
        period_boundaries = [
            anchor,
            datetime(2020, 1, 31, 1, 2, 3, tzinfo=timezone.utc),
            # Test that this is the 28th even during leap years
            datetime(2020, 2, 28, 1, 2, 3, tzinfo=timezone.utc),
            datetime(2020, 3, 31, 1, 2, 3, tzinfo=timezone.utc),
            datetime(2020, 4, 30, 1, 2, 3, tzinfo=timezone.utc),
            datetime(2020, 5, 31, 1, 2, 3, tzinfo=timezone.utc),
            datetime(2020, 6, 30, 1, 2, 3, tzinfo=timezone.utc),
            datetime(2020, 7, 31, 1, 2, 3, tzinfo=timezone.utc),
            datetime(2020, 8, 31, 1, 2, 3, tzinfo=timezone.utc),
            datetime(2020, 9, 30, 1, 2, 3, tzinfo=timezone.utc),
            datetime(2020, 10, 31, 1, 2, 3, tzinfo=timezone.utc),
            datetime(2020, 11, 30, 1, 2, 3, tzinfo=timezone.utc),
            datetime(2020, 12, 31, 1, 2, 3, tzinfo=timezone.utc),
            datetime(2021, 1, 31, 1, 2, 3, tzinfo=timezone.utc),
            datetime(2021, 2, 28, 1, 2, 3, tzinfo=timezone.utc),
        ]
        with self.assertRaises(AssertionError):
            add_months(anchor, -1)
        # Explicitly test add_months for each value of MAX_DAY_FOR_MONTH and
        # for crossing a year boundary
        for i, boundary in enumerate(period_boundaries):
            self.assertEqual(add_months(anchor, i), boundary)
        # Test next_month for small values
        for last, next_ in itertools.pairwise(period_boundaries):
            self.assertEqual(next_month(anchor, last), next_)
        # Test next_month for large values
        period_boundaries = [dt.replace(year=dt.year + 100) for dt in period_boundaries]
        for last, next_ in itertools.pairwise(period_boundaries):
            self.assertEqual(next_month(anchor, last), next_)

    def test_compute_plan_parameters(self) -> None:
        anchor = datetime(2019, 12, 31, 1, 2, 3, tzinfo=timezone.utc)
        month_later = datetime(2020, 1, 31, 1, 2, 3, tzinfo=timezone.utc)
        year_later = datetime(2020, 12, 31, 1, 2, 3, tzinfo=timezone.utc)
        customer_with_discount = Customer.objects.create(
            realm=get_realm("lear"),
            monthly_discounted_price=600,
            annual_discounted_price=6000,
            required_plan_tier=CustomerPlan.TIER_CLOUD_STANDARD,
        )
        customer_no_discount = Customer.objects.create(realm=get_realm("zulip"))
        test_cases = [
            # Annual standard no customer
            (
                (
                    CustomerPlan.TIER_CLOUD_STANDARD,
                    CustomerPlan.BILLING_SCHEDULE_ANNUAL,
                    None,
                ),
                (anchor, month_later, year_later, 8000),
            ),
            # Annual standard with discount
            (
                (
                    CustomerPlan.TIER_CLOUD_STANDARD,
                    CustomerPlan.BILLING_SCHEDULE_ANNUAL,
                    customer_with_discount,
                ),
                (anchor, month_later, year_later, 6000),
            ),
            # Annual standard customer but no discount
            (
                (
                    CustomerPlan.TIER_CLOUD_STANDARD,
                    CustomerPlan.BILLING_SCHEDULE_ANNUAL,
                    customer_no_discount,
                ),
                (anchor, month_later, year_later, 8000),
            ),
            # Annual plus customer with discount but different tier than required for discount
            (
                (
                    CustomerPlan.TIER_CLOUD_PLUS,
                    CustomerPlan.BILLING_SCHEDULE_ANNUAL,
                    customer_with_discount,
                ),
                (anchor, month_later, year_later, 12000),
            ),
            # Monthly standard no customer
            (
                (
                    CustomerPlan.TIER_CLOUD_STANDARD,
                    CustomerPlan.BILLING_SCHEDULE_MONTHLY,
                    None,
                ),
                (anchor, month_later, month_later, 800),
            ),
            # Monthly standard with discount
            (
                (
                    CustomerPlan.TIER_CLOUD_STANDARD,
                    CustomerPlan.BILLING_SCHEDULE_MONTHLY,
                    customer_with_discount,
                ),
                (anchor, month_later, month_later, 600),
            ),
            # Monthly standard customer but no discount
            (
                (
                    CustomerPlan.TIER_CLOUD_STANDARD,
                    CustomerPlan.BILLING_SCHEDULE_MONTHLY,
                    customer_no_discount,
                ),
                (anchor, month_later, month_later, 800),
            ),
            # Monthly plus customer with discount but different tier than required for discount
            (
                (
                    CustomerPlan.TIER_CLOUD_PLUS,
                    CustomerPlan.BILLING_SCHEDULE_MONTHLY,
                    customer_with_discount,
                ),
                (anchor, month_later, month_later, 1200),
            ),
        ]
        # compute_plan_parameters truncates microseconds in the anchor datetime.
        with time_machine.travel(anchor + timedelta(microseconds=654321), tick=False):
            for (tier, billing_schedule, customer), output in test_cases:
                output_ = compute_plan_parameters(
                    tier,
                    billing_schedule,
                    customer,
                )
                self.assertEqual(output_, output)

    def test_get_price_per_license(self) -> None:
        standard_discounted_customer = Customer.objects.create(
            realm=get_realm("lear"),
            monthly_discounted_price=400,
            annual_discounted_price=4000,
            required_plan_tier=CustomerPlan.TIER_CLOUD_STANDARD,
        )
        plus_discounted_customer = Customer.objects.create(
            realm=get_realm("zulip"),
            monthly_discounted_price=600,
            annual_discounted_price=6000,
            required_plan_tier=CustomerPlan.TIER_CLOUD_PLUS,
        )
        self.assertEqual(
            get_price_per_license(
                CustomerPlan.TIER_CLOUD_STANDARD, CustomerPlan.BILLING_SCHEDULE_ANNUAL
            ),
            8000,
        )
        self.assertEqual(
            get_price_per_license(
                CustomerPlan.TIER_CLOUD_STANDARD, CustomerPlan.BILLING_SCHEDULE_MONTHLY
            ),
            800,
        )
        self.assertEqual(
            get_price_per_license(
                CustomerPlan.TIER_CLOUD_STANDARD,
                CustomerPlan.BILLING_SCHEDULE_MONTHLY,
                standard_discounted_customer,
            ),
            400,
        )

        self.assertEqual(
            get_price_per_license(
                CustomerPlan.TIER_CLOUD_PLUS, CustomerPlan.BILLING_SCHEDULE_ANNUAL
            ),
            12000,
        )
        self.assertEqual(
            get_price_per_license(
                CustomerPlan.TIER_CLOUD_PLUS, CustomerPlan.BILLING_SCHEDULE_MONTHLY
            ),
            1200,
        )
        self.assertEqual(
            get_price_per_license(
                CustomerPlan.TIER_CLOUD_PLUS,
                CustomerPlan.BILLING_SCHEDULE_MONTHLY,
                # Wrong tier so discount not applied.
                standard_discounted_customer,
            ),
            1200,
        )
        self.assertEqual(
            get_price_per_license(
                CustomerPlan.TIER_CLOUD_PLUS,
                CustomerPlan.BILLING_SCHEDULE_MONTHLY,
                plus_discounted_customer,
            ),
            600,
        )

        with self.assertRaisesRegex(InvalidBillingScheduleError, "Unknown billing_schedule: 1000"):
            get_price_per_license(CustomerPlan.TIER_CLOUD_STANDARD, 1000)

        with self.assertRaisesRegex(InvalidTierError, "Unknown tier: 4"):
            get_price_per_license(
                CustomerPlan.TIER_CLOUD_ENTERPRISE, CustomerPlan.BILLING_SCHEDULE_ANNUAL
            )

    def test_get_plan_renewal_or_end_date(self) -> None:
        realm = get_realm("zulip")
        customer = Customer.objects.create(realm=realm, stripe_customer_id="cus_12345")
        billing_cycle_anchor = timezone_now()
        plan = CustomerPlan.objects.create(
            customer=customer,
            status=CustomerPlan.ACTIVE,
            billing_cycle_anchor=billing_cycle_anchor,
            billing_schedule=CustomerPlan.BILLING_SCHEDULE_MONTHLY,
            tier=CustomerPlan.TIER_CLOUD_STANDARD,
        )
        renewal_date = get_plan_renewal_or_end_date(plan, billing_cycle_anchor)
        self.assertEqual(renewal_date, add_months(billing_cycle_anchor, 1))

        # When the plan ends 2 days before the start of the next billing cycle,
        # the function should return the end_date.
        plan_end_date = add_months(billing_cycle_anchor, 1) - timedelta(days=2)
        plan.end_date = plan_end_date
        plan.save(update_fields=["end_date"])
        renewal_date = get_plan_renewal_or_end_date(plan, billing_cycle_anchor)
        self.assertEqual(renewal_date, plan_end_date)

    def test_update_or_create_stripe_customer_logic(self) -> None:
        user = self.example_user("hamlet")
        # No existing Customer object
        with patch(
            "corporate.lib.stripe.BillingSession.create_stripe_customer", return_value="returned"
        ) as mocked1:
            billing_session = RealmBillingSession(user)
            returned = billing_session.update_or_create_stripe_customer()
        mocked1.assert_called_once()
        self.assertEqual(returned, "returned")

        customer = Customer.objects.create(realm=get_realm("zulip"))
        # Customer exists but stripe_customer_id is None
        with patch(
            "corporate.lib.stripe.BillingSession.create_stripe_customer", return_value="returned"
        ) as mocked2:
            billing_session = RealmBillingSession(user)
            returned = billing_session.update_or_create_stripe_customer()
        mocked2.assert_called_once()
        self.assertEqual(returned, "returned")

        customer.stripe_customer_id = "cus_12345"
        customer.save()
        # Customer exists, replace payment source
        with patch("corporate.lib.stripe.BillingSession.replace_payment_method") as mocked3:
            billing_session = RealmBillingSession(user)
            returned_customer = billing_session.update_or_create_stripe_customer("pm_card_visa")
        mocked3.assert_called_once()
        self.assertEqual(returned_customer, customer)

        # Customer exists, do nothing
        with patch("corporate.lib.stripe.BillingSession.replace_payment_method") as mocked4:
            billing_session = RealmBillingSession(user)
            returned_customer = billing_session.update_or_create_stripe_customer(None)
        mocked4.assert_not_called()
        self.assertEqual(returned_customer, customer)

    def test_get_customer_by_realm(self) -> None:
        realm = get_realm("zulip")

        self.assertEqual(get_customer_by_realm(realm), None)

        customer = Customer.objects.create(realm=realm, stripe_customer_id="cus_12345")
        self.assertEqual(get_customer_by_realm(realm), customer)

    def test_get_current_plan_by_customer(self) -> None:
        realm = get_realm("zulip")
        customer = Customer.objects.create(realm=realm, stripe_customer_id="cus_12345")

        self.assertEqual(get_current_plan_by_customer(customer), None)

        plan = CustomerPlan.objects.create(
            customer=customer,
            status=CustomerPlan.ACTIVE,
            billing_cycle_anchor=timezone_now(),
            billing_schedule=CustomerPlan.BILLING_SCHEDULE_ANNUAL,
            tier=CustomerPlan.TIER_CLOUD_STANDARD,
        )
        self.assertEqual(get_current_plan_by_customer(customer), plan)

        plan.status = CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE
        plan.save(update_fields=["status"])
        self.assertEqual(get_current_plan_by_customer(customer), plan)

        plan.status = CustomerPlan.ENDED
        plan.save(update_fields=["status"])
        self.assertEqual(get_current_plan_by_customer(customer), None)

        plan.status = CustomerPlan.NEVER_STARTED
        plan.save(update_fields=["status"])
        self.assertEqual(get_current_plan_by_customer(customer), None)

    def test_get_current_plan_by_realm(self) -> None:
        realm = get_realm("zulip")

        self.assertEqual(get_current_plan_by_realm(realm), None)

        customer = Customer.objects.create(realm=realm, stripe_customer_id="cus_12345")
        self.assertEqual(get_current_plan_by_realm(realm), None)

        plan = CustomerPlan.objects.create(
            customer=customer,
            status=CustomerPlan.ACTIVE,
            billing_cycle_anchor=timezone_now(),
            billing_schedule=CustomerPlan.BILLING_SCHEDULE_ANNUAL,
            tier=CustomerPlan.TIER_CLOUD_STANDARD,
        )
        self.assertEqual(get_current_plan_by_realm(realm), plan)

    def test_is_realm_on_free_trial(self) -> None:
        realm = get_realm("zulip")
        self.assertFalse(is_realm_on_free_trial(realm))

        customer = Customer.objects.create(realm=realm, stripe_customer_id="cus_12345")
        plan = CustomerPlan.objects.create(
            customer=customer,
            status=CustomerPlan.ACTIVE,
            billing_cycle_anchor=timezone_now(),
            billing_schedule=CustomerPlan.BILLING_SCHEDULE_ANNUAL,
            tier=CustomerPlan.TIER_CLOUD_STANDARD,
        )
        self.assertFalse(is_realm_on_free_trial(realm))

        plan.status = CustomerPlan.FREE_TRIAL
        plan.save(update_fields=["status"])
        self.assertTrue(is_realm_on_free_trial(realm))

    def test_deactivate_reactivate_remote_server(self) -> None:
        server_uuid = str(uuid.uuid4())
        remote_server = RemoteZulipServer.objects.create(
            uuid=server_uuid,
            api_key="magic_secret_api_key",
            hostname="demo.example.com",
            contact_email="email@example.com",
        )
        self.assertFalse(remote_server.deactivated)
        remote_server_billing_user = RemoteServerBillingUser.objects.create(
            remote_server=remote_server, email="admin@example.com"
        )

        billing_session = RemoteServerBillingSession(remote_server, remote_server_billing_user)
        billing_session.do_deactivate_remote_server()

        remote_server = RemoteZulipServer.objects.get(uuid=server_uuid)
        remote_realm_audit_log = RemoteZulipServerAuditLog.objects.filter(
            event_type=AuditLogEventType.REMOTE_SERVER_DEACTIVATED
        ).last()
        assert remote_realm_audit_log is not None
        self.assertTrue(remote_server.deactivated)
        self.assertEqual(remote_realm_audit_log.acting_remote_user, remote_server_billing_user)

        # Try to deactivate a remote server that is already deactivated
        with self.assertLogs("corporate.stripe", "WARN") as warning_log:
            billing_session.do_deactivate_remote_server()
            self.assertEqual(
                warning_log.output,
                [
                    (
                        "WARNING:corporate.stripe:Cannot deactivate remote server with ID "
                        f"{remote_server.id}, server has already been deactivated."
                    )
                ],
            )

        billing_session.do_reactivate_remote_server()
        remote_server.refresh_from_db()
        self.assertFalse(remote_server.deactivated)
        remote_realm_audit_log = RemoteZulipServerAuditLog.objects.latest("id")
        self.assertEqual(
            remote_realm_audit_log.event_type, AuditLogEventType.REMOTE_SERVER_REACTIVATED
        )
        self.assertEqual(remote_realm_audit_log.server, remote_server)

        with self.assertLogs("corporate.stripe", "WARN") as warning_log:
            billing_session.do_reactivate_remote_server()
            self.assertEqual(
                warning_log.output,
                [
                    (
                        "WARNING:corporate.stripe:Cannot reactivate remote server with ID "
                        f"{remote_server.id}, server is already active."
                    )
                ],
            )

    def test_initialize_fixed_price_plan_realm(self) -> None:
        billing_cycle_anchor = datetime(2012, 1, 1, 1, 1, 1, tzinfo=timezone.utc)
        realm = get_realm("zulip")

        # Requires a Customer object for the billing entity.
        billing_session = RealmBillingSession(None, realm)
        with self.assertRaises(BillingError) as billing_context:
            billing_session.initialize_prepaid_fixed_price_plan(
                plan_tier=CustomerPlan.TIER_CLOUD_STANDARD,
                billing_cycle_anchor=billing_cycle_anchor,
            )
        self.assertEqual(
            "no_customer",
            billing_context.exception.error_description,
        )

        # Requires that the Customer object is linked to a
        # customer ID in Stripe.
        billing_session.update_or_create_customer()
        with self.assertRaises(BillingError) as billing_context:
            billing_session.initialize_prepaid_fixed_price_plan(
                plan_tier=CustomerPlan.TIER_CLOUD_STANDARD,
                billing_cycle_anchor=billing_cycle_anchor,
            )
        self.assertEqual(
            "no_stripe_id",
            billing_context.exception.error_description,
        )

        # Requires a fixed price plan offer to be configured
        # for the customer.
        customer = billing_session.get_customer()
        assert customer is not None
        customer.stripe_customer_id = "cus_123"
        customer.save(update_fields=["stripe_customer_id"])
        with self.assertRaises(BillingError) as billing_context:
            billing_session.initialize_prepaid_fixed_price_plan(
                plan_tier=CustomerPlan.TIER_CLOUD_STANDARD,
                billing_cycle_anchor=billing_cycle_anchor,
            )
        self.assertEqual(
            "no_plan_offer",
            billing_context.exception.error_description,
        )

        billing_session.set_required_plan_tier(CustomerPlan.TIER_CLOUD_STANDARD)
        billing_session.configure_fixed_price_plan(1000, None)
        self.assertEqual(realm.plan_type, Realm.PLAN_TYPE_SELF_HOSTED)
        billing_session.initialize_prepaid_fixed_price_plan(
            plan_tier=CustomerPlan.TIER_CLOUD_STANDARD,
            billing_cycle_anchor=billing_cycle_anchor,
        )
        self.assertEqual(realm.plan_type, Realm.PLAN_TYPE_STANDARD)
        plan = CustomerPlan.objects.first()
        assert plan is not None
        self.assertEqual(plan.fixed_price, 100000)
        self.assertEqual(plan.billing_cycle_anchor, billing_cycle_anchor)
        license_ledger = LicenseLedger.objects.filter(plan=plan, is_renewal=True).last()
        assert license_ledger is not None
        self.assertEqual(license_ledger.event_time, billing_cycle_anchor)

        # Confirm that if there is an active paid plan for the
        # customer, a new plan can not be initialized.
        with self.assertRaises(BillingError) as billing_context:
            billing_session.initialize_prepaid_fixed_price_plan(
                plan_tier=CustomerPlan.TIER_CLOUD_STANDARD,
                billing_cycle_anchor=billing_cycle_anchor,
            )
        self.assertEqual(
            "on_paid_plan",
            billing_context.exception.error_description,
        )

    def test_initialize_fixed_price_plan_remote_realm(self) -> None:
        billing_cycle_anchor = datetime(2012, 1, 1, 1, 1, 1, tzinfo=timezone.utc)
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

        # Requires a Customer object for the billing entity.
        billing_session = RemoteRealmBillingSession(remote_realm)
        with self.assertRaises(BillingError) as billing_context:
            billing_session.initialize_prepaid_fixed_price_plan(
                plan_tier=CustomerPlan.TIER_SELF_HOSTED_BASIC,
                billing_cycle_anchor=billing_cycle_anchor,
            )
        self.assertEqual(
            "no_customer",
            billing_context.exception.error_description,
        )

        # Requires that the Customer object is linked to a
        # customer ID in Stripe.
        billing_session.update_or_create_customer()
        with self.assertRaises(BillingError) as billing_context:
            billing_session.initialize_prepaid_fixed_price_plan(
                plan_tier=CustomerPlan.TIER_CLOUD_STANDARD,
                billing_cycle_anchor=billing_cycle_anchor,
            )
        self.assertEqual(
            "no_stripe_id",
            billing_context.exception.error_description,
        )

        # Requires a fixed price plan offer to be configured
        # for the customer.
        customer = billing_session.get_customer()
        assert customer is not None
        customer.stripe_customer_id = "cus_123"
        customer.save(update_fields=["stripe_customer_id"])
        with self.assertRaises(BillingError) as billing_context:
            billing_session.initialize_prepaid_fixed_price_plan(
                plan_tier=CustomerPlan.TIER_CLOUD_STANDARD,
                billing_cycle_anchor=billing_cycle_anchor,
            )
        self.assertEqual(
            "no_plan_offer",
            billing_context.exception.error_description,
        )

        billing_session.set_required_plan_tier(CustomerPlan.TIER_SELF_HOSTED_BASIC)
        billing_session.configure_fixed_price_plan(1200, None)
        self.assertEqual(remote_realm.plan_type, RemoteRealm.PLAN_TYPE_SELF_MANAGED)
        with mock.patch(
            "corporate.lib.stripe.RemoteRealmBillingSession.current_counts_for_billed_users",
            return_value=BillingUserCounts(60, 0),
        ):
            billing_session.initialize_prepaid_fixed_price_plan(
                plan_tier=CustomerPlan.TIER_SELF_HOSTED_BASIC,
                billing_cycle_anchor=billing_cycle_anchor,
            )
        self.assertEqual(remote_realm.plan_type, RemoteRealm.PLAN_TYPE_BASIC)
        plan = CustomerPlan.objects.first()
        assert plan is not None
        self.assertEqual(plan.fixed_price, 120000)
        self.assertEqual(plan.billing_cycle_anchor, billing_cycle_anchor)
        license_ledger = LicenseLedger.objects.filter(plan=plan, is_renewal=True).last()
        assert license_ledger is not None
        self.assertEqual(license_ledger.event_time, billing_cycle_anchor)

        # Confirm that if there is an active paid plan for the
        # customer, a new plan can not be initialized.
        with self.assertRaises(BillingError) as billing_context:
            billing_session.initialize_prepaid_fixed_price_plan(
                plan_tier=CustomerPlan.TIER_CLOUD_STANDARD,
                billing_cycle_anchor=billing_cycle_anchor,
            )
        self.assertEqual(
            "on_paid_plan",
            billing_context.exception.error_description,
        )

    def test_initialize_fixed_price_plan_remote_server(self) -> None:
        billing_cycle_anchor = datetime(2012, 1, 1, 1, 1, 1, tzinfo=timezone.utc)
        server_uuid = str(uuid.uuid4())
        remote_server = RemoteZulipServer.objects.create(
            uuid=server_uuid,
            api_key="magic_secret_api_key",
            hostname="demo.example.com",
            contact_email="email@example.com",
        )

        # Requires a Customer object for the billing entity.
        billing_session = RemoteServerBillingSession(remote_server)
        with self.assertRaises(BillingError) as billing_context:
            billing_session.initialize_prepaid_fixed_price_plan(
                plan_tier=CustomerPlan.TIER_SELF_HOSTED_BASIC,
                billing_cycle_anchor=billing_cycle_anchor,
            )
        self.assertEqual(
            "no_customer",
            billing_context.exception.error_description,
        )

        # Requires that the Customer object is linked to a
        # customer ID in Stripe.
        billing_session.update_or_create_customer()
        with self.assertRaises(BillingError) as billing_context:
            billing_session.initialize_prepaid_fixed_price_plan(
                plan_tier=CustomerPlan.TIER_CLOUD_STANDARD,
                billing_cycle_anchor=billing_cycle_anchor,
            )
        self.assertEqual(
            "no_stripe_id",
            billing_context.exception.error_description,
        )

        # Requires a fixed price plan offer to be configured
        # for the customer.
        customer = billing_session.get_customer()
        assert customer is not None
        customer.stripe_customer_id = "cus_123"
        customer.save(update_fields=["stripe_customer_id"])
        with self.assertRaises(BillingError) as billing_context:
            billing_session.initialize_prepaid_fixed_price_plan(
                plan_tier=CustomerPlan.TIER_CLOUD_STANDARD,
                billing_cycle_anchor=billing_cycle_anchor,
            )
        self.assertEqual(
            "no_plan_offer",
            billing_context.exception.error_description,
        )

        billing_session.set_required_plan_tier(CustomerPlan.TIER_SELF_HOSTED_BASIC)
        billing_session.configure_fixed_price_plan(1200, None)
        self.assertEqual(remote_server.plan_type, RemoteRealm.PLAN_TYPE_SELF_MANAGED)
        with mock.patch(
            "corporate.lib.stripe.RemoteServerBillingSession.current_counts_for_billed_users",
            return_value=BillingUserCounts(60, 0),
        ):
            billing_session.initialize_prepaid_fixed_price_plan(
                plan_tier=CustomerPlan.TIER_SELF_HOSTED_BASIC,
                billing_cycle_anchor=billing_cycle_anchor,
            )
        self.assertEqual(remote_server.plan_type, RemoteRealm.PLAN_TYPE_BASIC)
        plan = CustomerPlan.objects.first()
        assert plan is not None
        self.assertEqual(plan.fixed_price, 120000)
        self.assertEqual(plan.billing_cycle_anchor, billing_cycle_anchor)
        license_ledger = LicenseLedger.objects.filter(plan=plan, is_renewal=True).last()
        assert license_ledger is not None
        self.assertEqual(license_ledger.event_time, billing_cycle_anchor)

        # Confirm that if there is an active paid plan for the
        # customer, a new plan can not be initialized.
        with self.assertRaises(BillingError) as billing_context:
            billing_session.initialize_prepaid_fixed_price_plan(
                plan_tier=CustomerPlan.TIER_CLOUD_STANDARD,
                billing_cycle_anchor=billing_cycle_anchor,
            )
        self.assertEqual(
            "on_paid_plan",
            billing_context.exception.error_description,
        )


class LicenseLedgerTest(StripeTestCase):
    def test_add_plan_renewal_if_needed(self) -> None:
        with time_machine.travel(self.now, tick=False):
            self.local_upgrade(
                self.seat_count, True, CustomerPlan.BILLING_SCHEDULE_ANNUAL, True, False
            )
        self.assertEqual(LicenseLedger.objects.count(), 1)
        plan = CustomerPlan.objects.get()
        # Plan hasn't renewed yet
        realm = plan.customer.realm
        billing_session = RealmBillingSession(user=None, realm=realm)
        billing_session.make_end_of_cycle_updates_if_needed(
            plan, self.next_year - timedelta(days=1)
        )
        self.assertEqual(LicenseLedger.objects.count(), 1)
        # Plan needs to renew
        # TODO: do_deactivate_user for a user, so that licenses_at_next_renewal != licenses
        new_plan, ledger_entry = billing_session.make_end_of_cycle_updates_if_needed(
            plan, self.next_year
        )
        self.assertIsNone(new_plan)
        self.assertEqual(LicenseLedger.objects.count(), 2)
        assert ledger_entry is not None
        self.assertEqual(ledger_entry.plan, plan)
        self.assertTrue(ledger_entry.is_renewal)
        self.assertEqual(ledger_entry.event_time, self.next_year)
        self.assertEqual(ledger_entry.licenses, self.seat_count)
        self.assertEqual(ledger_entry.licenses_at_next_renewal, self.seat_count)
        # Plan needs to renew, but we already added the plan_renewal ledger entry
        billing_session.make_end_of_cycle_updates_if_needed(
            plan, self.next_year + timedelta(days=1)
        )
        self.assertEqual(LicenseLedger.objects.count(), 2)

    def test_update_license_ledger_if_needed(self) -> None:
        realm = get_realm("zulip")
        billing_session = RealmBillingSession(user=None, realm=realm)
        # Test no Customer
        billing_session.update_license_ledger_if_needed(self.now)
        self.assertFalse(LicenseLedger.objects.exists())
        # Test plan not automanaged
        with time_machine.travel(self.now, tick=False):
            self.local_upgrade(
                self.seat_count + 1, False, CustomerPlan.BILLING_SCHEDULE_ANNUAL, True, False
            )
        plan = CustomerPlan.objects.get()
        self.assertEqual(LicenseLedger.objects.count(), 1)
        self.assertEqual(plan.licenses(), self.seat_count + 1)
        self.assertEqual(plan.licenses_at_next_renewal(), self.seat_count + 1)
        billing_session.update_license_ledger_if_needed(self.now)
        self.assertEqual(LicenseLedger.objects.count(), 1)
        # Test no active plan
        plan.automanage_licenses = True
        plan.status = CustomerPlan.ENDED
        plan.save(update_fields=["automanage_licenses", "status"])
        billing_session.update_license_ledger_if_needed(self.now)
        self.assertEqual(LicenseLedger.objects.count(), 1)
        # Test update needed
        plan.status = CustomerPlan.ACTIVE
        plan.save(update_fields=["status"])
        billing_session.update_license_ledger_if_needed(self.now)
        self.assertEqual(LicenseLedger.objects.count(), 2)

    def test_update_license_ledger_for_automanaged_plan(self) -> None:
        realm = get_realm("zulip")
        with time_machine.travel(self.now, tick=False):
            self.local_upgrade(
                self.seat_count, True, CustomerPlan.BILLING_SCHEDULE_ANNUAL, True, False
            )
        plan = CustomerPlan.objects.first()
        assert plan is not None
        self.assertEqual(plan.licenses(), self.seat_count)
        self.assertEqual(plan.licenses_at_next_renewal(), self.seat_count)

        billing_session = RealmBillingSession(user=None, realm=realm)
        # Simple increase
        with patch("corporate.lib.stripe.get_latest_seat_count", return_value=23):
            billing_session.update_license_ledger_for_automanaged_plan(plan, self.now)
            self.assertEqual(plan.licenses(), 23)
            self.assertEqual(plan.licenses_at_next_renewal(), 23)
        # Decrease
        with patch("corporate.lib.stripe.get_latest_seat_count", return_value=20):
            billing_session.update_license_ledger_for_automanaged_plan(plan, self.now)
            self.assertEqual(plan.licenses(), 23)
            self.assertEqual(plan.licenses_at_next_renewal(), 20)
        # Increase, but not past high watermark
        with patch("corporate.lib.stripe.get_latest_seat_count", return_value=21):
            billing_session.update_license_ledger_for_automanaged_plan(plan, self.now)
            self.assertEqual(plan.licenses(), 23)
            self.assertEqual(plan.licenses_at_next_renewal(), 21)
        # Increase, but after renewal date, and below last year's high watermark
        with patch("corporate.lib.stripe.get_latest_seat_count", return_value=22):
            billing_session.update_license_ledger_for_automanaged_plan(
                plan, self.next_year + timedelta(seconds=1)
            )
            self.assertEqual(plan.licenses(), 22)
            self.assertEqual(plan.licenses_at_next_renewal(), 22)

        ledger_entries = list(
            LicenseLedger.objects.values_list(
                "is_renewal", "event_time", "licenses", "licenses_at_next_renewal"
            ).order_by("id")
        )
        self.assertEqual(
            ledger_entries,
            [
                (True, self.now, self.seat_count, self.seat_count),
                (False, self.now, 23, 23),
                (False, self.now, 23, 20),
                (False, self.now, 23, 21),
                (True, self.next_year, 21, 21),
                (False, self.next_year + timedelta(seconds=1), 22, 22),
            ],
        )

    def test_update_license_ledger_for_manual_plan(self) -> None:
        realm = get_realm("zulip")

        with time_machine.travel(self.now, tick=False):
            self.local_upgrade(
                self.seat_count + 1, False, CustomerPlan.BILLING_SCHEDULE_ANNUAL, True, False
            )

        billing_session = RealmBillingSession(user=None, realm=realm)
        plan = get_current_plan_by_realm(realm)
        assert plan is not None

        with patch("corporate.lib.stripe.get_latest_seat_count", return_value=self.seat_count):
            billing_session.update_license_ledger_for_manual_plan(
                plan, self.now, licenses=self.seat_count + 3
            )
            self.assertEqual(plan.licenses(), self.seat_count + 3)
            self.assertEqual(plan.licenses_at_next_renewal(), self.seat_count + 3)

        with (
            patch("corporate.lib.stripe.get_latest_seat_count", return_value=self.seat_count),
            self.assertRaises(AssertionError),
        ):
            billing_session.update_license_ledger_for_manual_plan(
                plan, self.now, licenses=self.seat_count
            )

        with patch("corporate.lib.stripe.get_latest_seat_count", return_value=self.seat_count):
            billing_session.update_license_ledger_for_manual_plan(
                plan, self.now, licenses_at_next_renewal=self.seat_count
            )
            self.assertEqual(plan.licenses(), self.seat_count + 3)
            self.assertEqual(plan.licenses_at_next_renewal(), self.seat_count)

        with (
            patch("corporate.lib.stripe.get_latest_seat_count", return_value=self.seat_count),
            self.assertRaises(AssertionError),
        ):
            billing_session.update_license_ledger_for_manual_plan(
                plan, self.now, licenses_at_next_renewal=self.seat_count - 1
            )

        with patch("corporate.lib.stripe.get_latest_seat_count", return_value=self.seat_count):
            billing_session.update_license_ledger_for_manual_plan(
                plan, self.now, licenses=self.seat_count + 10
            )
            self.assertEqual(plan.licenses(), self.seat_count + 10)
            self.assertEqual(plan.licenses_at_next_renewal(), self.seat_count + 10)

        billing_session.make_end_of_cycle_updates_if_needed(plan, self.next_year)
        self.assertEqual(plan.licenses(), self.seat_count + 10)

        ledger_entries = list(
            LicenseLedger.objects.values_list(
                "is_renewal", "event_time", "licenses", "licenses_at_next_renewal"
            ).order_by("id")
        )

        self.assertEqual(
            ledger_entries,
            [
                (True, self.now, self.seat_count + 1, self.seat_count + 1),
                (False, self.now, self.seat_count + 3, self.seat_count + 3),
                (False, self.now, self.seat_count + 3, self.seat_count),
                (False, self.now, self.seat_count + 10, self.seat_count + 10),
                (True, self.next_year, self.seat_count + 10, self.seat_count + 10),
            ],
        )

        with self.assertRaises(AssertionError):
            billing_session.update_license_ledger_for_manual_plan(plan, self.now)

    def test_user_changes(self) -> None:
        self.local_upgrade(self.seat_count, True, CustomerPlan.BILLING_SCHEDULE_ANNUAL, True, False)
        user = do_create_user("email", "password", get_realm("zulip"), "name", acting_user=None)
        do_deactivate_user(user, acting_user=None)
        do_reactivate_user(user, acting_user=None)

        # Not a proper use of do_activate_mirror_dummy_user, but fine for this test
        change_user_is_active(user, False)
        user.is_mirror_dummy = True
        user.save(update_fields=["is_mirror_dummy"])
        do_activate_mirror_dummy_user(user, acting_user=None)
        # Add a guest user
        guest = do_create_user(
            "guest_email",
            "guest_password",
            get_realm("zulip"),
            "guest_name",
            role=UserProfile.ROLE_GUEST,
            acting_user=None,
        )
        # Change guest user role to member
        self.set_user_role(guest, UserProfile.ROLE_MEMBER)
        # Change again to moderator, no LicenseLedger created
        self.set_user_role(guest, UserProfile.ROLE_MODERATOR)
        ledger_entries = list(
            LicenseLedger.objects.values_list(
                "is_renewal", "licenses", "licenses_at_next_renewal"
            ).order_by("id")
        )
        self.assertEqual(
            ledger_entries,
            [
                (True, self.seat_count, self.seat_count),
                (False, self.seat_count + 1, self.seat_count + 1),
                (False, self.seat_count + 1, self.seat_count),
                (False, self.seat_count + 1, self.seat_count + 1),
                (False, self.seat_count + 1, self.seat_count + 1),
                (False, self.seat_count + 1, self.seat_count + 1),
                (False, self.seat_count + 2, self.seat_count + 2),
            ],
        )

    def test_toggle_license_management(self) -> None:
        self.local_upgrade(self.seat_count, True, CustomerPlan.BILLING_SCHEDULE_ANNUAL, True, False)
        plan = get_current_plan_by_realm(get_realm("zulip"))
        assert plan is not None
        self.assertEqual(plan.automanage_licenses, True)
        self.assertEqual(plan.licenses(), self.seat_count)
        self.assertEqual(plan.licenses_at_next_renewal(), self.seat_count)
        billing_session = RealmBillingSession(user=None, realm=get_realm("zulip"))
        update_plan_request = UpdatePlanRequest(
            status=None,
            licenses=None,
            licenses_at_next_renewal=None,
            schedule=None,
            toggle_license_management=True,
        )
        billing_session.do_update_plan(update_plan_request)
        plan.refresh_from_db()
        self.assertEqual(plan.automanage_licenses, False)

        billing_session.do_update_plan(update_plan_request)
        plan.refresh_from_db()
        self.assertEqual(plan.automanage_licenses, True)


class InvoiceTest(StripeTestCase):
    def test_invoicing_status_is_started(self) -> None:
        # local_upgrade uses hamlet as user, therefore realm is zulip.
        self.local_upgrade(self.seat_count, True, CustomerPlan.BILLING_SCHEDULE_ANNUAL, True, False)
        plan = CustomerPlan.objects.first()
        assert plan is not None
        plan.invoicing_status = CustomerPlan.INVOICING_STATUS_STARTED
        plan.save(update_fields=["invoicing_status"])
        with self.assertRaises(NotImplementedError):
            billing_session = RealmBillingSession(realm=get_realm("zulip"))
            billing_session.invoice_plan(assert_is_not_none(CustomerPlan.objects.first()), self.now)

    def test_invoice_plan_without_stripe_customer(self) -> None:
        # local_upgrade uses hamlet as user, therefore realm is zulip.
        realm = get_realm("zulip")
        self.local_upgrade(
            self.seat_count, True, CustomerPlan.BILLING_SCHEDULE_ANNUAL, False, False
        )
        plan = get_current_plan_by_realm(realm)
        assert plan is not None
        plan.customer.stripe_customer_id = None
        plan.customer.save(update_fields=["stripe_customer_id"])
        with self.assertRaises(BillingError) as context:
            billing_session = RealmBillingSession(realm=realm)
            billing_session.invoice_plan(plan, timezone_now())
        self.assertRegex(
            context.exception.error_description,
            "Customer has a paid plan without a Stripe customer ID:",
        )

    @mock_stripe()
    def test_validate_licenses_for_manual_plan_management(self, *mocks: Mock) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)

        # Upgrade with one extra license
        with (
            time_machine.travel(self.now, tick=False),
            patch("corporate.lib.stripe.MIN_INVOICED_LICENSES", 3),
        ):
            self.upgrade(invoice=True, licenses=self.seat_count + 1)

        # Set renewal licenses to current seat count
        with (
            time_machine.travel(self.now, tick=False),
            patch("corporate.lib.stripe.MIN_INVOICED_LICENSES", 3),
        ):
            result = self.client_billing_patch(
                "/billing/plan",
                {"licenses_at_next_renewal": self.seat_count},
            )
            self.assert_json_success(result)

        # Add an extra user
        do_create_user(
            "email-extra-user",
            "password-extra-user",
            get_realm("zulip"),
            "name-extra-user",
            acting_user=None,
        )
        with self.assertLogs("corporate.stripe", level="ERROR") as m:
            invoice_plans_as_needed(self.next_year)
        self.assertIn(
            "ERROR:corporate.stripe:Invoicing failed: Customer.id:",
            m.output[0],
        )
        self.assertIn(
            "Customer has not manually updated plan for current license count:",
            m.output[0],
        )

    @mock_stripe()
    def test_invoice_plan(self, *mocks: Mock) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        with time_machine.travel(self.now, tick=False):
            self.add_card_and_upgrade(user)
        realm = get_realm("zulip")
        billing_session = RealmBillingSession(user=user, realm=realm)
        # Increase
        with patch("corporate.lib.stripe.get_latest_seat_count", return_value=self.seat_count + 3):
            billing_session.update_license_ledger_if_needed(self.now + timedelta(days=100))
        # Decrease
        with patch("corporate.lib.stripe.get_latest_seat_count", return_value=self.seat_count):
            billing_session.update_license_ledger_if_needed(self.now + timedelta(days=200))
        # Increase, but not past high watermark
        with patch("corporate.lib.stripe.get_latest_seat_count", return_value=self.seat_count + 1):
            billing_session.update_license_ledger_if_needed(self.now + timedelta(days=300))
        # Increase, but after renewal date, and below last year's high watermark
        with patch("corporate.lib.stripe.get_latest_seat_count", return_value=self.seat_count + 2):
            billing_session.update_license_ledger_if_needed(self.now + timedelta(days=400))
        # Increase, but after event_time
        with patch("corporate.lib.stripe.get_latest_seat_count", return_value=self.seat_count + 3):
            billing_session.update_license_ledger_if_needed(self.now + timedelta(days=500))
        plan = CustomerPlan.objects.first()
        assert plan is not None
        billing_session.invoice_plan(plan, self.now + timedelta(days=400))
        stripe_customer_id = plan.customer.stripe_customer_id
        assert stripe_customer_id is not None
        [invoice0, _invoice1] = iter(stripe.Invoice.list(customer=stripe_customer_id))
        self.assertIsNotNone(invoice0.status_transitions.finalized_at)
        [item0, item1, item2] = iter(invoice0.lines)

        self.assertEqual(item0.amount, int(8000 * (1 - ((400 - 366) / 365)) + 0.5))
        self.assertEqual(item0.description, "Additional Zulip Cloud Standard license")
        self.assertFalse(item0.discountable)
        self.assertEqual(item0.period.start, datetime_to_timestamp(self.now + timedelta(days=400)))
        self.assertEqual(
            item0.period.end, datetime_to_timestamp(self.now + timedelta(days=2 * 365 + 1))
        )
        self.assertEqual(item0.quantity, 1)

        self.assertEqual(item1.amount, 3 * int(8000 * (366 - 100) / 366 + 0.5))
        self.assertEqual(item1.description, "Additional Zulip Cloud Standard license")
        self.assertFalse(item1.discountable)
        self.assertEqual(item1.period.start, datetime_to_timestamp(self.now + timedelta(days=100)))
        self.assertEqual(item1.period.end, datetime_to_timestamp(self.now + timedelta(days=366)))
        self.assertEqual(item1.quantity, 3)

        self.assertEqual(item2.amount, 8000 * (self.seat_count + 1))
        self.assertEqual(item2.description, "Zulip Cloud Standard - renewal")
        self.assertFalse(item2.discountable)
        self.assertEqual(item2.period.start, datetime_to_timestamp(self.now + timedelta(days=366)))
        self.assertEqual(
            item2.period.end, datetime_to_timestamp(self.now + timedelta(days=2 * 365 + 1))
        )
        self.assertEqual(item2.quantity, self.seat_count + 1)

    @mock_stripe()
    def test_invoice_plan_bundle_additional_licenses(self, *mocks: Mock) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        with time_machine.travel(self.now, tick=False):
            self.add_card_and_upgrade(user)
        realm = get_realm("zulip")
        billing_session = RealmBillingSession(user=user, realm=realm)
        # Increase by 300 additional licenses in the first month of the
        # annual plan.
        updated_seat_count = self.seat_count
        for i in range(50):
            updated_seat_count += 1
            with patch(
                "corporate.lib.stripe.get_latest_seat_count", return_value=updated_seat_count
            ):
                billing_session.update_license_ledger_if_needed(
                    self.now + timedelta(days=10, seconds=i)
                )
        for i in range(100):
            updated_seat_count += 1
            with patch(
                "corporate.lib.stripe.get_latest_seat_count", return_value=updated_seat_count
            ):
                billing_session.update_license_ledger_if_needed(
                    self.now + timedelta(days=15, seconds=i)
                )
        for i in range(100):
            updated_seat_count += 1
            with patch(
                "corporate.lib.stripe.get_latest_seat_count", return_value=updated_seat_count
            ):
                billing_session.update_license_ledger_if_needed(
                    self.now + timedelta(days=20, seconds=i)
                )
        # Remove 20 active licenses to confirm we're still handling these ledger entries
        # correctly when bundling.
        for i in range(20):
            updated_seat_count -= 1
            with patch(
                "corporate.lib.stripe.get_latest_seat_count", return_value=updated_seat_count
            ):
                billing_session.update_license_ledger_if_needed(
                    self.now + timedelta(days=22, seconds=i)
                )
        for i in range(70):
            updated_seat_count += 1
            with patch(
                "corporate.lib.stripe.get_latest_seat_count", return_value=updated_seat_count
            ):
                billing_session.update_license_ledger_if_needed(
                    self.now + timedelta(days=25, seconds=i)
                )
        plan = CustomerPlan.objects.first()
        assert plan is not None
        billing_session.invoice_plan(plan, self.next_month)
        stripe_customer_id = plan.customer.stripe_customer_id
        assert stripe_customer_id is not None
        [invoice0, _invoice1] = iter(stripe.Invoice.list(customer=stripe_customer_id))
        self.assertIsNotNone(invoice0.status_transitions.finalized_at)
        [item0, item1, item2, item3] = iter(invoice0.lines.data)

        self.assertEqual(item0.amount, 50 * int(8000 * (366 - 25) / 366 + 0.5))
        self.assertEqual(item0.description, "Additional Zulip Cloud Standard license")
        self.assertFalse(item0.discountable)
        # We have to adjust the start datetime for the 20 license ledger
        # entries (by 20 seconds) that were for licenses that were already
        # paid for in the billing period.
        self.assertEqual(
            item0.period.start, datetime_to_timestamp(self.now + timedelta(days=25, seconds=20))
        )
        self.assertEqual(item0.period.end, datetime_to_timestamp(self.next_year))
        self.assertEqual(item0.quantity, 50)

        self.assertEqual(item1.amount, 100 * int(8000 * (366 - 20) / 366 + 0.5))
        self.assertEqual(item1.description, "Additional Zulip Cloud Standard license")
        self.assertFalse(item1.discountable)
        self.assertEqual(item1.period.start, datetime_to_timestamp(self.now + timedelta(days=20)))
        self.assertEqual(item1.period.end, datetime_to_timestamp(self.next_year))
        self.assertEqual(item1.quantity, 100)

        self.assertEqual(item2.amount, 100 * int(8000 * (366 - 15) / 366 + 0.5))
        self.assertEqual(item2.description, "Additional Zulip Cloud Standard license")
        self.assertFalse(item2.discountable)
        self.assertEqual(item2.period.start, datetime_to_timestamp(self.now + timedelta(days=15)))
        self.assertEqual(item2.period.end, datetime_to_timestamp(self.next_year))
        self.assertEqual(item2.quantity, 100)

        self.assertEqual(item3.amount, 50 * int(8000 * (366 - 10) / 366 + 0.5))
        self.assertEqual(item3.description, "Additional Zulip Cloud Standard license")
        self.assertFalse(item3.discountable)
        self.assertEqual(item3.period.start, datetime_to_timestamp(self.now + timedelta(days=10)))
        self.assertEqual(item3.period.end, datetime_to_timestamp(self.next_year))
        self.assertEqual(item3.quantity, 50)

    @mock_stripe()
    def test_fixed_price_plans(self, *mocks: Mock) -> None:
        # Also tests charge_automatically=False
        user = self.example_user("hamlet")
        self.login_user(user)
        with time_machine.travel(self.now, tick=False):
            self.upgrade(invoice=True)
        plan = CustomerPlan.objects.first()
        assert plan is not None
        plan.fixed_price = 100
        plan.price_per_license = 0
        plan.save(update_fields=["fixed_price", "price_per_license"])
        user.realm.refresh_from_db()
        billing_session = RealmBillingSession(realm=user.realm)
        billing_session.invoice_plan(plan, self.next_year)
        stripe_customer_id = plan.customer.stripe_customer_id
        assert stripe_customer_id is not None
        [invoice0, _invoice1] = iter(stripe.Invoice.list(customer=stripe_customer_id))
        self.assertEqual(invoice0.collection_method, "send_invoice")
        [item] = iter(invoice0.lines)
        self.assertEqual(item.amount, 100)
        self.assertEqual(item.description, "Zulip Cloud Standard - renewal")
        self.assertFalse(item.discountable)
        self.assertEqual(item.period.start, datetime_to_timestamp(self.next_year))
        self.assertEqual(
            item.period.end, datetime_to_timestamp(self.next_year + timedelta(days=365))
        )
        self.assertEqual(item.quantity, 1)

    @mock_stripe()
    def test_upgrade_to_fixed_price_plus_plan(self, *mocks: Mock) -> None:
        iago = self.example_user("iago")
        hamlet = self.example_user("hamlet")
        realm = get_realm("zulip")
        self.assertEqual(realm.plan_type, Realm.PLAN_TYPE_SELF_HOSTED)

        self.login_user(hamlet)
        with time_machine.travel(self.now, tick=False):
            self.upgrade(invoice=True)
        plan = CustomerPlan.objects.first()
        assert plan is not None
        self.assertIsNone(plan.end_date)
        self.assertEqual(plan.tier, CustomerPlan.TIER_CLOUD_STANDARD)
        realm.refresh_from_db()
        self.assertEqual(realm.plan_type, Realm.PLAN_TYPE_STANDARD)

        next_billing_cycle = get_next_billing_cycle_for_plan(plan)
        plan_end_date_string = next_billing_cycle.date().isoformat()
        plan_end_date = datetime.combine(
            date.fromisoformat(plan_end_date_string), time(0, 0, 0), tzinfo=timezone.utc
        )

        self.logout()
        self.login_user(iago)

        result = self.client_post(
            "/activity/support",
            {
                "realm_id": f"{realm.id}",
                "required_plan_tier": f"{CustomerPlanOffer.TIER_CLOUD_PLUS}",
            },
        )
        self.assert_in_success_response(
            ["Required plan tier for zulip set to Zulip Cloud Plus."],
            result,
        )

        with time_machine.travel(self.now, tick=False):
            result = self.client_post(
                "/activity/support",
                {
                    "realm_id": f"{realm.id}",
                    "plan_end_date": plan_end_date_string,
                },
            )
        self.assert_in_success_response(
            [f"Current plan for zulip updated to end on {plan_end_date_string}."],
            result,
        )

        plan.refresh_from_db()
        self.assertEqual(plan.end_date, plan_end_date)

        result = self.client_post(
            "/activity/support",
            {
                "realm_id": f"{realm.id}",
                "fixed_price": 360,
            },
        )
        self.assert_in_success_response(
            [f"Fixed price Zulip Cloud Plus plan scheduled to start on {plan_end_date_string}."],
            result,
        )

        plan.refresh_from_db()
        self.assertEqual(plan.status, CustomerPlan.SWITCH_PLAN_TIER_AT_PLAN_END)
        self.assertEqual(plan.next_invoice_date, plan_end_date)
        new_plan = CustomerPlan.objects.filter(fixed_price__isnull=False).first()
        assert new_plan is not None
        self.assertEqual(new_plan.next_invoice_date, plan_end_date)
        self.assertEqual(
            new_plan.invoicing_status, CustomerPlan.INVOICING_STATUS_INITIAL_INVOICE_TO_BE_SENT
        )

        with time_machine.travel(next_billing_cycle, tick=False):
            invoice_plans_as_needed()

        plan.refresh_from_db()
        self.assertEqual(plan.status, CustomerPlan.ENDED)
        self.assertEqual(plan.next_invoice_date, None)

        new_plan.refresh_from_db()
        self.assertEqual(new_plan.tier, CustomerPlan.TIER_CLOUD_PLUS)
        self.assertIsNotNone(new_plan.fixed_price)
        self.assertIsNone(new_plan.price_per_license)

        realm.refresh_from_db()
        self.assertEqual(realm.plan_type, Realm.PLAN_TYPE_PLUS)

        # Visit /billing
        self.logout()
        self.login_user(hamlet)
        with time_machine.travel(plan_end_date + timedelta(days=1), tick=False):
            response = self.client_get(f"{self.billing_session.billing_base_url}/billing/")
        for substring in [
            "Zulip Cloud Plus",
            "Annual",
            "Invoice",
            "This is a fixed-price plan",
            "You will be contacted by Zulip Sales",
        ]:
            self.assert_in_response(substring, response)
        self.assert_not_in_success_response(["Update card"], response)

    def test_no_invoice_needed(self) -> None:
        # local_upgrade uses hamlet as user, therefore realm is zulip.
        with time_machine.travel(self.now, tick=False):
            self.local_upgrade(
                self.seat_count, True, CustomerPlan.BILLING_SCHEDULE_ANNUAL, True, False
            )
        plan = CustomerPlan.objects.first()
        assert plan is not None
        self.assertEqual(plan.next_invoice_date, self.next_month)
        # Test this doesn't make any calls to stripe.Invoice or stripe.InvoiceItem
        assert plan.customer.realm is not None
        billing_session = RealmBillingSession(realm=plan.customer.realm)
        billing_session.invoice_plan(plan, self.next_month)
        plan = CustomerPlan.objects.first()
        # Test that we still update next_invoice_date
        assert plan is not None
        self.assertEqual(plan.next_invoice_date, self.next_month + timedelta(days=29))

    def test_invoice_plans_as_needed(self) -> None:
        with time_machine.travel(self.now, tick=False):
            self.local_upgrade(
                self.seat_count, True, CustomerPlan.BILLING_SCHEDULE_ANNUAL, True, False
            )
        plan = CustomerPlan.objects.first()
        assert plan is not None
        self.assertEqual(plan.next_invoice_date, self.next_month)
        # Test nothing needed to be done
        with patch("corporate.lib.stripe.BillingSession.invoice_plan") as mocked:
            invoice_plans_as_needed(self.next_month - timedelta(days=1))
        mocked.assert_not_called()
        # Test something needing to be done
        invoice_plans_as_needed(self.next_month)
        plan = CustomerPlan.objects.first()
        assert plan is not None
        self.assertEqual(plan.next_invoice_date, self.next_month + timedelta(days=29))

    @mock_stripe()
    def test_invoice_for_additional_license(self, *mocks: Mock) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        with time_machine.travel(self.now, tick=False):
            self.add_card_and_upgrade(user)
        plan = CustomerPlan.objects.first()
        assert plan is not None
        self.assertEqual(plan.next_invoice_date, self.next_month)
        assert plan.customer.realm is not None
        realm = plan.customer.realm

        # Adding a guest user and then changing their role to member
        # should invoice for a pro-rated license at the next invoice
        # date on a plan with annual billing.
        with time_machine.travel(self.now + timedelta(days=5), tick=False):
            user = do_create_user(
                "email",
                "password",
                realm,
                "name",
                role=UserProfile.ROLE_GUEST,
                acting_user=None,
            )

        with time_machine.travel(self.now + timedelta(days=10), tick=False):
            self.set_user_role(user, UserProfile.ROLE_MEMBER)

        billing_session = RealmBillingSession(realm=realm)
        billing_session.invoice_plan(plan, self.next_month)
        plan = CustomerPlan.objects.first()
        assert plan is not None
        self.assertEqual(plan.next_invoice_date, self.next_month + timedelta(days=29))
        stripe_customer_id = plan.customer.stripe_customer_id
        assert stripe_customer_id is not None
        [invoice0, _invoice1] = iter(stripe.Invoice.list(customer=stripe_customer_id))
        self.assertIsNotNone(invoice0.status_transitions.finalized_at)
        [item0] = iter(invoice0.lines)
        self.assertEqual(item0.amount, int(8000 * (1 - ((366 - 356) / 366)) + 0.5))
        self.assertEqual(item0.description, "Additional Zulip Cloud Standard license")
        self.assertEqual(item0.quantity, 1)


class TestTestClasses(ZulipTestCase):
    def test_subscribe_realm_to_manual_license_management_plan(self) -> None:
        realm = get_realm("zulip")
        plan, ledger = self.subscribe_realm_to_manual_license_management_plan(
            realm, 50, 60, CustomerPlan.BILLING_SCHEDULE_ANNUAL
        )

        plan.refresh_from_db()
        self.assertEqual(plan.automanage_licenses, False)
        self.assertEqual(plan.billing_schedule, CustomerPlan.BILLING_SCHEDULE_ANNUAL)
        self.assertEqual(plan.tier, CustomerPlan.TIER_CLOUD_STANDARD)
        self.assertEqual(plan.licenses(), 50)
        self.assertEqual(plan.licenses_at_next_renewal(), 60)

        ledger.refresh_from_db()
        self.assertEqual(ledger.plan, plan)
        self.assertEqual(ledger.licenses, 50)
        self.assertEqual(ledger.licenses_at_next_renewal, 60)

        realm.refresh_from_db()
        self.assertEqual(realm.plan_type, Realm.PLAN_TYPE_STANDARD)

    def test_subscribe_realm_to_monthly_plan_on_manual_license_management(self) -> None:
        realm = get_realm("zulip")
        plan, ledger = self.subscribe_realm_to_monthly_plan_on_manual_license_management(
            realm, 20, 30
        )

        plan.refresh_from_db()
        self.assertEqual(plan.automanage_licenses, False)
        self.assertEqual(plan.billing_schedule, CustomerPlan.BILLING_SCHEDULE_MONTHLY)
        self.assertEqual(plan.tier, CustomerPlan.TIER_CLOUD_STANDARD)
        self.assertEqual(plan.licenses(), 20)
        self.assertEqual(plan.licenses_at_next_renewal(), 30)

        ledger.refresh_from_db()
        self.assertEqual(ledger.plan, plan)
        self.assertEqual(ledger.licenses, 20)
        self.assertEqual(ledger.licenses_at_next_renewal, 30)

        realm.refresh_from_db()
        self.assertEqual(realm.plan_type, Realm.PLAN_TYPE_STANDARD)


class TestRealmBillingSession(StripeTestCase):
    def test_get_audit_log_error(self) -> None:
        user = self.example_user("hamlet")
        billing_session = RealmBillingSession(user)
        fake_audit_log = typing.cast(BillingSessionEventType, 0)
        with self.assertRaisesRegex(
            BillingSessionAuditLogEventError, "Unknown audit log event type: 0"
        ):
            billing_session.get_audit_log_event(event_type=fake_audit_log)

    def test_get_customer(self) -> None:
        user = self.example_user("hamlet")
        billing_session = RealmBillingSession(user)
        customer = billing_session.get_customer()
        self.assertEqual(customer, None)

        customer = Customer.objects.create(realm=user.realm, stripe_customer_id="cus_12345")
        self.assertEqual(billing_session.get_customer(), customer)


class TestSupportBillingHelpers(StripeTestCase):
    @mock_stripe()
    def test_attach_discount_to_realm(self, *mocks: Mock) -> None:
        # Attach discount before Stripe customer exists
        support_admin = self.example_user("iago")
        user = self.example_user("hamlet")
        billing_session = RealmBillingSession(support_admin, realm=user.realm, support_session=True)

        # Cannot attach discount without a required_plan_tier set.
        with self.assertRaises(AssertionError):
            billing_session.attach_discount_to_customer(
                monthly_discounted_price=120,
                annual_discounted_price=1200,
            )
        billing_session.update_or_create_customer()

        with self.assertRaises(AssertionError):
            billing_session.attach_discount_to_customer(
                monthly_discounted_price=120,
                annual_discounted_price=1200,
            )

        billing_session.set_required_plan_tier(CustomerPlan.TIER_CLOUD_STANDARD)
        billing_session.attach_discount_to_customer(
            monthly_discounted_price=120,
            annual_discounted_price=1200,
        )
        realm_audit_log = RealmAuditLog.objects.filter(
            event_type=AuditLogEventType.REALM_DISCOUNT_CHANGED
        ).last()
        assert realm_audit_log is not None
        expected_extra_data = {
            "new_annual_discounted_price": 1200,
            "new_monthly_discounted_price": 120,
            "old_annual_discounted_price": 0,
            "old_monthly_discounted_price": 0,
        }
        self.assertEqual(realm_audit_log.extra_data, expected_extra_data)
        self.login_user(user)
        # Check that the discount appears in page_params
        self.assert_in_success_response(["85"], self.client_get("/upgrade/"))
        # Check that the customer was charged the discounted amount
        self.add_card_and_upgrade(user)
        customer = Customer.objects.first()
        assert customer is not None
        assert customer.stripe_customer_id is not None
        [charge] = iter(stripe.Charge.list(customer=customer.stripe_customer_id))
        self.assertEqual(1200 * self.seat_count, charge.amount)
        stripe_customer_id = customer.stripe_customer_id
        assert stripe_customer_id is not None
        [invoice] = iter(stripe.Invoice.list(customer=stripe_customer_id))
        self.assertEqual(
            [1200 * self.seat_count],
            [item.amount for item in invoice.lines],
        )
        # Check CustomerPlan reflects the discount
        plan = CustomerPlan.objects.get(price_per_license=1200, discount="85")

        # Attach discount to existing Stripe customer
        plan.status = CustomerPlan.ENDED
        plan.save(update_fields=["status"])
        billing_session = RealmBillingSession(support_admin, realm=user.realm, support_session=True)
        billing_session.set_required_plan_tier(CustomerPlan.TIER_CLOUD_STANDARD)
        billing_session.attach_discount_to_customer(
            monthly_discounted_price=600,
            annual_discounted_price=6000,
        )
        with time_machine.travel(self.now, tick=False):
            self.add_card_and_upgrade(
                user, license_management="automatic", billing_modality="charge_automatically"
            )
        [charge, _] = iter(stripe.Charge.list(customer=customer.stripe_customer_id))
        self.assertEqual(6000 * self.seat_count, charge.amount)
        stripe_customer_id = customer.stripe_customer_id
        assert stripe_customer_id is not None
        [invoice, _] = iter(stripe.Invoice.list(customer=stripe_customer_id))
        self.assertEqual(
            [6000 * self.seat_count],
            [item.amount for item in invoice.lines],
        )
        plan = CustomerPlan.objects.get(price_per_license=6000, discount=Decimal(25))

        billing_session = RealmBillingSession(support_admin, realm=user.realm, support_session=True)
        billing_session.attach_discount_to_customer(
            monthly_discounted_price=400,
            annual_discounted_price=4000,
        )
        plan.refresh_from_db()
        self.assertEqual(plan.price_per_license, 4000)
        self.assertEqual(plan.discount, "50")
        customer.refresh_from_db()
        self.assertEqual(customer.monthly_discounted_price, 400)
        self.assertEqual(customer.annual_discounted_price, 4000)
        # Fast forward the next_invoice_date to next year.
        plan.next_invoice_date = self.next_year
        plan.save(update_fields=["next_invoice_date"])
        invoice_plans_as_needed(self.next_year + timedelta(days=10))
        stripe_customer_id = customer.stripe_customer_id
        assert stripe_customer_id is not None
        [invoice, _, _] = iter(stripe.Invoice.list(customer=stripe_customer_id))
        self.assertEqual([4000 * self.seat_count], [item.amount for item in invoice.lines])
        realm_audit_log = RealmAuditLog.objects.filter(
            event_type=AuditLogEventType.REALM_DISCOUNT_CHANGED
        ).last()
        assert realm_audit_log is not None
        expected_extra_data = {
            "new_annual_discounted_price": 4000,
            "new_monthly_discounted_price": 400,
            "old_annual_discounted_price": 6000,
            "old_monthly_discounted_price": 600,
        }
        self.assertEqual(realm_audit_log.extra_data, expected_extra_data)
        self.assertEqual(realm_audit_log.acting_user, support_admin)

        # Confirm that once a plan has been purchased and is active,
        # approving a full sponsorship (our version of 100% discount) fails.
        with self.assertRaisesRegex(
            SupportRequestError,
            "Customer on plan Zulip Cloud Standard. Please end current plan before approving sponsorship!",
        ):
            billing_session.approve_sponsorship()

    @mock_stripe()
    def test_add_minimum_licenses(self, *mocks: Mock) -> None:
        min_licenses = 25
        support_view_request = SupportViewRequest(
            support_type=SupportType.update_minimum_licenses, minimum_licenses=min_licenses
        )
        support_admin = self.example_user("iago")
        user = self.example_user("hamlet")
        billing_session = RealmBillingSession(support_admin, realm=user.realm, support_session=True)

        billing_session.update_or_create_customer()
        with self.assertRaisesRegex(
            SupportRequestError,
            "Discount for zulip must be updated before setting a minimum number of licenses.",
        ):
            billing_session.process_support_view_request(support_view_request)

        billing_session.set_required_plan_tier(CustomerPlan.TIER_CLOUD_STANDARD)
        billing_session.attach_discount_to_customer(
            monthly_discounted_price=400,
            annual_discounted_price=4000,
        )
        message = billing_session.process_support_view_request(support_view_request)
        self.assertEqual("Minimum licenses for zulip changed to 25 from 0.", message)
        realm_audit_log = RealmAuditLog.objects.filter(
            event_type=AuditLogEventType.CUSTOMER_PROPERTY_CHANGED
        ).last()
        assert realm_audit_log is not None
        expected_extra_data = {"old_value": None, "new_value": 25, "property": "minimum_licenses"}
        self.assertEqual(realm_audit_log.extra_data, expected_extra_data)

        self.login_user(user)
        self.add_card_and_upgrade(user)
        customer = billing_session.get_customer()
        assert customer is not None
        assert customer.stripe_customer_id is not None
        [charge] = iter(stripe.Charge.list(customer=customer.stripe_customer_id))
        self.assertEqual(4000 * min_licenses, charge.amount)

        min_licenses = 50
        support_view_request = SupportViewRequest(
            support_type=SupportType.update_minimum_licenses, minimum_licenses=min_licenses
        )
        with self.assertRaisesRegex(
            SupportRequestError,
            "Cannot set minimum licenses; active plan already exists for zulip.",
        ):
            billing_session.process_support_view_request(support_view_request)

    def test_set_required_plan_tier(self) -> None:
        valid_plan_tier = CustomerPlan.TIER_CLOUD_STANDARD
        support_view_request = SupportViewRequest(
            support_type=SupportType.update_required_plan_tier,
            required_plan_tier=valid_plan_tier,
        )
        support_admin = self.example_user("iago")
        user = self.example_user("hamlet")
        billing_session = RealmBillingSession(support_admin, realm=user.realm, support_session=True)
        customer = billing_session.get_customer()
        assert customer is None

        # Set valid plan tier - creates Customer object
        message = billing_session.process_support_view_request(support_view_request)
        self.assertEqual("Required plan tier for zulip set to Zulip Cloud Standard.", message)
        realm_audit_log = RealmAuditLog.objects.filter(
            event_type=AuditLogEventType.CUSTOMER_PROPERTY_CHANGED
        ).last()
        assert realm_audit_log is not None
        expected_extra_data = {
            "old_value": None,
            "new_value": valid_plan_tier,
            "property": "required_plan_tier",
        }
        self.assertEqual(realm_audit_log.extra_data, expected_extra_data)
        customer = billing_session.get_customer()
        assert customer is not None
        self.assertEqual(customer.required_plan_tier, valid_plan_tier)
        self.assertEqual(customer.monthly_discounted_price, 0)
        self.assertEqual(customer.annual_discounted_price, 0)

        # Check that discount is only applied to set plan tier
        billing_session.attach_discount_to_customer(
            monthly_discounted_price=400,
            annual_discounted_price=4000,
        )
        customer.refresh_from_db()
        self.assertEqual(customer.monthly_discounted_price, 400)
        self.assertEqual(customer.annual_discounted_price, 4000)

        monthly_discounted_price = customer.get_discounted_price_for_plan(
            valid_plan_tier, CustomerPlan.BILLING_SCHEDULE_MONTHLY
        )
        self.assertEqual(monthly_discounted_price, customer.monthly_discounted_price)
        annual_discounted_price = customer.get_discounted_price_for_plan(
            valid_plan_tier, CustomerPlan.BILLING_SCHEDULE_ANNUAL
        )
        self.assertEqual(annual_discounted_price, customer.annual_discounted_price)
        monthly_discounted_price = customer.get_discounted_price_for_plan(
            CustomerPlan.TIER_CLOUD_PLUS, CustomerPlan.BILLING_SCHEDULE_MONTHLY
        )
        self.assertEqual(monthly_discounted_price, None)
        annual_discounted_price = customer.get_discounted_price_for_plan(
            CustomerPlan.TIER_CLOUD_PLUS, CustomerPlan.BILLING_SCHEDULE_ANNUAL
        )
        self.assertEqual(annual_discounted_price, None)

        # Try to set invalid plan tier
        invalid_plan_tier = CustomerPlan.TIER_SELF_HOSTED_BASE
        support_view_request = SupportViewRequest(
            support_type=SupportType.update_required_plan_tier,
            required_plan_tier=invalid_plan_tier,
        )
        with self.assertRaisesRegex(SupportRequestError, "Invalid plan tier for zulip."):
            billing_session.process_support_view_request(support_view_request)

        # Cannot set required plan tier to None before setting discount to 0.
        support_view_request = SupportViewRequest(
            support_type=SupportType.update_required_plan_tier, required_plan_tier=0
        )
        with self.assertRaisesRegex(
            SupportRequestError,
            "Discount for zulip must be 0 before setting required plan tier to None.",
        ):
            billing_session.process_support_view_request(support_view_request)

        billing_session.attach_discount_to_customer(
            monthly_discounted_price=0,
            annual_discounted_price=0,
        )
        message = billing_session.process_support_view_request(support_view_request)
        self.assertEqual("Required plan tier for zulip set to None.", message)
        customer.refresh_from_db()
        self.assertIsNone(customer.required_plan_tier)
        discount_for_standard_plan = customer.get_discounted_price_for_plan(
            valid_plan_tier, CustomerPlan.BILLING_SCHEDULE_MONTHLY
        )
        self.assertEqual(discount_for_standard_plan, None)
        discount_for_plus_plan = customer.get_discounted_price_for_plan(
            CustomerPlan.TIER_CLOUD_PLUS, CustomerPlan.BILLING_SCHEDULE_MONTHLY
        )
        self.assertEqual(discount_for_plus_plan, None)
        realm_audit_log = RealmAuditLog.objects.filter(
            event_type=AuditLogEventType.CUSTOMER_PROPERTY_CHANGED
        ).last()
        assert realm_audit_log is not None
        expected_extra_data = {
            "old_value": valid_plan_tier,
            "new_value": None,
            "property": "required_plan_tier",
        }
        self.assertEqual(realm_audit_log.extra_data, expected_extra_data)

    def test_approve_realm_sponsorship(self) -> None:
        realm = get_realm("zulip")
        self.assertNotEqual(realm.plan_type, Realm.PLAN_TYPE_STANDARD_FREE)

        support_admin = self.example_user("iago")
        billing_session = RealmBillingSession(user=support_admin, realm=realm, support_session=True)
        billing_session.approve_sponsorship()
        self.assertEqual(realm.plan_type, Realm.PLAN_TYPE_STANDARD_FREE)

        expected_message = (
            "Your organization's request for sponsored hosting has been approved! You have been upgraded to Zulip Cloud Standard, free of charge. :tada:"
            "\n\nIf you could [list Zulip as a sponsor on your website](/help/linking-to-zulip-website), we would really appreciate it!"
        )
        sender = get_system_bot(settings.NOTIFICATION_BOT, realm.id)

        # Organization owners get the notification bot message
        bot_and_desdemona_recipient = self.get_dm_group_recipient(
            sender, self.example_user("desdemona")
        )
        message_to_owner = Message.objects.filter(
            realm_id=realm.id, sender=sender.id, recipient=bot_and_desdemona_recipient
        ).first()
        assert message_to_owner is not None
        self.assertEqual(message_to_owner.content, expected_message)
        self.assertEqual(message_to_owner.recipient.type, Recipient.DIRECT_MESSAGE_GROUP)

        # Hamlet is in `can_manage_billing_group` so should get the notification bot message
        bot_and_hamlet_recipient = self.get_dm_group_recipient(sender, self.example_user("hamlet"))
        message_to_hamlet = Message.objects.filter(
            realm_id=realm.id, sender=sender.id, recipient=bot_and_hamlet_recipient
        ).last()
        assert message_to_hamlet is not None
        self.assertEqual(message_to_hamlet.content, expected_message)
        self.assertEqual(message_to_hamlet.recipient.type, Recipient.DIRECT_MESSAGE_GROUP)

    def test_update_realm_sponsorship_status(self) -> None:
        lear = get_realm("lear")
        iago = self.example_user("iago")
        billing_session = RealmBillingSession(user=iago, realm=lear, support_session=True)
        billing_session.update_customer_sponsorship_status(True)
        customer = get_customer_by_realm(realm=lear)
        assert customer is not None
        self.assertTrue(customer.sponsorship_pending)
        realm_audit_log = RealmAuditLog.objects.filter(
            event_type=AuditLogEventType.REALM_SPONSORSHIP_PENDING_STATUS_CHANGED
        ).last()
        assert realm_audit_log is not None
        expected_extra_data = {"sponsorship_pending": True}
        self.assertEqual(realm_audit_log.extra_data, expected_extra_data)
        self.assertEqual(realm_audit_log.acting_user, iago)

    def test_update_realm_billing_modality(self) -> None:
        realm = get_realm("zulip")
        customer = Customer.objects.create(realm=realm, stripe_customer_id="cus_12345")
        plan = CustomerPlan.objects.create(
            customer=customer,
            status=CustomerPlan.ACTIVE,
            billing_cycle_anchor=timezone_now(),
            billing_schedule=CustomerPlan.BILLING_SCHEDULE_ANNUAL,
            tier=CustomerPlan.TIER_CLOUD_STANDARD,
        )
        self.assertEqual(plan.charge_automatically, False)

        support_admin = self.example_user("iago")
        billing_session = RealmBillingSession(user=support_admin, realm=realm, support_session=True)
        billing_session.update_billing_modality_of_current_plan(True)
        plan.refresh_from_db()
        self.assertEqual(plan.charge_automatically, True)
        realm_audit_log = RealmAuditLog.objects.filter(
            event_type=AuditLogEventType.REALM_BILLING_MODALITY_CHANGED
        ).last()
        assert realm_audit_log is not None
        expected_extra_data = {"charge_automatically": plan.charge_automatically}
        self.assertEqual(realm_audit_log.acting_user, support_admin)
        self.assertEqual(realm_audit_log.extra_data, expected_extra_data)

        billing_session.update_billing_modality_of_current_plan(False)
        plan.refresh_from_db()
        self.assertEqual(plan.charge_automatically, False)
        realm_audit_log = RealmAuditLog.objects.filter(
            event_type=AuditLogEventType.REALM_BILLING_MODALITY_CHANGED
        ).last()
        assert realm_audit_log is not None
        expected_extra_data = {"charge_automatically": plan.charge_automatically}
        self.assertEqual(realm_audit_log.acting_user, support_admin)
        self.assertEqual(realm_audit_log.extra_data, expected_extra_data)

    @mock_stripe()
    def test_switch_realm_from_standard_to_plus_plan(self, *mocks: Mock) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        self.add_card_and_upgrade(user)
        customer = get_customer_by_realm(user.realm)
        assert customer is not None
        original_plan = get_current_plan_by_customer(customer)
        assert original_plan is not None
        self.assertEqual(original_plan.tier, CustomerPlan.TIER_CLOUD_STANDARD)

        support_admin = self.example_user("iago")
        billing_session = RealmBillingSession(
            user=support_admin, realm=user.realm, support_session=True
        )
        support_request = SupportViewRequest(
            support_type=SupportType.modify_plan,
            plan_modification="upgrade_plan_tier",
            new_plan_tier=CustomerPlan.TIER_CLOUD_PLUS,
        )
        # Freeze time so the prorated credit (computed inside
        # ``change_plan_tier`` from ``timezone_now()``) doesn't drift
        # between fixture regenerations.
        with time_machine.travel(self.now, tick=False):
            success_message = billing_session.process_support_view_request(support_request)
        self.assertEqual(success_message, "zulip upgraded to Zulip Cloud Plus")
        customer.refresh_from_db()
        new_plan = get_current_plan_by_customer(customer)
        assert new_plan is not None
        self.assertEqual(new_plan.tier, CustomerPlan.TIER_CLOUD_PLUS)

    @mock_stripe()
    def test_downgrade_realm_and_void_open_invoices(self, *mocks: Mock) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        with time_machine.travel(self.now, tick=False):
            self.upgrade(invoice=True)
        customer = get_customer_by_realm(user.realm)
        assert customer is not None
        original_plan = get_current_plan_by_customer(customer)
        assert original_plan is not None
        self.assertEqual(original_plan.status, CustomerPlan.ACTIVE)

        support_admin = self.example_user("iago")
        billing_session = RealmBillingSession(
            user=support_admin, realm=user.realm, support_session=True
        )

        # Send renewal invoice.
        invoice_plans_as_needed(self.now + timedelta(days=367))

        support_request = SupportViewRequest(
            support_type=SupportType.modify_plan,
            plan_modification="downgrade_now_void_open_invoices",
        )
        success_message = billing_session.process_support_view_request(support_request)
        self.assertEqual(success_message, "zulip downgraded and voided 1 open invoices")
        original_plan.refresh_from_db()
        self.assertEqual(original_plan.status, CustomerPlan.ENDED)


class TestRemoteBillingWriteAuditLog(StripeTestCase):
    def test_write_audit_log(self) -> None:
        support_admin = self.example_user("iago")
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
        remote_realm_billing_user = RemoteRealmBillingUser.objects.create(
            remote_realm=remote_realm, email="admin@example.com", user_uuid=uuid.uuid4()
        )
        remote_server_billing_user = RemoteServerBillingUser.objects.create(
            remote_server=remote_server, email="admin@example.com"
        )
        event_time = timezone_now()

        def assert_audit_log(
            audit_log: RemoteRealmAuditLog | RemoteZulipServerAuditLog,
            acting_remote_user: RemoteRealmBillingUser | RemoteServerBillingUser | None,
            acting_support_user: UserProfile | None,
            event_type: int,
            event_time: datetime,
        ) -> None:
            self.assertEqual(audit_log.event_type, event_type)
            self.assertEqual(audit_log.event_time, event_time)
            self.assertEqual(audit_log.acting_remote_user, acting_remote_user)
            self.assertEqual(audit_log.acting_support_user, acting_support_user)

        for session_class, audit_log_class, remote_object, remote_user in [
            (
                RemoteRealmBillingSession,
                RemoteRealmAuditLog,
                remote_realm,
                remote_realm_billing_user,
            ),
            (
                RemoteServerBillingSession,
                RemoteZulipServerAuditLog,
                remote_server,
                remote_server_billing_user,
            ),
        ]:
            # Necessary cast or mypy doesn't understand that we can use Django's
            # model .objects. style queries on this.
            audit_log_model = cast(
                type[RemoteRealmAuditLog] | type[RemoteZulipServerAuditLog], audit_log_class
            )
            assert isinstance(remote_user, RemoteRealmBillingUser | RemoteServerBillingUser)
            # No acting user:
            session = session_class(remote_object)
            session.write_to_audit_log(
                # This "ordinary billing" event type value gets translated by write_to_audit_log
                # into a AuditLogEventType.CUSTOMER_PLAN_CREATED value.
                event_type=BillingSessionEventType.CUSTOMER_PLAN_CREATED,
                event_time=event_time,
            )
            audit_log = audit_log_model.objects.latest("id")
            assert_audit_log(
                audit_log, None, None, AuditLogEventType.CUSTOMER_PLAN_CREATED, event_time
            )

            session = session_class(remote_object, remote_billing_user=remote_user)
            session.write_to_audit_log(
                event_type=BillingSessionEventType.CUSTOMER_PLAN_CREATED,
                event_time=event_time,
            )
            audit_log = audit_log_model.objects.latest("id")
            assert_audit_log(
                audit_log, remote_user, None, AuditLogEventType.CUSTOMER_PLAN_CREATED, event_time
            )

            session = session_class(
                remote_object, remote_billing_user=None, support_staff=support_admin
            )
            session.write_to_audit_log(
                event_type=BillingSessionEventType.CUSTOMER_PLAN_CREATED,
                event_time=event_time,
            )
            audit_log = audit_log_model.objects.latest("id")
            assert_audit_log(
                audit_log, None, support_admin, AuditLogEventType.CUSTOMER_PLAN_CREATED, event_time
            )
