from django.db import models
from django.db.models import CASCADE, Q
from typing_extensions import override

from zerver.models import Realm
from zilencer.models import RemoteRealm, RemoteZulipServer


class Customer(models.Model):
    """
    This model primarily serves to connect a Realm with
    the corresponding Stripe customer object for payment purposes
    and the active plan, if any.
    """

    # The actual model object that this customer is associated
    # with. Exactly one of the following will be non-null.
    realm = models.OneToOneField(Realm, on_delete=CASCADE, null=True)
    remote_realm = models.OneToOneField(RemoteRealm, on_delete=CASCADE, null=True)
    remote_server = models.OneToOneField(RemoteZulipServer, on_delete=CASCADE, null=True)

    stripe_customer_id = models.CharField(max_length=255, null=True, unique=True)
    sponsorship_pending = models.BooleanField(default=False)

    # Discounted price for required_plan_tier in cents.
    # We treat 0 as no discount. Not using `null` here keeps the
    # checks simpler and avoids the cases where we forget to
    # check for both `null` and 0.
    monthly_discounted_price = models.IntegerField(default=0, null=False)
    annual_discounted_price = models.IntegerField(default=0, null=False)

    minimum_licenses = models.PositiveIntegerField(null=True)
    # Used for limiting discounted price or a fixed_price
    # to be used only for a particular CustomerPlan tier.
    required_plan_tier = models.SmallIntegerField(null=True)
    # Some non-profit organizations on manual license management pay
    # only for their paid employees.  We don't prevent these
    # organizations from adding more users than the number of licenses
    # they purchased.
    exempt_from_license_number_check = models.BooleanField(default=False)

    # In cents.
    flat_discount = models.IntegerField(default=2000)
    # Number of months left in the flat discount period.
    flat_discounted_months = models.IntegerField(default=0)

    class Meta:
        # Enforce that at least one of these is set.
        constraints = [
            models.CheckConstraint(
                condition=Q(realm__isnull=False)
                | Q(remote_server__isnull=False)
                | Q(remote_realm__isnull=False),
                name="has_associated_model_object",
            )
        ]

    @override
    def __str__(self) -> str:
        if self.realm is not None:
            return f"{self.realm!r} (with stripe_customer_id: {self.stripe_customer_id})"
        elif self.remote_realm is not None:
            return f"{self.remote_realm!r} (with stripe_customer_id: {self.stripe_customer_id})"
        else:
            return f"{self.remote_server!r} (with stripe_customer_id: {self.stripe_customer_id})"

    def get_discounted_price_for_plan(self, plan_tier: int, schedule: int) -> int | None:
        from corporate.models.plans import CustomerPlan

        if plan_tier != self.required_plan_tier:
            return None

        if schedule == CustomerPlan.BILLING_SCHEDULE_ANNUAL:
            return self.annual_discounted_price

        assert schedule == CustomerPlan.BILLING_SCHEDULE_MONTHLY
        return self.monthly_discounted_price


def get_customer_by_realm(realm: Realm) -> Customer | None:
    return Customer.objects.filter(realm=realm).first()


def get_customer_by_remote_server(remote_server: RemoteZulipServer) -> Customer | None:
    return Customer.objects.filter(remote_server=remote_server).first()


def get_customer_by_remote_realm(remote_realm: RemoteRealm) -> Customer | None:  # nocoverage
    return Customer.objects.filter(remote_realm=remote_realm).first()
