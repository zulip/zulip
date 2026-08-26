import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Any
from unittest.mock import Mock, patch

import orjson
import stripe
import time_machine
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core import signing
from django.urls.resolvers import get_resolver
from django.utils.timezone import now as timezone_now
from typing_extensions import override

from corporate.lib.stripe import (
    DEFAULT_INVOICE_DAYS_UNTIL_DUE,
    MAX_INVOICED_LICENSES,
    MIN_INVOICED_LICENSES,
    STRIPE_API_VERSION,
    BillingError,
    InitialUpgradeRequest,
    RealmBillingSession,
    StripeCardError,
    UpdatePlanRequest,
    add_months,
    catch_stripe_errors,
    customer_has_credit_card_as_default_payment_method,
    customer_has_last_n_invoices_open,
    downgrade_small_realms_behind_on_payments_as_needed,
    get_latest_seat_count,
    get_price_per_license,
    invoice_plans_as_needed,
    sign_string,
    stripe_customer_has_credit_card_as_default_payment_method,
    stripe_get_customer,
    unsign_string,
)
from corporate.lib.test_stripe_class import StripeTestCase, mock_stripe
from corporate.models.customers import Customer, get_customer_by_realm
from corporate.models.licenses import LicenseLedger
from corporate.models.plans import (
    CustomerPlan,
    get_current_plan_by_customer,
    get_current_plan_by_realm,
)
from corporate.models.stripe_state import Event, Invoice
from zerver.actions.create_realm import do_create_realm
from zerver.actions.realm_settings import do_deactivate_realm, do_reactivate_realm
from zerver.actions.users import do_deactivate_user
from zerver.lib.exceptions import JsonableError
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.timestamp import datetime_to_timestamp, timestamp_to_datetime
from zerver.lib.utils import assert_is_not_none
from zerver.models import Realm, RealmAuditLog, UserProfile
from zerver.models.realm_audit_logs import AuditLogEventType
from zerver.models.realms import get_realm
from zilencer.models import RemoteZulipServer


class StripeTest(StripeTestCase):
    def check_initial_ledger_entry(
        self, plan: CustomerPlan, licenses_purchased: int
    ) -> LicenseLedger:
        return LicenseLedger.objects.get(
            plan=plan,
            is_renewal=True,
            event_time=self.now,
            licenses=licenses_purchased,
            licenses_at_next_renewal=licenses_purchased,
        )

    def test_catch_stripe_errors(self) -> None:
        @catch_stripe_errors
        def raise_invalid_request_error() -> None:
            raise stripe.InvalidRequestError("message", "param", "code", json_body={})

        with self.assertLogs("corporate.stripe", "ERROR") as error_log:
            with self.assertRaises(BillingError) as billing_context:
                raise_invalid_request_error()
            self.assertEqual("other stripe error", billing_context.exception.error_description)
            self.assertEqual(
                error_log.output, ["ERROR:corporate.stripe:Stripe error: None None None None"]
            )

        @catch_stripe_errors
        def raise_card_error() -> None:
            error_message = "The card number is not a valid credit card number."
            json_body = {"error": {"message": error_message}}
            raise stripe.CardError(error_message, "number", "invalid_number", json_body=json_body)

        with self.assertLogs("corporate.stripe", "INFO") as info_log:
            with self.assertRaises(StripeCardError) as card_context:
                raise_card_error()
            self.assertIn("not a valid credit card", str(card_context.exception))
            self.assertEqual("card error", card_context.exception.error_description)
            self.assertEqual(
                info_log.output, ["INFO:corporate.stripe:Stripe card error: None None None None"]
            )

    def test_billing_not_enabled(self) -> None:
        iago = self.example_user("iago")
        with self.settings(BILLING_ENABLED=False):
            self.login_user(iago)
            response = self.client_get("/upgrade/", follow=True)
            self.assertEqual(response.status_code, 404)

    @mock_stripe()
    def test_stripe_billing_portal_urls(self, *mocks: Mock) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        self.add_card_to_customer_for_upgrade()

        response = self.client_get(f"/customer_portal/?tier={CustomerPlan.TIER_CLOUD_STANDARD}")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith("https://billing.stripe.com/"))

        self.upgrade(invoice=True)

        response = self.client_get("/customer_portal/?return_to_billing_page=true")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith("https://billing.stripe.com/"))

        response = self.client_get("/invoices/")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith("https://billing.stripe.com/"))

    @mock_stripe()
    def test_upgrade_by_card_to_plus_plan(self, *mocks: Mock) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        response = self.client_get("/upgrade/?tier=2")
        self.assert_in_success_response(
            ["Your subscription will renew automatically", "Zulip Cloud Plus"], response
        )
        self.assertEqual(user.realm.plan_type, Realm.PLAN_TYPE_SELF_HOSTED)
        # This also means there is no card set as default payment method set for the user.
        self.assertFalse(Customer.objects.filter(realm=user.realm).exists())
        stripe_customer = self.add_card_and_upgrade(user, tier=CustomerPlan.TIER_CLOUD_PLUS)

        self.assertEqual(stripe_customer.description, "zulip (Zulip Dev)")
        self.assertEqual(stripe_customer.discount, None)
        self.assertEqual(stripe_customer.email, user.delivery_email)
        assert stripe_customer.metadata is not None
        self.assertEqual(stripe_customer.metadata["realm_str"], "zulip")
        try:
            int(stripe_customer.metadata["realm_id"])
        except ValueError:  # nocoverage
            raise AssertionError("realm_id is not a number")

        # Check Charges in Stripe
        [charge] = iter(stripe.Charge.list(customer=stripe_customer.id))
        licenses_purchased = self.billing_session.min_licenses_for_plan(
            CustomerPlan.TIER_CLOUD_PLUS
        )
        self.assertEqual(charge.amount, 12000 * licenses_purchased)
        self.assertEqual(charge.description, "Payment for Invoice")
        self.assertEqual(charge.receipt_email, user.delivery_email)
        self.assertEqual(charge.statement_descriptor, "Zulip Cloud Plus")
        # Check Invoices in Stripe
        [invoice] = iter(stripe.Invoice.list(customer=stripe_customer.id))
        self.assertIsNotNone(invoice.status_transitions.finalized_at)
        self.assertEqual(invoice.amount_due, 120000)
        self.assertEqual(invoice.amount_paid, 120000)
        # auto_advance is False because the invoice has been paid
        self.assertFalse(invoice.auto_advance)
        self.assertEqual(invoice.collection_method, "charge_automatically")
        self.assertEqual(invoice.status, "paid")
        # Check Line Items on Stripe Invoice
        [item0] = iter(invoice.lines)
        self.assertEqual(item0.amount, 12000 * licenses_purchased)
        self.assertEqual(item0.currency, "usd")
        self.assertEqual(item0.description, "Zulip Cloud Plus")
        self.assertFalse(item0.discountable)
        assert item0.pricing is not None
        self.assertEqual(item0.pricing.unit_amount_decimal, Decimal(12000))
        self.assertEqual(item0.quantity, licenses_purchased)
        self.assertEqual(item0.period.start, datetime_to_timestamp(self.now))
        self.assertEqual(item0.period.end, datetime_to_timestamp(add_months(self.now, 12)))

        # Check that we correctly populated Customer, CustomerPlan, and LicenseLedger in Zulip
        customer = Customer.objects.get(stripe_customer_id=stripe_customer.id, realm=user.realm)
        plan = CustomerPlan.objects.get(
            customer=customer,
            automanage_licenses=True,
            price_per_license=12000,
            fixed_price=None,
            discount=None,
            billing_cycle_anchor=self.now,
            billing_schedule=CustomerPlan.BILLING_SCHEDULE_ANNUAL,
            invoiced_through=LicenseLedger.objects.first(),
            next_invoice_date=self.next_month,
            tier=CustomerPlan.TIER_CLOUD_PLUS,
            status=CustomerPlan.ACTIVE,
        )
        self.check_initial_ledger_entry(plan, licenses_purchased)
        # Check RealmAuditLog
        audit_log_entries = list(
            RealmAuditLog.objects.filter(acting_user=user)
            .values_list("event_type", "event_time")
            .order_by("id")
        )
        self.assertEqual(
            audit_log_entries[:3],
            [
                (
                    AuditLogEventType.STRIPE_CUSTOMER_CREATED,
                    timestamp_to_datetime(stripe_customer.created),
                ),
                (AuditLogEventType.STRIPE_CARD_CHANGED, self.now),
                (AuditLogEventType.CUSTOMER_PLAN_CREATED, self.now),
            ],
        )
        self.assertEqual(audit_log_entries[3][0], AuditLogEventType.REALM_PLAN_TYPE_CHANGED)
        first_audit_log_entry = (
            RealmAuditLog.objects.filter(event_type=AuditLogEventType.CUSTOMER_PLAN_CREATED)
            .values_list("extra_data", flat=True)
            .first()
        )
        assert first_audit_log_entry is not None
        self.assertTrue(first_audit_log_entry["automanage_licenses"])
        # Check that we correctly updated Realm
        realm = get_realm("zulip")
        self.assertEqual(realm.plan_type, Realm.PLAN_TYPE_PLUS)
        self.assertEqual(realm.max_invites, Realm.INVITES_STANDARD_REALM_DAILY_MAX)
        # Check that we can no longer access /upgrade
        response = self.client_get("/upgrade/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual("http://zulip.testserver/billing", response["Location"])

        # Check /billing/ has the correct information
        with time_machine.travel(self.now, tick=False):
            response = self.client_get("/billing/")
        self.assert_not_in_success_response(["Pay annually"], response)
        for substring in [
            "Zulip Cloud Plus",
            str(licenses_purchased),
            "Number of licenses",
            f"{licenses_purchased}",
            "Your plan will automatically renew on",
            "January 2, 2013",
            "$1,200.00",
            "Visa ending in 4242",
            "Update card",
        ]:
            self.assert_in_response(substring, response)

        self.assert_not_in_success_response(
            [
                "Number of licenses for current billing period",
                "You will receive an invoice for",
            ],
            response,
        )

    @mock_stripe()
    def test_upgrade_by_invoice_to_plus_plan(self, *mocks: Mock) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        # Click "Make payment" in Stripe Checkout
        with time_machine.travel(self.now, tick=False):
            self.upgrade(invoice=True, tier=CustomerPlan.TIER_CLOUD_PLUS)
        # Check that we correctly created a Customer in Stripe
        stripe_customer = stripe_get_customer(
            assert_is_not_none(Customer.objects.get(realm=user.realm).stripe_customer_id)
        )
        self.assertFalse(stripe_customer_has_credit_card_as_default_payment_method(stripe_customer))

        # Check Charges in Stripe
        # There is no charge created for out of band payments which is used
        # to test this method.
        self.assertFalse(stripe.Charge.list(customer=stripe_customer.id))
        # Check Invoices in Stripe
        [invoice] = iter(stripe.Invoice.list(customer=stripe_customer.id))
        self.assertIsNotNone(invoice.due_date)
        self.assertIsNotNone(invoice.status_transitions.finalized_at)
        self.assertEqual(invoice.amount_due, 12000 * 123)
        self.assertEqual(invoice.amount_paid, 12000 * 123)
        self.assertEqual(invoice.attempt_count, 0)
        self.assertFalse(invoice.auto_advance)
        self.assertEqual(invoice.collection_method, "send_invoice")
        self.assertEqual(invoice.statement_descriptor, "Zulip Cloud Plus")
        self.assertEqual(invoice.status, "paid")

        # Check Line Items on Stripe Invoice
        [item] = iter(invoice.lines)
        self.assertEqual(item.amount, 12000 * 123)
        self.assertEqual(item.currency, "usd")
        self.assertEqual(item.description, "Zulip Cloud Plus")
        self.assertFalse(item.discountable)
        assert item.pricing is not None
        self.assertEqual(item.pricing.unit_amount_decimal, Decimal(12000))
        self.assertEqual(item.quantity, 123)
        self.assertEqual(item.period.start, datetime_to_timestamp(self.now))
        self.assertEqual(item.period.end, datetime_to_timestamp(add_months(self.now, 12)))

        # Check that we correctly populated Customer, CustomerPlan and LicenseLedger in Zulip
        customer = Customer.objects.get(stripe_customer_id=stripe_customer.id, realm=user.realm)
        plan = CustomerPlan.objects.get(
            customer=customer,
            automanage_licenses=False,
            charge_automatically=False,
            price_per_license=12000,
            fixed_price=None,
            discount=None,
            billing_cycle_anchor=self.now,
            billing_schedule=CustomerPlan.BILLING_SCHEDULE_ANNUAL,
            invoiced_through=LicenseLedger.objects.first(),
            next_invoice_date=self.next_month,
            tier=CustomerPlan.TIER_CLOUD_PLUS,
            status=CustomerPlan.ACTIVE,
        )
        self.check_initial_ledger_entry(plan, 123)
        # Check RealmAuditLog
        audit_log_entries = list(
            RealmAuditLog.objects.filter(acting_user=user)
            .values_list("event_type", "event_time")
            .order_by("id")
        )
        self.assertEqual(
            audit_log_entries[:3],
            [
                (
                    AuditLogEventType.STRIPE_CUSTOMER_CREATED,
                    timestamp_to_datetime(stripe_customer.created),
                ),
                (AuditLogEventType.CUSTOMER_PLAN_CREATED, self.now),
                (AuditLogEventType.REALM_PLAN_TYPE_CHANGED, self.now),
            ],
        )
        self.assertEqual(audit_log_entries[2][0], AuditLogEventType.REALM_PLAN_TYPE_CHANGED)
        first_audit_log_entry = (
            RealmAuditLog.objects.filter(event_type=AuditLogEventType.CUSTOMER_PLAN_CREATED)
            .values_list("extra_data", flat=True)
            .first()
        )
        assert first_audit_log_entry is not None
        self.assertFalse(first_audit_log_entry["automanage_licenses"])
        # Check that we correctly updated Realm
        realm = get_realm("zulip")
        self.assertEqual(realm.plan_type, Realm.PLAN_TYPE_PLUS)
        self.assertEqual(realm.max_invites, Realm.INVITES_STANDARD_REALM_DAILY_MAX)
        # Check that we can no longer access /upgrade
        response = self.client_get("/upgrade/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual("http://zulip.testserver/billing", response["Location"])

        # Check /billing/ has the correct information
        with time_machine.travel(self.now, tick=False):
            response = self.client_get("/billing/")
        self.assert_not_in_success_response(["Pay annually", "Update card"], response)
        for substring in [
            "Zulip Cloud Plus",
            str(123),
            "Number of licenses for current billing period",
            f"licenses ({self.seat_count} in use)",
            "You will receive an invoice for",
            "January 2, 2013",
            "$14,760.00",  # 14760 = 120 * 123
        ]:
            self.assert_in_response(substring, response)

    @mock_stripe()
    def test_upgrade_by_card(self, *mocks: Mock) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        response = self.client_get("/upgrade/")
        self.assert_in_success_response(["Your subscription will renew automatically"], response)
        self.assertNotEqual(user.realm.plan_type, Realm.PLAN_TYPE_STANDARD)
        # This also means there is no card set as default payment method set for the user.
        self.assertFalse(Customer.objects.filter(realm=user.realm).exists())

        # Click "Purchase Zulip Cloud Standard" without adding a card.
        with self.assertLogs("corporate.stripe", "WARNING"):
            response = self.upgrade()
        self.assert_json_error(response, "Please add a credit card before upgrading.")

        stripe_customer = self.add_card_and_upgrade(user)

        self.assertEqual(stripe_customer.description, "zulip (Zulip Dev)")
        self.assertEqual(stripe_customer.discount, None)
        self.assertEqual(stripe_customer.email, user.delivery_email)
        assert stripe_customer.metadata is not None
        self.assertEqual(stripe_customer.metadata["realm_str"], "zulip")
        try:
            int(stripe_customer.metadata["realm_id"])
        except ValueError:  # nocoverage
            raise AssertionError("realm_id is not a number")

        # Check Charges in Stripe
        [charge] = iter(stripe.Charge.list(customer=stripe_customer.id))
        self.assertEqual(charge.amount, 8000 * self.seat_count)
        self.assertEqual(charge.description, "Payment for Invoice")
        self.assertEqual(charge.receipt_email, user.delivery_email)
        self.assertEqual(charge.statement_descriptor, "Zulip Cloud Standard")
        # Check Invoices in Stripe
        [invoice] = iter(stripe.Invoice.list(customer=stripe_customer.id))
        self.assertIsNotNone(invoice.status_transitions.finalized_at)
        self.assertEqual(invoice.amount_due, 48000)
        self.assertEqual(invoice.amount_paid, 48000)
        # auto_advance is False because the invoice has been paid
        self.assertFalse(invoice.auto_advance)
        self.assertEqual(invoice.collection_method, "charge_automatically")
        self.assertEqual(invoice.statement_descriptor, "Zulip Cloud Standard")

        # Check Line Items on Stripe Invoice
        [item0] = iter(invoice.lines)
        self.assertEqual(item0.amount, 8000 * self.seat_count)
        self.assertEqual(item0.currency, "usd")
        self.assertEqual(item0.description, "Zulip Cloud Standard")
        self.assertFalse(item0.discountable)
        assert item0.pricing is not None
        self.assertEqual(item0.pricing.unit_amount_decimal, Decimal(8000))
        self.assertEqual(item0.quantity, self.seat_count)
        self.assertEqual(item0.period.start, datetime_to_timestamp(self.now))
        self.assertEqual(item0.period.end, datetime_to_timestamp(add_months(self.now, 12)))

        # Check that we correctly populated Customer, CustomerPlan, and LicenseLedger in Zulip
        customer = Customer.objects.get(stripe_customer_id=stripe_customer.id, realm=user.realm)
        plan = CustomerPlan.objects.get(
            customer=customer,
            automanage_licenses=True,
            price_per_license=8000,
            fixed_price=None,
            discount=None,
            billing_cycle_anchor=self.now,
            billing_schedule=CustomerPlan.BILLING_SCHEDULE_ANNUAL,
            invoiced_through=LicenseLedger.objects.first(),
            next_invoice_date=self.next_month,
            tier=CustomerPlan.TIER_CLOUD_STANDARD,
            status=CustomerPlan.ACTIVE,
        )
        self.check_initial_ledger_entry(plan, self.seat_count)
        # Check RealmAuditLog
        audit_log_entries = list(
            RealmAuditLog.objects.filter(acting_user=user)
            .values_list("event_type", "event_time")
            .order_by("id")
        )
        self.assertEqual(
            audit_log_entries[:3],
            [
                (
                    AuditLogEventType.STRIPE_CUSTOMER_CREATED,
                    timestamp_to_datetime(stripe_customer.created),
                ),
                (AuditLogEventType.STRIPE_CARD_CHANGED, self.now),
                (AuditLogEventType.CUSTOMER_PLAN_CREATED, self.now),
            ],
        )
        self.assertEqual(audit_log_entries[3][0], AuditLogEventType.REALM_PLAN_TYPE_CHANGED)
        first_audit_log_entry = (
            RealmAuditLog.objects.filter(event_type=AuditLogEventType.CUSTOMER_PLAN_CREATED)
            .values_list("extra_data", flat=True)
            .first()
        )
        assert first_audit_log_entry is not None
        self.assertTrue(first_audit_log_entry["automanage_licenses"])
        # Check that we correctly updated Realm
        realm = get_realm("zulip")
        self.assertEqual(realm.plan_type, Realm.PLAN_TYPE_STANDARD)
        self.assertEqual(realm.max_invites, Realm.INVITES_STANDARD_REALM_DAILY_MAX)
        # Check that we can no longer access /upgrade
        response = self.client_get("/upgrade/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual("http://zulip.testserver/billing", response["Location"])

        # Check /billing/ has the correct information
        with time_machine.travel(self.now, tick=False):
            response = self.client_get("/billing/")
        self.assert_not_in_success_response(["Pay annually"], response)
        for substring in [
            "Zulip Cloud Standard",
            str(self.seat_count),
            "Number of licenses",
            f"{self.seat_count}",
            "Your plan will automatically renew on",
            "January 2, 2013",
            f"${80 * self.seat_count}.00",
            "Visa ending in 4242",
            "Update card",
        ]:
            self.assert_in_response(substring, response)

        self.assert_not_in_success_response(
            [
                "Number of licenses for current billing period",
                "You will receive an invoice for",
            ],
            response,
        )

    @mock_stripe()
    def test_card_attached_to_customer_but_payment_fails(self, *mocks: Mock) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        self.add_card_to_customer_for_upgrade(charge_succeeds=False)
        with self.assertLogs("corporate.stripe", "WARNING"):
            response = self.upgrade()
        self.assert_json_error_contains(response, "Your card was declined.")

        # Customer added a card which always requires authentication, we cannot
        # use these cards for automatic payments.
        # TODO: Add a test case for it here.

    @mock_stripe()
    def test_upgrade_by_invoice(self, *mocks: Mock) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        # Click "Make payment" in Stripe Checkout
        with time_machine.travel(self.now, tick=False):
            self.upgrade(invoice=True)
        # Check that we correctly created a Customer in Stripe
        stripe_customer = stripe_get_customer(
            assert_is_not_none(Customer.objects.get(realm=user.realm).stripe_customer_id)
        )
        self.assertFalse(stripe_customer_has_credit_card_as_default_payment_method(stripe_customer))

        # Check Charges in Stripe
        self.assertFalse(stripe.Charge.list(customer=stripe_customer.id))
        # Check Invoices in Stripe
        [invoice] = iter(stripe.Invoice.list(customer=stripe_customer.id))
        self.assertIsNotNone(invoice.due_date)
        self.assertIsNotNone(invoice.status_transitions.finalized_at)
        self.assertEqual(invoice.amount_due, 8000 * 123)
        self.assertEqual(invoice.amount_paid, 8000 * 123)
        self.assertEqual(invoice.attempt_count, 0)
        self.assertFalse(invoice.auto_advance)
        self.assertEqual(invoice.collection_method, "send_invoice")
        self.assertEqual(invoice.statement_descriptor, "Zulip Cloud Standard")
        self.assertEqual(invoice.status, "paid")

        # Check Line Items on Stripe Invoice
        [item] = iter(invoice.lines)
        self.assertEqual(item.currency, "usd")
        self.assertEqual(item.amount, 8000 * 123)
        self.assertEqual(item.description, "Zulip Cloud Standard")
        self.assertFalse(item.discountable)
        self.assertEqual(item.quantity, 123)
        assert item.pricing is not None
        self.assertEqual(item.pricing.unit_amount_decimal, Decimal(8000))
        self.assertEqual(item.period.start, datetime_to_timestamp(self.now))
        self.assertEqual(item.period.end, datetime_to_timestamp(add_months(self.now, 12)))

        # Check that we correctly populated Customer, CustomerPlan and LicenseLedger in Zulip
        customer = Customer.objects.get(stripe_customer_id=stripe_customer.id, realm=user.realm)
        plan = CustomerPlan.objects.get(
            customer=customer,
            automanage_licenses=False,
            charge_automatically=False,
            price_per_license=8000,
            fixed_price=None,
            discount=None,
            billing_cycle_anchor=self.now,
            billing_schedule=CustomerPlan.BILLING_SCHEDULE_ANNUAL,
            invoiced_through=LicenseLedger.objects.first(),
            next_invoice_date=self.next_month,
            tier=CustomerPlan.TIER_CLOUD_STANDARD,
            status=CustomerPlan.ACTIVE,
        )
        self.check_initial_ledger_entry(plan, 123)
        # Check RealmAuditLog
        audit_log_entries = list(
            RealmAuditLog.objects.filter(acting_user=user)
            .values_list("event_type", "event_time")
            .order_by("id")
        )
        self.assertEqual(
            audit_log_entries[:3],
            [
                (
                    AuditLogEventType.STRIPE_CUSTOMER_CREATED,
                    timestamp_to_datetime(stripe_customer.created),
                ),
                (AuditLogEventType.CUSTOMER_PLAN_CREATED, self.now),
                (AuditLogEventType.REALM_PLAN_TYPE_CHANGED, self.now),
            ],
        )
        self.assertEqual(audit_log_entries[2][0], AuditLogEventType.REALM_PLAN_TYPE_CHANGED)
        first_audit_log_entry = (
            RealmAuditLog.objects.filter(event_type=AuditLogEventType.CUSTOMER_PLAN_CREATED)
            .values_list("extra_data", flat=True)
            .first()
        )
        assert first_audit_log_entry is not None
        self.assertFalse(first_audit_log_entry["automanage_licenses"])
        # Check that we correctly updated Realm
        realm = get_realm("zulip")
        self.assertEqual(realm.plan_type, Realm.PLAN_TYPE_STANDARD)
        self.assertEqual(realm.max_invites, Realm.INVITES_STANDARD_REALM_DAILY_MAX)
        # Check that we can no longer access /upgrade
        response = self.client_get("/upgrade/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual("http://zulip.testserver/billing", response["Location"])

        # Check /billing/ has the correct information
        with time_machine.travel(self.now, tick=False):
            response = self.client_get("/billing/")
        self.assert_not_in_success_response(["Pay annually", "Update card"], response)
        for substring in [
            "Zulip Cloud Standard",
            str(123),
            "Number of licenses for current billing period",
            f"licenses ({self.seat_count} in use)",
            "You will receive an invoice for",
            "January 2, 2013",
            "$9,840.00",  # 9840 = 80 * 123
        ]:
            self.assert_in_response(substring, response)

    @mock_stripe()
    def test_free_trial_upgrade_by_card(self, *mocks: Mock) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)

        with self.settings(CLOUD_FREE_TRIAL_DAYS=60):
            response = self.client_get("/upgrade/")
            free_trial_end_date = self.now + timedelta(days=60)

            self.assert_in_success_response(
                ["Your card will not be charged", "free trial", "60-day"], response
            )
            self.assertNotEqual(user.realm.plan_type, Realm.PLAN_TYPE_STANDARD)
            self.assertFalse(Customer.objects.filter(realm=user.realm).exists())

            # Require free trial users to add a credit card.
            with (
                time_machine.travel(self.now, tick=False),
                self.assertLogs("corporate.stripe", "WARNING"),
            ):
                response = self.upgrade()
            self.assert_json_error(
                response, "Please add a credit card before starting your free trial."
            )

            stripe_customer = self.add_card_and_upgrade(user)

            self.assertEqual(Invoice.objects.count(), 0)
            self.assertEqual(stripe_customer.description, "zulip (Zulip Dev)")
            self.assertEqual(stripe_customer.discount, None)
            self.assertEqual(stripe_customer.email, user.delivery_email)
            assert stripe_customer.metadata is not None
            self.assertEqual(stripe_customer.metadata["realm_str"], "zulip")
            try:
                int(stripe_customer.metadata["realm_id"])
            except ValueError:  # nocoverage
                raise AssertionError("realm_id is not a number")

            self.assertFalse(stripe.Charge.list(customer=stripe_customer.id))

            self.assertFalse(stripe.Invoice.list(customer=stripe_customer.id))

            customer = Customer.objects.get(stripe_customer_id=stripe_customer.id, realm=user.realm)
            plan = CustomerPlan.objects.get(
                customer=customer,
                automanage_licenses=True,
                price_per_license=8000,
                fixed_price=None,
                discount=None,
                billing_cycle_anchor=self.now,
                billing_schedule=CustomerPlan.BILLING_SCHEDULE_ANNUAL,
                invoiced_through=LicenseLedger.objects.first(),
                next_invoice_date=free_trial_end_date,
                tier=CustomerPlan.TIER_CLOUD_STANDARD,
                status=CustomerPlan.FREE_TRIAL,
                # For payment through card.
                charge_automatically=True,
            )
            self.check_initial_ledger_entry(plan, self.seat_count)
            audit_log_entries = list(
                RealmAuditLog.objects.filter(acting_user=user)
                .values_list("event_type", "event_time")
                .order_by("id")
            )
            self.assertEqual(
                audit_log_entries[:4],
                [
                    (
                        AuditLogEventType.STRIPE_CUSTOMER_CREATED,
                        timestamp_to_datetime(stripe_customer.created),
                    ),
                    (
                        AuditLogEventType.STRIPE_CARD_CHANGED,
                        self.now,
                    ),
                    (AuditLogEventType.CUSTOMER_PLAN_CREATED, self.now),
                    (AuditLogEventType.REALM_PLAN_TYPE_CHANGED, self.now),
                ],
            )
            self.assertEqual(audit_log_entries[3][0], AuditLogEventType.REALM_PLAN_TYPE_CHANGED)
            first_audit_log_entry = (
                RealmAuditLog.objects.filter(event_type=AuditLogEventType.CUSTOMER_PLAN_CREATED)
                .values_list("extra_data", flat=True)
                .first()
            )
            assert first_audit_log_entry is not None
            self.assertTrue(first_audit_log_entry["automanage_licenses"])

            realm = get_realm("zulip")
            self.assertEqual(realm.plan_type, Realm.PLAN_TYPE_STANDARD)
            self.assertEqual(realm.max_invites, Realm.INVITES_STANDARD_REALM_DAILY_MAX)

            with time_machine.travel(self.now, tick=False):
                response = self.client_get("/billing/")
            self.assert_not_in_success_response(["Pay annually"], response)
            for substring in [
                "Zulip Cloud Standard <i>(free trial)</i>",
                str(self.seat_count),
                "Number of licenses",
                f"{self.seat_count}",
                "Your plan will automatically renew on",
                "March 2, 2012",
                f"${80 * self.seat_count}.00",
                "Visa ending in 4242",
                "Update card",
            ]:
                self.assert_in_response(substring, response)
            self.assert_not_in_success_response(["Go to your Zulip organization"], response)

            billing_session = RealmBillingSession(user=user, realm=realm)
            with patch("corporate.lib.stripe.get_latest_seat_count", return_value=12):
                billing_session.update_license_ledger_if_needed(self.now)
            self.check_last_ledger_entry_license_counts(plan, 12, 12)

            with patch("corporate.lib.stripe.get_latest_seat_count", return_value=15):
                billing_session.update_license_ledger_if_needed(self.next_month)
            self.check_last_ledger_entry_license_counts(plan, 15, 15)

            invoice_plans_as_needed(self.next_month)
            self.assertFalse(stripe.Invoice.list(customer=stripe_customer.id))
            customer_plan = CustomerPlan.objects.get(customer=customer)
            self.assertEqual(customer_plan.status, CustomerPlan.FREE_TRIAL)
            self.assertEqual(customer_plan.next_invoice_date, free_trial_end_date)

            invoice_plans_as_needed(free_trial_end_date)
            customer_plan.refresh_from_db()
            realm.refresh_from_db()
            self.assertEqual(customer_plan.status, CustomerPlan.ACTIVE)
            self.assertEqual(customer_plan.next_invoice_date, add_months(free_trial_end_date, 1))
            self.assertEqual(realm.plan_type, Realm.PLAN_TYPE_STANDARD)

            [invoice] = iter(stripe.Invoice.list(customer=stripe_customer.id))
            self.assertEqual(invoice.amount_due, 15 * 80 * 100)
            self.assertEqual(invoice.amount_paid, 0)
            self.assertEqual(invoice.amount_remaining, 15 * 80 * 100)
            self.assertTrue(invoice.auto_advance)
            self.assertEqual(invoice.collection_method, "charge_automatically")
            self.assertEqual(invoice.customer_email, self.example_email("hamlet"))
            self.assertEqual(invoice.status, "open")

            [invoice_item] = iter(invoice.lines)
            self.assertEqual(invoice_item.amount, 15 * 80 * 100)
            self.assertEqual(invoice_item.description, "Zulip Cloud Standard - renewal")
            self.assertEqual(invoice_item.quantity, 15)
            self.assertFalse(invoice_item.discountable)
            assert invoice_item.pricing is not None
            self.assertEqual(invoice_item.pricing.unit_amount_decimal, Decimal(8000))
            self.assertEqual(invoice_item.period.start, datetime_to_timestamp(free_trial_end_date))
            self.assertEqual(
                invoice_item.period.end, datetime_to_timestamp(add_months(free_trial_end_date, 12))
            )

            invoice_plans_as_needed(add_months(free_trial_end_date, 1))
            [invoice] = iter(stripe.Invoice.list(customer=stripe_customer.id))

            with patch("corporate.lib.stripe.get_latest_seat_count", return_value=19):
                billing_session.update_license_ledger_if_needed(add_months(free_trial_end_date, 10))
            self.check_last_ledger_entry_license_counts(plan, 19, 19)

            # Fast forward next_invoice_date to 10 months from the free_trial_end_date
            plan.next_invoice_date = add_months(free_trial_end_date, 10)
            plan.save(update_fields=["next_invoice_date"])
            invoice_plans_as_needed(add_months(free_trial_end_date, 10))
            [invoice0, _invoice1] = iter(stripe.Invoice.list(customer=stripe_customer.id))
            self.assertEqual(invoice0.amount_due, 5172)
            self.assertEqual(invoice0.auto_advance, True)
            self.assertEqual(invoice0.collection_method, "charge_automatically")
            self.assertEqual(invoice0.customer_email, "hamlet@zulip.com")

            [invoice_item] = iter(invoice0.lines)
            self.assertEqual(invoice_item.amount, 5172)
            self.assertEqual(invoice_item.description, "Additional Zulip Cloud Standard license")
            self.assertFalse(invoice_item.discountable)
            self.assertEqual(invoice_item.quantity, 4)
            self.assertEqual(
                invoice_item.period.start,
                datetime_to_timestamp(add_months(free_trial_end_date, 10)),
            )
            self.assertEqual(
                invoice_item.period.end, datetime_to_timestamp(add_months(free_trial_end_date, 12))
            )

            # Fast forward next_invoice_date to one year from the free_trial_end_date
            plan.next_invoice_date = add_months(free_trial_end_date, 12)
            plan.save(update_fields=["next_invoice_date"])
            invoice_plans_as_needed(add_months(free_trial_end_date, 12))
            [invoice0, _invoice1, _invoice2] = iter(
                stripe.Invoice.list(customer=stripe_customer.id)
            )

        # Check /billing/ has correct information for fixed price customers.
        plan.fixed_price = 127
        plan.price_per_license = None
        plan.save(update_fields=["fixed_price", "price_per_license"])
        with time_machine.travel(self.now, tick=False):
            response = self.client_get("/billing/")
        self.assert_in_success_response(["$1.27"], response)
        # Don't show price breakdown
        self.assert_not_in_success_response(["{self.seat_count} x"], response)

    @mock_stripe()
    def test_free_trial_upgrade_by_invoice(self, *mocks: Mock) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)

        free_trial_end_date = self.now + timedelta(days=60)
        with self.settings(CLOUD_FREE_TRIAL_DAYS=60):
            response = self.client_get("/upgrade/")

            self.assert_in_success_response(
                ["Your card will not be charged", "free trial", "60-day"], response
            )
            self.assertNotEqual(user.realm.plan_type, Realm.PLAN_TYPE_STANDARD)
            self.assertFalse(Customer.objects.filter(realm=user.realm).exists())

            with time_machine.travel(self.now, tick=False):
                self.upgrade(invoice=True)

            stripe_customer = stripe_get_customer(
                assert_is_not_none(Customer.objects.get(realm=user.realm).stripe_customer_id)
            )
            self.assertEqual(stripe_customer.discount, None)
            self.assertEqual(stripe_customer.email, user.delivery_email)
            assert stripe_customer.metadata is not None
            self.assertEqual(stripe_customer.metadata["realm_str"], "zulip")
            try:
                int(stripe_customer.metadata["realm_id"])
            except ValueError:  # nocoverage
                raise AssertionError("realm_id is not a number")

            [invoice] = iter(stripe.Invoice.list(customer=stripe_customer.id))
            self.assertEqual(invoice.amount_due, 123 * 80 * 100)
            self.assertEqual(invoice.amount_paid, 0)
            self.assertEqual(invoice.amount_remaining, 123 * 80 * 100)
            self.assertTrue(invoice.auto_advance)
            self.assertEqual(invoice.collection_method, "send_invoice")
            self.assertEqual(invoice.customer_email, self.example_email("hamlet"))
            self.assertEqual(invoice.status, "open")

            customer = Customer.objects.get(stripe_customer_id=stripe_customer.id, realm=user.realm)
            plan = CustomerPlan.objects.get(
                customer=customer,
                automanage_licenses=False,
                price_per_license=8000,
                fixed_price=None,
                discount=None,
                billing_cycle_anchor=self.now,
                billing_schedule=CustomerPlan.BILLING_SCHEDULE_ANNUAL,
                invoiced_through=LicenseLedger.objects.first(),
                next_invoice_date=free_trial_end_date,
                tier=CustomerPlan.TIER_CLOUD_STANDARD,
                status=CustomerPlan.FREE_TRIAL,
                # For invoice billing.
                charge_automatically=False,
            )

            self.check_initial_ledger_entry(plan, 123)
            audit_log_entries = list(
                RealmAuditLog.objects.filter(acting_user=user)
                .values_list("event_type", "event_time")
                .order_by("id")
            )
            self.assertEqual(
                audit_log_entries[:3],
                [
                    (
                        AuditLogEventType.STRIPE_CUSTOMER_CREATED,
                        timestamp_to_datetime(stripe_customer.created),
                    ),
                    (AuditLogEventType.CUSTOMER_PLAN_CREATED, self.now),
                    (AuditLogEventType.REALM_PLAN_TYPE_CHANGED, self.now),
                ],
            )
            self.assertEqual(audit_log_entries[2][0], AuditLogEventType.REALM_PLAN_TYPE_CHANGED)
            first_audit_log_entry = (
                RealmAuditLog.objects.filter(event_type=AuditLogEventType.CUSTOMER_PLAN_CREATED)
                .values_list("extra_data", flat=True)
                .first()
            )
            assert first_audit_log_entry is not None
            self.assertFalse(first_audit_log_entry["automanage_licenses"])

            realm = get_realm("zulip")
            self.assertEqual(realm.plan_type, Realm.PLAN_TYPE_STANDARD)
            self.assertEqual(realm.max_invites, Realm.INVITES_STANDARD_REALM_DAILY_MAX)

            with time_machine.travel(self.now, tick=False):
                response = self.client_get("/billing/")
            self.assert_not_in_success_response(["Pay annually"], response)
            for substring in [
                "Zulip Cloud Standard <i>(free trial)</i>",
                str(self.seat_count),
                "Number of licenses for next billing period",
                f"{self.seat_count} in use",
                "To ensure continuous access",
                "please pay",
                "before the end of your trial",
                "March 2, 2012",
                "Invoice",
            ]:
                self.assert_in_response(substring, response)

            [invoice_item] = iter(invoice.lines)
            self.assertEqual(invoice_item.amount, 123 * 80 * 100)
            self.assertEqual(invoice_item.description, "Zulip Cloud Standard")
            self.assertEqual(invoice_item.quantity, 123)
            self.assertFalse(invoice_item.discountable)
            self.assertEqual(invoice_item.period.start, datetime_to_timestamp(free_trial_end_date))
            self.assertEqual(
                invoice_item.period.end, datetime_to_timestamp(add_months(free_trial_end_date, 12))
            )

            with patch("corporate.lib.stripe.BillingSession.invoice_plan") as mocked:
                invoice_plans_as_needed(self.next_month)
            mocked.assert_not_called()
            mocked.reset_mock()
            customer_plan = CustomerPlan.objects.get(customer=customer)
            self.assertEqual(customer_plan.status, CustomerPlan.FREE_TRIAL)
            self.assertEqual(customer_plan.next_invoice_date, free_trial_end_date)

            cursor = self.pin_event_cursor()
            last_renewal_ledger = (
                LicenseLedger.objects.filter(plan=plan, is_renewal=True).order_by("-id").first()
            )
            assert last_renewal_ledger is not None
            self.assertEqual(
                last_renewal_ledger.event_time,
                self.now,
            )

            # Customer pays the invoice
            assert invoice.id is not None
            stripe.Invoice.pay(invoice.id, paid_out_of_band=True)
            self.send_stripe_webhook_events(cursor, "invoice.paid")

            with time_machine.travel(self.now, tick=False):
                response = self.client_get("/billing/")

            self.assert_in_success_response(["You have no outstanding invoices."], response)
            self.assert_in_success_response(
                [f"An invoice will be sent to <b>{user.delivery_email}</b> on the same day."],
                response,
            )

            invoice_plans_as_needed(free_trial_end_date)
            last_renewal_ledger.refresh_from_db()
            customer_plan.refresh_from_db()
            realm.refresh_from_db()
            plan.refresh_from_db()
            self.assertEqual(customer_plan.status, CustomerPlan.ACTIVE)
            self.assertEqual(customer_plan.next_invoice_date, add_months(free_trial_end_date, 1))
            self.assertEqual(realm.plan_type, Realm.PLAN_TYPE_STANDARD)
            self.assertEqual(last_renewal_ledger.event_time, free_trial_end_date)
            self.assertEqual(customer_plan.billing_cycle_anchor, free_trial_end_date)

            before_ledger_count = LicenseLedger.objects.filter(plan=plan).count()
            self.billing_session.make_end_of_cycle_updates_if_needed(plan, free_trial_end_date)
            after_ledger_count = LicenseLedger.objects.filter(plan=plan).count()
            # No additional ledger entries are created.
            self.assertEqual(before_ledger_count, after_ledger_count)

    @mock_stripe()
    def test_free_trial_upgrade_by_invoice_voided(self, *mocks: Mock) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)

        with self.settings(CLOUD_FREE_TRIAL_DAYS=60), time_machine.travel(self.now, tick=False):
            self.upgrade(invoice=True)

        customer = Customer.objects.get(realm=user.realm)
        stripe_customer_id = assert_is_not_none(customer.stripe_customer_id)
        [stripe_invoice] = iter(stripe.Invoice.list(customer=stripe_customer_id))
        assert stripe_invoice.id is not None
        self.assertEqual(stripe_invoice.status, "open")

        invoice = Invoice.objects.get(customer=customer, stripe_invoice_id=stripe_invoice.id)
        self.assertEqual(invoice.status, Invoice.SENT)
        self.assertIsNone(invoice.get_last_associated_event())

        # Support voids the unpaid invoice in Stripe, delivering an invoice.voided webhook.
        cursor = self.pin_event_cursor()
        stripe.Invoice.void_invoice(stripe_invoice.id)
        self.send_stripe_webhook_events(cursor, "invoice.voided")

        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.VOID)
        event = invoice.get_last_associated_event()
        assert event is not None
        self.assertEqual(event.type, "invoice.voided")
        self.assertEqual(event.status, Event.EVENT_HANDLER_SUCCEEDED)

    def test_free_trial_billing_page_after_invoice_voided(self) -> None:
        # An invoice-billed free trial whose invoice is later voided should
        # show the pending downgrade instead of a stale prompt to pay it.
        user = self.example_user("hamlet")
        self.login_user(user)

        with self.settings(CLOUD_FREE_TRIAL_DAYS=60), time_machine.travel(self.now, tick=False):
            self.local_upgrade(
                self.seat_count,
                False,
                CustomerPlan.BILLING_SCHEDULE_ANNUAL,
                False,
                True,
            )

        customer = get_customer_by_realm(user.realm)
        assert customer is not None
        plan = get_current_plan_by_customer(customer)
        assert plan is not None
        self.assertEqual(plan.status, CustomerPlan.FREE_TRIAL)
        invoice = Invoice.objects.get(plan=plan)
        self.assertTrue(invoice.is_created_for_free_trial_upgrade)
        self.assertEqual(invoice.status, Invoice.SENT)

        mock_customer = Mock(email=user.delivery_email)
        with (
            time_machine.travel(self.now, tick=False),
            patch("corporate.lib.stripe.stripe_get_customer", return_value=mock_customer),
        ):
            response = self.client_get("/billing/")
            self.assert_in_success_response(["To ensure continuous access", "please pay"], response)

            # Mark the invoice void, as the invoice.voided webhook does; see
            # test_free_trial_upgrade_by_invoice_voided for that half of the flow.
            invoice.status = Invoice.VOID
            invoice.save(update_fields=["status"])

            response = self.client_get("/billing/")
            self.assert_in_success_response(
                [
                    (
                        "will be downgraded to <strong>Zulip Cloud Free</strong> "
                        "at the end of the free trial"
                    )
                ],
                response,
            )
            self.assert_not_in_success_response(
                ["To ensure continuous access", "please pay"], response
            )

    def test_make_end_of_cycle_updates_errors_without_free_trial_invoice(self) -> None:
        realm = get_realm("zulip")
        customer = Customer.objects.create(realm=realm, stripe_customer_id="cus_123")
        free_trial_end_date = self.now + timedelta(days=30)
        plan = CustomerPlan.objects.create(
            customer=customer,
            tier=CustomerPlan.TIER_CLOUD_STANDARD,
            status=CustomerPlan.FREE_TRIAL,
            # Billed by invoice rather than charged automatically.
            charge_automatically=False,
            billing_cycle_anchor=self.now,
            billing_schedule=CustomerPlan.BILLING_SCHEDULE_ANNUAL,
            price_per_license=8000,
            next_invoice_date=free_trial_end_date,
        )
        LicenseLedger.objects.create(
            plan=plan,
            is_renewal=True,
            event_time=self.now,
            licenses=10,
            licenses_at_next_renewal=10,
        )
        # No Invoice object exists for the plan.
        billing_session = RealmBillingSession(realm=realm)
        with self.assertRaises(BillingError) as billing_context:
            billing_session.make_end_of_cycle_updates_if_needed(plan, free_trial_end_date)
        self.assertEqual(
            f"Invoice-billed free trial has no invoice: {plan}.",
            billing_context.exception.error_description,
        )

    @mock_stripe()
    def test_free_trial_upgrade_by_invoice_with_additional_users_after_payment(
        self, *mocks: Mock
    ) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)

        free_trial_end_date = self.now + timedelta(days=60)
        with self.settings(CLOUD_FREE_TRIAL_DAYS=60):
            response = self.client_get("/upgrade/")

            self.assert_in_success_response(
                ["Your card will not be charged", "free trial", "60-day"], response
            )
            self.assertNotEqual(user.realm.plan_type, Realm.PLAN_TYPE_STANDARD)
            self.assertFalse(Customer.objects.filter(realm=user.realm).exists())

            with time_machine.travel(self.now, tick=False):
                self.upgrade(invoice=True)

            stripe_customer = stripe_get_customer(
                assert_is_not_none(Customer.objects.get(realm=user.realm).stripe_customer_id)
            )
            self.assertEqual(stripe_customer.discount, None)
            self.assertEqual(stripe_customer.email, user.delivery_email)
            assert stripe_customer.metadata is not None
            self.assertEqual(stripe_customer.metadata["realm_str"], "zulip")
            try:
                int(stripe_customer.metadata["realm_id"])
            except ValueError:  # nocoverage
                raise AssertionError("realm_id is not a number")

            [invoice] = iter(stripe.Invoice.list(customer=stripe_customer.id))
            self.assertEqual(invoice.amount_due, 123 * 80 * 100)
            self.assertEqual(invoice.amount_paid, 0)
            self.assertEqual(invoice.amount_remaining, 123 * 80 * 100)
            self.assertTrue(invoice.auto_advance)
            self.assertEqual(invoice.collection_method, "send_invoice")
            self.assertEqual(invoice.customer_email, self.example_email("hamlet"))
            self.assertEqual(invoice.status, "open")

            customer = Customer.objects.get(stripe_customer_id=stripe_customer.id, realm=user.realm)
            plan = CustomerPlan.objects.get(
                customer=customer,
                automanage_licenses=False,
                price_per_license=8000,
                fixed_price=None,
                discount=None,
                billing_cycle_anchor=self.now,
                billing_schedule=CustomerPlan.BILLING_SCHEDULE_ANNUAL,
                invoiced_through=LicenseLedger.objects.first(),
                next_invoice_date=free_trial_end_date,
                tier=CustomerPlan.TIER_CLOUD_STANDARD,
                status=CustomerPlan.FREE_TRIAL,
                # For invoice billing.
                charge_automatically=False,
            )

            self.check_initial_ledger_entry(plan, 123)
            audit_log_entries = list(
                RealmAuditLog.objects.filter(acting_user=user)
                .values_list("event_type", "event_time")
                .order_by("id")
            )
            self.assertEqual(
                audit_log_entries[:3],
                [
                    (
                        AuditLogEventType.STRIPE_CUSTOMER_CREATED,
                        timestamp_to_datetime(stripe_customer.created),
                    ),
                    (AuditLogEventType.CUSTOMER_PLAN_CREATED, self.now),
                    (AuditLogEventType.REALM_PLAN_TYPE_CHANGED, self.now),
                ],
            )
            self.assertEqual(audit_log_entries[2][0], AuditLogEventType.REALM_PLAN_TYPE_CHANGED)
            first_audit_log_entry = (
                RealmAuditLog.objects.filter(event_type=AuditLogEventType.CUSTOMER_PLAN_CREATED)
                .values_list("extra_data", flat=True)
                .first()
            )
            assert first_audit_log_entry is not None
            self.assertFalse(first_audit_log_entry["automanage_licenses"])

            realm = get_realm("zulip")
            self.assertEqual(realm.plan_type, Realm.PLAN_TYPE_STANDARD)
            self.assertEqual(realm.max_invites, Realm.INVITES_STANDARD_REALM_DAILY_MAX)

            with time_machine.travel(self.now, tick=False):
                response = self.client_get("/billing/")
            self.assert_not_in_success_response(["Pay annually"], response)
            for substring in [
                "Zulip Cloud Standard <i>(free trial)</i>",
                str(self.seat_count),
                "Number of licenses for next billing period",
                f"{self.seat_count} in use",
                "To ensure continuous access",
                "please pay",
                "before the end of your trial",
                "March 2, 2012",
                "Invoice",
            ]:
                self.assert_in_response(substring, response)

            [invoice_item] = iter(invoice.lines)
            self.assertEqual(invoice_item.amount, 123 * 80 * 100)
            self.assertEqual(invoice_item.description, "Zulip Cloud Standard")
            self.assertEqual(invoice_item.quantity, 123)
            self.assertFalse(invoice_item.discountable)
            self.assertEqual(invoice_item.period.start, datetime_to_timestamp(free_trial_end_date))
            self.assertEqual(
                invoice_item.period.end, datetime_to_timestamp(add_months(free_trial_end_date, 12))
            )

            with patch("corporate.lib.stripe.BillingSession.invoice_plan") as mocked:
                invoice_plans_as_needed(self.next_month)
            mocked.assert_not_called()
            mocked.reset_mock()
            customer_plan = CustomerPlan.objects.get(customer=customer)
            self.assertEqual(customer_plan.status, CustomerPlan.FREE_TRIAL)
            self.assertEqual(customer_plan.next_invoice_date, free_trial_end_date)

            cursor = self.pin_event_cursor()
            # Customer pays the invoice
            assert invoice.id is not None
            stripe.Invoice.pay(invoice.id, paid_out_of_band=True)
            self.send_stripe_webhook_events(cursor, "invoice.paid")

            with time_machine.travel(self.now, tick=False):
                response = self.client_get("/billing/")

            self.assert_in_success_response(["You have no outstanding invoices."], response)

            update_plan_request = UpdatePlanRequest(
                status=None,
                licenses=125,
                licenses_at_next_renewal=None,
                schedule=None,
                toggle_license_management=False,
            )
            # Customer cannot update licenses while in free trial.
            with time_machine.travel(self.now, tick=False), self.assertRaises(JsonableError) as exc:
                self.billing_session.do_update_plan(update_plan_request)
            self.assertEqual(
                str(exc.exception),
                "Cannot update licenses in the current billing period for free trial plan.",
            )

            # Customer paid the invoice and then added 2 new users for the next renewal period.
            update_plan_request = UpdatePlanRequest(
                status=None,
                licenses=None,
                licenses_at_next_renewal=125,
                schedule=None,
                toggle_license_management=False,
            )
            self.check_last_ledger_entry_license_counts(plan, 123, 123)
            with time_machine.travel(self.now, tick=False):
                self.billing_session.do_update_plan(update_plan_request)
            self.check_last_ledger_entry_license_counts(plan, 123, 125)

            invoice_plans_as_needed(free_trial_end_date)
            customer_plan.refresh_from_db()
            realm.refresh_from_db()
            plan.refresh_from_db()
            self.assertEqual(customer_plan.status, CustomerPlan.ACTIVE)
            self.assertEqual(customer_plan.next_invoice_date, add_months(free_trial_end_date, 1))
            self.assertEqual(realm.plan_type, Realm.PLAN_TYPE_STANDARD)
            self.assertEqual(customer_plan.billing_cycle_anchor, free_trial_end_date)

            [additional_license_invoice, renewal_invoice] = iter(
                stripe.Invoice.list(customer=stripe_customer.id)
            )
            self.assertEqual(renewal_invoice.id, invoice.id)

            self.assertEqual(additional_license_invoice.amount_due, 2 * 80 * 100)
            self.assertEqual(additional_license_invoice.amount_paid, 0)
            self.assertEqual(additional_license_invoice.amount_remaining, 2 * 80 * 100)
            self.assertTrue(additional_license_invoice.auto_advance)
            self.assertEqual(additional_license_invoice.collection_method, "send_invoice")
            self.assertEqual(
                additional_license_invoice.customer_email, self.example_email("hamlet")
            )
            self.assertEqual(additional_license_invoice.status, "open")

    @mock_stripe()
    def test_free_trial_upgrade_by_invoice_customer_fails_to_pay(self, *mocks: Mock) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)

        free_trial_end_date = self.now + timedelta(days=60)
        with self.settings(CLOUD_FREE_TRIAL_DAYS=60):
            response = self.client_get("/upgrade/")

            self.assert_in_success_response(
                ["Your card will not be charged", "free trial", "60-day"], response
            )
            self.assertNotEqual(user.realm.plan_type, Realm.PLAN_TYPE_STANDARD)
            self.assertFalse(Customer.objects.filter(realm=user.realm).exists())

            with time_machine.travel(self.now, tick=False):
                self.upgrade(invoice=True)

            stripe_customer = stripe_get_customer(
                assert_is_not_none(Customer.objects.get(realm=user.realm).stripe_customer_id)
            )
            self.assertEqual(stripe_customer.discount, None)
            self.assertEqual(stripe_customer.email, user.delivery_email)
            assert stripe_customer.metadata is not None
            self.assertEqual(stripe_customer.metadata["realm_str"], "zulip")
            try:
                int(stripe_customer.metadata["realm_id"])
            except ValueError:  # nocoverage
                raise AssertionError("realm_id is not a number")

            [invoice] = iter(stripe.Invoice.list(customer=stripe_customer.id))
            self.assertEqual(invoice.amount_due, 123 * 80 * 100)
            self.assertEqual(invoice.amount_paid, 0)
            self.assertEqual(invoice.amount_remaining, 123 * 80 * 100)
            self.assertTrue(invoice.auto_advance)
            self.assertEqual(invoice.collection_method, "send_invoice")
            self.assertEqual(invoice.customer_email, self.example_email("hamlet"))
            self.assertEqual(invoice.status, "open")

            customer = Customer.objects.get(stripe_customer_id=stripe_customer.id, realm=user.realm)
            plan = CustomerPlan.objects.get(
                customer=customer,
                automanage_licenses=False,
                price_per_license=8000,
                fixed_price=None,
                discount=None,
                billing_cycle_anchor=self.now,
                billing_schedule=CustomerPlan.BILLING_SCHEDULE_ANNUAL,
                invoiced_through=LicenseLedger.objects.first(),
                next_invoice_date=free_trial_end_date,
                tier=CustomerPlan.TIER_CLOUD_STANDARD,
                status=CustomerPlan.FREE_TRIAL,
                # For invoice billing.
                charge_automatically=False,
            )

            self.check_initial_ledger_entry(plan, 123)
            audit_log_entries = list(
                RealmAuditLog.objects.filter(acting_user=user)
                .values_list("event_type", "event_time")
                .order_by("id")
            )
            self.assertEqual(
                audit_log_entries[:3],
                [
                    (
                        AuditLogEventType.STRIPE_CUSTOMER_CREATED,
                        timestamp_to_datetime(stripe_customer.created),
                    ),
                    (AuditLogEventType.CUSTOMER_PLAN_CREATED, self.now),
                    (AuditLogEventType.REALM_PLAN_TYPE_CHANGED, self.now),
                ],
            )
            self.assertEqual(audit_log_entries[2][0], AuditLogEventType.REALM_PLAN_TYPE_CHANGED)
            first_audit_log_entry = (
                RealmAuditLog.objects.filter(event_type=AuditLogEventType.CUSTOMER_PLAN_CREATED)
                .values_list("extra_data", flat=True)
                .first()
            )
            assert first_audit_log_entry is not None
            self.assertFalse(first_audit_log_entry["automanage_licenses"])

            realm = get_realm("zulip")
            self.assertEqual(realm.plan_type, Realm.PLAN_TYPE_STANDARD)
            self.assertEqual(realm.max_invites, Realm.INVITES_STANDARD_REALM_DAILY_MAX)

            with time_machine.travel(self.now, tick=False):
                response = self.client_get("/billing/")
            self.assert_not_in_success_response(["Pay annually"], response)
            for substring in [
                "Zulip Cloud Standard <i>(free trial)</i>",
                str(self.seat_count),
                "Number of licenses for next billing period",
                f"{self.seat_count} in use",
                "To ensure continuous access",
                "please pay",
                "before the end of your trial",
                "March 2, 2012",
                "Invoice",
            ]:
                self.assert_in_response(substring, response)

            [invoice_item] = iter(invoice.lines)
            self.assertEqual(invoice_item.amount, 123 * 80 * 100)
            self.assertEqual(invoice_item.description, "Zulip Cloud Standard")
            self.assertEqual(invoice_item.quantity, 123)
            self.assertFalse(invoice_item.discountable)
            self.assertEqual(invoice_item.period.start, datetime_to_timestamp(free_trial_end_date))
            self.assertEqual(
                invoice_item.period.end, datetime_to_timestamp(add_months(free_trial_end_date, 12))
            )

            # We reached free trial end but customer didn't pay the invoice.
            invoice_plans_as_needed(free_trial_end_date)
            customer_plan = CustomerPlan.objects.get(customer=customer)
            self.assertEqual(customer_plan.status, CustomerPlan.ENDED)
            realm.refresh_from_db()
            self.assertEqual(realm.plan_type, Realm.PLAN_TYPE_LIMITED)

            response = self.client_get("/upgrade/")
            self.assert_in_success_response(
                ["Your free trial", "has expired", "To reactivate", "please pay"], response
            )

            # Customer decides to pay later
            cursor = self.pin_event_cursor()
            assert invoice.id is not None
            stripe.Invoice.pay(invoice.id, paid_out_of_band=True)
            self.send_stripe_webhook_events(cursor, "invoice.paid")

            invoice_plans_as_needed(free_trial_end_date)
            CustomerPlan.objects.get(customer=customer, status=CustomerPlan.ACTIVE)
            realm.refresh_from_db()
            self.assertEqual(realm.plan_type, Realm.PLAN_TYPE_STANDARD)

    @mock_stripe()
    def test_upgrade_by_card_with_outdated_seat_count(self, *mocks: Mock) -> None:
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)
        # Higher than original seat count
        new_seat_count = 23
        initial_upgrade_request = InitialUpgradeRequest(
            manual_license_management=False,
            tier=CustomerPlan.TIER_CLOUD_STANDARD,
            billing_modality="charge_automatically",
        )
        billing_session = RealmBillingSession(hamlet)
        _, context_when_upgrade_page_is_rendered = billing_session.get_initial_upgrade_context(
            initial_upgrade_request
        )
        # Change the seat count in upgrade flow: after do_upgrade, during process_initial_upgrade
        with (
            patch(
                "corporate.lib.stripe.BillingSession.stale_license_count_check",
                return_value=self.seat_count,
            ),
            patch("corporate.lib.stripe.get_latest_seat_count", return_value=new_seat_count),
            patch(
                "corporate.lib.stripe.RealmBillingSession.get_initial_upgrade_context",
                return_value=(_, context_when_upgrade_page_is_rendered),
            ),
        ):
            self.add_card_and_upgrade(hamlet)

        customer = Customer.objects.first()
        assert customer is not None
        stripe_customer_id: str = assert_is_not_none(customer.stripe_customer_id)
        # Check that the Charge used the old quantity, not new_seat_count
        [charge] = iter(stripe.Charge.list(customer=stripe_customer_id))
        self.assertEqual(8000 * self.seat_count, charge.amount)
        # Check that the invoice has a credit for the old amount and a charge for the new one
        [additional_license_invoice, upgrade_invoice] = iter(
            stripe.Invoice.list(customer=stripe_customer_id)
        )
        self.assertEqual(
            [8000 * self.seat_count],
            [item.amount for item in upgrade_invoice.lines],
        )
        self.assertEqual(
            [8000 * (new_seat_count - self.seat_count)],
            [item.amount for item in additional_license_invoice.lines],
        )
        # Check LicenseLedger has the new amount
        plan = get_current_plan_by_customer(customer)
        assert plan is not None
        self.check_last_ledger_entry_license_counts(plan, new_seat_count, new_seat_count)

    @mock_stripe()
    def test_upgrade_by_card_with_outdated_lower_seat_count(self, *mocks: Mock) -> None:
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)
        new_seat_count = self.seat_count - 1
        initial_upgrade_request = InitialUpgradeRequest(
            manual_license_management=False,
            tier=CustomerPlan.TIER_CLOUD_STANDARD,
            billing_modality="charge_automatically",
        )
        billing_session = RealmBillingSession(hamlet)
        _, context_when_upgrade_page_is_rendered = billing_session.get_initial_upgrade_context(
            initial_upgrade_request
        )
        # Change the seat count in upgrade flow: after do_upgrade, during process_initial_upgrade
        with (
            patch(
                "corporate.lib.stripe.BillingSession.stale_license_count_check",
                return_value=self.seat_count,
            ),
            patch("corporate.lib.stripe.get_latest_seat_count", return_value=new_seat_count),
            patch(
                "corporate.lib.stripe.RealmBillingSession.get_initial_upgrade_context",
                return_value=(_, context_when_upgrade_page_is_rendered),
            ),
        ):
            self.add_card_and_upgrade(hamlet)

        customer = Customer.objects.first()
        assert customer is not None
        stripe_customer_id: str = assert_is_not_none(customer.stripe_customer_id)
        # Check that the Charge used the old quantity, not new_seat_count
        [charge] = iter(stripe.Charge.list(customer=stripe_customer_id))
        self.assertEqual(8000 * self.seat_count, charge.amount)
        [upgrade_invoice] = iter(stripe.Invoice.list(customer=stripe_customer_id))
        self.assertEqual(
            [8000 * self.seat_count],
            [item.amount for item in upgrade_invoice.lines],
        )
        # Check LicenseLedger has the reduced license count at renewal
        plan = get_current_plan_by_customer(customer)
        assert plan is not None
        self.check_last_ledger_entry_license_counts(plan, self.seat_count, new_seat_count)

        # Check that we informed the support team about the potential billing error.
        from django.core.mail import outbox

        self.assert_length(outbox, 1)

        for message in outbox:
            self.assert_length(message.to, 1)
            self.assertEqual(message.to[0], "sales@zulip.com")
            self.assertEqual(
                message.subject,
                f"Check initial licenses invoiced for {billing_session.billing_entity_display_name}",
            )
            self.assertEqual(self.email_envelope_from(message), settings.NOREPLY_EMAIL_ADDRESS)

    @mock_stripe()
    def test_upgrade_by_card_with_outdated_seat_count_and_minimum_for_plan_tier(
        self, *mocks: Mock
    ) -> None:
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)
        # New seat count is under the minimum for the plan tier
        minimum_for_plan_tier = self.seat_count - 1
        new_seat_count = self.seat_count - 2
        initial_upgrade_request = InitialUpgradeRequest(
            manual_license_management=False,
            tier=CustomerPlan.TIER_CLOUD_STANDARD,
            billing_modality="charge_automatically",
        )
        billing_session = RealmBillingSession(hamlet)
        _, context_when_upgrade_page_is_rendered = billing_session.get_initial_upgrade_context(
            initial_upgrade_request
        )
        assert context_when_upgrade_page_is_rendered is not None
        assert context_when_upgrade_page_is_rendered.get("seat_count") == self.seat_count
        # Change the current and minimum license counts in do_upgrade
        with (
            patch(
                "corporate.lib.stripe.BillingSession.min_licenses_for_plan",
                return_value=minimum_for_plan_tier,
            ),
            patch("corporate.lib.stripe.get_latest_seat_count", return_value=new_seat_count),
            patch(
                "corporate.lib.stripe.RealmBillingSession.get_initial_upgrade_context",
                return_value=(_, context_when_upgrade_page_is_rendered),
            ),
        ):
            self.add_card_and_upgrade(hamlet)

        customer = Customer.objects.first()
        assert customer is not None
        stripe_customer_id: str = assert_is_not_none(customer.stripe_customer_id)
        # Check that the Charge used the minimum seat count
        [charge] = iter(stripe.Charge.list(customer=stripe_customer_id))
        self.assertEqual(8000 * minimum_for_plan_tier, charge.amount)
        [upgrade_invoice] = iter(stripe.Invoice.list(customer=stripe_customer_id))
        self.assertEqual(
            [8000 * minimum_for_plan_tier],
            [item.amount for item in upgrade_invoice.lines],
        )
        # Check LicenseLedger has the minimum license count
        plan = get_current_plan_by_customer(customer)
        assert plan is not None
        self.check_last_ledger_entry_license_counts(
            plan, minimum_for_plan_tier, minimum_for_plan_tier
        )

    @mock_stripe()
    def test_customer_minimum_licenses_for_plan(self, *mocks: Mock) -> None:
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)
        # We set a 1 license minimum for the initial upgrade.
        minimum_for_plan_tier = 1
        with (
            patch(
                "corporate.lib.stripe.BillingSession.min_licenses_for_plan",
                return_value=minimum_for_plan_tier,
            ),
        ):
            self.add_card_and_upgrade(hamlet, tier=CustomerPlan.TIER_CLOUD_PLUS)

        customer = Customer.objects.first()
        assert customer is not None
        assert customer.stripe_customer_id is not None
        # Check LicenseLedger has the current seat count.
        plan = get_current_plan_by_customer(customer)
        assert plan is not None
        self.check_last_ledger_entry_license_counts(plan, self.seat_count, self.seat_count)

        # We manually set customer.minimum_licenses to the current seat count,
        # which is below the general Plus plan minimum licenses.
        customer.minimum_licenses = self.seat_count
        customer.save()

        # Next year, they are still invoiced for the current seat count.
        invoice_plans_as_needed(self.next_year)
        # Check both invoices (initial and renewal)
        [invoice0, invoice1] = iter(stripe.Invoice.list(customer=customer.stripe_customer_id))
        self.assertEqual(
            [12000 * self.seat_count],
            [item.amount for item in invoice0.lines],
        )
        self.assertEqual(
            [12000 * self.seat_count],
            [item.amount for item in invoice1.lines],
        )

        # Without the minimum_licenses set on the customer, a BillingError is raised when
        # invoicing plans.
        customer.minimum_licenses = None
        customer.save()

        with self.assertLogs("corporate.stripe", level="ERROR") as m:
            invoice_plans_as_needed(self.next_year + timedelta(days=366))
        self.assertIn(
            f"ERROR:corporate.stripe:Invoicing failed: Customer.id: {customer.id}",
            m.output[0],
        )
        self.assertIn(
            "Renewal licenses (6) less than minimum licenses (10) required for plan Zulip Cloud Plus.",
            m.output[0],
        )

    def test_upgrade_with_tampered_seat_count(self) -> None:
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)
        with self.assertLogs("corporate.stripe", "WARNING"):
            response = self.upgrade(talk_to_stripe=False, salt="badsalt")
        self.assert_json_error_contains(response, "Something went wrong. Please contact")
        self.assertEqual(orjson.loads(response.content)["error_description"], "tampered seat count")

    @mock_stripe()
    def test_upgrade_race_condition_during_card_upgrade(self, *mocks: Mock) -> None:
        hamlet = self.example_user("hamlet")
        iago = self.example_user("iago")
        self.login_user(iago)
        iago_upgrade_page_response = self.client_get("/upgrade/")

        self.login_user(hamlet)
        self.add_card_to_customer_for_upgrade()
        cursor_before_upgrade = self.pin_event_cursor()
        hamlet_upgrade_page_response = self.client_get("/upgrade/")
        self.client_billing_post(
            "/billing/upgrade",
            {
                "billing_modality": "charge_automatically",
                "schedule": "annual",
                "signed_seat_count": self.get_signed_seat_count_from_response(
                    hamlet_upgrade_page_response
                ),
                "salt": self.get_salt_from_response(hamlet_upgrade_page_response),
                "license_management": "automatic",
            },
        )

        # Get the last generated invoice for Hamlet
        customer = get_customer_by_realm(get_realm("zulip"))
        assert customer is not None
        assert customer.stripe_customer_id is not None
        [hamlet_invoice] = iter(stripe.Invoice.list(customer=customer.stripe_customer_id))

        self.login_user(iago)
        with self.settings(CLOUD_FREE_TRIAL_DAYS=60):
            # Iago completed the upgrade while we were waiting on success payment event for Hamlet.
            # NOTE: Used free trial to avoid creating any stripe invoice events.
            self.client_billing_post(
                "/billing/upgrade",
                {
                    "billing_modality": "charge_automatically",
                    "schedule": "annual",
                    "signed_seat_count": self.get_signed_seat_count_from_response(
                        iago_upgrade_page_response
                    ),
                    "salt": self.get_salt_from_response(iago_upgrade_page_response),
                    "license_management": "automatic",
                },
            )

        with self.assertLogs("corporate.stripe", "WARNING"):
            self.send_stripe_webhook_events(cursor_before_upgrade)

        assert hamlet_invoice.id is not None
        self.assert_details_of_valid_invoice_payment_from_event_status_endpoint(
            hamlet_invoice.id,
            {
                "status": "paid",
                "event_handler": {
                    "status": "failed",
                    "error": {
                        "message": "The organization is already subscribed to a plan. Please reload the billing page.",
                        "description": "subscribing with existing subscription",
                    },
                },
            },
        )

        # Check that we informed the support team about the failure.
        from django.core.mail import outbox

        self.assert_length(outbox, 1)

        for message in outbox:
            self.assert_length(message.to, 1)
            self.assertEqual(message.to[0], "sales@zulip.com")
            self.assertEqual(message.subject, "Error processing paid customer invoice")
            self.assertEqual(self.email_envelope_from(message), settings.NOREPLY_EMAIL_ADDRESS)

    def test_upgrade_race_condition_during_invoice_upgrade(self) -> None:
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)
        self.local_upgrade(self.seat_count, True, CustomerPlan.BILLING_SCHEDULE_ANNUAL, True, False)
        with (
            self.assertLogs("corporate.stripe", "WARNING") as m,
            self.assertRaises(BillingError) as context,
        ):
            self.local_upgrade(
                self.seat_count, True, CustomerPlan.BILLING_SCHEDULE_ANNUAL, True, False
            )
        self.assertEqual(
            "subscribing with existing subscription", context.exception.error_description
        )
        self.assertEqual(
            m.output[0],
            "WARNING:corporate.stripe:Upgrade of <Realm: zulip 2> (stripe: cus_123) failed because of existing active plan.",
        )
        self.assert_length(m.output, 1)

    @mock_stripe()
    def test_check_upgrade_parameters(self, *mocks: Mock) -> None:
        def check_error(
            error_message: str,
            error_description: str,
            upgrade_params: Mapping[str, Any],
            del_args: Sequence[str] = [],
        ) -> None:
            if error_description:
                with self.assertLogs("corporate.stripe", "WARNING"):
                    response = self.upgrade(
                        talk_to_stripe=False, del_args=del_args, **upgrade_params
                    )
                    self.assertEqual(
                        orjson.loads(response.content)["error_description"], error_description
                    )
            else:
                response = self.upgrade(talk_to_stripe=False, del_args=del_args, **upgrade_params)
            self.assert_json_error_contains(response, error_message)

        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)
        self.add_card_to_customer_for_upgrade()
        check_error("Invalid billing_modality", "", {"billing_modality": "invalid"})
        check_error("Invalid schedule", "", {"schedule": "invalid"})
        check_error("Invalid license_management", "", {"license_management": "invalid"})

        check_error(
            "Something went wrong. Please contact",
            "unknown license_management",
            {},
            del_args=["license_management"],
        )

        check_error(
            "You must purchase licenses for all active users in your organization (minimum 30).",
            "not enough licenses",
            {"billing_modality": "send_invoice", "licenses": -1},
        )
        check_error(
            "You must purchase licenses for all active users in your organization (minimum 30).",
            "not enough licenses",
            {"billing_modality": "send_invoice"},
        )
        check_error(
            "You must purchase licenses for all active users in your organization (minimum 30).",
            "not enough licenses",
            {"billing_modality": "send_invoice", "licenses": 25},
        )
        check_error(
            "Invoices with more than 1000 licenses can't be processed from this page",
            "too many licenses",
            {"billing_modality": "send_invoice", "licenses": 10000},
        )

        check_error(
            "You must purchase licenses for all active users in your organization (minimum 6).",
            "not enough licenses",
            {"billing_modality": "charge_automatically", "license_management": "manual"},
        )

        check_error(
            "You must purchase licenses for all active users in your organization (minimum 6).",
            "not enough licenses",
            {
                "billing_modality": "charge_automatically",
                "license_management": "manual",
                "licenses": 3,
            },
        )

    @mock_stripe()
    def test_upgrade_license_counts(self, *mocks: Mock) -> None:
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)
        self.add_card_to_customer_for_upgrade()

        def check_min_licenses_error(
            invoice: bool,
            licenses: int | None,
            min_licenses_in_response: int,
            upgrade_params: Mapping[str, Any] = {},
        ) -> None:
            upgrade_params = dict(upgrade_params)
            if licenses is None:
                del_args = ["licenses"]
            else:
                del_args = []
                upgrade_params["licenses"] = licenses
            with self.assertLogs("corporate.stripe", "WARNING"):
                response = self.upgrade(
                    invoice=invoice, talk_to_stripe=False, del_args=del_args, **upgrade_params
                )
            self.assert_json_error_contains(response, f"minimum {min_licenses_in_response}")
            self.assertEqual(
                orjson.loads(response.content)["error_description"], "not enough licenses"
            )

        def check_max_licenses_error(licenses: int) -> None:
            with self.assertLogs("corporate.stripe", "WARNING"):
                response = self.upgrade(invoice=True, talk_to_stripe=False, licenses=licenses)
            self.assert_json_error_contains(
                response, f"with more than {MAX_INVOICED_LICENSES} licenses"
            )
            self.assertEqual(
                orjson.loads(response.content)["error_description"], "too many licenses"
            )

        def check_success(
            invoice: bool, licenses: int | None, upgrade_params: Mapping[str, Any] = {}
        ) -> None:
            upgrade_params = dict(upgrade_params)
            if licenses is None:
                del_args = ["licenses"]
            else:
                del_args = []
                upgrade_params["licenses"] = licenses
            with (
                patch("corporate.lib.stripe.BillingSession.process_initial_upgrade"),
                patch(
                    "corporate.lib.stripe.BillingSession.create_stripe_invoice_and_charge",
                    return_value="fake_stripe_invoice_id",
                ),
            ):
                response = self.upgrade(
                    invoice=invoice, talk_to_stripe=False, del_args=del_args, **upgrade_params
                )
            self.assert_json_success(response)

        # Autopay with licenses < seat count
        check_min_licenses_error(
            False, self.seat_count - 1, self.seat_count, {"license_management": "manual"}
        )
        # Autopay with not setting licenses
        check_min_licenses_error(False, None, self.seat_count, {"license_management": "manual"})
        # Invoice with licenses < MIN_INVOICED_LICENSES
        check_min_licenses_error(True, MIN_INVOICED_LICENSES - 1, MIN_INVOICED_LICENSES)
        # Invoice with licenses < seat count
        with patch("corporate.lib.stripe.MIN_INVOICED_LICENSES", 3):
            check_min_licenses_error(True, 4, self.seat_count)
        # Invoice with not setting licenses
        check_min_licenses_error(True, None, MIN_INVOICED_LICENSES)
        # Invoice exceeding max licenses
        check_max_licenses_error(MAX_INVOICED_LICENSES + 1)
        with patch(
            "corporate.lib.stripe.get_latest_seat_count", return_value=MAX_INVOICED_LICENSES + 5
        ):
            check_max_licenses_error(MAX_INVOICED_LICENSES + 5)

        # Autopay with automatic license_management
        check_success(False, None)
        # Autopay with automatic license_management, should just ignore the licenses entry
        check_success(False, self.seat_count)
        # Autopay
        check_success(False, self.seat_count, {"license_management": "manual"})
        # Autopay has no limit on max licenses
        check_success(False, MAX_INVOICED_LICENSES + 1, {"license_management": "manual"})
        # Invoice
        check_success(True, self.seat_count + MIN_INVOICED_LICENSES)
        # Invoice
        check_success(True, MAX_INVOICED_LICENSES)

        # By default, an organization on a "Pay by card" plan with Manual license
        # management cannot purchase less licenses than the current seat count.
        # If exempt_from_license_number_check is enabled, they should be able to though.
        customer = Customer.objects.get_or_create(realm=hamlet.realm)[0]
        customer.exempt_from_license_number_check = True
        customer.save()
        check_success(False, self.seat_count - 1, {"license_management": "manual"})

    @mock_stripe()
    def test_upgrade_with_uncaught_exception(self, *mock_args: Any) -> None:
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)
        self.add_card_to_customer_for_upgrade()
        with (
            patch(
                "corporate.lib.stripe.BillingSession.create_stripe_invoice_and_charge",
                side_effect=Exception,
            ),
            self.assertLogs("corporate.stripe", "WARNING") as m,
        ):
            response = self.upgrade(talk_to_stripe=False)
            self.assertIn("ERROR:corporate.stripe:Uncaught exception in billing", m.output[0])
            self.assertIn(m.records[0].stack_info, m.output[0])
        self.assert_json_error_contains(
            response, "Something went wrong. Please contact desdemona+admin@zulip.com."
        )
        self.assertEqual(
            orjson.loads(response.content)["error_description"], "uncaught exception during upgrade"
        )

    @mock_stripe()
    def test_invoice_payment_succeeded_event_with_uncaught_exception(self, *mock_args: Any) -> None:
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)
        self.add_card_to_customer_for_upgrade()

        with (
            patch(
                "corporate.lib.stripe.BillingSession.process_initial_upgrade", side_effect=Exception
            ),
            self.assertLogs("corporate.stripe", "WARNING"),
        ):
            response = self.upgrade()

        response_dict = self.assert_json_success(response)

        self.assert_details_of_valid_invoice_payment_from_event_status_endpoint(
            response_dict["stripe_invoice_id"],
            {
                "status": "paid",
                "event_handler": {
                    "status": "failed",
                    "error": {
                        "message": "Something went wrong. Please contact desdemona+admin@zulip.com.",
                        "description": "uncaught exception in invoice.paid event handler",
                    },
                },
            },
        )

    def test_redirect_for_billing_page(self) -> None:
        user = self.example_user("othello")
        self.login_user(user)
        response = self.client_get("/billing/")
        not_admin_message = "You do not have permission to view this page."
        self.assert_in_success_response([not_admin_message], response)

        user.realm.plan_type = Realm.PLAN_TYPE_STANDARD_FREE
        user.realm.save()
        response = self.client_get("/billing/")
        self.assert_in_success_response([not_admin_message], response)

        # Billing page redirects to sponsorship page for standard free admins.
        user = self.example_user("hamlet")
        self.login_user(user)
        response = self.client_get("/billing/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual("/sponsorship/", response["Location"])

        user.realm.plan_type = Realm.PLAN_TYPE_LIMITED
        user.realm.save()
        customer = Customer.objects.create(realm=user.realm, stripe_customer_id="cus_123")
        response = self.client_get("/billing/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual("/plans/", response["Location"])

        # Check redirects for sponsorship pending
        customer.sponsorship_pending = True
        customer.save()
        response = self.client_get("/billing/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual("/sponsorship/", response["Location"])

        # Don't redirect to sponsorship for paid plans.
        user.realm.plan_type = Realm.PLAN_TYPE_STANDARD
        user.realm.save()
        response = self.client_get("/billing/")
        self.assertNotEqual("/sponsorship/", response["Location"])

        user.realm.plan_type = Realm.PLAN_TYPE_PLUS
        user.realm.save()
        response = self.client_get("/billing/")
        self.assertNotEqual("/sponsorship/", response["Location"])

    @mock_stripe()
    def test_redirect_for_billing_page_downgrade_at_free_trial_end(self, *mocks: Mock) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)

        with self.settings(CLOUD_FREE_TRIAL_DAYS=30):
            response = self.client_get("/upgrade/")
            free_trial_end_date = self.now + timedelta(days=30)

            self.assert_in_success_response(
                ["Your card will not be charged", "free trial", "30-day"], response
            )
            self.assertNotEqual(user.realm.plan_type, Realm.PLAN_TYPE_STANDARD)
            self.assertFalse(Customer.objects.filter(realm=user.realm).exists())

            stripe_customer = self.add_card_and_upgrade(user)
            customer = Customer.objects.get(stripe_customer_id=stripe_customer.id, realm=user.realm)
            plan = CustomerPlan.objects.get(
                customer=customer,
                automanage_licenses=True,
                price_per_license=8000,
                fixed_price=None,
                discount=None,
                billing_cycle_anchor=self.now,
                billing_schedule=CustomerPlan.BILLING_SCHEDULE_ANNUAL,
                invoiced_through=LicenseLedger.objects.first(),
                next_invoice_date=free_trial_end_date,
                tier=CustomerPlan.TIER_CLOUD_STANDARD,
                status=CustomerPlan.FREE_TRIAL,
                # For payment through card.
                charge_automatically=True,
            )
            self.check_initial_ledger_entry(plan, self.seat_count)

            realm = get_realm("zulip")
            self.assertEqual(realm.plan_type, Realm.PLAN_TYPE_STANDARD)

            with time_machine.travel(self.now, tick=False):
                response = self.client_get("/billing/")
            self.assert_not_in_success_response(["Pay annually"], response)
            for substring in [
                "Zulip Cloud Standard <i>(free trial)</i>",
                "Your plan will automatically renew on",
                "February 1, 2012",
                "Visa ending in 4242",
                "Update card",
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
            with time_machine.travel(free_trial_end_date, tick=False):
                response = self.client_get("/billing/")
                self.assertEqual(response.status_code, 302)
                self.assertEqual("/plans/", response["Location"])

    def test_upgrade_page_for_demo_organizations(self) -> None:
        user = self.example_user("hamlet")
        user.realm.demo_organization_scheduled_deletion_date = timezone_now() + timedelta(days=30)
        user.realm.save()
        self.login_user(user)

        response = self.client_get("/billing/", follow=True)
        self.assert_in_success_response(
            ["Demo organizations cannot be directly upgraded to a paid plan."], response
        )

    def test_redirect_for_upgrade_page(self) -> None:
        user = self.example_user("iago")
        cordelia = self.example_user("cordelia")
        self.login_user(cordelia)
        # Cordelia is not in `can_manage_billing_group`, so can't access the page.
        response = self.client_get("/upgrade/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/billing/")

        self.login_user(user)

        response = self.client_get("/upgrade/")
        self.assertEqual(response.status_code, 200)

        user.realm.plan_type = Realm.PLAN_TYPE_STANDARD_FREE
        user.realm.save()
        response = self.client_get("/upgrade/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "http://zulip.testserver/sponsorship")

        stripe_customer_id = "cus_123"
        # Avoid contacting stripe as we only want to check redirects here.
        with (
            patch(
                "corporate.lib.stripe.customer_has_credit_card_as_default_payment_method",
                return_value=False,
            ),
            patch(
                "stripe.Customer.retrieve",
                return_value=Mock(id=stripe_customer_id, email="test@zulip.com"),
            ),
        ):
            user.realm.plan_type = Realm.PLAN_TYPE_LIMITED
            user.realm.save()
            customer = Customer.objects.create(
                realm=user.realm, stripe_customer_id=stripe_customer_id
            )
            response = self.client_get("/upgrade/")
            self.assertEqual(response.status_code, 200)

            CustomerPlan.objects.create(
                customer=customer,
                billing_cycle_anchor=timezone_now(),
                billing_schedule=CustomerPlan.BILLING_SCHEDULE_ANNUAL,
                tier=CustomerPlan.TIER_CLOUD_STANDARD,
            )
            response = self.client_get("/upgrade/")
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response["Location"], "http://zulip.testserver/billing")

            with self.settings(CLOUD_FREE_TRIAL_DAYS=30):
                response = self.client_get("/upgrade/")
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response["Location"], "http://zulip.testserver/billing")

    def test_get_latest_seat_count(self) -> None:
        realm = get_realm("zulip")
        initial_count = get_latest_seat_count(realm)
        user1 = UserProfile.objects.create(
            realm=realm, email="user1@zulip.com", delivery_email="user1@zulip.com"
        )
        user2 = UserProfile.objects.create(
            realm=realm, email="user2@zulip.com", delivery_email="user2@zulip.com"
        )
        self.assertEqual(get_latest_seat_count(realm), initial_count + 2)

        # Test that bots aren't counted
        user1.is_bot = True
        user1.save(update_fields=["is_bot"])
        self.assertEqual(get_latest_seat_count(realm), initial_count + 1)

        # Test that inactive users aren't counted
        do_deactivate_user(user2, acting_user=None)
        self.assertEqual(get_latest_seat_count(realm), initial_count)

        # Test guests
        # Adding a guest to a realm with a lot of members shouldn't change anything
        UserProfile.objects.create(
            realm=realm,
            email="user3@zulip.com",
            delivery_email="user3@zulip.com",
            role=UserProfile.ROLE_GUEST,
        )
        self.assertEqual(get_latest_seat_count(realm), initial_count)
        # Test 1 member and 5 guests
        realm = do_create_realm(string_id="second", name="second")
        UserProfile.objects.create(
            realm=realm, email="member@second.com", delivery_email="member@second.com"
        )
        for i in range(5):
            UserProfile.objects.create(
                realm=realm,
                email=f"guest{i}@second.com",
                delivery_email=f"guest{i}@second.com",
                role=UserProfile.ROLE_GUEST,
            )
        self.assertEqual(get_latest_seat_count(realm), 1)
        # Test 1 member and 6 guests
        UserProfile.objects.create(
            realm=realm,
            email="guest5@second.com",
            delivery_email="guest5@second.com",
            role=UserProfile.ROLE_GUEST,
        )
        self.assertEqual(get_latest_seat_count(realm), 2)

    def test_sign_string(self) -> None:
        string = "abc"
        signed_string, salt = sign_string(string)
        self.assertEqual(string, unsign_string(signed_string, salt))

        with self.assertRaises(signing.BadSignature):
            unsign_string(signed_string, "randomsalt")

    @mock_stripe()
    def test_payment_method_string(self, *mocks: Mock) -> None:
        # If you pay by invoice, your payment method should be
        # "Invoice", even if you have a card on file.
        user = self.example_user("hamlet")
        billing_session = RealmBillingSession(user)
        billing_session.create_stripe_customer()
        self.login_user(user)
        self.add_card_to_customer_for_upgrade()
        self.upgrade(invoice=True)
        response = self.client_get("/billing/")
        self.assert_not_in_success_response(["Visa ending in"], response)
        self.assert_in_success_response(["Invoice", "You will receive an invoice for"], response)

    @mock_stripe()
    def test_replace_payment_method(self, *mocks: Mock) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        self.add_card_and_upgrade(user)

        # Check that the card is displayed on the billing page.
        response = self.client_get("/billing/")
        self.assert_in_success_response(["Visa ending in 4242"], response)

        # Create an open invoice
        customer = Customer.objects.first()
        assert customer is not None
        stripe_customer_id = customer.stripe_customer_id
        assert stripe_customer_id is not None
        stripe_invoice = stripe.Invoice.create(customer=stripe_customer_id)
        assert stripe_invoice.id is not None
        stripe.InvoiceItem.create(
            invoice=stripe_invoice.id, amount=5000, currency="usd", customer=stripe_customer_id
        )
        stripe.Invoice.finalize_invoice(stripe_invoice)
        RealmAuditLog.objects.filter(event_type=AuditLogEventType.STRIPE_CARD_CHANGED).delete()

        start_session_json_response = self.client_billing_post(
            "/billing/session/start_card_update_session"
        )
        response_dict = self.assert_json_success(start_session_json_response)
        self.assert_details_of_valid_session_from_event_status_endpoint(
            response_dict["stripe_session_id"],
            {
                "type": "card_update_from_billing_page",
                "status": "created",
                "is_manual_license_management_upgrade_session": False,
                "tier": None,
            },
        )
        with self.assertRaises(stripe.CardError):
            # We don't have to handle this since the Stripe Checkout page would
            # ask Customer to enter a valid card number. trigger_stripe_checkout_session_completed_webhook
            # emulates what happens in the Stripe Checkout page. Adding this check mostly for coverage of
            # create_payment_method.
            self.trigger_stripe_checkout_session_completed_webhook(
                self.get_test_card_token(attaches_to_customer=False)
            )

        start_session_json_response = self.client_billing_post(
            "/billing/session/start_card_update_session"
        )
        response_dict = self.assert_json_success(start_session_json_response)
        self.assert_details_of_valid_session_from_event_status_endpoint(
            response_dict["stripe_session_id"],
            {
                "type": "card_update_from_billing_page",
                "status": "created",
                "is_manual_license_management_upgrade_session": False,
                "tier": None,
            },
        )
        with self.assertLogs("corporate.stripe", "INFO") as m:
            self.trigger_stripe_checkout_session_completed_webhook(
                self.get_test_card_token(attaches_to_customer=True, charge_succeeds=False)
            )
            self.assertEqual(
                m.output[0],
                "INFO:corporate.stripe:Stripe card error: 402 card_error card_declined None",
            )
        response_dict = self.assert_json_success(start_session_json_response)
        self.assert_details_of_valid_session_from_event_status_endpoint(
            response_dict["stripe_session_id"],
            {
                "type": "card_update_from_billing_page",
                "status": "completed",
                "is_manual_license_management_upgrade_session": False,
                "tier": None,
                "event_handler": {
                    "status": "failed",
                    "error": {"message": "Your card was declined.", "description": "card error"},
                },
            },
        )

        response = self.client_get("/billing/")
        self.assert_in_success_response(["Visa ending in 0341"], response)
        assert RealmAuditLog.objects.filter(
            event_type=AuditLogEventType.STRIPE_CARD_CHANGED
        ).exists()
        stripe_payment_methods = stripe.PaymentMethod.list(customer=stripe_customer_id, type="card")
        self.assert_length(stripe_payment_methods, 2)

        for stripe_payment_method in stripe_payment_methods:
            stripe.PaymentMethod.detach(stripe_payment_method.id)
        response = self.client_get("/billing/")
        self.assert_in_success_response(["No payment method on file."], response)

        start_session_json_response = self.client_billing_post(
            "/billing/session/start_card_update_session"
        )
        self.assert_json_success(start_session_json_response)
        self.trigger_stripe_checkout_session_completed_webhook(
            self.get_test_card_token(
                attaches_to_customer=True, charge_succeeds=True, card_provider="mastercard"
            )
        )
        response_dict = self.assert_json_success(start_session_json_response)
        self.assert_details_of_valid_session_from_event_status_endpoint(
            response_dict["stripe_session_id"],
            {
                "type": "card_update_from_billing_page",
                "status": "completed",
                "is_manual_license_management_upgrade_session": False,
                "tier": None,
                "event_handler": {"status": "succeeded"},
            },
        )

        self.login_user(self.example_user("othello"))
        response = self.client_billing_get(
            "/billing/event/status",
            {"stripe_session_id": response_dict["stripe_session_id"]},
        )
        self.assert_json_error_contains(response, "Insufficient permission")

        self.login_user(self.example_user("hamlet"))
        response = self.client_get("/billing/")
        self.assert_in_success_response(["Mastercard ending in 4444"], response)
        self.assert_length(stripe.PaymentMethod.list(customer=stripe_customer_id, type="card"), 1)
        # Ideally we'd also test that we don't pay invoices with collection_method=='send_invoice'
        for stripe_invoice in stripe.Invoice.list(customer=stripe_customer_id):
            self.assertEqual(stripe_invoice.status, "paid")
        self.assertEqual(
            2,
            RealmAuditLog.objects.filter(event_type=AuditLogEventType.STRIPE_CARD_CHANGED).count(),
        )

        # Test if manual license management upgrade session is created and is successfully recovered.
        start_session_json_response = self.client_billing_post(
            "/upgrade/session/start_card_update_session",
            {
                "manual_license_management": "true",
                "tier": 1,
            },
        )
        response_dict = self.assert_json_success(start_session_json_response)
        self.assert_details_of_valid_session_from_event_status_endpoint(
            response_dict["stripe_session_id"],
            {
                "type": "card_update_from_upgrade_page",
                "status": "created",
                "is_manual_license_management_upgrade_session": True,
                "tier": 1,
            },
        )

    def test_downgrade(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        with time_machine.travel(self.now, tick=False):
            self.local_upgrade(
                self.seat_count, True, CustomerPlan.BILLING_SCHEDULE_ANNUAL, True, False
            )
        customer = get_customer_by_realm(user.realm)
        assert customer is not None
        plan = get_current_plan_by_customer(customer)
        assert plan is not None
        self.assertEqual(plan.licenses(), self.seat_count)
        self.assertEqual(plan.licenses_at_next_renewal(), self.seat_count)
        with (
            self.assertLogs("corporate.stripe", "INFO") as m,
            time_machine.travel(self.now, tick=False),
        ):
            response = self.client_billing_patch(
                "/billing/plan",
                {"status": CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE},
            )
            expected_log = f"INFO:corporate.stripe:Change plan status: Customer.id: {customer.id}, CustomerPlan.id: {plan.id}, status: {CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE}"
            self.assertEqual(m.output[0], expected_log)
            self.assert_json_success(response)
        plan.refresh_from_db()
        self.assertEqual(plan.licenses(), self.seat_count)
        self.assertEqual(plan.licenses_at_next_renewal(), None)

        with time_machine.travel(self.now, tick=False):
            mock_customer = Mock(email=user.delivery_email)
            mock_customer.invoice_settings.default_payment_method = Mock(
                spec=stripe.PaymentMethod, type=Mock()
            )
            with patch("corporate.lib.stripe.stripe_get_customer", return_value=mock_customer):
                response = self.client_get("/billing/")
                self.assert_in_success_response(
                    [
                        "Your organization will be downgraded to <strong>Zulip Cloud Free</strong> at the end of the current billing",
                        "<strong>January 2, 2013</strong>",
                        "Reactivate subscription",
                    ],
                    response,
                )

        # Verify that we still write LicenseLedger rows during the remaining
        # part of the cycle
        billing_session = RealmBillingSession(user=user, realm=user.realm)
        with patch("corporate.lib.stripe.get_latest_seat_count", return_value=20):
            billing_session.update_license_ledger_if_needed(self.now)
        self.check_last_ledger_entry_license_counts(plan, 20, 20)

        # Verify that we invoice them for the additional users
        mocked = self.setup_mocked_stripe(invoice_plans_as_needed, self.next_month)
        mocked["InvoiceItem"].create.assert_called_once()
        mocked["Invoice"].finalize_invoice.assert_called_once()
        mocked["Invoice"].create.assert_called_once()

        # Check that we downgrade properly if the cycle is over
        with patch("corporate.lib.stripe.get_latest_seat_count", return_value=30):
            billing_session.update_license_ledger_if_needed(self.next_year)
        plan.refresh_from_db()
        self.assertEqual(get_realm("zulip").plan_type, Realm.PLAN_TYPE_LIMITED)
        self.assertEqual(plan.status, CustomerPlan.ENDED)
        self.check_last_ledger_entry_license_counts(plan, 20, 20)

        realm_audit_log = RealmAuditLog.objects.latest("id")
        self.assertEqual(realm_audit_log.event_type, AuditLogEventType.REALM_PLAN_TYPE_CHANGED)
        self.assertEqual(realm_audit_log.acting_user, None)

        # Verify that we don't write LicenseLedger rows once we've downgraded
        with patch("corporate.lib.stripe.get_latest_seat_count", return_value=40):
            billing_session.update_license_ledger_if_needed(self.next_year)
        self.check_last_ledger_entry_license_counts(plan, 20, 20)

        # Verify that we call invoice_plan once more after cycle end but
        # don't invoice them for users added after the cycle end
        plan.refresh_from_db()
        self.assertIsNotNone(plan.next_invoice_date)

        mocked = self.setup_mocked_stripe(
            invoice_plans_as_needed, self.next_year + timedelta(days=32)
        )
        mocked["InvoiceItem"].create.assert_not_called()
        mocked["Invoice"].finalize_invoice.assert_not_called()
        mocked["Invoice"].create.assert_not_called()

        # Check that we updated next_invoice_date in invoice_plan
        plan.refresh_from_db()
        self.assertIsNone(plan.next_invoice_date)

        # Check that we don't call invoice_plan after that final call
        with patch("corporate.lib.stripe.get_latest_seat_count", return_value=50):
            billing_session.update_license_ledger_if_needed(self.next_year + timedelta(days=80))

        mocked = self.setup_mocked_stripe(
            invoice_plans_as_needed, self.next_year + timedelta(days=400)
        )
        mocked["InvoiceItem"].create.assert_not_called()
        mocked["Invoice"].finalize_invoice.assert_not_called()
        mocked["Invoice"].create.assert_not_called()

    @mock_stripe()
    def test_switch_from_monthly_plan_to_annual_plan_for_automatic_license_management(
        self, *mocks: Mock
    ) -> None:
        user = self.example_user("hamlet")

        self.login_user(user)
        self.add_card_and_upgrade(user, schedule="monthly")
        customer = get_customer_by_realm(user.realm)
        assert customer is not None
        monthly_plan = get_current_plan_by_customer(customer)
        assert monthly_plan is not None
        self.assertEqual(monthly_plan.automanage_licenses, True)
        self.assertEqual(monthly_plan.billing_schedule, CustomerPlan.BILLING_SCHEDULE_MONTHLY)

        with (
            self.assertLogs("corporate.stripe", "INFO") as m,
            time_machine.travel(self.now, tick=False),
        ):
            response = self.client_billing_patch(
                "/billing/plan",
                {"status": CustomerPlan.SWITCH_TO_ANNUAL_AT_END_OF_CYCLE},
            )
            expected_log = f"INFO:corporate.stripe:Change plan status: Customer.id: {customer.id}, CustomerPlan.id: {monthly_plan.id}, status: {CustomerPlan.SWITCH_TO_ANNUAL_AT_END_OF_CYCLE}"
            self.assertEqual(m.output[0], expected_log)
            self.assert_json_success(response)
        monthly_plan.refresh_from_db()
        self.assertEqual(monthly_plan.status, CustomerPlan.SWITCH_TO_ANNUAL_AT_END_OF_CYCLE)
        with time_machine.travel(self.now, tick=False):
            response = self.client_get("/billing/")
        self.assert_in_success_response(
            ["Your plan will switch to annual billing on February 2, 2012"], response
        )

        billing_session = RealmBillingSession(user=user, realm=user.realm)
        with patch("corporate.lib.stripe.get_latest_seat_count", return_value=20):
            billing_session.update_license_ledger_if_needed(self.now)
        self.assertEqual(LicenseLedger.objects.filter(plan=monthly_plan).count(), 2)
        self.check_last_ledger_entry_license_counts(monthly_plan, 20, 20)

        with (
            time_machine.travel(self.next_month, tick=False),
            patch("corporate.lib.stripe.get_latest_seat_count", return_value=25),
        ):
            billing_session.update_license_ledger_if_needed(self.next_month)
        self.assertEqual(LicenseLedger.objects.filter(plan=monthly_plan).count(), 2)
        customer = get_customer_by_realm(user.realm)
        assert customer is not None
        self.assertEqual(CustomerPlan.objects.filter(customer=customer).count(), 2)
        monthly_plan.refresh_from_db()
        self.assertEqual(monthly_plan.status, CustomerPlan.ENDED)
        self.assertEqual(monthly_plan.next_invoice_date, self.next_month)
        annual_plan = get_current_plan_by_realm(user.realm)
        assert annual_plan is not None
        self.assertEqual(annual_plan.status, CustomerPlan.ACTIVE)
        self.assertEqual(annual_plan.billing_schedule, CustomerPlan.BILLING_SCHEDULE_ANNUAL)
        self.assertEqual(
            annual_plan.invoicing_status, CustomerPlan.INVOICING_STATUS_INITIAL_INVOICE_TO_BE_SENT
        )
        self.assertEqual(annual_plan.billing_cycle_anchor, self.next_month)
        self.assertEqual(annual_plan.next_invoice_date, self.next_month)
        self.assertEqual(annual_plan.invoiced_through, None)
        annual_ledger_entries = LicenseLedger.objects.filter(plan=annual_plan).order_by("id")
        self.assert_length(annual_ledger_entries, 2)
        self.assertEqual(annual_ledger_entries[0].is_renewal, True)
        self.assertEqual(
            annual_ledger_entries.values_list("licenses", "licenses_at_next_renewal")[0], (20, 20)
        )
        self.assertEqual(annual_ledger_entries[1].is_renewal, False)
        self.assertEqual(
            annual_ledger_entries.values_list("licenses", "licenses_at_next_renewal")[1], (25, 25)
        )
        audit_log = RealmAuditLog.objects.get(
            event_type=AuditLogEventType.CUSTOMER_SWITCHED_FROM_MONTHLY_TO_ANNUAL_PLAN
        )
        self.assertEqual(audit_log.realm, user.realm)
        self.assertEqual(audit_log.extra_data["monthly_plan_id"], monthly_plan.id)
        self.assertEqual(audit_log.extra_data["annual_plan_id"], annual_plan.id)

        invoice_plans_as_needed(self.next_month)

        annual_ledger_entries = LicenseLedger.objects.filter(plan=annual_plan).order_by("id")
        self.assert_length(annual_ledger_entries, 2)
        annual_plan.refresh_from_db()
        self.assertEqual(annual_plan.invoicing_status, CustomerPlan.INVOICING_STATUS_DONE)
        self.assertEqual(annual_plan.invoiced_through, annual_ledger_entries[1])
        self.assertEqual(annual_plan.billing_cycle_anchor, self.next_month)
        self.assertEqual(annual_plan.next_invoice_date, add_months(self.next_month, 1))
        monthly_plan.refresh_from_db()
        self.assertEqual(monthly_plan.next_invoice_date, None)

        assert customer.stripe_customer_id
        [invoice0, invoice1, _invoice2] = iter(
            stripe.Invoice.list(customer=customer.stripe_customer_id)
        )

        [invoice_item0, invoice_item1] = iter(invoice0.lines)
        self.assertEqual(invoice_item0.amount, 5 * 80 * 100)
        self.assertEqual(invoice_item0.description, "Additional Zulip Cloud Standard license")
        self.assertEqual(invoice_item0.quantity, 5)
        self.assertEqual(invoice_item0.discountable, False)
        self.assertEqual(invoice_item0.period.start, datetime_to_timestamp(self.next_month))
        self.assertEqual(
            invoice_item0.period.end, datetime_to_timestamp(add_months(self.next_month, 12))
        )

        self.assertEqual(invoice_item1.amount, 20 * 80 * 100)
        self.assertEqual(invoice_item1.description, "Zulip Cloud Standard - renewal")
        self.assertEqual(invoice_item1.quantity, 20)
        self.assertFalse(invoice_item1.discountable)
        self.assertEqual(invoice_item1.period.start, datetime_to_timestamp(self.next_month))
        self.assertEqual(
            invoice_item1.period.end, datetime_to_timestamp(add_months(self.next_month, 12))
        )

        [monthly_plan_invoice_item] = iter(invoice1.lines)
        self.assertEqual(monthly_plan_invoice_item.amount, 14 * 8 * 100)
        self.assertEqual(
            monthly_plan_invoice_item.description, "Additional Zulip Cloud Standard license"
        )
        self.assertEqual(monthly_plan_invoice_item.quantity, 14)
        self.assertFalse(monthly_plan_invoice_item.discountable)
        self.assertEqual(monthly_plan_invoice_item.period.start, datetime_to_timestamp(self.now))
        self.assertEqual(
            monthly_plan_invoice_item.period.end, datetime_to_timestamp(self.next_month)
        )

        with patch("corporate.lib.stripe.get_latest_seat_count", return_value=30):
            billing_session.update_license_ledger_if_needed(add_months(self.next_month, 1))
        invoice_plans_as_needed(add_months(self.next_month, 1))

        [invoice0, invoice1, _invoice2, _invoice3] = iter(
            stripe.Invoice.list(customer=customer.stripe_customer_id)
        )

        [monthly_plan_invoice_item] = iter(invoice0.lines)
        self.assertEqual(monthly_plan_invoice_item.amount, 5 * 7366)
        self.assertEqual(
            monthly_plan_invoice_item.description, "Additional Zulip Cloud Standard license"
        )
        self.assertEqual(monthly_plan_invoice_item.quantity, 5)
        self.assertFalse(monthly_plan_invoice_item.discountable)
        self.assertEqual(
            monthly_plan_invoice_item.period.start,
            datetime_to_timestamp(add_months(self.next_month, 1)),
        )
        self.assertEqual(
            monthly_plan_invoice_item.period.end,
            datetime_to_timestamp(add_months(self.next_month, 12)),
        )

        # Fast forward next_invoice_date to one year from the day we switched to annual plan.
        annual_plan.next_invoice_date = add_months(self.now, 13)
        annual_plan.save(update_fields=["next_invoice_date"])
        invoice_plans_as_needed(add_months(self.now, 13))

        [invoice0, invoice1, _invoice2, _invoice3, _invoice4] = iter(
            stripe.Invoice.list(customer=customer.stripe_customer_id)
        )

        [invoice_item] = iter(invoice0.lines)
        self.assertEqual(invoice_item.amount, 30 * 80 * 100)
        self.assertEqual(invoice_item.description, "Zulip Cloud Standard - renewal")
        self.assertEqual(invoice_item.quantity, 30)
        self.assertFalse(invoice_item.discountable)
        self.assertEqual(
            invoice_item.period.start, datetime_to_timestamp(add_months(self.next_month, 12))
        )
        self.assertEqual(
            invoice_item.period.end, datetime_to_timestamp(add_months(self.next_month, 24))
        )

    @mock_stripe()
    def test_switch_from_monthly_plan_to_annual_plan_for_manual_license_management(
        self, *mocks: Mock
    ) -> None:
        user = self.example_user("hamlet")
        num_licenses = 35

        self.login_user(user)
        self.add_card_and_upgrade(
            user, schedule="monthly", license_management="manual", licenses=num_licenses
        )
        customer = get_customer_by_realm(user.realm)
        assert customer is not None
        monthly_plan = get_current_plan_by_customer(customer)
        assert monthly_plan is not None
        self.assertEqual(monthly_plan.automanage_licenses, False)
        self.assertEqual(monthly_plan.billing_schedule, CustomerPlan.BILLING_SCHEDULE_MONTHLY)
        with (
            self.assertLogs("corporate.stripe", "INFO") as m,
            time_machine.travel(self.now, tick=False),
        ):
            response = self.client_billing_patch(
                "/billing/plan",
                {"status": CustomerPlan.SWITCH_TO_ANNUAL_AT_END_OF_CYCLE},
            )
            self.assertEqual(
                m.output[0],
                f"INFO:corporate.stripe:Change plan status: Customer.id: {customer.id}, CustomerPlan.id: {monthly_plan.id}, status: {CustomerPlan.SWITCH_TO_ANNUAL_AT_END_OF_CYCLE}",
            )
            self.assert_json_success(response)
        monthly_plan.refresh_from_db()
        self.assertEqual(monthly_plan.status, CustomerPlan.SWITCH_TO_ANNUAL_AT_END_OF_CYCLE)
        with time_machine.travel(self.now, tick=False):
            response = self.client_get("/billing/")
        self.assert_in_success_response(
            ["Your plan will switch to annual billing on February 2, 2012"], response
        )

        invoice_plans_as_needed(self.next_month)

        self.assertEqual(LicenseLedger.objects.filter(plan=monthly_plan).count(), 1)
        customer = get_customer_by_realm(user.realm)
        assert customer is not None
        self.assertEqual(CustomerPlan.objects.filter(customer=customer).count(), 2)
        monthly_plan.refresh_from_db()
        self.assertEqual(monthly_plan.status, CustomerPlan.ENDED)
        self.assertEqual(monthly_plan.next_invoice_date, None)
        annual_plan = get_current_plan_by_realm(user.realm)
        assert annual_plan is not None
        self.assertEqual(annual_plan.status, CustomerPlan.ACTIVE)
        self.assertEqual(annual_plan.billing_schedule, CustomerPlan.BILLING_SCHEDULE_ANNUAL)
        self.assertEqual(
            annual_plan.invoicing_status, CustomerPlan.INVOICING_STATUS_INITIAL_INVOICE_TO_BE_SENT
        )
        self.assertEqual(annual_plan.billing_cycle_anchor, self.next_month)
        self.assertEqual(annual_plan.next_invoice_date, self.next_month)
        annual_ledger_entries = LicenseLedger.objects.filter(plan=annual_plan).order_by("id")
        self.assert_length(annual_ledger_entries, 1)
        self.assertEqual(annual_ledger_entries[0].is_renewal, True)
        self.assertEqual(
            annual_ledger_entries.values_list("licenses", "licenses_at_next_renewal")[0],
            (num_licenses, num_licenses),
        )
        self.assertEqual(annual_plan.invoiced_through, None)

        # First call of invoice_plans_as_needed creates the new plan. Second call
        # calls invoice_plan on the newly created plan.
        invoice_plans_as_needed(self.next_month + timedelta(days=1))

        annual_plan.refresh_from_db()
        self.assertEqual(annual_plan.invoiced_through, annual_ledger_entries[0])
        self.assertEqual(annual_plan.next_invoice_date, add_months(self.next_month, 1))
        self.assertEqual(annual_plan.invoicing_status, CustomerPlan.INVOICING_STATUS_DONE)

        assert customer.stripe_customer_id
        [invoice0, _invoice1] = iter(stripe.Invoice.list(customer=customer.stripe_customer_id))

        [invoice_item] = iter(invoice0.lines)
        self.assertEqual(invoice_item.amount, num_licenses * 80 * 100)
        self.assertEqual(invoice_item.description, "Zulip Cloud Standard - renewal")
        self.assertEqual(invoice_item.quantity, num_licenses)
        self.assertFalse(invoice_item.discountable)
        self.assertEqual(invoice_item.period.start, datetime_to_timestamp(self.next_month))
        self.assertEqual(
            invoice_item.period.end, datetime_to_timestamp(add_months(self.next_month, 12))
        )

        invoice_plans_as_needed(add_months(self.now, 13))

        [invoice0, _invoice1, _invoice2] = iter(
            stripe.Invoice.list(customer=customer.stripe_customer_id)
        )

        [invoice_item] = iter(invoice0.lines)
        self.assertEqual(invoice_item.amount, num_licenses * 80 * 100)
        self.assertEqual(invoice_item.description, "Zulip Cloud Standard - renewal")
        self.assertEqual(invoice_item.quantity, num_licenses)
        self.assertFalse(invoice_item.discountable)
        self.assertEqual(
            invoice_item.period.start, datetime_to_timestamp(add_months(self.next_month, 12))
        )
        self.assertEqual(
            invoice_item.period.end, datetime_to_timestamp(add_months(self.next_month, 24))
        )

    @mock_stripe()
    def test_switch_from_annual_plan_to_monthly_plan_for_automatic_license_management(
        self, *mocks: Mock
    ) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        self.add_card_and_upgrade(user, schedule="annual")
        customer = get_customer_by_realm(user.realm)
        assert customer is not None
        annual_plan = get_current_plan_by_customer(customer)
        assert annual_plan is not None
        self.assertEqual(annual_plan.automanage_licenses, True)
        self.assertEqual(annual_plan.billing_schedule, CustomerPlan.BILLING_SCHEDULE_ANNUAL)

        assert self.now is not None
        with (
            self.assertLogs("corporate.stripe", "INFO") as m,
            time_machine.travel(self.now, tick=False),
        ):
            response = self.client_billing_patch(
                "/billing/plan",
                {"status": CustomerPlan.SWITCH_TO_MONTHLY_AT_END_OF_CYCLE},
            )
            expected_log = f"INFO:corporate.stripe:Change plan status: Customer.id: {customer.id}, CustomerPlan.id: {annual_plan.id}, status: {CustomerPlan.SWITCH_TO_MONTHLY_AT_END_OF_CYCLE}"
            self.assertEqual(m.output[0], expected_log)
            self.assert_json_success(response)
        annual_plan.refresh_from_db()
        self.assertEqual(annual_plan.status, CustomerPlan.SWITCH_TO_MONTHLY_AT_END_OF_CYCLE)
        with time_machine.travel(self.now, tick=False):
            response = self.client_get("/billing/")
        self.assert_in_success_response(
            ["Your plan will switch to monthly billing on January 2, 2013"], response
        )

        billing_session = RealmBillingSession(user=user, realm=user.realm)
        with patch("corporate.lib.stripe.get_latest_seat_count", return_value=20):
            billing_session.update_license_ledger_if_needed(self.now)
        self.assertEqual(LicenseLedger.objects.filter(plan=annual_plan).count(), 2)
        self.check_last_ledger_entry_license_counts(annual_plan, 20, 20)

        # Check that we don't switch to monthly plan at next invoice date (which is used to charge user for
        # additional licenses) but at the end of current billing cycle.
        self.assertEqual(annual_plan.next_invoice_date, self.next_month)
        assert annual_plan.next_invoice_date is not None
        with (
            time_machine.travel(annual_plan.next_invoice_date, tick=False),
            patch("corporate.lib.stripe.get_latest_seat_count", return_value=25),
        ):
            billing_session.update_license_ledger_if_needed(annual_plan.next_invoice_date)

        annual_plan.refresh_from_db()
        self.assertEqual(annual_plan.status, CustomerPlan.SWITCH_TO_MONTHLY_AT_END_OF_CYCLE)
        self.assertEqual(annual_plan.next_invoice_date, self.next_month)
        self.assertEqual(annual_plan.billing_schedule, CustomerPlan.BILLING_SCHEDULE_ANNUAL)
        self.assertEqual(LicenseLedger.objects.filter(plan=annual_plan).count(), 3)

        invoice_plans_as_needed(self.next_month + timedelta(days=1))

        annual_plan.refresh_from_db()
        self.assertEqual(annual_plan.next_invoice_date, add_months(self.next_month, 1))
        self.assertEqual(annual_plan.invoicing_status, CustomerPlan.INVOICING_STATUS_DONE)
        self.assertEqual(LicenseLedger.objects.filter(plan=annual_plan).count(), 3)

        customer = get_customer_by_realm(user.realm)
        assert customer is not None
        assert customer.stripe_customer_id
        [invoice0, _invoice1] = iter(stripe.Invoice.list(customer=customer.stripe_customer_id))
        [invoice_item1, invoice_item2] = iter(invoice0.lines)
        self.assertEqual(invoice_item1.amount, 7322 * 5)
        self.assertEqual(invoice_item1.description, "Additional Zulip Cloud Standard license")
        self.assertEqual(invoice_item1.quantity, 5)
        self.assertFalse(invoice_item1.discountable)
        self.assertEqual(invoice_item1.period.start, datetime_to_timestamp(self.next_month))
        self.assertEqual(invoice_item1.period.end, datetime_to_timestamp(self.next_year))

        self.assertEqual(invoice_item2.amount, 14 * 80 * 1 * 100)
        self.assertEqual(invoice_item2.description, "Additional Zulip Cloud Standard license")
        self.assertEqual(invoice_item2.quantity, 14)
        self.assertFalse(invoice_item2.discountable)
        self.assertEqual(invoice_item2.period.start, datetime_to_timestamp(self.now))
        self.assertEqual(invoice_item2.period.end, datetime_to_timestamp(self.next_year))

        # Check that we switch to monthly plan at the end of current billing cycle.
        with (
            time_machine.travel(self.next_year, tick=False),
            patch("corporate.lib.stripe.get_latest_seat_count", return_value=25),
        ):
            billing_session.update_license_ledger_if_needed(self.next_year)
        self.assertEqual(LicenseLedger.objects.filter(plan=annual_plan).count(), 3)
        customer = get_customer_by_realm(user.realm)
        assert customer is not None
        annual_plan.refresh_from_db()
        self.assertEqual(annual_plan.status, CustomerPlan.ENDED)
        self.assertEqual(annual_plan.next_invoice_date, add_months(self.next_month, 1))
        monthly_plan = get_current_plan_by_realm(user.realm)
        assert monthly_plan is not None
        self.assertEqual(monthly_plan.status, CustomerPlan.ACTIVE)
        self.assertEqual(monthly_plan.billing_schedule, CustomerPlan.BILLING_SCHEDULE_MONTHLY)
        self.assertEqual(
            monthly_plan.invoicing_status, CustomerPlan.INVOICING_STATUS_INITIAL_INVOICE_TO_BE_SENT
        )
        self.assertEqual(monthly_plan.billing_cycle_anchor, self.next_year)
        self.assertEqual(monthly_plan.next_invoice_date, self.next_year)
        self.assertEqual(monthly_plan.invoiced_through, None)
        monthly_ledger_entries = LicenseLedger.objects.filter(plan=monthly_plan).order_by("id")
        self.assert_length(monthly_ledger_entries, 2)
        self.assertEqual(monthly_ledger_entries[0].is_renewal, True)
        self.assertEqual(
            monthly_ledger_entries.values_list("licenses", "licenses_at_next_renewal")[0], (25, 25)
        )
        self.assertEqual(monthly_ledger_entries[1].is_renewal, False)
        self.assertEqual(
            monthly_ledger_entries.values_list("licenses", "licenses_at_next_renewal")[1], (25, 25)
        )
        audit_log = RealmAuditLog.objects.get(
            event_type=AuditLogEventType.CUSTOMER_SWITCHED_FROM_ANNUAL_TO_MONTHLY_PLAN
        )
        self.assertEqual(audit_log.realm, user.realm)
        self.assertEqual(audit_log.extra_data["annual_plan_id"], annual_plan.id)
        self.assertEqual(audit_log.extra_data["monthly_plan_id"], monthly_plan.id)

        invoice_plans_as_needed(self.next_year)

        monthly_ledger_entries = LicenseLedger.objects.filter(plan=monthly_plan).order_by("id")
        self.assert_length(monthly_ledger_entries, 2)
        monthly_plan.refresh_from_db()
        self.assertEqual(monthly_plan.invoicing_status, CustomerPlan.INVOICING_STATUS_DONE)
        self.assertEqual(monthly_plan.invoiced_through, monthly_ledger_entries[1])
        self.assertEqual(monthly_plan.billing_cycle_anchor, self.next_year)
        self.assertEqual(monthly_plan.next_invoice_date, add_months(self.next_year, 1))
        annual_plan.refresh_from_db()
        self.assertEqual(annual_plan.next_invoice_date, None)

        assert customer.stripe_customer_id
        [invoice0, _invoice1, _invoice2] = iter(
            stripe.Invoice.list(customer=customer.stripe_customer_id)
        )

        [invoice_item0] = iter(invoice0.lines)

        self.assertEqual(invoice_item0.amount, 25 * 8 * 100)
        self.assertEqual(invoice_item0.description, "Zulip Cloud Standard - renewal")
        self.assertEqual(invoice_item0.quantity, 25)
        self.assertFalse(invoice_item0.discountable)
        self.assertEqual(invoice_item0.period.start, datetime_to_timestamp(self.next_year))
        self.assertEqual(
            invoice_item0.period.end, datetime_to_timestamp(add_months(self.next_year, 1))
        )

        with time_machine.travel(self.next_year, tick=False):
            response = self.client_get("/billing/")
        self.assert_not_in_success_response(
            ["Your plan will switch to annual billing on February 2, 2012"], response
        )

    def test_reupgrade_after_plan_status_changed_to_downgrade_at_end_of_cycle(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        with time_machine.travel(self.now, tick=False):
            self.local_upgrade(
                self.seat_count, True, CustomerPlan.BILLING_SCHEDULE_ANNUAL, True, False
            )
        with (
            self.assertLogs("corporate.stripe", "INFO") as m,
            time_machine.travel(self.now, tick=False),
        ):
            response = self.client_billing_patch(
                "/billing/plan",
                {"status": CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE},
            )
            customer = get_customer_by_realm(user.realm)
            assert customer is not None
            plan = get_current_plan_by_customer(customer)
            assert plan is not None
            expected_log = f"INFO:corporate.stripe:Change plan status: Customer.id: {customer.id}, CustomerPlan.id: {plan.id}, status: {CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE}"
            self.assertEqual(m.output[0], expected_log)
            self.assert_json_success(response)
        plan.refresh_from_db()
        self.assertEqual(plan.status, CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE)
        with (
            self.assertLogs("corporate.stripe", "INFO") as m,
            time_machine.travel(self.now, tick=False),
        ):
            response = self.client_billing_patch(
                "/billing/plan",
                {"status": CustomerPlan.ACTIVE},
            )
            expected_log = f"INFO:corporate.stripe:Change plan status: Customer.id: {customer.id}, CustomerPlan.id: {plan.id}, status: {CustomerPlan.ACTIVE}"
            self.assertEqual(m.output[0], expected_log)
            self.assert_json_success(response)
        plan.refresh_from_db()
        self.assertEqual(plan.status, CustomerPlan.ACTIVE)

    @patch("stripe.Invoice.create")
    @patch("stripe.Invoice.finalize_invoice")
    @patch("stripe.InvoiceItem.create")
    def test_downgrade_during_invoicing(self, *mocks: Mock) -> None:
        # The difference between this test and test_downgrade is that
        # CustomerPlan.status is DOWNGRADE_AT_END_OF_CYCLE rather than ENDED
        # when we call invoice_plans_as_needed
        # This test is essentially checking that we call make_end_of_cycle_updates_if_needed
        # during the invoicing process.
        user = self.example_user("hamlet")
        self.login_user(user)
        with time_machine.travel(self.now, tick=False):
            self.local_upgrade(
                self.seat_count, True, CustomerPlan.BILLING_SCHEDULE_ANNUAL, True, False
            )
        customer = get_customer_by_realm(user.realm)
        assert customer is not None
        plan = get_current_plan_by_customer(customer)
        assert plan is not None
        with self.assertLogs("corporate.stripe", "INFO") as m:
            with time_machine.travel(self.now, tick=False):
                self.client_billing_patch(
                    "/billing/plan",
                    {"status": CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE},
                )
            expected_log = f"INFO:corporate.stripe:Change plan status: Customer.id: {customer.id}, CustomerPlan.id: {plan.id}, status: {CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE}"
            self.assertEqual(m.output[0], expected_log)
        plan.refresh_from_db()
        self.assertIsNotNone(plan.next_invoice_date)
        self.assertEqual(plan.status, CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE)
        # Fast forward the next_invoice_date to next year.
        plan.next_invoice_date = self.next_year
        plan.save(update_fields=["next_invoice_date"])
        invoice_plans_as_needed(self.next_year)
        plan.refresh_from_db()
        self.assertIsNone(plan.next_invoice_date)
        self.assertEqual(plan.status, CustomerPlan.ENDED)

    @mock_stripe()
    def test_switch_now_free_trial_from_monthly_to_annual(self, *mocks: Mock) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)

        free_trial_end_date = self.now + timedelta(days=60)
        with self.settings(CLOUD_FREE_TRIAL_DAYS=60), time_machine.travel(self.now, tick=False):
            self.add_card_and_upgrade(user, schedule="monthly")
            plan = CustomerPlan.objects.get()
            self.assertEqual(plan.next_invoice_date, free_trial_end_date)
            self.assertEqual(get_realm("zulip").plan_type, Realm.PLAN_TYPE_STANDARD)
            self.assertEqual(plan.status, CustomerPlan.FREE_TRIAL)

            customer = get_customer_by_realm(user.realm)
            assert customer is not None
            result = self.client_billing_patch(
                "/billing/plan",
                {
                    "status": CustomerPlan.FREE_TRIAL,
                    "schedule": CustomerPlan.BILLING_SCHEDULE_ANNUAL,
                },
            )
            self.assert_json_success(result)

            plan.refresh_from_db()
            self.assertEqual(plan.status, CustomerPlan.ENDED)
            self.assertIsNone(plan.next_invoice_date)

            new_plan = CustomerPlan.objects.get(
                customer=customer,
                automanage_licenses=True,
                price_per_license=8000,
                fixed_price=None,
                discount=None,
                billing_cycle_anchor=self.now,
                billing_schedule=CustomerPlan.BILLING_SCHEDULE_ANNUAL,
                next_invoice_date=free_trial_end_date,
                tier=CustomerPlan.TIER_CLOUD_STANDARD,
                status=CustomerPlan.FREE_TRIAL,
                charge_automatically=True,
            )
            ledger_entry = self.check_initial_ledger_entry(new_plan, self.seat_count)
            self.assertEqual(new_plan.invoiced_through, ledger_entry)

            realm_audit_log = RealmAuditLog.objects.filter(
                event_type=AuditLogEventType.CUSTOMER_SWITCHED_FROM_MONTHLY_TO_ANNUAL_PLAN
            ).last()
            assert realm_audit_log is not None

    @mock_stripe()
    def test_switch_now_free_trial_from_annual_to_monthly(self, *mocks: Mock) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)

        free_trial_end_date = self.now + timedelta(days=60)
        with self.settings(CLOUD_FREE_TRIAL_DAYS=60), time_machine.travel(self.now, tick=False):
            self.add_card_and_upgrade(user, schedule="annual")
            plan = CustomerPlan.objects.get()
            self.assertEqual(plan.next_invoice_date, free_trial_end_date)
            self.assertEqual(get_realm("zulip").plan_type, Realm.PLAN_TYPE_STANDARD)
            self.assertEqual(plan.status, CustomerPlan.FREE_TRIAL)

            customer = get_customer_by_realm(user.realm)
            assert customer is not None
            result = self.client_billing_patch(
                "/billing/plan",
                {
                    "status": CustomerPlan.FREE_TRIAL,
                    "schedule": CustomerPlan.BILLING_SCHEDULE_MONTHLY,
                },
            )
            self.assert_json_success(result)
            plan.refresh_from_db()
            self.assertEqual(plan.status, CustomerPlan.ENDED)
            self.assertIsNone(plan.next_invoice_date)

            new_plan = CustomerPlan.objects.get(
                customer=customer,
                automanage_licenses=True,
                price_per_license=800,
                fixed_price=None,
                discount=None,
                billing_cycle_anchor=self.now,
                billing_schedule=CustomerPlan.BILLING_SCHEDULE_MONTHLY,
                next_invoice_date=free_trial_end_date,
                tier=CustomerPlan.TIER_CLOUD_STANDARD,
                status=CustomerPlan.FREE_TRIAL,
                charge_automatically=True,
            )
            ledger_entry = self.check_initial_ledger_entry(new_plan, self.seat_count)
            self.assertEqual(new_plan.invoiced_through, ledger_entry)

            realm_audit_log = RealmAuditLog.objects.filter(
                event_type=AuditLogEventType.CUSTOMER_SWITCHED_FROM_ANNUAL_TO_MONTHLY_PLAN
            ).last()
            assert realm_audit_log is not None

    @mock_stripe()
    def test_end_free_trial(self, *mocks: Mock) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)

        free_trial_end_date = self.now + timedelta(days=60)
        with self.settings(CLOUD_FREE_TRIAL_DAYS=60):
            with time_machine.travel(self.now, tick=False):
                self.add_card_and_upgrade(user, schedule="annual")

            plan = CustomerPlan.objects.get()
            self.assertEqual(plan.next_invoice_date, free_trial_end_date)
            self.assertEqual(get_realm("zulip").plan_type, Realm.PLAN_TYPE_STANDARD)
            self.assertEqual(plan.status, CustomerPlan.FREE_TRIAL)

            # Add some extra users before the realm is deactivated
            billing_session = RealmBillingSession(user=user, realm=user.realm)
            with patch("corporate.lib.stripe.get_latest_seat_count", return_value=21):
                billing_session.update_license_ledger_if_needed(self.now)

            last_ledger_entry = self.check_last_ledger_entry_license_counts(plan, 21, 21)

            self.login_user(user)

            with time_machine.travel(self.now, tick=False):
                self.client_billing_patch(
                    "/billing/plan",
                    {"status": CustomerPlan.ENDED},
                )

            plan.refresh_from_db()
            self.assertEqual(get_realm("zulip").plan_type, Realm.PLAN_TYPE_LIMITED)
            self.assertEqual(plan.status, CustomerPlan.ENDED)
            self.assertEqual(plan.invoiced_through, last_ledger_entry)
            self.assertIsNone(plan.next_invoice_date)

            self.login_user(user)
            response = self.client_get("/billing/")
            self.assertEqual(response.status_code, 302)
            self.assertEqual("/plans/", response["Location"])

            # The extra users added in the final month are not charged
            with patch("corporate.lib.stripe.BillingSession.invoice_plan") as mocked:
                invoice_plans_as_needed(self.next_month)
            mocked.assert_not_called()

            # The plan is not renewed after an year
            with patch("corporate.lib.stripe.BillingSession.invoice_plan") as mocked:
                invoice_plans_as_needed(self.next_year)
            mocked.assert_not_called()

    @mock_stripe()
    def test_downgrade_at_end_of_free_trial(self, *mocks: Mock) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)

        free_trial_end_date = self.now + timedelta(days=60)
        with self.settings(CLOUD_FREE_TRIAL_DAYS=60):
            with time_machine.travel(self.now, tick=False):
                self.add_card_and_upgrade(user, schedule="annual")
            customer = get_customer_by_realm(user.realm)
            assert customer is not None
            plan = get_current_plan_by_customer(customer)
            assert plan is not None
            self.assertEqual(plan.next_invoice_date, free_trial_end_date)
            self.assertEqual(get_realm("zulip").plan_type, Realm.PLAN_TYPE_STANDARD)
            self.assertEqual(plan.status, CustomerPlan.FREE_TRIAL)
            self.assertEqual(plan.licenses(), self.seat_count)
            self.assertEqual(plan.licenses_at_next_renewal(), self.seat_count)

            # Schedule downgrade
            with (
                self.assertLogs("corporate.stripe", "INFO") as m,
                time_machine.travel(self.now, tick=False),
            ):
                response = self.client_billing_patch(
                    "/billing/plan",
                    {"status": CustomerPlan.DOWNGRADE_AT_END_OF_FREE_TRIAL},
                )
                expected_log = f"INFO:corporate.stripe:Change plan status: Customer.id: {customer.id}, CustomerPlan.id: {plan.id}, status: {CustomerPlan.DOWNGRADE_AT_END_OF_FREE_TRIAL}"
                self.assertEqual(m.output[0], expected_log)
                self.assert_json_success(response)
            plan.refresh_from_db()
            self.assertEqual(plan.next_invoice_date, free_trial_end_date)
            self.assertEqual(get_realm("zulip").plan_type, Realm.PLAN_TYPE_STANDARD)
            self.assertEqual(plan.status, CustomerPlan.DOWNGRADE_AT_END_OF_FREE_TRIAL)
            self.assertEqual(plan.licenses(), self.seat_count)
            self.assertEqual(plan.licenses_at_next_renewal(), None)

            with time_machine.travel(self.now, tick=False):
                mock_customer = Mock(email=user.delivery_email)
                mock_customer.invoice_settings.default_payment_method = Mock(
                    spec=stripe.PaymentMethod, type=Mock()
                )
                with patch("corporate.lib.stripe.stripe_get_customer", return_value=mock_customer):
                    response = self.client_get("/billing/")
                    self.assert_in_success_response(
                        [
                            "Your organization will be downgraded to <strong>Zulip Cloud Free</strong> at the end of the free trial",
                            "<strong>March 2, 2012</strong>",
                        ],
                        response,
                    )

            billing_session = RealmBillingSession(user=user, realm=user.realm)
            # Verify that we still write LicenseLedger rows during the remaining
            # part of the cycle
            with patch("corporate.lib.stripe.get_latest_seat_count", return_value=20):
                billing_session.update_license_ledger_if_needed(self.now)
            self.check_last_ledger_entry_license_counts(plan, 20, 20)

            # Verify that we don't invoice them for the additional users during free trial.
            mocked = self.setup_mocked_stripe(invoice_plans_as_needed, self.next_month)
            mocked["InvoiceItem"].create.assert_not_called()
            mocked["Invoice"].finalize_invoice.assert_not_called()
            mocked["Invoice"].create.assert_not_called()

            # Check that we downgrade properly if the cycle is over
            with patch("corporate.lib.stripe.get_latest_seat_count", return_value=30):
                billing_session.update_license_ledger_if_needed(free_trial_end_date)
            plan.refresh_from_db()
            self.assertIsNone(plan.next_invoice_date)
            self.assertEqual(plan.status, CustomerPlan.ENDED)
            self.assertEqual(get_realm("zulip").plan_type, Realm.PLAN_TYPE_LIMITED)
            self.check_last_ledger_entry_license_counts(plan, 20, 20)

            # Verify that we don't write LicenseLedger rows once we've downgraded
            with patch("corporate.lib.stripe.get_latest_seat_count", return_value=40):
                billing_session.update_license_ledger_if_needed(self.next_year)
            self.check_last_ledger_entry_license_counts(plan, 20, 20)

            self.login_user(user)
            response = self.client_get("/billing/")
            self.assertEqual(response.status_code, 302)
            self.assertEqual("/plans/", response["Location"])

            # The extra users added in the final month are not charged
            with patch("corporate.lib.stripe.BillingSession.invoice_plan") as mocked:
                invoice_plans_as_needed(self.next_month)
            mocked.assert_not_called()

            # The plan is not renewed after an year
            with patch("corporate.lib.stripe.BillingSession.invoice_plan") as mocked:
                invoice_plans_as_needed(self.next_year)
            mocked.assert_not_called()

    @mock_stripe()
    def test_cancel_downgrade_at_end_of_free_trial(self, *mocks: Mock) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)

        free_trial_end_date = self.now + timedelta(days=60)
        with self.settings(CLOUD_FREE_TRIAL_DAYS=60):
            with time_machine.travel(self.now, tick=False):
                self.add_card_and_upgrade(user, schedule="annual")
            customer = get_customer_by_realm(user.realm)
            assert customer is not None
            plan = get_current_plan_by_customer(customer)
            assert plan is not None
            self.assertEqual(plan.next_invoice_date, free_trial_end_date)
            self.assertEqual(get_realm("zulip").plan_type, Realm.PLAN_TYPE_STANDARD)
            self.assertEqual(plan.status, CustomerPlan.FREE_TRIAL)
            self.assertEqual(plan.licenses(), self.seat_count)
            self.assertEqual(plan.licenses_at_next_renewal(), self.seat_count)

            # Schedule downgrade
            with (
                self.assertLogs("corporate.stripe", "INFO") as m,
                time_machine.travel(self.now, tick=False),
            ):
                response = self.client_billing_patch(
                    "/billing/plan",
                    {"status": CustomerPlan.DOWNGRADE_AT_END_OF_FREE_TRIAL},
                )
                expected_log = f"INFO:corporate.stripe:Change plan status: Customer.id: {customer.id}, CustomerPlan.id: {plan.id}, status: {CustomerPlan.DOWNGRADE_AT_END_OF_FREE_TRIAL}"
                self.assertEqual(m.output[0], expected_log)
                self.assert_json_success(response)
            plan.refresh_from_db()
            self.assertEqual(plan.next_invoice_date, free_trial_end_date)
            self.assertEqual(get_realm("zulip").plan_type, Realm.PLAN_TYPE_STANDARD)
            self.assertEqual(plan.status, CustomerPlan.DOWNGRADE_AT_END_OF_FREE_TRIAL)
            self.assertEqual(plan.licenses(), self.seat_count)
            self.assertEqual(plan.licenses_at_next_renewal(), None)

            # Cancel downgrade
            with (
                self.assertLogs("corporate.stripe", "INFO") as m,
                time_machine.travel(self.now, tick=False),
            ):
                response = self.client_billing_patch(
                    "/billing/plan",
                    {"status": CustomerPlan.FREE_TRIAL},
                )
                expected_log = f"INFO:corporate.stripe:Change plan status: Customer.id: {customer.id}, CustomerPlan.id: {plan.id}, status: {CustomerPlan.FREE_TRIAL}"
                self.assertEqual(m.output[0], expected_log)
                self.assert_json_success(response)
            plan.refresh_from_db()
            self.assertEqual(plan.next_invoice_date, free_trial_end_date)
            self.assertEqual(get_realm("zulip").plan_type, Realm.PLAN_TYPE_STANDARD)
            self.assertEqual(plan.status, CustomerPlan.FREE_TRIAL)
            self.assertEqual(plan.licenses(), self.seat_count)
            self.assertEqual(plan.licenses_at_next_renewal(), self.seat_count)

    def test_reupgrade_by_billing_admin_after_downgrade(self) -> None:
        user = self.example_user("hamlet")

        with time_machine.travel(self.now, tick=False):
            self.local_upgrade(
                self.seat_count, True, CustomerPlan.BILLING_SCHEDULE_ANNUAL, True, False
            )

        self.login_user(user)
        with self.assertLogs("corporate.stripe", "INFO") as m:
            with time_machine.travel(self.now, tick=False):
                self.client_billing_patch(
                    "/billing/plan",
                    {"status": CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE},
                )
            customer = get_customer_by_realm(user.realm)
            assert customer is not None
            plan = get_current_plan_by_customer(customer)
            assert plan is not None
            expected_log = f"INFO:corporate.stripe:Change plan status: Customer.id: {customer.id}, CustomerPlan.id: {plan.id}, status: {CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE}"
            self.assertEqual(m.output[0], expected_log)

        with (
            self.assertRaises(BillingError) as context,
            self.assertLogs("corporate.stripe", "WARNING") as m,
            time_machine.travel(self.now, tick=False),
        ):
            self.local_upgrade(
                self.seat_count, True, CustomerPlan.BILLING_SCHEDULE_ANNUAL, True, False
            )
        self.assertEqual(
            m.output[0],
            "WARNING:corporate.stripe:Upgrade of <Realm: zulip 2> (stripe: cus_123) failed because of existing active plan.",
        )
        self.assertEqual(
            context.exception.error_description, "subscribing with existing subscription"
        )

        # Fast forward the next_invoice_date to next year.
        plan.next_invoice_date = self.next_year
        plan.save(update_fields=["next_invoice_date"])
        invoice_plans_as_needed(self.next_year)

        with time_machine.travel(self.next_year, tick=False):
            response = self.client_get("/billing/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual("/plans/", response["Location"])

        with time_machine.travel(self.next_year, tick=False):
            self.local_upgrade(
                self.seat_count, True, CustomerPlan.BILLING_SCHEDULE_ANNUAL, True, False
            )

        self.assertEqual(Customer.objects.count(), 1)
        self.assertEqual(CustomerPlan.objects.count(), 2)

        current_plan = CustomerPlan.objects.all().order_by("id").last()
        assert current_plan is not None
        next_invoice_date = add_months(self.next_year, 1)
        self.assertEqual(current_plan.next_invoice_date, next_invoice_date)
        self.assertEqual(get_realm("zulip").plan_type, Realm.PLAN_TYPE_STANDARD)
        self.assertEqual(current_plan.status, CustomerPlan.ACTIVE)

        old_plan = CustomerPlan.objects.all().order_by("id").first()
        assert old_plan is not None
        self.assertEqual(old_plan.next_invoice_date, None)
        self.assertEqual(old_plan.status, CustomerPlan.ENDED)

    @mock_stripe()
    def test_update_licenses_of_manual_plan_from_billing_page(self, *mocks: Mock) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)

        with time_machine.travel(self.now, tick=False):
            self.upgrade(invoice=True, licenses=100)

        with time_machine.travel(self.now, tick=False):
            result = self.client_billing_patch("/billing/plan", {"licenses": 100})
            self.assert_json_error_contains(
                result, "Your plan is already on 100 licenses in the current billing period."
            )

        with time_machine.travel(self.now, tick=False):
            result = self.client_billing_patch(
                "/billing/plan",
                {"licenses_at_next_renewal": 100},
            )
            self.assert_json_error_contains(
                result, "Your plan is already scheduled to renew with 100 licenses."
            )

        with time_machine.travel(self.now, tick=False):
            result = self.client_billing_patch("/billing/plan", {"licenses": 50})
            self.assert_json_error_contains(
                result, "You cannot decrease the licenses in the current billing period."
            )

        with time_machine.travel(self.now, tick=False):
            result = self.client_billing_patch(
                "/billing/plan",
                {"licenses_at_next_renewal": 25},
            )
            self.assert_json_error_contains(
                result,
                "You must purchase licenses for all active users in your organization (minimum 30).",
            )

        with time_machine.travel(self.now, tick=False):
            result = self.client_billing_patch("/billing/plan", {"licenses": 2000})
            self.assert_json_error_contains(
                result, "Invoices with more than 1000 licenses can't be processed from this page."
            )

        with time_machine.travel(self.now, tick=False):
            result = self.client_billing_patch("/billing/plan", {"licenses": 150})
            self.assert_json_success(result)
        invoice_plans_as_needed(self.next_year)
        stripe_customer = stripe_get_customer(
            assert_is_not_none(Customer.objects.get(realm=user.realm).stripe_customer_id)
        )

        [renewal_invoice, additional_licenses_invoice, _old_renewal_invoice] = iter(
            stripe.Invoice.list(customer=stripe_customer.id)
        )

        self.assertEqual(renewal_invoice.amount_due, 8000 * 150)
        self.assertEqual(renewal_invoice.amount_paid, 0)
        self.assertEqual(renewal_invoice.attempt_count, 0)
        self.assertTrue(renewal_invoice.auto_advance)
        self.assertEqual(renewal_invoice.collection_method, "send_invoice")
        self.assertEqual(renewal_invoice.statement_descriptor, "Zulip Cloud Standard")
        self.assertEqual(renewal_invoice.status, "open")

        [renewal_item] = iter(renewal_invoice.lines)

        self.assertEqual(renewal_item.amount, 8000 * 150)
        self.assertEqual(renewal_item.description, "Zulip Cloud Standard - renewal")
        self.assertFalse(renewal_item.discountable)
        self.assertEqual(renewal_item.period.start, datetime_to_timestamp(self.next_year))
        self.assertEqual(
            renewal_item.period.end, datetime_to_timestamp(self.next_year + timedelta(days=365))
        )
        self.assertEqual(renewal_item.quantity, 150)

        self.assertEqual(additional_licenses_invoice.amount_due, 8000 * 50)
        self.assertEqual(additional_licenses_invoice.amount_paid, 0)
        self.assertEqual(additional_licenses_invoice.attempt_count, 0)
        self.assertTrue(additional_licenses_invoice.auto_advance)
        self.assertEqual(additional_licenses_invoice.collection_method, "send_invoice")
        self.assertEqual(additional_licenses_invoice.statement_descriptor, "Zulip Cloud Standard")
        self.assertEqual(additional_licenses_invoice.status, "open")

        [extra_license_item] = iter(additional_licenses_invoice.lines)

        self.assertEqual(extra_license_item.amount, 8000 * 50)
        self.assertEqual(extra_license_item.description, "Additional Zulip Cloud Standard license")
        self.assertFalse(extra_license_item.discountable)
        self.assertEqual(extra_license_item.period.start, datetime_to_timestamp(self.now))
        self.assertEqual(extra_license_item.period.end, datetime_to_timestamp(self.next_year))
        self.assertEqual(extra_license_item.quantity, 50)

        with time_machine.travel(self.next_year, tick=False):
            result = self.client_billing_patch(
                "/billing/plan",
                {"licenses_at_next_renewal": 120},
            )
            self.assert_json_success(result)
        invoice_plans_as_needed(self.next_year + timedelta(days=365))
        [renewal_invoice, _, _, _] = iter(stripe.Invoice.list(customer=stripe_customer.id))

        self.assertEqual(renewal_invoice.amount_due, 8000 * 120)
        self.assertEqual(renewal_invoice.amount_paid, 0)
        self.assertEqual(renewal_invoice.attempt_count, 0)
        self.assertTrue(renewal_invoice.auto_advance)
        self.assertEqual(renewal_invoice.collection_method, "send_invoice")
        self.assertEqual(renewal_invoice.statement_descriptor, "Zulip Cloud Standard")
        self.assertEqual(renewal_invoice.status, "open")

        [renewal_item] = iter(renewal_invoice.lines)

        self.assertEqual(renewal_item.amount, 8000 * 120)
        self.assertEqual(renewal_item.description, "Zulip Cloud Standard - renewal")
        self.assertFalse(renewal_item.discountable)
        self.assertEqual(
            renewal_item.period.start, datetime_to_timestamp(self.next_year + timedelta(days=365))
        )
        self.assertEqual(
            renewal_item.period.end, datetime_to_timestamp(self.next_year + timedelta(days=2 * 365))
        )
        self.assertEqual(renewal_item.quantity, 120)

    def test_update_licenses_of_manual_plan_from_billing_page_exempt_from_license_number_check(
        self,
    ) -> None:
        """
        Verifies that an organization exempt from the license number check can reduce their number
        of licenses.
        """
        user = self.example_user("hamlet")
        self.login_user(user)

        customer = Customer.objects.get_or_create(realm=user.realm)[0]
        reduced_seat_count = get_latest_seat_count(user.realm) - 2
        customer.exempt_from_license_number_check = True
        customer.save()

        paid_license_count = 100
        with time_machine.travel(self.now, tick=False):
            self.local_upgrade(
                paid_license_count, False, CustomerPlan.BILLING_SCHEDULE_ANNUAL, True, False
            )

        with time_machine.travel(self.now, tick=False):
            result = self.client_billing_patch(
                "/billing/plan",
                {"licenses_at_next_renewal": reduced_seat_count},
            )

        self.assert_json_success(result)
        plan = get_current_plan_by_customer(customer)
        assert plan is not None
        self.check_last_ledger_entry_license_counts(plan, paid_license_count, reduced_seat_count)

    def test_upgrade_exempt_from_license_number_check_realm_less_licenses_than_seat_count(
        self,
    ) -> None:
        """
        Verifies that an organization exempt from the license number check can upgrade their plan,
        specifying a number of licenses less than their current number of licenses and be charged
        for the number of licenses specified. Tests against a former bug, where the organization
        was charged for the current seat count, despite specifying a lower number of licenses.
        """
        user = self.example_user("hamlet")
        self.login_user(user)

        customer = Customer.objects.get_or_create(realm=user.realm)[0]
        customer.exempt_from_license_number_check = True
        customer.save()

        reduced_seat_count = get_latest_seat_count(user.realm) - 2

        with time_machine.travel(self.now, tick=False):
            self.local_upgrade(
                reduced_seat_count, False, CustomerPlan.BILLING_SCHEDULE_ANNUAL, True, False
            )

        plan = get_current_plan_by_customer(customer)
        assert plan is not None
        self.check_last_ledger_entry_license_counts(plan, reduced_seat_count, reduced_seat_count)

    def test_update_licenses_of_automatic_plan_from_billing_page(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)

        with time_machine.travel(self.now, tick=False):
            self.local_upgrade(
                self.seat_count, True, CustomerPlan.BILLING_SCHEDULE_ANNUAL, True, False
            )

        with time_machine.travel(self.now, tick=False):
            result = self.client_billing_patch("/billing/plan", {"licenses": 100})
            self.assert_json_error_contains(result, "Your plan is on automatic license management.")

        with time_machine.travel(self.now, tick=False):
            result = self.client_billing_patch(
                "/billing/plan",
                {"licenses_at_next_renewal": 100},
            )
            self.assert_json_error_contains(result, "Your plan is on automatic license management.")

    def test_update_plan_with_invalid_status(self) -> None:
        with time_machine.travel(self.now, tick=False):
            self.local_upgrade(
                self.seat_count, True, CustomerPlan.BILLING_SCHEDULE_ANNUAL, True, False
            )
        self.login_user(self.example_user("hamlet"))

        response = self.client_billing_patch(
            "/billing/plan",
            {"status": CustomerPlan.NEVER_STARTED},
        )
        self.assert_json_error_contains(response, "Invalid status")

    def test_update_plan_without_any_params(self) -> None:
        with time_machine.travel(self.now, tick=False):
            self.local_upgrade(
                self.seat_count, True, CustomerPlan.BILLING_SCHEDULE_ANNUAL, True, False
            )

        self.login_user(self.example_user("hamlet"))
        with time_machine.travel(self.now, tick=False):
            response = self.client_billing_patch("/billing/plan", {})
        self.assert_json_error_contains(response, "Nothing to change")

    def test_update_plan_that_which_is_due_for_expiry(self) -> None:
        with time_machine.travel(self.now, tick=False):
            self.local_upgrade(
                self.seat_count, True, CustomerPlan.BILLING_SCHEDULE_ANNUAL, True, False
            )

        self.login_user(self.example_user("hamlet"))
        with (
            self.assertLogs("corporate.stripe", "INFO") as m,
            time_machine.travel(self.now, tick=False),
        ):
            result = self.client_billing_patch(
                "/billing/plan",
                {"status": CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE},
            )
            self.assert_json_success(result)
            self.assertRegex(
                m.output[0],
                r"INFO:corporate.stripe:Change plan status: Customer.id: \d*, CustomerPlan.id: \d*, status: 2",
            )

        with time_machine.travel(self.next_year, tick=False):
            result = self.client_billing_patch(
                "/billing/plan",
                {"status": CustomerPlan.ACTIVE},
            )
            self.assert_json_error_contains(
                result, "Unable to update the plan. The plan has ended."
            )

    def test_update_plan_that_which_is_due_for_replacement(self) -> None:
        with time_machine.travel(self.now, tick=False):
            self.local_upgrade(
                self.seat_count, True, CustomerPlan.BILLING_SCHEDULE_MONTHLY, True, False
            )

        self.login_user(self.example_user("hamlet"))
        with (
            self.assertLogs("corporate.stripe", "INFO") as m,
            time_machine.travel(self.now, tick=False),
        ):
            result = self.client_billing_patch(
                "/billing/plan",
                {"status": CustomerPlan.SWITCH_TO_ANNUAL_AT_END_OF_CYCLE},
            )
            self.assert_json_success(result)
            self.assertRegex(
                m.output[0],
                r"INFO:corporate.stripe:Change plan status: Customer.id: \d*, CustomerPlan.id: \d*, status: 4",
            )

        with time_machine.travel(self.next_month, tick=False):
            result = self.client_billing_patch("/billing/plan", {})
            self.assert_json_error_contains(
                result,
                "Unable to update the plan. The plan has been expired and replaced with a new plan.",
            )

    @patch("corporate.lib.stripe.billing_logger.info")
    def test_deactivate_realm(self, mock_: Mock) -> None:
        user = self.example_user("hamlet")
        with time_machine.travel(self.now, tick=False):
            self.local_upgrade(
                self.seat_count, True, CustomerPlan.BILLING_SCHEDULE_ANNUAL, True, False
            )

        plan = CustomerPlan.objects.get()
        self.assertEqual(plan.next_invoice_date, self.next_month)
        self.assertEqual(get_realm("zulip").plan_type, Realm.PLAN_TYPE_STANDARD)
        self.assertEqual(plan.status, CustomerPlan.ACTIVE)

        # Add some extra users before the realm is deactivated
        billing_session = RealmBillingSession(user=user, realm=user.realm)
        with patch("corporate.lib.stripe.get_latest_seat_count", return_value=20):
            billing_session.update_license_ledger_if_needed(self.now)

        last_ledger_entry = self.check_last_ledger_entry_license_counts(plan, 20, 20)

        do_deactivate_realm(
            get_realm("zulip"),
            acting_user=None,
            deactivation_reason="owner_request",
            email_owners=False,
        )

        plan.refresh_from_db()
        self.assertTrue(get_realm("zulip").deactivated)
        self.assertEqual(get_realm("zulip").plan_type, Realm.PLAN_TYPE_LIMITED)
        self.assertEqual(plan.status, CustomerPlan.ENDED)
        self.assertEqual(plan.invoiced_through, last_ledger_entry)
        self.assertIsNone(plan.next_invoice_date)

        do_reactivate_realm(get_realm("zulip"))

        self.login_user(user)
        response = self.client_get("/billing/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual("/plans/", response["Location"])

        # The extra users added in the final month are not charged
        with patch("corporate.lib.stripe.BillingSession.invoice_plan") as mocked:
            invoice_plans_as_needed(self.next_month)
        mocked.assert_not_called()

        # The plan is not renewed after an year
        with patch("corporate.lib.stripe.BillingSession.invoice_plan") as mocked:
            invoice_plans_as_needed(self.next_year)
        mocked.assert_not_called()

    def test_reupgrade_by_billing_admin_after_realm_deactivation(self) -> None:
        user = self.example_user("hamlet")

        with time_machine.travel(self.now, tick=False):
            self.local_upgrade(
                self.seat_count, True, CustomerPlan.BILLING_SCHEDULE_ANNUAL, True, False
            )

        do_deactivate_realm(
            get_realm("zulip"),
            acting_user=None,
            deactivation_reason="owner_request",
            email_owners=False,
        )
        self.assertTrue(get_realm("zulip").deactivated)
        do_reactivate_realm(get_realm("zulip"))

        self.login_user(user)
        response = self.client_get("/billing/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual("/plans/", response["Location"])

        with time_machine.travel(self.now, tick=False):
            self.local_upgrade(
                self.seat_count, True, CustomerPlan.BILLING_SCHEDULE_ANNUAL, True, False
            )

        self.assertEqual(Customer.objects.count(), 1)

        self.assertEqual(CustomerPlan.objects.count(), 2)

        current_plan = CustomerPlan.objects.all().order_by("id").last()
        assert current_plan is not None
        self.assertEqual(current_plan.next_invoice_date, self.next_month)
        self.assertEqual(get_realm("zulip").plan_type, Realm.PLAN_TYPE_STANDARD)
        self.assertEqual(current_plan.status, CustomerPlan.ACTIVE)

        old_plan = CustomerPlan.objects.all().order_by("id").first()
        assert old_plan is not None
        self.assertEqual(old_plan.next_invoice_date, None)
        self.assertEqual(old_plan.status, CustomerPlan.ENDED)

    @mock_stripe()
    def test_void_all_open_invoices(self, *mock: Mock) -> None:
        iago = self.example_user("iago")
        king = self.lear_user("king")

        voided_invoice_count = RealmBillingSession(
            user=None, realm=iago.realm
        ).void_all_open_invoices()
        self.assertEqual(voided_invoice_count, 0)

        zulip_customer = RealmBillingSession(iago).update_or_create_stripe_customer()
        lear_customer = RealmBillingSession(king).update_or_create_stripe_customer()

        assert zulip_customer.stripe_customer_id
        stripe_invoice = stripe.Invoice.create(
            auto_advance=True,
            collection_method="send_invoice",
            customer=zulip_customer.stripe_customer_id,
            days_until_due=30,
            statement_descriptor="Zulip Cloud Standard",
        )
        assert stripe_invoice.id is not None
        stripe.InvoiceItem.create(
            invoice=stripe_invoice.id,
            currency="usd",
            customer=zulip_customer.stripe_customer_id,
            description="Zulip Cloud Standard upgrade",
            discountable=False,
            unit_amount_decimal=Decimal(800),
            quantity=8,
        )
        stripe.Invoice.finalize_invoice(stripe_invoice)

        assert lear_customer.stripe_customer_id
        stripe_invoice = stripe.Invoice.create(
            auto_advance=True,
            collection_method="send_invoice",
            customer=lear_customer.stripe_customer_id,
            days_until_due=30,
            statement_descriptor="Zulip Cloud Standard",
        )
        assert stripe_invoice.id is not None
        stripe.InvoiceItem.create(
            invoice=stripe_invoice.id,
            currency="usd",
            customer=lear_customer.stripe_customer_id,
            description="Zulip Cloud Standard upgrade",
            discountable=False,
            unit_amount_decimal=Decimal(800),
            quantity=8,
        )
        stripe.Invoice.finalize_invoice(stripe_invoice)

        voided_invoice_count = RealmBillingSession(
            user=None, realm=iago.realm
        ).void_all_open_invoices()
        self.assertEqual(voided_invoice_count, 1)
        invoices = stripe.Invoice.list(customer=zulip_customer.stripe_customer_id)
        self.assert_length(invoices, 1)
        for invoice in invoices:
            self.assertEqual(invoice.status, "void")

        lear_stripe_customer_id = lear_customer.stripe_customer_id
        lear_customer.stripe_customer_id = None
        lear_customer.save(update_fields=["stripe_customer_id"])
        voided_invoice_count = RealmBillingSession(
            user=None, realm=king.realm
        ).void_all_open_invoices()
        self.assertEqual(voided_invoice_count, 0)

        lear_customer.stripe_customer_id = lear_stripe_customer_id
        lear_customer.save(update_fields=["stripe_customer_id"])
        voided_invoice_count = RealmBillingSession(
            user=None, realm=king.realm
        ).void_all_open_invoices()
        self.assertEqual(voided_invoice_count, 1)
        invoices = stripe.Invoice.list(customer=lear_customer.stripe_customer_id)
        self.assert_length(invoices, 1)
        for invoice in invoices:
            self.assertEqual(invoice.status, "void")

    def create_invoices(self, customer: Customer, num_invoices: int) -> list[stripe.Invoice]:
        invoices = []
        assert customer.stripe_customer_id is not None
        for _ in range(num_invoices):
            invoice = stripe.Invoice.create(
                auto_advance=True,
                collection_method="send_invoice",
                customer=customer.stripe_customer_id,
                days_until_due=DEFAULT_INVOICE_DAYS_UNTIL_DUE,
                statement_descriptor="Zulip Cloud Standard",
            )
            assert invoice.id is not None
            stripe.InvoiceItem.create(
                invoice=invoice.id,
                amount=10000,
                currency="usd",
                customer=customer.stripe_customer_id,
                description="Zulip Cloud Standard",
                discountable=False,
            )

            stripe.Invoice.finalize_invoice(invoice)
            invoices.append(invoice)
        return invoices

    @mock_stripe()
    def test_downgrade_small_realms_behind_on_payments_as_needed(self, *mock: Mock) -> None:
        test_realm_count = 0

        def create_realm(
            users_to_create: int,
            create_stripe_customer: bool,
            create_plan: bool,
            num_invoices: int | None = None,
        ) -> tuple[Realm, CustomerPlan | None, list[stripe.Invoice]]:
            nonlocal test_realm_count
            test_realm_count += 1
            realm_string_id = "test-realm-" + str(test_realm_count)
            realm = do_create_realm(
                string_id=realm_string_id,
                name=realm_string_id,
                plan_type=Realm.PLAN_TYPE_SELF_HOSTED,
            )
            users = []
            for i in range(users_to_create):
                user = UserProfile.objects.create(
                    delivery_email=f"user-{i}-{realm_string_id}@zulip.com",
                    email=f"user-{i}-{realm_string_id}@zulip.com",
                    realm=realm,
                )
                users.append(user)

            user = users[0]
            user.role = UserProfile.ROLE_REALM_OWNER
            user.save(update_fields=["role"])

            customer = None
            if create_stripe_customer:
                billing_session = RealmBillingSession(users[0])
                customer = billing_session.create_stripe_customer()
            plan = None
            if create_plan:
                plan, _ = self.subscribe_realm_to_monthly_plan_on_manual_license_management(
                    realm, users_to_create, users_to_create
                )
            invoices = []
            if num_invoices is not None:
                assert customer is not None
                invoices = self.create_invoices(customer, num_invoices)
            return realm, plan, invoices

        @dataclass
        class Row:
            realm: Realm
            expected_plan_type: int
            plan: CustomerPlan | None
            expected_plan_status: int | None
            expected_invoice_count: int
            email_expected_to_be_sent: bool

        rows: list[Row] = []

        # no stripe customer ID (excluded from query)
        realm, _, _ = create_realm(
            users_to_create=1, create_stripe_customer=False, create_plan=False
        )
        billing_session = RealmBillingSession(
            user=self.example_user("iago"), realm=realm, support_session=True
        )
        billing_session.set_required_plan_tier(CustomerPlan.TIER_CLOUD_STANDARD)
        billing_session.attach_discount_to_customer(640, 6400)
        rows.append(Row(realm, Realm.PLAN_TYPE_SELF_HOSTED, None, None, 0, False))

        # no active paid plan or invoices (no action)
        realm, _, _ = create_realm(
            users_to_create=1, create_stripe_customer=True, create_plan=False
        )
        rows.append(Row(realm, Realm.PLAN_TYPE_SELF_HOSTED, None, None, 0, False))

        # no active plan, one unpaid invoice (will be voided, no downgrade or email)
        realm, _, _ = create_realm(
            users_to_create=1, create_stripe_customer=True, create_plan=False, num_invoices=1
        )
        rows.append(Row(realm, Realm.PLAN_TYPE_SELF_HOSTED, None, None, 0, False))

        # active plan, no invoices (no action)
        realm, plan, _ = create_realm(
            users_to_create=1, create_stripe_customer=True, create_plan=True
        )
        rows.append(Row(realm, Realm.PLAN_TYPE_STANDARD, plan, CustomerPlan.ACTIVE, 0, False))

        # active plan, only one unpaid invoice (not downgraded or voided)
        realm, plan, _ = create_realm(
            users_to_create=1, create_stripe_customer=True, create_plan=True, num_invoices=1
        )
        rows.append(Row(realm, Realm.PLAN_TYPE_STANDARD, plan, CustomerPlan.ACTIVE, 1, False))

        # active plan, two unpaid invoices (will be downgraded, voided and emailed)
        realm, plan, _ = create_realm(
            users_to_create=3, create_stripe_customer=True, create_plan=True, num_invoices=2
        )
        rows.append(Row(realm, Realm.PLAN_TYPE_LIMITED, plan, CustomerPlan.ENDED, 0, True))

        # active plan, two paid invoices (not downgraded)
        realm, plan, invoices = create_realm(
            users_to_create=1, create_stripe_customer=True, create_plan=True, num_invoices=2
        )
        for invoice in invoices:
            stripe.Invoice.pay(invoice, paid_out_of_band=True)
        rows.append(Row(realm, Realm.PLAN_TYPE_STANDARD, plan, CustomerPlan.ACTIVE, 0, False))

        # not a small realm, two unpaid invoices (not downgraded or voided)
        realm, plan, _ = create_realm(
            users_to_create=20, create_stripe_customer=True, create_plan=True, num_invoices=2
        )
        rows.append(Row(realm, Realm.PLAN_TYPE_STANDARD, plan, CustomerPlan.ACTIVE, 2, False))

        # Customer objects without a realm should be excluded from query.
        remote_server = RemoteZulipServer.objects.create(
            uuid=str(uuid.uuid4()),
            api_key="magic_secret_api_key",
            hostname="demo.example.com",
            contact_email="email@example.com",
        )
        Customer.objects.create(remote_server=remote_server, stripe_customer_id="cus_xxx")

        downgrade_small_realms_behind_on_payments_as_needed()

        from django.core.mail import outbox

        for row in rows:
            row.realm.refresh_from_db()
            self.assertEqual(row.realm.plan_type, row.expected_plan_type)
            if row.plan is not None:
                row.plan.refresh_from_db()
                self.assertEqual(row.plan.status, row.expected_plan_status)
                customer = get_customer_by_realm(row.realm)
                if customer is not None and customer.stripe_customer_id is not None:
                    open_invoices = customer_has_last_n_invoices_open(
                        customer, row.expected_invoice_count
                    )
                    self.assertTrue(open_invoices)

            email_found = False
            for email in outbox:
                recipient = UserProfile.objects.get(email=email.to[0])
                if recipient.realm == row.realm:
                    self.assertIn(
                        f"Your organization, http://{row.realm.string_id}.testserver, has been downgraded",
                        outbox[0].body,
                    )
                    self.assert_length(email.to, 1)
                    email_found = True
            self.assertEqual(row.email_expected_to_be_sent, email_found)

    @mock_stripe()
    def test_upgrade_pay_by_invoice(self, *mock: Mock) -> None:
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)
        response = self.client_get("/upgrade/?setup_payment_by_invoice=true")
        self.assert_in_success_response(["pay by card", "Send invoice"], response)

        # Send invoice
        response = self.client_billing_post(
            "/billing/upgrade",
            {
                "billing_modality": "send_invoice",
                "schedule": "annual",
                "signed_seat_count": self.get_signed_seat_count_from_response(response),
                "salt": self.get_salt_from_response(response),
                "license_management": "manual",
                "licenses": 40,
            },
        )
        self.assert_json_success(response)

        response = self.client_get("/upgrade/?setup_payment_by_invoice=true")
        self.assert_in_success_response(["An invoice", "has been sent"], response)

    @mock_stripe()
    def test_change_plan_tier_from_standard_to_plus(self, *mock: Mock) -> None:
        iago = self.example_user("iago")
        realm = iago.realm
        iago_billing_session = RealmBillingSession(iago)
        iago_billing_session.update_or_create_customer()

        # Test upgrading to Plus when realm has no active subscription
        with self.assertRaises(BillingError) as billing_context:
            iago_billing_session.do_change_plan_to_new_tier(CustomerPlan.TIER_CLOUD_PLUS)
        self.assertEqual(
            "Organization does not have an active plan",
            billing_context.exception.error_description,
        )

        plan, ledger = self.subscribe_realm_to_manual_license_management_plan(
            realm, 9, 9, CustomerPlan.BILLING_SCHEDULE_MONTHLY
        )
        # Test upgrading to Plus when realm has no stripe_customer_id
        with self.assertRaises(BillingError) as billing_context:
            iago_billing_session.do_change_plan_to_new_tier(CustomerPlan.TIER_CLOUD_PLUS)
        self.assertEqual(
            "Organization missing Stripe customer.", billing_context.exception.error_description
        )

        king = self.lear_user("king")
        realm = king.realm
        king_billing_session = RealmBillingSession(king)
        customer = king_billing_session.update_or_create_stripe_customer()
        plan = CustomerPlan.objects.create(
            customer=customer,
            automanage_licenses=True,
            billing_cycle_anchor=timezone_now(),
            billing_schedule=CustomerPlan.BILLING_SCHEDULE_MONTHLY,
            tier=CustomerPlan.TIER_CLOUD_STANDARD,
        )
        ledger = LicenseLedger.objects.create(
            plan=plan,
            is_renewal=True,
            event_time=timezone_now(),
            licenses=9,
            licenses_at_next_renewal=9,
        )
        realm.plan_type = Realm.PLAN_TYPE_STANDARD
        realm.save(update_fields=["plan_type"])
        plan.invoiced_through = ledger
        plan.price_per_license = get_price_per_license(
            CustomerPlan.TIER_CLOUD_STANDARD, CustomerPlan.BILLING_SCHEDULE_MONTHLY
        )
        plan.save(update_fields=["invoiced_through", "price_per_license"])

        with self.assertRaises(BillingError) as billing_context:
            king_billing_session.do_change_plan_to_new_tier(CustomerPlan.TIER_CLOUD_STANDARD)
        self.assertEqual(
            "Invalid change of customer plan tier.", billing_context.exception.error_description
        )

        king_billing_session.do_change_plan_to_new_tier(CustomerPlan.TIER_CLOUD_PLUS)

        plan.refresh_from_db()
        self.assertEqual(plan.status, CustomerPlan.ENDED)
        plus_plan = get_current_plan_by_realm(realm)
        assert plus_plan is not None
        self.assertEqual(plus_plan.tier, CustomerPlan.TIER_CLOUD_PLUS)
        self.assertEqual(LicenseLedger.objects.filter(plan=plus_plan).count(), 1)

        realm.refresh_from_db()
        self.assertEqual(realm.plan_type, Realm.PLAN_TYPE_PLUS)

        # There are 9 licenses and the realm is on the Standard monthly plan.
        # Therefore, the customer has already paid 800 * 9 = 7200 = $72 for
        # the month. Once they upgrade to Plus, they will have to pay for 10
        # licenses as that is the minimum licenses for that plan.
        # The new price for their 10 licenses will be 1200 * 10 = 12000 = $120.
        # Since the customer has already paid $72 for a month, -7200 = -$72 will
        # be credited to the customer's balance.
        stripe_customer_id = customer.stripe_customer_id
        assert stripe_customer_id is not None
        _, cb_txn = iter(stripe.Customer.list_balance_transactions(stripe_customer_id))
        self.assertEqual(cb_txn.amount, -7200)
        self.assertEqual(
            cb_txn.description,
            "Credit from early termination of active plan",
        )
        self.assertEqual(cb_txn.type, "adjustment")

        # The customer now only pays the difference 12000 - 7200 = 4800 = $48,
        # since the unused proration is for the whole month.
        (invoice,) = iter(stripe.Invoice.list(customer=stripe_customer_id))
        self.assertEqual(invoice.amount_due, 4800)

    @mock_stripe()
    def test_customer_has_credit_card_as_default_payment_method(self, *mocks: Mock) -> None:
        iago = self.example_user("iago")
        customer = Customer.objects.create(realm=iago.realm)
        self.assertFalse(customer_has_credit_card_as_default_payment_method(customer))

        billing_session = RealmBillingSession(iago)
        customer = billing_session.update_or_create_stripe_customer()
        self.assertFalse(customer_has_credit_card_as_default_payment_method(customer))

        self.login_user(iago)
        self.add_card_and_upgrade(iago)
        self.assertTrue(customer_has_credit_card_as_default_payment_method(customer))


class StripeWebhookEndpointTest(ZulipTestCase):
    def test_stripe_webhook_with_invalid_data(self) -> None:
        result = self.client_post(
            "/stripe/webhook/",
            '["dsdsds"]',
            content_type="application/json",
        )
        self.assertEqual(result.status_code, 400)

    def test_stripe_webhook_endpoint_invalid_api_version(self) -> None:
        event_data = {
            "id": "stripe_event_id",
            "api_version": "1991-02-20",
            "type": "event_type",
            "data": {"object": {"object": "checkout.session", "id": "stripe_session_id"}},
        }

        expected_error_message = rf"Mismatch between billing system Stripe API version({STRIPE_API_VERSION}) and Stripe webhook event API version(1991-02-20)."
        with self.assertLogs("corporate.stripe", "ERROR") as error_log:
            self.client_post(
                "/stripe/webhook/",
                event_data,
                content_type="application/json",
            )
            self.assertEqual(error_log.output, [f"ERROR:corporate.stripe:{expected_error_message}"])

    def test_stripe_webhook_drops_unhandled_event_type(self) -> None:
        # The polling loop when generating test fixtures filters down to
        # HANDLED_STRIPE_EVENT_TYPES, so saved test fixtures never carry
        # unhandled types, but Stripe will still POST other types in
        # production. The webhook view must send a 200 response for
        # those events without touching the database.
        unhandled_event_data = {
            "id": "stripe_event_id",
            "api_version": STRIPE_API_VERSION,
            "type": "invoice.updated",
            "data": {"object": {"object": "invoice", "id": "stripe_invoice_id"}},
        }
        result = self.client_post(
            "/stripe/webhook/",
            unhandled_event_data,
            content_type="application/json",
        )
        self.assertEqual(result.status_code, 200)
        self.assert_length(Event.objects.all(), 0)

    def test_stripe_webhook_for_session_completed_event(self) -> None:
        # We don't process sessions for which we don't have a `Session` entry.
        valid_session_event_data = {
            "id": "stripe_event_id",
            "api_version": STRIPE_API_VERSION,
            "type": "checkout.session.completed",
            "data": {"object": {"object": "checkout.session", "id": "stripe_session_id"}},
        }
        with patch(
            "corporate.lib.stripe_event_handler.handle_checkout_session_completed_event"
        ) as m:
            result = self.client_post(
                "/stripe/webhook/",
                valid_session_event_data,
                content_type="application/json",
            )
        self.assert_length(Event.objects.all(), 0)
        self.assertEqual(result.status_code, 200)
        m.assert_not_called()

    def test_stripe_webhook_for_invoice_payment_events(self) -> None:
        customer = Customer.objects.create(realm=get_realm("zulip"))

        stripe_event_id = "stripe_event_id"
        stripe_invoice_id = "stripe_invoice_id"
        valid_session_event_data = {
            "id": stripe_event_id,
            "type": "invoice.paid",
            "api_version": STRIPE_API_VERSION,
            "data": {"object": {"object": "invoice", "id": stripe_invoice_id}},
        }

        with patch("corporate.lib.stripe_event_handler.handle_invoice_paid_event") as m:
            result = self.client_post(
                "/stripe/webhook/",
                valid_session_event_data,
                content_type="application/json",
            )
        self.assert_length(Event.objects.filter(stripe_event_id=stripe_event_id), 0)
        self.assertEqual(result.status_code, 200)
        m.assert_not_called()

        Invoice.objects.create(
            stripe_invoice_id=stripe_invoice_id,
            customer=customer,
            status=Invoice.SENT,
        )

        self.assert_length(Event.objects.filter(stripe_event_id=stripe_event_id), 0)
        with patch("corporate.lib.stripe_event_handler.handle_invoice_paid_event") as m:
            result = self.client_post(
                "/stripe/webhook/",
                valid_session_event_data,
                content_type="application/json",
            )
        [event] = Event.objects.filter(stripe_event_id=stripe_event_id)
        self.assertEqual(result.status_code, 200)
        strip_event = stripe.Event.construct_from(valid_session_event_data, stripe.api_key)
        m.assert_called_once_with(strip_event.data.object, event)

        with patch("corporate.lib.stripe_event_handler.handle_invoice_paid_event") as m:
            result = self.client_post(
                "/stripe/webhook/",
                valid_session_event_data,
                content_type="application/json",
            )
        self.assert_length(Event.objects.filter(stripe_event_id=stripe_event_id), 1)
        self.assertEqual(result.status_code, 200)
        m.assert_not_called()

    def test_stripe_webhook_for_invoice_paid_events(self) -> None:
        customer = Customer.objects.create(realm=get_realm("zulip"))

        stripe_event_id = "stripe_event_id"
        stripe_invoice_id = "stripe_invoice_id"
        valid_invoice_paid_event_data = {
            "id": stripe_event_id,
            "type": "invoice.paid",
            "api_version": STRIPE_API_VERSION,
            "data": {"object": {"object": "invoice", "id": stripe_invoice_id}},
        }

        with patch("corporate.lib.stripe_event_handler.handle_invoice_paid_event") as m:
            result = self.client_post(
                "/stripe/webhook/",
                valid_invoice_paid_event_data,
                content_type="application/json",
            )
        self.assert_length(Event.objects.filter(stripe_event_id=stripe_event_id), 0)
        self.assertEqual(result.status_code, 200)
        m.assert_not_called()

        Invoice.objects.create(
            stripe_invoice_id=stripe_invoice_id,
            customer=customer,
            status=Invoice.SENT,
        )

        self.assert_length(Event.objects.filter(stripe_event_id=stripe_event_id), 0)
        with patch("corporate.lib.stripe_event_handler.handle_invoice_paid_event") as m:
            result = self.client_post(
                "/stripe/webhook/",
                valid_invoice_paid_event_data,
                content_type="application/json",
            )
        [event] = Event.objects.filter(stripe_event_id=stripe_event_id)
        self.assertEqual(result.status_code, 200)
        strip_event = stripe.Event.construct_from(valid_invoice_paid_event_data, stripe.api_key)
        m.assert_called_once_with(strip_event.data.object, event)

        with patch("corporate.lib.stripe_event_handler.handle_invoice_paid_event") as m:
            result = self.client_post(
                "/stripe/webhook/",
                valid_invoice_paid_event_data,
                content_type="application/json",
            )
        self.assert_length(Event.objects.filter(stripe_event_id=stripe_event_id), 1)
        self.assertEqual(result.status_code, 200)
        m.assert_not_called()

    def test_stripe_event_handler_billing_error_logging(self) -> None:
        customer = Customer.objects.create(realm=get_realm("zulip"))
        stripe_invoice_id = "stripe_invoice_id"
        invoice = Invoice.objects.create(
            stripe_invoice_id=stripe_invoice_id,
            customer=customer,
            status=Invoice.SENT,
        )
        content_type = ContentType.objects.get_for_model(Invoice)
        event = Event.objects.create(
            stripe_event_id="stripe_event_id",
            type="invoice.paid",
            content_type=content_type,
            object_id=invoice.id,
        )

        stripe_invoice = stripe.Invoice.construct_from(
            {
                "id": stripe_invoice_id,
                "object": "invoice",
                "customer": "cus_test123",
                "metadata": {"plan_tier": "1", "billing_schedule": "1"},
            },
            stripe.api_key,
        )

        from corporate.lib.stripe_event_handler import stripe_event_handler_decorator

        @stripe_event_handler_decorator
        def raise_billing_error(stripe_object: stripe.Invoice, invoice: Invoice) -> None:
            raise BillingError("test error", "test error description")

        with self.assertLogs("corporate.stripe", "WARNING") as warning_log:
            raise_billing_error(stripe_invoice, event)

        self.assert_length(warning_log.output, 1)
        self.assertIn(
            "BillingError in invoice.paid event handler: test error."
            f" stripe_object_id={stripe_invoice_id},"
            " customer_id=cus_test123 metadata=",
            warning_log.output[0],
        )

        event.refresh_from_db()
        self.assertEqual(event.status, Event.EVENT_HANDLER_FAILED)
        self.assertEqual(
            event.handler_error,
            {"message": "test error description", "description": "test error"},
        )


class EventStatusTest(StripeTestCase):
    def test_event_status_json_endpoint_errors(self) -> None:
        self.login_user(self.example_user("iago"))

        response = self.client_get("/json/billing/event/status")
        self.assert_json_error_contains(response, "No customer for this organization!")

        Customer.objects.create(realm=get_realm("zulip"), stripe_customer_id="cus_123")
        response = self.client_get(
            "/json/billing/event/status", {"stripe_session_id": "invalid_session_id"}
        )
        self.assert_json_error_contains(response, "Session not found")

        response = self.client_get(
            "/json/billing/event/status", {"stripe_invoice_id": "invalid_invoice_id"}
        )
        self.assert_json_error_contains(response, "Payment intent not found")

        response = self.client_get(
            "/json/billing/event/status",
        )
        self.assert_json_error_contains(response, "Pass stripe_session_id or stripe_invoice_id")

    def test_event_status_page(self) -> None:
        self.login_user(self.example_user("polonius"))

        stripe_session_id = "cs_test_9QCz62mPTJQUwvhcwZHBpJMHmMZiLU512AQHU9g5znkx6NweU3j7kJvY"
        response = self.client_get(
            "/billing/event_status/", {"stripe_session_id": stripe_session_id}
        )
        self.assert_in_success_response([f'data-stripe-session-id="{stripe_session_id}"'], response)

        stripe_invoice_id = "pi_1JGLpnA4KHR4JzRvUfkF9Tn7"
        response = self.client_get(
            "/billing/event_status/", {"stripe_invoice_id": stripe_invoice_id}
        )
        self.assert_in_success_response([f'data-stripe-invoice-id="{stripe_invoice_id}"'], response)


class RequiresBillingAccessTest(StripeTestCase):
    @override
    def setUp(self, *mocks: Mock) -> None:
        super().setUp()
        desdemona = self.example_user("desdemona")
        desdemona.role = UserProfile.ROLE_REALM_OWNER
        desdemona.save(update_fields=["role"])

    def test_json_endpoints_permissions(self) -> None:
        guest = self.example_user("polonius")
        member = self.example_user("othello")

        tested_endpoints = set()

        def check_users_cant_access(
            users: list[UserProfile],
            error_message: str,
            url: str,
            method: str,
            data: dict[str, Any],
        ) -> None:
            tested_endpoints.add(url)
            for user in users:
                self.login_user(user)
                if method == "POST":
                    client_func: Any = self.client_post
                elif method == "GET":
                    client_func = self.client_get
                else:
                    client_func = self.client_patch
                result = client_func(
                    url,
                    data,
                    content_type="application/json",
                )
                self.assert_json_error_contains(result, error_message)

        check_users_cant_access(
            [guest, member],
            "Insufficient permission",
            "/json/billing/upgrade",
            "POST",
            {},
        )

        check_users_cant_access(
            [guest, member],
            "Insufficient permission",
            "/json/billing/sponsorship",
            "POST",
            {},
        )

        check_users_cant_access(
            [guest, member],
            "Insufficient permission",
            "/json/billing/plan",
            "PATCH",
            {},
        )

        check_users_cant_access(
            [guest, member],
            "Insufficient permission",
            "/json/billing/session/start_card_update_session",
            "POST",
            {},
        )

        check_users_cant_access(
            [guest, member],
            "Insufficient permission",
            "/json/upgrade/session/start_card_update_session",
            "POST",
            {},
        )

        check_users_cant_access(
            [guest, member],
            "Insufficient permission",
            "/json/billing/event/status",
            "GET",
            {},
        )

        # Make sure that we are testing all the JSON endpoints
        # Quite a hack, but probably fine for now
        reverse_dict = get_resolver("corporate.urls").reverse_dict
        json_endpoints = {
            pat
            for name in reverse_dict
            for matches, pat, defaults, converters in reverse_dict.getlist(name)
            if pat.startswith("json/") and not (pat.startswith(("json/realm/", "json/server/")))
        }
        self.assert_length(json_endpoints, len(tested_endpoints))

    @mock_stripe()
    def test_billing_page_permissions(self, *mocks: Mock) -> None:
        # Guest users can't access /upgrade/ page
        self.login_user(self.example_user("polonius"))
        response = self.client_get("/upgrade/", follow=True)
        self.assertEqual(response.status_code, 404)

        # Check user in `can_manage_billing_group` has access
        desdemona = self.example_user("desdemona")
        desdemona.role = UserProfile.ROLE_REALM_OWNER
        desdemona.save(update_fields=["role"])
        self.login_user(self.example_user("desdemona"))
        self.add_card_and_upgrade(desdemona)
        response = self.client_get("/billing/")
        self.assert_in_success_response(["Zulip Cloud Standard"], response)

        # Check that member who is not in `can_manage_billing_group` does not have access
        self.login_user(self.example_user("cordelia"))
        response = self.client_get("/billing/")
        self.assert_in_success_response(["You do not have permission to view this page."], response)

    def test_start_card_update_stripe_session_requires_billing_access(self) -> None:
        # Verify that only users with billing access can update card.
        guest = self.example_user("polonius")
        member = self.example_user("othello")
        realm_owner = self.example_user("desdemona")
        realm_owner.role = UserProfile.ROLE_REALM_OWNER
        realm_owner.save(update_fields=["role"])

        # Guest users should not have access
        self.login_user(guest)
        response = self.client_post(
            "/json/billing/session/start_card_update_session",
            {},
            content_type="application/json",
        )
        self.assert_json_error_contains(response, "Insufficient permission")

        # Regular members should not have access
        self.login_user(member)
        response = self.client_post(
            "/json/billing/session/start_card_update_session",
            {},
            content_type="application/json",
        )
        self.assert_json_error_contains(response, "Insufficient permission")

        # Realm owner should have access (they have billing access)
        self.login_user(realm_owner)
        with patch(
            "corporate.lib.stripe.RealmBillingSession.create_card_update_session",
            return_value={"stripe_session_id": "cs_test_session_id"},
        ):
            response = self.client_post(
                "/json/billing/session/start_card_update_session",
                {},
                content_type="application/json",
            )
            self.assert_json_success(response)
