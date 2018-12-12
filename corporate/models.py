import datetime
from decimal import Decimal
from typing import Optional

from django.db import models

from zerver.models import Realm, RealmAuditLog

class Customer(models.Model):
    realm = models.OneToOneField(Realm, on_delete=models.CASCADE)  # type: Realm
    stripe_customer_id = models.CharField(max_length=255, unique=True)  # type: str
    # Becomes True the first time a payment successfully goes through, and never
    # goes back to being False
    has_billing_relationship = models.BooleanField(default=False)  # type: bool
    default_discount = models.DecimalField(decimal_places=4, max_digits=7, null=True)  # type: Optional[Decimal]

    def __str__(self) -> str:
        return "<Customer %s %s>" % (self.realm, self.stripe_customer_id)

class Plan(models.Model):
    # The two possible values for nickname
    CLOUD_MONTHLY = 'monthly'
    CLOUD_ANNUAL = 'annual'
    nickname = models.CharField(max_length=40, unique=True)  # type: str

    stripe_plan_id = models.CharField(max_length=255, unique=True)  # type: str

# Everything below here is legacy

class Coupon(models.Model):
    percent_off = models.SmallIntegerField(unique=True)  # type: int
    stripe_coupon_id = models.CharField(max_length=255, unique=True)  # type: str

    def __str__(self) -> str:
        return '<Coupon: %s %s %s>' % (self.percent_off, self.stripe_coupon_id, self.id)

class BillingProcessor(models.Model):
    log_row = models.ForeignKey(RealmAuditLog, on_delete=models.CASCADE)  # RealmAuditLog
    # Exactly one processor, the global processor, has realm=None.
    realm = models.OneToOneField(Realm, null=True, on_delete=models.CASCADE)  # type: Realm

    DONE = 'done'
    STARTED = 'started'
    SKIPPED = 'skipped'  # global processor only
    STALLED = 'stalled'  # realm processors only
    state = models.CharField(max_length=20)  # type: str

    last_modified = models.DateTimeField(auto_now=True)  # type: datetime.datetime

    def __str__(self) -> str:
        return '<BillingProcessor: %s %s %s>' % (self.realm, self.log_row, self.id)
