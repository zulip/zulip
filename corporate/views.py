import logging
import stripe
from typing import Any, Dict, Optional, Tuple, cast

from django.core import signing
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.utils import timezone
from django.utils.translation import ugettext as _, ugettext as err_
from django.shortcuts import redirect, render
from django.urls import reverse
from django.conf import settings

from zerver.decorator import zulip_login_required, require_billing_access
from zerver.lib.json_encoder_for_html import JSONEncoderForHTML
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_error, json_success
from zerver.lib.validator import check_string, check_int
from zerver.lib.timestamp import timestamp_to_datetime
from zerver.models import UserProfile, Realm
from corporate.lib.stripe import STRIPE_PUBLISHABLE_KEY, \
    stripe_get_customer, upcoming_invoice_total, get_seat_count, \
    extract_current_subscription, process_initial_upgrade, sign_string, \
    unsign_string, BillingError, process_downgrade, do_replace_payment_source, \
    MIN_INVOICED_SEAT_COUNT, DEFAULT_INVOICE_DAYS_UNTIL_DUE
from corporate.models import Customer, Plan

billing_logger = logging.getLogger('corporate.stripe')

def unsign_and_check_upgrade_parameters(user: UserProfile, plan_nickname: str,
                                        signed_seat_count: str, salt: str,
                                        billing_modality: str) -> Tuple[Plan, int]:
    provided_plans = {
        'charge_automatically': [Plan.CLOUD_ANNUAL, Plan.CLOUD_MONTHLY],
        'send_invoice': [Plan.CLOUD_ANNUAL],
    }
    if plan_nickname not in provided_plans[billing_modality]:
        billing_logger.warning("Tampered plan during realm upgrade. user: %s, realm: %s (%s)."
                               % (user.id, user.realm.id, user.realm.string_id))
        raise BillingError('tampered plan', BillingError.CONTACT_SUPPORT)
    plan = Plan.objects.get(nickname=plan_nickname)

    try:
        seat_count = int(unsign_string(signed_seat_count, salt))
    except signing.BadSignature:
        billing_logger.warning("Tampered seat count during realm upgrade. user: %s, realm: %s (%s)."
                               % (user.id, user.realm.id, user.realm.string_id))
        raise BillingError('tampered seat count', BillingError.CONTACT_SUPPORT)
    return plan, seat_count

def payment_method_string(stripe_customer: stripe.Customer) -> str:
    subscription = extract_current_subscription(stripe_customer)
    if subscription is not None and subscription.billing == "send_invoice":
        return _("Billed by invoice")
    stripe_source = stripe_customer.default_source
    # In case of e.g. an expired card
    if stripe_source is None:  # nocoverage
        return _("No payment method on file")
    if stripe_source.object == "card":
        return _("Card ending in %(last4)s" % {'last4': cast(stripe.Card, stripe_source).last4})
    # You can get here if e.g. you sign up to pay by invoice, and then
    # immediately downgrade. In that case, stripe_source.object == 'source',
    # and stripe_source.type = 'ach_credit_transfer'.
    # Using a catch-all error message here since there might be one-off stuff we
    # do for a particular customer that would land them here. E.g. by default we
    # don't support ACH for automatic payments, but in theory we could add it for
    # a customer via the Stripe dashboard.
    return _("Unknown payment method. Please contact %s." % (settings.ZULIP_ADMINISTRATOR,))  # nocoverage

@has_request_variables
def upgrade(request: HttpRequest, user: UserProfile,
            plan: str=REQ(validator=check_string),
            signed_seat_count: str=REQ(validator=check_string),
            salt: str=REQ(validator=check_string),
            billing_modality: str=REQ(validator=check_string),
            invoiced_seat_count: int=REQ(validator=check_int, default=-1),
            stripe_token: str=REQ(validator=check_string, default=None)) -> HttpResponse:
    try:
        plan, seat_count = unsign_and_check_upgrade_parameters(user, plan, signed_seat_count,
                                                               salt, billing_modality)
        if billing_modality == 'send_invoice':
            min_required_seat_count = max(seat_count, MIN_INVOICED_SEAT_COUNT)
            if invoiced_seat_count < min_required_seat_count:
                raise BillingError(
                    'lowball seat count',
                    "You must invoice for at least %d users." % (min_required_seat_count,))
            seat_count = invoiced_seat_count
        process_initial_upgrade(user, plan, seat_count, stripe_token)
    except BillingError as e:
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
    if customer is not None and customer.has_billing_relationship:
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
        'min_seat_count_for_invoice': max(seat_count, MIN_INVOICED_SEAT_COUNT),
        'default_invoice_days_until_due': DEFAULT_INVOICE_DAYS_UNTIL_DUE,
        'plan': "Zulip Standard",
        'nickname_monthly': Plan.CLOUD_MONTHLY,
        'nickname_annual': Plan.CLOUD_ANNUAL,
        'page_params': JSONEncoderForHTML().encode({
            'seat_count': seat_count,
            'nickname_annual': Plan.CLOUD_ANNUAL,
            'nickname_monthly': Plan.CLOUD_MONTHLY,
            'annual_price': 8000,
            'monthly_price': 800,
            'percent_off': float(percent_off),
        }),
    }  # type: Dict[str, Any]
    response = render(request, 'corporate/upgrade.html', context=context)
    return response

PLAN_NAMES = {
    Plan.CLOUD_ANNUAL: "Zulip Standard (billed annually)",
    Plan.CLOUD_MONTHLY: "Zulip Standard (billed monthly)",
}

@zulip_login_required
def billing_home(request: HttpRequest) -> HttpResponse:
    user = request.user
    customer = Customer.objects.filter(realm=user.realm).first()
    if customer is None:
        return HttpResponseRedirect(reverse('corporate.views.initial_upgrade'))
    if not customer.has_billing_relationship:
        return HttpResponseRedirect(reverse('corporate.views.initial_upgrade'))

    if not user.is_realm_admin and not user.is_billing_admin:
        context = {'admin_access': False}  # type: Dict[str, Any]
        return render(request, 'corporate/billing.html', context=context)
    context = {'admin_access': True}

    stripe_customer = stripe_get_customer(customer.stripe_customer_id)
    if stripe_customer.account_balance > 0:  # nocoverage, waiting for mock_stripe to mature
        context.update({'account_charges': '{:,.2f}'.format(stripe_customer.account_balance / 100.)})
    if stripe_customer.account_balance < 0:  # nocoverage
        context.update({'account_credits': '{:,.2f}'.format(-stripe_customer.account_balance / 100.)})

    billed_by_invoice = False
    subscription = extract_current_subscription(stripe_customer)
    if subscription:
        plan_name = PLAN_NAMES[Plan.objects.get(stripe_plan_id=subscription.plan.id).nickname]
        seat_count = subscription.quantity
        # Need user's timezone to do this properly
        renewal_date = '{dt:%B} {dt.day}, {dt.year}'.format(
            dt=timestamp_to_datetime(subscription.current_period_end))
        renewal_amount = upcoming_invoice_total(customer.stripe_customer_id)
        if subscription.billing == 'send_invoice':
            billed_by_invoice = True
    # Can only get here by subscribing and then downgrading. We don't support downgrading
    # yet, but keeping this code here since we will soon.
    else:  # nocoverage
        plan_name = "Zulip Free"
        seat_count = 0
        renewal_date = ''
        renewal_amount = 0

    context.update({
        'plan_name': plan_name,
        'seat_count': seat_count,
        'renewal_date': renewal_date,
        'renewal_amount': '{:,.2f}'.format(renewal_amount / 100.),
        'payment_method': payment_method_string(stripe_customer),
        'billed_by_invoice': billed_by_invoice,
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
