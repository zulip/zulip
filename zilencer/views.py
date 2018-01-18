
import logging
from typing import Any, Dict, Optional, Text, Union, cast

from django.http import HttpRequest, HttpResponse
from django.utils import timezone
from django.utils.translation import ugettext as _
from django.shortcuts import render
from django.conf import settings
from django.views.decorators.http import require_GET
from django.views.decorators.csrf import csrf_exempt
import stripe
from stripe.error import CardError, RateLimitError, InvalidRequestError, \
    AuthenticationError, APIConnectionError, StripeError

from zerver.decorator import require_post, zulip_login_required
from zerver.lib.exceptions import JsonableError
from zerver.lib.push_notifications import send_android_push_notification, \
    send_apple_push_notification
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_error, json_success
from zerver.lib.validator import check_int
from zerver.models import UserProfile
from zerver.views.push_notifications import validate_token
from zilencer.models import RemotePushDeviceToken, RemoteZulipServer, Customer
from zproject.settings import get_secret

STRIPE_SECRET_KEY = get_secret('stripe_secret_key')
STRIPE_PUBLISHABLE_KEY = get_secret('stripe_publishable_key')
stripe.api_key = STRIPE_SECRET_KEY

def validate_entity(entity: Union[UserProfile, RemoteZulipServer]) -> None:
    if not isinstance(entity, RemoteZulipServer):
        raise JsonableError(_("Must validate with valid Zulip server API key"))

def validate_bouncer_token_request(entity: Union[UserProfile, RemoteZulipServer],
                                   token: bytes, kind: int) -> None:
    if kind not in [RemotePushDeviceToken.APNS, RemotePushDeviceToken.GCM]:
        raise JsonableError(_("Invalid token type"))
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
        return json_error(_("Token does not exist"))

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


@zulip_login_required
def add_payment_method(request: HttpRequest) -> HttpResponse:
    user = request.user
    ctx = {
        "publishable_key": STRIPE_PUBLISHABLE_KEY,
        "email": user.email,
    }  # type: Dict[str, Any]
    if not user.is_realm_admin:
        ctx["error_message"] = _("You should be an administrator of the organization %s to view this page."
                                 % (user.realm.name,))
        return render(request, 'zilencer/payment.html', context=ctx)
    if STRIPE_PUBLISHABLE_KEY is None:
        # Dev-only message; no translation needed.
        ctx["error_message"] = "Missing Stripe config. In dev, add to zproject/dev-secrets.conf ."
        return render(request, 'zilencer/payment.html', context=ctx)

    try:
        if request.method == "GET":
            try:
                customer_obj = Customer.objects.get(realm=user.realm)
                cards = stripe.Customer.retrieve(customer_obj.stripe_customer_id).sources.all(object="card")
                ctx["num_cards"] = len(cards["data"])
            except Customer.DoesNotExist:
                ctx["num_cards"] = 0
            return render(request, 'zilencer/payment.html', context=ctx)

        if request.method == "POST":
            token = request.POST.get("stripeToken", "")
            # The card metadata doesn't show up in Dashboard but can be accessed
            # using the API.
            card_metadata = {"added_user_id": user.id, "added_user_email": user.email}
            try:
                customer_obj = Customer.objects.get(realm=user.realm)
                customer = stripe.Customer.retrieve(customer_obj.stripe_customer_id)
                customer.sources.create(source=token, metadata=card_metadata)
                ctx["num_cards"] = len(customer.sources.all(object="card")["data"])
            except Customer.DoesNotExist:
                customer_metadata = {"string_id": user.realm.string_id}
                # Description makes it easier to identify customers in Stripe dashboard
                description = "{} ({})".format(user.realm.name, user.realm.string_id)
                customer = stripe.Customer.create(source=token,
                                                  description=description,
                                                  metadata=customer_metadata)

                card = customer.sources.all(object="card")["data"][0]
                card.metadata = card_metadata
                card.save()
                Customer.objects.create(realm=user.realm, stripe_customer_id=customer.id)
                ctx["num_cards"] = 1
            ctx["payment_method_added"] = True
            return render(request, 'zilencer/payment.html', context=ctx)
    except (CardError, RateLimitError, APIConnectionError) as e:
        err = e.json_body.get('error', {})
        logging.error("Stripe error - Status: {}, Type: {}, Code: {}, Param: {}, Message: {}".format(
            e.http_status, err.get('type'), err.get('code'), err.get('param'), err.get('message')
        ))
        ctx["error_message"] = err.get('message')
        return render(request, 'zilencer/payment.html', context=ctx)
    except (InvalidRequestError, AuthenticationError, StripeError) as e:
        err = e.json_body.get('error', {})
        logging.error("Stripe error - Status: {}, Type: {}, Code: {}, Param: {}, Message: {}".format(
            e.http_status, err.get('type'), err.get('code'), err.get('param'), err.get('message')
        ))
    except Exception as e:
        logging.error('Stripe error: %s' % (str(e),))
    ctx["error_message"] = _("Something went wrong. Please try again or email us at %s."
                             % (settings.ZULIP_ADMINISTRATOR,))
    return render(request, 'zilencer/payment.html', context=ctx)
