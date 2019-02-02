import logging
import stripe
from typing import Any, Dict, cast

from django.core import signing
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.utils.timezone import now as timezone_now
from django.utils.translation import ugettext as _
from django.shortcuts import render
from django.urls import reverse
from django.conf import settings

from zerver.decorator import zulip_login_required, require_billing_access
from zerver.lib.json_encoder_for_html import JSONEncoderForHTML
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_error, json_success
from zerver.lib.validator import check_string, check_int
from zerver.models import UserProfile
from corporate.lib.stripe import STRIPE_PUBLISHABLE_KEY, \
    stripe_get_customer, get_seat_count, \
    process_initial_upgrade, sign_string, \
    unsign_string, BillingError, process_downgrade, do_replace_payment_source, \
    MIN_INVOICED_LICENSES, DEFAULT_INVOICE_DAYS_UNTIL_DUE, \
    next_renewal_date, renewal_amount, \
    add_plan_renewal_to_license_ledger_if_needed
from corporate.models import Customer, CustomerPlan, \
    get_active_plan

billing_logger = logging.getLogger('corporate.stripe')

def unsign_seat_count(signed_seat_count: str, salt: str) -> int:
    try:
        return int(unsign_string(signed_seat_count, salt))
    except signing.BadSignature:
        raise BillingError('tampered seat count')

def check_upgrade_parameters(
        billing_modality: str, schedule: str, license_management: str, licenses: int,
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
    if billing_modality == 'send_invoice':
        min_licenses = max(seat_count, MIN_INVOICED_LICENSES)
    if licenses is None or licenses < min_licenses:
        raise BillingError('not enough licenses',
                           _("You must invoice for at least {} users.".format(min_licenses)))

# Should only be called if the customer is being charged automatically
def payment_method_string(stripe_customer: stripe.Customer) -> str:
    stripe_source = stripe_customer.default_source
    # In case of e.g. an expired card
    if stripe_source is None:  # nocoverage
        return _("No payment method on file")
    if stripe_source.object == "card":
        return _("%(brand)s ending in %(last4)s" % {
            'brand': cast(stripe.Card, stripe_source).brand,
            'last4': cast(stripe.Card, stripe_source).last4})
    # There might be one-off stuff we do for a particular customer that
    # would land them here. E.g. by default we don't support ACH for
    # automatic payments, but in theory we could add it for a customer via
    # the Stripe dashboard.
    return _("Unknown payment method. Please contact %s." % (settings.ZULIP_ADMINISTRATOR,))  # nocoverage

@has_request_variables
def upgrade(request: HttpRequest, user: UserProfile,
            billing_modality: str=REQ(validator=check_string),
            schedule: str=REQ(validator=check_string),
            license_management: str=REQ(validator=check_string, default=None),
            licenses: int=REQ(validator=check_int, default=None),
            stripe_token: str=REQ(validator=check_string, default=None),
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
        automanage_licenses = license_management == 'automatic'

        billing_schedule = {'annual': CustomerPlan.ANNUAL,
                            'monthly': CustomerPlan.MONTHLY}[schedule]
        process_initial_upgrade(user, licenses, automanage_licenses, billing_schedule, stripe_token)
    except BillingError as e:
        if not settings.TEST_SUITE:  # nocoverage
            billing_logger.warning(
                ("BillingError during upgrade: %s. user=%s, realm=%s (%s), billing_modality=%s, "
                 "schedule=%s, license_management=%s, licenses=%s, has stripe_token: %s")
                % (e.description, user.id, user.realm.id, user.realm.string_id, billing_modality,
                   schedule, license_management, licenses, stripe_token is not None))
        return json_error(e.message, data={'error_description': e.description})
    except Exception as e:
        billing_logger.exception("Uncaught exception in billing: %s" % (e,))
        error_message = BillingError.CONTACT_SUPPORT
        error_description = "uncaught exception during upgrade"
        return json_error(error_message, data={'error_description': error_description})
    else:
        return json_success()

@zulip_login_required
def initial_upgrade(request: HttpRequest) -> HttpResponse:
    if not settings.BILLING_ENABLED:
        return render(request, "404.html")

    user = request.user
    customer = Customer.objects.filter(realm=user.realm).first()
    if customer is not None and CustomerPlan.objects.filter(customer=customer).exists():
        return HttpResponseRedirect(reverse('corporate.views.billing_home'))

    percent_off = 0
    if customer is not None and customer.default_discount is not None:
        percent_off = customer.default_discount

    seat_count = get_seat_count(user.realm)
    signed_seat_count, salt = sign_string(str(seat_count))
    context = {
        'publishable_key': STRIPE_PUBLISHABLE_KEY,
        'email': user.email,
        'seat_count': seat_count,
        'signed_seat_count': signed_seat_count,
        'salt': salt,
        'min_invoiced_licenses': max(seat_count, MIN_INVOICED_LICENSES),
        'default_invoice_days_until_due': DEFAULT_INVOICE_DAYS_UNTIL_DUE,
        'plan': "Zulip Standard",
        'page_params': JSONEncoderForHTML().encode({
            'seat_count': seat_count,
            'annual_price': 8000,
            'monthly_price': 800,
            'percent_off': float(percent_off),
        }),
    }  # type: Dict[str, Any]
    response = render(request, 'corporate/upgrade.html', context=context)
    return response

@zulip_login_required
def billing_home(request: HttpRequest) -> HttpResponse:
    user = request.user
    customer = Customer.objects.filter(realm=user.realm).first()
    if customer is None:
        return HttpResponseRedirect(reverse('corporate.views.initial_upgrade'))
    if not CustomerPlan.objects.filter(customer=customer).exists():
        return HttpResponseRedirect(reverse('corporate.views.initial_upgrade'))

    if not user.is_realm_admin and not user.is_billing_admin:
        context = {'admin_access': False}  # type: Dict[str, Any]
        return render(request, 'corporate/billing.html', context=context)
    context = {'admin_access': True}

    stripe_customer = stripe_get_customer(customer.stripe_customer_id)
    plan = get_active_plan(customer)
    if plan is not None:
        plan_name = {
            CustomerPlan.STANDARD: 'Zulip Standard',
            CustomerPlan.PLUS: 'Zulip Plus',
        }[plan.tier]
        now = timezone_now()
        last_ledger_entry = add_plan_renewal_to_license_ledger_if_needed(plan, now)
        licenses = last_ledger_entry.licenses
        licenses_used = get_seat_count(user.realm)
        # Should do this in javascript, using the user's timezone
        renewal_date = '{dt:%B} {dt.day}, {dt.year}'.format(dt=next_renewal_date(plan, now))
        renewal_cents = renewal_amount(plan, now)
        # TODO: this is the case where the plan doesn't automatically renew
        if renewal_cents is None:  # nocoverage
            renewal_cents = 0
        charge_automatically = plan.charge_automatically
        if charge_automatically:
            payment_method = payment_method_string(stripe_customer)
        else:
            payment_method = 'Billed by invoice'
    # Can only get here by subscribing and then downgrading. We don't support downgrading
    # yet, but keeping this code here since we will soon.
    else:  # nocoverage
        plan_name = "Zulip Free"
        licenses = 0
        renewal_date = ''
        renewal_cents = 0
        payment_method = ''
        charge_automatically = False

    context.update({
        'plan_name': plan_name,
        'licenses': licenses,
        'licenses_used': licenses_used,
        'renewal_date': renewal_date,
        'renewal_amount': '{:,.2f}'.format(renewal_cents / 100.),
        'payment_method': payment_method,
        'charge_automatically': charge_automatically,
        'publishable_key': STRIPE_PUBLISHABLE_KEY,
        'stripe_email': stripe_customer.email,
    })
    return render(request, 'corporate/billing.html', context=context)

@require_billing_access
def downgrade(request: HttpRequest, user: UserProfile) -> HttpResponse:  # nocoverage
    try:
        process_downgrade(user)
    except BillingError as e:
        return json_error(e.message, data={'error_description': e.description})
    return json_success()

@require_billing_access
@has_request_variables
def replace_payment_source(request: HttpRequest, user: UserProfile,
                           stripe_token: str=REQ("stripe_token", validator=check_string)) -> HttpResponse:
    try:
        do_replace_payment_source(user, stripe_token)
    except BillingError as e:
        return json_error(e.message, data={'error_description': e.description})
    return json_success()
