
from typing import Any, Dict, Optional, Text, TypeVar, Union, cast

from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.utils import timezone
from django.utils.translation import ugettext as _, ugettext as err_
from django.shortcuts import redirect, render
from django.urls import reverse
from django.conf import settings
from django.views.decorators.http import require_GET
from django.views.decorators.csrf import csrf_exempt

from zerver.decorator import require_post, zulip_login_required
from zerver.lib.exceptions import JsonableError
from zerver.lib.push_notifications import send_android_push_notification, \
    send_apple_push_notification
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_error, json_success
from zerver.lib.timestamp import timestamp_to_datetime
from zerver.lib.validator import check_int
from zerver.models import UserProfile, Realm
from zerver.views.push_notifications import validate_token
from zilencer.lib.stripe import STRIPE_PUBLISHABLE_KEY, StripeError, \
    do_create_customer_with_payment_source, do_subscribe_customer_to_plan, \
    get_stripe_customer, get_upcoming_invoice, payment_source
from zilencer.models import RemotePushDeviceToken, RemoteZulipServer, \
    Customer, Plan

def validate_entity(entity: Union[UserProfile, RemoteZulipServer]) -> None:
    if not isinstance(entity, RemoteZulipServer):
        raise JsonableError(err_("Invalid API key"))

def validate_bouncer_token_request(entity: Union[UserProfile, RemoteZulipServer],
                                   token: bytes, kind: int) -> None:
    if kind not in [RemotePushDeviceToken.APNS, RemotePushDeviceToken.GCM]:
        raise JsonableError(err_("Invalid token type"))
    validate_entity(entity)
    validate_token(token, kind)

@has_request_variables
def remote_server_register_push(request: HttpRequest, entity: Union[UserProfile, RemoteZulipServer],
                                user_id: int=REQ(), token: bytes=REQ(),
                                token_kind: int=REQ(validator=check_int),
                                ios_app_id: Optional[Text]=None) -> HttpResponse:
    validate_bouncer_token_request(entity, token, token_kind)
    server = cast(RemoteZulipServer, entity)

    # If a user logged out on a device and failed to unregister,
    # we should delete any other user associations for this token
    # & RemoteServer pair
    RemotePushDeviceToken.objects.filter(
        token=token, kind=token_kind, server=server).exclude(user_id=user_id).delete()

    # Save or update
    remote_token, created = RemotePushDeviceToken.objects.update_or_create(
        user_id=user_id,
        server=server,
        kind=token_kind,
        token=token,
        defaults=dict(
            ios_app_id=ios_app_id,
            last_updated=timezone.now()))

    return json_success()

@has_request_variables
def remote_server_unregister_push(request: HttpRequest, entity: Union[UserProfile, RemoteZulipServer],
                                  token: bytes=REQ(),
                                  token_kind: int=REQ(validator=check_int),
                                  ios_app_id: Optional[Text]=None) -> HttpResponse:
    validate_bouncer_token_request(entity, token, token_kind)
    server = cast(RemoteZulipServer, entity)
    deleted = RemotePushDeviceToken.objects.filter(token=token,
                                                   kind=token_kind,
                                                   server=server).delete()
    if deleted[0] == 0:
        return json_error(err_("Token does not exist"))

    return json_success()

@has_request_variables
def remote_server_notify_push(request: HttpRequest, entity: Union[UserProfile, RemoteZulipServer],
                              payload: Dict[str, Any]=REQ(argument_type='body')) -> HttpResponse:
    validate_entity(entity)
    server = cast(RemoteZulipServer, entity)

    user_id = payload['user_id']
    gcm_payload = payload['gcm_payload']
    apns_payload = payload['apns_payload']

    android_devices = list(RemotePushDeviceToken.objects.filter(
        user_id=user_id,
        kind=RemotePushDeviceToken.GCM,
        server=server
    ))

    apple_devices = list(RemotePushDeviceToken.objects.filter(
        user_id=user_id,
        kind=RemotePushDeviceToken.APNS,
        server=server
    ))

    if android_devices:
        send_android_push_notification(android_devices, gcm_payload, remote=True)

    if apple_devices:
        send_apple_push_notification(user_id, apple_devices, apns_payload)

    return json_success()

def billable_users(realm: Realm) -> int:
    # This is not going to match the analytics numbers, but we might not
    # have an analytics number if the realm just started today, and also
    # they may have added a bunch of people in the last day before deciding to upgrade.
    # Note that this makes it harder to "replay" billing.
    return UserProfile.objects.filter(realm=realm, is_active=True, is_bot=False).count()

@zulip_login_required
def initial_upgrade(request: HttpRequest) -> HttpResponse:
    user = request.user
    if Customer.objects.filter(realm=user.realm).exists():
        return HttpResponseRedirect(reverse('zilencer.views.billing_home'))

    if request.method == 'POST':
        stripe_customer_id = do_create_customer_with_payment_source(user, request.POST['stripeToken'])
        do_subscribe_customer_to_plan(
            stripe_customer_id=stripe_customer_id,
            stripe_plan_id=Plan.objects.get(nickname=request.POST['plan']).stripe_plan_id,
            num_users=billable_users(user.realm),
            # TODO: billing address details are passed to us in the request;
            # use that to calculate taxes.
            tax_percent=0)
        # TODO: raise error if needed
        # TODO: do_change_plan_type(realm, ..)
        return HttpResponseRedirect(reverse('zilencer.views.billing_home'))

    context = {
        'publishable_key': STRIPE_PUBLISHABLE_KEY,
        'email': user.email,
        'num_users': billable_users(user.realm),
        'plan': "Zulip Premium",
        'nickname_monthly': Plan.CLOUD_MONTHLY,
        'nickname_annual': Plan.CLOUD_ANNUAL,
    }  # type: Dict[str, Any]
    return render(request, 'zilencer/upgrade.html', context=context)

@zulip_login_required
def billing_home(request: HttpRequest) -> HttpResponse:
    user = request.user
    customer = Customer.objects.filter(realm=user.realm).first()
    if customer is None:
        return HttpResponseRedirect(reverse('zilencer.views.initial_upgrade'))

    if not user.is_realm_admin and not user == customer.billing_user:
        # context['error_message'] = _("You must be an administrator to view this page.")
        # return render(request, 'zilencer/billing.html', context=context)
        pass

    stripe_customer = get_stripe_customer(customer.stripe_customer_id)

    if stripe_customer.subscriptions:
        subscription = stripe_customer.subscriptions.data[0]
        plan_nickname = Plan.objects.get(stripe_plan_id=subscription.plan.id).nickname
        if plan_nickname == Plan.CLOUD_ANNUAL:
            plan_name = "Zulip Premium (billed annually)"
        elif plan_nickname == Plan.CLOUD_MONTHLY:
            plan_name = "Zulip Premium (billed monthly)"
        else:
            pass
        num_users = subscription.quantity
        # Need user's timezone to do this properly
        renewal_date = '{dt:%B} {dt.day}, {dt.year}'.format(
            dt=timestamp_to_datetime(subscription.current_period_end))
        renewal_amount = subscription.plan.amount * subscription.quantity / 100.
    else:
        plan_name = "Zulip Free"
        renewal_date = None
        renewal_amount = 0

    prorated_credits = 0
    prorated_charges = get_upcoming_invoice(customer.stripe_customer_id).amount_due / 100. - renewal_amount
    if prorated_charges < 0:
        prorated_credits = -prorated_charges
        prorated_charges = 0

    payment_method = None
    source = payment_source(stripe_customer)
    if source is not None:
        payment_method = "Card ending in %(last4)s" % {'last4': source.last4}

    context = {
        'plan_name': plan_name,
        'num_users': num_users,
        'renewal_date': renewal_date,
        'renewal_amount': renewal_amount,
        'payment_method': payment_method,
        'prorated_charges': prorated_charges,
        'prorated_credits': prorated_credits,
    }  # type: Dict[str, Any]

    return render(request, 'zilencer/billing.html', context=context)
