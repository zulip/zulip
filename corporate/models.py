import datetime
from decimal import Decimal
from typing import Optional

from django.db import models
from django.db.models import CASCADE

from zerver.models import Realm

class Customer(models.Model):
    realm = models.OneToOneField(Realm, on_delete=CASCADE)  # type: Realm
    stripe_customer_id = models.CharField(max_length=255, null=True, unique=True)  # type: str
    # A percentage, like 85.
    default_discount = models.DecimalField(decimal_places=4, max_digits=7, null=True)  # type: Optional[Decimal]

    def __str__(self) -> str:
        return "<Customer %s %s>" % (self.realm, self.stripe_customer_id)

class CustomerPlan(models.Model):
    customer = models.ForeignKey(Customer, on_delete=CASCADE)  # type: Customer
    automanage_licenses = models.BooleanField(default=False)  # type: bool
    charge_automatically = models.BooleanField(default=False)  # type: bool

    # Both of these are in cents. Exactly one of price_per_license or
    # fixed_price should be set. fixed_price is only for manual deals, and
    # can't be set via the self-serve billing system.
    price_per_license = models.IntegerField(null=True)  # type: Optional[int]
    fixed_price = models.IntegerField(null=True)  # type: Optional[int]

    # Discount that was applied. For display purposes only.
    discount = models.DecimalField(decimal_places=4, max_digits=6, null=True)  # type: Optional[Decimal]

    billing_cycle_anchor = models.DateTimeField()  # type: datetime.datetime
    ANNUAL = 1
    MONTHLY = 2
    billing_schedule = models.SmallIntegerField()  # type: int

    next_invoice_date = models.DateTimeField(db_index=True)  # type: datetime.datetime
    invoiced_through = models.ForeignKey(
        'LicenseLedger', null=True, on_delete=CASCADE, related_name='+')  # type: Optional[LicenseLedger]
    DONE = 1
    STARTED = 2
    invoicing_status = models.SmallIntegerField(default=DONE)  # type: int

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
