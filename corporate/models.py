import datetime
from decimal import Decimal
from typing import Optional

from django.db import models
from django.db.models import CASCADE

from zerver.models import Realm


class Customer(models.Model):
    realm: Realm = models.OneToOneField(Realm, on_delete=CASCADE)
    stripe_customer_id: str = models.CharField(max_length=255, null=True, unique=True)
    sponsorship_pending: bool = models.BooleanField(default=False)
    # A percentage, like 85.
    default_discount: Optional[Decimal] = models.DecimalField(decimal_places=4, max_digits=7, null=True)

    def __str__(self) -> str:
        return f"<Customer {self.realm} {self.stripe_customer_id}>"

def get_customer_by_realm(realm: Realm) -> Optional[Customer]:
    return Customer.objects.filter(realm=realm).first()

class CustomerPlan(models.Model):
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

    billing_cycle_anchor: datetime.datetime = models.DateTimeField()
    ANNUAL = 1
    MONTHLY = 2
    billing_schedule: int = models.SmallIntegerField()

    next_invoice_date: Optional[datetime.datetime] = models.DateTimeField(db_index=True, null=True)
    invoiced_through: Optional["LicenseLedger"] = models.ForeignKey(
        'LicenseLedger', null=True, on_delete=CASCADE, related_name='+')
    DONE = 1
    STARTED = 2
    INITIAL_INVOICE_TO_BE_SENT = 3
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

    # TODO maybe override setattr to ensure billing_cycle_anchor, etc are immutable

    @property
    def name(self) -> str:
        return {
            CustomerPlan.STANDARD: 'Zulip Standard',
            CustomerPlan.PLUS: 'Zulip Plus',
            CustomerPlan.ENTERPRISE: 'Zulip Enterprise',
        }[self.tier]

    def get_plan_status_as_text(self) -> str:
        return {
            self.ACTIVE: "Active",
            self.DOWNGRADE_AT_END_OF_CYCLE: "Scheduled for downgrade at end of cycle",
            self.FREE_TRIAL: "Free trial",
            self.ENDED: "Ended",
            self.NEVER_STARTED: "Never started"
        }[self.status]

def get_current_plan_by_customer(customer: Customer) -> Optional[CustomerPlan]:
    return CustomerPlan.objects.filter(
        customer=customer, status__lt=CustomerPlan.LIVE_STATUS_THRESHOLD).first()

def get_current_plan_by_realm(realm: Realm) -> Optional[CustomerPlan]:
    customer = get_customer_by_realm(realm)
    if customer is None:
        return None
    return get_current_plan_by_customer(customer)

class LicenseLedger(models.Model):
    plan: CustomerPlan = models.ForeignKey(CustomerPlan, on_delete=CASCADE)
    # Also True for the initial upgrade.
    is_renewal: bool = models.BooleanField(default=False)
    event_time: datetime.datetime = models.DateTimeField()
    licenses: int = models.IntegerField()
    # None means the plan does not automatically renew.
    # This cannot be None if plan.automanage_licenses.
    licenses_at_next_renewal: Optional[int] = models.IntegerField(null=True)
