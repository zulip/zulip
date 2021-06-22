import logging
import math
import os
import secrets
from datetime import datetime, timedelta
from decimal import Decimal
from functools import wraps
from typing import Callable, Dict, Optional, Tuple, TypeVar, cast

import orjson
import stripe
from django.conf import settings
from django.core.signing import Signer
from django.db import transaction
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.utils.translation import override as override_language

from corporate.models import (
    Customer,
    CustomerPlan,
    LicenseLedger,
    get_current_plan_by_customer,
    get_current_plan_by_realm,
    get_customer_by_realm,
)
from zerver.lib.logging_util import log_to_file
from zerver.lib.timestamp import datetime_to_timestamp, timestamp_to_datetime
from zerver.models import Realm, RealmAuditLog, UserProfile, get_system_bot
from zproject.config import get_secret

STRIPE_PUBLISHABLE_KEY = get_secret("stripe_publishable_key")
stripe.api_key = get_secret("stripe_secret_key")

BILLING_LOG_PATH = os.path.join(
    "/var/log/zulip" if not settings.DEVELOPMENT else settings.DEVELOPMENT_LOG_DIRECTORY,
    "billing.log",
)
billing_logger = logging.getLogger("corporate.stripe")
log_to_file(billing_logger, BILLING_LOG_PATH)
log_to_file(logging.getLogger("stripe"), BILLING_LOG_PATH)

CallableT = TypeVar("CallableT", bound=Callable[..., object])

MIN_INVOICED_LICENSES = 30
MAX_INVOICED_LICENSES = 1000
DEFAULT_INVOICE_DAYS_UNTIL_DUE = 30


def get_latest_seat_count(realm: Realm) -> int:
    non_guests = (
        UserProfile.objects.filter(realm=realm, is_active=True, is_bot=False)
        .exclude(role=UserProfile.ROLE_GUEST)
        .count()
    )
    guests = UserProfile.objects.filter(
        realm=realm, is_active=True, is_bot=False, role=UserProfile.ROLE_GUEST
    ).count()
    return max(non_guests, math.ceil(guests / 5))


def sign_string(string: str) -> Tuple[str, str]:
    salt = secrets.token_hex(32)
    signer = Signer(salt=salt)
    return signer.sign(string), salt


def unsign_string(signed_string: str, salt: str) -> str:
    signer = Signer(salt=salt)
    return signer.unsign(signed_string)


def validate_licenses(charge_automatically: bool, licenses: Optional[int], seat_count: int) -> None:
    min_licenses = seat_count
    max_licenses = None
    if not charge_automatically:
        min_licenses = max(seat_count, MIN_INVOICED_LICENSES)
        max_licenses = MAX_INVOICED_LICENSES

    if licenses is None or licenses < min_licenses:
        raise BillingError(
            "not enough licenses", _("You must invoice for at least {} users.").format(min_licenses)
        )

    if max_licenses is not None and licenses > max_licenses:
        message = _(
            "Invoices with more than {} licenses can't be processed from this page. To complete "
            "the upgrade, please contact {}."
        ).format(max_licenses, settings.ZULIP_ADMINISTRATOR)
        raise BillingError("too many licenses", message)


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
    if plan.is_free_trial():
        assert plan.next_invoice_date is not None  # for mypy
        return plan.next_invoice_date

    months_per_period = {
        CustomerPlan.ANNUAL: 12,
        CustomerPlan.MONTHLY: 1,
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
        CustomerPlan.ANNUAL: 12,
        CustomerPlan.MONTHLY: 1,
    }[plan.billing_schedule]
    if plan.automanage_licenses:
        months_per_period = 1
    periods = 1
    dt = plan.billing_cycle_anchor
    while dt <= plan.next_invoice_date:
        dt = add_months(plan.billing_cycle_anchor, months_per_period * periods)
        periods += 1
    return dt


def renewal_amount(plan: CustomerPlan, event_time: datetime) -> int:  # nocoverage: TODO
    if plan.fixed_price is not None:
        return plan.fixed_price
    new_plan, last_ledger_entry = make_end_of_cycle_updates_if_needed(plan, event_time)
    if last_ledger_entry is None:
        return 0
    if last_ledger_entry.licenses_at_next_renewal is None:
        return 0
    if new_plan is not None:
        plan = new_plan
    assert plan.price_per_license is not None  # for mypy
    return plan.price_per_license * last_ledger_entry.licenses_at_next_renewal


def get_idempotency_key(ledger_entry: LicenseLedger) -> Optional[str]:
    if settings.TEST_SUITE:
        return None
    return f"ledger_entry:{ledger_entry.id}"  # nocoverage


def cents_to_dollar_string(cents: int) -> str:
    return f"{cents / 100.:,.2f}"


class BillingError(Exception):
    # error messages
    CONTACT_SUPPORT = gettext_lazy("Something went wrong. Please contact {email}.")
    TRY_RELOADING = gettext_lazy("Something went wrong. Please reload the page.")

    # description is used only for tests
    def __init__(self, description: str, message: Optional[str] = None) -> None:
        self.description = description
        if message is None:
            message = BillingError.CONTACT_SUPPORT.format(email=settings.ZULIP_ADMINISTRATOR)
        self.message = message


class LicenseLimitError(Exception):
    pass


class StripeCardError(BillingError):
    pass


class StripeConnectionError(BillingError):
    pass


class InvalidBillingSchedule(Exception):
    def __init__(self, billing_schedule: int) -> None:
        self.message = f"Unknown billing_schedule: {billing_schedule}"
        super().__init__(self.message)


def catch_stripe_errors(func: CallableT) -> CallableT:
    @wraps(func)
    def wrapped(*args: object, **kwargs: object) -> object:
        if settings.DEVELOPMENT and not settings.TEST_SUITE:  # nocoverage
            if STRIPE_PUBLISHABLE_KEY is None:
                raise BillingError(
                    "missing stripe config",
                    "Missing Stripe config. "
                    "See https://zulip.readthedocs.io/en/latest/subsystems/billing.html.",
                )
        try:
            return func(*args, **kwargs)
        # See https://stripe.com/docs/api/python#error_handling, though
        # https://stripe.com/docs/api/ruby#error_handling suggests there are additional fields, and
        # https://stripe.com/docs/error-codes gives a more detailed set of error codes
        except stripe.error.StripeError as e:
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

    return cast(CallableT, wrapped)


@catch_stripe_errors
def stripe_get_customer(stripe_customer_id: str) -> stripe.Customer:
    return stripe.Customer.retrieve(stripe_customer_id, expand=["default_source"])


@catch_stripe_errors
def do_create_stripe_customer(user: UserProfile, stripe_token: Optional[str] = None) -> Customer:
    realm = user.realm
    # We could do a better job of handling race conditions here, but if two
    # people from a realm try to upgrade at exactly the same time, the main
    # bad thing that will happen is that we will create an extra stripe
    # customer that we can delete or ignore.
    stripe_customer = stripe.Customer.create(
        description=f"{realm.string_id} ({realm.name})",
        email=user.delivery_email,
        metadata={"realm_id": realm.id, "realm_str": realm.string_id},
        source=stripe_token,
    )
    event_time = timestamp_to_datetime(stripe_customer.created)
    with transaction.atomic(savepoint=False):
        RealmAuditLog.objects.create(
            realm=user.realm,
            acting_user=user,
            event_type=RealmAuditLog.STRIPE_CUSTOMER_CREATED,
            event_time=event_time,
        )
        if stripe_token is not None:
            RealmAuditLog.objects.create(
                realm=user.realm,
                acting_user=user,
                event_type=RealmAuditLog.STRIPE_CARD_CHANGED,
                event_time=event_time,
            )
        customer, created = Customer.objects.update_or_create(
            realm=realm, defaults={"stripe_customer_id": stripe_customer.id}
        )
        from zerver.lib.actions import do_make_user_billing_admin

        do_make_user_billing_admin(user)
    return customer


@catch_stripe_errors
def do_replace_payment_source(
    user: UserProfile, stripe_token: str, pay_invoices: bool = False
) -> stripe.Customer:
    customer = get_customer_by_realm(user.realm)
    assert customer is not None  # for mypy

    stripe_customer = stripe_get_customer(customer.stripe_customer_id)
    stripe_customer.source = stripe_token
    # Deletes existing card: https://stripe.com/docs/api#update_customer-source
    updated_stripe_customer = stripe.Customer.save(stripe_customer)
    RealmAuditLog.objects.create(
        realm=user.realm,
        acting_user=user,
        event_type=RealmAuditLog.STRIPE_CARD_CHANGED,
        event_time=timezone_now(),
    )
    if pay_invoices:
        for stripe_invoice in stripe.Invoice.list(
            billing="charge_automatically", customer=stripe_customer.id, status="open"
        ):
            # The user will get either a receipt or a "failed payment" email, but the in-app
            # messaging could be clearer here (e.g. it could explicitly tell the user that there
            # were payment(s) and that they succeeded or failed).
            # Worth fixing if we notice that a lot of cards end up failing at this step.
            stripe.Invoice.pay(stripe_invoice)
    return updated_stripe_customer


def stripe_customer_has_credit_card_as_default_source(stripe_customer: stripe.Customer) -> bool:
    if not stripe_customer.default_source:
        return False
    return stripe_customer.default_source.object == "card"


def customer_has_credit_card_as_default_source(customer: Customer) -> bool:
    if not customer.stripe_customer_id:
        return False
    stripe_customer = stripe_get_customer(customer.stripe_customer_id)
    return stripe_customer_has_credit_card_as_default_source(stripe_customer)


# event_time should roughly be timezone_now(). Not designed to handle
# event_times in the past or future
@transaction.atomic(savepoint=False)
def make_end_of_cycle_updates_if_needed(
    plan: CustomerPlan, event_time: datetime
) -> Tuple[Optional[CustomerPlan], Optional[LicenseLedger]]:
    last_ledger_entry = LicenseLedger.objects.filter(plan=plan).order_by("-id").first()
    last_renewal = (
        LicenseLedger.objects.filter(plan=plan, is_renewal=True).order_by("-id").first().event_time
    )
    next_billing_cycle = start_of_next_billing_cycle(plan, last_renewal)
    if next_billing_cycle <= event_time:
        if plan.status == CustomerPlan.ACTIVE:
            return None, LicenseLedger.objects.create(
                plan=plan,
                is_renewal=True,
                event_time=next_billing_cycle,
                licenses=last_ledger_entry.licenses_at_next_renewal,
                licenses_at_next_renewal=last_ledger_entry.licenses_at_next_renewal,
            )
        if plan.is_free_trial():
            plan.invoiced_through = last_ledger_entry
            assert plan.next_invoice_date is not None
            plan.billing_cycle_anchor = plan.next_invoice_date.replace(microsecond=0)
            plan.status = CustomerPlan.ACTIVE
            plan.save(update_fields=["invoiced_through", "billing_cycle_anchor", "status"])
            return None, LicenseLedger.objects.create(
                plan=plan,
                is_renewal=True,
                event_time=next_billing_cycle,
                licenses=last_ledger_entry.licenses_at_next_renewal,
                licenses_at_next_renewal=last_ledger_entry.licenses_at_next_renewal,
            )

        if plan.status == CustomerPlan.SWITCH_TO_ANNUAL_AT_END_OF_CYCLE:
            if plan.fixed_price is not None:  # nocoverage
                raise NotImplementedError("Can't switch fixed priced monthly plan to annual.")

            plan.status = CustomerPlan.ENDED
            plan.save(update_fields=["status"])

            discount = plan.customer.default_discount or plan.discount
            _, _, _, price_per_license = compute_plan_parameters(
                automanage_licenses=plan.automanage_licenses,
                billing_schedule=CustomerPlan.ANNUAL,
                discount=plan.discount,
            )

            new_plan = CustomerPlan.objects.create(
                customer=plan.customer,
                billing_schedule=CustomerPlan.ANNUAL,
                automanage_licenses=plan.automanage_licenses,
                charge_automatically=plan.charge_automatically,
                price_per_license=price_per_license,
                discount=discount,
                billing_cycle_anchor=next_billing_cycle,
                tier=plan.tier,
                status=CustomerPlan.ACTIVE,
                next_invoice_date=next_billing_cycle,
                invoiced_through=None,
                invoicing_status=CustomerPlan.INITIAL_INVOICE_TO_BE_SENT,
            )

            new_plan_ledger_entry = LicenseLedger.objects.create(
                plan=new_plan,
                is_renewal=True,
                event_time=next_billing_cycle,
                licenses=last_ledger_entry.licenses_at_next_renewal,
                licenses_at_next_renewal=last_ledger_entry.licenses_at_next_renewal,
            )

            RealmAuditLog.objects.create(
                realm=new_plan.customer.realm,
                event_time=event_time,
                event_type=RealmAuditLog.CUSTOMER_SWITCHED_FROM_MONTHLY_TO_ANNUAL_PLAN,
                extra_data=orjson.dumps(
                    {
                        "monthly_plan_id": plan.id,
                        "annual_plan_id": new_plan.id,
                    }
                ).decode(),
            )
            return new_plan, new_plan_ledger_entry

        if plan.status == CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE:
            process_downgrade(plan)
        return None, None
    return None, last_ledger_entry


# Returns Customer instead of stripe_customer so that we don't make a Stripe
# API call if there's nothing to update
def update_or_create_stripe_customer(
    user: UserProfile, stripe_token: Optional[str] = None
) -> Customer:
    realm = user.realm
    customer = get_customer_by_realm(realm)
    if customer is None or customer.stripe_customer_id is None:
        return do_create_stripe_customer(user, stripe_token=stripe_token)
    if stripe_token is not None:
        do_replace_payment_source(user, stripe_token)
    return customer


def calculate_discounted_price_per_license(
    original_price_per_license: int, discount: Decimal
) -> int:
    # There are no fractional cents in Stripe, so round down to nearest integer.
    return int(float(original_price_per_license * (1 - discount / 100)) + 0.00001)


def get_price_per_license(
    tier: int, billing_schedule: int, discount: Optional[Decimal] = None
) -> int:
    # TODO use variables to account for Zulip Plus
    assert tier == CustomerPlan.STANDARD

    price_per_license: Optional[int] = None
    if billing_schedule == CustomerPlan.ANNUAL:
        price_per_license = 8000
    elif billing_schedule == CustomerPlan.MONTHLY:
        price_per_license = 800
    else:  # nocoverage
        raise InvalidBillingSchedule(billing_schedule)
    if discount is not None:
        price_per_license = calculate_discounted_price_per_license(price_per_license, discount)
    return price_per_license


def compute_plan_parameters(
    automanage_licenses: bool,
    billing_schedule: int,
    discount: Optional[Decimal],
    free_trial: bool = False,
) -> Tuple[datetime, datetime, datetime, int]:
    # Everything in Stripe is stored as timestamps with 1 second resolution,
    # so standardize on 1 second resolution.
    # TODO talk about leapseconds?
    billing_cycle_anchor = timezone_now().replace(microsecond=0)
    if billing_schedule == CustomerPlan.ANNUAL:
        period_end = add_months(billing_cycle_anchor, 12)
    elif billing_schedule == CustomerPlan.MONTHLY:
        period_end = add_months(billing_cycle_anchor, 1)
    else:  # nocoverage
        raise InvalidBillingSchedule(billing_schedule)

    price_per_license = get_price_per_license(CustomerPlan.STANDARD, billing_schedule, discount)

    next_invoice_date = period_end
    if automanage_licenses:
        next_invoice_date = add_months(billing_cycle_anchor, 1)
    if free_trial:
        period_end = billing_cycle_anchor + timedelta(days=settings.FREE_TRIAL_DAYS)
        next_invoice_date = period_end
    return billing_cycle_anchor, next_invoice_date, period_end, price_per_license


def decimal_to_float(obj: object) -> object:
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError  # nocoverage


def is_free_trial_offer_enabled() -> bool:
    return settings.FREE_TRIAL_DAYS not in (None, 0)


# Only used for cloud signups
@catch_stripe_errors
def process_initial_upgrade(
    user: UserProfile,
    licenses: int,
    automanage_licenses: bool,
    billing_schedule: int,
    stripe_token: Optional[str],
) -> None:
    realm = user.realm
    customer = update_or_create_stripe_customer(user, stripe_token=stripe_token)
    charge_automatically = stripe_token is not None
    free_trial = is_free_trial_offer_enabled()

    if get_current_plan_by_customer(customer) is not None:
        # Unlikely race condition from two people upgrading (clicking "Make payment")
        # at exactly the same time. Doesn't fully resolve the race condition, but having
        # a check here reduces the likelihood.
        billing_logger.warning(
            "Customer %s trying to upgrade, but has an active subscription",
            customer,
        )
        raise BillingError(
            "subscribing with existing subscription", str(BillingError.TRY_RELOADING)
        )

    (
        billing_cycle_anchor,
        next_invoice_date,
        period_end,
        price_per_license,
    ) = compute_plan_parameters(
        automanage_licenses, billing_schedule, customer.default_discount, free_trial
    )
    # The main design constraint in this function is that if you upgrade with a credit card, and the
    # charge fails, everything should be rolled back as if nothing had happened. This is because we
    # expect frequent card failures on initial signup.
    # Hence, if we're going to charge a card, do it at the beginning, even if we later may have to
    # adjust the number of licenses.
    if charge_automatically:
        if not free_trial:
            stripe_charge = stripe.Charge.create(
                amount=price_per_license * licenses,
                currency="usd",
                customer=customer.stripe_customer_id,
                description=f"Upgrade to Zulip Standard, ${price_per_license/100} x {licenses}",
                receipt_email=user.delivery_email,
                statement_descriptor="Zulip Standard",
            )
            # Not setting a period start and end, but maybe we should? Unclear what will make things
            # most similar to the renewal case from an accounting perspective.
            assert isinstance(stripe_charge.source, stripe.Card)
            description = f"Payment (Card ending in {stripe_charge.source.last4})"
            stripe.InvoiceItem.create(
                amount=price_per_license * licenses * -1,
                currency="usd",
                customer=customer.stripe_customer_id,
                description=description,
                discountable=False,
            )

    # TODO: The correctness of this relies on user creation, deactivation, etc being
    # in a transaction.atomic(savepoint=False) with the relevant RealmAuditLog entries
    with transaction.atomic(savepoint=False):
        # billed_licenses can greater than licenses if users are added between the start of
        # this function (process_initial_upgrade) and now
        billed_licenses = max(get_latest_seat_count(realm), licenses)
        plan_params = {
            "automanage_licenses": automanage_licenses,
            "charge_automatically": charge_automatically,
            "price_per_license": price_per_license,
            "discount": customer.default_discount,
            "billing_cycle_anchor": billing_cycle_anchor,
            "billing_schedule": billing_schedule,
            "tier": CustomerPlan.STANDARD,
        }
        if free_trial:
            plan_params["status"] = CustomerPlan.FREE_TRIAL
        plan = CustomerPlan.objects.create(
            customer=customer, next_invoice_date=next_invoice_date, **plan_params
        )
        ledger_entry = LicenseLedger.objects.create(
            plan=plan,
            is_renewal=True,
            event_time=billing_cycle_anchor,
            licenses=billed_licenses,
            licenses_at_next_renewal=billed_licenses,
        )
        plan.invoiced_through = ledger_entry
        plan.save(update_fields=["invoiced_through"])
        RealmAuditLog.objects.create(
            realm=realm,
            acting_user=user,
            event_time=billing_cycle_anchor,
            event_type=RealmAuditLog.CUSTOMER_PLAN_CREATED,
            extra_data=orjson.dumps(plan_params, default=decimal_to_float).decode(),
        )

    if not free_trial:
        stripe.InvoiceItem.create(
            currency="usd",
            customer=customer.stripe_customer_id,
            description="Zulip Standard",
            discountable=False,
            period={
                "start": datetime_to_timestamp(billing_cycle_anchor),
                "end": datetime_to_timestamp(period_end),
            },
            quantity=billed_licenses,
            unit_amount=price_per_license,
        )

        if charge_automatically:
            billing_method = "charge_automatically"
            days_until_due = None
        else:
            billing_method = "send_invoice"
            days_until_due = DEFAULT_INVOICE_DAYS_UNTIL_DUE

        stripe_invoice = stripe.Invoice.create(
            auto_advance=True,
            billing=billing_method,
            customer=customer.stripe_customer_id,
            days_until_due=days_until_due,
            statement_descriptor="Zulip Standard",
        )
        stripe.Invoice.finalize_invoice(stripe_invoice)

    from zerver.lib.actions import do_change_plan_type

    do_change_plan_type(realm, Realm.STANDARD, acting_user=user)


def update_license_ledger_for_manual_plan(
    plan: CustomerPlan,
    event_time: datetime,
    licenses: Optional[int] = None,
    licenses_at_next_renewal: Optional[int] = None,
) -> None:
    if licenses is not None:
        assert get_latest_seat_count(plan.customer.realm) <= licenses
        assert licenses > plan.licenses()
        LicenseLedger.objects.create(
            plan=plan, event_time=event_time, licenses=licenses, licenses_at_next_renewal=licenses
        )
    elif licenses_at_next_renewal is not None:
        assert get_latest_seat_count(plan.customer.realm) <= licenses_at_next_renewal
        LicenseLedger.objects.create(
            plan=plan,
            event_time=event_time,
            licenses=plan.licenses(),
            licenses_at_next_renewal=licenses_at_next_renewal,
        )
    else:
        raise AssertionError("Pass licenses or licenses_at_next_renewal")


def update_license_ledger_for_automanaged_plan(
    realm: Realm, plan: CustomerPlan, event_time: datetime
) -> None:
    new_plan, last_ledger_entry = make_end_of_cycle_updates_if_needed(plan, event_time)
    if last_ledger_entry is None:
        return
    if new_plan is not None:
        plan = new_plan
    licenses_at_next_renewal = get_latest_seat_count(realm)
    licenses = max(licenses_at_next_renewal, last_ledger_entry.licenses)

    LicenseLedger.objects.create(
        plan=plan,
        event_time=event_time,
        licenses=licenses,
        licenses_at_next_renewal=licenses_at_next_renewal,
    )


def update_license_ledger_if_needed(realm: Realm, event_time: datetime) -> None:
    plan = get_current_plan_by_realm(realm)
    if plan is None:
        return
    if not plan.automanage_licenses:
        return
    update_license_ledger_for_automanaged_plan(realm, plan, event_time)


def invoice_plan(plan: CustomerPlan, event_time: datetime) -> None:
    if plan.invoicing_status == CustomerPlan.STARTED:
        raise NotImplementedError("Plan with invoicing_status==STARTED needs manual resolution.")
    make_end_of_cycle_updates_if_needed(plan, event_time)

    if plan.invoicing_status == CustomerPlan.INITIAL_INVOICE_TO_BE_SENT:
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
        price_args: Dict[str, int] = {}
        if ledger_entry.is_renewal:
            if plan.fixed_price is not None:
                price_args = {"amount": plan.fixed_price}
            else:
                assert plan.price_per_license is not None  # needed for mypy
                price_args = {
                    "unit_amount": plan.price_per_license,
                    "quantity": ledger_entry.licenses,
                }
            description = "Zulip Standard - renewal"
        elif licenses_base is not None and ledger_entry.licenses != licenses_base:
            assert plan.price_per_license
            last_renewal = (
                LicenseLedger.objects.filter(
                    plan=plan, is_renewal=True, event_time__lte=ledger_entry.event_time
                )
                .order_by("-id")
                .first()
                .event_time
            )
            period_end = start_of_next_billing_cycle(plan, ledger_entry.event_time)
            proration_fraction = (period_end - ledger_entry.event_time) / (
                period_end - last_renewal
            )
            price_args = {
                "unit_amount": int(plan.price_per_license * proration_fraction + 0.5),
                "quantity": ledger_entry.licenses - licenses_base,
            }
            description = "Additional license ({} - {})".format(
                ledger_entry.event_time.strftime("%b %-d, %Y"), period_end.strftime("%b %-d, %Y")
            )

        if price_args:
            plan.invoiced_through = ledger_entry
            plan.invoicing_status = CustomerPlan.STARTED
            plan.save(update_fields=["invoicing_status", "invoiced_through"])
            stripe.InvoiceItem.create(
                currency="usd",
                customer=plan.customer.stripe_customer_id,
                description=description,
                discountable=False,
                period={
                    "start": datetime_to_timestamp(ledger_entry.event_time),
                    "end": datetime_to_timestamp(
                        start_of_next_billing_cycle(plan, ledger_entry.event_time)
                    ),
                },
                idempotency_key=get_idempotency_key(ledger_entry),
                **price_args,
            )
            invoice_item_created = True
        plan.invoiced_through = ledger_entry
        plan.invoicing_status = CustomerPlan.DONE
        plan.save(update_fields=["invoicing_status", "invoiced_through"])
        licenses_base = ledger_entry.licenses

    if invoice_item_created:
        if plan.charge_automatically:
            billing_method = "charge_automatically"
            days_until_due = None
        else:
            billing_method = "send_invoice"
            days_until_due = DEFAULT_INVOICE_DAYS_UNTIL_DUE
        stripe_invoice = stripe.Invoice.create(
            auto_advance=True,
            billing=billing_method,
            customer=plan.customer.stripe_customer_id,
            days_until_due=days_until_due,
            statement_descriptor="Zulip Standard",
        )
        stripe.Invoice.finalize_invoice(stripe_invoice)

    plan.next_invoice_date = next_invoice_date(plan)
    plan.save(update_fields=["next_invoice_date"])


def invoice_plans_as_needed(event_time: datetime = timezone_now()) -> None:
    for plan in CustomerPlan.objects.filter(next_invoice_date__lte=event_time):
        invoice_plan(plan, event_time)


def is_realm_on_free_trial(realm: Realm) -> bool:
    plan = get_current_plan_by_realm(realm)
    return plan is not None and plan.is_free_trial()


def attach_discount_to_realm(
    realm: Realm, discount: Decimal, *, acting_user: Optional[UserProfile]
) -> None:
    customer = get_customer_by_realm(realm)
    old_discount: Optional[Decimal] = None
    if customer is not None:
        old_discount = customer.default_discount
        customer.default_discount = discount
        customer.save(update_fields=["default_discount"])
    else:
        Customer.objects.create(realm=realm, default_discount=discount)
    plan = get_current_plan_by_realm(realm)
    if plan is not None:
        plan.price_per_license = get_price_per_license(plan.tier, plan.billing_schedule, discount)
        plan.discount = discount
        plan.save(update_fields=["price_per_license", "discount"])
    RealmAuditLog.objects.create(
        realm=realm,
        acting_user=acting_user,
        event_type=RealmAuditLog.REALM_DISCOUNT_CHANGED,
        event_time=timezone_now(),
        extra_data={"old_discount": old_discount, "new_discount": discount},
    )


def update_sponsorship_status(
    realm: Realm, sponsorship_pending: bool, *, acting_user: Optional[UserProfile]
) -> None:
    customer, _ = Customer.objects.get_or_create(realm=realm)
    customer.sponsorship_pending = sponsorship_pending
    customer.save(update_fields=["sponsorship_pending"])
    RealmAuditLog.objects.create(
        realm=realm,
        acting_user=acting_user,
        event_type=RealmAuditLog.REALM_SPONSORSHIP_PENDING_STATUS_CHANGED,
        event_time=timezone_now(),
        extra_data={
            "sponsorship_pending": sponsorship_pending,
        },
    )


def approve_sponsorship(realm: Realm, *, acting_user: Optional[UserProfile]) -> None:
    from zerver.lib.actions import do_change_plan_type, internal_send_private_message

    do_change_plan_type(realm, Realm.STANDARD_FREE, acting_user=acting_user)
    customer = get_customer_by_realm(realm)
    if customer is not None and customer.sponsorship_pending:
        customer.sponsorship_pending = False
        customer.save(update_fields=["sponsorship_pending"])
        RealmAuditLog.objects.create(
            realm=realm,
            acting_user=acting_user,
            event_type=RealmAuditLog.REALM_SPONSORSHIP_APPROVED,
            event_time=timezone_now(),
        )
    notification_bot = get_system_bot(settings.NOTIFICATION_BOT)
    for billing_admin in realm.get_human_billing_admin_users():
        with override_language(billing_admin.default_language):
            # Using variable to make life easier for translators if these details change.
            plan_name = "Zulip Cloud Standard"
            emoji = ":tada:"
            message = _(
                f"Your organization's request for sponsored hosting has been approved! {emoji}.\n"
                f"You have been upgraded to {plan_name}, free of charge."
            )
            internal_send_private_message(notification_bot, billing_admin, message)


def is_sponsored_realm(realm: Realm) -> bool:
    return realm.plan_type == Realm.STANDARD_FREE


def get_discount_for_realm(realm: Realm) -> Optional[Decimal]:
    customer = get_customer_by_realm(realm)
    if customer is not None:
        return customer.default_discount
    return None


def do_change_plan_status(plan: CustomerPlan, status: int) -> None:
    plan.status = status
    plan.save(update_fields=["status"])
    billing_logger.info(
        "Change plan status: Customer.id: %s, CustomerPlan.id: %s, status: %s",
        plan.customer.id,
        plan.id,
        status,
    )


def process_downgrade(plan: CustomerPlan) -> None:
    from zerver.lib.actions import do_change_plan_type

    do_change_plan_type(plan.customer.realm, Realm.LIMITED, acting_user=None)
    plan.status = CustomerPlan.ENDED
    plan.save(update_fields=["status"])


def estimate_annual_recurring_revenue_by_realm() -> Dict[str, int]:  # nocoverage
    annual_revenue = {}
    for plan in CustomerPlan.objects.filter(status=CustomerPlan.ACTIVE).select_related(
        "customer__realm"
    ):
        # TODO: figure out what to do for plans that don't automatically
        # renew, but which probably will renew
        renewal_cents = renewal_amount(plan, timezone_now())
        if plan.billing_schedule == CustomerPlan.MONTHLY:
            renewal_cents *= 12
        # TODO: Decimal stuff
        annual_revenue[plan.customer.realm.string_id] = int(renewal_cents / 100)
    return annual_revenue


def get_realms_to_default_discount_dict() -> Dict[str, Decimal]:
    realms_to_default_discount = {}
    customers = Customer.objects.exclude(default_discount=None).exclude(default_discount=0)
    for customer in customers:
        realms_to_default_discount[customer.realm.string_id] = customer.default_discount
    return realms_to_default_discount


# During realm deactivation we instantly downgrade the plan to Limited.
# Extra users added in the final month are not charged. Also used
# for the cancellation of Free Trial.
def downgrade_now_without_creating_additional_invoices(realm: Realm) -> None:
    plan = get_current_plan_by_realm(realm)
    if plan is None:
        return

    process_downgrade(plan)
    plan.invoiced_through = LicenseLedger.objects.filter(plan=plan).order_by("id").last()
    plan.next_invoice_date = next_invoice_date(plan)
    plan.save(update_fields=["invoiced_through", "next_invoice_date"])


def downgrade_at_the_end_of_billing_cycle(realm: Realm) -> None:
    plan = get_current_plan_by_realm(realm)
    assert plan is not None
    do_change_plan_status(plan, CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE)


def void_all_open_invoices(realm: Realm) -> int:
    customer = get_customer_by_realm(realm)
    if customer is None:
        return 0
    invoices = stripe.Invoice.list(customer=customer.stripe_customer_id)
    voided_invoices_count = 0
    for invoice in invoices:
        if invoice.status == "open":
            stripe.Invoice.void_invoice(invoice.id)
            voided_invoices_count += 1
    return voided_invoices_count


def update_billing_method_of_current_plan(
    realm: Realm, charge_automatically: bool, *, acting_user: Optional[UserProfile]
) -> None:
    plan = get_current_plan_by_realm(realm)
    if plan is not None:
        plan.charge_automatically = charge_automatically
        plan.save(update_fields=["charge_automatically"])
        RealmAuditLog.objects.create(
            realm=realm,
            acting_user=acting_user,
            event_type=RealmAuditLog.REALM_BILLING_METHOD_CHANGED,
            event_time=timezone_now(),
            extra_data={
                "charge_automatically": charge_automatically,
            },
        )
