from typing import Any, Dict, Optional, Tuple
import logging

from django.core import signing
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.utils import timezone
from django.utils.translation import ugettext as _, ugettext as err_
from django.shortcuts import redirect, render
from django.urls import reverse
from django.conf import settings

from zerver.decorator import zulip_login_required, require_billing_access
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_error, json_success
from zerver.lib.validator import check_string
from zerver.lib.timestamp import timestamp_to_datetime
from zerver.models import UserProfile, Realm
from corporate.lib.stripe import STRIPE_PUBLISHABLE_KEY, \
    stripe_get_customer, stripe_get_upcoming_invoice, get_seat_count, \
    extract_current_subscription, process_initial_upgrade, sign_string, \
    unsign_string, BillingError, process_downgrade, do_replace_payment_source
from corporate.models import Customer, Plan

billing_logger = logging.getLogger('corporate.stripe')

def unsign_and_check_upgrade_parameters(user: UserProfile, plan_nickname: str,
                                        signed_seat_count: str, salt: str) -> Tuple[Plan, int]:
    if plan_nickname not in [Plan.CLOUD_ANNUAL, Plan.CLOUD_MONTHLY]:
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

@zulip_login_required
def initial_upgrade(request: HttpRequest) -> HttpResponse:
    if not settings.BILLING_ENABLED:
        return render(request, "404.html")

    user = request.user
    error_message = ""
    error_description = ""  # only used in tests

    customer = Customer.objects.filter(realm=user.realm).first()
    if customer is not None and customer.has_billing_relationship:
        return HttpResponseRedirect(reverse('corporate.views.billing_home'))

    if request.method == 'POST':
        try:
            plan, seat_count = unsign_and_check_upgrade_parameters(
                user, request.POST['plan'], request.POST['signed_seat_count'], request.POST['salt'])
            process_initial_upgrade(user, plan, seat_count, request.POST['stripeToken'])
        except BillingError as e:
            error_message = e.message
            error_description = e.description
        except Exception as e:
            billing_logger.exception("Uncaught exception in billing: %s" % (e,))
            error_message = BillingError.CONTACT_SUPPORT
            error_description = "uncaught exception during upgrade"
        else:
            return HttpResponseRedirect(reverse('corporate.views.billing_home'))

    seat_count = get_seat_count(user.realm)
    signed_seat_count, salt = sign_string(str(seat_count))
    context = {
        'publishable_key': STRIPE_PUBLISHABLE_KEY,
        'email': user.email,
        'seat_count': seat_count,
        'signed_seat_count': signed_seat_count,
        'salt': salt,
        'plan': "Zulip Standard",
        'nickname_monthly': Plan.CLOUD_MONTHLY,
        'nickname_annual': Plan.CLOUD_ANNUAL,
        'error_message': error_message,
        'cloud_monthly_price': 8,
        'cloud_annual_price': 80,
        'cloud_annual_price_per_month': 6.67,
    }  # type: Dict[str, Any]
    response = render(request, 'corporate/upgrade.html', context=context)
    response['error_description'] = error_description
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

    subscription = extract_current_subscription(stripe_customer)
    if subscription:
        plan_name = PLAN_NAMES[Plan.objects.get(stripe_plan_id=subscription.plan.id).nickname]
        seat_count = subscription.quantity
        # Need user's timezone to do this properly
        renewal_date = '{dt:%B} {dt.day}, {dt.year}'.format(
            dt=timestamp_to_datetime(subscription.current_period_end))
        renewal_amount = stripe_get_upcoming_invoice(customer.stripe_customer_id).total
    # Can only get here by subscribing and then downgrading. We don't support downgrading
    # yet, but keeping this code here since we will soon.
    else:  # nocoverage
        plan_name = "Zulip Free"
        seat_count = 0
        renewal_date = ''
        renewal_amount = 0

    payment_method = None
    if stripe_customer.default_source is not None:
        payment_method = "Card ending in %(last4)s" % {'last4': stripe_customer.default_source.last4}

    context.update({
        'plan_name': plan_name,
        'seat_count': seat_count,
        'renewal_date': renewal_date,
        'renewal_amount': '{:,.2f}'.format(renewal_amount / 100.),
        'payment_method': payment_method,
        'publishable_key': STRIPE_PUBLISHABLE_KEY,
        'stripe_email': stripe_customer.email,
    })

    return render(request, 'corporate/billing.html', context=context)

@require_billing_access
def downgrade(request: HttpRequest, user: UserProfile) -> HttpResponse:
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
