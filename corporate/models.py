import datetime
from decimal import Decimal
from typing import Optional

from django.db import models
from django.db.models import CASCADE

from zerver.models import Realm, RealmAuditLog

class Customer(models.Model):
    realm = models.OneToOneField(Realm, on_delete=CASCADE)  # type: Realm
    stripe_customer_id = models.CharField(max_length=255, unique=True)  # type: str
    # Deprecated .. delete once everyone is migrated to new billing system
    has_billing_relationship = models.BooleanField(default=False)  # type: bool
    default_discount = models.DecimalField(decimal_places=4, max_digits=7, null=True)  # type: Optional[Decimal]

    def __str__(self) -> str:
        return "<Customer %s %s>" % (self.realm, self.stripe_customer_id)

class CustomerPlan(models.Model):
    customer = models.ForeignKey(Customer, on_delete=CASCADE)  # type: Customer
    # Deprecated .. delete once everyone is migrated to new billing system
    licenses = models.IntegerField()  # type: int
    automanage_licenses = models.BooleanField(default=False)  # type: bool
    charge_automatically = models.BooleanField(default=False)  # type: bool

    # Both of these are in cents. Exactly one of price_per_license or
    # fixed_price should be set. fixed_price is only for manual deals, and
    # can't be set via the self-serve billing system.
    price_per_license = models.IntegerField(null=True)  # type: Optional[int]
    fixed_price = models.IntegerField(null=True)  # type: Optional[int]

    # A percentage, like 85
    discount = models.DecimalField(decimal_places=4, max_digits=6, null=True)  # type: Optional[Decimal]

    billing_cycle_anchor = models.DateTimeField()  # type: datetime.datetime
    ANNUAL = 1
    MONTHLY = 2
    billing_schedule = models.SmallIntegerField()  # type: int

    # This is like analytic's FillState, but for billing
    billed_through = models.DateTimeField()  # type: datetime.datetime
    next_billing_date = models.DateTimeField(db_index=True)  # type: datetime.datetime

    STANDARD = 1
    PLUS = 2  # not available through self-serve signup
    ENTERPRISE = 10
    tier = models.SmallIntegerField()  # type: int

    ACTIVE = 1
    ENDED = 2
    NEVER_STARTED = 3
    # You can only have 1 active subscription at a time
    status = models.SmallIntegerField(default=ACTIVE)  # type: int

    # TODO maybe override setattr to ensure billing_cycle_anchor, etc are immutable

def get_active_plan(customer: Customer) -> Optional[CustomerPlan]:
    return CustomerPlan.objects.filter(customer=customer, status=CustomerPlan.ACTIVE).first()

class LicenseLedger(models.Model):
    plan = models.ForeignKey(CustomerPlan, on_delete=CASCADE)  # type: CustomerPlan
    # Also True for the initial upgrade.
    is_renewal = models.BooleanField(default=False)  # type: bool
    event_time = models.DateTimeField()  # type: datetime.datetime
    licenses = models.IntegerField()  # type: int
    # None means the plan does not automatically renew.
    # 0 means the plan has been explicitly downgraded.
    # This cannot be None if plan.automanage_licenses.
    licenses_at_next_renewal = models.IntegerField(null=True)  # type: Optional[int]

# Everything below here is legacy

class Plan(models.Model):
    # The two possible values for nickname
    CLOUD_MONTHLY = 'monthly'
    CLOUD_ANNUAL = 'annual'
    nickname = models.CharField(max_length=40, unique=True)  # type: str

    stripe_plan_id = models.CharField(max_length=255, unique=True)  # type: str

class Coupon(models.Model):
    percent_off = models.SmallIntegerField(unique=True)  # type: int
    stripe_coupon_id = models.CharField(max_length=255, unique=True)  # type: str

    def __str__(self) -> str:
        return '<Coupon: %s %s %s>' % (self.percent_off, self.stripe_coupon_id, self.id)

class BillingProcessor(models.Model):
    log_row = models.ForeignKey(RealmAuditLog, on_delete=CASCADE)  # RealmAuditLog
    # Exactly one processor, the global processor, has realm=None.
    realm = models.OneToOneField(Realm, null=True, on_delete=CASCADE)  # type: Realm

    DONE = 'done'
    STARTED = 'started'
    SKIPPED = 'skipped'  # global processor only
    STALLED = 'stalled'  # realm processors only
    state = models.CharField(max_length=20)  # type: str

    last_modified = models.DateTimeField(auto_now=True)  # type: datetime.datetime

    def __str__(self) -> str:
        return '<BillingProcessor: %s %s %s>' % (self.realm, self.log_row, self.id)
