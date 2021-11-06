import json
import logging

import stripe
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.http import HttpRequest, HttpResponse
from django.views.decorators.csrf import csrf_exempt

from corporate.lib.stripe import STRIPE_API_VERSION
from corporate.lib.stripe_event_handler import (
    handle_checkout_session_completed_event,
    handle_payment_intent_payment_failed_event,
    handle_payment_intent_succeeded_event,
)
from corporate.models import Event, PaymentIntent, Session
from zproject.config import get_secret

billing_logger = logging.getLogger("corporate.stripe")


@csrf_exempt
def stripe_webhook(request: HttpRequest) -> HttpResponse:
    stripe_webhook_endpoint_secret = get_secret("stripe_webhook_endpoint_secret", "")
    if (
        stripe_webhook_endpoint_secret and not settings.TEST_SUITE
    ):  # nocoverage: We can't verify the signature in test suite since we fetch the events
        # from Stripe events API and manually post to the webhook endpoint.
        try:
            stripe_event = stripe.Webhook.construct_event(
                request.body,
                request.META.get("HTTP_STRIPE_SIGNATURE"),
                stripe_webhook_endpoint_secret,
            )
        except ValueError:
            return HttpResponse(status=400)
        except stripe.error.SignatureVerificationError:
            return HttpResponse(status=400)
    else:
        assert not settings.PRODUCTION
        try:
            stripe_event = stripe.Event.construct_from(json.loads(request.body), stripe.api_key)
        except Exception:
            return HttpResponse(status=400)

    if stripe_event.api_version != STRIPE_API_VERSION:
        error_message = f"Mismatch between billing system Stripe API version({STRIPE_API_VERSION}) and Stripe webhook event API version({stripe_event.api_version})."
        billing_logger.error(error_message)
        return HttpResponse(status=400)

    if stripe_event.type not in [
        "checkout.session.completed",
        "payment_intent.succeeded",
        "payment_intent.payment_failed",
    ]:
        return HttpResponse(status=200)

    if Event.objects.filter(stripe_event_id=stripe_event.id).exists():
        return HttpResponse(status=200)

    event = Event(stripe_event_id=stripe_event.id, type=stripe_event.type)

    if stripe_event.type == "checkout.session.completed":
        stripe_session = stripe_event.data.object
        assert isinstance(stripe_session, stripe.checkout.Session)
        try:
            session = Session.objects.get(stripe_session_id=stripe_session.id)
        except Session.DoesNotExist:
            return HttpResponse(status=200)
        event.content_type = ContentType.objects.get_for_model(Session)
        event.object_id = session.id
        event.save()
        handle_checkout_session_completed_event(stripe_session, event)
    elif stripe_event.type == "payment_intent.succeeded":
        stripe_payment_intent = stripe_event.data.object
        assert isinstance(stripe_payment_intent, stripe.PaymentIntent)
        try:
            payment_intent = PaymentIntent.objects.get(
                stripe_payment_intent_id=stripe_payment_intent.id
            )
        except PaymentIntent.DoesNotExist:
            # PaymentIntent that was not manually created from the billing system.
            # Could be an Invoice getting paid which is is not an event we are interested in.
            return HttpResponse(status=200)
        event.content_type = ContentType.objects.get_for_model(PaymentIntent)
        event.object_id = payment_intent.id
        event.save()
        handle_payment_intent_succeeded_event(stripe_payment_intent, event)
    elif stripe_event.type == "payment_intent.payment_failed":
        stripe_payment_intent = stripe_event.data.object
        try:
            assert isinstance(stripe_payment_intent, stripe.PaymentIntent)
            payment_intent = PaymentIntent.objects.get(
                stripe_payment_intent_id=stripe_payment_intent.id
            )
        except PaymentIntent.DoesNotExist:
            # PaymentIntent that was not manually created from the billing system.
            # Could be an Invoice getting paid which is is not an event we are interested in.
            return HttpResponse(status=200)
        event.content_type = ContentType.objects.get_for_model(PaymentIntent)
        event.object_id = payment_intent.id
        event.save()
        handle_payment_intent_payment_failed_event(stripe_payment_intent, event)
    return HttpResponse(status=200)
