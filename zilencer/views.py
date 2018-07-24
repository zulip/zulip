from typing import Any, Dict, Optional, Union, cast

from django.core.exceptions import ValidationError
from django.core.validators import validate_email, URLValidator
from django.db import IntegrityError
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.utils import timezone
from django.utils.translation import ugettext as _, ugettext as err_
from django.shortcuts import redirect, render
from django.urls import reverse
from django.conf import settings
from django.views.decorators.http import require_GET
from django.views.decorators.csrf import csrf_exempt

from zerver.decorator import require_post, zulip_login_required, InvalidZulipServerKeyError
from zerver.lib.exceptions import JsonableError
from zerver.lib.push_notifications import send_android_push_notification, \
    send_apple_push_notification
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_error, json_success
from zerver.lib.validator import check_int, check_string, check_url, \
    validate_login_email, check_capped_string, check_string_fixed_length
from zerver.lib.timestamp import timestamp_to_datetime
from zerver.models import UserProfile, Realm
from zerver.views.push_notifications import validate_token
from zilencer.lib.stripe import STRIPE_PUBLISHABLE_KEY, StripeError, \
    do_create_customer_with_payment_source, do_subscribe_customer_to_plan, \
    get_stripe_customer, get_upcoming_invoice, payment_source, \
    get_seat_count, extract_current_subscription
from zilencer.models import RemotePushDeviceToken, RemoteZulipServer, \
    Customer, Plan

def validate_entity(entity: Union[UserProfile, RemoteZulipServer]) -> None:
    if not isinstance(entity, RemoteZulipServer):
        raise JsonableError(err_("Must validate with valid Zulip server API key"))

def validate_bouncer_token_request(entity: Union[UserProfile, RemoteZulipServer],
                                   token: bytes, kind: int) -> None:
    if kind not in [RemotePushDeviceToken.APNS, RemotePushDeviceToken.GCM]:
        raise JsonableError(err_("Invalid token type"))
    validate_entity(entity)
    validate_token(token, kind)

@csrf_exempt
@require_post
@has_request_variables
def register_remote_server(
        request: HttpRequest,
        zulip_org_id: str=REQ(str_validator=check_string_fixed_length(RemoteZulipServer.UUID_LENGTH)),
        zulip_org_key: str=REQ(str_validator=check_string_fixed_length(RemoteZulipServer.API_KEY_LENGTH)),
        hostname: str=REQ(str_validator=check_capped_string(RemoteZulipServer.HOSTNAME_MAX_LENGTH)),
        contact_email: str=REQ(str_validator=check_string),
        new_org_key: Optional[str]=REQ(str_validator=check_string_fixed_length(
            RemoteZulipServer.API_KEY_LENGTH), default=None),
) -> HttpResponse:
    # REQ validated the the field lengths, but we still need to
    # validate the format of these fields.
    try:
        # TODO: Ideally we'd not abuse the URL validator this way
        url_validator = URLValidator()
        url_validator('http://' + hostname)
    except ValidationError:
        raise JsonableError(_('%s is not a valid hostname') % (hostname,))

    try:
        validate_email(contact_email)
    except ValidationError as e:
        raise JsonableError(e.message)

    remote_server, created = RemoteZulipServer.objects.get_or_create(
        uuid=zulip_org_id,
        defaults={'hostname': hostname, 'contact_email': contact_email,
                  'api_key': zulip_org_key})

    if not created:
        if remote_server.api_key != zulip_org_key:
            raise InvalidZulipServerKeyError(zulip_org_id)
        else:
            remote_server.hostname = hostname
            remote_server.contact_email = contact_email
            if new_org_key is not None:
                remote_server.api_key = new_org_key
            remote_server.save()

    return json_success({'created': created})

@has_request_variables
def register_remote_push_device(request: HttpRequest, entity: Union[UserProfile, RemoteZulipServer],
                                user_id: int=REQ(), token: bytes=REQ(),
                                token_kind: int=REQ(validator=check_int),
                                ios_app_id: Optional[str]=None) -> HttpResponse:
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
def unregister_remote_push_device(request: HttpRequest, entity: Union[UserProfile, RemoteZulipServer],
                                  token: bytes=REQ(),
                                  token_kind: int=REQ(validator=check_int),
                                  ios_app_id: Optional[str]=None) -> HttpResponse:
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
        send_apple_push_notification(user_id, apple_devices, apns_payload, remote=True)

    return json_success()

@zulip_login_required
def initial_upgrade(request: HttpRequest) -> HttpResponse:
    user = request.user
    if Customer.objects.filter(realm=user.realm).exists():
        return HttpResponseRedirect(reverse('zilencer.views.billing_home'))

    if request.method == 'POST':
        stripe_customer = do_create_customer_with_payment_source(user, request.POST['stripeToken'])
        # TODO: the current way this is done is subject to tampering by the user.
        seat_count = int(request.POST['seat_count'])
        if seat_count < 1:
            raise AssertionError('seat_count is less than 1')
        do_subscribe_customer_to_plan(
            stripe_customer=stripe_customer,
            stripe_plan_id=Plan.objects.get(nickname=request.POST['plan']).stripe_plan_id,
            seat_count=seat_count,
            # TODO: billing address details are passed to us in the request;
            # use that to calculate taxes.
            tax_percent=0)
        # TODO: check for errors and raise/send to frontend
        return HttpResponseRedirect(reverse('zilencer.views.billing_home'))

    context = {
        'publishable_key': STRIPE_PUBLISHABLE_KEY,
        'email': user.email,
        'seat_count': get_seat_count(user.realm),
        'plan': "Zulip Premium",
        'nickname_monthly': Plan.CLOUD_MONTHLY,
        'nickname_annual': Plan.CLOUD_ANNUAL,
    }  # type: Dict[str, Any]
    return render(request, 'zilencer/upgrade.html', context=context)

PLAN_NAMES = {
    Plan.CLOUD_ANNUAL: "Zulip Premium (billed annually)",
    Plan.CLOUD_MONTHLY: "Zulip Premium (billed monthly)",
}

@zulip_login_required
def billing_home(request: HttpRequest) -> HttpResponse:
    user = request.user
    customer = Customer.objects.filter(realm=user.realm).first()
    if customer is None:
        return HttpResponseRedirect(reverse('zilencer.views.initial_upgrade'))

    if not user.is_realm_admin and not user == customer.billing_user:
        context = {'admin_access': False}  # type: Dict[str, Any]
        return render(request, 'zilencer/billing.html', context=context)
    context = {'admin_access': True}

    stripe_customer = get_stripe_customer(customer.stripe_customer_id)
    subscription = extract_current_subscription(stripe_customer)

    if subscription:
        plan_name = PLAN_NAMES[Plan.objects.get(stripe_plan_id=subscription.plan.id).nickname]
        seat_count = subscription.quantity
        # Need user's timezone to do this properly
        renewal_date = '{dt:%B} {dt.day}, {dt.year}'.format(
            dt=timestamp_to_datetime(subscription.current_period_end))
        upcoming_invoice = get_upcoming_invoice(customer.stripe_customer_id)
        renewal_amount = subscription.plan.amount * subscription.quantity / 100.
        prorated_credits = 0
        prorated_charges = upcoming_invoice.amount_due / 100. - renewal_amount
        if prorated_charges < 0:
            prorated_credits = -prorated_charges  # nocoverage -- no way to get here yet
            prorated_charges = 0  # nocoverage
    else:  # nocoverage -- no way to get here yet
        plan_name = "Zulip Free"
        renewal_date = ''
        renewal_amount = 0
        prorated_credits = 0
        prorated_charges = 0
        seat_count = 0

    payment_method = None
    source = payment_source(stripe_customer)
    if source is not None:
        payment_method = "Card ending in %(last4)s" % {'last4': source.last4}

    context.update({
        'plan_name': plan_name,
        'seat_count': seat_count,
        'renewal_date': renewal_date,
        'renewal_amount': '{:,.2f}'.format(renewal_amount),
        'payment_method': payment_method,
        'prorated_charges': '{:,.2f}'.format(prorated_charges),
        'prorated_credits': '{:,.2f}'.format(prorated_credits),
    })

    return render(request, 'zilencer/billing.html', context=context)
