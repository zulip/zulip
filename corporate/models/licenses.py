from django.db import models
from django.db.models import CASCADE
from typing_extensions import override

from corporate.models.plans import CustomerPlan


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

    plan = models.ForeignKey(CustomerPlan, on_delete=CASCADE)

    # Also True for the initial upgrade.
    is_renewal = models.BooleanField(default=False)

    event_time = models.DateTimeField()

    # The number of licenses ("seats") purchased by the organization at the time of ledger
    # entry creation. Normally, to add a user the organization needs at least one spare license.
    # Once a license is purchased, it is valid till the end of the billing period, irrespective
    # of whether the license is used or not. So the value of licenses will never decrease for
    # subsequent LicenseLedger entries in the same billing period.
    licenses = models.IntegerField()

    # The number of licenses the organization needs in the next billing cycle. The value of
    # licenses_at_next_renewal can increase or decrease for subsequent LicenseLedger entries in
    # the same billing period. For plans on automatic license management this value is usually
    # equal to the number of activated users in the organization.
    licenses_at_next_renewal = models.IntegerField(null=True)

    @override
    def __str__(self) -> str:
        ledger_type = "renewal" if self.is_renewal else "update"
        ledger_time = self.event_time.strftime("%Y-%m-%d %H:%M")
        return f"License {ledger_type}, {self.licenses} purchased, {self.licenses_at_next_renewal} next cycle, {ledger_time} (id={self.id})"
