import logging
import math
import os
import secrets
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from functools import wraps
from typing import (
    Any,
    Callable,
    Dict,
    Generator,
    Literal,
    Optional,
    Tuple,
    TypedDict,
    TypeVar,
    Union,
)
from urllib.parse import urlencode, urljoin

import stripe
from django import forms
from django.conf import settings
from django.core import signing
from django.core.signing import Signer
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.utils.translation import override as override_language
from typing_extensions import ParamSpec, override

from corporate.models import (
    Customer,
    CustomerPlan,
    CustomerPlanOffer,
    Invoice,
    LicenseLedger,
    Session,
    SponsoredPlanTypes,
    ZulipSponsorshipRequest,
    get_current_plan_by_customer,
    get_current_plan_by_realm,
    get_customer_by_realm,
    get_customer_by_remote_realm,
    get_customer_by_remote_server,
)
from zerver.lib.cache import cache_with_key, get_realm_seat_count_cache_key
from zerver.lib.exceptions import JsonableError
from zerver.lib.logging_util import log_to_file
from zerver.lib.send_email import (
    FromAddress,
    send_email,
    send_email_to_billing_admins_and_realm_owners,
)
from zerver.lib.timestamp import datetime_to_timestamp, timestamp_to_datetime
from zerver.lib.url_encoding import append_url_query_string
from zerver.lib.utils import assert_is_not_none
from zerver.models import Realm, RealmAuditLog, UserProfile
from zerver.models.realms import get_org_type_display_name, get_realm
from zerver.models.users import get_system_bot
from zilencer.lib.remote_counts import MissingDataError
from zilencer.models import (
    RemoteRealm,
    RemoteRealmAuditLog,
    RemoteRealmBillingUser,
    RemoteServerBillingUser,
    RemoteZulipServer,
    RemoteZulipServerAuditLog,
    get_remote_realm_guest_and_non_guest_count,
    get_remote_server_guest_and_non_guest_count,
    has_stale_audit_log,
)
from zproject.config import get_secret

stripe.api_key = get_secret("stripe_secret_key")

BILLING_LOG_PATH = os.path.join(
    "/var/log/zulip" if not settings.DEVELOPMENT else settings.DEVELOPMENT_LOG_DIRECTORY,
    "billing.log",
)
billing_logger = logging.getLogger("corporate.stripe")
log_to_file(billing_logger, BILLING_LOG_PATH)
log_to_file(logging.getLogger("stripe"), BILLING_LOG_PATH)

ParamT = ParamSpec("ParamT")
ReturnT = TypeVar("ReturnT")

BILLING_SUPPORT_EMAIL = "sales@zulip.com"

MIN_INVOICED_LICENSES = 30
MAX_INVOICED_LICENSES = 1000
DEFAULT_INVOICE_DAYS_UNTIL_DUE = 15

VALID_BILLING_MODALITY_VALUES = ["send_invoice", "charge_automatically"]
VALID_BILLING_SCHEDULE_VALUES = ["annual", "monthly"]
VALID_LICENSE_MANAGEMENT_VALUES = ["automatic", "manual"]

CARD_CAPITALIZATION = {
    "amex": "American Express",
    "diners": "Diners Club",
    "discover": "Discover",
    "jcb": "JCB",
    "mastercard": "Mastercard",
    "unionpay": "UnionPay",
    "visa": "Visa",
}

# The version of Stripe API the billing system supports.
STRIPE_API_VERSION = "2020-08-27"

stripe.api_version = STRIPE_API_VERSION


# This function imitates the behavior of the format_money in billing/helpers.ts
def format_money(cents: float) -> str:
    # allow for small floating point errors
    cents = math.ceil(cents - 0.001)
    if cents % 100 == 0:
        precision = 0
    else:
        precision = 2

    dollars = cents / 100
    # Format the number as a string with the correct number of decimal places
    return f"{dollars:.{precision}f}"


def get_amount_due_fixed_price_plan(fixed_price: int, billing_schedule: int) -> int:
    amount_due = fixed_price
    if billing_schedule == CustomerPlan.BILLING_SCHEDULE_MONTHLY:
        amount_due = int(float(format_money(fixed_price / 12)) * 100)
    return amount_due


def format_discount_percentage(discount: Optional[Decimal]) -> Optional[str]:
    if type(discount) is not Decimal or discount == Decimal(0):
        return None

    # This will look good for any custom discounts that we apply.
    if discount * 100 % 100 == 0:
        precision = 0
    else:
        precision = 2  # nocoverage
    return f"{discount:.{precision}f}"


def get_latest_seat_count(realm: Realm) -> int:
    return get_seat_count(realm, extra_non_guests_count=0, extra_guests_count=0)


@cache_with_key(lambda realm: get_realm_seat_count_cache_key(realm.id), timeout=3600 * 24)
def get_cached_seat_count(realm: Realm) -> int:
    # This is a cache value  we're intentionally okay with not invalidating.
    # All that means is that this value will lag up to 24 hours before getting updated.
    # We use this for calculating the uploaded files storage limit for paid Cloud organizations.
    return get_latest_seat_count(realm)


def get_seat_count(
    realm: Realm, extra_non_guests_count: int = 0, extra_guests_count: int = 0
) -> int:
    non_guests = (
        UserProfile.objects.filter(realm=realm, is_active=True, is_bot=False)
        .exclude(role=UserProfile.ROLE_GUEST)
        .count()
    ) + extra_non_guests_count

    # This guest count calculation should match the similar query in render_stats().
    guests = (
        UserProfile.objects.filter(
            realm=realm, is_active=True, is_bot=False, role=UserProfile.ROLE_GUEST
        ).count()
        + extra_guests_count
    )

    # This formula achieves the pricing of the first 5*N guests
    # being free of charge (where N is the number of non-guests in the organization)
    # and each consecutive one being worth 1/5 the non-guest price.
    return max(non_guests, math.ceil(guests / 5))


def sign_string(string: str) -> Tuple[str, str]:
    salt = secrets.token_hex(32)
    signer = Signer(salt=salt)
    return signer.sign(string), salt


def unsign_string(signed_string: str, salt: str) -> str:
    signer = Signer(salt=salt)
    return signer.unsign(signed_string)


def unsign_seat_count(signed_seat_count: str, salt: str) -> int:
    try:
        return int(unsign_string(signed_seat_count, salt))
    except signing.BadSignature:
        raise BillingError("tampered seat count")


def validate_licenses(
    charge_automatically: bool,
    licenses: Optional[int],
    seat_count: int,
    exempt_from_license_number_check: bool,
    min_licenses_for_plan: int,
) -> None:
    min_licenses = max(seat_count, min_licenses_for_plan)
    max_licenses = None
    # max / min license check for invoiced plans is disabled in production right now.
    # Logic and tests are kept in case we decide to enable it in future.
    if settings.TEST_SUITE and not charge_automatically:
        min_licenses = max(seat_count, MIN_INVOICED_LICENSES)
        max_licenses = MAX_INVOICED_LICENSES

    if licenses is None or (not exempt_from_license_number_check and licenses < min_licenses):
        raise BillingError(
            "not enough licenses",
            _(
                "You must purchase licenses for all active users in your organization (minimum {min_licenses})."
            ).format(min_licenses=min_licenses),
        )

    if max_licenses is not None and licenses > max_licenses:
        message = _(
            "Invoices with more than {max_licenses} licenses can't be processed from this page. To"
            " complete the upgrade, please contact {email}."
        ).format(max_licenses=max_licenses, email=settings.ZULIP_ADMINISTRATOR)
        raise BillingError("too many licenses", message)


def check_upgrade_parameters(
    billing_modality: str,
    schedule: str,
    license_management: Optional[str],
    licenses: Optional[int],
    seat_count: int,
    exempt_from_license_number_check: bool,
    min_licenses_for_plan: int,
) -> None:
    if billing_modality not in VALID_BILLING_MODALITY_VALUES:  # nocoverage
        raise BillingError("unknown billing_modality", "")
    if schedule not in VALID_BILLING_SCHEDULE_VALUES:  # nocoverage
        raise BillingError("unknown schedule")
    if license_management not in VALID_LICENSE_MANAGEMENT_VALUES:  # nocoverage
        raise BillingError("unknown license_management")
    validate_licenses(
        billing_modality == "charge_automatically",
        licenses,
        seat_count,
        exempt_from_license_number_check,
        min_licenses_for_plan,
    )


# Be extremely careful changing this function. Historical billing periods
# are not stored anywhere, and are just computed on the fly using this
# function. Any change you make here should return the same value (or be
# within a few seconds) for basically any value from when the billing system
# went online to within a year from now.
def add_months(dt: datetime, months: int) -> datetime:
    assert months >= 0
    # It's fine that the max day in Feb is 28 for leap years.
    MAX_DAY_FOR_MONTH = {
        1: 31,
        2: 28,
        3: 31,
        4: 30,
        5: 31,
        6: 30,
        7: 31,
        8: 31,
        9: 30,
        10: 31,
        11: 30,
        12: 31,
    }
    year = dt.year
    month = dt.month + months
    while month > 12:
        year += 1
        month -= 12
    day = min(dt.day, MAX_DAY_FOR_MONTH[month])
    # datetimes don't support leap seconds, so don't need to worry about those
    return dt.replace(year=year, month=month, day=day)


def next_month(billing_cycle_anchor: datetime, dt: datetime) -> datetime:
    estimated_months = round((dt - billing_cycle_anchor).days * 12.0 / 365)
    for months in range(max(estimated_months - 1, 0), estimated_months + 2):
        proposed_next_month = add_months(billing_cycle_anchor, months)
        if 20 < (proposed_next_month - dt).days < 40:
            return proposed_next_month
    raise AssertionError(
        "Something wrong in next_month calculation with "
        f"billing_cycle_anchor: {billing_cycle_anchor}, dt: {dt}"
    )


def start_of_next_billing_cycle(plan: CustomerPlan, event_time: datetime) -> datetime:
    months_per_period = {
        CustomerPlan.BILLING_SCHEDULE_ANNUAL: 12,
        CustomerPlan.BILLING_SCHEDULE_MONTHLY: 1,
    }[plan.billing_schedule]
    periods = 1
    dt = plan.billing_cycle_anchor
    while dt <= event_time:
        dt = add_months(plan.billing_cycle_anchor, months_per_period * periods)
        periods += 1
    return dt


def next_invoice_date(plan: CustomerPlan) -> Optional[datetime]:
    if plan.status == CustomerPlan.ENDED:
        return None
    assert plan.next_invoice_date is not None  # for mypy
    months_per_period = 1
    periods = 1
    dt = plan.billing_cycle_anchor
    while dt <= plan.next_invoice_date:
        dt = add_months(plan.billing_cycle_anchor, months_per_period * periods)
        periods += 1
    return dt


def get_amount_to_credit_for_plan_tier_change(
    current_plan: CustomerPlan, plan_change_date: datetime
) -> int:
    last_renewal_ledger = (
        LicenseLedger.objects.filter(is_renewal=True, plan=current_plan).order_by("id").last()
    )
    assert last_renewal_ledger is not None
    assert current_plan.price_per_license is not None

    next_renewal_date = start_of_next_billing_cycle(current_plan, plan_change_date)

    last_renewal_amount = last_renewal_ledger.licenses * current_plan.price_per_license
    last_renewal_date = last_renewal_ledger.event_time

    prorated_fraction = 1 - (plan_change_date - last_renewal_date) / (
        next_renewal_date - last_renewal_date
    )
    amount_to_credit_back = math.ceil(last_renewal_amount * prorated_fraction)

    return amount_to_credit_back


def get_idempotency_key(ledger_entry: LicenseLedger) -> Optional[str]:
    if settings.TEST_SUITE:
        return None
    return f"ledger_entry:{ledger_entry.id}"  # nocoverage


def cents_to_dollar_string(cents: int) -> str:
    return f"{cents / 100.:,.2f}"


# Should only be called if the customer is being charged automatically
def payment_method_string(stripe_customer: stripe.Customer) -> str:
    assert stripe_customer.invoice_settings is not None
    default_payment_method = stripe_customer.invoice_settings.default_payment_method
    if default_payment_method is None:
        return _("No payment method on file.")

    assert isinstance(default_payment_method, stripe.PaymentMethod)
    if default_payment_method.type == "card":
        assert default_payment_method.card is not None
        brand_name = default_payment_method.card.brand
        if brand_name in CARD_CAPITALIZATION:
            brand_name = CARD_CAPITALIZATION[default_payment_method.card.brand]
        return _("{brand} ending in {last4}").format(
            brand=brand_name,
            last4=default_payment_method.card.last4,
        )
    # There might be one-off stuff we do for a particular customer that
    # would land them here. E.g. by default we don't support ACH for
    # automatic payments, but in theory we could add it for a customer via
    # the Stripe dashboard.
    return _("Unknown payment method. Please contact {email}.").format(
        email=settings.ZULIP_ADMINISTRATOR,
    )  # nocoverage


def build_support_url(support_view: str, query_text: str) -> str:
    support_realm_url = get_realm(settings.STAFF_SUBDOMAIN).uri
    support_url = urljoin(support_realm_url, reverse(support_view))
    query = urlencode({"q": query_text})
    support_url = append_url_query_string(support_url, query)
    return support_url


def get_configured_fixed_price_plan_offer(
    customer: Customer, plan_tier: int
) -> Optional[CustomerPlanOffer]:
    """
    Fixed price plan offer configured via /support which the
    customer is yet to buy or schedule a purchase.
    """
    if plan_tier == customer.required_plan_tier:
        return CustomerPlanOffer.objects.filter(
            customer=customer,
            tier=plan_tier,
            fixed_price__isnull=False,
            status=CustomerPlanOffer.CONFIGURED,
        ).first()
    return None


class BillingError(JsonableError):
    data_fields = ["error_description"]
    # error messages
    CONTACT_SUPPORT = gettext_lazy("Something went wrong. Please contact {email}.")
    TRY_RELOADING = gettext_lazy("Something went wrong. Please reload the page.")

    def __init__(self, description: str, message: Optional[str] = None) -> None:
        self.error_description = description
        if message is None:
            message = BillingError.CONTACT_SUPPORT.format(email=settings.ZULIP_ADMINISTRATOR)
        super().__init__(message)


class LicenseLimitError(Exception):
    pass


class StripeCardError(BillingError):
    pass


class StripeConnectionError(BillingError):
    pass


class ServerDeactivateWithExistingPlanError(BillingError):  # nocoverage
    def __init__(self) -> None:
        super().__init__(
            "server deactivation with existing plan",
            "",
        )


class UpgradeWithExistingPlanError(BillingError):
    def __init__(self) -> None:
        super().__init__(
            "subscribing with existing subscription",
            "The organization is already subscribed to a plan. Please reload the billing page.",
        )


class InvalidPlanUpgradeError(BillingError):  # nocoverage
    def __init__(self, message: str) -> None:
        super().__init__(
            "invalid plan upgrade",
            message,
        )


class InvalidBillingScheduleError(Exception):
    def __init__(self, billing_schedule: int) -> None:
        self.message = f"Unknown billing_schedule: {billing_schedule}"
        super().__init__(self.message)


class InvalidTierError(Exception):
    def __init__(self, tier: int) -> None:
        self.message = f"Unknown tier: {tier}"
        super().__init__(self.message)


class SupportRequestError(BillingError):
    def __init__(self, message: str) -> None:
        super().__init__(
            "invalid support request",
            message,
        )


def catch_stripe_errors(func: Callable[ParamT, ReturnT]) -> Callable[ParamT, ReturnT]:
    @wraps(func)
    def wrapped(*args: ParamT.args, **kwargs: ParamT.kwargs) -> ReturnT:
        try:
            return func(*args, **kwargs)
        # See https://stripe.com/docs/api/python#error_handling, though
        # https://stripe.com/docs/api/ruby#error_handling suggests there are additional fields, and
        # https://stripe.com/docs/error-codes gives a more detailed set of error codes
        except stripe.StripeError as e:
            assert isinstance(e.json_body, dict)
            err = e.json_body.get("error", {})
            if isinstance(e, stripe.CardError):
                billing_logger.info(
                    "Stripe card error: %s %s %s %s",
                    e.http_status,
                    err.get("type"),
                    err.get("code"),
                    err.get("param"),
                )
                # TODO: Look into i18n for this
                raise StripeCardError("card error", err.get("message"))
            billing_logger.error(
                "Stripe error: %s %s %s %s",
                e.http_status,
                err.get("type"),
                err.get("code"),
                err.get("param"),
            )
            if isinstance(e, (stripe.RateLimitError, stripe.APIConnectionError)):  # nocoverage TODO
                raise StripeConnectionError(
                    "stripe connection error",
                    _("Something went wrong. Please wait a few seconds and try again."),
                )
            raise BillingError("other stripe error")

    return wrapped


@catch_stripe_errors
def stripe_get_customer(stripe_customer_id: str) -> stripe.Customer:
    return stripe.Customer.retrieve(
        stripe_customer_id, expand=["invoice_settings", "invoice_settings.default_payment_method"]
    )


def sponsorship_org_type_key_helper(d: Any) -> int:
    return d[1]["display_order"]


class PriceArgs(TypedDict, total=False):
    amount: int
    unit_amount: int
    quantity: int


@dataclass
class StripeCustomerData:
    description: str
    email: str
    metadata: Dict[str, Any]


@dataclass
class UpgradeRequest:
    billing_modality: str
    schedule: str
    signed_seat_count: str
    salt: str
    license_management: Optional[str]
    licenses: Optional[int]
    tier: int
    remote_server_plan_start_date: Optional[str]


@dataclass
class InitialUpgradeRequest:
    manual_license_management: bool
    tier: int
    billing_modality: str
    success_message: str = ""


@dataclass
class UpdatePlanRequest:
    status: Optional[int]
    licenses: Optional[int]
    licenses_at_next_renewal: Optional[int]
    schedule: Optional[int]


@dataclass
class EventStatusRequest:
    stripe_session_id: Optional[str]
    stripe_invoice_id: Optional[str]


class SupportType(Enum):
    approve_sponsorship = 1
    update_sponsorship_status = 2
    attach_discount = 3
    update_billing_modality = 4
    modify_plan = 5
    update_minimum_licenses = 6
    update_plan_end_date = 7
    update_required_plan_tier = 8
    configure_fixed_price_plan = 9
    delete_fixed_price_next_plan = 10


class SupportViewRequest(TypedDict, total=False):
    support_type: SupportType
    sponsorship_status: Optional[bool]
    discount: Optional[Decimal]
    billing_modality: Optional[str]
    plan_modification: Optional[str]
    new_plan_tier: Optional[int]
    minimum_licenses: Optional[int]
    plan_end_date: Optional[str]
    required_plan_tier: Optional[int]
    fixed_price: Optional[int]
    sent_invoice_id: Optional[str]


class AuditLogEventType(Enum):
    STRIPE_CUSTOMER_CREATED = 1
    STRIPE_CARD_CHANGED = 2
    CUSTOMER_PLAN_CREATED = 3
    DISCOUNT_CHANGED = 4
    SPONSORSHIP_APPROVED = 5
    SPONSORSHIP_PENDING_STATUS_CHANGED = 6
    BILLING_MODALITY_CHANGED = 7
    CUSTOMER_SWITCHED_FROM_MONTHLY_TO_ANNUAL_PLAN = 8
    CUSTOMER_SWITCHED_FROM_ANNUAL_TO_MONTHLY_PLAN = 9
    BILLING_ENTITY_PLAN_TYPE_CHANGED = 10
    CUSTOMER_PROPERTY_CHANGED = 11
    CUSTOMER_PLAN_PROPERTY_CHANGED = 12


class PlanTierChangeType(Enum):
    INVALID = 1
    UPGRADE = 2
    DOWNGRADE = 3


class BillingSessionAuditLogEventError(Exception):
    def __init__(self, event_type: AuditLogEventType) -> None:
        self.message = f"Unknown audit log event type: {event_type}"
        super().__init__(self.message)


# Sync this with upgrade_params_schema in base_page_params.ts.
class UpgradePageParams(TypedDict):
    page_type: Literal["upgrade"]
    annual_price: int
    demo_organization_scheduled_deletion_date: Optional[datetime]
    monthly_price: int
    seat_count: int
    billing_base_url: str
    tier: int
    flat_discount: int
    flat_discounted_months: int
    fixed_price: Optional[int]
    setup_payment_by_invoice: bool
    free_trial_days: Optional[int]


class UpgradePageSessionTypeSpecificContext(TypedDict):
    customer_name: str
    email: str
    is_demo_organization: bool
    demo_organization_scheduled_deletion_date: Optional[datetime]
    is_self_hosting: bool


class SponsorshipApplicantInfo(TypedDict):
    name: str
    role: str
    email: str


class SponsorshipRequestSessionSpecificContext(TypedDict):
    # We don't store UserProfile for remote realms.
    realm_user: Optional[UserProfile]
    user_info: SponsorshipApplicantInfo
    # TODO: Call this what we end up calling it for /support page.
    realm_string_id: str


class UpgradePageContext(TypedDict):
    customer_name: str
    discount_percent: Optional[str]
    email: str
    exempt_from_license_number_check: bool
    free_trial_end_date: Optional[str]
    is_demo_organization: bool
    manual_license_management: bool
    using_min_licenses_for_plan: bool
    min_licenses_for_plan: int
    page_params: UpgradePageParams
    payment_method: Optional[str]
    plan: str
    fixed_price_plan: bool
    pay_by_invoice_payments_page: Optional[str]
    remote_server_legacy_plan_end_date: Optional[str]
    salt: str
    seat_count: int
    signed_seat_count: str
    success_message: str
    is_sponsorship_pending: bool
    sponsorship_plan_name: str
    scheduled_upgrade_invoice_amount_due: Optional[str]
    is_free_trial_invoice_expired_notice: bool
    free_trial_invoice_expired_notice_page_plan_name: Optional[str]


class SponsorshipRequestForm(forms.Form):
    website = forms.URLField(max_length=ZulipSponsorshipRequest.MAX_ORG_URL_LENGTH, required=False)
    organization_type = forms.IntegerField()
    description = forms.CharField(widget=forms.Textarea)
    expected_total_users = forms.CharField(widget=forms.Textarea)
    paid_users_count = forms.CharField(widget=forms.Textarea)
    paid_users_description = forms.CharField(widget=forms.Textarea, required=False)
    requested_plan = forms.ChoiceField(
        choices=[(plan.value, plan.name) for plan in SponsoredPlanTypes], required=False
    )


class BillingSession(ABC):
    @property
    @abstractmethod
    def billing_entity_display_name(self) -> str:
        pass

    @property
    @abstractmethod
    def billing_session_url(self) -> str:
        pass

    @property
    @abstractmethod
    def billing_base_url(self) -> str:
        pass

    @abstractmethod
    def support_url(self) -> str:
        pass

    @abstractmethod
    def get_customer(self) -> Optional[Customer]:
        pass

    @abstractmethod
    def get_email(self) -> str:
        pass

    @abstractmethod
    def current_count_for_billed_licenses(self, event_time: datetime = timezone_now()) -> int:
        pass

    @abstractmethod
    def get_audit_log_event(self, event_type: AuditLogEventType) -> int:
        pass

    @abstractmethod
    def write_to_audit_log(
        self,
        event_type: AuditLogEventType,
        event_time: datetime,
        *,
        background_update: bool = False,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        pass

    @abstractmethod
    def get_data_for_stripe_customer(self) -> StripeCustomerData:
        pass

    @abstractmethod
    def update_data_for_checkout_session_and_invoice_payment(
        self, metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    def org_name(self) -> str:
        pass

    def customer_plan_exists(self) -> bool:
        # Checks if the realm / server had a plan anytime in the past.
        customer = self.get_customer()

        if customer is not None and CustomerPlan.objects.filter(customer=customer).exists():
            return True

        if isinstance(self, RemoteRealmBillingSession):
            return CustomerPlan.objects.filter(
                customer=get_customer_by_remote_server(self.remote_realm.server)
            ).exists()

        return False

    def get_past_invoices_session_url(self) -> str:
        headline = "List of past invoices"
        customer = self.get_customer()
        assert customer is not None and customer.stripe_customer_id is not None

        # Check if customer has any $0 invoices.
        list_params = stripe.Invoice.ListParams(
            customer=customer.stripe_customer_id,
            limit=1,
            status="paid",
        )
        list_params["total"] = 0  # type: ignore[typeddict-unknown-key]  # Not documented or annotated, but https://github.com/zulip/zulip/pull/28785/files#r1477005528 says it works
        if stripe.Invoice.list(**list_params).data:  # nocoverage
            # These are payment for upgrades which were paid directly by the customer and then we
            # created an invoice for them resulting in `$0` invoices since there was no amount due.
            headline += " ($0 invoices include payment)"

        configuration = stripe.billing_portal.Configuration.create(
            business_profile={
                "headline": headline,
            },
            features={
                "invoice_history": {"enabled": True},
            },
        )

        return stripe.billing_portal.Session.create(
            customer=customer.stripe_customer_id,
            configuration=configuration.id,
            return_url=f"{self.billing_session_url}/billing/",
        ).url

    def get_stripe_customer_portal_url(
        self,
        return_to_billing_page: bool,
        manual_license_management: bool,
        tier: Optional[int] = None,
        setup_payment_by_invoice: bool = False,
    ) -> str:
        customer = self.get_customer()
        if setup_payment_by_invoice and (
            customer is None or customer.stripe_customer_id is None
        ):  # nocoverage
            customer = self.create_stripe_customer()

        assert customer is not None and customer.stripe_customer_id is not None

        if return_to_billing_page:
            return_url = f"{self.billing_session_url}/billing/"
        else:
            assert tier is not None
            base_return_url = f"{self.billing_session_url}/upgrade/"
            params = {
                "manual_license_management": str(manual_license_management).lower(),
                "tier": str(tier),
                "setup_payment_by_invoice": str(setup_payment_by_invoice).lower(),
            }
            return_url = f"{base_return_url}?{urlencode(params)}"

        configuration = stripe.billing_portal.Configuration.create(
            business_profile={
                "headline": "Invoice and receipt billing information",
            },
            features={"customer_update": {"enabled": True, "allowed_updates": ["address", "name"]}},
        )

        return stripe.billing_portal.Session.create(
            customer=customer.stripe_customer_id,
            configuration=configuration.id,
            return_url=return_url,
        ).url

    def generate_invoice_for_upgrade(
        self,
        customer: Customer,
        price_per_license: Optional[int],
        fixed_price: Optional[int],
        licenses: int,
        plan_tier: int,
        billing_schedule: int,
        charge_automatically: bool,
        invoice_period: stripe.InvoiceItem.CreateParamsPeriod,
        license_management: Optional[str] = None,
        days_until_due: Optional[int] = None,
        on_free_trial: bool = False,
        current_plan_id: Optional[int] = None,
    ) -> stripe.Invoice:
        assert customer.stripe_customer_id is not None
        plan_name = CustomerPlan.name_from_tier(plan_tier)
        assert price_per_license is None or fixed_price is None
        price_args: PriceArgs = {}
        if fixed_price is None:
            assert price_per_license is not None
            price_args = {
                "quantity": licenses,
                "unit_amount": price_per_license,
            }
        else:
            assert fixed_price is not None
            amount_due = get_amount_due_fixed_price_plan(fixed_price, billing_schedule)
            price_args = {"amount": amount_due}

        stripe.InvoiceItem.create(
            currency="usd",
            customer=customer.stripe_customer_id,
            description=plan_name,
            discountable=False,
            period=invoice_period,
            **price_args,
        )

        if fixed_price is None and customer.flat_discounted_months > 0:
            num_months = 12 if billing_schedule == CustomerPlan.BILLING_SCHEDULE_ANNUAL else 1
            flat_discounted_months = min(customer.flat_discounted_months, num_months)
            discount = customer.flat_discount * flat_discounted_months
            customer.flat_discounted_months -= flat_discounted_months
            customer.save(update_fields=["flat_discounted_months"])

            stripe.InvoiceItem.create(
                currency="usd",
                customer=customer.stripe_customer_id,
                description=f"${cents_to_dollar_string(customer.flat_discount)}/month new customer discount",
                # Negative value to apply discount.
                amount=(-1 * discount),
                period=invoice_period,
            )

        if charge_automatically:
            collection_method: Literal["charge_automatically" | "send_invoice"] = (
                "charge_automatically"
            )
        else:
            collection_method = "send_invoice"
            # days_until_due is required for `send_invoice` collection method. Since this is an invoice
            # for upgrade, the due date is irrelevant since customer will upgrade once they pay the invoice
            # regardless of the due date. Using `1` shows `Due today / tomorrow` which seems nice.
            if days_until_due is None:
                days_until_due = 1

        metadata = {
            "plan_tier": str(plan_tier),
            "billing_schedule": str(billing_schedule),
            "licenses": str(licenses),
            "license_management": str(license_management),
            "on_free_trial": str(on_free_trial),
            "current_plan_id": str(current_plan_id),
        }

        if hasattr(self, "user"):
            metadata["user_id"] = self.user.id

        # We only need to email customer about open invoice for manual billing.
        # If automatic charge fails, we simply void the invoice.
        # https://stripe.com/docs/invoicing/integration/automatic-advancement-collection
        auto_advance = not charge_automatically
        invoice_params = stripe.Invoice.CreateParams(
            auto_advance=auto_advance,
            collection_method=collection_method,
            customer=customer.stripe_customer_id,
            statement_descriptor=plan_name,
            metadata=metadata,
        )
        if days_until_due is not None:
            invoice_params["days_until_due"] = days_until_due
        stripe_invoice = stripe.Invoice.create(**invoice_params)
        stripe.Invoice.finalize_invoice(stripe_invoice)
        return stripe_invoice

    @abstractmethod
    def update_or_create_customer(
        self, stripe_customer_id: Optional[str] = None, *, defaults: Optional[Dict[str, Any]] = None
    ) -> Customer:
        pass

    @abstractmethod
    def do_change_plan_type(
        self, *, tier: Optional[int], is_sponsored: bool = False, background_update: bool = False
    ) -> None:
        pass

    @abstractmethod
    def process_downgrade(self, plan: CustomerPlan, background_update: bool = False) -> None:
        pass

    @abstractmethod
    def approve_sponsorship(self) -> str:
        pass

    @abstractmethod
    def is_sponsored(self) -> bool:
        pass

    @abstractmethod
    def get_sponsorship_request_session_specific_context(
        self,
    ) -> SponsorshipRequestSessionSpecificContext:
        pass

    @abstractmethod
    def save_org_type_from_request_sponsorship_session(self, org_type: int) -> None:
        pass

    @abstractmethod
    def get_upgrade_page_session_type_specific_context(
        self,
    ) -> UpgradePageSessionTypeSpecificContext:
        pass

    @abstractmethod
    def check_plan_tier_is_billable(self, plan_tier: int) -> bool:
        pass

    @abstractmethod
    def get_type_of_plan_tier_change(
        self, current_plan_tier: int, new_plan_tier: int
    ) -> PlanTierChangeType:
        pass

    @abstractmethod
    def has_billing_access(self) -> bool:
        pass

    @abstractmethod
    def on_paid_plan(self) -> bool:
        pass

    @abstractmethod
    def add_sponsorship_info_to_context(self, context: Dict[str, Any]) -> None:
        pass

    @abstractmethod
    def get_metadata_for_stripe_update_card(self) -> Dict[str, str]:
        pass

    @abstractmethod
    def sync_license_ledger_if_needed(self) -> None:
        # Updates the license ledger based on RemoteRealmAuditLog
        # entries.
        #
        # Supports backfilling entries from weeks if the past if
        # needed when we receive audit logs, making any end-of-cycle
        # updates that happen to be scheduled inside the interval that
        # we are processing.
        #
        # But this support is fragile, in that it does not handle the
        # possibility that some other code path changed or ended the
        # customer's current plan at some point after
        # last_ledger.event_time but before the event times for the
        # audit logs we will be processing.
        pass

    def is_sponsored_or_pending(self, customer: Optional[Customer]) -> bool:
        if (customer is not None and customer.sponsorship_pending) or self.is_sponsored():
            return True
        return False

    def get_remote_server_legacy_plan(
        self, customer: Optional[Customer], status: int = CustomerPlan.ACTIVE
    ) -> Optional[CustomerPlan]:
        # status = CustomerPlan.ACTIVE means that the legacy plan is not scheduled for an upgrade.
        # status = CustomerPlan.SWITCH_PLAN_TIER_AT_PLAN_END means that the legacy plan is scheduled for an upgrade.
        if customer is None:
            return None

        return CustomerPlan.objects.filter(
            customer=customer,
            tier=CustomerPlan.TIER_SELF_HOSTED_LEGACY,
            status=status,
        ).first()

    def get_formatted_remote_server_legacy_plan_end_date(
        self, customer: Optional[Customer], status: int = CustomerPlan.ACTIVE
    ) -> Optional[str]:  # nocoverage
        plan = self.get_remote_server_legacy_plan(customer, status)
        if plan is None:
            return None

        assert plan.end_date is not None
        return plan.end_date.strftime("%B %d, %Y")

    def get_legacy_remote_server_next_plan(self, customer: Customer) -> Optional[CustomerPlan]:
        legacy_plan = self.get_remote_server_legacy_plan(
            customer, CustomerPlan.SWITCH_PLAN_TIER_AT_PLAN_END
        )
        if legacy_plan is None:
            return None

        # This also asserts that such a plan should exist.
        assert legacy_plan.end_date is not None
        return CustomerPlan.objects.get(
            customer=customer,
            billing_cycle_anchor=legacy_plan.end_date,
            status=CustomerPlan.NEVER_STARTED,
        )

    def get_legacy_remote_server_next_plan_name(self, customer: Customer) -> Optional[str]:
        next_plan = self.get_legacy_remote_server_next_plan(customer)
        if next_plan is None:
            return None
        return next_plan.name

    @catch_stripe_errors
    def create_stripe_customer(self) -> Customer:
        stripe_customer_data = self.get_data_for_stripe_customer()
        stripe_customer = stripe.Customer.create(
            description=stripe_customer_data.description,
            email=stripe_customer_data.email,
            metadata=stripe_customer_data.metadata,
        )
        event_time = timestamp_to_datetime(stripe_customer.created)
        with transaction.atomic():
            self.write_to_audit_log(AuditLogEventType.STRIPE_CUSTOMER_CREATED, event_time)
            customer = self.update_or_create_customer(stripe_customer.id)
        return customer

    @catch_stripe_errors
    def replace_payment_method(
        self, stripe_customer_id: str, payment_method: str, pay_invoices: bool = False
    ) -> None:
        stripe.Customer.modify(
            stripe_customer_id, invoice_settings={"default_payment_method": payment_method}
        )
        self.write_to_audit_log(AuditLogEventType.STRIPE_CARD_CHANGED, timezone_now())
        if pay_invoices:
            for stripe_invoice in stripe.Invoice.list(
                collection_method="charge_automatically",
                customer=stripe_customer_id,
                status="open",
            ):
                # The stripe customer with the associated ID will get either a receipt
                # or a "failed payment" email, but the in-app messaging could be clearer
                # here (e.g. it could explicitly tell the user that there were payment(s)
                # and that they succeeded or failed). Worth fixing if we notice that a
                # lot of cards end up failing at this step.
                stripe.Invoice.pay(stripe_invoice)

    # Returns Customer instead of stripe_customer so that we don't make a Stripe
    # API call if there's nothing to update
    @catch_stripe_errors
    def update_or_create_stripe_customer(self, payment_method: Optional[str] = None) -> Customer:
        customer = self.get_customer()
        if customer is None or customer.stripe_customer_id is None:
            # A stripe.PaymentMethod should be attached to a stripe.Customer via replace_payment_method.
            # Here we just want to create a new stripe.Customer.
            assert payment_method is None
            # We could do a better job of handling race conditions here, but if two
            # people try to upgrade at exactly the same time, the main bad thing that
            # will happen is that we will create an extra stripe.Customer that we can
            # delete or ignore.
            return self.create_stripe_customer()
        if payment_method is not None:
            self.replace_payment_method(customer.stripe_customer_id, payment_method, True)
        return customer

    def create_stripe_invoice_and_charge(
        self,
        metadata: Dict[str, Any],
    ) -> str:
        """
        Charge customer based on `billing_modality`. If `billing_modality` is `charge_automatically`,
        charge customer immediately. If the charge fails, the invoice will be voided.
        If `billing_modality` is `send_invoice`, create an invoice and send it to the customer.
        """
        customer = self.get_customer()
        assert customer is not None and customer.stripe_customer_id is not None
        charge_automatically = metadata["billing_modality"] == "charge_automatically"
        # Ensure customers have a default payment method set.
        stripe_customer = stripe_get_customer(customer.stripe_customer_id)
        if charge_automatically and not stripe_customer_has_credit_card_as_default_payment_method(
            stripe_customer
        ):
            raise BillingError(
                "no payment method",
                "Please add a credit card before upgrading.",
            )

        if charge_automatically:
            assert stripe_customer.invoice_settings is not None
            assert stripe_customer.invoice_settings.default_payment_method is not None
        stripe_invoice = None
        try:
            current_plan_id = metadata.get("current_plan_id")
            on_free_trial = bool(metadata.get("on_free_trial"))
            stripe_invoice = self.generate_invoice_for_upgrade(
                customer,
                metadata["price_per_license"],
                metadata["fixed_price"],
                metadata["licenses"],
                metadata["plan_tier"],
                metadata["billing_schedule"],
                charge_automatically=charge_automatically,
                license_management=metadata["license_management"],
                invoice_period=metadata["invoice_period"],
                days_until_due=metadata.get("days_until_due"),
                on_free_trial=on_free_trial,
                current_plan_id=current_plan_id,
            )
            assert stripe_invoice.id is not None

            invoice = Invoice.objects.create(
                stripe_invoice_id=stripe_invoice.id,
                customer=customer,
                status=Invoice.SENT,
                plan_id=current_plan_id,
                is_created_for_free_trial_upgrade=current_plan_id is not None and on_free_trial,
            )

            if charge_automatically:
                # Stripe takes its sweet hour to charge customers after creating an invoice.
                # Since we want to charge customers immediately, we charge them manually.
                # Then poll for the status of the invoice to see if the payment succeeded.
                stripe_invoice = stripe.Invoice.pay(stripe_invoice.id)
        except Exception as e:
            if stripe_invoice is not None:
                assert stripe_invoice.id is not None
                # Void invoice to avoid double charging if customer tries to upgrade again.
                stripe.Invoice.void_invoice(stripe_invoice.id)
                invoice.status = Invoice.VOID
                invoice.save(update_fields=["status"])
            if isinstance(e, stripe.CardError):
                raise StripeCardError("card error", e.user_message)
            else:  # nocoverage
                raise e

        assert stripe_invoice.id is not None
        return stripe_invoice.id

    def create_card_update_session_for_upgrade(
        self,
        manual_license_management: bool,
        tier: int,
    ) -> Dict[str, Any]:
        metadata = self.get_metadata_for_stripe_update_card()
        customer = self.update_or_create_stripe_customer()
        assert customer.stripe_customer_id is not None

        # URL when user cancels the card update session.
        base_cancel_url = f"{self.billing_session_url}/upgrade/"
        params = {
            "manual_license_management": str(manual_license_management).lower(),
            "tier": str(tier),
        }
        cancel_url = f"{base_cancel_url}?{urlencode(params)}"

        stripe_session = stripe.checkout.Session.create(
            cancel_url=cancel_url,
            customer=customer.stripe_customer_id,
            metadata=metadata,
            mode="setup",
            payment_method_types=["card"],
            success_url=f"{self.billing_session_url}/billing/event_status/?stripe_session_id={{CHECKOUT_SESSION_ID}}",
            billing_address_collection="required",
            customer_update={"address": "auto", "name": "auto"},
        )
        Session.objects.create(
            stripe_session_id=stripe_session.id,
            customer=customer,
            type=Session.CARD_UPDATE_FROM_UPGRADE_PAGE,
            is_manual_license_management_upgrade_session=manual_license_management,
            tier=tier,
        )
        return {
            "stripe_session_url": stripe_session.url,
            "stripe_session_id": stripe_session.id,
        }

    def create_card_update_session(self) -> Dict[str, Any]:
        metadata = self.get_metadata_for_stripe_update_card()
        customer = self.get_customer()
        assert customer is not None and customer.stripe_customer_id is not None
        stripe_session = stripe.checkout.Session.create(
            cancel_url=f"{self.billing_session_url}/billing/",
            customer=customer.stripe_customer_id,
            metadata=metadata,
            mode="setup",
            payment_method_types=["card"],
            success_url=f"{self.billing_session_url}/billing/event_status/?stripe_session_id={{CHECKOUT_SESSION_ID}}",
            billing_address_collection="required",
        )
        Session.objects.create(
            stripe_session_id=stripe_session.id,
            customer=customer,
            type=Session.CARD_UPDATE_FROM_BILLING_PAGE,
        )
        return {
            "stripe_session_url": stripe_session.url,
            "stripe_session_id": stripe_session.id,
        }

    def apply_discount_to_plan(
        self,
        plan: CustomerPlan,
        discount: Decimal,
    ) -> None:
        plan.discount = discount
        plan.price_per_license = get_price_per_license(plan.tier, plan.billing_schedule, discount)
        plan.save(update_fields=["discount", "price_per_license"])

    def attach_discount_to_customer(self, new_discount: Decimal) -> str:
        # Remove flat discount if giving customer a percentage discount.
        customer = self.get_customer()

        # We set required plan tier before setting a discount for the customer, so it's always defined.
        assert customer is not None
        assert customer.required_plan_tier is not None

        old_discount = customer.default_discount
        customer.default_discount = new_discount
        customer.flat_discounted_months = 0
        customer.save(update_fields=["default_discount", "flat_discounted_months"])
        plan = get_current_plan_by_customer(customer)
        if plan is not None and plan.tier == customer.required_plan_tier:
            self.apply_discount_to_plan(plan, new_discount)

        # If the customer has a next plan, apply discount to that plan as well.
        # Make this a check on CustomerPlan.SWITCH_PLAN_TIER_AT_PLAN_END status
        # if we support this for other plans.
        next_plan = self.get_legacy_remote_server_next_plan(customer)
        if next_plan is not None and next_plan.tier == customer.required_plan_tier:
            self.apply_discount_to_plan(next_plan, new_discount)

        self.write_to_audit_log(
            event_type=AuditLogEventType.DISCOUNT_CHANGED,
            event_time=timezone_now(),
            extra_data={"old_discount": old_discount, "new_discount": new_discount},
        )
        new_discount_string = (
            format_discount_percentage(new_discount) if (new_discount != Decimal(0)) else "0"
        )
        old_discount_string = (
            format_discount_percentage(old_discount)
            if (old_discount is not None and old_discount != Decimal(0))
            else "0"
        )
        return f"Discount for {self.billing_entity_display_name} changed to {new_discount_string}% from {old_discount_string}%."

    def update_customer_minimum_licenses(self, new_minimum_license_count: int) -> str:
        previous_minimum_license_count = None
        customer = self.get_customer()

        # Currently, the support admin view shows the form for adding
        # a minimum license count after a default discount has been set.
        assert customer is not None
        if customer.default_discount is None or int(customer.default_discount) == 0:
            raise SupportRequestError(
                f"Discount for {self.billing_entity_display_name} must be updated before setting a minimum number of licenses."
            )

        plan = get_current_plan_by_customer(customer)
        if plan is not None and plan.tier != CustomerPlan.TIER_SELF_HOSTED_LEGACY:
            raise SupportRequestError(
                f"Cannot set minimum licenses; active plan already exists for {self.billing_entity_display_name}."
            )

        next_plan = self.get_legacy_remote_server_next_plan(customer)
        if next_plan is not None:
            raise SupportRequestError(
                f"Cannot set minimum licenses; upgrade to new plan already scheduled for {self.billing_entity_display_name}."
            )

        previous_minimum_license_count = customer.minimum_licenses
        customer.minimum_licenses = new_minimum_license_count
        customer.save(update_fields=["minimum_licenses"])

        self.write_to_audit_log(
            event_type=AuditLogEventType.CUSTOMER_PROPERTY_CHANGED,
            event_time=timezone_now(),
            extra_data={
                "old_value": previous_minimum_license_count,
                "new_value": new_minimum_license_count,
                "property": "minimum_licenses",
            },
        )
        if previous_minimum_license_count is None:
            previous_minimum_license_count = 0
        return f"Minimum licenses for {self.billing_entity_display_name} changed to {new_minimum_license_count} from {previous_minimum_license_count}."

    def set_required_plan_tier(self, required_plan_tier: int) -> str:
        previous_required_plan_tier = None
        new_plan_tier = None
        if required_plan_tier != 0:
            new_plan_tier = required_plan_tier
        customer = self.get_customer()

        if new_plan_tier is not None and not self.check_plan_tier_is_billable(required_plan_tier):
            raise SupportRequestError(f"Invalid plan tier for {self.billing_entity_display_name}.")

        if customer is not None:
            if new_plan_tier is None and customer.default_discount:
                raise SupportRequestError(
                    f"Discount for {self.billing_entity_display_name} must be 0 before setting required plan tier to None."
                )
            previous_required_plan_tier = customer.required_plan_tier
            customer.required_plan_tier = new_plan_tier
            customer.save(update_fields=["required_plan_tier"])
        else:
            assert new_plan_tier is not None
            customer = self.update_or_create_customer(
                defaults={"required_plan_tier": new_plan_tier}
            )

        self.write_to_audit_log(
            event_type=AuditLogEventType.CUSTOMER_PROPERTY_CHANGED,
            event_time=timezone_now(),
            extra_data={
                "old_value": previous_required_plan_tier,
                "new_value": new_plan_tier,
                "property": "required_plan_tier",
            },
        )
        plan_tier_name = "None"
        if new_plan_tier is not None:
            plan_tier_name = CustomerPlan.name_from_tier(new_plan_tier)
        return f"Required plan tier for {self.billing_entity_display_name} set to {plan_tier_name}."

    def configure_fixed_price_plan(self, fixed_price: int, sent_invoice_id: Optional[str]) -> str:
        customer = self.get_customer()
        if customer is None:
            customer = self.update_or_create_customer()

        if customer.required_plan_tier is None:
            raise SupportRequestError("Required plan tier should not be set to None")
        required_plan_tier_name = CustomerPlan.name_from_tier(customer.required_plan_tier)

        fixed_price_cents = fixed_price * 100
        fixed_price_plan_params: Dict[str, Any] = {
            "fixed_price": fixed_price_cents,
            "tier": customer.required_plan_tier,
        }

        current_plan = get_current_plan_by_customer(customer)
        if current_plan is not None and self.check_plan_tier_is_billable(current_plan.tier):
            if current_plan.end_date is None:
                raise SupportRequestError(
                    f"Configure {self.billing_entity_display_name} current plan end-date, before scheduling a new plan."
                )
            # Handles the case when the current_plan is a fixed-price plan with
            # a monthly billing schedule. We can't schedule a new plan until the
            # invoice for the 12th month is processed.
            if current_plan.end_date != self.get_next_billing_cycle(current_plan):
                raise SupportRequestError(
                    f"New plan for {self.billing_entity_display_name} can not be scheduled until all the invoices of the current plan are processed."
                )
            fixed_price_plan_params["billing_cycle_anchor"] = current_plan.end_date
            fixed_price_plan_params["end_date"] = add_months(
                current_plan.end_date, CustomerPlan.FIXED_PRICE_PLAN_DURATION_MONTHS
            )
            fixed_price_plan_params["status"] = CustomerPlan.NEVER_STARTED
            fixed_price_plan_params["next_invoice_date"] = current_plan.end_date
            fixed_price_plan_params["invoicing_status"] = (
                CustomerPlan.INVOICING_STATUS_INITIAL_INVOICE_TO_BE_SENT
            )
            fixed_price_plan_params["billing_schedule"] = current_plan.billing_schedule
            fixed_price_plan_params["charge_automatically"] = current_plan.charge_automatically
            # Manual license management is not available for fixed price plan.
            fixed_price_plan_params["automanage_licenses"] = True

            CustomerPlan.objects.create(
                customer=customer,
                **fixed_price_plan_params,
            )
            self.write_to_audit_log(
                event_type=AuditLogEventType.CUSTOMER_PLAN_CREATED,
                event_time=timezone_now(),
                extra_data=fixed_price_plan_params,
            )

            current_plan.status = CustomerPlan.SWITCH_PLAN_TIER_AT_PLAN_END
            current_plan.next_invoice_date = current_plan.end_date
            current_plan.save(update_fields=["status", "next_invoice_date"])
            return f"Fixed price {required_plan_tier_name} plan scheduled to start on {current_plan.end_date.date()}."

        if sent_invoice_id is not None:
            sent_invoice_id = sent_invoice_id.strip()
            # Verify 'sent_invoice_id' before storing in database.
            try:
                invoice = stripe.Invoice.retrieve(sent_invoice_id)
                if invoice.status != "open":
                    raise SupportRequestError(
                        "Invoice status should be open. Please verify sent_invoice_id."
                    )
            except Exception as e:
                raise SupportRequestError(str(e))

            fixed_price_plan_params["sent_invoice_id"] = sent_invoice_id
            Invoice.objects.create(
                customer=customer,
                stripe_invoice_id=sent_invoice_id,
                status=Invoice.SENT,
            )

        fixed_price_plan_params["status"] = CustomerPlanOffer.CONFIGURED
        CustomerPlanOffer.objects.create(
            customer=customer,
            **fixed_price_plan_params,
        )
        self.write_to_audit_log(
            event_type=AuditLogEventType.CUSTOMER_PLAN_CREATED,
            event_time=timezone_now(),
            extra_data=fixed_price_plan_params,
        )
        return f"Customer can now buy a fixed price {required_plan_tier_name} plan."

    def update_customer_sponsorship_status(self, sponsorship_pending: bool) -> str:
        customer = self.get_customer()
        if customer is None:
            customer = self.update_or_create_customer()
        customer.sponsorship_pending = sponsorship_pending
        customer.save(update_fields=["sponsorship_pending"])
        self.write_to_audit_log(
            event_type=AuditLogEventType.SPONSORSHIP_PENDING_STATUS_CHANGED,
            event_time=timezone_now(),
            extra_data={"sponsorship_pending": sponsorship_pending},
        )

        if sponsorship_pending:
            success_message = f"{self.billing_entity_display_name} marked as pending sponsorship."
        else:
            success_message = (
                f"{self.billing_entity_display_name} is no longer pending sponsorship."
            )
        return success_message

    def update_billing_modality_of_current_plan(self, charge_automatically: bool) -> str:
        customer = self.get_customer()
        if customer is not None:
            plan = get_current_plan_by_customer(customer)
            if plan is not None:
                plan.charge_automatically = charge_automatically
                plan.save(update_fields=["charge_automatically"])
                self.write_to_audit_log(
                    event_type=AuditLogEventType.BILLING_MODALITY_CHANGED,
                    event_time=timezone_now(),
                    extra_data={"charge_automatically": charge_automatically},
                )
        if charge_automatically:
            success_message = f"Billing collection method of {self.billing_entity_display_name} updated to charge automatically."
        else:
            success_message = f"Billing collection method of {self.billing_entity_display_name} updated to send invoice."
        return success_message

    def update_end_date_of_current_plan(self, end_date_string: str) -> str:
        new_end_date = datetime.strptime(end_date_string, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        if new_end_date.date() <= timezone_now().date():
            raise SupportRequestError(
                f"Cannot update current plan for {self.billing_entity_display_name} to end on {end_date_string}."
            )
        customer = self.get_customer()
        if customer is not None:
            plan = get_current_plan_by_customer(customer)
            if plan is not None:
                assert plan.status == CustomerPlan.ACTIVE
                old_end_date = plan.end_date
                plan.end_date = new_end_date
                # Legacy plans should be invoiced once on the end_date to
                # downgrade or switch to a new tier.
                next_invoice_date_changed_extra_data = None
                if plan.tier == CustomerPlan.TIER_SELF_HOSTED_LEGACY:
                    next_invoice_date_changed_extra_data = {
                        "old_value": plan.next_invoice_date,
                        "new_value": new_end_date,
                        "property": "next_invoice_date",
                    }
                    plan.next_invoice_date = new_end_date
                # Currently, we send a reminder email 2 months before the end date.
                # Reset it when we are extending the end_date.
                reminder_to_review_plan_email_sent_changed_extra_data = None
                if (
                    plan.reminder_to_review_plan_email_sent
                    and old_end_date is not None  # for mypy
                    and new_end_date > old_end_date
                ):
                    plan.reminder_to_review_plan_email_sent = False
                    reminder_to_review_plan_email_sent_changed_extra_data = {
                        "old_value": True,
                        "new_value": False,
                        "plan_id": plan.id,
                        "property": "reminder_to_review_plan_email_sent",
                    }
                plan.save(
                    update_fields=[
                        "end_date",
                        "next_invoice_date",
                        "reminder_to_review_plan_email_sent",
                    ]
                )

                def write_to_audit_log_plan_property_changed(extra_data: Dict[str, Any]) -> None:
                    extra_data["plan_id"] = plan.id
                    self.write_to_audit_log(
                        event_type=AuditLogEventType.CUSTOMER_PLAN_PROPERTY_CHANGED,
                        event_time=timezone_now(),
                        extra_data=extra_data,
                    )

                end_date_changed_extra_data = {
                    "old_value": old_end_date,
                    "new_value": new_end_date,
                    "property": "end_date",
                }
                write_to_audit_log_plan_property_changed(end_date_changed_extra_data)

                if next_invoice_date_changed_extra_data:
                    write_to_audit_log_plan_property_changed(next_invoice_date_changed_extra_data)

                if reminder_to_review_plan_email_sent_changed_extra_data:
                    write_to_audit_log_plan_property_changed(
                        reminder_to_review_plan_email_sent_changed_extra_data
                    )

                return f"Current plan for {self.billing_entity_display_name} updated to end on {end_date_string}."
        raise SupportRequestError(
            f"No current plan for {self.billing_entity_display_name}."
        )  # nocoverage

    def generate_stripe_invoice(
        self,
        plan_tier: int,
        licenses: int,
        license_management: str,
        billing_schedule: int,
        billing_modality: str,
        on_free_trial: bool = False,
        days_until_due: Optional[int] = None,
        current_plan_id: Optional[int] = None,
    ) -> str:
        customer = self.update_or_create_stripe_customer()
        assert customer is not None  # for mypy
        fixed_price_plan_offer = get_configured_fixed_price_plan_offer(customer, plan_tier)
        general_metadata = {
            "billing_modality": billing_modality,
            "billing_schedule": billing_schedule,
            "licenses": licenses,
            "license_management": license_management,
            "price_per_license": None,
            "fixed_price": None,
            "type": "upgrade",
            "plan_tier": plan_tier,
            "on_free_trial": on_free_trial,
            "days_until_due": days_until_due,
            "current_plan_id": current_plan_id,
        }
        discount_for_plan = customer.get_discount_for_plan_tier(plan_tier)
        (
            invoice_period_start,
            _,
            invoice_period_end,
            price_per_license,
        ) = compute_plan_parameters(
            plan_tier,
            billing_schedule,
            discount_for_plan,
            on_free_trial,
            None,
            not isinstance(self, RealmBillingSession),
        )
        if fixed_price_plan_offer is None:
            general_metadata["price_per_license"] = price_per_license
        else:
            general_metadata["fixed_price"] = fixed_price_plan_offer.fixed_price
            invoice_period_end = add_months(
                invoice_period_start, CustomerPlan.FIXED_PRICE_PLAN_DURATION_MONTHS
            )

        if on_free_trial and billing_modality == "send_invoice":
            # Paid plan starts at the end of free trial.
            invoice_period_start = invoice_period_end
            purchased_months = 1
            if billing_schedule == CustomerPlan.BILLING_SCHEDULE_ANNUAL:
                purchased_months = 12
            invoice_period_end = add_months(invoice_period_end, purchased_months)

        general_metadata["invoice_period"] = {
            "start": datetime_to_timestamp(invoice_period_start),
            "end": datetime_to_timestamp(invoice_period_end),
        }
        updated_metadata = self.update_data_for_checkout_session_and_invoice_payment(
            general_metadata
        )
        return self.create_stripe_invoice_and_charge(updated_metadata)

    def ensure_current_plan_is_upgradable(self, customer: Customer, new_plan_tier: int) -> None:
        # Upgrade for customers with an existing plan is only supported for remote realm / server right now.
        if isinstance(self, RealmBillingSession):
            ensure_customer_does_not_have_active_plan(customer)
            return

        plan = get_current_plan_by_customer(customer)
        # Customers without a plan can always upgrade.
        if plan is None:
            return

        type_of_plan_change = self.get_type_of_plan_tier_change(plan.tier, new_plan_tier)
        if type_of_plan_change != PlanTierChangeType.UPGRADE:  # nocoverage
            raise InvalidPlanUpgradeError(
                f"Cannot upgrade from {plan.name} to {CustomerPlan.name_from_tier(new_plan_tier)}"
            )

    def check_customer_not_on_paid_plan(self, customer: Customer) -> str:
        current_plan = get_current_plan_by_customer(customer)
        if current_plan is not None:
            # Check if the customer is scheduled for an upgrade.
            next_plan = self.get_next_plan(current_plan)
            if next_plan is not None:  # nocoverage
                return f"Customer scheduled for upgrade to {next_plan.name}. Please cancel upgrade before approving sponsorship!"

            # It is fine to end legacy plan not scheduled for an upgrade.
            if current_plan.tier != CustomerPlan.TIER_SELF_HOSTED_LEGACY:
                return f"Customer on plan {current_plan.name}. Please end current plan before approving sponsorship!"

        return ""

    @catch_stripe_errors
    def process_initial_upgrade(
        self,
        plan_tier: int,
        licenses: int,
        automanage_licenses: bool,
        billing_schedule: int,
        charge_automatically: bool,
        free_trial: bool,
        remote_server_legacy_plan: Optional[CustomerPlan] = None,
        should_schedule_upgrade_for_legacy_remote_server: bool = False,
        stripe_invoice_paid: bool = False,
    ) -> None:
        is_self_hosted_billing = not isinstance(self, RealmBillingSession)
        if stripe_invoice_paid:
            customer = self.update_or_create_customer()
        else:
            customer = self.update_or_create_stripe_customer()
        self.ensure_current_plan_is_upgradable(customer, plan_tier)
        billing_cycle_anchor = None

        if remote_server_legacy_plan is not None:
            # Legacy servers don't get an additional free trial.
            free_trial = False
        if should_schedule_upgrade_for_legacy_remote_server:
            assert remote_server_legacy_plan is not None
            billing_cycle_anchor = remote_server_legacy_plan.end_date

        discount_for_plan = None
        fixed_price_plan_offer = get_configured_fixed_price_plan_offer(customer, plan_tier)
        if fixed_price_plan_offer is None:
            discount_for_plan = customer.get_discount_for_plan_tier(plan_tier)
        else:
            assert automanage_licenses is True

        (
            billing_cycle_anchor,
            next_invoice_date,
            period_end,
            price_per_license,
        ) = compute_plan_parameters(
            plan_tier,
            billing_schedule,
            discount_for_plan,
            free_trial,
            billing_cycle_anchor,
            is_self_hosted_billing,
            should_schedule_upgrade_for_legacy_remote_server,
        )

        # TODO: The correctness of this relies on user creation, deactivation, etc being
        # in a transaction.atomic() with the relevant RealmAuditLog entries
        with transaction.atomic():
            # billed_licenses can be greater than licenses if users are added between the start of
            # this function (process_initial_upgrade) and now
            current_licenses_count = self.get_billable_licenses_for_customer(
                customer, plan_tier, licenses
            )
            # In case user wants more licenses for the plan. (manual license management)
            billed_licenses = max(current_licenses_count, licenses)
            plan_params = {
                "automanage_licenses": automanage_licenses,
                "charge_automatically": charge_automatically,
                "billing_cycle_anchor": billing_cycle_anchor,
                "billing_schedule": billing_schedule,
                "tier": plan_tier,
            }

            if fixed_price_plan_offer is None:
                plan_params["price_per_license"] = price_per_license
                plan_params["discount"] = discount_for_plan

            if free_trial:
                plan_params["status"] = CustomerPlan.FREE_TRIAL

                if charge_automatically:
                    # Ensure free trial customers not paying via invoice have a default payment method set
                    assert customer.stripe_customer_id is not None  # for mypy
                    stripe_customer = stripe_get_customer(customer.stripe_customer_id)
                    if not stripe_customer_has_credit_card_as_default_payment_method(
                        stripe_customer
                    ):
                        raise BillingError(
                            "no payment method",
                            _("Please add a credit card before starting your free trial."),
                        )

            event_time = billing_cycle_anchor
            if should_schedule_upgrade_for_legacy_remote_server:
                # In this code path, we are currently on a legacy plan
                # and are scheduling an upgrade to a non-legacy plan
                # that should occur when the legacy plan expires.
                #
                # We will create a new NEVER_STARTED plan for the
                # customer, scheduled to start when the current one
                # expires.
                assert remote_server_legacy_plan is not None
                if charge_automatically:
                    # Ensure customers not paying via invoice have a default payment method set.
                    assert customer.stripe_customer_id is not None  # for mypy
                    stripe_customer = stripe_get_customer(customer.stripe_customer_id)
                    if not stripe_customer_has_credit_card_as_default_payment_method(
                        stripe_customer
                    ):  # nocoverage
                        raise BillingError(
                            "no payment method",
                            _("Please add a credit card to schedule upgrade."),
                        )

                # Settings status > CustomerPLan.LIVE_STATUS_THRESHOLD makes sure we don't have
                # to worry about this plan being used for any other purpose.
                # NOTE: This is the 2nd plan for the customer.
                plan_params["status"] = CustomerPlan.NEVER_STARTED
                plan_params["invoicing_status"] = (
                    CustomerPlan.INVOICING_STATUS_INITIAL_INVOICE_TO_BE_SENT
                )
                event_time = timezone_now().replace(microsecond=0)

                # Schedule switching to the new plan at plan end date.
                assert remote_server_legacy_plan.end_date == billing_cycle_anchor
                last_ledger_entry = (
                    LicenseLedger.objects.filter(plan=remote_server_legacy_plan)
                    .order_by("-id")
                    .first()
                )
                # Update license_at_next_renewal as per new plan.
                assert last_ledger_entry is not None
                last_ledger_entry.licenses_at_next_renewal = billed_licenses
                last_ledger_entry.save(update_fields=["licenses_at_next_renewal"])
                remote_server_legacy_plan.status = CustomerPlan.SWITCH_PLAN_TIER_AT_PLAN_END
                remote_server_legacy_plan.save(update_fields=["status"])
            elif remote_server_legacy_plan is not None:  # nocoverage
                remote_server_legacy_plan.status = CustomerPlan.ENDED
                remote_server_legacy_plan.save(update_fields=["status"])

            if fixed_price_plan_offer is not None:
                # Manual license management is not available for fixed price plan.
                assert automanage_licenses is True
                plan_params["fixed_price"] = fixed_price_plan_offer.fixed_price
                period_end = add_months(
                    billing_cycle_anchor, CustomerPlan.FIXED_PRICE_PLAN_DURATION_MONTHS
                )
                plan_params["end_date"] = period_end
                fixed_price_plan_offer.status = CustomerPlanOffer.PROCESSED
                fixed_price_plan_offer.save(update_fields=["status"])

            plan = CustomerPlan.objects.create(
                customer=customer, next_invoice_date=next_invoice_date, **plan_params
            )

            self.write_to_audit_log(
                event_type=AuditLogEventType.CUSTOMER_PLAN_CREATED,
                event_time=event_time,
                extra_data=plan_params,
            )

            if plan.status < CustomerPlan.LIVE_STATUS_THRESHOLD:
                # Tier and usage limit change will happen when plan becomes live.
                self.do_change_plan_type(tier=plan_tier)

                # LicenseLedger entries are way for us to charge customer and track their license usage.
                # So, we should only create these entries for live plans.
                ledger_entry = LicenseLedger.objects.create(
                    plan=plan,
                    is_renewal=True,
                    event_time=event_time,
                    licenses=licenses,
                    licenses_at_next_renewal=licenses,
                )
                plan.invoiced_through = ledger_entry
                plan.save(update_fields=["invoiced_through"])

                # TODO: Do a check for max licenses for fixed price plans here after we add that.
                if (
                    stripe_invoice_paid
                    and billed_licenses != licenses
                    and not customer.exempt_from_license_number_check
                    and not fixed_price_plan_offer
                ):
                    # Customer paid for less licenses than they have.
                    # We need to create a new ledger entry to track the additional licenses.
                    LicenseLedger.objects.create(
                        plan=plan,
                        is_renewal=False,
                        event_time=event_time,
                        licenses=billed_licenses,
                        licenses_at_next_renewal=billed_licenses,
                    )
                    # Creates due today invoice for additional licenses.
                    self.invoice_plan(plan, event_time)

        if not stripe_invoice_paid and not (
            free_trial or should_schedule_upgrade_for_legacy_remote_server
        ):
            # We don't actually expect to ever reach here but this is just a safety net
            # in case any future changes make this possible.
            assert plan is not None
            self.generate_invoice_for_upgrade(
                customer,
                price_per_license=price_per_license,
                fixed_price=plan.fixed_price,
                licenses=billed_licenses,
                plan_tier=plan.tier,
                billing_schedule=billing_schedule,
                charge_automatically=False,
                invoice_period={
                    "start": datetime_to_timestamp(billing_cycle_anchor),
                    "end": datetime_to_timestamp(period_end),
                },
            )
        elif free_trial and not charge_automatically:
            assert stripe_invoice_paid is False
            assert plan is not None
            assert plan.next_invoice_date is not None
            # Send an invoice to the customer which expires at the end of free trial. If the customer
            # fails to pay the invoice before expiration, we downgrade the customer.
            self.generate_stripe_invoice(
                plan_tier,
                licenses=billed_licenses,
                license_management="automatic" if automanage_licenses else "manual",
                billing_schedule=billing_schedule,
                billing_modality="send_invoice",
                on_free_trial=True,
                days_until_due=(plan.next_invoice_date - event_time).days,
                current_plan_id=plan.id,
            )

    def do_upgrade(self, upgrade_request: UpgradeRequest) -> Dict[str, Any]:
        customer = self.get_customer()
        if customer is not None:
            self.ensure_current_plan_is_upgradable(customer, upgrade_request.tier)
        billing_modality = upgrade_request.billing_modality
        schedule = upgrade_request.schedule
        license_management = upgrade_request.license_management
        licenses = upgrade_request.licenses

        seat_count = unsign_seat_count(upgrade_request.signed_seat_count, upgrade_request.salt)
        if billing_modality == "charge_automatically" and license_management == "automatic":
            licenses = seat_count
        if billing_modality == "send_invoice":
            license_management = "manual"

        exempt_from_license_number_check = (
            customer is not None and customer.exempt_from_license_number_check
        )
        check_upgrade_parameters(
            billing_modality,
            schedule,
            license_management,
            licenses,
            seat_count,
            exempt_from_license_number_check,
            self.min_licenses_for_plan(upgrade_request.tier),
        )
        assert licenses is not None and license_management is not None
        automanage_licenses = license_management == "automatic"
        charge_automatically = billing_modality == "charge_automatically"

        billing_schedule = {
            "annual": CustomerPlan.BILLING_SCHEDULE_ANNUAL,
            "monthly": CustomerPlan.BILLING_SCHEDULE_MONTHLY,
        }[schedule]
        data: Dict[str, Any] = {}

        is_self_hosted_billing = not isinstance(self, RealmBillingSession)
        free_trial = is_free_trial_offer_enabled(is_self_hosted_billing, upgrade_request.tier)
        if customer is not None:
            fixed_price_plan_offer = get_configured_fixed_price_plan_offer(
                customer, upgrade_request.tier
            )
            if fixed_price_plan_offer is not None:
                free_trial = False

        if self.customer_plan_exists():
            # Free trial is not available for existing customers.
            free_trial = False

        remote_server_legacy_plan = self.get_remote_server_legacy_plan(customer)
        should_schedule_upgrade_for_legacy_remote_server = (
            remote_server_legacy_plan is not None
            and upgrade_request.remote_server_plan_start_date == "billing_cycle_end_date"
        )
        # Directly upgrade free trial orgs or invoice payment orgs to standard plan.
        if should_schedule_upgrade_for_legacy_remote_server or free_trial:
            self.process_initial_upgrade(
                upgrade_request.tier,
                licenses,
                automanage_licenses,
                billing_schedule,
                charge_automatically,
                free_trial,
                remote_server_legacy_plan,
                should_schedule_upgrade_for_legacy_remote_server,
            )
            data["organization_upgrade_successful"] = True
        else:
            stripe_invoice_id = self.generate_stripe_invoice(
                upgrade_request.tier,
                licenses,
                license_management,
                billing_schedule,
                billing_modality,
            )
            data["stripe_invoice_id"] = stripe_invoice_id
        return data

    def do_change_schedule_after_free_trial(self, plan: CustomerPlan, schedule: int) -> None:
        # NOTE: Schedule change for free trial with invoice payments is not supported due to complication
        # involving sending another invoice and handling payment difference if customer already paid.
        assert plan.charge_automatically
        # Change the billing frequency of the plan after the free trial ends.
        assert schedule in (
            CustomerPlan.BILLING_SCHEDULE_MONTHLY,
            CustomerPlan.BILLING_SCHEDULE_ANNUAL,
        )
        last_ledger_entry = LicenseLedger.objects.filter(plan=plan).order_by("-id").first()
        assert last_ledger_entry is not None
        licenses_at_next_renewal = last_ledger_entry.licenses_at_next_renewal
        assert licenses_at_next_renewal is not None
        assert plan.next_invoice_date is not None
        next_billing_cycle = plan.next_invoice_date

        if plan.fixed_price is not None:  # nocoverage
            raise BillingError("Customer is already on monthly fixed plan.")

        plan.status = CustomerPlan.ENDED
        plan.next_invoice_date = None
        plan.save(update_fields=["status", "next_invoice_date"])

        discount_for_current_plan = plan.discount
        _, _, _, price_per_license = compute_plan_parameters(
            tier=plan.tier,
            billing_schedule=schedule,
            discount=discount_for_current_plan,
        )

        new_plan = CustomerPlan.objects.create(
            customer=plan.customer,
            billing_schedule=schedule,
            automanage_licenses=plan.automanage_licenses,
            charge_automatically=plan.charge_automatically,
            price_per_license=price_per_license,
            discount=discount_for_current_plan,
            billing_cycle_anchor=plan.billing_cycle_anchor,
            tier=plan.tier,
            status=CustomerPlan.FREE_TRIAL,
            next_invoice_date=next_billing_cycle,
        )

        ledger_entry = LicenseLedger.objects.create(
            plan=new_plan,
            is_renewal=True,
            event_time=plan.billing_cycle_anchor,
            licenses=licenses_at_next_renewal,
            licenses_at_next_renewal=licenses_at_next_renewal,
        )

        new_plan.invoiced_through = ledger_entry
        new_plan.save(update_fields=["invoiced_through"])

        if schedule == CustomerPlan.BILLING_SCHEDULE_ANNUAL:
            self.write_to_audit_log(
                event_type=AuditLogEventType.CUSTOMER_SWITCHED_FROM_MONTHLY_TO_ANNUAL_PLAN,
                event_time=timezone_now(),
                extra_data={
                    "monthly_plan_id": plan.id,
                    "annual_plan_id": new_plan.id,
                },
            )
        else:
            self.write_to_audit_log(
                event_type=AuditLogEventType.CUSTOMER_SWITCHED_FROM_ANNUAL_TO_MONTHLY_PLAN,
                event_time=timezone_now(),
                extra_data={
                    "annual_plan_id": plan.id,
                    "monthly_plan_id": new_plan.id,
                },
            )

    def get_next_billing_cycle(self, plan: CustomerPlan) -> datetime:
        if plan.status in (
            CustomerPlan.FREE_TRIAL,
            CustomerPlan.DOWNGRADE_AT_END_OF_FREE_TRIAL,
            CustomerPlan.NEVER_STARTED,
        ):
            assert plan.next_invoice_date is not None
            next_billing_cycle = plan.next_invoice_date
        elif plan.status == CustomerPlan.SWITCH_PLAN_TIER_AT_PLAN_END:
            assert plan.end_date is not None
            next_billing_cycle = plan.end_date
        else:
            last_ledger_renewal = (
                LicenseLedger.objects.filter(plan=plan, is_renewal=True).order_by("-id").first()
            )
            assert last_ledger_renewal is not None
            last_renewal = last_ledger_renewal.event_time
            next_billing_cycle = start_of_next_billing_cycle(plan, last_renewal)

        if plan.end_date is not None:
            next_billing_cycle = min(next_billing_cycle, plan.end_date)

        return next_billing_cycle

    # event_time should roughly be timezone_now(). Not designed to handle
    # event_times in the past or future
    @transaction.atomic
    def make_end_of_cycle_updates_if_needed(
        self, plan: CustomerPlan, event_time: datetime
    ) -> Tuple[Optional[CustomerPlan], Optional[LicenseLedger]]:
        last_ledger_entry = (
            LicenseLedger.objects.filter(plan=plan, event_time__lte=event_time)
            .order_by("-id")
            .first()
        )
        next_billing_cycle = self.get_next_billing_cycle(plan)
        event_in_next_billing_cycle = next_billing_cycle <= event_time

        if event_in_next_billing_cycle and last_ledger_entry is not None:
            licenses_at_next_renewal = last_ledger_entry.licenses_at_next_renewal
            assert licenses_at_next_renewal is not None

            if plan.end_date == next_billing_cycle and plan.status == CustomerPlan.ACTIVE:
                self.process_downgrade(plan, True)
                return None, None

            if plan.status == CustomerPlan.ACTIVE:
                return None, LicenseLedger.objects.create(
                    plan=plan,
                    is_renewal=True,
                    event_time=next_billing_cycle,
                    licenses=licenses_at_next_renewal,
                    licenses_at_next_renewal=licenses_at_next_renewal,
                )
            if plan.is_free_trial():
                is_renewal = True
                # Check if user has already paid for the plan by invoice.
                if not plan.charge_automatically:
                    last_sent_invoice = Invoice.objects.filter(plan=plan).order_by("-id").first()
                    if last_sent_invoice and last_sent_invoice.status == Invoice.PAID:
                        # This will create invoice for any additional licenses that user has at the time of
                        # switching from free trial to paid plan since they already paid for the plan's this billing cycle.
                        is_renewal = False
                    else:
                        # We end the free trial since customer hasn't paid.
                        plan.status = CustomerPlan.DOWNGRADE_AT_END_OF_FREE_TRIAL
                        plan.save(update_fields=["status"])
                        self.make_end_of_cycle_updates_if_needed(plan, event_time)
                        return None, None

                plan.invoiced_through = last_ledger_entry
                plan.billing_cycle_anchor = next_billing_cycle.replace(microsecond=0)
                plan.status = CustomerPlan.ACTIVE
                plan.save(update_fields=["invoiced_through", "billing_cycle_anchor", "status"])
                return None, LicenseLedger.objects.create(
                    plan=plan,
                    is_renewal=is_renewal,
                    event_time=next_billing_cycle,
                    licenses=licenses_at_next_renewal,
                    licenses_at_next_renewal=licenses_at_next_renewal,
                )

            if plan.status == CustomerPlan.SWITCH_PLAN_TIER_AT_PLAN_END:  # nocoverage
                plan.status = CustomerPlan.ENDED
                plan.save(update_fields=["status"])

                assert plan.end_date is not None
                new_plan = CustomerPlan.objects.get(
                    customer=plan.customer,
                    billing_cycle_anchor=plan.end_date,
                    status=CustomerPlan.NEVER_STARTED,
                )
                new_plan.status = CustomerPlan.ACTIVE
                new_plan.save(update_fields=["status"])
                self.do_change_plan_type(tier=new_plan.tier, background_update=True)
                return None, LicenseLedger.objects.create(
                    plan=new_plan,
                    is_renewal=True,
                    event_time=next_billing_cycle,
                    licenses=licenses_at_next_renewal,
                    licenses_at_next_renewal=licenses_at_next_renewal,
                )

            if plan.status == CustomerPlan.SWITCH_TO_ANNUAL_AT_END_OF_CYCLE:
                if plan.fixed_price is not None:  # nocoverage
                    raise NotImplementedError("Can't switch fixed priced monthly plan to annual.")

                plan.status = CustomerPlan.ENDED
                plan.save(update_fields=["status"])

                discount_for_current_plan = plan.discount
                _, _, _, price_per_license = compute_plan_parameters(
                    tier=plan.tier,
                    billing_schedule=CustomerPlan.BILLING_SCHEDULE_ANNUAL,
                    discount=discount_for_current_plan,
                )

                new_plan = CustomerPlan.objects.create(
                    customer=plan.customer,
                    billing_schedule=CustomerPlan.BILLING_SCHEDULE_ANNUAL,
                    automanage_licenses=plan.automanage_licenses,
                    charge_automatically=plan.charge_automatically,
                    price_per_license=price_per_license,
                    discount=discount_for_current_plan,
                    billing_cycle_anchor=next_billing_cycle,
                    tier=plan.tier,
                    status=CustomerPlan.ACTIVE,
                    next_invoice_date=next_billing_cycle,
                    invoiced_through=None,
                    invoicing_status=CustomerPlan.INVOICING_STATUS_INITIAL_INVOICE_TO_BE_SENT,
                )

                new_plan_ledger_entry = LicenseLedger.objects.create(
                    plan=new_plan,
                    is_renewal=True,
                    event_time=next_billing_cycle,
                    licenses=licenses_at_next_renewal,
                    licenses_at_next_renewal=licenses_at_next_renewal,
                )

                self.write_to_audit_log(
                    event_type=AuditLogEventType.CUSTOMER_SWITCHED_FROM_MONTHLY_TO_ANNUAL_PLAN,
                    event_time=event_time,
                    extra_data={
                        "monthly_plan_id": plan.id,
                        "annual_plan_id": new_plan.id,
                    },
                    background_update=True,
                )
                return new_plan, new_plan_ledger_entry

            if plan.status == CustomerPlan.SWITCH_TO_MONTHLY_AT_END_OF_CYCLE:
                if plan.fixed_price is not None:  # nocoverage
                    raise BillingError("Customer is already on monthly fixed plan.")

                plan.status = CustomerPlan.ENDED
                plan.save(update_fields=["status"])

                discount_for_current_plan = plan.discount
                _, _, _, price_per_license = compute_plan_parameters(
                    tier=plan.tier,
                    billing_schedule=CustomerPlan.BILLING_SCHEDULE_MONTHLY,
                    discount=discount_for_current_plan,
                )

                new_plan = CustomerPlan.objects.create(
                    customer=plan.customer,
                    billing_schedule=CustomerPlan.BILLING_SCHEDULE_MONTHLY,
                    automanage_licenses=plan.automanage_licenses,
                    charge_automatically=plan.charge_automatically,
                    price_per_license=price_per_license,
                    discount=discount_for_current_plan,
                    billing_cycle_anchor=next_billing_cycle,
                    tier=plan.tier,
                    status=CustomerPlan.ACTIVE,
                    next_invoice_date=next_billing_cycle,
                    invoiced_through=None,
                    invoicing_status=CustomerPlan.INVOICING_STATUS_INITIAL_INVOICE_TO_BE_SENT,
                )

                new_plan_ledger_entry = LicenseLedger.objects.create(
                    plan=new_plan,
                    is_renewal=True,
                    event_time=next_billing_cycle,
                    licenses=licenses_at_next_renewal,
                    licenses_at_next_renewal=licenses_at_next_renewal,
                )

                self.write_to_audit_log(
                    event_type=AuditLogEventType.CUSTOMER_SWITCHED_FROM_ANNUAL_TO_MONTHLY_PLAN,
                    event_time=event_time,
                    extra_data={
                        "annual_plan_id": plan.id,
                        "monthly_plan_id": new_plan.id,
                    },
                    background_update=True,
                )
                return new_plan, new_plan_ledger_entry

            if plan.status == CustomerPlan.DOWNGRADE_AT_END_OF_FREE_TRIAL:
                self.downgrade_now_without_creating_additional_invoices(
                    plan, background_update=True
                )

            if plan.status == CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE:
                self.process_downgrade(plan, background_update=True)

            return None, None
        return None, last_ledger_entry

    def get_next_plan(self, plan: CustomerPlan) -> Optional[CustomerPlan]:
        if plan.status == CustomerPlan.SWITCH_PLAN_TIER_AT_PLAN_END:
            assert plan.end_date is not None
            return CustomerPlan.objects.filter(
                customer=plan.customer,
                billing_cycle_anchor=plan.end_date,
                status=CustomerPlan.NEVER_STARTED,
            ).first()
        return None

    def get_customer_plan_renewal_amount(
        self,
        plan: CustomerPlan,
        last_ledger_entry: LicenseLedger,
    ) -> int:
        if plan.fixed_price is not None:
            if plan.end_date == self.get_next_billing_cycle(plan):
                return 0
            return get_amount_due_fixed_price_plan(plan.fixed_price, plan.billing_schedule)
        if last_ledger_entry.licenses_at_next_renewal is None:
            return 0  # nocoverage
        assert plan.price_per_license is not None  # for mypy
        return plan.price_per_license * last_ledger_entry.licenses_at_next_renewal

    def get_billing_context_from_plan(
        self,
        customer: Customer,
        plan: CustomerPlan,
        last_ledger_entry: LicenseLedger,
        now: datetime,
    ) -> Dict[str, Any]:
        is_self_hosted_billing = not isinstance(self, RealmBillingSession)
        downgrade_at_end_of_cycle = plan.status == CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE
        downgrade_at_end_of_free_trial = plan.status == CustomerPlan.DOWNGRADE_AT_END_OF_FREE_TRIAL
        switch_to_annual_at_end_of_cycle = (
            plan.status == CustomerPlan.SWITCH_TO_ANNUAL_AT_END_OF_CYCLE
        )
        switch_to_monthly_at_end_of_cycle = (
            plan.status == CustomerPlan.SWITCH_TO_MONTHLY_AT_END_OF_CYCLE
        )
        licenses = last_ledger_entry.licenses
        licenses_at_next_renewal = last_ledger_entry.licenses_at_next_renewal
        assert licenses_at_next_renewal is not None
        min_licenses_for_plan = self.min_licenses_for_plan(plan.tier)
        seat_count = self.current_count_for_billed_licenses()
        using_min_licenses_for_plan = (
            min_licenses_for_plan == licenses_at_next_renewal
            and licenses_at_next_renewal > seat_count
        )

        # Should do this in JavaScript, using the user's time zone
        if plan.is_free_trial() or downgrade_at_end_of_free_trial:
            assert plan.next_invoice_date is not None
            renewal_date = f"{plan.next_invoice_date:%B} {plan.next_invoice_date.day}, {plan.next_invoice_date.year}"
        else:
            renewal_date = "{dt:%B} {dt.day}, {dt.year}".format(
                dt=start_of_next_billing_cycle(plan, now)
            )

        has_paid_invoice_for_free_trial = False
        free_trial_next_renewal_date_after_invoice_paid = None
        if plan.is_free_trial() and not plan.charge_automatically:
            last_sent_invoice = Invoice.objects.filter(plan=plan).order_by("-id").first()
            # If the customer doesn't have any invoice, this likely means a bug and customer needs to be handled manually.
            assert last_sent_invoice is not None
            has_paid_invoice_for_free_trial = last_sent_invoice.status == Invoice.PAID

            if has_paid_invoice_for_free_trial:
                assert plan.next_invoice_date is not None
                free_trial_days = get_free_trial_days(is_self_hosted_billing, plan.tier)
                assert free_trial_days is not None
                free_trial_next_renewal_date_after_invoice_paid = (
                    "{dt:%B} {dt.day}, {dt.year}".format(
                        dt=(
                            start_of_next_billing_cycle(plan, plan.next_invoice_date)
                            + timedelta(days=free_trial_days)
                        )
                    )
                )

        billing_frequency = CustomerPlan.BILLING_SCHEDULES[plan.billing_schedule]
        discount_for_current_plan = plan.discount

        if switch_to_annual_at_end_of_cycle:
            num_months_next_cycle = 12
            annual_price_per_license = get_price_per_license(
                plan.tier, CustomerPlan.BILLING_SCHEDULE_ANNUAL, discount_for_current_plan
            )
            renewal_cents = annual_price_per_license * licenses_at_next_renewal
            price_per_license = format_money(annual_price_per_license / 12)
        elif switch_to_monthly_at_end_of_cycle:
            num_months_next_cycle = 1
            monthly_price_per_license = get_price_per_license(
                plan.tier, CustomerPlan.BILLING_SCHEDULE_MONTHLY, discount_for_current_plan
            )
            renewal_cents = monthly_price_per_license * licenses_at_next_renewal
            price_per_license = format_money(monthly_price_per_license)
        else:
            num_months_next_cycle = (
                12 if plan.billing_schedule == CustomerPlan.BILLING_SCHEDULE_ANNUAL else 1
            )
            renewal_cents = self.get_customer_plan_renewal_amount(plan, last_ledger_entry)

            if plan.price_per_license is None:
                price_per_license = ""
            elif billing_frequency == "Annual":
                price_per_license = format_money(plan.price_per_license / 12)
            else:
                price_per_license = format_money(plan.price_per_license)

        pre_discount_renewal_cents = renewal_cents
        flat_discount, flat_discounted_months = self.get_flat_discount_info(plan.customer)
        if plan.fixed_price is None and flat_discounted_months > 0:
            flat_discounted_months = min(flat_discounted_months, num_months_next_cycle)
            discount = flat_discount * flat_discounted_months
            renewal_cents = renewal_cents - discount

        charge_automatically = plan.charge_automatically
        if customer.stripe_customer_id is not None:
            stripe_customer = stripe_get_customer(customer.stripe_customer_id)
            stripe_email = stripe_customer.email
            if charge_automatically:
                payment_method = payment_method_string(stripe_customer)
            else:
                payment_method = "Invoice"
        elif settings.DEVELOPMENT:  # nocoverage
            # Allow access to billing page in development environment without a stripe_customer_id.
            payment_method = "Payment method not populated"
            stripe_email = "not_populated@zulip.com"
        else:  # nocoverage
            raise BillingError(f"stripe_customer_id is None for {customer}")

        remote_server_legacy_plan_end_date = self.get_formatted_remote_server_legacy_plan_end_date(
            customer, status=CustomerPlan.SWITCH_PLAN_TIER_AT_PLAN_END
        )
        legacy_remote_server_next_plan_name = self.get_legacy_remote_server_next_plan_name(customer)
        context = {
            "plan_name": plan.name,
            "has_active_plan": True,
            "free_trial": plan.is_free_trial(),
            "downgrade_at_end_of_cycle": downgrade_at_end_of_cycle,
            "downgrade_at_end_of_free_trial": downgrade_at_end_of_free_trial,
            "automanage_licenses": plan.automanage_licenses,
            "switch_to_annual_at_end_of_cycle": switch_to_annual_at_end_of_cycle,
            "switch_to_monthly_at_end_of_cycle": switch_to_monthly_at_end_of_cycle,
            "licenses": licenses,
            "licenses_at_next_renewal": licenses_at_next_renewal,
            "seat_count": seat_count,
            "renewal_date": renewal_date,
            "renewal_amount": cents_to_dollar_string(renewal_cents) if renewal_cents != 0 else None,
            "payment_method": payment_method,
            "charge_automatically": charge_automatically,
            "stripe_email": stripe_email,
            "CustomerPlan": CustomerPlan,
            "billing_frequency": billing_frequency,
            "fixed_price_plan": plan.fixed_price is not None,
            "price_per_license": price_per_license,
            "is_sponsorship_pending": customer.sponsorship_pending,
            "sponsorship_plan_name": self.get_sponsorship_plan_name(
                customer, is_self_hosted_billing
            ),
            "discount_percent": format_discount_percentage(discount_for_current_plan),
            "is_self_hosted_billing": is_self_hosted_billing,
            "is_server_on_legacy_plan": remote_server_legacy_plan_end_date is not None,
            "remote_server_legacy_plan_end_date": remote_server_legacy_plan_end_date,
            "legacy_remote_server_next_plan_name": legacy_remote_server_next_plan_name,
            "using_min_licenses_for_plan": using_min_licenses_for_plan,
            "min_licenses_for_plan": min_licenses_for_plan,
            "pre_discount_renewal_cents": cents_to_dollar_string(pre_discount_renewal_cents),
            "flat_discount": format_money(customer.flat_discount),
            "discounted_months_left": customer.flat_discounted_months,
            "has_paid_invoice_for_free_trial": has_paid_invoice_for_free_trial,
            "free_trial_next_renewal_date_after_invoice_paid": free_trial_next_renewal_date_after_invoice_paid,
        }
        return context

    def get_billing_page_context(self) -> Dict[str, Any]:
        now = timezone_now()

        customer = self.get_customer()
        assert customer is not None

        plan = get_current_plan_by_customer(customer)
        assert plan is not None

        new_plan, last_ledger_entry = self.make_end_of_cycle_updates_if_needed(plan, now)
        if last_ledger_entry is None:
            return {"current_plan_downgraded": True}
        plan = new_plan if new_plan is not None else plan

        context = self.get_billing_context_from_plan(customer, plan, last_ledger_entry, now)

        next_plan = self.get_next_plan(plan)
        if next_plan is not None:
            next_plan_context = self.get_billing_context_from_plan(
                customer, next_plan, last_ledger_entry, now
            )
            # Settings we want to display from the next plan instead of the current one.
            # HACK: Our billing page is not designed to handle two plans, so while this is hacky,
            # it's the easiest way to get the UI we want without making things too complicated for us.
            keys = [
                "renewal_amount",
                "payment_method",
                "charge_automatically",
                "billing_frequency",
                "fixed_price_plan",
                "price_per_license",
                "discount_percent",
                "using_min_licenses_for_plan",
                "min_licenses_for_plan",
                "pre_discount_renewal_cents",
            ]

            for key in keys:
                context[key] = next_plan_context[key]
        return context

    def get_flat_discount_info(self, customer: Optional[Customer] = None) -> Tuple[int, int]:
        is_self_hosted_billing = not isinstance(self, RealmBillingSession)
        flat_discount = 0
        flat_discounted_months = 0
        if is_self_hosted_billing and (customer is None or customer.flat_discounted_months > 0):
            if customer is None:
                temp_customer = Customer()
                flat_discount = temp_customer.flat_discount
                flat_discounted_months = 12
            else:
                flat_discount = customer.flat_discount
                flat_discounted_months = customer.flat_discounted_months
            assert isinstance(flat_discount, int)
            assert isinstance(flat_discounted_months, int)
        return flat_discount, flat_discounted_months

    def get_initial_upgrade_context(
        self, initial_upgrade_request: InitialUpgradeRequest
    ) -> Tuple[Optional[str], Optional[UpgradePageContext]]:
        customer = self.get_customer()

        # Allow users to upgrade to business regardless of current sponsorship status.
        if self.is_sponsored_or_pending(customer) and initial_upgrade_request.tier not in [
            CustomerPlan.TIER_SELF_HOSTED_BASIC,
            CustomerPlan.TIER_SELF_HOSTED_BUSINESS,
        ]:
            return f"{self.billing_session_url}/sponsorship", None

        remote_server_legacy_plan_end_date = self.get_formatted_remote_server_legacy_plan_end_date(
            customer
        )
        # Show upgrade page for remote servers on legacy plan.
        if customer is not None and remote_server_legacy_plan_end_date is None:
            customer_plan = get_current_plan_by_customer(customer)
            if customer_plan is not None:
                return f"{self.billing_session_url}/billing", None

        exempt_from_license_number_check = (
            customer is not None and customer.exempt_from_license_number_check
        )

        # Check if user was successful in adding a card and we are rendering the page again.
        current_payment_method = None
        if customer is not None and customer_has_credit_card_as_default_payment_method(customer):
            assert customer.stripe_customer_id is not None
            stripe_customer = stripe_get_customer(customer.stripe_customer_id)
            current_payment_method = payment_method_string(stripe_customer)

        tier = initial_upgrade_request.tier

        fixed_price = None
        pay_by_invoice_payments_page = None
        scheduled_upgrade_invoice_amount_due = None
        is_free_trial_invoice_expired_notice = False
        free_trial_invoice_expired_notice_page_plan_name = None
        if customer is not None:
            fixed_price_plan_offer = get_configured_fixed_price_plan_offer(customer, tier)
            if fixed_price_plan_offer:
                assert fixed_price_plan_offer.fixed_price is not None
                fixed_price = fixed_price_plan_offer.fixed_price

                if fixed_price_plan_offer.sent_invoice_id is not None:
                    invoice = stripe.Invoice.retrieve(fixed_price_plan_offer.sent_invoice_id)
                    pay_by_invoice_payments_page = invoice.hosted_invoice_url
            else:
                # NOTE: Only use `last_send_invoice` to display invoice due information and not to verify payment.
                # Since `last_send_invoice` can vary from invoice for upgrade, additional license, support contract etc.
                last_send_invoice = (
                    Invoice.objects.filter(customer=customer, status=Invoice.SENT)
                    .order_by("id")
                    .last()
                )

                if last_send_invoice is not None:
                    invoice = stripe.Invoice.retrieve(last_send_invoice.stripe_invoice_id)
                    if invoice is not None:
                        scheduled_upgrade_invoice_amount_due = format_money(invoice.amount_due)
                        pay_by_invoice_payments_page = f"{self.billing_base_url}/invoices"

                        if (
                            last_send_invoice.plan is not None
                            and last_send_invoice.is_created_for_free_trial_upgrade
                        ):
                            # Automatic payment invoice would have been marked void already.
                            assert not last_send_invoice.plan.charge_automatically
                            is_free_trial_invoice_expired_notice = True
                            free_trial_invoice_expired_notice_page_plan_name = (
                                last_send_invoice.plan.name
                            )

        percent_off = Decimal(0)
        if customer is not None:
            discount_for_plan_tier = customer.get_discount_for_plan_tier(tier)
            if discount_for_plan_tier is not None:
                percent_off = discount_for_plan_tier

        customer_specific_context = self.get_upgrade_page_session_type_specific_context()
        min_licenses_for_plan = self.min_licenses_for_plan(tier)

        setup_payment_by_invoice = initial_upgrade_request.billing_modality == "send_invoice"
        # Regardless of value passed, invoice payments always have manual license management.
        if setup_payment_by_invoice:
            initial_upgrade_request.manual_license_management = True

        seat_count = self.current_count_for_billed_licenses()
        using_min_licenses_for_plan = min_licenses_for_plan > seat_count
        if using_min_licenses_for_plan:
            seat_count = min_licenses_for_plan
        signed_seat_count, salt = sign_string(str(seat_count))

        free_trial_days = None
        free_trial_end_date = None
        # Don't show free trial for remote servers on legacy plan.
        is_self_hosted_billing = not isinstance(self, RealmBillingSession)
        if fixed_price is None and remote_server_legacy_plan_end_date is None:
            free_trial_days = get_free_trial_days(is_self_hosted_billing, tier)
            if self.customer_plan_exists():
                # Free trial is not available for existing customers.
                free_trial_days = None
            if free_trial_days is not None:
                _, _, free_trial_end, _ = compute_plan_parameters(
                    tier,
                    CustomerPlan.BILLING_SCHEDULE_ANNUAL,
                    None,
                    True,
                    is_self_hosted_billing=is_self_hosted_billing,
                )
                free_trial_end_date = (
                    f"{free_trial_end:%B} {free_trial_end.day}, {free_trial_end.year}"
                )

        flat_discount, flat_discounted_months = self.get_flat_discount_info(customer)
        context: UpgradePageContext = {
            "customer_name": customer_specific_context["customer_name"],
            "discount_percent": format_discount_percentage(percent_off),
            "email": customer_specific_context["email"],
            "exempt_from_license_number_check": exempt_from_license_number_check,
            "free_trial_end_date": free_trial_end_date,
            "is_demo_organization": customer_specific_context["is_demo_organization"],
            "remote_server_legacy_plan_end_date": remote_server_legacy_plan_end_date,
            "manual_license_management": initial_upgrade_request.manual_license_management,
            "page_params": {
                "page_type": "upgrade",
                "annual_price": get_price_per_license(
                    tier, CustomerPlan.BILLING_SCHEDULE_ANNUAL, percent_off
                ),
                "demo_organization_scheduled_deletion_date": customer_specific_context[
                    "demo_organization_scheduled_deletion_date"
                ],
                "monthly_price": get_price_per_license(
                    tier, CustomerPlan.BILLING_SCHEDULE_MONTHLY, percent_off
                ),
                "seat_count": seat_count,
                "billing_base_url": self.billing_base_url,
                "tier": tier,
                "flat_discount": flat_discount,
                "flat_discounted_months": flat_discounted_months,
                "fixed_price": fixed_price,
                "setup_payment_by_invoice": setup_payment_by_invoice,
                "free_trial_days": free_trial_days,
            },
            "using_min_licenses_for_plan": using_min_licenses_for_plan,
            "min_licenses_for_plan": min_licenses_for_plan,
            "payment_method": current_payment_method,
            "plan": CustomerPlan.name_from_tier(tier),
            "fixed_price_plan": fixed_price is not None,
            "pay_by_invoice_payments_page": pay_by_invoice_payments_page,
            "salt": salt,
            "seat_count": seat_count,
            "signed_seat_count": signed_seat_count,
            "success_message": initial_upgrade_request.success_message,
            "is_sponsorship_pending": customer is not None and customer.sponsorship_pending,
            "sponsorship_plan_name": self.get_sponsorship_plan_name(
                customer, is_self_hosted_billing
            ),
            "scheduled_upgrade_invoice_amount_due": scheduled_upgrade_invoice_amount_due,
            "is_free_trial_invoice_expired_notice": is_free_trial_invoice_expired_notice,
            "free_trial_invoice_expired_notice_page_plan_name": free_trial_invoice_expired_notice_page_plan_name,
        }

        return None, context

    def min_licenses_for_flat_discount_to_self_hosted_basic_plan(
        self,
        customer: Optional[Customer],
        is_plan_free_trial_with_invoice_payment: bool = False,
    ) -> int:
        # Since monthly and annual TIER_SELF_HOSTED_BASIC plans have same per user price we only need to do this calculation once.
        # If we decided to apply this for other tiers, then we will have to do this calculation based on billing schedule selected by the user.
        price_per_license = get_price_per_license(
            CustomerPlan.TIER_SELF_HOSTED_BASIC, CustomerPlan.BILLING_SCHEDULE_MONTHLY
        )
        if customer is None or is_plan_free_trial_with_invoice_payment:
            return (
                Customer._meta.get_field("flat_discount").get_default() // price_per_license
            ) + 1
        elif customer.flat_discounted_months > 0:
            return (customer.flat_discount // price_per_license) + 1
        # If flat discount is not applied.
        return 1

    def min_licenses_for_plan(
        self, tier: int, is_plan_free_trial_with_invoice_payment: bool = False
    ) -> int:
        customer = self.get_customer()
        if customer is not None and customer.minimum_licenses:
            assert customer.default_discount is not None
            return customer.minimum_licenses

        if tier == CustomerPlan.TIER_SELF_HOSTED_BASIC:
            return min(
                self.min_licenses_for_flat_discount_to_self_hosted_basic_plan(
                    customer,
                    is_plan_free_trial_with_invoice_payment,
                ),
                10,
            )
        if tier == CustomerPlan.TIER_SELF_HOSTED_BUSINESS:
            return 25
        return 1

    def downgrade_at_the_end_of_billing_cycle(self, plan: Optional[CustomerPlan] = None) -> None:
        if plan is None:  # nocoverage
            # TODO: Add test coverage. Right now, this logic is used
            # in production but mocked in tests.
            customer = self.get_customer()
            assert customer is not None
            plan = get_current_plan_by_customer(customer)
        assert plan is not None
        do_change_plan_status(plan, CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE)

    def void_all_open_invoices(self) -> int:
        customer = self.get_customer()
        if customer is None:
            return 0
        invoices = get_all_invoices_for_customer(customer)
        voided_invoices_count = 0
        for invoice in invoices:
            if invoice.status == "open":
                assert invoice.id is not None
                stripe.Invoice.void_invoice(invoice.id)
                voided_invoices_count += 1
        return voided_invoices_count

    # During realm deactivation we instantly downgrade the plan to Limited.
    # Extra users added in the final month are not charged. Also used
    # for the cancellation of Free Trial.
    def downgrade_now_without_creating_additional_invoices(
        self,
        plan: Optional[CustomerPlan] = None,
        background_update: bool = False,
    ) -> None:
        if plan is None:
            customer = self.get_customer()
            if customer is None:
                return
            plan = get_current_plan_by_customer(customer)
            if plan is None:
                return  # nocoverage

        self.process_downgrade(plan, background_update=background_update)
        plan.invoiced_through = LicenseLedger.objects.filter(plan=plan).order_by("id").last()
        plan.next_invoice_date = next_invoice_date(plan)
        plan.save(update_fields=["invoiced_through", "next_invoice_date"])

    def do_update_plan(self, update_plan_request: UpdatePlanRequest) -> None:
        customer = self.get_customer()
        assert customer is not None
        plan = get_current_plan_by_customer(customer)
        assert plan is not None  # for mypy

        new_plan, last_ledger_entry = self.make_end_of_cycle_updates_if_needed(plan, timezone_now())
        if new_plan is not None:
            raise JsonableError(
                _(
                    "Unable to update the plan. The plan has been expired and replaced with a new plan."
                )
            )

        if last_ledger_entry is None:
            raise JsonableError(_("Unable to update the plan. The plan has ended."))

        status = update_plan_request.status
        if status is not None:
            if status == CustomerPlan.ACTIVE:
                assert plan.status < CustomerPlan.LIVE_STATUS_THRESHOLD
                with transaction.atomic():
                    # Switch to a different plan was cancelled. We end the next plan
                    # and set the current one as active.
                    if plan.status == CustomerPlan.SWITCH_PLAN_TIER_AT_PLAN_END:
                        next_plan = self.get_next_plan(plan)
                        assert next_plan is not None
                        do_change_plan_status(next_plan, CustomerPlan.ENDED)
                    do_change_plan_status(plan, status)
            elif status == CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE:
                assert not plan.is_free_trial()
                assert plan.status < CustomerPlan.LIVE_STATUS_THRESHOLD
                self.downgrade_at_the_end_of_billing_cycle(plan=plan)
            elif status == CustomerPlan.SWITCH_TO_ANNUAL_AT_END_OF_CYCLE:
                assert plan.billing_schedule == CustomerPlan.BILLING_SCHEDULE_MONTHLY
                assert plan.status < CustomerPlan.LIVE_STATUS_THRESHOLD
                # Customer needs to switch to an active plan first to avoid unexpected behavior.
                assert plan.status != CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE
                # Switching billing frequency for free trial should happen instantly.
                assert not plan.is_free_trial()
                assert plan.fixed_price is None
                do_change_plan_status(plan, status)
            elif status == CustomerPlan.SWITCH_TO_MONTHLY_AT_END_OF_CYCLE:
                assert plan.billing_schedule == CustomerPlan.BILLING_SCHEDULE_ANNUAL
                assert plan.status < CustomerPlan.LIVE_STATUS_THRESHOLD
                # Customer needs to switch to an active plan first to avoid unexpected behavior.
                assert plan.status != CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE
                # Switching billing frequency for free trial should happen instantly.
                assert not plan.is_free_trial()
                assert plan.fixed_price is None
                do_change_plan_status(plan, status)
            elif status == CustomerPlan.ENDED:
                # Not used right now on billing page but kept in case we need it.
                assert plan.is_free_trial()
                self.downgrade_now_without_creating_additional_invoices(plan=plan)
            elif status == CustomerPlan.DOWNGRADE_AT_END_OF_FREE_TRIAL:
                assert plan.is_free_trial()
                # For payment by invoice, we don't allow changing plan schedule and status.
                assert plan.charge_automatically
                do_change_plan_status(plan, status)
            elif status == CustomerPlan.FREE_TRIAL:
                assert plan.charge_automatically
                if update_plan_request.schedule is not None:
                    self.do_change_schedule_after_free_trial(plan, update_plan_request.schedule)
                else:
                    assert plan.status == CustomerPlan.DOWNGRADE_AT_END_OF_FREE_TRIAL
                    do_change_plan_status(plan, status)
            return

        licenses = update_plan_request.licenses
        if licenses is not None:
            if plan.is_free_trial():  # nocoverage
                raise JsonableError(
                    _("Cannot update licenses in the current billing period for free trial plan.")
                )
            if plan.automanage_licenses:
                raise JsonableError(
                    _(
                        "Unable to update licenses manually. Your plan is on automatic license management."
                    )
                )
            if last_ledger_entry.licenses == licenses:
                raise JsonableError(
                    _(
                        "Your plan is already on {licenses} licenses in the current billing period."
                    ).format(licenses=licenses)
                )
            if last_ledger_entry.licenses > licenses:
                raise JsonableError(
                    _("You cannot decrease the licenses in the current billing period.")
                )
            validate_licenses(
                plan.charge_automatically,
                licenses,
                self.current_count_for_billed_licenses(),
                plan.customer.exempt_from_license_number_check,
                self.min_licenses_for_plan(plan.tier),
            )
            self.update_license_ledger_for_manual_plan(plan, timezone_now(), licenses=licenses)
            return

        licenses_at_next_renewal = update_plan_request.licenses_at_next_renewal
        if licenses_at_next_renewal is not None:
            if plan.automanage_licenses:
                raise JsonableError(
                    _(
                        "Unable to update licenses manually. Your plan is on automatic license management."
                    )
                )
            if plan.status in (
                CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE,
                CustomerPlan.DOWNGRADE_AT_END_OF_FREE_TRIAL,
            ):  # nocoverage
                raise JsonableError(
                    _(
                        "Cannot change the licenses for next billing cycle for a plan that is being downgraded."
                    )
                )
            if last_ledger_entry.licenses_at_next_renewal == licenses_at_next_renewal:
                raise JsonableError(
                    _(
                        "Your plan is already scheduled to renew with {licenses_at_next_renewal} licenses."
                    ).format(licenses_at_next_renewal=licenses_at_next_renewal)
                )
            is_plan_free_trial_with_invoice_payment = (
                plan.is_free_trial() and not plan.charge_automatically
            )
            validate_licenses(
                plan.charge_automatically,
                licenses_at_next_renewal,
                self.current_count_for_billed_licenses(),
                plan.customer.exempt_from_license_number_check,
                self.min_licenses_for_plan(plan.tier, is_plan_free_trial_with_invoice_payment),
            )

            # User is trying to change licenses while in free trial.
            if is_plan_free_trial_with_invoice_payment:  # nocoverage
                invoice = Invoice.objects.filter(plan=plan).order_by("-id").first()
                assert invoice is not None
                # Don't allow customer to reduce licenses for next billing cycle if they have paid invoice.
                if invoice.status == Invoice.PAID:
                    assert last_ledger_entry.licenses_at_next_renewal is not None
                    if last_ledger_entry.licenses_at_next_renewal > licenses_at_next_renewal:
                        raise JsonableError(
                            _(
                                "You’ve already purchased {licenses_at_next_renewal} licenses for the next billing period."
                            ).format(
                                licenses_at_next_renewal=last_ledger_entry.licenses_at_next_renewal
                            )
                        )
                    else:
                        # If customer has paid already, we will send them an invoice for additional
                        # licenses at the end of free trial.
                        self.update_license_ledger_for_manual_plan(
                            plan, timezone_now(), licenses_at_next_renewal=licenses_at_next_renewal
                        )
                else:
                    # Discard the old invoice and create a new one with updated licenses.
                    self.update_free_trial_invoice_with_licenses(
                        plan, timezone_now(), licenses_at_next_renewal
                    )
            else:
                self.update_license_ledger_for_manual_plan(
                    plan, timezone_now(), licenses_at_next_renewal=licenses_at_next_renewal
                )
            return

        raise JsonableError(_("Nothing to change."))

    def switch_plan_tier(self, current_plan: CustomerPlan, new_plan_tier: int) -> None:
        assert current_plan.status == CustomerPlan.SWITCH_PLAN_TIER_NOW
        assert current_plan.next_invoice_date is not None
        next_billing_cycle = current_plan.next_invoice_date

        current_plan.end_date = next_billing_cycle
        current_plan.status = CustomerPlan.ENDED
        current_plan.save(update_fields=["status", "end_date"])

        discount_for_new_plan_tier = current_plan.customer.get_discount_for_plan_tier(new_plan_tier)
        new_price_per_license = get_price_per_license(
            new_plan_tier, current_plan.billing_schedule, discount_for_new_plan_tier
        )

        new_plan_billing_cycle_anchor = current_plan.end_date.replace(microsecond=0)

        new_plan = CustomerPlan.objects.create(
            customer=current_plan.customer,
            status=CustomerPlan.ACTIVE,
            automanage_licenses=current_plan.automanage_licenses,
            charge_automatically=current_plan.charge_automatically,
            price_per_license=new_price_per_license,
            discount=discount_for_new_plan_tier,
            billing_schedule=current_plan.billing_schedule,
            tier=new_plan_tier,
            billing_cycle_anchor=new_plan_billing_cycle_anchor,
            invoicing_status=CustomerPlan.INVOICING_STATUS_INITIAL_INVOICE_TO_BE_SENT,
            next_invoice_date=new_plan_billing_cycle_anchor,
        )

        current_plan_last_ledger = (
            LicenseLedger.objects.filter(plan=current_plan).order_by("id").last()
        )
        assert current_plan_last_ledger is not None
        licenses_for_new_plan = current_plan_last_ledger.licenses_at_next_renewal
        assert licenses_for_new_plan is not None
        LicenseLedger.objects.create(
            plan=new_plan,
            is_renewal=True,
            event_time=new_plan_billing_cycle_anchor,
            licenses=licenses_for_new_plan,
            licenses_at_next_renewal=licenses_for_new_plan,
        )

    def invoice_plan(self, plan: CustomerPlan, event_time: datetime) -> None:
        if plan.invoicing_status == CustomerPlan.INVOICING_STATUS_STARTED:
            raise NotImplementedError(
                "Plan with invoicing_status==STARTED needs manual resolution."
            )
        if (
            plan.tier != CustomerPlan.TIER_SELF_HOSTED_LEGACY
            and not plan.customer.stripe_customer_id
        ):
            raise BillingError(
                f"Customer has a paid plan without a Stripe customer ID: {plan.customer!s}"
            )

        # Updating a CustomerPlan with a status to switch the plan tier,
        # is done via switch_plan_tier, so we do not need to make end of
        # cycle updates for that case.
        if plan.status is not CustomerPlan.SWITCH_PLAN_TIER_NOW:
            self.make_end_of_cycle_updates_if_needed(plan, event_time)

        # The primary way to not create an invoice for a plan is to not have
        # any new ledger entry. The 'plan.is_a_paid_plan()' check adds an extra
        # layer of defense to avoid creating any invoices for customers not on
        # paid plan. It saves a DB query too.
        if plan.is_a_paid_plan():
            assert plan.customer.stripe_customer_id is not None
            if plan.invoicing_status == CustomerPlan.INVOICING_STATUS_INITIAL_INVOICE_TO_BE_SENT:
                invoiced_through_id = -1
                licenses_base = None
            else:
                assert plan.invoiced_through is not None
                licenses_base = plan.invoiced_through.licenses
                invoiced_through_id = plan.invoiced_through.id

            invoice_item_created = False
            invoice_period: stripe.InvoiceItem.CreateParamsPeriod | None = None
            for ledger_entry in LicenseLedger.objects.filter(
                plan=plan, id__gt=invoiced_through_id, event_time__lte=event_time
            ).order_by("id"):
                price_args: PriceArgs = {}
                if ledger_entry.is_renewal:
                    if plan.fixed_price is not None:
                        amount_due = get_amount_due_fixed_price_plan(
                            plan.fixed_price, plan.billing_schedule
                        )
                        price_args = {"amount": amount_due}
                    else:
                        assert plan.price_per_license is not None  # needed for mypy
                        price_args = {
                            "unit_amount": plan.price_per_license,
                            "quantity": ledger_entry.licenses,
                        }
                    description = f"{plan.name} - renewal"
                elif (
                    plan.fixed_price is None
                    and licenses_base is not None
                    and ledger_entry.licenses != licenses_base
                ):
                    assert plan.price_per_license is not None
                    last_ledger_entry_renewal = (
                        LicenseLedger.objects.filter(
                            plan=plan, is_renewal=True, event_time__lte=ledger_entry.event_time
                        )
                        .order_by("-id")
                        .first()
                    )
                    assert last_ledger_entry_renewal is not None
                    last_renewal = last_ledger_entry_renewal.event_time
                    billing_period_end = start_of_next_billing_cycle(plan, ledger_entry.event_time)
                    plan_renewal_or_end_date = get_plan_renewal_or_end_date(
                        plan, ledger_entry.event_time
                    )
                    unit_amount = plan.price_per_license
                    if not plan.is_free_trial():
                        proration_fraction = (
                            plan_renewal_or_end_date - ledger_entry.event_time
                        ) / (billing_period_end - last_renewal)
                        unit_amount = int(plan.price_per_license * proration_fraction + 0.5)
                    price_args = {
                        "unit_amount": unit_amount,
                        "quantity": ledger_entry.licenses - licenses_base,
                    }
                    description = "Additional license ({} - {})".format(
                        ledger_entry.event_time.strftime("%b %-d, %Y"),
                        plan_renewal_or_end_date.strftime("%b %-d, %Y"),
                    )

                if price_args:
                    plan.invoiced_through = ledger_entry
                    plan.invoicing_status = CustomerPlan.INVOICING_STATUS_STARTED
                    plan.save(update_fields=["invoicing_status", "invoiced_through"])
                    invoice_period = {
                        "start": datetime_to_timestamp(ledger_entry.event_time),
                        "end": datetime_to_timestamp(
                            get_plan_renewal_or_end_date(plan, ledger_entry.event_time)
                        ),
                    }
                    stripe.InvoiceItem.create(
                        currency="usd",
                        customer=plan.customer.stripe_customer_id,
                        description=description,
                        discountable=False,
                        period=invoice_period,
                        idempotency_key=get_idempotency_key(ledger_entry),
                        **price_args,
                    )
                    invoice_item_created = True
                plan.invoiced_through = ledger_entry
                plan.invoicing_status = CustomerPlan.INVOICING_STATUS_DONE
                plan.save(update_fields=["invoicing_status", "invoiced_through"])
                licenses_base = ledger_entry.licenses

            if invoice_item_created:
                assert invoice_period is not None
                flat_discount, flat_discounted_months = self.get_flat_discount_info(plan.customer)
                if plan.fixed_price is None and flat_discounted_months > 0:
                    num_months = (
                        12 if plan.billing_schedule == CustomerPlan.BILLING_SCHEDULE_ANNUAL else 1
                    )
                    flat_discounted_months = min(flat_discounted_months, num_months)
                    discount = flat_discount * flat_discounted_months
                    plan.customer.flat_discounted_months -= flat_discounted_months
                    plan.customer.save(update_fields=["flat_discounted_months"])
                    stripe.InvoiceItem.create(
                        currency="usd",
                        customer=plan.customer.stripe_customer_id,
                        description=f"${cents_to_dollar_string(flat_discount)}/month new customer discount",
                        # Negative value to apply discount.
                        amount=(-1 * discount),
                        period=invoice_period,
                    )

                if plan.charge_automatically:
                    collection_method: Literal["charge_automatically" | "send_invoice"] = (
                        "charge_automatically"
                    )
                    days_until_due = None
                else:
                    collection_method = "send_invoice"
                    days_until_due = DEFAULT_INVOICE_DAYS_UNTIL_DUE
                invoice_params = stripe.Invoice.CreateParams(
                    auto_advance=True,
                    collection_method=collection_method,
                    customer=plan.customer.stripe_customer_id,
                    statement_descriptor=plan.name,
                )
                if days_until_due is not None:
                    invoice_params["days_until_due"] = days_until_due
                stripe_invoice = stripe.Invoice.create(**invoice_params)
                stripe.Invoice.finalize_invoice(stripe_invoice)

        plan.next_invoice_date = next_invoice_date(plan)
        plan.invoice_overdue_email_sent = False
        plan.save(update_fields=["next_invoice_date", "invoice_overdue_email_sent"])

    def do_change_plan_to_new_tier(self, new_plan_tier: int) -> str:
        customer = self.get_customer()
        assert customer is not None
        current_plan = get_current_plan_by_customer(customer)

        if not current_plan or current_plan.status != CustomerPlan.ACTIVE:
            raise BillingError("Organization does not have an active plan")

        if not current_plan.customer.stripe_customer_id:
            raise BillingError("Organization missing Stripe customer.")

        type_of_tier_change = self.get_type_of_plan_tier_change(current_plan.tier, new_plan_tier)

        if type_of_tier_change == PlanTierChangeType.INVALID:
            raise BillingError("Invalid change of customer plan tier.")

        if type_of_tier_change == PlanTierChangeType.UPGRADE:
            plan_switch_time = timezone_now()
            current_plan.status = CustomerPlan.SWITCH_PLAN_TIER_NOW
            current_plan.next_invoice_date = plan_switch_time
            current_plan.save(update_fields=["status", "next_invoice_date"])

            self.do_change_plan_type(tier=new_plan_tier)

            amount_to_credit_for_early_termination = get_amount_to_credit_for_plan_tier_change(
                current_plan, plan_switch_time
            )
            stripe.Customer.create_balance_transaction(
                current_plan.customer.stripe_customer_id,
                amount=-1 * amount_to_credit_for_early_termination,
                currency="usd",
                description="Credit from early termination of active plan",
            )
            self.switch_plan_tier(current_plan, new_plan_tier)
            self.invoice_plan(current_plan, plan_switch_time)
            new_plan = get_current_plan_by_customer(customer)
            assert new_plan is not None  # for mypy
            self.invoice_plan(new_plan, plan_switch_time)
            return f"{self.billing_entity_display_name} upgraded to {new_plan.name}"

        # TODO: Implement downgrade that is a change from and to a paid plan
        # tier. This should keep the same billing cycle schedule and change
        # the plan when it's next invoiced vs immediately. Note this will need
        # new CustomerPlan.status value, e.g. SWITCH_PLAN_TIER_AT_PLAN_END.
        assert type_of_tier_change == PlanTierChangeType.DOWNGRADE  # nocoverage
        return ""  # nocoverage

    def get_event_status(self, event_status_request: EventStatusRequest) -> Dict[str, Any]:
        customer = self.get_customer()

        if customer is None:
            raise JsonableError(_("No customer for this organization!"))

        stripe_session_id = event_status_request.stripe_session_id
        if stripe_session_id is not None:
            try:
                session = Session.objects.get(
                    stripe_session_id=stripe_session_id, customer=customer
                )
            except Session.DoesNotExist:
                raise JsonableError(_("Session not found"))

            if (
                session.type == Session.CARD_UPDATE_FROM_BILLING_PAGE
                and not self.has_billing_access()
            ):
                raise JsonableError(_("Must be a billing administrator or an organization owner"))
            return {"session": session.to_dict()}

        stripe_invoice_id = event_status_request.stripe_invoice_id
        if stripe_invoice_id is not None:
            stripe_invoice = Invoice.objects.filter(
                stripe_invoice_id=stripe_invoice_id,
                customer=customer,
            ).last()

            if stripe_invoice is None:
                raise JsonableError(_("Payment intent not found"))
            return {"stripe_invoice": stripe_invoice.to_dict()}

        raise JsonableError(_("Pass stripe_session_id or stripe_invoice_id"))

    def get_sponsorship_plan_name(
        self, customer: Optional[Customer], is_remotely_hosted: bool
    ) -> str:
        if customer is not None and customer.sponsorship_pending:
            # For sponsorship pending requests, we also show the type of sponsorship requested.
            # In other cases, we just show the plan user is currently on.
            sponsorship_request = (
                ZulipSponsorshipRequest.objects.filter(customer=customer).order_by("-id").first()
            )
            # It's possible that we marked `customer.sponsorship_pending` via support page
            # without user submitting a sponsorship request.
            if sponsorship_request is not None and sponsorship_request.requested_plan not in (
                None,
                SponsoredPlanTypes.UNSPECIFIED.value,
            ):  # nocoverage
                return sponsorship_request.requested_plan

        # Default name for sponsorship plan.
        sponsored_plan_name = CustomerPlan.name_from_tier(CustomerPlan.TIER_CLOUD_STANDARD)
        if is_remotely_hosted:
            sponsored_plan_name = CustomerPlan.name_from_tier(
                CustomerPlan.TIER_SELF_HOSTED_COMMUNITY
            )

        return sponsored_plan_name

    def get_sponsorship_request_context(self) -> Optional[Dict[str, Any]]:
        customer = self.get_customer()
        is_remotely_hosted = isinstance(
            self, (RemoteRealmBillingSession, RemoteServerBillingSession)
        )

        plan_name = "Zulip Cloud Free"
        if is_remotely_hosted:
            plan_name = "Free"

        context: Dict[str, Any] = {
            "billing_base_url": self.billing_base_url,
            "is_remotely_hosted": is_remotely_hosted,
            "sponsorship_plan_name": self.get_sponsorship_plan_name(customer, is_remotely_hosted),
            "plan_name": plan_name,
            "org_name": self.org_name(),
        }

        if customer is not None and customer.sponsorship_pending:
            if self.on_paid_plan():
                return None

            context["is_sponsorship_pending"] = True

        if self.is_sponsored():
            context["is_sponsored"] = True

        if customer is not None:
            plan = get_current_plan_by_customer(customer)
            if plan is not None:
                context["plan_name"] = plan.name
                context["free_trial"] = plan.is_free_trial()
                context["is_server_on_legacy_plan"] = (
                    plan.tier == CustomerPlan.TIER_SELF_HOSTED_LEGACY
                )

        self.add_sponsorship_info_to_context(context)
        return context

    def request_sponsorship(self, form: SponsorshipRequestForm) -> None:
        if not form.is_valid():
            message = " ".join(
                error["message"]
                for error_list in form.errors.get_json_data().values()
                for error in error_list
            )
            raise BillingError("Form validation error", message=message)

        request_context = self.get_sponsorship_request_session_specific_context()
        with transaction.atomic():
            # Ensures customer is created first before updating sponsorship status.
            self.update_customer_sponsorship_status(True)
            sponsorship_request = ZulipSponsorshipRequest(
                customer=self.get_customer(),
                requested_by=request_context["realm_user"],
                org_website=form.cleaned_data["website"],
                org_description=form.cleaned_data["description"],
                org_type=form.cleaned_data["organization_type"],
                expected_total_users=form.cleaned_data["expected_total_users"],
                paid_users_count=form.cleaned_data["paid_users_count"],
                paid_users_description=form.cleaned_data["paid_users_description"],
                requested_plan=form.cleaned_data["requested_plan"],
            )
            sponsorship_request.save()

            org_type = form.cleaned_data["organization_type"]
            self.save_org_type_from_request_sponsorship_session(org_type)

            if request_context["realm_user"] is not None:
                # TODO: Refactor to not create an import cycle.
                from zerver.actions.users import do_change_is_billing_admin

                do_change_is_billing_admin(request_context["realm_user"], True)

            org_type_display_name = get_org_type_display_name(org_type)

        user_info = request_context["user_info"]
        support_url = self.support_url()
        context = {
            "requested_by": user_info["name"],
            "user_role": user_info["role"],
            "billing_entity": self.billing_entity_display_name,
            "support_url": support_url,
            "organization_type": org_type_display_name,
            "website": sponsorship_request.org_website,
            "description": sponsorship_request.org_description,
            "expected_total_users": sponsorship_request.expected_total_users,
            "paid_users_count": sponsorship_request.paid_users_count,
            "paid_users_description": sponsorship_request.paid_users_description,
            "requested_plan": sponsorship_request.requested_plan,
            "is_cloud_organization": isinstance(self, RealmBillingSession),
        }
        send_email(
            "zerver/emails/sponsorship_request",
            to_emails=[BILLING_SUPPORT_EMAIL],
            # Sent to the server's support team, so this email is not user-facing.
            from_name="Zulip sponsorship request",
            from_address=FromAddress.tokenized_no_reply_address(),
            reply_to_email=user_info["email"],
            context=context,
        )

    def process_support_view_request(self, support_request: SupportViewRequest) -> str:
        support_type = support_request["support_type"]
        success_message = ""

        if support_type == SupportType.approve_sponsorship:
            success_message = self.approve_sponsorship()
        elif support_type == SupportType.update_sponsorship_status:
            assert support_request["sponsorship_status"] is not None
            sponsorship_status = support_request["sponsorship_status"]
            success_message = self.update_customer_sponsorship_status(sponsorship_status)
        elif support_type == SupportType.attach_discount:
            assert support_request["discount"] is not None
            new_discount = support_request["discount"]
            success_message = self.attach_discount_to_customer(new_discount)
        elif support_type == SupportType.update_minimum_licenses:
            assert support_request["minimum_licenses"] is not None
            new_minimum_license_count = support_request["minimum_licenses"]
            success_message = self.update_customer_minimum_licenses(new_minimum_license_count)
        elif support_type == SupportType.update_required_plan_tier:
            required_plan_tier = support_request.get("required_plan_tier")
            assert required_plan_tier is not None
            success_message = self.set_required_plan_tier(required_plan_tier)
        elif support_type == SupportType.configure_fixed_price_plan:
            assert support_request["fixed_price"] is not None
            new_fixed_price = support_request["fixed_price"]
            sent_invoice_id = support_request["sent_invoice_id"]
            success_message = self.configure_fixed_price_plan(new_fixed_price, sent_invoice_id)
        elif support_type == SupportType.update_billing_modality:
            assert support_request["billing_modality"] is not None
            assert support_request["billing_modality"] in VALID_BILLING_MODALITY_VALUES
            charge_automatically = support_request["billing_modality"] == "charge_automatically"
            success_message = self.update_billing_modality_of_current_plan(charge_automatically)
        elif support_type == SupportType.update_plan_end_date:
            assert support_request["plan_end_date"] is not None
            new_plan_end_date = support_request["plan_end_date"]
            success_message = self.update_end_date_of_current_plan(new_plan_end_date)
        elif support_type == SupportType.modify_plan:
            assert support_request["plan_modification"] is not None
            plan_modification = support_request["plan_modification"]
            if plan_modification == "downgrade_at_billing_cycle_end":
                self.downgrade_at_the_end_of_billing_cycle()
                success_message = f"{self.billing_entity_display_name} marked for downgrade at the end of billing cycle"
            elif plan_modification == "downgrade_now_without_additional_licenses":
                self.downgrade_now_without_creating_additional_invoices()
                success_message = f"{self.billing_entity_display_name} downgraded without creating additional invoices"
            elif plan_modification == "downgrade_now_void_open_invoices":
                self.downgrade_now_without_creating_additional_invoices()
                voided_invoices_count = self.void_all_open_invoices()
                success_message = f"{self.billing_entity_display_name} downgraded and voided {voided_invoices_count} open invoices"
            else:
                assert plan_modification == "upgrade_plan_tier"
                assert support_request["new_plan_tier"] is not None
                new_plan_tier = support_request["new_plan_tier"]
                success_message = self.do_change_plan_to_new_tier(new_plan_tier)
        elif support_type == SupportType.delete_fixed_price_next_plan:
            customer = self.get_customer()
            assert customer is not None
            fixed_price_offer = CustomerPlanOffer.objects.filter(
                customer=customer, status=CustomerPlanOffer.CONFIGURED
            ).first()
            assert fixed_price_offer is not None
            fixed_price_offer.delete()
            success_message = "Fixed price offer deleted"

        return success_message

    def update_free_trial_invoice_with_licenses(
        self,
        plan: CustomerPlan,
        event_time: datetime,
        licenses: int,
    ) -> None:  # nocoverage
        assert (
            self.get_billable_licenses_for_customer(plan.customer, plan.tier, licenses) <= licenses
        )
        last_sent_invoice = Invoice.objects.filter(plan=plan).order_by("-id").first()
        assert last_sent_invoice is not None
        assert last_sent_invoice.status == Invoice.SENT

        assert plan.automanage_licenses is False
        assert plan.charge_automatically is False
        assert plan.fixed_price is None
        assert plan.is_free_trial()

        # Create a new renewal invoice with updated licenses so that this becomes the last
        # renewal invoice for customer which will be used for any future comparisons.
        LicenseLedger.objects.create(
            plan=plan,
            is_renewal=True,
            event_time=event_time,
            licenses=licenses,
            licenses_at_next_renewal=licenses,
        )

        # Update the last sent invoice with the new licenses. We just need to update `quantity` in
        # the first invoice item. So, we void the current invoice and create a new copy of it with
        # the updated quantity.
        stripe_invoice = stripe.Invoice.retrieve(last_sent_invoice.stripe_invoice_id)
        assert stripe_invoice.status == "open"
        assert isinstance(stripe_invoice.customer, str)
        assert stripe_invoice.statement_descriptor is not None
        assert stripe_invoice.metadata is not None
        invoice_items = stripe_invoice.lines.data
        # Stripe does something weird and puts the discount item first, so we need to reverse the order here.
        invoice_items.reverse()
        for invoice_item in invoice_items:
            assert invoice_item.description is not None
            price_args: PriceArgs = {}
            # If amount is positive, this must be non-discount item we need to update.
            if invoice_item.amount > 0:
                assert invoice_item.price is not None
                assert invoice_item.price.unit_amount is not None
                price_args = {
                    "quantity": licenses,
                    "unit_amount": invoice_item.price.unit_amount,
                }
            else:
                price_args = {
                    "amount": invoice_item.amount,
                }
            stripe.InvoiceItem.create(
                currency=invoice_item.currency,
                customer=stripe_invoice.customer,
                description=invoice_item.description,
                period={
                    "start": invoice_item.period.start,
                    "end": invoice_item.period.end,
                },
                **price_args,
            )

        assert plan.next_invoice_date is not None
        # Difference between end of free trial and event time
        days_until_due = (plan.next_invoice_date - event_time).days

        new_stripe_invoice = stripe.Invoice.create(
            auto_advance=False,
            collection_method="send_invoice",
            customer=stripe_invoice.customer,
            days_until_due=days_until_due,
            statement_descriptor=stripe_invoice.statement_descriptor,
            metadata=stripe_invoice.metadata,
        )
        new_stripe_invoice = stripe.Invoice.finalize_invoice(new_stripe_invoice)
        last_sent_invoice.stripe_invoice_id = str(new_stripe_invoice.id)
        last_sent_invoice.save(update_fields=["stripe_invoice_id"])

        assert stripe_invoice.id is not None
        stripe.Invoice.void_invoice(stripe_invoice.id)

    def update_license_ledger_for_manual_plan(
        self,
        plan: CustomerPlan,
        event_time: datetime,
        licenses: Optional[int] = None,
        licenses_at_next_renewal: Optional[int] = None,
    ) -> None:
        if licenses is not None:
            if not plan.customer.exempt_from_license_number_check:
                assert self.current_count_for_billed_licenses() <= licenses
            assert licenses > plan.licenses()
            LicenseLedger.objects.create(
                plan=plan,
                event_time=event_time,
                licenses=licenses,
                licenses_at_next_renewal=licenses,
            )
        elif licenses_at_next_renewal is not None:
            assert (
                self.get_billable_licenses_for_customer(
                    plan.customer, plan.tier, licenses_at_next_renewal
                )
                <= licenses_at_next_renewal
            )
            LicenseLedger.objects.create(
                plan=plan,
                event_time=event_time,
                licenses=plan.licenses(),
                licenses_at_next_renewal=licenses_at_next_renewal,
            )
        else:
            raise AssertionError("Pass licenses or licenses_at_next_renewal")

    def get_billable_licenses_for_customer(
        self,
        customer: Customer,
        tier: int,
        licenses: Optional[int] = None,
        event_time: datetime = timezone_now(),
    ) -> int:
        if licenses is not None and customer.exempt_from_license_number_check:
            return licenses

        current_licenses_count = self.current_count_for_billed_licenses(event_time)
        min_licenses_for_plan = self.min_licenses_for_plan(tier)
        if customer.exempt_from_license_number_check:  # nocoverage
            billed_licenses = current_licenses_count
        else:
            billed_licenses = max(current_licenses_count, min_licenses_for_plan)
        return billed_licenses

    def update_license_ledger_for_automanaged_plan(
        self, plan: CustomerPlan, event_time: datetime
    ) -> Optional[CustomerPlan]:
        new_plan, last_ledger_entry = self.make_end_of_cycle_updates_if_needed(plan, event_time)
        if last_ledger_entry is None:
            return None
        if new_plan is not None:
            plan = new_plan

        if plan.status == CustomerPlan.SWITCH_PLAN_TIER_AT_PLAN_END:  # nocoverage
            next_plan = self.get_next_plan(plan)
            assert next_plan is not None
            licenses_at_next_renewal = self.get_billable_licenses_for_customer(
                plan.customer,
                next_plan.tier,
                event_time=event_time,
            )
            # Current licenses stay as per the limits of current plan.
            current_plan_licenses_at_next_renewal = self.get_billable_licenses_for_customer(
                plan.customer,
                plan.tier,
                event_time=event_time,
            )
            licenses = max(current_plan_licenses_at_next_renewal, last_ledger_entry.licenses)
        else:
            licenses_at_next_renewal = self.get_billable_licenses_for_customer(
                plan.customer,
                plan.tier,
                event_time=event_time,
            )
            licenses = max(licenses_at_next_renewal, last_ledger_entry.licenses)

        LicenseLedger.objects.create(
            plan=plan,
            event_time=event_time,
            licenses=licenses,
            licenses_at_next_renewal=licenses_at_next_renewal,
        )

        # Returning plan is particularly helpful for 'sync_license_ledger_if_needed'.
        # If a new plan is created during the end of cycle update, then that function
        # needs the updated plan for a correct LicenseLedger update.
        return plan

    def migrate_customer_to_legacy_plan(
        self,
        renewal_date: datetime,
        end_date: datetime,
    ) -> None:
        assert not isinstance(self, RealmBillingSession)
        # Set stripe_customer_id to None to avoid customer being charged without a payment method.
        customer = self.update_or_create_customer(
            stripe_customer_id=None, defaults={"stripe_customer_id": None}
        )

        # Servers on legacy plan which are scheduled to be upgraded have 2 plans.
        # This plan will be used to track the current status of SWITCH_PLAN_TIER_AT_PLAN_END
        # and will not charge the customer. The other plan will be used to track the new plan
        # customer will move to the end of this plan.
        legacy_plan_anchor = renewal_date
        legacy_plan_params = {
            "billing_cycle_anchor": legacy_plan_anchor,
            "status": CustomerPlan.ACTIVE,
            "tier": CustomerPlan.TIER_SELF_HOSTED_LEGACY,
            # End when the new plan starts.
            "end_date": end_date,
            "next_invoice_date": end_date,
            # The primary mechanism for preventing charges under this
            # plan is setting 'invoiced_through' to last ledger_entry below,
            # but setting a 0 price is useful defense in depth here.
            "price_per_license": 0,
            "billing_schedule": CustomerPlan.BILLING_SCHEDULE_ANNUAL,
            "automanage_licenses": True,
        }
        legacy_plan = CustomerPlan.objects.create(
            customer=customer,
            **legacy_plan_params,
        )

        try:
            billed_licenses = self.get_billable_licenses_for_customer(customer, legacy_plan.tier)
        except MissingDataError:
            billed_licenses = 0

        # Create a ledger entry for the legacy plan for tracking purposes.
        ledger_entry = LicenseLedger.objects.create(
            plan=legacy_plan,
            is_renewal=True,
            event_time=legacy_plan_anchor,
            licenses=billed_licenses,
            licenses_at_next_renewal=billed_licenses,
        )
        legacy_plan.invoiced_through = ledger_entry
        legacy_plan.save(update_fields=["invoiced_through"])
        self.write_to_audit_log(
            event_type=AuditLogEventType.CUSTOMER_PLAN_CREATED,
            event_time=legacy_plan_anchor,
            extra_data=legacy_plan_params,
        )

        self.do_change_plan_type(tier=CustomerPlan.TIER_SELF_HOSTED_LEGACY, is_sponsored=False)

    def add_customer_to_community_plan(self) -> None:
        # There is no CustomerPlan for organizations on Zulip Cloud and
        # they enjoy the same benefits as the Standard plan.
        # For self-hosted organizations, sponsored organizations have
        # a Community CustomerPlan and they have different benefits compared
        # to customers on Business plan.
        assert not isinstance(self, RealmBillingSession)

        customer = self.update_or_create_customer()
        plan = get_current_plan_by_customer(customer)
        # Only plan that can be active is legacy plan. Which is already
        # ended by the support path from which is this function is called.
        assert plan is None
        now = timezone_now()
        community_plan_params = {
            "billing_cycle_anchor": now,
            "status": CustomerPlan.ACTIVE,
            "tier": CustomerPlan.TIER_SELF_HOSTED_COMMUNITY,
            # The primary mechanism for preventing charges under this
            # plan is setting a null `next_invoice_date`, but setting
            # a 0 price is useful defense in depth here.
            "next_invoice_date": None,
            "price_per_license": 0,
            "billing_schedule": CustomerPlan.BILLING_SCHEDULE_ANNUAL,
            "automanage_licenses": True,
        }
        community_plan = CustomerPlan.objects.create(
            customer=customer,
            **community_plan_params,
        )

        try:
            billed_licenses = self.get_billable_licenses_for_customer(customer, community_plan.tier)
        except MissingDataError:
            billed_licenses = 0

        # Create a ledger entry for the community plan for tracking purposes.
        # Also, since it is an active plan we need to it have at least one license ledger entry.
        ledger_entry = LicenseLedger.objects.create(
            plan=community_plan,
            is_renewal=True,
            event_time=now,
            licenses=billed_licenses,
            licenses_at_next_renewal=billed_licenses,
        )
        community_plan.invoiced_through = ledger_entry
        community_plan.save(update_fields=["invoiced_through"])
        self.write_to_audit_log(
            event_type=AuditLogEventType.CUSTOMER_PLAN_CREATED,
            event_time=now,
            extra_data=community_plan_params,
        )

    def get_last_ledger_for_automanaged_plan_if_exists(
        self,
    ) -> Optional[LicenseLedger]:
        customer = self.get_customer()
        if customer is None:
            return None
        plan = get_current_plan_by_customer(customer)
        if plan is None:
            return None
        if not plan.automanage_licenses:
            return None

        # It's an invariant that any current plan have at least an
        # initial ledger entry.
        last_ledger = LicenseLedger.objects.filter(plan=plan).order_by("id").last()
        assert last_ledger is not None

        return last_ledger


class RealmBillingSession(BillingSession):
    def __init__(
        self,
        user: Optional[UserProfile] = None,
        realm: Optional[Realm] = None,
        *,
        support_session: bool = False,
    ) -> None:
        self.user = user
        assert user is not None or realm is not None
        if support_session:
            assert user is not None and user.is_staff
        self.support_session = support_session

        if user is not None and realm is not None:
            assert user.is_staff or user.realm == realm
            self.realm = realm
        elif user is not None:
            self.realm = user.realm
        else:
            assert realm is not None  # for mypy
            self.realm = realm

    PAID_PLANS = [
        Realm.PLAN_TYPE_STANDARD,
        Realm.PLAN_TYPE_PLUS,
    ]

    @override
    @property
    def billing_entity_display_name(self) -> str:
        return self.realm.string_id

    @override
    @property
    def billing_session_url(self) -> str:
        return self.realm.uri

    @override
    @property
    def billing_base_url(self) -> str:
        return ""

    @override
    def support_url(self) -> str:
        return build_support_url("support", self.realm.string_id)

    @override
    def get_customer(self) -> Optional[Customer]:
        return get_customer_by_realm(self.realm)

    @override
    def get_email(self) -> str:
        assert self.user is not None
        return self.user.delivery_email

    @override
    def current_count_for_billed_licenses(self, event_time: datetime = timezone_now()) -> int:
        return get_latest_seat_count(self.realm)

    @override
    def get_audit_log_event(self, event_type: AuditLogEventType) -> int:
        if event_type is AuditLogEventType.STRIPE_CUSTOMER_CREATED:
            return RealmAuditLog.STRIPE_CUSTOMER_CREATED
        elif event_type is AuditLogEventType.STRIPE_CARD_CHANGED:
            return RealmAuditLog.STRIPE_CARD_CHANGED
        elif event_type is AuditLogEventType.CUSTOMER_PLAN_CREATED:
            return RealmAuditLog.CUSTOMER_PLAN_CREATED
        elif event_type is AuditLogEventType.DISCOUNT_CHANGED:
            return RealmAuditLog.REALM_DISCOUNT_CHANGED
        elif event_type is AuditLogEventType.CUSTOMER_PROPERTY_CHANGED:
            return RealmAuditLog.CUSTOMER_PROPERTY_CHANGED
        elif event_type is AuditLogEventType.SPONSORSHIP_APPROVED:
            return RealmAuditLog.REALM_SPONSORSHIP_APPROVED
        elif event_type is AuditLogEventType.SPONSORSHIP_PENDING_STATUS_CHANGED:
            return RealmAuditLog.REALM_SPONSORSHIP_PENDING_STATUS_CHANGED
        elif event_type is AuditLogEventType.BILLING_MODALITY_CHANGED:
            return RealmAuditLog.REALM_BILLING_MODALITY_CHANGED
        elif event_type is AuditLogEventType.CUSTOMER_PLAN_PROPERTY_CHANGED:
            return RealmAuditLog.CUSTOMER_PLAN_PROPERTY_CHANGED  # nocoverage
        elif event_type is AuditLogEventType.CUSTOMER_SWITCHED_FROM_MONTHLY_TO_ANNUAL_PLAN:
            return RealmAuditLog.CUSTOMER_SWITCHED_FROM_MONTHLY_TO_ANNUAL_PLAN
        elif event_type is AuditLogEventType.CUSTOMER_SWITCHED_FROM_ANNUAL_TO_MONTHLY_PLAN:
            return RealmAuditLog.CUSTOMER_SWITCHED_FROM_ANNUAL_TO_MONTHLY_PLAN
        else:
            raise BillingSessionAuditLogEventError(event_type)

    @override
    def write_to_audit_log(
        self,
        event_type: AuditLogEventType,
        event_time: datetime,
        *,
        background_update: bool = False,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        audit_log_event = self.get_audit_log_event(event_type)
        audit_log_data = {
            "realm": self.realm,
            "event_type": audit_log_event,
            "event_time": event_time,
        }

        if extra_data:
            audit_log_data["extra_data"] = extra_data

        if self.user is not None and not background_update:
            audit_log_data["acting_user"] = self.user

        RealmAuditLog.objects.create(**audit_log_data)

    @override
    def get_data_for_stripe_customer(self) -> StripeCustomerData:
        # Support requests do not set any stripe billing information.
        assert self.support_session is False
        assert self.user is not None
        metadata: Dict[str, Any] = {}
        metadata["realm_id"] = self.realm.id
        metadata["realm_str"] = self.realm.string_id
        realm_stripe_customer_data = StripeCustomerData(
            description=f"{self.realm.string_id} ({self.realm.name})",
            email=self.get_email(),
            metadata=metadata,
        )
        return realm_stripe_customer_data

    @override
    def update_data_for_checkout_session_and_invoice_payment(
        self, metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        assert self.user is not None
        updated_metadata = dict(
            user_email=self.get_email(),
            realm_id=self.realm.id,
            realm_str=self.realm.string_id,
            user_id=self.user.id,
            **metadata,
        )
        return updated_metadata

    @override
    def update_or_create_customer(
        self, stripe_customer_id: Optional[str] = None, *, defaults: Optional[Dict[str, Any]] = None
    ) -> Customer:
        if stripe_customer_id is not None:
            # Support requests do not set any stripe billing information.
            assert self.support_session is False
            customer, created = Customer.objects.update_or_create(
                realm=self.realm, defaults={"stripe_customer_id": stripe_customer_id}
            )
            from zerver.actions.users import do_change_is_billing_admin

            assert self.user is not None
            do_change_is_billing_admin(self.user, True)
            return customer
        else:
            customer, created = Customer.objects.update_or_create(
                realm=self.realm, defaults=defaults
            )
            return customer

    @override
    def do_change_plan_type(
        self, *, tier: Optional[int], is_sponsored: bool = False, background_update: bool = False
    ) -> None:
        from zerver.actions.realm_settings import do_change_realm_plan_type

        # This function needs to translate between the different
        # formats of CustomerPlan.tier and Realm.plan_type.
        if is_sponsored:
            # Cloud sponsored customers don't have an active CustomerPlan.
            plan_type = Realm.PLAN_TYPE_STANDARD_FREE
        elif tier == CustomerPlan.TIER_CLOUD_STANDARD:
            plan_type = Realm.PLAN_TYPE_STANDARD
        elif tier == CustomerPlan.TIER_CLOUD_PLUS:
            plan_type = Realm.PLAN_TYPE_PLUS
        else:
            raise AssertionError("Unexpected tier")

        acting_user = None
        if not background_update:
            acting_user = self.user

        do_change_realm_plan_type(self.realm, plan_type, acting_user=acting_user)

    @override
    def process_downgrade(self, plan: CustomerPlan, background_update: bool = False) -> None:
        from zerver.actions.realm_settings import do_change_realm_plan_type

        acting_user = None
        if not background_update:
            acting_user = self.user

        assert plan.customer.realm is not None
        do_change_realm_plan_type(
            plan.customer.realm, Realm.PLAN_TYPE_LIMITED, acting_user=acting_user
        )
        plan.status = CustomerPlan.ENDED
        plan.save(update_fields=["status"])

    @override
    def approve_sponsorship(self) -> str:
        # Sponsorship approval is only a support admin action.
        assert self.support_session

        customer = self.get_customer()
        if customer is not None:
            error_message = self.check_customer_not_on_paid_plan(customer)
            if error_message != "":
                raise SupportRequestError(error_message)

        from zerver.actions.message_send import internal_send_private_message

        self.do_change_plan_type(tier=None, is_sponsored=True)
        if customer is not None and customer.sponsorship_pending:
            customer.sponsorship_pending = False
            customer.save(update_fields=["sponsorship_pending"])
            self.write_to_audit_log(
                event_type=AuditLogEventType.SPONSORSHIP_APPROVED, event_time=timezone_now()
            )
        notification_bot = get_system_bot(settings.NOTIFICATION_BOT, self.realm.id)
        for user in self.realm.get_human_billing_admin_and_realm_owner_users():
            with override_language(user.default_language):
                # Using variable to make life easier for translators if these details change.
                message = _(
                    "Your organization's request for sponsored hosting has been approved! "
                    "You have been upgraded to {plan_name}, free of charge. {emoji}\n\n"
                    "If you could {begin_link}list Zulip as a sponsor on your website{end_link}, "
                    "we would really appreciate it!"
                ).format(
                    plan_name=CustomerPlan.name_from_tier(CustomerPlan.TIER_CLOUD_STANDARD),
                    emoji=":tada:",
                    begin_link="[",
                    end_link="](/help/linking-to-zulip-website)",
                )
                internal_send_private_message(notification_bot, user, message)
        return f"Sponsorship approved for {self.billing_entity_display_name}"

    @override
    def is_sponsored(self) -> bool:
        return self.realm.plan_type == self.realm.PLAN_TYPE_STANDARD_FREE

    @override
    def get_metadata_for_stripe_update_card(self) -> Dict[str, str]:
        assert self.user is not None
        return {
            "type": "card_update",
            "user_id": str(self.user.id),
        }

    @override
    def get_upgrade_page_session_type_specific_context(
        self,
    ) -> UpgradePageSessionTypeSpecificContext:
        assert self.user is not None
        return UpgradePageSessionTypeSpecificContext(
            customer_name=self.realm.name,
            email=self.get_email(),
            is_demo_organization=self.realm.demo_organization_scheduled_deletion_date is not None,
            demo_organization_scheduled_deletion_date=self.realm.demo_organization_scheduled_deletion_date,
            is_self_hosting=False,
        )

    @override
    def check_plan_tier_is_billable(self, plan_tier: int) -> bool:
        implemented_plan_tiers = [
            CustomerPlan.TIER_CLOUD_STANDARD,
            CustomerPlan.TIER_CLOUD_PLUS,
        ]
        if plan_tier in implemented_plan_tiers:
            return True
        return False

    @override
    def get_type_of_plan_tier_change(
        self, current_plan_tier: int, new_plan_tier: int
    ) -> PlanTierChangeType:
        valid_plan_tiers = [CustomerPlan.TIER_CLOUD_STANDARD, CustomerPlan.TIER_CLOUD_PLUS]
        if (
            current_plan_tier not in valid_plan_tiers
            or new_plan_tier not in valid_plan_tiers
            or current_plan_tier == new_plan_tier
        ):
            return PlanTierChangeType.INVALID
        if (
            current_plan_tier == CustomerPlan.TIER_CLOUD_STANDARD
            and new_plan_tier == CustomerPlan.TIER_CLOUD_PLUS
        ):
            return PlanTierChangeType.UPGRADE
        else:  # nocoverage, not currently implemented
            assert current_plan_tier == CustomerPlan.TIER_CLOUD_PLUS
            assert new_plan_tier == CustomerPlan.TIER_CLOUD_STANDARD
            return PlanTierChangeType.DOWNGRADE

    @override
    def has_billing_access(self) -> bool:
        assert self.user is not None
        return self.user.has_billing_access

    @override
    def on_paid_plan(self) -> bool:
        return self.realm.plan_type in self.PAID_PLANS

    @override
    def org_name(self) -> str:
        return self.realm.name

    @override
    def add_sponsorship_info_to_context(self, context: Dict[str, Any]) -> None:
        context.update(
            realm_org_type=self.realm.org_type,
            sorted_org_types=sorted(
                (
                    [org_type_name, org_type]
                    for (org_type_name, org_type) in Realm.ORG_TYPES.items()
                    if not org_type.get("hidden")
                ),
                key=sponsorship_org_type_key_helper,
            ),
        )

    @override
    def get_sponsorship_request_session_specific_context(
        self,
    ) -> SponsorshipRequestSessionSpecificContext:
        assert self.user is not None
        return SponsorshipRequestSessionSpecificContext(
            realm_user=self.user,
            user_info=SponsorshipApplicantInfo(
                name=self.user.full_name,
                email=self.get_email(),
                role=self.user.get_role_name(),
            ),
            realm_string_id=self.realm.string_id,
        )

    @override
    def save_org_type_from_request_sponsorship_session(self, org_type: int) -> None:
        # TODO: Use the actions.py method for this.
        if self.realm.org_type != org_type:
            self.realm.org_type = org_type
            self.realm.save(update_fields=["org_type"])

    def update_license_ledger_if_needed(self, event_time: datetime) -> None:
        customer = self.get_customer()
        if customer is None:
            return
        plan = get_current_plan_by_customer(customer)
        if plan is None:
            return
        if not plan.automanage_licenses:
            return
        self.update_license_ledger_for_automanaged_plan(plan, event_time)

    @override
    def sync_license_ledger_if_needed(self) -> None:  # nocoverage
        # TODO: For zulip cloud, currently we use 'update_license_ledger_if_needed'
        # to update the ledger. For consistency, we plan to use RealmAuditlog
        # to update the ledger as we currently do for self-hosted system using
        # RemoteRealmAuditlog. This will also help the cloud billing system to
        # recover from a multi-day outage of the invoicing process without doing
        # anything weird.
        pass


class RemoteRealmBillingSession(BillingSession):
    def __init__(
        self,
        remote_realm: RemoteRealm,
        remote_billing_user: Optional[RemoteRealmBillingUser] = None,
        support_staff: Optional[UserProfile] = None,
    ) -> None:
        self.remote_realm = remote_realm
        self.remote_billing_user = remote_billing_user
        self.support_staff = support_staff
        if support_staff is not None:  # nocoverage
            assert support_staff.is_staff
            self.support_session = True
        else:
            self.support_session = False

    @override
    @property
    def billing_entity_display_name(self) -> str:  # nocoverage
        return self.remote_realm.name

    @override
    @property
    def billing_session_url(self) -> str:  # nocoverage
        return f"{settings.EXTERNAL_URI_SCHEME}{settings.SELF_HOSTING_MANAGEMENT_SUBDOMAIN}.{settings.EXTERNAL_HOST}/realm/{self.remote_realm.uuid}"

    @override
    @property
    def billing_base_url(self) -> str:
        return f"/realm/{self.remote_realm.uuid}"

    @override
    def support_url(self) -> str:  # nocoverage
        return build_support_url("remote_servers_support", str(self.remote_realm.uuid))

    @override
    def get_customer(self) -> Optional[Customer]:
        return get_customer_by_remote_realm(self.remote_realm)

    @override
    def get_email(self) -> str:
        assert self.remote_billing_user is not None
        return self.remote_billing_user.email

    @override
    def current_count_for_billed_licenses(self, event_time: datetime = timezone_now()) -> int:
        if has_stale_audit_log(self.remote_realm.server):
            raise MissingDataError
        remote_realm_counts = get_remote_realm_guest_and_non_guest_count(
            self.remote_realm, event_time
        )
        return remote_realm_counts.non_guest_user_count + remote_realm_counts.guest_user_count

    def missing_data_error_page(self, request: HttpRequest) -> HttpResponse:  # nocoverage
        # The RemoteRealm error page code path should not really be
        # possible, in that the self-hosted server will have uploaded
        # current audit log data as needed as part of logging the user
        # in.
        missing_data_context: Dict[str, Any] = {
            "remote_realm_session": True,
            "supports_remote_realms": self.remote_realm.server.last_api_feature_level is not None,
        }
        return render(
            request,
            "corporate/billing/server_not_uploading_data.html",
            context=missing_data_context,
        )

    @override
    def get_audit_log_event(self, event_type: AuditLogEventType) -> int:
        if event_type is AuditLogEventType.STRIPE_CUSTOMER_CREATED:
            return RemoteRealmAuditLog.STRIPE_CUSTOMER_CREATED
        elif event_type is AuditLogEventType.STRIPE_CARD_CHANGED:
            return RemoteRealmAuditLog.STRIPE_CARD_CHANGED
        elif event_type is AuditLogEventType.CUSTOMER_PLAN_CREATED:
            return RemoteRealmAuditLog.CUSTOMER_PLAN_CREATED
        elif event_type is AuditLogEventType.DISCOUNT_CHANGED:
            return RemoteRealmAuditLog.REMOTE_SERVER_DISCOUNT_CHANGED
        elif event_type is AuditLogEventType.CUSTOMER_PROPERTY_CHANGED:
            return RemoteRealmAuditLog.CUSTOMER_PROPERTY_CHANGED  # nocoverage
        elif event_type is AuditLogEventType.SPONSORSHIP_APPROVED:
            return RemoteRealmAuditLog.REMOTE_SERVER_SPONSORSHIP_APPROVED
        elif event_type is AuditLogEventType.SPONSORSHIP_PENDING_STATUS_CHANGED:
            return RemoteRealmAuditLog.REMOTE_SERVER_SPONSORSHIP_PENDING_STATUS_CHANGED
        elif event_type is AuditLogEventType.BILLING_MODALITY_CHANGED:
            return RemoteRealmAuditLog.REMOTE_SERVER_BILLING_MODALITY_CHANGED  # nocoverage
        elif event_type is AuditLogEventType.CUSTOMER_PLAN_PROPERTY_CHANGED:
            return RemoteRealmAuditLog.CUSTOMER_PLAN_PROPERTY_CHANGED
        elif event_type is AuditLogEventType.BILLING_ENTITY_PLAN_TYPE_CHANGED:
            return RemoteRealmAuditLog.REMOTE_SERVER_PLAN_TYPE_CHANGED
        elif (
            event_type is AuditLogEventType.CUSTOMER_SWITCHED_FROM_MONTHLY_TO_ANNUAL_PLAN
        ):  # nocoverage
            return RemoteRealmAuditLog.CUSTOMER_SWITCHED_FROM_MONTHLY_TO_ANNUAL_PLAN
        elif (
            event_type is AuditLogEventType.CUSTOMER_SWITCHED_FROM_ANNUAL_TO_MONTHLY_PLAN
        ):  # nocoverage
            return RemoteRealmAuditLog.CUSTOMER_SWITCHED_FROM_ANNUAL_TO_MONTHLY_PLAN
        else:  # nocoverage
            raise BillingSessionAuditLogEventError(event_type)

    @override
    def write_to_audit_log(
        self,
        event_type: AuditLogEventType,
        event_time: datetime,
        *,
        background_update: bool = False,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        # These audit logs don't use all the fields of `RemoteRealmAuditLog`:
        #
        # * remote_id is None because this is not synced from a remote table.
        # * realm_id is None because we do not aim to store both remote_realm
        #   and the legacy realm_id field.
        audit_log_event = self.get_audit_log_event(event_type)
        log_data = {
            "server": self.remote_realm.server,
            "remote_realm": self.remote_realm,
            "event_type": audit_log_event,
            "event_time": event_time,
        }

        if not background_update:
            log_data.update(
                {
                    # At most one of these should be set, but we may
                    # not want an assert for that yet:
                    "acting_support_user": self.support_staff,
                    "acting_remote_user": self.remote_billing_user,
                }
            )

        if extra_data:
            log_data["extra_data"] = extra_data

        RemoteRealmAuditLog.objects.create(**log_data)

    @override
    def get_data_for_stripe_customer(self) -> StripeCustomerData:
        # Support requests do not set any stripe billing information.
        assert self.support_session is False
        metadata: Dict[str, Any] = {}
        metadata["remote_realm_uuid"] = self.remote_realm.uuid
        metadata["remote_realm_host"] = str(self.remote_realm.host)
        realm_stripe_customer_data = StripeCustomerData(
            description=str(self.remote_realm),
            email=self.get_email(),
            metadata=metadata,
        )
        return realm_stripe_customer_data

    @override
    def update_data_for_checkout_session_and_invoice_payment(
        self, metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        assert self.remote_billing_user is not None
        updated_metadata = dict(
            remote_realm_user_id=self.remote_billing_user.id,
            remote_realm_user_email=self.get_email(),
            remote_realm_host=self.remote_realm.host,
            **metadata,
        )
        return updated_metadata

    @override
    def update_or_create_customer(
        self, stripe_customer_id: Optional[str] = None, *, defaults: Optional[Dict[str, Any]] = None
    ) -> Customer:
        if stripe_customer_id is not None:
            # Support requests do not set any stripe billing information.
            assert self.support_session is False
            customer, created = Customer.objects.update_or_create(
                remote_realm=self.remote_realm,
                defaults={"stripe_customer_id": stripe_customer_id},
            )
        else:
            customer, created = Customer.objects.update_or_create(
                remote_realm=self.remote_realm, defaults=defaults
            )

        if created and not customer.default_discount:
            customer.flat_discounted_months = 12
            customer.save(update_fields=["flat_discounted_months"])

        return customer

    @override
    @transaction.atomic
    def do_change_plan_type(
        self, *, tier: Optional[int], is_sponsored: bool = False, background_update: bool = False
    ) -> None:  # nocoverage
        if is_sponsored:
            plan_type = RemoteRealm.PLAN_TYPE_COMMUNITY
            self.add_customer_to_community_plan()
        elif tier == CustomerPlan.TIER_SELF_HOSTED_BASIC:
            plan_type = RemoteRealm.PLAN_TYPE_BASIC
        elif tier == CustomerPlan.TIER_SELF_HOSTED_BUSINESS:
            plan_type = RemoteRealm.PLAN_TYPE_BUSINESS
        elif tier == CustomerPlan.TIER_SELF_HOSTED_LEGACY:
            plan_type = RemoteRealm.PLAN_TYPE_SELF_MANAGED_LEGACY
        else:
            raise AssertionError("Unexpected tier")

        old_plan_type = self.remote_realm.plan_type
        self.remote_realm.plan_type = plan_type
        self.remote_realm.save(update_fields=["plan_type"])
        self.write_to_audit_log(
            event_type=AuditLogEventType.BILLING_ENTITY_PLAN_TYPE_CHANGED,
            event_time=timezone_now(),
            extra_data={"old_value": old_plan_type, "new_value": plan_type},
            background_update=background_update,
        )

    @override
    def approve_sponsorship(self) -> str:  # nocoverage
        # Sponsorship approval is only a support admin action.
        assert self.support_session

        customer = self.get_customer()
        if customer is not None:
            error_message = self.check_customer_not_on_paid_plan(customer)
            if error_message != "":
                raise SupportRequestError(error_message)

            if self.remote_realm.plan_type == RemoteRealm.PLAN_TYPE_SELF_MANAGED_LEGACY:
                plan = get_current_plan_by_customer(customer)
                # Ideally we should have always have a plan here but since this is support page, we can be lenient about it.
                if plan is not None:
                    assert self.get_next_plan(plan) is None
                    assert plan.tier == CustomerPlan.TIER_SELF_HOSTED_LEGACY
                    plan.status = CustomerPlan.ENDED
                    plan.save(update_fields=["status"])

        self.do_change_plan_type(tier=None, is_sponsored=True)
        if customer is not None and customer.sponsorship_pending:
            customer.sponsorship_pending = False
            customer.save(update_fields=["sponsorship_pending"])
            self.write_to_audit_log(
                event_type=AuditLogEventType.SPONSORSHIP_APPROVED, event_time=timezone_now()
            )
        emailed_string = ""
        billing_emails = list(
            RemoteRealmBillingUser.objects.filter(remote_realm_id=self.remote_realm.id).values_list(
                "email", flat=True
            )
        )
        if len(billing_emails) > 0:
            send_email(
                "zerver/emails/sponsorship_approved_community_plan",
                to_emails=billing_emails,
                from_address=BILLING_SUPPORT_EMAIL,
                context={
                    "billing_entity": self.billing_entity_display_name,
                    "plans_link": "https://zulip.com/plans/#self-hosted",
                    "link_to_zulip": "https://zulip.com/help/linking-to-zulip-website",
                },
            )
            emailed_string = "Emailed existing billing users."
        else:
            emailed_string = "No billing users exist to email."

        return f"Sponsorship approved for {self.billing_entity_display_name}; " + emailed_string

    @override
    def is_sponsored(self) -> bool:
        return self.remote_realm.plan_type == self.remote_realm.PLAN_TYPE_COMMUNITY

    @override
    def get_metadata_for_stripe_update_card(self) -> Dict[str, str]:  # nocoverage
        assert self.remote_billing_user is not None
        return {"type": "card_update", "remote_realm_user_id": str(self.remote_billing_user.id)}

    @override
    def get_upgrade_page_session_type_specific_context(
        self,
    ) -> UpgradePageSessionTypeSpecificContext:
        return UpgradePageSessionTypeSpecificContext(
            customer_name=self.remote_realm.host,
            email=self.get_email(),
            is_demo_organization=False,
            demo_organization_scheduled_deletion_date=None,
            is_self_hosting=True,
        )

    @override
    def process_downgrade(
        self, plan: CustomerPlan, background_update: bool = False
    ) -> None:  # nocoverage
        with transaction.atomic():
            old_plan_type = self.remote_realm.plan_type
            new_plan_type = RemoteRealm.PLAN_TYPE_SELF_MANAGED
            self.remote_realm.plan_type = new_plan_type
            self.remote_realm.save(update_fields=["plan_type"])
            self.write_to_audit_log(
                event_type=AuditLogEventType.BILLING_ENTITY_PLAN_TYPE_CHANGED,
                event_time=timezone_now(),
                extra_data={"old_value": old_plan_type, "new_value": new_plan_type},
                background_update=background_update,
            )

        plan.status = CustomerPlan.ENDED
        plan.save(update_fields=["status"])

    @override
    def check_plan_tier_is_billable(self, plan_tier: int) -> bool:  # nocoverage
        implemented_plan_tiers = [
            CustomerPlan.TIER_SELF_HOSTED_BASIC,
            CustomerPlan.TIER_SELF_HOSTED_BUSINESS,
        ]
        if plan_tier in implemented_plan_tiers:
            return True
        return False

    @override
    def get_type_of_plan_tier_change(
        self, current_plan_tier: int, new_plan_tier: int
    ) -> PlanTierChangeType:  # nocoverage
        valid_plan_tiers = [
            CustomerPlan.TIER_SELF_HOSTED_LEGACY,
            CustomerPlan.TIER_SELF_HOSTED_BASIC,
            CustomerPlan.TIER_SELF_HOSTED_BUSINESS,
        ]
        if (
            current_plan_tier not in valid_plan_tiers
            or new_plan_tier not in valid_plan_tiers
            or current_plan_tier == new_plan_tier
        ):
            return PlanTierChangeType.INVALID
        if (
            current_plan_tier == CustomerPlan.TIER_SELF_HOSTED_BASIC
            and new_plan_tier == CustomerPlan.TIER_SELF_HOSTED_BUSINESS
        ):
            return PlanTierChangeType.UPGRADE
        elif current_plan_tier == CustomerPlan.TIER_SELF_HOSTED_LEGACY and new_plan_tier in (
            CustomerPlan.TIER_SELF_HOSTED_BASIC,
            CustomerPlan.TIER_SELF_HOSTED_BUSINESS,
        ):
            return PlanTierChangeType.UPGRADE
        elif (
            current_plan_tier == CustomerPlan.TIER_SELF_HOSTED_BASIC
            and new_plan_tier == CustomerPlan.TIER_SELF_HOSTED_LEGACY
        ):
            return PlanTierChangeType.DOWNGRADE
        elif (
            current_plan_tier == CustomerPlan.TIER_SELF_HOSTED_BUSINESS
            and new_plan_tier == CustomerPlan.TIER_SELF_HOSTED_LEGACY
        ):
            return PlanTierChangeType.DOWNGRADE
        else:
            assert current_plan_tier == CustomerPlan.TIER_SELF_HOSTED_BUSINESS
            assert new_plan_tier == CustomerPlan.TIER_SELF_HOSTED_BASIC
            return PlanTierChangeType.DOWNGRADE

    @override
    def has_billing_access(self) -> bool:  # nocoverage
        # We don't currently have a way to authenticate a remote
        # session that isn't authorized for billing access.
        return True

    PAID_PLANS = [
        RemoteRealm.PLAN_TYPE_BASIC,
        RemoteRealm.PLAN_TYPE_BUSINESS,
        RemoteRealm.PLAN_TYPE_ENTERPRISE,
    ]

    @override
    def on_paid_plan(self) -> bool:  # nocoverage
        return self.remote_realm.plan_type in self.PAID_PLANS

    @override
    def org_name(self) -> str:
        return self.remote_realm.host

    @override
    def add_sponsorship_info_to_context(self, context: Dict[str, Any]) -> None:
        context.update(
            realm_org_type=self.remote_realm.org_type,
            sorted_org_types=sorted(
                (
                    [org_type_name, org_type]
                    for (org_type_name, org_type) in Realm.ORG_TYPES.items()
                    if not org_type.get("hidden")
                ),
                key=sponsorship_org_type_key_helper,
            ),
        )

    @override
    def get_sponsorship_request_session_specific_context(
        self,
    ) -> SponsorshipRequestSessionSpecificContext:  # nocoverage
        assert self.remote_billing_user is not None
        return SponsorshipRequestSessionSpecificContext(
            realm_user=None,
            user_info=SponsorshipApplicantInfo(
                name=self.remote_billing_user.full_name,
                email=self.get_email(),
                # We don't have role data for the user.
                role="Remote realm administrator",
            ),
            # TODO: Check if this works on support page.
            realm_string_id=self.remote_realm.host,
        )

    @override
    def save_org_type_from_request_sponsorship_session(self, org_type: int) -> None:  # nocoverage
        if self.remote_realm.org_type != org_type:
            self.remote_realm.org_type = org_type
            self.remote_realm.save(update_fields=["org_type"])

    @override
    def sync_license_ledger_if_needed(self) -> None:
        last_ledger = self.get_last_ledger_for_automanaged_plan_if_exists()
        if last_ledger is None:
            return

        # New audit logs since last_ledger for the plan was created.
        new_audit_logs = (
            RemoteRealmAuditLog.objects.filter(
                remote_realm=self.remote_realm,
                event_time__gt=last_ledger.event_time,
                event_type__in=RemoteRealmAuditLog.SYNCED_BILLING_EVENTS,
            )
            .exclude(extra_data={})
            .order_by("event_time")
        )

        current_plan = last_ledger.plan
        for audit_log in new_audit_logs:
            end_of_cycle_plan = self.update_license_ledger_for_automanaged_plan(
                current_plan, audit_log.event_time
            )
            if end_of_cycle_plan is None:
                return  # nocoverage
            current_plan = end_of_cycle_plan


class RemoteServerBillingSession(BillingSession):
    """Billing session for pre-8.0 servers that do not yet support
    creating RemoteRealm objects."""

    def __init__(
        self,
        remote_server: RemoteZulipServer,
        remote_billing_user: Optional[RemoteServerBillingUser] = None,
        support_staff: Optional[UserProfile] = None,
    ) -> None:
        self.remote_server = remote_server
        self.remote_billing_user = remote_billing_user
        self.support_staff = support_staff
        if support_staff is not None:  # nocoverage
            assert support_staff.is_staff
            self.support_session = True
        else:
            self.support_session = False

    @override
    @property
    def billing_entity_display_name(self) -> str:  # nocoverage
        return self.remote_server.hostname

    @override
    @property
    def billing_session_url(self) -> str:  # nocoverage
        return f"{settings.EXTERNAL_URI_SCHEME}{settings.SELF_HOSTING_MANAGEMENT_SUBDOMAIN}.{settings.EXTERNAL_HOST}/server/{self.remote_server.uuid}"

    @override
    @property
    def billing_base_url(self) -> str:
        return f"/server/{self.remote_server.uuid}"

    @override
    def support_url(self) -> str:  # nocoverage
        return build_support_url("remote_servers_support", str(self.remote_server.uuid))

    @override
    def get_customer(self) -> Optional[Customer]:
        return get_customer_by_remote_server(self.remote_server)

    @override
    def get_email(self) -> str:
        assert self.remote_billing_user is not None
        return self.remote_billing_user.email

    @override
    def current_count_for_billed_licenses(self, event_time: datetime = timezone_now()) -> int:
        if has_stale_audit_log(self.remote_server):
            raise MissingDataError
        remote_server_counts = get_remote_server_guest_and_non_guest_count(
            self.remote_server.id, event_time
        )
        return remote_server_counts.non_guest_user_count + remote_server_counts.guest_user_count

    def missing_data_error_page(self, request: HttpRequest) -> HttpResponse:  # nocoverage
        # The remedy for a RemoteZulipServer login is usually
        # upgrading to Zulip 8.0 or enabling SUBMIT_USAGE_STATISTICS.
        missing_data_context = {
            "remote_realm_session": False,
            "supports_remote_realms": self.remote_server.last_api_feature_level is not None,
        }
        return render(
            request,
            "corporate/billing/server_not_uploading_data.html",
            context=missing_data_context,
        )

    @override
    def get_audit_log_event(self, event_type: AuditLogEventType) -> int:
        if event_type is AuditLogEventType.STRIPE_CUSTOMER_CREATED:
            return RemoteZulipServerAuditLog.STRIPE_CUSTOMER_CREATED
        elif event_type is AuditLogEventType.STRIPE_CARD_CHANGED:
            return RemoteZulipServerAuditLog.STRIPE_CARD_CHANGED
        elif event_type is AuditLogEventType.CUSTOMER_PLAN_CREATED:
            return RemoteZulipServerAuditLog.CUSTOMER_PLAN_CREATED
        elif event_type is AuditLogEventType.DISCOUNT_CHANGED:
            return RemoteZulipServerAuditLog.REMOTE_SERVER_DISCOUNT_CHANGED  # nocoverage
        elif event_type is AuditLogEventType.CUSTOMER_PROPERTY_CHANGED:
            return RemoteZulipServerAuditLog.CUSTOMER_PROPERTY_CHANGED  # nocoverage
        elif event_type is AuditLogEventType.SPONSORSHIP_APPROVED:
            return RemoteZulipServerAuditLog.REMOTE_SERVER_SPONSORSHIP_APPROVED
        elif event_type is AuditLogEventType.SPONSORSHIP_PENDING_STATUS_CHANGED:
            return RemoteZulipServerAuditLog.REMOTE_SERVER_SPONSORSHIP_PENDING_STATUS_CHANGED
        elif event_type is AuditLogEventType.BILLING_MODALITY_CHANGED:
            return RemoteZulipServerAuditLog.REMOTE_SERVER_BILLING_MODALITY_CHANGED  # nocoverage
        elif event_type is AuditLogEventType.CUSTOMER_PLAN_PROPERTY_CHANGED:
            return RemoteZulipServerAuditLog.CUSTOMER_PLAN_PROPERTY_CHANGED  # nocoverage
        elif event_type is AuditLogEventType.BILLING_ENTITY_PLAN_TYPE_CHANGED:
            return RemoteZulipServerAuditLog.REMOTE_SERVER_PLAN_TYPE_CHANGED
        elif (
            event_type is AuditLogEventType.CUSTOMER_SWITCHED_FROM_MONTHLY_TO_ANNUAL_PLAN
        ):  # nocoverage
            return RemoteZulipServerAuditLog.CUSTOMER_SWITCHED_FROM_MONTHLY_TO_ANNUAL_PLAN
        elif (
            event_type is AuditLogEventType.CUSTOMER_SWITCHED_FROM_ANNUAL_TO_MONTHLY_PLAN
        ):  # nocoverage
            return RemoteZulipServerAuditLog.CUSTOMER_SWITCHED_FROM_ANNUAL_TO_MONTHLY_PLAN
        else:  # nocoverage
            raise BillingSessionAuditLogEventError(event_type)

    @override
    def write_to_audit_log(
        self,
        event_type: AuditLogEventType,
        event_time: datetime,
        *,
        background_update: bool = False,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        audit_log_event = self.get_audit_log_event(event_type)
        log_data = {
            "server": self.remote_server,
            "event_type": audit_log_event,
            "event_time": event_time,
        }

        if not background_update:
            log_data.update(
                {
                    # At most one of these should be set, but we may
                    # not want an assert for that yet:
                    "acting_support_user": self.support_staff,
                    "acting_remote_user": self.remote_billing_user,
                }
            )

        if extra_data:
            log_data["extra_data"] = extra_data

        RemoteZulipServerAuditLog.objects.create(**log_data)

    @override
    def get_data_for_stripe_customer(self) -> StripeCustomerData:
        # Support requests do not set any stripe billing information.
        assert self.support_session is False
        metadata: Dict[str, Any] = {}
        metadata["remote_server_uuid"] = self.remote_server.uuid
        metadata["remote_server_str"] = str(self.remote_server)
        realm_stripe_customer_data = StripeCustomerData(
            description=str(self.remote_server),
            email=self.get_email(),
            metadata=metadata,
        )
        return realm_stripe_customer_data

    @override
    def update_data_for_checkout_session_and_invoice_payment(
        self, metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        assert self.remote_billing_user is not None
        updated_metadata = dict(
            remote_server_user_id=self.remote_billing_user.id,
            remote_server_user_email=self.get_email(),
            remote_server_host=self.remote_server.hostname,
            **metadata,
        )
        return updated_metadata

    @override
    def update_or_create_customer(
        self, stripe_customer_id: Optional[str] = None, *, defaults: Optional[Dict[str, Any]] = None
    ) -> Customer:
        if stripe_customer_id is not None:
            # Support requests do not set any stripe billing information.
            assert self.support_session is False
            customer, created = Customer.objects.update_or_create(
                remote_server=self.remote_server,
                defaults={"stripe_customer_id": stripe_customer_id},
            )
        else:
            customer, created = Customer.objects.update_or_create(
                remote_server=self.remote_server, defaults=defaults
            )

        if created and not customer.default_discount:
            customer.flat_discounted_months = 12
            customer.save(update_fields=["flat_discounted_months"])

        return customer

    @override
    @transaction.atomic
    def do_change_plan_type(
        self, *, tier: Optional[int], is_sponsored: bool = False, background_update: bool = False
    ) -> None:
        # This function needs to translate between the different
        # formats of CustomerPlan.tier and RealmZulipServer.plan_type.
        if is_sponsored:
            plan_type = RemoteZulipServer.PLAN_TYPE_COMMUNITY
            self.add_customer_to_community_plan()
        elif tier == CustomerPlan.TIER_SELF_HOSTED_BASIC:
            plan_type = RemoteZulipServer.PLAN_TYPE_BASIC
        elif tier == CustomerPlan.TIER_SELF_HOSTED_BUSINESS:
            plan_type = RemoteZulipServer.PLAN_TYPE_BUSINESS
        elif tier == CustomerPlan.TIER_SELF_HOSTED_LEGACY:
            plan_type = RemoteZulipServer.PLAN_TYPE_SELF_MANAGED_LEGACY
        else:
            raise AssertionError("Unexpected tier")

        old_plan_type = self.remote_server.plan_type
        self.remote_server.plan_type = plan_type
        self.remote_server.save(update_fields=["plan_type"])
        self.write_to_audit_log(
            event_type=AuditLogEventType.BILLING_ENTITY_PLAN_TYPE_CHANGED,
            event_time=timezone_now(),
            extra_data={"old_value": old_plan_type, "new_value": plan_type},
            background_update=background_update,
        )

    @override
    def approve_sponsorship(self) -> str:  # nocoverage
        # Sponsorship approval is only a support admin action.
        assert self.support_session

        # Check no realm has a current plan, which would mean
        # approving this sponsorship would violate our invariant that
        # we never have active plans for both a remote realm and its
        # remote server.
        realm_plans = CustomerPlan.objects.filter(
            customer__remote_realm__server=self.remote_server
        ).exclude(status=CustomerPlan.ENDED)
        if realm_plans.exists():
            return "Cannot approve server-level Community plan while some realms active plans."

        customer = self.get_customer()
        if customer is not None:
            error_message = self.check_customer_not_on_paid_plan(customer)
            if error_message != "":
                raise SupportRequestError(error_message)

            if self.remote_server.plan_type == RemoteZulipServer.PLAN_TYPE_SELF_MANAGED_LEGACY:
                plan = get_current_plan_by_customer(customer)
                # Ideally we should have always have a plan here but since this is support page, we can be lenient about it.
                if plan is not None:
                    assert self.get_next_plan(plan) is None
                    assert plan.tier == CustomerPlan.TIER_SELF_HOSTED_LEGACY
                    plan.status = CustomerPlan.ENDED
                    plan.save(update_fields=["status"])

        self.do_change_plan_type(tier=None, is_sponsored=True)
        if customer is not None and customer.sponsorship_pending:
            customer.sponsorship_pending = False
            customer.save(update_fields=["sponsorship_pending"])
            self.write_to_audit_log(
                event_type=AuditLogEventType.SPONSORSHIP_APPROVED, event_time=timezone_now()
            )
        billing_emails = list(
            RemoteServerBillingUser.objects.filter(remote_server=self.remote_server).values_list(
                "email", flat=True
            )
        )
        if len(billing_emails) > 0:
            send_email(
                "zerver/emails/sponsorship_approved_community_plan",
                to_emails=billing_emails,
                from_address=BILLING_SUPPORT_EMAIL,
                context={
                    "billing_entity": self.billing_entity_display_name,
                    "plans_link": "https://zulip.com/plans/#self-hosted",
                    "link_to_zulip": "https://zulip.com/help/linking-to-zulip-website",
                },
            )
            emailed_string = "Emailed existing billing users."
        else:
            emailed_string = "No billing users exist to email."

        return f"Sponsorship approved for {self.billing_entity_display_name}; " + emailed_string

    @override
    def process_downgrade(
        self, plan: CustomerPlan, background_update: bool = False
    ) -> None:  # nocoverage
        with transaction.atomic():
            old_plan_type = self.remote_server.plan_type
            new_plan_type = RemoteZulipServer.PLAN_TYPE_SELF_MANAGED
            self.remote_server.plan_type = new_plan_type
            self.remote_server.save(update_fields=["plan_type"])
            self.write_to_audit_log(
                event_type=AuditLogEventType.BILLING_ENTITY_PLAN_TYPE_CHANGED,
                event_time=timezone_now(),
                extra_data={"old_value": old_plan_type, "new_value": new_plan_type},
                background_update=background_update,
            )

        plan.status = CustomerPlan.ENDED
        plan.save(update_fields=["status"])

    @override
    def is_sponsored(self) -> bool:
        return self.remote_server.plan_type == self.remote_server.PLAN_TYPE_COMMUNITY

    @override
    def get_metadata_for_stripe_update_card(self) -> Dict[str, str]:  # nocoverage
        assert self.remote_billing_user is not None
        return {"type": "card_update", "remote_server_user_id": str(self.remote_billing_user.id)}

    @override
    def get_upgrade_page_session_type_specific_context(
        self,
    ) -> UpgradePageSessionTypeSpecificContext:
        return UpgradePageSessionTypeSpecificContext(
            customer_name=self.remote_server.hostname,
            email=self.get_email(),
            is_demo_organization=False,
            demo_organization_scheduled_deletion_date=None,
            is_self_hosting=True,
        )

    @override
    def check_plan_tier_is_billable(self, plan_tier: int) -> bool:  # nocoverage
        implemented_plan_tiers = [
            CustomerPlan.TIER_SELF_HOSTED_BASIC,
            CustomerPlan.TIER_SELF_HOSTED_BUSINESS,
        ]
        if plan_tier in implemented_plan_tiers:
            return True
        return False

    @override
    def get_type_of_plan_tier_change(
        self, current_plan_tier: int, new_plan_tier: int
    ) -> PlanTierChangeType:  # nocoverage
        valid_plan_tiers = [
            CustomerPlan.TIER_SELF_HOSTED_LEGACY,
            CustomerPlan.TIER_SELF_HOSTED_BASIC,
            CustomerPlan.TIER_SELF_HOSTED_BUSINESS,
        ]
        if (
            current_plan_tier not in valid_plan_tiers
            or new_plan_tier not in valid_plan_tiers
            or current_plan_tier == new_plan_tier
        ):
            return PlanTierChangeType.INVALID

        if current_plan_tier == CustomerPlan.TIER_SELF_HOSTED_LEGACY and new_plan_tier in (
            CustomerPlan.TIER_SELF_HOSTED_BASIC,
            CustomerPlan.TIER_SELF_HOSTED_BUSINESS,
        ):
            return PlanTierChangeType.UPGRADE
        elif (
            current_plan_tier == CustomerPlan.TIER_SELF_HOSTED_BASIC
            and new_plan_tier == CustomerPlan.TIER_SELF_HOSTED_BUSINESS
        ):
            return PlanTierChangeType.UPGRADE
        elif (
            current_plan_tier == CustomerPlan.TIER_SELF_HOSTED_BASIC
            and new_plan_tier == CustomerPlan.TIER_SELF_HOSTED_LEGACY
        ):
            return PlanTierChangeType.DOWNGRADE
        elif (
            current_plan_tier == CustomerPlan.TIER_SELF_HOSTED_BUSINESS
            and new_plan_tier == CustomerPlan.TIER_SELF_HOSTED_LEGACY
        ):
            return PlanTierChangeType.DOWNGRADE
        else:
            assert current_plan_tier == CustomerPlan.TIER_SELF_HOSTED_BUSINESS
            assert new_plan_tier == CustomerPlan.TIER_SELF_HOSTED_BASIC
            return PlanTierChangeType.DOWNGRADE

    @override
    def has_billing_access(self) -> bool:
        # We don't currently have a way to authenticate a remote
        # session that isn't authorized for billing access.
        return True

    PAID_PLANS = [
        RemoteZulipServer.PLAN_TYPE_BASIC,
        RemoteZulipServer.PLAN_TYPE_BUSINESS,
        RemoteZulipServer.PLAN_TYPE_ENTERPRISE,
    ]

    @override
    def on_paid_plan(self) -> bool:  # nocoverage
        return self.remote_server.plan_type in self.PAID_PLANS

    @override
    def org_name(self) -> str:
        return self.remote_server.hostname

    @override
    def add_sponsorship_info_to_context(self, context: Dict[str, Any]) -> None:  # nocoverage
        context.update(
            realm_org_type=self.remote_server.org_type,
            sorted_org_types=sorted(
                (
                    [org_type_name, org_type]
                    for (org_type_name, org_type) in Realm.ORG_TYPES.items()
                    if not org_type.get("hidden")
                ),
                key=sponsorship_org_type_key_helper,
            ),
        )

    @override
    def get_sponsorship_request_session_specific_context(
        self,
    ) -> SponsorshipRequestSessionSpecificContext:  # nocoverage
        assert self.remote_billing_user is not None
        return SponsorshipRequestSessionSpecificContext(
            realm_user=None,
            user_info=SponsorshipApplicantInfo(
                name=self.remote_billing_user.full_name,
                email=self.get_email(),
                # We don't have role data for the user.
                role="Remote server administrator",
            ),
            # TODO: Check if this works on support page.
            realm_string_id=self.remote_server.hostname,
        )

    @override
    def save_org_type_from_request_sponsorship_session(self, org_type: int) -> None:  # nocoverage
        if self.remote_server.org_type != org_type:
            self.remote_server.org_type = org_type
            self.remote_server.save(update_fields=["org_type"])

    @override
    def sync_license_ledger_if_needed(self) -> None:
        last_ledger = self.get_last_ledger_for_automanaged_plan_if_exists()
        if last_ledger is None:
            return

        # New audit logs since last_ledger for the plan was created.
        new_audit_logs = (
            RemoteRealmAuditLog.objects.filter(
                server=self.remote_server,
                event_time__gt=last_ledger.event_time,
                event_type__in=RemoteRealmAuditLog.SYNCED_BILLING_EVENTS,
            )
            .exclude(extra_data={})
            .order_by("event_time")
        )

        current_plan = last_ledger.plan
        for audit_log in new_audit_logs:
            end_of_cycle_plan = self.update_license_ledger_for_automanaged_plan(
                current_plan, audit_log.event_time
            )
            if end_of_cycle_plan is None:  # nocoverage
                return
            current_plan = end_of_cycle_plan


def stripe_customer_has_credit_card_as_default_payment_method(
    stripe_customer: stripe.Customer,
) -> bool:
    assert stripe_customer.invoice_settings is not None
    if not stripe_customer.invoice_settings.default_payment_method:
        return False
    assert isinstance(stripe_customer.invoice_settings.default_payment_method, stripe.PaymentMethod)
    return stripe_customer.invoice_settings.default_payment_method.type == "card"


def customer_has_credit_card_as_default_payment_method(customer: Customer) -> bool:
    if not customer.stripe_customer_id:
        return False
    stripe_customer = stripe_get_customer(customer.stripe_customer_id)
    return stripe_customer_has_credit_card_as_default_payment_method(stripe_customer)


def calculate_discounted_price_per_license(
    original_price_per_license: int, discount: Decimal
) -> int:
    # There are no fractional cents in Stripe, so round down to nearest integer.
    return int(float(original_price_per_license * (1 - discount / 100)) + 0.00001)


def get_price_per_license(
    tier: int, billing_schedule: int, discount: Optional[Decimal] = None
) -> int:
    price_map: Dict[int, Dict[str, int]] = {
        CustomerPlan.TIER_CLOUD_STANDARD: {"Annual": 8000, "Monthly": 800},
        CustomerPlan.TIER_CLOUD_PLUS: {"Annual": 12000, "Monthly": 1200},
        CustomerPlan.TIER_SELF_HOSTED_BASIC: {"Annual": 4200, "Monthly": 350},
        CustomerPlan.TIER_SELF_HOSTED_BUSINESS: {"Annual": 8000, "Monthly": 800},
        # To help with processing discount request on support page.
        CustomerPlan.TIER_SELF_HOSTED_LEGACY: {"Annual": 0, "Monthly": 0},
    }

    try:
        price_per_license = price_map[tier][CustomerPlan.BILLING_SCHEDULES[billing_schedule]]
    except KeyError:
        if tier not in price_map:
            raise InvalidTierError(tier)
        else:  # nocoverage
            raise InvalidBillingScheduleError(billing_schedule)

    if discount is not None:
        price_per_license = calculate_discounted_price_per_license(price_per_license, discount)
    return price_per_license


def compute_plan_parameters(
    tier: int,
    billing_schedule: int,
    discount: Optional[Decimal],
    free_trial: bool = False,
    billing_cycle_anchor: Optional[datetime] = None,
    is_self_hosted_billing: bool = False,
    should_schedule_upgrade_for_legacy_remote_server: bool = False,
) -> Tuple[datetime, datetime, datetime, int]:
    # Everything in Stripe is stored as timestamps with 1 second resolution,
    # so standardize on 1 second resolution.
    # TODO talk about leap seconds?
    if billing_cycle_anchor is None:
        billing_cycle_anchor = timezone_now().replace(microsecond=0)

    if billing_schedule == CustomerPlan.BILLING_SCHEDULE_ANNUAL:
        period_end = add_months(billing_cycle_anchor, 12)
    elif billing_schedule == CustomerPlan.BILLING_SCHEDULE_MONTHLY:
        period_end = add_months(billing_cycle_anchor, 1)
    else:  # nocoverage
        raise InvalidBillingScheduleError(billing_schedule)

    price_per_license = get_price_per_license(tier, billing_schedule, discount)

    # `next_invoice_date` is the date when we check if there are any invoices that need to be generated.
    # It is always the next month regardless of the billing schedule / billing modality.
    next_invoice_date = add_months(billing_cycle_anchor, 1)
    if free_trial:
        period_end = billing_cycle_anchor + timedelta(
            days=assert_is_not_none(get_free_trial_days(is_self_hosted_billing, tier))
        )
        next_invoice_date = period_end
    if should_schedule_upgrade_for_legacy_remote_server:
        next_invoice_date = billing_cycle_anchor
    return billing_cycle_anchor, next_invoice_date, period_end, price_per_license


def get_free_trial_days(
    is_self_hosted_billing: bool = False, tier: Optional[int] = None
) -> Optional[int]:
    if is_self_hosted_billing:
        # Free trial is only available for self-hosted basic plan.
        if tier is not None and tier != CustomerPlan.TIER_SELF_HOSTED_BASIC:
            return None
        return settings.SELF_HOSTING_FREE_TRIAL_DAYS

    return settings.CLOUD_FREE_TRIAL_DAYS


def is_free_trial_offer_enabled(is_self_hosted_billing: bool, tier: Optional[int] = None) -> bool:
    return get_free_trial_days(is_self_hosted_billing, tier) not in (None, 0)


def ensure_customer_does_not_have_active_plan(customer: Customer) -> None:
    if get_current_plan_by_customer(customer) is not None:
        # Unlikely race condition from two people upgrading (clicking "Make payment")
        # at exactly the same time. Doesn't fully resolve the race condition, but having
        # a check here reduces the likelihood.
        billing_logger.warning(
            "Upgrade of %s failed because of existing active plan.",
            str(customer),
        )
        raise UpgradeWithExistingPlanError


@transaction.atomic
def do_reactivate_remote_server(remote_server: RemoteZulipServer) -> None:
    """
    Utility function for reactivating deactivated registrations.
    """

    if not remote_server.deactivated:
        billing_logger.warning(
            "Cannot reactivate remote server with ID %d, server is already active.",
            remote_server.id,
        )
        return

    remote_server.deactivated = False
    remote_server.save(update_fields=["deactivated"])
    RemoteZulipServerAuditLog.objects.create(
        event_type=RealmAuditLog.REMOTE_SERVER_REACTIVATED,
        server=remote_server,
        event_time=timezone_now(),
    )


@transaction.atomic
def do_deactivate_remote_server(
    remote_server: RemoteZulipServer, billing_session: RemoteServerBillingSession
) -> None:
    if remote_server.deactivated:
        billing_logger.warning(
            "Cannot deactivate remote server with ID %d, server has already been deactivated.",
            remote_server.id,
        )
        return

    server_plans_to_consider = CustomerPlan.objects.filter(
        customer__remote_server=remote_server
    ).exclude(status=CustomerPlan.ENDED)
    realm_plans_to_consider = CustomerPlan.objects.filter(
        customer__remote_realm__server=remote_server
    ).exclude(status=CustomerPlan.ENDED)

    for possible_plan in list(server_plans_to_consider) + list(realm_plans_to_consider):
        if possible_plan.tier in [
            CustomerPlan.TIER_SELF_HOSTED_BASE,
            CustomerPlan.TIER_SELF_HOSTED_LEGACY,
            CustomerPlan.TIER_SELF_HOSTED_COMMUNITY,
        ]:  # nocoverage
            # No action required for free plans.
            continue

        if possible_plan.status in [
            CustomerPlan.DOWNGRADE_AT_END_OF_FREE_TRIAL,
            CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE,
        ]:  # nocoverage
            # No action required for plans scheduled to downgrade
            # automatically.
            continue

        # This customer has some sort of paid plan; ask the customer
        # to downgrade their paid plan so that they get the
        # communication in that flow, and then they can come back and
        # deactivate their server.
        raise ServerDeactivateWithExistingPlanError  # nocoverage

    remote_server.deactivated = True
    remote_server.save(update_fields=["deactivated"])
    RemoteZulipServerAuditLog.objects.create(
        event_type=RealmAuditLog.REMOTE_SERVER_DEACTIVATED,
        server=remote_server,
        event_time=timezone_now(),
    )


def get_plan_renewal_or_end_date(plan: CustomerPlan, event_time: datetime) -> datetime:
    billing_period_end = start_of_next_billing_cycle(plan, event_time)

    if plan.end_date is not None and plan.end_date < billing_period_end:
        return plan.end_date
    return billing_period_end


def invoice_plans_as_needed(event_time: Optional[datetime] = None) -> None:
    if event_time is None:
        event_time = timezone_now()
    # For self hosted legacy plan with status SWITCH_PLAN_TIER_AT_PLAN_END, we need
    # to invoice legacy plan followed by new plan on the same day, hence ordered by ID.
    for plan in CustomerPlan.objects.filter(next_invoice_date__lte=event_time).order_by("id"):
        remote_server: Optional[RemoteZulipServer] = None
        if plan.customer.realm is not None:
            billing_session: BillingSession = RealmBillingSession(realm=plan.customer.realm)
        elif plan.customer.remote_realm is not None:
            remote_realm = plan.customer.remote_realm
            remote_server = remote_realm.server
            billing_session = RemoteRealmBillingSession(remote_realm=remote_realm)
        elif plan.customer.remote_server is not None:
            remote_server = plan.customer.remote_server
            billing_session = RemoteServerBillingSession(remote_server=remote_server)

        assert plan.next_invoice_date is not None  # for mypy

        if remote_server:
            if (
                plan.fixed_price is not None
                and not plan.reminder_to_review_plan_email_sent
                and plan.end_date is not None  # for mypy
                # The max gap between two months is 62 days. (1 Jul - 1 Sep)
                and plan.end_date - plan.next_invoice_date <= timedelta(days=62)
            ):
                context = {
                    "billing_entity": billing_session.billing_entity_display_name,
                    "end_date": plan.end_date.strftime("%Y-%m-%d"),
                    "support_url": billing_session.support_url(),
                    "notice_reason": "fixed_price_plan_ends_soon",
                }
                send_email(
                    "zerver/emails/internal_billing_notice",
                    to_emails=[BILLING_SUPPORT_EMAIL],
                    from_address=FromAddress.tokenized_no_reply_address(),
                    context=context,
                )
                plan.reminder_to_review_plan_email_sent = True
                plan.save(update_fields=["reminder_to_review_plan_email_sent"])

            free_plan_with_no_next_plan = (
                not plan.is_a_paid_plan() and plan.status == CustomerPlan.ACTIVE
            )
            free_trial_pay_by_invoice_plan = plan.is_free_trial() and not plan.charge_automatically
            last_audit_log_update = remote_server.last_audit_log_update
            if not free_plan_with_no_next_plan and (
                last_audit_log_update is None or plan.next_invoice_date > last_audit_log_update
            ):
                if (
                    last_audit_log_update is None
                    or plan.next_invoice_date - last_audit_log_update >= timedelta(days=1)
                ) and not plan.invoice_overdue_email_sent:
                    last_audit_log_update_string = "Never uploaded"
                    if last_audit_log_update is not None:
                        last_audit_log_update_string = last_audit_log_update.strftime("%Y-%m-%d")
                    context = {
                        "billing_entity": billing_session.billing_entity_display_name,
                        "support_url": billing_session.support_url(),
                        "last_audit_log_update": last_audit_log_update_string,
                        "notice_reason": "invoice_overdue",
                    }
                    send_email(
                        "zerver/emails/internal_billing_notice",
                        to_emails=[BILLING_SUPPORT_EMAIL],
                        from_address=FromAddress.tokenized_no_reply_address(),
                        context=context,
                    )
                    plan.invoice_overdue_email_sent = True
                    plan.save(update_fields=["invoice_overdue_email_sent"])

                # We still process free trial plans so that we can directly downgrade them.
                # Above emails can serve as a reminder to followup for additional feedback.
                if not free_trial_pay_by_invoice_plan:
                    continue

        while (
            plan.next_invoice_date is not None  # type: ignore[redundant-expr] # plan.next_invoice_date can be None after calling invoice_plan.
            and plan.next_invoice_date <= event_time
        ):
            billing_session.invoice_plan(plan, plan.next_invoice_date)
            plan.refresh_from_db()


def is_realm_on_free_trial(realm: Realm) -> bool:
    plan = get_current_plan_by_realm(realm)
    return plan is not None and plan.is_free_trial()


def do_change_plan_status(plan: CustomerPlan, status: int) -> None:
    plan.status = status
    plan.save(update_fields=["status"])
    billing_logger.info(
        "Change plan status: Customer.id: %s, CustomerPlan.id: %s, status: %s",
        plan.customer.id,
        plan.id,
        status,
    )


def get_all_invoices_for_customer(customer: Customer) -> Generator[stripe.Invoice, None, None]:
    if customer.stripe_customer_id is None:
        return

    invoices = stripe.Invoice.list(customer=customer.stripe_customer_id, limit=100)
    while len(invoices):
        for invoice in invoices:
            yield invoice
            last_invoice = invoice
        assert last_invoice.id is not None
        invoices = stripe.Invoice.list(
            customer=customer.stripe_customer_id, starting_after=last_invoice.id, limit=100
        )


def customer_has_last_n_invoices_open(customer: Customer, n: int) -> bool:
    if customer.stripe_customer_id is None:  # nocoverage
        return False

    open_invoice_count = 0
    for invoice in stripe.Invoice.list(customer=customer.stripe_customer_id, limit=n):
        if invoice.status == "open":
            open_invoice_count += 1
    return open_invoice_count == n


def downgrade_small_realms_behind_on_payments_as_needed() -> None:
    customers = Customer.objects.all().exclude(stripe_customer_id=None).exclude(realm=None)
    for customer in customers:
        realm = customer.realm
        assert realm is not None

        # For larger realms, we generally want to talk to the customer
        # before downgrading or cancelling invoices; so this logic only applies with 5.
        if get_latest_seat_count(realm) >= 5:
            continue

        if get_current_plan_by_customer(customer) is not None:
            # Only customers with last 2 invoices open should be downgraded.
            if not customer_has_last_n_invoices_open(customer, 2):
                continue

            # We've now decided to downgrade this customer and void all invoices, and the below will execute this.
            billing_session = RealmBillingSession(user=None, realm=realm)
            billing_session.downgrade_now_without_creating_additional_invoices()
            billing_session.void_all_open_invoices()
            context: Dict[str, Union[str, Realm]] = {
                "upgrade_url": f"{realm.uri}{reverse('upgrade_page')}",
                "realm": realm,
            }
            send_email_to_billing_admins_and_realm_owners(
                "zerver/emails/realm_auto_downgraded",
                realm,
                from_name=FromAddress.security_email_from_name(language=realm.default_language),
                from_address=FromAddress.tokenized_no_reply_address(),
                language=realm.default_language,
                context=context,
            )
        else:
            if customer_has_last_n_invoices_open(customer, 1):
                # If a small realm, without an active plan, has
                # the last invoice open, void the open invoices.
                billing_session = RealmBillingSession(user=None, realm=realm)
                billing_session.void_all_open_invoices()


@dataclass
class PushNotificationsEnabledStatus:
    can_push: bool
    expected_end_timestamp: Optional[int]

    # Not sent to clients, just for debugging
    message: str


MAX_USERS_WITHOUT_PLAN = 10


def get_push_status_for_remote_request(
    remote_server: RemoteZulipServer, remote_realm: Optional[RemoteRealm]
) -> PushNotificationsEnabledStatus:
    # First, get the operative Customer object for this
    # installation.
    customer = None
    current_plan = None
    realm_billing_session: Optional[BillingSession] = None
    server_billing_session: Optional[RemoteServerBillingSession] = None

    if remote_realm is not None:
        realm_billing_session = RemoteRealmBillingSession(remote_realm)
        if realm_billing_session.is_sponsored():
            return PushNotificationsEnabledStatus(
                can_push=True,
                expected_end_timestamp=None,
                message="Community plan",
            )

        customer = realm_billing_session.get_customer()
        if customer is not None:
            current_plan = get_current_plan_by_customer(customer)

    # If there's a `RemoteRealm` customer with an active plan, that
    # takes precedence, but look for a current plan on the server if
    # there is a customer with only inactive/expired plans on the Realm.
    if customer is None or current_plan is None:
        server_billing_session = RemoteServerBillingSession(remote_server)
        if server_billing_session.is_sponsored():
            return PushNotificationsEnabledStatus(
                can_push=True,
                expected_end_timestamp=None,
                message="Community plan",
            )

        customer = server_billing_session.get_customer()
        if customer is not None:
            current_plan = get_current_plan_by_customer(customer)

    if realm_billing_session is not None:
        user_count_billing_session: BillingSession = realm_billing_session
    else:
        assert server_billing_session is not None
        user_count_billing_session = server_billing_session

    user_count: Optional[int] = None
    if current_plan is None:
        try:
            user_count = user_count_billing_session.current_count_for_billed_licenses()
        except MissingDataError:
            return PushNotificationsEnabledStatus(
                can_push=False,
                expected_end_timestamp=None,
                message="Missing data",
            )

        if user_count > MAX_USERS_WITHOUT_PLAN:
            return PushNotificationsEnabledStatus(
                can_push=False,
                expected_end_timestamp=None,
                message="Push notifications access with 10+ users requires signing up for a plan. https://zulip.com/plans/",
            )

        return PushNotificationsEnabledStatus(
            can_push=True,
            expected_end_timestamp=None,
            message="No plan few users",
        )

    if current_plan.status not in [
        CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE,
        CustomerPlan.DOWNGRADE_AT_END_OF_FREE_TRIAL,
    ]:
        # Current plan, no expected end.
        return PushNotificationsEnabledStatus(
            can_push=True,
            expected_end_timestamp=None,
            message="Active plan",
        )

    try:
        user_count = user_count_billing_session.current_count_for_billed_licenses()
    except MissingDataError:
        user_count = None

    if user_count is not None and user_count <= MAX_USERS_WITHOUT_PLAN:
        # We have an expiring plan, but we know we have few enough
        # users that once the plan expires, we will enter the "No plan
        # few users" case, so don't notify users about the plan
        # expiring via sending expected_end_timestamp.
        return PushNotificationsEnabledStatus(
            can_push=True,
            expected_end_timestamp=None,
            message="Expiring plan few users",
        )

    # TODO: Move get_next_billing_cycle to be plan.get_next_billing_cycle
    # to avoid this somewhat evil use of a possibly non-matching billing session.
    expected_end_timestamp = datetime_to_timestamp(
        user_count_billing_session.get_next_billing_cycle(current_plan)
    )
    return PushNotificationsEnabledStatus(
        can_push=True,
        expected_end_timestamp=expected_end_timestamp,
        message="Scheduled end",
    )
