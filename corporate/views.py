import logging
from decimal import Decimal
from typing import Any, Dict, Optional, Union
from urllib.parse import urlencode, urljoin, urlunsplit

import stripe
from django.conf import settings
from django.core import signing
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.timezone import now as timezone_now
from django.utils.translation import ugettext as _

from corporate.lib.stripe import (
    DEFAULT_INVOICE_DAYS_UNTIL_DUE,
    MAX_INVOICED_LICENSES,
    MIN_INVOICED_LICENSES,
    STRIPE_PUBLISHABLE_KEY,
    BillingError,
    do_change_plan_status,
    do_replace_payment_source,
    downgrade_at_the_end_of_billing_cycle,
    downgrade_now_without_creating_additional_invoices,
    get_latest_seat_count,
    make_end_of_cycle_updates_if_needed,
    process_initial_upgrade,
    renewal_amount,
    sign_string,
    start_of_next_billing_cycle,
    stripe_get_customer,
    unsign_string,
    update_sponsorship_status,
)
from corporate.models import (
    CustomerPlan,
    get_current_plan_by_customer,
    get_current_plan_by_realm,
    get_customer_by_realm,
)
from zerver.decorator import (
    require_billing_access,
    require_organization_member,
    zulip_login_required,
)
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_error, json_success
from zerver.lib.send_email import FromAddress, send_email
from zerver.lib.validator import check_int, check_string
from zerver.models import UserProfile, get_realm

billing_logger = logging.getLogger('corporate.stripe')

def unsign_seat_count(signed_seat_count: str, salt: str) -> int:
    try:
        return int(unsign_string(signed_seat_count, salt))
    except signing.BadSignature:
        raise BillingError('tampered seat count')

def check_upgrade_parameters(
        billing_modality: str, schedule: str, license_management: Optional[str], licenses: Optional[int],
        has_stripe_token: bool, seat_count: int) -> None:
    if billing_modality not in ['send_invoice', 'charge_automatically']:
        raise BillingError('unknown billing_modality')
    if schedule not in ['annual', 'monthly']:
        raise BillingError('unknown schedule')
    if license_management not in ['automatic', 'manual']:
        raise BillingError('unknown license_management')

    if billing_modality == 'charge_automatically':
        if not has_stripe_token:
            raise BillingError('autopay with no card')

    min_licenses = seat_count
    max_licenses = None
    if billing_modality == 'send_invoice':
        min_licenses = max(seat_count, MIN_INVOICED_LICENSES)
        max_licenses = MAX_INVOICED_LICENSES

    if licenses is None or licenses < min_licenses:
        raise BillingError('not enough licenses',
                           _("You must invoice for at least {} users.").format(min_licenses))

    if max_licenses is not None and licenses > max_licenses:
        message = _("Invoices with more than {} licenses can't be processed from this page. To complete "
                    "the upgrade, please contact {}.").format(max_licenses, settings.ZULIP_ADMINISTRATOR)
        raise BillingError('too many licenses', message)

# Should only be called if the customer is being charged automatically
def payment_method_string(stripe_customer: stripe.Customer) -> str:
    stripe_source: Optional[Union[stripe.Card, stripe.Source]] = stripe_customer.default_source
    # In case of e.g. an expired card
    if stripe_source is None:  # nocoverage
        return _("No payment method on file")
    if stripe_source.object == "card":
        assert isinstance(stripe_source, stripe.Card)
        return _("{brand} ending in {last4}").format(
            brand=stripe_source.brand, last4=stripe_source.last4,
        )
    # There might be one-off stuff we do for a particular customer that
    # would land them here. E.g. by default we don't support ACH for
    # automatic payments, but in theory we could add it for a customer via
    # the Stripe dashboard.
    return _("Unknown payment method. Please contact {email}.").format(
        email=settings.ZULIP_ADMINISTRATOR,
    )  # nocoverage

@require_organization_member
@has_request_variables
def upgrade(request: HttpRequest, user: UserProfile,
            billing_modality: str=REQ(validator=check_string),
            schedule: str=REQ(validator=check_string),
            license_management: Optional[str]=REQ(validator=check_string, default=None),
            licenses: Optional[int]=REQ(validator=check_int, default=None),
            stripe_token: Optional[str]=REQ(validator=check_string, default=None),
            signed_seat_count: str=REQ(validator=check_string),
            salt: str=REQ(validator=check_string)) -> HttpResponse:
    try:
        seat_count = unsign_seat_count(signed_seat_count, salt)
        if billing_modality == 'charge_automatically' and license_management == 'automatic':
            licenses = seat_count
        if billing_modality == 'send_invoice':
            schedule = 'annual'
            license_management = 'manual'
        check_upgrade_parameters(
            billing_modality, schedule, license_management, licenses,
            stripe_token is not None, seat_count)
        assert licenses is not None
        automanage_licenses = license_management == 'automatic'

        billing_schedule = {'annual': CustomerPlan.ANNUAL,
                            'monthly': CustomerPlan.MONTHLY}[schedule]
        process_initial_upgrade(user, licenses, automanage_licenses, billing_schedule, stripe_token)
    except BillingError as e:
        if not settings.TEST_SUITE:  # nocoverage
            billing_logger.warning(
                "BillingError during upgrade: %s. user=%s, realm=%s (%s), billing_modality=%s, "
                "schedule=%s, license_management=%s, licenses=%s, has stripe_token: %s",
                e.description, user.id, user.realm.id, user.realm.string_id, billing_modality,
                schedule, license_management, licenses, stripe_token is not None,
            )
        return json_error(e.message, data={'error_description': e.description})
    except Exception:
        billing_logger.exception("Uncaught exception in billing:", stack_info=True)
        error_message = BillingError.CONTACT_SUPPORT
        error_description = "uncaught exception during upgrade"
        return json_error(error_message, data={'error_description': error_description})
    else:
        return json_success()

@zulip_login_required
def initial_upgrade(request: HttpRequest) -> HttpResponse:
    user = request.user

    if not settings.BILLING_ENABLED or user.is_guest:
        return render(request, "404.html", status=404)

    billing_page_url = reverse(billing_home)

    customer = get_customer_by_realm(user.realm)
    if customer is not None and (get_current_plan_by_customer(customer) is not None or customer.sponsorship_pending):
        if request.GET.get("onboarding") is not None:
            billing_page_url = f"{billing_page_url}?onboarding=true"
        return HttpResponseRedirect(billing_page_url)

    if user.realm.plan_type == user.realm.STANDARD_FREE:
        return HttpResponseRedirect(billing_page_url)

    percent_off = Decimal(0)
    if customer is not None and customer.default_discount is not None:
        percent_off = customer.default_discount

    seat_count = get_latest_seat_count(user.realm)
    signed_seat_count, salt = sign_string(str(seat_count))
    context: Dict[str, Any] = {
        'realm': user.realm,
        'publishable_key': STRIPE_PUBLISHABLE_KEY,
        'email': user.delivery_email,
        'seat_count': seat_count,
        'signed_seat_count': signed_seat_count,
        'salt': salt,
        'min_invoiced_licenses': max(seat_count, MIN_INVOICED_LICENSES),
        'default_invoice_days_until_due': DEFAULT_INVOICE_DAYS_UNTIL_DUE,
        'plan': "Zulip Standard",
        "free_trial_days": settings.FREE_TRIAL_DAYS,
        "onboarding": request.GET.get("onboarding") is not None,
        'page_params': {
            'seat_count': seat_count,
            'annual_price': 8000,
            'monthly_price': 800,
            'percent_off': float(percent_off),
        },
    }
    response = render(request, 'corporate/upgrade.html', context=context)
    return response

@require_organization_member
@has_request_variables
def sponsorship(request: HttpRequest, user: UserProfile,
                organization_type: str=REQ("organization-type", validator=check_string),
                website: str=REQ("website", validator=check_string),
                description: str=REQ("description", validator=check_string)) -> HttpResponse:
    realm = user.realm

    requested_by = user.full_name
    user_role = user.get_role_name()

    support_realm_uri = get_realm(settings.STAFF_SUBDOMAIN).uri
    support_url = urljoin(support_realm_uri, urlunsplit(("", "", reverse("support"),
                          urlencode({"q": realm.string_id}), "")))

    context = {
        "requested_by": requested_by,
        "user_role": user_role,
        "string_id": realm.string_id,
        "support_url": support_url,
        "organization_type": organization_type,
        "website": website,
        "description": description,
    }
    send_email(
        "zerver/emails/sponsorship_request",
        to_emails=[FromAddress.SUPPORT],
        from_name="Zulip sponsorship",
        from_address=FromAddress.tokenized_no_reply_address(),
        reply_to_email=user.delivery_email,
        context=context,
    )

    update_sponsorship_status(realm, True)
    user.is_billing_admin = True
    user.save(update_fields=["is_billing_admin"])

    return json_success()

@zulip_login_required
def billing_home(request: HttpRequest) -> HttpResponse:
    user = request.user
    customer = get_customer_by_realm(user.realm)
    context: Dict[str, Any] = {
        "admin_access": user.has_billing_access,
        'has_active_plan': False,
    }

    if user.realm.plan_type == user.realm.STANDARD_FREE:
        context["is_sponsored"] = True
        return render(request, 'corporate/billing.html', context=context)

    if customer is None:
        return HttpResponseRedirect(reverse(initial_upgrade))

    if customer.sponsorship_pending:
        context["sponsorship_pending"] = True
        return render(request, 'corporate/billing.html', context=context)

    if not CustomerPlan.objects.filter(customer=customer).exists():
        return HttpResponseRedirect(reverse(initial_upgrade))

    if not user.has_billing_access:
        return render(request, 'corporate/billing.html', context=context)

    plan = get_current_plan_by_customer(customer)
    if plan is not None:
        now = timezone_now()
        new_plan, last_ledger_entry = make_end_of_cycle_updates_if_needed(plan, now)
        if last_ledger_entry is not None:
            if new_plan is not None:  # nocoverage
                plan = new_plan
            assert(plan is not None)  # for mypy
            free_trial = plan.status == CustomerPlan.FREE_TRIAL
            downgrade_at_end_of_cycle = plan.status == CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE
            switch_to_annual_at_end_of_cycle = plan.status == CustomerPlan.SWITCH_TO_ANNUAL_AT_END_OF_CYCLE
            licenses = last_ledger_entry.licenses
            licenses_used = get_latest_seat_count(user.realm)
            # Should do this in javascript, using the user's timezone
            renewal_date = '{dt:%B} {dt.day}, {dt.year}'.format(dt=start_of_next_billing_cycle(plan, now))
            renewal_cents = renewal_amount(plan, now)
            charge_automatically = plan.charge_automatically
            stripe_customer = stripe_get_customer(customer.stripe_customer_id)
            if charge_automatically:
                payment_method = payment_method_string(stripe_customer)
            else:
                payment_method = 'Billed by invoice'

            context.update(
                plan_name=plan.name,
                has_active_plan=True,
                free_trial=free_trial,
                downgrade_at_end_of_cycle=downgrade_at_end_of_cycle,
                automanage_licenses=plan.automanage_licenses,
                switch_to_annual_at_end_of_cycle=switch_to_annual_at_end_of_cycle,
                licenses=licenses,
                licenses_used=licenses_used,
                renewal_date=renewal_date,
                renewal_amount=f'{renewal_cents / 100.:,.2f}',
                payment_method=payment_method,
                charge_automatically=charge_automatically,
                publishable_key=STRIPE_PUBLISHABLE_KEY,
                stripe_email=stripe_customer.email,
                CustomerPlan=CustomerPlan,
                onboarding=request.GET.get("onboarding") is not None,
            )

    return render(request, 'corporate/billing.html', context=context)

@require_billing_access
@has_request_variables
def change_plan_status(request: HttpRequest, user: UserProfile,
                       status: int=REQ("status", validator=check_int)) -> HttpResponse:
    assert(status in [CustomerPlan.ACTIVE, CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE,
                      CustomerPlan.SWITCH_TO_ANNUAL_AT_END_OF_CYCLE, CustomerPlan.ENDED])

    plan = get_current_plan_by_realm(user.realm)
    assert(plan is not None)  # for mypy

    if status == CustomerPlan.ACTIVE:
        assert(plan.status == CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE)
        do_change_plan_status(plan, status)
    elif status == CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE:
        assert(plan.status == CustomerPlan.ACTIVE)
        downgrade_at_the_end_of_billing_cycle(user.realm)
    elif status == CustomerPlan.SWITCH_TO_ANNUAL_AT_END_OF_CYCLE:
        assert(plan.billing_schedule == CustomerPlan.MONTHLY)
        assert(plan.status == CustomerPlan.ACTIVE)
        assert(plan.fixed_price is None)
        do_change_plan_status(plan, status)
    elif status == CustomerPlan.ENDED:
        assert(plan.status == CustomerPlan.FREE_TRIAL)
        downgrade_now_without_creating_additional_invoices(user.realm)
    return json_success()

@require_billing_access
@has_request_variables
def replace_payment_source(request: HttpRequest, user: UserProfile,
                           stripe_token: str=REQ("stripe_token", validator=check_string)) -> HttpResponse:
    try:
        do_replace_payment_source(user, stripe_token, pay_invoices=True)
    except BillingError as e:
        return json_error(e.message, data={'error_description': e.description})
    return json_success()
