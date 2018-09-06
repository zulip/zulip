from typing import Any, Dict, Optional, Tuple, Union, cast
import logging

from django.core import signing
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
from zilencer.lib.stripe import STRIPE_PUBLISHABLE_KEY, \
    stripe_get_customer, stripe_get_upcoming_invoice, get_seat_count, \
    extract_current_subscription, process_initial_upgrade, sign_string, \
    unsign_string, BillingError, process_downgrade, do_replace_payment_source
from zilencer.models import RemotePushDeviceToken, RemoteZulipServer, \
    Customer, Plan

billing_logger = logging.getLogger('zilencer.stripe')

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
        return HttpResponseRedirect(reverse('zilencer.views.billing_home'))

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
        else:
            return HttpResponseRedirect(reverse('zilencer.views.billing_home'))

    seat_count = get_seat_count(user.realm)
    signed_seat_count, salt = sign_string(str(seat_count))
    context = {
        'publishable_key': STRIPE_PUBLISHABLE_KEY,
        'email': user.email,
        'seat_count': seat_count,
        'signed_seat_count': signed_seat_count,
        'salt': salt,
        'plan': "Zulip Premium",
        'nickname_monthly': Plan.CLOUD_MONTHLY,
        'nickname_annual': Plan.CLOUD_ANNUAL,
        'error_message': error_message,
        'cloud_monthly_price': 8,
        'cloud_annual_price': 80,
        'cloud_annual_price_per_month': 6.67,
    }  # type: Dict[str, Any]
    response = render(request, 'zilencer/upgrade.html', context=context)
    response['error_description'] = error_description
    return response

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
    if not customer.has_billing_relationship:
        return HttpResponseRedirect(reverse('zilencer.views.initial_upgrade'))

    if not user.is_realm_admin and not user.is_billing_admin:
        context = {'admin_access': False}  # type: Dict[str, Any]
        return render(request, 'zilencer/billing.html', context=context)
    context = {'admin_access': True}

    stripe_customer = stripe_get_customer(customer.stripe_customer_id)
    subscription = extract_current_subscription(stripe_customer)

    prorated_charges = stripe_customer.account_balance
    if subscription:
        plan_name = PLAN_NAMES[Plan.objects.get(stripe_plan_id=subscription.plan.id).nickname]
        seat_count = subscription.quantity
        # Need user's timezone to do this properly
        renewal_date = '{dt:%B} {dt.day}, {dt.year}'.format(
            dt=timestamp_to_datetime(subscription.current_period_end))
        upcoming_invoice = stripe_get_upcoming_invoice(customer.stripe_customer_id)
        renewal_amount = subscription.plan.amount * subscription.quantity
        prorated_charges += upcoming_invoice.total - renewal_amount
    # Can only get here by subscribing and then downgrading. We don't support downgrading
    # yet, but keeping this code here since we will soon.
    else:  # nocoverage
        plan_name = "Zulip Free"
        seat_count = 0
        renewal_date = ''
        renewal_amount = 0

    prorated_credits = 0
    if prorated_charges < 0:  # nocoverage
        prorated_credits = -prorated_charges
        prorated_charges = 0

    payment_method = None
    if stripe_customer.default_source is not None:
        payment_method = "Card ending in %(last4)s" % {'last4': stripe_customer.default_source.last4}

    context.update({
        'plan_name': plan_name,
        'seat_count': seat_count,
        'renewal_date': renewal_date,
        'renewal_amount': '{:,.2f}'.format(renewal_amount / 100.),
        'payment_method': payment_method,
        'prorated_charges': '{:,.2f}'.format(prorated_charges / 100.),
        'prorated_credits': '{:,.2f}'.format(prorated_credits / 100.),
        'publishable_key': STRIPE_PUBLISHABLE_KEY,
        'stripe_email': stripe_customer.email,
    })

    return render(request, 'zilencer/billing.html', context=context)

def downgrade(request: HttpRequest, user: UserProfile) -> HttpResponse:
    if not user.is_realm_admin and not user.is_billing_admin:
        return json_error(_('Access denied'))
    try:
        process_downgrade(user)
    except BillingError as e:
        return json_error(e.message, data={'error_description': e.description})
    return json_success()

@has_request_variables
def replace_payment_source(request: HttpRequest, user: UserProfile,
                           stripe_token: str=REQ("stripe_token", validator=check_string)) -> HttpResponse:
    if not user.is_realm_admin and not user.is_billing_admin:
        return json_error(_("Access denied"))
    try:
        do_replace_payment_source(user, stripe_token)
    except BillingError as e:
        return json_error(e.message, data={'error_description': e.description})
    return json_success()
