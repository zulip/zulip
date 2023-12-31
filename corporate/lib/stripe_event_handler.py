import logging
from typing import Any, Callable, Dict, Optional, Union

import stripe
from django.conf import settings

from corporate.lib.stripe import (
    BillingError,
    InvalidPlanUpgradeError,
    RealmBillingSession,
    RemoteRealmBillingSession,
    RemoteServerBillingSession,
    UpgradeWithExistingPlanError,
)
from corporate.models import Customer, CustomerPlan, Event, PaymentIntent, Session
from zerver.models.users import get_active_user_profile_by_id_in_realm

billing_logger = logging.getLogger("corporate.stripe")


def error_handler(
    func: Callable[[Any, Any], None],
) -> Callable[[Union[stripe.checkout.Session, stripe.PaymentIntent], Event], None]:
    def wrapper(
        stripe_object: Union[stripe.checkout.Session, stripe.PaymentIntent], event: Event
    ) -> None:
        event.status = Event.EVENT_HANDLER_STARTED
        event.save(update_fields=["status"])

        try:
            func(stripe_object, event.content_object)
        except BillingError as e:
            billing_logger.warning(
                "BillingError in %s event handler: %s. stripe_object_id=%s, customer_id=%s metadata=%s",
                event.type,
                e.error_description,
                stripe_object.id,
                stripe_object.customer,
                stripe_object.metadata,
            )
            event.status = Event.EVENT_HANDLER_FAILED
            event.handler_error = {
                "message": e.msg,
                "description": e.error_description,
            }
            event.save(update_fields=["status", "handler_error"])
        except Exception:
            billing_logger.exception(
                "Uncaught exception in %s event handler:",
                event.type,
                stack_info=True,
            )
            event.status = Event.EVENT_HANDLER_FAILED
            event.handler_error = {
                "description": f"uncaught exception in {event.type} event handler",
                "message": BillingError.CONTACT_SUPPORT.format(email=settings.ZULIP_ADMINISTRATOR),
            }
            event.save(update_fields=["status", "handler_error"])
        else:
            event.status = Event.EVENT_HANDLER_SUCCEEDED
            event.save()

    return wrapper


def get_billing_session_for_stripe_webhook(
    customer: Customer, user_id: Optional[str]
) -> Union[RealmBillingSession, RemoteRealmBillingSession, RemoteServerBillingSession]:
    if customer.remote_realm is not None:  # nocoverage
        return RemoteRealmBillingSession(customer.remote_realm)
    elif customer.remote_server is not None:  # nocoverage
        return RemoteServerBillingSession(customer.remote_server)
    else:
        assert user_id is not None
        assert customer.realm is not None
        user = get_active_user_profile_by_id_in_realm(int(user_id), customer.realm)
        return RealmBillingSession(user)


@error_handler
def handle_checkout_session_completed_event(
    stripe_session: stripe.checkout.Session, session: Session
) -> None:
    session.status = Session.COMPLETED
    session.save()

    assert isinstance(stripe_session.setup_intent, str)
    assert stripe_session.metadata is not None
    stripe_setup_intent = stripe.SetupIntent.retrieve(stripe_session.setup_intent)
    billing_session = get_billing_session_for_stripe_webhook(
        session.customer, stripe_session.metadata.get("user_id")
    )
    payment_method = stripe_setup_intent.payment_method
    assert isinstance(payment_method, (str, type(None)))

    if session.type in [
        Session.CARD_UPDATE_FROM_BILLING_PAGE,
        Session.CARD_UPDATE_FROM_UPGRADE_PAGE,
    ]:
        billing_session.update_or_create_stripe_customer(payment_method)


@error_handler
def handle_payment_intent_succeeded_event(
    stripe_payment_intent: stripe.PaymentIntent, payment_intent: PaymentIntent
) -> None:
    payment_intent.status = PaymentIntent.SUCCEEDED
    payment_intent.save()
    metadata: Dict[str, Any] = stripe_payment_intent.metadata

    description = ""
    charge: stripe.Charge
    for charge in stripe_payment_intent.charges:  # type: ignore[attr-defined] # https://stripe.com/docs/upgrades#2022-11-15
        assert charge.payment_method_details is not None
        assert charge.payment_method_details.card is not None
        description = f"Payment (Card ending in {charge.payment_method_details.card.last4})"
        break

    stripe.InvoiceItem.create(
        amount=stripe_payment_intent.amount * -1,
        currency="usd",
        customer=stripe_payment_intent.customer,
        description=description,
        discountable=False,
    )
    billing_session = get_billing_session_for_stripe_webhook(
        payment_intent.customer, metadata.get("user_id")
    )
    plan_tier = int(metadata["plan_tier"])
    try:
        billing_session.ensure_current_plan_is_upgradable(payment_intent.customer, plan_tier)
    except (UpgradeWithExistingPlanError, InvalidPlanUpgradeError) as e:
        stripe_invoice = stripe.Invoice.create(
            auto_advance=True,
            collection_method="charge_automatically",
            customer=stripe_payment_intent.customer,
            days_until_due=None,
            statement_descriptor=CustomerPlan.name_from_tier(plan_tier).replace("Zulip ", "")
            + " Credit",
        )
        stripe.Invoice.finalize_invoice(stripe_invoice)
        raise e

    billing_session.process_initial_upgrade(
        plan_tier,
        int(metadata["licenses"]),
        metadata["license_management"] == "automatic",
        int(metadata["billing_schedule"]),
        True,
        False,
        billing_session.get_remote_server_legacy_plan(payment_intent.customer),
    )
