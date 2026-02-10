from enum import Enum

from django.db import models
from django.db.models import CASCADE

from corporate.models.customers import Customer
from zerver.models import Realm, UserProfile


class SponsoredPlanTypes(Enum):
    # unspecified used for cloud sponsorship requests
    UNSPECIFIED = ""
    COMMUNITY = "Community"
    BASIC = "Basic"
    BUSINESS = "Business"


class ZulipSponsorshipRequest(models.Model):
    customer = models.ForeignKey(Customer, on_delete=CASCADE)
    requested_by = models.ForeignKey(UserProfile, on_delete=CASCADE, null=True, blank=True)

    org_type = models.PositiveSmallIntegerField(
        default=Realm.ORG_TYPES["unspecified"]["id"],
        choices=[(t["id"], t["name"]) for t in Realm.ORG_TYPES.values()],
    )

    MAX_ORG_URL_LENGTH: int = 200
    org_website = models.URLField(max_length=MAX_ORG_URL_LENGTH, blank=True, null=True)

    org_description = models.TextField(default="")
    expected_total_users = models.TextField(default="")
    plan_to_use_zulip = models.TextField(default="")
    paid_users_count = models.TextField(default="")
    paid_users_description = models.TextField(default="")

    requested_plan = models.CharField(
        max_length=50,
        choices=[(plan.value, plan.name) for plan in SponsoredPlanTypes],
        default=SponsoredPlanTypes.UNSPECIFIED.value,
    )
