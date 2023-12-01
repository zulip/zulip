from decimal import Decimal
from typing import Optional
from urllib.parse import urlencode, urljoin, urlunsplit

from django.conf import settings
from django.urls import reverse

from corporate.lib.stripe import RealmBillingSession
from corporate.models import CustomerPlan, get_customer_by_realm
from zerver.models import Realm, get_realm


def get_support_url(realm: Realm) -> str:
    support_realm_uri = get_realm(settings.STAFF_SUBDOMAIN).uri
    support_url = urljoin(
        support_realm_uri,
        urlunsplit(("", "", reverse("support"), urlencode({"q": realm.string_id}), "")),
    )
    return support_url


def get_discount_for_realm(realm: Realm) -> Optional[Decimal]:
    customer = get_customer_by_realm(realm)
    if customer is not None:
        return customer.default_discount
    return None


def switch_realm_from_standard_to_plus_plan(realm: Realm) -> None:
    billing_session = RealmBillingSession(realm=realm)
    billing_session.do_change_plan_to_new_tier(new_plan_tier=CustomerPlan.TIER_CLOUD_PLUS)
