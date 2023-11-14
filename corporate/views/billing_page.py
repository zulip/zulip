import logging
from typing import Any, Dict, Optional

import stripe
from django.conf import settings
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _

from corporate.lib.stripe import (
    RealmBillingSession,
    cents_to_dollar_string,
    do_change_plan_status,
    downgrade_at_the_end_of_billing_cycle,
    downgrade_now_without_creating_additional_invoices,
    format_money,
    get_latest_seat_count,
    renewal_amount,
    start_of_next_billing_cycle,
    stripe_get_customer,
    update_license_ledger_for_manual_plan,
    validate_licenses,
)
from corporate.models import (
    CustomerPlan,
    get_current_plan_by_customer,
    get_current_plan_by_realm,
    get_customer_by_realm,
)
from zerver.decorator import require_billing_access, zulip_login_required
from zerver.lib.exceptions import JsonableError
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.validator import check_bool, check_int, check_int_in, check_string
from zerver.models import Realm, UserProfile

billing_logger = logging.getLogger("corporate.stripe")

CARD_CAPITALIZATION = {
    "amex": "American Express",
    "diners": "Diners Club",
    "discover": "Discover",
    "jcb": "JCB",
    "mastercard": "Mastercard",
    "unionpay": "UnionPay",
    "visa": "Visa",
}


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


def add_sponsorship_info_to_context(context: Dict[str, Any], user_profile: UserProfile) -> None:
    def key_helper(d: Any) -> int:
        return d[1]["display_order"]

    context.update(
        realm_org_type=user_profile.realm.org_type,
        sorted_org_types=sorted(
            (
                [org_type_name, org_type]
                for (org_type_name, org_type) in Realm.ORG_TYPES.items()
                if not org_type.get("hidden")
            ),
            key=key_helper,
        ),
    )


@zulip_login_required
@has_request_variables
def sponsorship_request(request: HttpRequest) -> HttpResponse:
    user = request.user
    assert user.is_authenticated
    context: Dict[str, Any] = {}

    customer = get_customer_by_realm(user.realm)
    if customer is not None and customer.sponsorship_pending:
        context["is_sponsorship_pending"] = True

    if user.realm.plan_type == user.realm.PLAN_TYPE_STANDARD_FREE:
        context["is_sponsored"] = True

    add_sponsorship_info_to_context(context, user)
    return render(request, "corporate/sponsorship.html", context=context)


@zulip_login_required
@has_request_variables
def billing_home(
    request: HttpRequest,
    onboarding: bool = REQ(default=False, json_validator=check_bool),
    success_message: str = REQ(default="", str_validator=check_string),
) -> HttpResponse:
    user = request.user
    assert user.is_authenticated

    context: Dict[str, Any] = {
        "admin_access": user.has_billing_access,
        "has_active_plan": False,
        "org_name": user.realm.name,
    }

    if not user.has_billing_access:
        return render(request, "corporate/billing.html", context=context)

    if user.realm.plan_type == user.realm.PLAN_TYPE_STANDARD_FREE:
        return HttpResponseRedirect(reverse("sponsorship_request"))

    PAID_PLANS = [
        Realm.PLAN_TYPE_STANDARD,
        Realm.PLAN_TYPE_PLUS,
    ]

    customer = get_customer_by_realm(user.realm)
    if customer is not None and customer.sponsorship_pending:
        # Don't redirect to sponsorship page if the realm is on a paid plan
        if user.realm.plan_type not in PAID_PLANS:
            return HttpResponseRedirect(reverse("sponsorship_request"))
        # If the realm is on a paid plan, show the sponsorship pending message
        # TODO: Add a sponsorship pending message to the billing page
        context["sponsorship_pending"] = True

    if user.realm.plan_type == user.realm.PLAN_TYPE_LIMITED:
        return HttpResponseRedirect(reverse("plans"))

    if customer is None:
        from corporate.views.upgrade import initial_upgrade

        return HttpResponseRedirect(reverse(initial_upgrade))

    if not CustomerPlan.objects.filter(customer=customer).exists():
        from corporate.views.upgrade import initial_upgrade

        return HttpResponseRedirect(reverse(initial_upgrade))

    plan = get_current_plan_by_customer(customer)
    if plan is not None:
        now = timezone_now()
        realm = plan.customer.realm
        billing_session = RealmBillingSession(user=None, realm=realm)
        new_plan, last_ledger_entry = billing_session.make_end_of_cycle_updates_if_needed(plan, now)
        if last_ledger_entry is not None:
            if new_plan is not None:  # nocoverage
                plan = new_plan
            assert plan is not None  # for mypy
            downgrade_at_end_of_cycle = plan.status == CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE
            switch_to_annual_at_end_of_cycle = (
                plan.status == CustomerPlan.SWITCH_TO_ANNUAL_AT_END_OF_CYCLE
            )
            licenses = last_ledger_entry.licenses
            licenses_at_next_renewal = last_ledger_entry.licenses_at_next_renewal
            seat_count = get_latest_seat_count(user.realm)

            # Should do this in JavaScript, using the user's time zone
            if plan.is_free_trial():
                assert plan.next_invoice_date is not None
                renewal_date = "{dt:%B} {dt.day}, {dt.year}".format(dt=plan.next_invoice_date)
            else:
                renewal_date = "{dt:%B} {dt.day}, {dt.year}".format(
                    dt=start_of_next_billing_cycle(plan, now)
                )

            renewal_cents = renewal_amount(plan, now)
            charge_automatically = plan.charge_automatically
            assert customer.stripe_customer_id is not None  # for mypy
            stripe_customer = stripe_get_customer(customer.stripe_customer_id)
            if charge_automatically:
                payment_method = payment_method_string(stripe_customer)
            else:
                payment_method = "Billed by invoice"

            fixed_price = (
                cents_to_dollar_string(plan.fixed_price) if plan.fixed_price is not None else None
            )

            billing_frequency = CustomerPlan.BILLING_SCHEDULES[plan.billing_schedule]

            if plan.price_per_license is None:
                price_per_license = ""
            elif billing_frequency == "Annual":
                price_per_license = format_money(plan.price_per_license / 12)
            else:
                price_per_license = format_money(plan.price_per_license)

            context.update(
                plan_name=plan.name,
                has_active_plan=True,
                free_trial=plan.is_free_trial(),
                downgrade_at_end_of_cycle=downgrade_at_end_of_cycle,
                automanage_licenses=plan.automanage_licenses,
                switch_to_annual_at_end_of_cycle=switch_to_annual_at_end_of_cycle,
                licenses=licenses,
                licenses_at_next_renewal=licenses_at_next_renewal,
                seat_count=seat_count,
                renewal_date=renewal_date,
                renewal_amount=cents_to_dollar_string(renewal_cents),
                payment_method=payment_method,
                charge_automatically=charge_automatically,
                stripe_email=stripe_customer.email,
                CustomerPlan=CustomerPlan,
                onboarding=onboarding,
                billing_frequency=billing_frequency,
                fixed_price=fixed_price,
                price_per_license=price_per_license,
                success_message=success_message,
            )

    return render(request, "corporate/billing.html", context=context)


@require_billing_access
@has_request_variables
def update_plan(
    request: HttpRequest,
    user: UserProfile,
    status: Optional[int] = REQ(
        "status",
        json_validator=check_int_in(
            [
                CustomerPlan.ACTIVE,
                CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE,
                CustomerPlan.SWITCH_TO_ANNUAL_AT_END_OF_CYCLE,
                CustomerPlan.ENDED,
            ]
        ),
        default=None,
    ),
    licenses: Optional[int] = REQ("licenses", json_validator=check_int, default=None),
    licenses_at_next_renewal: Optional[int] = REQ(
        "licenses_at_next_renewal", json_validator=check_int, default=None
    ),
) -> HttpResponse:
    plan = get_current_plan_by_realm(user.realm)
    assert plan is not None  # for mypy

    realm = plan.customer.realm
    billing_session = RealmBillingSession(user=None, realm=realm)
    new_plan, last_ledger_entry = billing_session.make_end_of_cycle_updates_if_needed(
        plan, timezone_now()
    )
    if new_plan is not None:
        raise JsonableError(
            _("Unable to update the plan. The plan has been expired and replaced with a new plan.")
        )

    if last_ledger_entry is None:
        raise JsonableError(_("Unable to update the plan. The plan has ended."))

    if status is not None:
        if status == CustomerPlan.ACTIVE:
            assert plan.status == CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE
            do_change_plan_status(plan, status)
        elif status == CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE:
            assert plan.status == CustomerPlan.ACTIVE
            downgrade_at_the_end_of_billing_cycle(user.realm)
        elif status == CustomerPlan.SWITCH_TO_ANNUAL_AT_END_OF_CYCLE:
            assert plan.billing_schedule == CustomerPlan.MONTHLY
            assert plan.status == CustomerPlan.ACTIVE
            assert plan.fixed_price is None
            do_change_plan_status(plan, status)
        elif status == CustomerPlan.ENDED:
            assert plan.is_free_trial()
            downgrade_now_without_creating_additional_invoices(user.realm)
        return json_success(request)

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
            get_latest_seat_count(user.realm),
            plan.customer.exempt_from_license_number_check,
        )
        update_license_ledger_for_manual_plan(plan, timezone_now(), licenses=licenses)
        return json_success(request)

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
            get_latest_seat_count(user.realm),
            plan.customer.exempt_from_license_number_check,
        )
        update_license_ledger_for_manual_plan(
            plan, timezone_now(), licenses_at_next_renewal=licenses_at_next_renewal
        )
        return json_success(request)

    raise JsonableError(_("Nothing to change."))
