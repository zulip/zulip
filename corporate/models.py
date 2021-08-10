import datetime
from decimal import Decimal
from typing import Optional

from django.db import models
from django.db.models import CASCADE

from zerver.models import Realm, UserProfile


class Customer(models.Model):
    """
    This model primarily serves to connect a Realm with
    the corresponding Stripe customer object for payment purposes
    and the active plan, if any.
    """

    realm: Realm = models.OneToOneField(Realm, on_delete=CASCADE)
    stripe_customer_id: Optional[str] = models.CharField(max_length=255, null=True, unique=True)
    sponsorship_pending: bool = models.BooleanField(default=False)
    # A percentage, like 85.
    default_discount: Optional[Decimal] = models.DecimalField(
        decimal_places=4, max_digits=7, null=True
    )
    # Some non-profit organizations on manual license management pay
    # only for their paid employees.  We don't prevent these
    # organizations from adding more users than the number of licenses
    # they purchased.
    exempt_from_from_license_number_check: bool = models.BooleanField(default=False)

    def __str__(self) -> str:
        return f"<Customer {self.realm} {self.stripe_customer_id}>"


def get_customer_by_realm(realm: Realm) -> Optional[Customer]:
    return Customer.objects.filter(realm=realm).first()


class CustomerPlan(models.Model):
    """
    This is for storing most of the fiddly details
    of the customer's plan.
    """

    # A customer can only have one ACTIVE plan, but old, inactive plans
    # are preserved to allow auditing - so there can be multiple
    # CustomerPlan objects pointing to one Customer.
    customer: Customer = models.ForeignKey(Customer, on_delete=CASCADE)

    automanage_licenses: bool = models.BooleanField(default=False)
    charge_automatically: bool = models.BooleanField(default=False)

    # Both of these are in cents. Exactly one of price_per_license or
    # fixed_price should be set. fixed_price is only for manual deals, and
    # can't be set via the self-serve billing system.
    price_per_license: Optional[int] = models.IntegerField(null=True)
    fixed_price: Optional[int] = models.IntegerField(null=True)

    # Discount that was applied. For display purposes only.
    discount: Optional[Decimal] = models.DecimalField(decimal_places=4, max_digits=6, null=True)

    # Initialized with the time of plan creation. Used for calculating
    # start of next billing cycle, next invoice date etc. This value
    # should never be modified. The only exception is when we change
    # the status of the plan from free trial to active and reset the
    # billing_cycle_anchor.
    billing_cycle_anchor: datetime.datetime = models.DateTimeField()

    ANNUAL = 1
    MONTHLY = 2
    billing_schedule: int = models.SmallIntegerField()

    # The next date the billing system should go through ledger
    # entries and create invoices for additional users or plan
    # renewal. Since we use a daily cron job for invoicing, the
    # invoice will be generated the first time the cron job runs after
    # next_invoice_date.
    next_invoice_date: Optional[datetime.datetime] = models.DateTimeField(db_index=True, null=True)

    # On next_invoice_date, we go through ledger entries that were
    # created after invoiced_through and process them by generating
    # invoices for any additional users and/or plan renewal. Once the
    # invoice is generated, we update the value of invoiced_through
    # and set it to the last ledger entry we processed.
    invoiced_through: Optional["LicenseLedger"] = models.ForeignKey(
        "LicenseLedger", null=True, on_delete=CASCADE, related_name="+"
    )

    DONE = 1
    STARTED = 2
    INITIAL_INVOICE_TO_BE_SENT = 3
    # This status field helps ensure any errors encountered during the
    # invoicing process do not leave our invoicing system in a broken
    # state.
    invoicing_status: int = models.SmallIntegerField(default=DONE)

    STANDARD = 1
    PLUS = 2  # not available through self-serve signup
    ENTERPRISE = 10
    tier: int = models.SmallIntegerField()

    ACTIVE = 1
    DOWNGRADE_AT_END_OF_CYCLE = 2
    FREE_TRIAL = 3
    SWITCH_TO_ANNUAL_AT_END_OF_CYCLE = 4
    # "Live" plans should have a value < LIVE_STATUS_THRESHOLD.
    # There should be at most one live plan per customer.
    LIVE_STATUS_THRESHOLD = 10
    ENDED = 11
    NEVER_STARTED = 12
    status: int = models.SmallIntegerField(default=ACTIVE)

    # TODO maybe override setattr to ensure billing_cycle_anchor, etc
    # are immutable.

    @property
    def name(self) -> str:
        return {
            CustomerPlan.STANDARD: "Zulip Standard",
            CustomerPlan.PLUS: "Zulip Plus",
            CustomerPlan.ENTERPRISE: "Zulip Enterprise",
        }[self.tier]

    def get_plan_status_as_text(self) -> str:
        return {
            self.ACTIVE: "Active",
            self.DOWNGRADE_AT_END_OF_CYCLE: "Scheduled for downgrade at end of cycle",
            self.FREE_TRIAL: "Free trial",
            self.ENDED: "Ended",
            self.NEVER_STARTED: "Never started",
        }[self.status]

    def licenses(self) -> int:
        ledger_entry = LicenseLedger.objects.filter(plan=self).order_by("id").last()
        assert ledger_entry is not None
        return ledger_entry.licenses

    def licenses_at_next_renewal(self) -> Optional[int]:
        if self.status == CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE:
            return None
        ledger_entry = LicenseLedger.objects.filter(plan=self).order_by("id").last()
        assert ledger_entry is not None
        return ledger_entry.licenses_at_next_renewal

    def is_free_trial(self) -> bool:
        return self.status == CustomerPlan.FREE_TRIAL


def get_current_plan_by_customer(customer: Customer) -> Optional[CustomerPlan]:
    return CustomerPlan.objects.filter(
        customer=customer, status__lt=CustomerPlan.LIVE_STATUS_THRESHOLD
    ).first()


def get_current_plan_by_realm(realm: Realm) -> Optional[CustomerPlan]:
    customer = get_customer_by_realm(realm)
    if customer is None:
        return None
    return get_current_plan_by_customer(customer)


class LicenseLedger(models.Model):
    """
    This table's purpose is to store the current, and historical,
    count of "seats" purchased by the organization.

    Because we want to keep historical data, when the purchased
    seat count changes, a new LicenseLedger object is created,
    instead of updating the old one. This lets us preserve
    the entire history of how the seat count changes, which is
    important for analytics as well as auditing and debugging
    in case of issues.
    """

    plan: CustomerPlan = models.ForeignKey(CustomerPlan, on_delete=CASCADE)

    # Also True for the initial upgrade.
    is_renewal: bool = models.BooleanField(default=False)

    event_time: datetime.datetime = models.DateTimeField()

    # The number of licenses ("seats") purchased by the the organization at the time of ledger
    # entry creation. Normally, to add a user the organization needs at least one spare license.
    # Once a license is purchased, it is valid till the end of the billing period, irrespective
    # of whether the license is used or not. So the value of licenses will never decrease for
    # subsequent LicenseLedger entries in the same billing period.
    licenses: int = models.IntegerField()

    # The number of licenses the organization needs in the next billing cycle. The value of
    # licenses_at_next_renewal can increase or decrease for subsequent LicenseLedger entries in
    # the same billing period. For plans on automatic license management this value is usually
    # equal to the number of activated users in the organization.
    licenses_at_next_renewal: Optional[int] = models.IntegerField(null=True)


class ZulipSponsorshipRequest(models.Model):
    id: int = models.AutoField(auto_created=True, primary_key=True, verbose_name="ID")
    realm: Realm = models.ForeignKey(Realm, on_delete=CASCADE)
    requested_by: UserProfile = models.ForeignKey(UserProfile, on_delete=CASCADE)

    org_type: int = models.PositiveSmallIntegerField(
        default=Realm.ORG_TYPES["unspecified"]["id"],
        choices=[(t["id"], t["name"]) for t in Realm.ORG_TYPES.values()],
    )

    MAX_ORG_URL_LENGTH: int = 200
    org_website: str = models.URLField(max_length=MAX_ORG_URL_LENGTH, blank=True, null=True)

    org_description: str = models.TextField(default="")
