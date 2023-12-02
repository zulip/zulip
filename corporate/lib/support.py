from decimal import Decimal
from typing import Optional
from urllib.parse import urlencode, urljoin, urlunsplit

from django.conf import settings
from django.urls import reverse

from corporate.models import Customer
from zerver.models import Realm, get_realm


def get_support_url(realm: Realm) -> str:
    support_realm_uri = get_realm(settings.STAFF_SUBDOMAIN).uri
    support_url = urljoin(
        support_realm_uri,
        urlunsplit(("", "", reverse("support"), urlencode({"q": realm.string_id}), "")),
    )
    return support_url


def get_customer_discount_for_support_view(
    customer: Optional[Customer] = None,
) -> Optional[Decimal]:
    if customer is None:
        return None
    return customer.default_discount
