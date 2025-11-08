from django.db import models
from django.db.models import CASCADE
from typing_extensions import override

from corporate.models.customers import Customer, get_customer_by_realm
from zerver.models import Realm


class AbstractCustomerPlan(models.Model):
    # A customer can only have one ACTIVE / CONFIGURED plan,
    # but old, inactive / processed plans are preserved to allow
    # auditing - so there can be multiple CustomerPlan / CustomerPlanOffer
    # objects pointing to one Customer.
    customer = models.ForeignKey(Customer, on_delete=CASCADE)

    fixed_price = models.IntegerField(null=True)

    class Meta:
        abstract = True


class CustomerPlanOffer(AbstractCustomerPlan):
    """
    This is for storing offers configured via /support which
    the customer is yet to buy or schedule a purchase.

    Once customer buys or schedules a purchase, we create a
    CustomerPlan record. The record in this table stays for
    audit purpose with status=PROCESSED.
    """

    TIER_CLOUD_STANDARD = 1
    TIER_CLOUD_PLUS = 2
    TIER_SELF_HOSTED_BASIC = 103
    TIER_SELF_HOSTED_BUSINESS = 104
    tier = models.SmallIntegerField()

    # Whether the offer is:
    # * only configured
    # * processed by the customer to buy or schedule a purchase.
    CONFIGURED = 1
    PROCESSED = 2
    status = models.SmallIntegerField()

    # ID of invoice sent when chose to 'Pay by invoice'.
    sent_invoice_id = models.CharField(max_length=255, null=True)

    @override
    def __str__(self) -> str:
        return f"{self.name} (status: {self.get_plan_status_as_text()})"

    def get_plan_status_as_text(self) -> str:
        return {
            self.CONFIGURED: "Configured",
            self.PROCESSED: "Processed",
        }[self.status]

    @staticmethod
    def name_from_tier(tier: int) -> str:
        return {
            CustomerPlanOffer.TIER_CLOUD_STANDARD: "Zulip Cloud Standard",
            CustomerPlanOffer.TIER_CLOUD_PLUS: "Zulip Cloud Plus",
            CustomerPlanOffer.TIER_SELF_HOSTED_BASIC: "Zulip Basic",
            CustomerPlanOffer.TIER_SELF_HOSTED_BUSINESS: "Zulip Business",
        }[tier]

    @property
    def name(self) -> str:
        return self.name_from_tier(self.tier)


class CustomerPlan(AbstractCustomerPlan):
    """
    This is for storing most of the fiddly details
    of the customer's plan.
    """

    automanage_licenses = models.BooleanField(default=False)
    charge_automatically = models.BooleanField(default=False)

    # Both of the price_per_license and fixed_price are in cents. Exactly
    # one of them should be set. fixed_price is only for manual deals, and
    # can't be set via the self-serve billing system.
    price_per_license = models.IntegerField(null=True)

    # Discount for current `billing_schedule`. For display purposes only.
    # Explicitly set to be TextField to avoid being used in calculations.
    # NOTE: This discount can be different for annual and monthly schedules.
    discount = models.TextField(null=True)

    # Initialized with the time of plan creation. Used for calculating
    # start of next billing cycle, next invoice date etc. This value
    # should never be modified. The only exception is when we change
    # the status of the plan from free trial to active and reset the
    # billing_cycle_anchor.
    billing_cycle_anchor = models.DateTimeField()

    BILLING_SCHEDULE_ANNUAL = 1
    BILLING_SCHEDULE_MONTHLY = 2
    BILLING_SCHEDULES = {
        BILLING_SCHEDULE_ANNUAL: "Annual",
        BILLING_SCHEDULE_MONTHLY: "Monthly",
    }
    billing_schedule = models.SmallIntegerField()

    # The next date the billing system should go through ledger
    # entries and create invoices for additional users or plan
    # renewal. Since we use a daily cron job for invoicing, the
    # invoice will be generated the first time the cron job runs after
    # next_invoice_date.
    next_invoice_date = models.DateTimeField(db_index=True, null=True)

    # Flag to track if an email has been sent to Zulip team for delay
    # of invoicing by >= one day. Helps to send an email only once
    # and not every time when cron run.
    stale_audit_log_data_email_sent = models.BooleanField(default=False)

    # Flag to track if an email has been sent to Zulip team to
    # review the pricing, 60 days before the end date. Helps to send
    # an email only once and not every time when cron run.
    reminder_to_review_plan_email_sent = models.BooleanField(default=False)

    # On next_invoice_date, we call invoice_plan, which goes through
    # ledger entries that were created after invoiced_through and
    # process them. An invoice will be generated for any additional
    # users and/or plan renewal (if it's the end of the billing cycle).
    # Once all new ledger entries have been processed, invoiced_through
    # will be have been set to the last ledger entry we checked.
    invoiced_through = models.ForeignKey(
        "LicenseLedger", null=True, on_delete=CASCADE, related_name="+"
    )
    end_date = models.DateTimeField(null=True)

    INVOICING_STATUS_DONE = 1
    INVOICING_STATUS_STARTED = 2
    INVOICING_STATUS_INITIAL_INVOICE_TO_BE_SENT = 3
    # This status field helps ensure any errors encountered during the
    # invoicing process do not leave our invoicing system in a broken
    # state.
    invoicing_status = models.SmallIntegerField(default=INVOICING_STATUS_DONE)

    TIER_CLOUD_STANDARD = 1
    TIER_CLOUD_PLUS = 2
    # Reserved tier IDs for future use
    TIER_CLOUD_COMMUNITY = 3
    TIER_CLOUD_ENTERPRISE = 4

    TIER_SELF_HOSTED_BASE = 100
    TIER_SELF_HOSTED_LEGACY = 101
    TIER_SELF_HOSTED_COMMUNITY = 102
    TIER_SELF_HOSTED_BASIC = 103
    TIER_SELF_HOSTED_BUSINESS = 104
    TIER_SELF_HOSTED_ENTERPRISE = 105
    tier = models.SmallIntegerField()

    PAID_PLAN_TIERS = [
        TIER_CLOUD_STANDARD,
        TIER_CLOUD_PLUS,
        TIER_SELF_HOSTED_BASIC,
        TIER_SELF_HOSTED_BUSINESS,
        TIER_SELF_HOSTED_ENTERPRISE,
    ]

    COMPLIMENTARY_PLAN_TIERS = [TIER_SELF_HOSTED_LEGACY]

    ACTIVE = 1
    DOWNGRADE_AT_END_OF_CYCLE = 2
    FREE_TRIAL = 3
    SWITCH_TO_ANNUAL_AT_END_OF_CYCLE = 4
    SWITCH_PLAN_TIER_NOW = 5
    SWITCH_TO_MONTHLY_AT_END_OF_CYCLE = 6
    DOWNGRADE_AT_END_OF_FREE_TRIAL = 7
    SWITCH_PLAN_TIER_AT_PLAN_END = 8
    # "Live" plans should have a value < LIVE_STATUS_THRESHOLD.
    # There should be at most one live plan per customer.
    LIVE_STATUS_THRESHOLD = 10
    ENDED = 11
    NEVER_STARTED = 12
    status = models.SmallIntegerField(default=ACTIVE)

    # Currently, all the fixed-price plans are configured for one year.
    # In future, we might change this to a field.
    FIXED_PRICE_PLAN_DURATION_MONTHS = 12

    # TODO maybe override setattr to ensure billing_cycle_anchor, etc
    # are immutable.

    @override
    def __str__(self) -> str:
        return f"{self.name} (status: {self.get_plan_status_as_text()})"

    @staticmethod
    def name_from_tier(tier: int) -> str:
        # NOTE: Check `statement_descriptor` values after updating this.
        # Stripe has a 22 character limit on the statement descriptor length.
        # https://stripe.com/docs/payments/account/statement-descriptors
        return {
            CustomerPlan.TIER_CLOUD_STANDARD: "Zulip Cloud Standard",
            CustomerPlan.TIER_CLOUD_PLUS: "Zulip Cloud Plus",
            CustomerPlan.TIER_CLOUD_ENTERPRISE: "Zulip Enterprise",
            CustomerPlan.TIER_SELF_HOSTED_BASIC: "Zulip Basic",
            CustomerPlan.TIER_SELF_HOSTED_BUSINESS: "Zulip Business",
            CustomerPlan.TIER_SELF_HOSTED_COMMUNITY: "Community",
            # Complimentary access plans should never be billed through Stripe,
            # so the tier name can exceed the 22 character limit noted above.
            CustomerPlan.TIER_SELF_HOSTED_LEGACY: "Zulip Basic (complimentary)",
        }[tier]

    @property
    def name(self) -> str:
        return self.name_from_tier(self.tier)

    def get_plan_status_as_text(self) -> str:
        return {
            self.ACTIVE: "Active",
            self.DOWNGRADE_AT_END_OF_CYCLE: "Downgrade end of cycle",
            self.FREE_TRIAL: "Free trial",
            self.SWITCH_TO_ANNUAL_AT_END_OF_CYCLE: "Scheduled switch to annual",
            self.SWITCH_TO_MONTHLY_AT_END_OF_CYCLE: "Scheduled switch to monthly",
            self.DOWNGRADE_AT_END_OF_FREE_TRIAL: "Downgrade end of free trial",
            self.SWITCH_PLAN_TIER_AT_PLAN_END: "New plan scheduled",
            self.ENDED: "Ended",
            self.NEVER_STARTED: "Never started",
        }[self.status]

    def licenses(self) -> int:
        from corporate.models.licenses import LicenseLedger

        ledger_entry = LicenseLedger.objects.filter(plan=self).order_by("id").last()
        assert ledger_entry is not None
        return ledger_entry.licenses

    def licenses_at_next_renewal(self) -> int | None:
        from corporate.models.licenses import LicenseLedger

        if self.status in (
            CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE,
            CustomerPlan.DOWNGRADE_AT_END_OF_FREE_TRIAL,
        ):
            return None
        ledger_entry = LicenseLedger.objects.filter(plan=self).order_by("id").last()
        assert ledger_entry is not None
        return ledger_entry.licenses_at_next_renewal

    def is_free_trial(self) -> bool:
        return self.status == CustomerPlan.FREE_TRIAL

    def is_complimentary_access_plan(self) -> bool:
        return self.tier in self.COMPLIMENTARY_PLAN_TIERS

    def is_a_paid_plan(self) -> bool:
        return self.tier in self.PAID_PLAN_TIERS


def get_current_plan_by_customer(customer: Customer) -> CustomerPlan | None:
    return CustomerPlan.objects.filter(
        customer=customer, status__lt=CustomerPlan.LIVE_STATUS_THRESHOLD
    ).first()


def get_current_plan_by_realm(realm: Realm) -> CustomerPlan | None:
    customer = get_customer_by_realm(realm)
    if customer is None:
        return None
    return get_current_plan_by_customer(customer)
