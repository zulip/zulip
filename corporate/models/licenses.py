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

    # The number of workplace user licenses ("seats") purchased by the organization at the time
    # of ledger entry creation. Normally, to add a user the organization needs at least one spare
    # license. Once a license is purchased, it is valid till the end of the billing period,
    # irrespective of whether the license is used or not. So the value of workplace_licenses will
    # never decrease for subsequent LicenseLedger entries in the same billing period.
    #
    # The database columns for these fields are still named "licenses" and
    # "licenses_at_next_renewal". Renaming them would break the previous release's code, which
    # still queries the old names, during the window where it runs against the migrated database.
    workplace_licenses = models.IntegerField(db_column="licenses")

    # The number of workplace user licenses the organization needs in the next billing cycle. The
    # value of workplace_licenses_at_next_renewal can increase or decrease for subsequent
    # LicenseLedger entries in the same billing period. For plans on automatic license management
    # this value is usually equal to the number of activated workplace users in the organization.
    workplace_licenses_at_next_renewal = models.IntegerField(
        null=True, db_column="licenses_at_next_renewal"
    )

    # The number of licenses for users outside the realm's workplace_users_group at the time of
    # ledger entry creation. These are billed at a discounted rate, so they are counted
    # separately from workplace_licenses rather than being folded into it. The same "a license is
    # valid till the end of the billing period" rule applies, so external_licenses never
    # decreases for subsequent LicenseLedger entries in the same billing period.
    #
    # This counts the licenses actually billed at the discounted rate, so it is 0 for a plan
    # that does not bill an external tier, even if the realm's workplace_users_group happens to
    # exclude some users. Whether a plan bills an external tier is a property of the plan.
    external_licenses = models.IntegerField(db_default=0, default=0)

    # The number of external licenses the organization needs in the next billing cycle. Like
    # workplace_licenses_at_next_renewal, this can increase or decrease for subsequent
    # LicenseLedger entries in the same billing period.
    external_licenses_at_next_renewal = models.IntegerField(db_default=0, default=0)

    @override
    def __str__(self) -> str:
        ledger_type = "renewal" if self.is_renewal else "update"
        ledger_time = self.event_time.replace(tzinfo=None).isoformat(" ", "minutes")
        external = ""
        # Omitted entirely for plans without an external tier, which is the common case.
        if self.external_licenses or self.external_licenses_at_next_renewal:
            external = (
                f", {self.external_licenses} external"
                f" ({self.external_licenses_at_next_renewal} next cycle)"
            )
        return f"License {ledger_type}, {self.workplace_licenses} purchased, {self.workplace_licenses_at_next_renewal} next cycle{external}, {ledger_time} (id={self.id})"
