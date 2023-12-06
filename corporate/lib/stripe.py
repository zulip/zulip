import logging
import math
import os
import secrets
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, Generator, Optional, Tuple, TypedDict, TypeVar, Union
from urllib.parse import urlencode, urljoin

import stripe
from django import forms
from django.conf import settings
from django.core import signing
from django.core.signing import Signer
from django.db import transaction
from django.urls import reverse
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.utils.translation import override as override_language
from typing_extensions import ParamSpec, override

from corporate.models import (
    Customer,
    CustomerPlan,
    LicenseLedger,
    PaymentIntent,
    Session,
    ZulipSponsorshipRequest,
    get_current_plan_by_customer,
    get_current_plan_by_realm,
    get_customer_by_realm,
    get_customer_by_remote_realm,
    get_customer_by_remote_server,
)
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
from zerver.models import (
    Realm,
    RealmAuditLog,
    UserProfile,
    get_org_type_display_name,
    get_realm,
    get_system_bot,
)
from zilencer.models import (
    RemoteRealm,
    RemoteRealmAuditLog,
    RemoteZulipServer,
    RemoteZulipServerAuditLog,
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

MIN_INVOICED_LICENSES = 30
MAX_INVOICED_LICENSES = 1000
DEFAULT_INVOICE_DAYS_UNTIL_DUE = 30

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


def format_discount_percentage(discount: Optional[Decimal]) -> Optional[str]:
    if type(discount) is not Decimal or discount == Decimal(0):
        return None

    # Even though it looks like /activity/support only finds integers valid,
    # this will look good for any custom discounts that we apply.
    if discount * 100 % 100 == 0:
        precision = 0
    else:
        precision = 2  # nocoverage
    return f"{discount:.{precision}f}"


def get_latest_seat_count(realm: Realm) -> int:
    return get_seat_count(realm, extra_non_guests_count=0, extra_guests_count=0)


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
) -> None:
    min_licenses = seat_count
    max_licenses = None
    if not charge_automatically:
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
    months_per_period = {
        CustomerPlan.BILLING_SCHEDULE_ANNUAL: 12,
        CustomerPlan.BILLING_SCHEDULE_MONTHLY: 1,
    }[plan.billing_schedule]
    if plan.automanage_licenses:
        months_per_period = 1
    periods = 1
    dt = plan.billing_cycle_anchor
    while dt <= plan.next_invoice_date:
        dt = add_months(plan.billing_cycle_anchor, months_per_period * periods)
        periods += 1
    return dt


def renewal_amount(
    plan: CustomerPlan, event_time: datetime, last_ledger_entry: Optional[LicenseLedger] = None
) -> int:  # nocoverage: TODO
    if plan.fixed_price is not None:
        return plan.fixed_price
    new_plan = None
    if last_ledger_entry is None:
        realm = plan.customer.realm
        billing_session = RealmBillingSession(user=None, realm=realm)
        new_plan, last_ledger_entry = billing_session.make_end_of_cycle_updates_if_needed(
            plan, event_time
        )
    if last_ledger_entry is None:
        return 0
    if last_ledger_entry.licenses_at_next_renewal is None:
        return 0
    if new_plan is not None:
        plan = new_plan
    assert plan.price_per_license is not None  # for mypy
    return plan.price_per_license * last_ledger_entry.licenses_at_next_renewal


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


class BillingError(JsonableError):
    data_fields = ["error_description"]
    # error messages
    CONTACT_SUPPORT = gettext_lazy("Something went wrong. Please contact {email}.")
    TRY_RELOADING = gettext_lazy("Something went wrong. Please reload the page.")

    # description is used only for tests
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


def catch_stripe_errors(func: Callable[ParamT, ReturnT]) -> Callable[ParamT, ReturnT]:
    @wraps(func)
    def wrapped(*args: ParamT.args, **kwargs: ParamT.kwargs) -> ReturnT:
        try:
            return func(*args, **kwargs)
        # See https://stripe.com/docs/api/python#error_handling, though
        # https://stripe.com/docs/api/ruby#error_handling suggests there are additional fields, and
        # https://stripe.com/docs/error-codes gives a more detailed set of error codes
        except stripe.error.StripeError as e:
            assert isinstance(e.json_body, dict)
            err = e.json_body.get("error", {})
            if isinstance(e, stripe.error.CardError):
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
            if isinstance(
                e, (stripe.error.RateLimitError, stripe.error.APIConnectionError)
            ):  # nocoverage TODO
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
class StripePaymentIntentData:
    amount: int
    description: str
    plan_name: str
    email: str


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


@dataclass
class UpdatePlanRequest:
    status: Optional[int]
    licenses: Optional[int]
    licenses_at_next_renewal: Optional[int]
    schedule: Optional[int]


@dataclass
class EventStatusRequest:
    stripe_session_id: Optional[str]
    stripe_payment_intent_id: Optional[str]


class SupportType(Enum):
    approve_sponsorship = 1
    update_sponsorship_status = 2
    attach_discount = 3
    update_billing_modality = 4
    modify_plan = 5


class SupportViewRequest(TypedDict, total=False):
    support_type: SupportType
    sponsorship_status: Optional[bool]
    discount: Optional[Decimal]
    billing_modality: Optional[str]
    plan_modification: Optional[str]
    new_plan_tier: Optional[int]


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


class PlanTierChangeType(Enum):
    INVALID = 1
    UPGRADE = 2
    DOWNGRADE = 3


class BillingSessionAuditLogEventError(Exception):
    def __init__(self, event_type: AuditLogEventType) -> None:
        self.message = f"Unknown audit log event type: {event_type}"
        super().__init__(self.message)


class UpgradePageParams(TypedDict):
    annual_price: int
    demo_organization_scheduled_deletion_date: Optional[datetime]
    monthly_price: int
    seat_count: int
    billing_base_url: str


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
    default_invoice_days_until_due: int
    discount_percent: Optional[str]
    email: str
    exempt_from_license_number_check: bool
    free_trial_days: Optional[int]
    free_trial_end_date: Optional[str]
    is_demo_organization: bool
    manual_license_management: bool
    min_invoiced_licenses: int
    page_params: UpgradePageParams
    payment_method: Optional[str]
    plan: str
    remote_server_legacy_plan_end_date: Optional[str]
    salt: str
    seat_count: int
    signed_seat_count: str


class SponsorshipRequestForm(forms.Form):
    website = forms.URLField(max_length=ZulipSponsorshipRequest.MAX_ORG_URL_LENGTH, required=False)
    organization_type = forms.IntegerField()
    description = forms.CharField(widget=forms.Textarea)
    expected_total_users = forms.CharField(widget=forms.Textarea)
    paid_users_count = forms.CharField(widget=forms.Textarea)
    paid_users_description = forms.CharField(widget=forms.Textarea, required=False)


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
    def current_count_for_billed_licenses(self) -> int:
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
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        pass

    @abstractmethod
    def get_data_for_stripe_customer(self) -> StripeCustomerData:
        pass

    @abstractmethod
    def update_data_for_checkout_session_and_payment_intent(
        self, metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        pass

    def get_data_for_stripe_payment_intent(
        self,
        price_per_license: int,
        licenses: int,
        plan_tier: int,
        email: str,
    ) -> StripePaymentIntentData:
        if hasattr(self, "support_session") and self.support_session:  # nocoverage
            raise BillingError(
                "invalid support session",
                "Support requests do not set any stripe billing information.",
            )

        amount = price_per_license * licenses

        plan_name = CustomerPlan.name_from_tier(plan_tier)
        description = f"Upgrade to {plan_name}, ${price_per_license/100} x {licenses}"
        return StripePaymentIntentData(
            amount=amount,
            description=description,
            plan_name=plan_name,
            email=email,
        )

    @abstractmethod
    def update_or_create_customer(
        self, stripe_customer_id: Optional[str] = None, *, defaults: Optional[Dict[str, Any]] = None
    ) -> Customer:
        pass

    @abstractmethod
    def do_change_plan_type(self, *, tier: Optional[int], is_sponsored: bool = False) -> None:
        pass

    @abstractmethod
    def process_downgrade(self, plan: CustomerPlan) -> None:
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
    def get_metadata_for_stripe_update_card(self) -> Dict[str, Any]:
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
            next_invoice_date=None,
        ).first()

    def get_formatted_remote_server_legacy_plan_end_date(
        self, customer: Optional[Customer], status: int = CustomerPlan.ACTIVE
    ) -> Optional[str]:  # nocoverage
        plan = self.get_remote_server_legacy_plan(customer, status)
        if plan is None:
            return None

        assert plan.end_date is not None
        return plan.end_date.strftime("%B %d, %Y")

    def get_legacy_remote_server_new_plan_name(
        self, customer: Customer
    ) -> Optional[str]:  # nocoverage
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
        ).name

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
            # A stripe.PaymentMethod should be attached to a stripe.Customer via
            # a stripe.SetupIntent or stripe.PaymentIntent. Here we just want to
            # create a new stripe.Customer.
            assert payment_method is None
            # We could do a better job of handling race conditions here, but if two
            # people try to upgrade at exactly the same time, the main bad thing that
            # will happen is that we will create an extra stripe.Customer that we can
            # delete or ignore.
            return self.create_stripe_customer()
        if payment_method is not None:
            self.replace_payment_method(customer.stripe_customer_id, payment_method, True)
        return customer

    def create_stripe_payment_intent(
        self, price_per_license: int, licenses: int, metadata: Dict[str, Any]
    ) -> str:
        # NOTE: This charges users immediately.
        customer = self.get_customer()
        assert customer is not None and customer.stripe_customer_id is not None
        payment_intent_data = self.get_data_for_stripe_payment_intent(
            price_per_license, licenses, metadata["plan_tier"], self.get_email()
        )
        # Ensure customers have a default payment method set.
        stripe_customer = stripe_get_customer(customer.stripe_customer_id)
        if not stripe_customer_has_credit_card_as_default_payment_method(stripe_customer):
            raise BillingError(
                "no payment method",
                "Please add a credit card before upgrading.",
            )

        assert stripe_customer.invoice_settings is not None
        assert stripe_customer.invoice_settings.default_payment_method is not None
        try:
            # Try to charge user immediately, and if that fails, we inform the user about the failure.
            stripe_payment_intent = stripe.PaymentIntent.create(
                amount=payment_intent_data.amount,
                currency="usd",
                customer=customer.stripe_customer_id,
                description=payment_intent_data.description,
                receipt_email=payment_intent_data.email,
                confirm=True,
                statement_descriptor=payment_intent_data.plan_name,
                metadata=metadata,
                off_session=True,
                payment_method=stripe_customer.invoice_settings.default_payment_method,
            )
        except stripe.error.CardError as e:
            raise StripeCardError("card error", e.user_message)

        PaymentIntent.objects.create(
            customer=customer,
            stripe_payment_intent_id=stripe_payment_intent.id,
            status=PaymentIntent.get_status_integer_from_status_text(stripe_payment_intent.status),
        )
        return stripe_payment_intent.id

    def create_card_update_session_for_upgrade(
        self,
        manual_license_management: bool,
    ) -> Dict[str, Any]:
        metadata = self.get_metadata_for_stripe_update_card()
        customer = self.update_or_create_stripe_customer()
        cancel_url = f"{self.billing_session_url}/upgrade/"
        if manual_license_management:
            cancel_url = f"{self.billing_session_url}/upgrade/?manual_license_management=true"

        stripe_session = stripe.checkout.Session.create(
            cancel_url=cancel_url,
            customer=customer.stripe_customer_id,
            metadata=metadata,
            mode="setup",
            payment_method_types=["card"],
            success_url=f"{self.billing_session_url}/billing/event_status?stripe_session_id={{CHECKOUT_SESSION_ID}}",
        )
        Session.objects.create(
            stripe_session_id=stripe_session.id,
            customer=customer,
            type=Session.CARD_UPDATE_FROM_UPGRADE_PAGE,
            is_manual_license_management_upgrade_session=manual_license_management,
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
            success_url=f"{self.billing_session_url}/billing/event_status?stripe_session_id={{CHECKOUT_SESSION_ID}}",
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

    def attach_discount_to_customer(self, new_discount: Decimal) -> str:
        customer = self.get_customer()
        old_discount = None
        if customer is not None:
            old_discount = customer.default_discount
            customer.default_discount = new_discount
            customer.save(update_fields=["default_discount"])
        else:
            customer = self.update_or_create_customer(defaults={"default_discount": new_discount})
        plan = get_current_plan_by_customer(customer)
        if plan is not None:
            plan.price_per_license = get_price_per_license(
                plan.tier, plan.billing_schedule, new_discount
            )
            plan.discount = new_discount
            plan.save(update_fields=["price_per_license", "discount"])
        self.write_to_audit_log(
            event_type=AuditLogEventType.DISCOUNT_CHANGED,
            event_time=timezone_now(),
            extra_data={"old_discount": old_discount, "new_discount": new_discount},
        )
        if old_discount is None:
            old_discount = Decimal(0)
        return f"Discount for {self.billing_entity_display_name} changed to {new_discount}% from {old_discount}%."

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

    def setup_upgrade_payment_intent_and_charge(
        self,
        plan_tier: int,
        seat_count: int,
        licenses: int,
        license_management: str,
        billing_schedule: int,
        billing_modality: str,
    ) -> str:
        customer = self.update_or_create_stripe_customer()
        assert customer is not None  # for mypy
        price_per_license = get_price_per_license(
            plan_tier, billing_schedule, customer.default_discount
        )
        general_metadata = {
            "billing_modality": billing_modality,
            "billing_schedule": billing_schedule,
            "licenses": licenses,
            "license_management": license_management,
            "price_per_license": price_per_license,
            "seat_count": seat_count,
            "type": "upgrade",
            "plan_tier": plan_tier,
        }
        updated_metadata = self.update_data_for_checkout_session_and_payment_intent(
            general_metadata
        )
        stripe_payment_intent_id = self.create_stripe_payment_intent(
            price_per_license, licenses, updated_metadata
        )
        return stripe_payment_intent_id

    def ensure_current_plan_is_upgradable(
        self, customer: Customer, new_plan_tier: int
    ) -> None:  # nocoverage
        # Upgrade for customers with an existing plan is only supported for remote servers right now.
        if not hasattr(self, "remote_server"):
            ensure_customer_does_not_have_active_plan(customer)
            return

        plan = get_current_plan_by_customer(customer)
        assert plan is not None
        type_of_plan_change = self.get_type_of_plan_tier_change(plan.tier, new_plan_tier)
        if type_of_plan_change != PlanTierChangeType.UPGRADE:
            raise InvalidPlanUpgradeError(
                f"Cannot upgrade from {plan.name} to {CustomerPlan.name_from_tier(new_plan_tier)}"
            )

    # Only used for cloud signups
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
    ) -> None:
        customer = self.update_or_create_stripe_customer()
        assert customer.stripe_customer_id is not None  # for mypy
        self.ensure_current_plan_is_upgradable(customer, plan_tier)
        billing_cycle_anchor = None
        if should_schedule_upgrade_for_legacy_remote_server:  # nocoverage
            assert remote_server_legacy_plan is not None
            billing_cycle_anchor = remote_server_legacy_plan.end_date

        (
            billing_cycle_anchor,
            next_invoice_date,
            period_end,
            price_per_license,
        ) = compute_plan_parameters(
            plan_tier,
            automanage_licenses,
            billing_schedule,
            customer.default_discount,
            free_trial,
            billing_cycle_anchor,
        )

        # TODO: The correctness of this relies on user creation, deactivation, etc being
        # in a transaction.atomic() with the relevant RealmAuditLog entries
        with transaction.atomic():
            if customer.exempt_from_license_number_check:
                billed_licenses = licenses
            else:
                # billed_licenses can be greater than licenses if users are added between the start of
                # this function (process_initial_upgrade) and now
                current_licenses_count = self.current_count_for_billed_licenses()
                billed_licenses = max(current_licenses_count, licenses)
            plan_params = {
                "automanage_licenses": automanage_licenses,
                "charge_automatically": charge_automatically,
                "price_per_license": price_per_license,
                "discount": customer.default_discount,
                "billing_cycle_anchor": billing_cycle_anchor,
                "billing_schedule": billing_schedule,
                "tier": plan_tier,
            }
            if free_trial:
                plan_params["status"] = CustomerPlan.FREE_TRIAL

                if charge_automatically:
                    # Ensure free trial customers not paying via invoice have a default payment method set
                    stripe_customer = stripe_get_customer(customer.stripe_customer_id)
                    if not stripe_customer_has_credit_card_as_default_payment_method(
                        stripe_customer
                    ):
                        raise BillingError(
                            "no payment method",
                            _("Please add a credit card before starting your free trial."),
                        )

            event_time = billing_cycle_anchor
            if should_schedule_upgrade_for_legacy_remote_server:  # nocoverage
                # In this code path, we are currently on a legacy plan
                # and are scheduling an upgrade to a non-legacy plan
                # that should occur when the legacy plan expires.
                #
                # We will create a new NEVER_STARTED plan for the
                # customer, scheduled to start when the current one
                # expires.
                assert remote_server_legacy_plan is not None
                if charge_automatically:
                    remote_server_legacy_plan.charge_automatically = True
                    # Ensure customers not paying via invoice have a default payment method set.
                    stripe_customer = stripe_get_customer(customer.stripe_customer_id)
                    if not stripe_customer_has_credit_card_as_default_payment_method(
                        stripe_customer
                    ):
                        raise BillingError(
                            "no payment method",
                            _("Please add a credit card to schedule upgrade."),
                        )

                # Settings status > CustomerPLan.LIVE_STATUS_THRESHOLD makes sure we don't have
                # to worry about this plan being used for any other purpose.
                # NOTE: This is the 2nd plan for the customer.
                plan_params["status"] = CustomerPlan.NEVER_STARTED
                event_time = timezone_now().replace(microsecond=0)

                # Schedule switching to the new plan at plan end date.
                #
                # HACK: We set price_per_license on the legacy plan
                # here in order to make the billing page display
                # something reasonable. We avoid any charges, because
                # next_invoice_date is None for this plan.
                #
                # This hack is a workaround for the billing page not
                # having first-class support for displaying a future
                # NEVER_STARTED plan.
                assert remote_server_legacy_plan.end_date == billing_cycle_anchor
                remote_server_legacy_plan.status = CustomerPlan.SWITCH_PLAN_TIER_AT_PLAN_END
                remote_server_legacy_plan.price_per_license = price_per_license
                remote_server_legacy_plan.save(
                    update_fields=["status", "charge_automatically", "price_per_license"]
                )
            elif remote_server_legacy_plan is not None:  # nocoverage
                remote_server_legacy_plan.status = CustomerPlan.ENDED
                remote_server_legacy_plan.save(update_fields=["status"])

            plan = CustomerPlan.objects.create(
                customer=customer, next_invoice_date=next_invoice_date, **plan_params
            )
            # HACK: In theory, we should be creating these ledger
            # entries only outside the code path for
            # should_schedule_upgrade_for_legacy_remote_server; they
            # exist mainly to help the existing code display accurate
            # information about the second NEVER_STARTED plan on the
            # billing page.
            ledger_entry = LicenseLedger.objects.create(
                plan=plan,
                is_renewal=True,
                event_time=event_time,
                licenses=billed_licenses,
                licenses_at_next_renewal=billed_licenses,
            )
            plan.invoiced_through = ledger_entry
            plan.save(update_fields=["invoiced_through"])
            self.write_to_audit_log(
                event_type=AuditLogEventType.CUSTOMER_PLAN_CREATED,
                event_time=event_time,
                extra_data=plan_params,
            )

        if not (free_trial or should_schedule_upgrade_for_legacy_remote_server):
            assert plan is not None
            stripe.InvoiceItem.create(
                currency="usd",
                customer=customer.stripe_customer_id,
                description=plan.name,
                discountable=False,
                period={
                    "start": datetime_to_timestamp(billing_cycle_anchor),
                    "end": datetime_to_timestamp(period_end),
                },
                quantity=billed_licenses,
                unit_amount=price_per_license,
            )

            if charge_automatically:
                collection_method = "charge_automatically"
                days_until_due = None
            else:
                collection_method = "send_invoice"
                days_until_due = DEFAULT_INVOICE_DAYS_UNTIL_DUE

            stripe_invoice = stripe.Invoice.create(
                auto_advance=True,
                collection_method=collection_method,
                customer=customer.stripe_customer_id,
                days_until_due=days_until_due,
                statement_descriptor=plan.name,
            )
            stripe.Invoice.finalize_invoice(stripe_invoice)

        self.do_change_plan_type(tier=plan_tier)

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
            schedule = "annual"
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
        )
        assert licenses is not None and license_management is not None
        automanage_licenses = license_management == "automatic"
        charge_automatically = billing_modality == "charge_automatically"

        billing_schedule = {
            "annual": CustomerPlan.BILLING_SCHEDULE_ANNUAL,
            "monthly": CustomerPlan.BILLING_SCHEDULE_MONTHLY,
        }[schedule]
        data: Dict[str, Any] = {}
        free_trial = is_free_trial_offer_enabled()
        remote_server_legacy_plan = self.get_remote_server_legacy_plan(customer)
        should_schedule_upgrade_for_legacy_remote_server = (
            remote_server_legacy_plan is not None
            and upgrade_request.remote_server_plan_start_date == "billing_cycle_end_date"
        )
        # Directly upgrade free trial orgs or invoice payment orgs to standard plan.
        if (
            should_schedule_upgrade_for_legacy_remote_server
            or free_trial
            or not charge_automatically
        ):
            self.process_initial_upgrade(
                upgrade_request.tier,
                licenses,
                automanage_licenses,
                billing_schedule,
                charge_automatically,
                is_free_trial_offer_enabled(),
                remote_server_legacy_plan,
                should_schedule_upgrade_for_legacy_remote_server,
            )
            data["organization_upgrade_successful"] = True
        else:
            stripe_payment_intent_id = self.setup_upgrade_payment_intent_and_charge(
                upgrade_request.tier,
                seat_count,
                licenses,
                license_management,
                billing_schedule,
                billing_modality,
            )
            data["stripe_payment_intent_id"] = stripe_payment_intent_id
        return data

    def do_change_schedule_after_free_trial(self, plan: CustomerPlan, schedule: int) -> None:
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
        plan.save(update_fields=["status"])

        discount = plan.customer.default_discount or plan.discount
        _, _, _, price_per_license = compute_plan_parameters(
            tier=plan.tier,
            automanage_licenses=plan.automanage_licenses,
            billing_schedule=schedule,
            discount=plan.discount,
        )

        new_plan = CustomerPlan.objects.create(
            customer=plan.customer,
            billing_schedule=schedule,
            automanage_licenses=plan.automanage_licenses,
            charge_automatically=plan.charge_automatically,
            price_per_license=price_per_license,
            discount=discount,
            billing_cycle_anchor=plan.billing_cycle_anchor,
            tier=plan.tier,
            status=CustomerPlan.FREE_TRIAL,
            next_invoice_date=next_billing_cycle,
            invoiced_through=None,
            invoicing_status=CustomerPlan.INVOICING_STATUS_INITIAL_INVOICE_TO_BE_SENT,
        )

        LicenseLedger.objects.create(
            plan=new_plan,
            is_renewal=True,
            event_time=plan.billing_cycle_anchor,
            licenses=licenses_at_next_renewal,
            licenses_at_next_renewal=licenses_at_next_renewal,
        )

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
        last_ledger_renewal = (
            LicenseLedger.objects.filter(plan=plan, is_renewal=True).order_by("-id").first()
        )
        assert last_ledger_renewal is not None
        last_renewal = last_ledger_renewal.event_time

        if plan.status in (
            CustomerPlan.FREE_TRIAL,
            CustomerPlan.DOWNGRADE_AT_END_OF_FREE_TRIAL,
        ):
            assert plan.next_invoice_date is not None
            next_billing_cycle = plan.next_invoice_date
        elif plan.status == CustomerPlan.SWITCH_PLAN_TIER_AT_PLAN_END:  # nocoverage
            assert plan.end_date is not None
            next_billing_cycle = plan.end_date
        else:
            next_billing_cycle = start_of_next_billing_cycle(plan, last_renewal)

        return next_billing_cycle

    # event_time should roughly be timezone_now(). Not designed to handle
    # event_times in the past or future
    @transaction.atomic
    def make_end_of_cycle_updates_if_needed(
        self, plan: CustomerPlan, event_time: datetime
    ) -> Tuple[Optional[CustomerPlan], Optional[LicenseLedger]]:
        last_ledger_entry = LicenseLedger.objects.filter(plan=plan).order_by("-id").first()
        next_billing_cycle = self.get_next_billing_cycle(plan)
        event_in_next_billing_cycle = next_billing_cycle <= event_time

        if event_in_next_billing_cycle and last_ledger_entry is not None:
            licenses_at_next_renewal = last_ledger_entry.licenses_at_next_renewal
            assert licenses_at_next_renewal is not None
            if plan.status == CustomerPlan.ACTIVE:
                return None, LicenseLedger.objects.create(
                    plan=plan,
                    is_renewal=True,
                    event_time=next_billing_cycle,
                    licenses=licenses_at_next_renewal,
                    licenses_at_next_renewal=licenses_at_next_renewal,
                )
            if plan.is_free_trial():
                plan.invoiced_through = last_ledger_entry
                plan.billing_cycle_anchor = next_billing_cycle.replace(microsecond=0)
                plan.status = CustomerPlan.ACTIVE
                plan.save(update_fields=["invoiced_through", "billing_cycle_anchor", "status"])
                return None, LicenseLedger.objects.create(
                    plan=plan,
                    is_renewal=True,
                    event_time=next_billing_cycle,
                    licenses=licenses_at_next_renewal,
                    licenses_at_next_renewal=licenses_at_next_renewal,
                )

            if plan.status == CustomerPlan.SWITCH_PLAN_TIER_AT_PLAN_END:  # nocoverage
                # Only plan tier we do this for right now.
                assert plan.tier == CustomerPlan.TIER_SELF_HOSTED_LEGACY
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

                discount = plan.customer.default_discount or plan.discount
                _, _, _, price_per_license = compute_plan_parameters(
                    tier=plan.tier,
                    automanage_licenses=plan.automanage_licenses,
                    billing_schedule=CustomerPlan.BILLING_SCHEDULE_ANNUAL,
                    discount=plan.discount,
                )

                new_plan = CustomerPlan.objects.create(
                    customer=plan.customer,
                    billing_schedule=CustomerPlan.BILLING_SCHEDULE_ANNUAL,
                    automanage_licenses=plan.automanage_licenses,
                    charge_automatically=plan.charge_automatically,
                    price_per_license=price_per_license,
                    discount=discount,
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
                )
                return new_plan, new_plan_ledger_entry

            if plan.status == CustomerPlan.SWITCH_TO_MONTHLY_AT_END_OF_CYCLE:
                if plan.fixed_price is not None:  # nocoverage
                    raise BillingError("Customer is already on monthly fixed plan.")

                plan.status = CustomerPlan.ENDED
                plan.save(update_fields=["status"])

                discount = plan.customer.default_discount or plan.discount
                _, _, _, price_per_license = compute_plan_parameters(
                    tier=plan.tier,
                    automanage_licenses=plan.automanage_licenses,
                    billing_schedule=CustomerPlan.BILLING_SCHEDULE_MONTHLY,
                    discount=plan.discount,
                )

                new_plan = CustomerPlan.objects.create(
                    customer=plan.customer,
                    billing_schedule=CustomerPlan.BILLING_SCHEDULE_MONTHLY,
                    automanage_licenses=plan.automanage_licenses,
                    charge_automatically=plan.charge_automatically,
                    price_per_license=price_per_license,
                    discount=discount,
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
                )
                return new_plan, new_plan_ledger_entry

            if plan.status == CustomerPlan.DOWNGRADE_AT_END_OF_FREE_TRIAL:
                self.downgrade_now_without_creating_additional_invoices(plan)

            if plan.status == CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE:
                self.process_downgrade(plan)

            return None, None
        return None, last_ledger_entry

    def get_billing_page_context(self) -> Dict[str, Any]:
        customer = self.get_customer()
        assert customer is not None
        plan = get_current_plan_by_customer(customer)
        context: Dict[str, Any] = {}
        assert plan is not None
        now = timezone_now()
        new_plan, last_ledger_entry = self.make_end_of_cycle_updates_if_needed(plan, now)
        if last_ledger_entry is not None:
            if new_plan is not None:  # nocoverage
                plan = new_plan
            assert plan is not None  # for mypy
            downgrade_at_end_of_cycle = plan.status == CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE
            downgrade_at_end_of_free_trial = (
                plan.status == CustomerPlan.DOWNGRADE_AT_END_OF_FREE_TRIAL
            )
            switch_to_annual_at_end_of_cycle = (
                plan.status == CustomerPlan.SWITCH_TO_ANNUAL_AT_END_OF_CYCLE
            )
            switch_to_monthly_at_end_of_cycle = (
                plan.status == CustomerPlan.SWITCH_TO_MONTHLY_AT_END_OF_CYCLE
            )
            licenses = last_ledger_entry.licenses
            licenses_at_next_renewal = last_ledger_entry.licenses_at_next_renewal
            assert licenses_at_next_renewal is not None
            seat_count = self.current_count_for_billed_licenses()

            # Should do this in JavaScript, using the user's time zone
            if plan.is_free_trial() or downgrade_at_end_of_free_trial:
                assert plan.next_invoice_date is not None
                renewal_date = "{dt:%B} {dt.day}, {dt.year}".format(dt=plan.next_invoice_date)
            else:
                renewal_date = "{dt:%B} {dt.day}, {dt.year}".format(
                    dt=start_of_next_billing_cycle(plan, now)
                )

            billing_frequency = CustomerPlan.BILLING_SCHEDULES[plan.billing_schedule]

            if switch_to_annual_at_end_of_cycle:
                annual_price_per_license = get_price_per_license(
                    plan.tier, CustomerPlan.BILLING_SCHEDULE_ANNUAL, customer.default_discount
                )
                renewal_cents = annual_price_per_license * licenses_at_next_renewal
                price_per_license = format_money(annual_price_per_license / 12)
            elif switch_to_monthly_at_end_of_cycle:
                monthly_price_per_license = get_price_per_license(
                    plan.tier, CustomerPlan.BILLING_SCHEDULE_MONTHLY, customer.default_discount
                )
                renewal_cents = monthly_price_per_license * licenses_at_next_renewal
                price_per_license = format_money(monthly_price_per_license)
            else:
                renewal_cents = renewal_amount(plan, now, last_ledger_entry)

                if plan.price_per_license is None:
                    price_per_license = ""
                elif billing_frequency == "Annual":
                    price_per_license = format_money(plan.price_per_license / 12)
                else:
                    price_per_license = format_money(plan.price_per_license)

            charge_automatically = plan.charge_automatically
            assert customer.stripe_customer_id is not None  # for mypy
            stripe_customer = stripe_get_customer(customer.stripe_customer_id)
            if charge_automatically:
                payment_method = payment_method_string(stripe_customer)
            else:
                payment_method = "Billed by invoice"

            fixed_price = (
                cents_to_dollar_string(plan.fixed_price)
                if plan.fixed_price is not None
                else None
            )
            remote_server_legacy_plan_end_date = (
                self.get_formatted_remote_server_legacy_plan_end_date(
                    customer, status=CustomerPlan.SWITCH_PLAN_TIER_AT_PLAN_END
                )
            )
            legacy_remote_server_new_plan_name = self.get_legacy_remote_server_new_plan_name(
                customer
            )
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
                "renewal_amount": cents_to_dollar_string(renewal_cents),
                "payment_method": payment_method,
                "charge_automatically": charge_automatically,
                "stripe_email": stripe_customer.email,
                "CustomerPlan": CustomerPlan,
                "billing_frequency": billing_frequency,
                "fixed_price": fixed_price,
                "price_per_license": price_per_license,
                "is_sponsorship_pending": customer.sponsorship_pending,
                "discount_percent": format_discount_percentage(customer.default_discount),
                "is_self_hosted_billing": not isinstance(self, RealmBillingSession),
                "is_server_on_legacy_plan": remote_server_legacy_plan_end_date is not None,
                "remote_server_legacy_plan_end_date": remote_server_legacy_plan_end_date,
                "legacy_remote_server_new_plan_name": legacy_remote_server_new_plan_name,
            }
        return context

    def get_initial_upgrade_context(
        self, initial_upgrade_request: InitialUpgradeRequest
    ) -> Tuple[Optional[str], Optional[UpgradePageContext]]:
        customer = self.get_customer()

        if self.is_sponsored_or_pending(customer):
            return f"{self.billing_session_url}/sponsorship", None

        remote_server_legacy_plan_end_date = self.get_formatted_remote_server_legacy_plan_end_date(
            customer
        )
        # Show upgrade page for remote servers on legacy plan.
        if customer is not None and remote_server_legacy_plan_end_date is None:
            customer_plan = get_current_plan_by_customer(customer)
            if customer_plan is not None:
                return f"{self.billing_session_url}/billing", None

        percent_off = Decimal(0)
        if customer is not None and customer.default_discount is not None:
            percent_off = customer.default_discount

        exempt_from_license_number_check = (
            customer is not None and customer.exempt_from_license_number_check
        )

        # Check if user was successful in adding a card and we are rendering the page again.
        current_payment_method = None
        if customer is not None and customer_has_credit_card_as_default_payment_method(customer):
            assert customer.stripe_customer_id is not None
            stripe_customer = stripe_get_customer(customer.stripe_customer_id)
            payment_method = payment_method_string(stripe_customer)
            # Show "Update card" button if user has already added a card.
            current_payment_method = None if "ending in" not in payment_method else payment_method

        customer_specific_context = self.get_upgrade_page_session_type_specific_context()
        seat_count = self.current_count_for_billed_licenses()
        signed_seat_count, salt = sign_string(str(seat_count))
        tier = initial_upgrade_request.tier

        free_trial_days = None
        free_trial_end_date = None
        # Don't show free trial for remote servers on legacy plan.
        if remote_server_legacy_plan_end_date is None:
            free_trial_days = settings.FREE_TRIAL_DAYS
            if free_trial_days is not None:
                _, _, free_trial_end, _ = compute_plan_parameters(
                    tier, False, CustomerPlan.BILLING_SCHEDULE_ANNUAL, None, True
                )
                free_trial_end_date = (
                    f"{free_trial_end:%B} {free_trial_end.day}, {free_trial_end.year}"
                )

        context: UpgradePageContext = {
            "customer_name": customer_specific_context["customer_name"],
            "default_invoice_days_until_due": DEFAULT_INVOICE_DAYS_UNTIL_DUE,
            "discount_percent": format_discount_percentage(percent_off),
            "email": customer_specific_context["email"],
            "exempt_from_license_number_check": exempt_from_license_number_check,
            "free_trial_days": free_trial_days,
            "free_trial_end_date": free_trial_end_date,
            "is_demo_organization": customer_specific_context["is_demo_organization"],
            "remote_server_legacy_plan_end_date": remote_server_legacy_plan_end_date,
            "manual_license_management": initial_upgrade_request.manual_license_management,
            "min_invoiced_licenses": max(seat_count, MIN_INVOICED_LICENSES),
            "page_params": {
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
            },
            "payment_method": current_payment_method,
            "plan": CustomerPlan.name_from_tier(tier),
            "salt": salt,
            "seat_count": seat_count,
            "signed_seat_count": signed_seat_count,
        }

        return None, context

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
    ) -> None:
        if plan is None:
            customer = self.get_customer()
            if customer is None:
                return
            plan = get_current_plan_by_customer(customer)
            if plan is None:
                return  # nocoverage

        self.process_downgrade(plan)
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
                do_change_plan_status(plan, status)
            elif status == CustomerPlan.FREE_TRIAL:
                if update_plan_request.schedule is not None:
                    self.do_change_schedule_after_free_trial(plan, update_plan_request.schedule)
                else:
                    assert plan.status == CustomerPlan.DOWNGRADE_AT_END_OF_FREE_TRIAL
                    do_change_plan_status(plan, status)
            return

        licenses = update_plan_request.licenses
        if licenses is not None:
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
            if last_ledger_entry.licenses_at_next_renewal == licenses_at_next_renewal:
                raise JsonableError(
                    _(
                        "Your plan is already scheduled to renew with {licenses_at_next_renewal} licenses."
                    ).format(licenses_at_next_renewal=licenses_at_next_renewal)
                )
            validate_licenses(
                plan.charge_automatically,
                licenses_at_next_renewal,
                self.current_count_for_billed_licenses(),
                plan.customer.exempt_from_license_number_check,
            )
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

        new_price_per_license = get_price_per_license(
            new_plan_tier, current_plan.billing_schedule, current_plan.customer.default_discount
        )

        new_plan_billing_cycle_anchor = current_plan.end_date.replace(microsecond=0)

        new_plan = CustomerPlan.objects.create(
            customer=current_plan.customer,
            status=CustomerPlan.ACTIVE,
            automanage_licenses=current_plan.automanage_licenses,
            charge_automatically=current_plan.charge_automatically,
            price_per_license=new_price_per_license,
            discount=current_plan.customer.default_discount,
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
        if not plan.customer.stripe_customer_id:
            raise BillingError(
                f"Customer has a paid plan without a Stripe customer ID: {plan.customer!s}"
            )

        # Updating a CustomerPlan with a status to switch the plan tier,
        # is done via switch_plan_tier, so we do not need to make end of
        # cycle updates for that case.
        if plan.status is not CustomerPlan.SWITCH_PLAN_TIER_NOW:
            self.make_end_of_cycle_updates_if_needed(plan, event_time)

        if plan.invoicing_status == CustomerPlan.INVOICING_STATUS_INITIAL_INVOICE_TO_BE_SENT:
            invoiced_through_id = -1
            licenses_base = None
        else:
            assert plan.invoiced_through is not None
            licenses_base = plan.invoiced_through.licenses
            invoiced_through_id = plan.invoiced_through.id

        invoice_item_created = False
        for ledger_entry in LicenseLedger.objects.filter(
            plan=plan, id__gt=invoiced_through_id, event_time__lte=event_time
        ).order_by("id"):
            price_args: PriceArgs = {}
            if ledger_entry.is_renewal:
                if plan.fixed_price is not None:
                    price_args = {"amount": plan.fixed_price}
                else:
                    assert plan.price_per_license is not None  # needed for mypy
                    price_args = {
                        "unit_amount": plan.price_per_license,
                        "quantity": ledger_entry.licenses,
                    }
                description = f"{plan.name} - renewal"
            elif licenses_base is not None and ledger_entry.licenses != licenses_base:
                assert plan.price_per_license
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
                proration_fraction = (plan_renewal_or_end_date - ledger_entry.event_time) / (
                    billing_period_end - last_renewal
                )
                price_args = {
                    "unit_amount": int(plan.price_per_license * proration_fraction + 0.5),
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
                stripe.InvoiceItem.create(
                    currency="usd",
                    customer=plan.customer.stripe_customer_id,
                    description=description,
                    discountable=False,
                    period={
                        "start": datetime_to_timestamp(ledger_entry.event_time),
                        "end": datetime_to_timestamp(
                            get_plan_renewal_or_end_date(plan, ledger_entry.event_time)
                        ),
                    },
                    idempotency_key=get_idempotency_key(ledger_entry),
                    **price_args,
                )
                invoice_item_created = True
            plan.invoiced_through = ledger_entry
            plan.invoicing_status = CustomerPlan.INVOICING_STATUS_DONE
            plan.save(update_fields=["invoicing_status", "invoiced_through"])
            licenses_base = ledger_entry.licenses

        if invoice_item_created:
            if plan.charge_automatically:
                collection_method = "charge_automatically"
                days_until_due = None
            else:
                collection_method = "send_invoice"
                days_until_due = DEFAULT_INVOICE_DAYS_UNTIL_DUE
            stripe_invoice = stripe.Invoice.create(
                auto_advance=True,
                collection_method=collection_method,
                customer=plan.customer.stripe_customer_id,
                days_until_due=days_until_due,
                statement_descriptor=plan.name,
            )
            stripe.Invoice.finalize_invoice(stripe_invoice)

        plan.next_invoice_date = next_invoice_date(plan)
        plan.save(update_fields=["next_invoice_date"])

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

        stripe_payment_intent_id = event_status_request.stripe_payment_intent_id
        if stripe_payment_intent_id is not None:
            payment_intent = PaymentIntent.objects.filter(
                stripe_payment_intent_id=stripe_payment_intent_id,
                customer=customer,
            ).last()

            if payment_intent is None:
                raise JsonableError(_("Payment intent not found"))
            return {"payment_intent": payment_intent.to_dict()}

        raise JsonableError(_("Pass stripe_session_id or stripe_payment_intent_id"))

    def get_sponsorship_request_context(self) -> Optional[Dict[str, Any]]:
        customer = self.get_customer()
        is_remotely_hosted = isinstance(
            self, (RemoteRealmBillingSession, RemoteServerBillingSession)
        )

        # We only support sponsorships for these plans.
        sponsored_plan_name = CustomerPlan.name_from_tier(CustomerPlan.TIER_CLOUD_STANDARD)
        if is_remotely_hosted:
            sponsored_plan_name = CustomerPlan.name_from_tier(
                CustomerPlan.TIER_SELF_HOSTED_COMMUNITY
            )

        plan_name = "Zulip Cloud Free"
        if is_remotely_hosted:
            plan_name = "Self-managed"

        context: Dict[str, Any] = {
            "billing_base_url": self.billing_base_url,
            "is_remotely_hosted": is_remotely_hosted,
            "sponsored_plan_name": sponsored_plan_name,
            "plan_name": plan_name,
        }

        if customer is not None and customer.sponsorship_pending:
            if self.on_paid_plan():
                return None

            context["is_sponsorship_pending"] = True

        if self.is_sponsored():
            context["is_sponsored"] = True
            context["plan_name"] = sponsored_plan_name

        if customer is not None:
            plan = get_current_plan_by_customer(customer)
            if plan is not None:
                context["plan_name"] = plan.name
                context["free_trial"] = plan.is_free_trial()

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
        }
        send_email(
            "zerver/emails/sponsorship_request",
            to_emails=[FromAddress.SUPPORT],
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
        elif support_type == SupportType.update_billing_modality:
            assert support_request["billing_modality"] is not None
            assert support_request["billing_modality"] in VALID_BILLING_MODALITY_VALUES
            charge_automatically = support_request["billing_modality"] == "charge_automatically"
            success_message = self.update_billing_modality_of_current_plan(charge_automatically)
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

        return success_message

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
            if not plan.customer.exempt_from_license_number_check:
                assert self.current_count_for_billed_licenses() <= licenses_at_next_renewal
            LicenseLedger.objects.create(
                plan=plan,
                event_time=event_time,
                licenses=plan.licenses(),
                licenses_at_next_renewal=licenses_at_next_renewal,
            )
        else:
            raise AssertionError("Pass licenses or licenses_at_next_renewal")

    def update_license_ledger_for_automanaged_plan(
        self, plan: CustomerPlan, event_time: datetime
    ) -> None:
        new_plan, last_ledger_entry = self.make_end_of_cycle_updates_if_needed(plan, event_time)
        if last_ledger_entry is None:
            return
        if new_plan is not None:
            plan = new_plan
        licenses_at_next_renewal = self.current_count_for_billed_licenses()
        licenses = max(licenses_at_next_renewal, last_ledger_entry.licenses)

        LicenseLedger.objects.create(
            plan=plan,
            event_time=event_time,
            licenses=licenses,
            licenses_at_next_renewal=licenses_at_next_renewal,
        )

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
    def current_count_for_billed_licenses(self) -> int:
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
        elif event_type is AuditLogEventType.SPONSORSHIP_APPROVED:
            return RealmAuditLog.REALM_SPONSORSHIP_APPROVED
        elif event_type is AuditLogEventType.SPONSORSHIP_PENDING_STATUS_CHANGED:
            return RealmAuditLog.REALM_SPONSORSHIP_PENDING_STATUS_CHANGED
        elif event_type is AuditLogEventType.BILLING_MODALITY_CHANGED:
            return RealmAuditLog.REALM_BILLING_MODALITY_CHANGED
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

        if self.user is not None:
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
    def update_data_for_checkout_session_and_payment_intent(
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
    def do_change_plan_type(self, *, tier: Optional[int], is_sponsored: bool = False) -> None:
        from zerver.actions.realm_settings import do_change_realm_plan_type

        # This function needs to translate between the different
        # formats of CustomerPlan.tier and Realm.plan_type.
        if is_sponsored:
            plan_type = Realm.PLAN_TYPE_STANDARD_FREE
        elif tier == CustomerPlan.TIER_CLOUD_STANDARD:
            plan_type = Realm.PLAN_TYPE_STANDARD
        elif (
            tier == CustomerPlan.TIER_CLOUD_PLUS
        ):  # nocoverage # Plus plan doesn't use this code path yet.
            plan_type = Realm.PLAN_TYPE_PLUS
        else:
            raise AssertionError("Unexpected tier")
        do_change_realm_plan_type(self.realm, plan_type, acting_user=self.user)

    @override
    def process_downgrade(self, plan: CustomerPlan) -> None:
        from zerver.actions.realm_settings import do_change_realm_plan_type

        assert plan.customer.realm is not None
        do_change_realm_plan_type(plan.customer.realm, Realm.PLAN_TYPE_LIMITED, acting_user=None)
        plan.status = CustomerPlan.ENDED
        plan.save(update_fields=["status"])

    @override
    def approve_sponsorship(self) -> str:
        # Sponsorship approval is only a support admin action.
        assert self.support_session

        from zerver.actions.message_send import internal_send_private_message

        self.do_change_plan_type(tier=None, is_sponsored=True)
        customer = self.get_customer()
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
                    # TODO: Don't hardcode plan names.
                    plan_name="Zulip Cloud Standard",
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
    def get_metadata_for_stripe_update_card(self) -> Dict[str, Any]:
        assert self.user is not None
        return {
            "type": "card_update",
            "user_id": self.user.id,
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
        context["org_name"] = self.realm.name

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


class RemoteRealmBillingSession(BillingSession):  # nocoverage
    def __init__(
        self,
        remote_realm: RemoteRealm,
        support_staff: Optional[UserProfile] = None,
    ) -> None:
        self.remote_realm = remote_realm
        if support_staff is not None:
            assert support_staff.is_staff
            self.support_session = True
        else:
            self.support_session = False

    @override
    @property
    def billing_entity_display_name(self) -> str:
        return self.remote_realm.name

    @override
    @property
    def billing_session_url(self) -> str:
        return f"{settings.EXTERNAL_URI_SCHEME}{settings.SELF_HOSTING_MANAGEMENT_SUBDOMAIN}.{settings.EXTERNAL_HOST}/realm/{self.remote_realm.uuid}"

    @override
    @property
    def billing_base_url(self) -> str:
        return f"/realm/{self.remote_realm.uuid}"

    @override
    def support_url(self) -> str:
        return build_support_url("remote_servers_support", self.remote_realm.server.hostname)

    @override
    def get_customer(self) -> Optional[Customer]:
        return get_customer_by_remote_realm(self.remote_realm)

    @override
    def get_email(self) -> str:
        # BUG: This is an email for the whole server. We probably
        # need a separable field here.
        return self.remote_realm.server.contact_email

    @override
    def current_count_for_billed_licenses(self) -> int:
        # TODO: Do the proper calculation here.
        return 10

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
        elif event_type is AuditLogEventType.SPONSORSHIP_APPROVED:
            return RemoteRealmAuditLog.REMOTE_SERVER_SPONSORSHIP_APPROVED
        elif event_type is AuditLogEventType.SPONSORSHIP_PENDING_STATUS_CHANGED:
            return RemoteRealmAuditLog.REMOTE_SERVER_SPONSORSHIP_PENDING_STATUS_CHANGED
        elif event_type is AuditLogEventType.BILLING_MODALITY_CHANGED:
            return RemoteRealmAuditLog.REMOTE_SERVER_BILLING_MODALITY_CHANGED
        elif event_type is AuditLogEventType.BILLING_ENTITY_PLAN_TYPE_CHANGED:
            return RemoteRealmAuditLog.REMOTE_SERVER_PLAN_TYPE_CHANGED
        else:
            raise BillingSessionAuditLogEventError(event_type)

    @override
    def write_to_audit_log(
        self,
        event_type: AuditLogEventType,
        event_time: datetime,
        *,
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
    def update_data_for_checkout_session_and_payment_intent(
        self, metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        # TODO: Figure out what this should do.
        updated_metadata = dict(
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
            return customer
        else:
            customer, created = Customer.objects.update_or_create(
                remote_realm=self.remote_realm, defaults=defaults
            )
            return customer

    @override
    def do_change_plan_type(self, *, tier: Optional[int], is_sponsored: bool = False) -> None:
        if is_sponsored:
            plan_type = RemoteRealm.PLAN_TYPE_COMMUNITY
        elif tier == CustomerPlan.TIER_SELF_HOSTED_BUSINESS:
            plan_type = RemoteRealm.PLAN_TYPE_BUSINESS
        elif (
            tier == CustomerPlan.TIER_SELF_HOSTED_PLUS
        ):  # nocoverage # Plus plan doesn't use this code path yet.
            plan_type = RemoteRealm.PLAN_TYPE_ENTERPRISE
        else:
            raise AssertionError("Unexpected tier")

        # TODO: Audit logging and set usage limits.

        self.remote_realm.plan_type = plan_type
        self.remote_realm.save(update_fields=["plan_type"])

    @override
    def approve_sponsorship(self) -> str:
        # Sponsorship approval is only a support admin action.
        assert self.support_session

        self.do_change_plan_type(tier=None, is_sponsored=True)
        customer = self.get_customer()
        if customer is not None and customer.sponsorship_pending:
            customer.sponsorship_pending = False
            customer.save(update_fields=["sponsorship_pending"])
            self.write_to_audit_log(
                event_type=AuditLogEventType.SPONSORSHIP_APPROVED, event_time=timezone_now()
            )
        # TODO: Add something (probably email) to let remote realm
        # organization know that the sponsorship request was approved.
        return f"Sponsorship approved for {self.billing_entity_display_name}"

    @override
    def is_sponsored(self) -> bool:
        return self.remote_realm.plan_type == self.remote_realm.PLAN_TYPE_COMMUNITY

    @override
    def get_metadata_for_stripe_update_card(self) -> Dict[str, Any]:
        return {
            "type": "card_update",
            # TODO: Add user identity metadata from the remote realm identity
            # "user_id": user.id,
        }

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
    def process_downgrade(self, plan: CustomerPlan) -> None:
        with transaction.atomic():
            old_plan_type = self.remote_realm.plan_type
            new_plan_type = RemoteRealm.PLAN_TYPE_SELF_HOSTED
            self.remote_realm.plan_type = new_plan_type
            self.remote_realm.save(update_fields=["plan_type"])
            self.write_to_audit_log(
                event_type=AuditLogEventType.BILLING_ENTITY_PLAN_TYPE_CHANGED,
                event_time=timezone_now(),
                extra_data={"old_value": old_plan_type, "new_value": new_plan_type},
            )

        plan.status = CustomerPlan.ENDED
        plan.save(update_fields=["status"])

    @override
    def get_type_of_plan_tier_change(
        self, current_plan_tier: int, new_plan_tier: int
    ) -> PlanTierChangeType:
        valid_plan_tiers = [
            CustomerPlan.TIER_SELF_HOSTED_BUSINESS,
            CustomerPlan.TIER_SELF_HOSTED_PLUS,
        ]
        if (
            current_plan_tier not in valid_plan_tiers
            or new_plan_tier not in valid_plan_tiers
            or current_plan_tier == new_plan_tier
        ):
            return PlanTierChangeType.INVALID
        if (
            current_plan_tier == CustomerPlan.TIER_SELF_HOSTED_BUSINESS
            and new_plan_tier == CustomerPlan.TIER_SELF_HOSTED_PLUS
        ):
            return PlanTierChangeType.UPGRADE
        else:
            assert current_plan_tier == CustomerPlan.TIER_SELF_HOSTED_PLUS
            assert new_plan_tier == CustomerPlan.TIER_SELF_HOSTED_BUSINESS
            return PlanTierChangeType.DOWNGRADE

    @override
    def has_billing_access(self) -> bool:
        # We don't currently have a way to authenticate a remote
        # session that isn't authorized for billing access.
        return True

    PAID_PLANS = [
        RemoteRealm.PLAN_TYPE_BUSINESS,
        RemoteRealm.PLAN_TYPE_ENTERPRISE,
    ]

    @override
    def on_paid_plan(self) -> bool:
        return self.remote_realm.plan_type in self.PAID_PLANS

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
        context["org_name"] = self.remote_realm.host

    @override
    def get_sponsorship_request_session_specific_context(
        self,
    ) -> SponsorshipRequestSessionSpecificContext:
        return SponsorshipRequestSessionSpecificContext(
            realm_user=None,
            user_info=SponsorshipApplicantInfo(
                # TODO: Plumb through the session data on the acting user.
                name="Remote realm administrator",
                email=self.get_email(),
                # TODO: Set user_role when determining which set of users can access the page.
                role="Remote realm administrator",
            ),
            # TODO: Check if this works on support page.
            realm_string_id=self.remote_realm.host,
        )

    @override
    def save_org_type_from_request_sponsorship_session(self, org_type: int) -> None:
        if self.remote_realm.org_type != org_type:
            self.remote_realm.org_type = org_type
            self.remote_realm.save(update_fields=["org_type"])


class RemoteServerBillingSession(BillingSession):  # nocoverage
    """Billing session for pre-8.0 servers that do not yet support
    creating RemoteRealm objects."""

    def __init__(
        self,
        remote_server: RemoteZulipServer,
        support_staff: Optional[UserProfile] = None,
    ) -> None:
        self.remote_server = remote_server
        if support_staff is not None:
            assert support_staff.is_staff
            self.support_session = True
        else:
            self.support_session = False

    @override
    @property
    def billing_entity_display_name(self) -> str:
        return self.remote_server.hostname

    @override
    @property
    def billing_session_url(self) -> str:
        return f"{settings.EXTERNAL_URI_SCHEME}{settings.SELF_HOSTING_MANAGEMENT_SUBDOMAIN}.{settings.EXTERNAL_HOST}/server/{self.remote_server.uuid}"

    @override
    @property
    def billing_base_url(self) -> str:
        return f"/server/{self.remote_server.uuid}"

    @override
    def support_url(self) -> str:
        return build_support_url("remote_servers_support", self.remote_server.hostname)

    @override
    def get_customer(self) -> Optional[Customer]:
        return get_customer_by_remote_server(self.remote_server)

    @override
    def get_email(self) -> str:
        return self.remote_server.contact_email

    @override
    def current_count_for_billed_licenses(self) -> int:
        # TODO: Do the proper calculation here.
        return 10

    @override
    def get_audit_log_event(self, event_type: AuditLogEventType) -> int:
        if event_type is AuditLogEventType.STRIPE_CUSTOMER_CREATED:
            return RemoteZulipServerAuditLog.STRIPE_CUSTOMER_CREATED
        elif event_type is AuditLogEventType.STRIPE_CARD_CHANGED:
            return RemoteZulipServerAuditLog.STRIPE_CARD_CHANGED
        elif event_type is AuditLogEventType.CUSTOMER_PLAN_CREATED:
            return RemoteZulipServerAuditLog.CUSTOMER_PLAN_CREATED
        elif event_type is AuditLogEventType.DISCOUNT_CHANGED:
            return RemoteZulipServerAuditLog.REMOTE_SERVER_DISCOUNT_CHANGED
        elif event_type is AuditLogEventType.SPONSORSHIP_APPROVED:
            return RemoteZulipServerAuditLog.REMOTE_SERVER_SPONSORSHIP_APPROVED
        elif event_type is AuditLogEventType.SPONSORSHIP_PENDING_STATUS_CHANGED:
            return RemoteZulipServerAuditLog.REMOTE_SERVER_SPONSORSHIP_PENDING_STATUS_CHANGED
        elif event_type is AuditLogEventType.BILLING_MODALITY_CHANGED:
            return RemoteZulipServerAuditLog.REMOTE_SERVER_BILLING_MODALITY_CHANGED
        elif event_type is AuditLogEventType.BILLING_ENTITY_PLAN_TYPE_CHANGED:
            return RemoteZulipServerAuditLog.REMOTE_SERVER_PLAN_TYPE_CHANGED
        else:
            raise BillingSessionAuditLogEventError(event_type)

    @override
    def write_to_audit_log(
        self,
        event_type: AuditLogEventType,
        event_time: datetime,
        *,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        audit_log_event = self.get_audit_log_event(event_type)
        log_data = {
            "server": self.remote_server,
            "event_type": audit_log_event,
            "event_time": event_time,
        }

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
    def update_data_for_checkout_session_and_payment_intent(
        self, metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        updated_metadata = dict(
            server=self.remote_server,
            email=self.get_email(),
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
            return customer
        else:
            customer, created = Customer.objects.update_or_create(
                remote_server=self.remote_server, defaults=defaults
            )
            return customer

    @override
    def do_change_plan_type(self, *, tier: Optional[int], is_sponsored: bool = False) -> None:
        # TODO: Create actual plan types.

        # This function needs to translate between the different
        # formats of CustomerPlan.tier and RealmZulipServer.plan_type.
        if is_sponsored:
            plan_type = RemoteZulipServer.PLAN_TYPE_COMMUNITY
        elif tier == CustomerPlan.TIER_SELF_HOSTED_BUSINESS:
            plan_type = RemoteZulipServer.PLAN_TYPE_BUSINESS
        elif (
            tier == CustomerPlan.TIER_SELF_HOSTED_PLUS
        ):  # nocoverage # Plus plan doesn't use this code path yet.
            plan_type = RemoteZulipServer.PLAN_TYPE_ENTERPRISE
        else:
            raise AssertionError("Unexpected tier")

        # TODO: Audit logging and set usage limits.

        self.remote_server.plan_type = plan_type
        self.remote_server.save(update_fields=["plan_type"])

    @override
    def approve_sponsorship(self) -> str:
        # Sponsorship approval is only a support admin action.
        assert self.support_session

        self.do_change_plan_type(tier=None, is_sponsored=True)
        customer = self.get_customer()
        if customer is not None and customer.sponsorship_pending:
            customer.sponsorship_pending = False
            customer.save(update_fields=["sponsorship_pending"])
            self.write_to_audit_log(
                event_type=AuditLogEventType.SPONSORSHIP_APPROVED, event_time=timezone_now()
            )
        # TODO: Add something (probably email) to let remote server
        # organization know that the sponsorship request was approved.
        return f"Sponsorship approved for {self.billing_entity_display_name}"

    @override
    def process_downgrade(self, plan: CustomerPlan) -> None:
        with transaction.atomic():
            old_plan_type = self.remote_server.plan_type
            new_plan_type = RemoteZulipServer.PLAN_TYPE_SELF_HOSTED
            self.remote_server.plan_type = new_plan_type
            self.remote_server.save(update_fields=["plan_type"])
            self.write_to_audit_log(
                event_type=AuditLogEventType.BILLING_ENTITY_PLAN_TYPE_CHANGED,
                event_time=timezone_now(),
                extra_data={"old_value": old_plan_type, "new_value": new_plan_type},
            )

        plan.status = CustomerPlan.ENDED
        plan.save(update_fields=["status"])

    @override
    def is_sponsored(self) -> bool:
        return self.remote_server.plan_type == self.remote_server.PLAN_TYPE_COMMUNITY

    @override
    def get_metadata_for_stripe_update_card(self) -> Dict[str, Any]:
        return {
            "type": "card_update",
            # TODO: Maybe add some user identity metadata from the remote server identity
            # "user_id": user.id,
        }

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
    def get_type_of_plan_tier_change(
        self, current_plan_tier: int, new_plan_tier: int
    ) -> PlanTierChangeType:
        valid_plan_tiers = [
            CustomerPlan.TIER_SELF_HOSTED_LEGACY,
            CustomerPlan.TIER_SELF_HOSTED_BUSINESS,
            CustomerPlan.TIER_SELF_HOSTED_PLUS,
        ]
        if (
            current_plan_tier not in valid_plan_tiers
            or new_plan_tier not in valid_plan_tiers
            or current_plan_tier == new_plan_tier
        ):
            return PlanTierChangeType.INVALID

        if current_plan_tier == CustomerPlan.TIER_SELF_HOSTED_LEGACY and new_plan_tier in (
            CustomerPlan.TIER_SELF_HOSTED_BUSINESS,
            CustomerPlan.TIER_SELF_HOSTED_PLUS,
        ):
            return PlanTierChangeType.UPGRADE
        elif (
            current_plan_tier == CustomerPlan.TIER_SELF_HOSTED_BUSINESS
            and new_plan_tier == CustomerPlan.TIER_SELF_HOSTED_PLUS
        ):
            return PlanTierChangeType.UPGRADE
        elif (
            current_plan_tier == CustomerPlan.TIER_SELF_HOSTED_BUSINESS
            and new_plan_tier == CustomerPlan.TIER_SELF_HOSTED_LEGACY
        ):
            return PlanTierChangeType.DOWNGRADE
        else:
            assert current_plan_tier == CustomerPlan.TIER_SELF_HOSTED_PLUS
            assert new_plan_tier == CustomerPlan.TIER_SELF_HOSTED_BUSINESS
            return PlanTierChangeType.DOWNGRADE

    @override
    def has_billing_access(self) -> bool:
        # We don't currently have a way to authenticate a remote
        # session that isn't authorized for billing access.
        return True

    PAID_PLANS = [
        RemoteZulipServer.PLAN_TYPE_BUSINESS,
        RemoteZulipServer.PLAN_TYPE_ENTERPRISE,
    ]

    @override
    def on_paid_plan(self) -> bool:
        return self.remote_server.plan_type in self.PAID_PLANS

    @override
    def add_sponsorship_info_to_context(self, context: Dict[str, Any]) -> None:
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
        context["org_name"] = self.remote_server.hostname

    @override
    def get_sponsorship_request_session_specific_context(
        self,
    ) -> SponsorshipRequestSessionSpecificContext:
        return SponsorshipRequestSessionSpecificContext(
            realm_user=None,
            user_info=SponsorshipApplicantInfo(
                # TODO: Figure out a better story here. We don't
                # actually have a name or other details on the person
                # doing this flow, but could ask for it in the login
                # form if desired.
                name="Remote server administrator",
                email=self.get_email(),
                role="Remote server administrator",
            ),
            # TODO: Check if this works on support page.
            realm_string_id=self.remote_server.hostname,
        )

    @override
    def save_org_type_from_request_sponsorship_session(self, org_type: int) -> None:
        if self.remote_server.org_type != org_type:
            self.remote_server.org_type = org_type
            self.remote_server.save(update_fields=["org_type"])

    def add_server_to_legacy_plan(
        self,
        renewal_date: datetime,
        end_date: datetime,
    ) -> None:
        # Set stripe_customer_id to None to avoid customer being charged without a payment method.
        customer = Customer.objects.create(
            remote_server=self.remote_server, stripe_customer_id=None
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
            # The primary mechanism for preventing charges under this
            # plan is setting a null `next_invoice_date`, but setting
            # a 0 price is useful defense in depth here.
            "next_invoice_date": None,
            "price_per_license": 0,
            "billing_schedule": CustomerPlan.BILLING_SCHEDULE_ANNUAL,
            "automanage_licenses": True,
        }
        legacy_plan = CustomerPlan.objects.create(
            customer=customer,
            **legacy_plan_params,
        )

        # Create a ledger entry for the legacy plan for tracking purposes.
        billed_licenses = self.current_count_for_billed_licenses()
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
        CustomerPlan.TIER_CLOUD_PLUS: {"Annual": 16000, "Monthly": 1600},
        # Placeholder self-hosted plan for development.
        CustomerPlan.TIER_SELF_HOSTED_BUSINESS: {"Annual": 8000, "Monthly": 800},
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
    automanage_licenses: bool,
    billing_schedule: int,
    discount: Optional[Decimal],
    free_trial: bool = False,
    billing_cycle_anchor: Optional[datetime] = None,
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

    next_invoice_date = period_end
    if automanage_licenses:
        next_invoice_date = add_months(billing_cycle_anchor, 1)
    if free_trial:
        period_end = billing_cycle_anchor + timedelta(
            days=assert_is_not_none(settings.FREE_TRIAL_DAYS)
        )
        next_invoice_date = period_end
    return billing_cycle_anchor, next_invoice_date, period_end, price_per_license


def is_free_trial_offer_enabled() -> bool:
    return settings.FREE_TRIAL_DAYS not in (None, 0)


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
def do_change_remote_server_plan_type(remote_server: RemoteZulipServer, plan_type: int) -> None:
    old_value = remote_server.plan_type
    remote_server.plan_type = plan_type
    remote_server.save(update_fields=["plan_type"])
    RemoteZulipServerAuditLog.objects.create(
        event_type=RealmAuditLog.REMOTE_SERVER_PLAN_TYPE_CHANGED,
        server=remote_server,
        event_time=timezone_now(),
        extra_data={"old_value": old_value, "new_value": plan_type},
    )


@transaction.atomic
def do_deactivate_remote_server(remote_server: RemoteZulipServer) -> None:
    if remote_server.deactivated:
        billing_logger.warning(
            "Cannot deactivate remote server with ID %d, server has already been deactivated.",
            remote_server.id,
        )
        return

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
    if event_time is None:  # nocoverage
        event_time = timezone_now()
    # TODO: Add RemoteRealmBillingSession and RemoteServerBillingSession cases.
    for plan in CustomerPlan.objects.filter(next_invoice_date__lte=event_time):
        if plan.customer.realm is not None:
            RealmBillingSession(realm=plan.customer.realm).invoice_plan(plan, event_time)
        # TODO: Assert that we never invoice legacy plans.


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
        invoices = stripe.Invoice.list(
            customer=customer.stripe_customer_id, starting_after=last_invoice, limit=100
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
