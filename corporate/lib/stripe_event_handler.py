import logging
from collections.abc import Callable
from typing import Any

import stripe
from django.conf import settings

from corporate.lib.stripe import (
    BILLING_SUPPORT_EMAIL,
    BillingError,
    RealmBillingSession,
    RemoteRealmBillingSession,
    RemoteServerBillingSession,
    get_configured_fixed_price_plan_offer,
)
from corporate.models.customers import Customer
from corporate.models.plans import CustomerPlan, get_current_plan_by_customer
from corporate.models.stripe_state import Event, Invoice, Session
from zerver.lib.send_email import FromAddress, send_email
from zerver.models.users import get_active_user_profile_by_id_in_realm

billing_logger = logging.getLogger("corporate.stripe")


def stripe_event_handler_decorator(
    func: Callable[[Any, Any], None],
) -> Callable[[stripe.checkout.Session | stripe.Invoice, Event], None]:
    def wrapper(
        stripe_object: stripe.checkout.Session | stripe.Invoice,
        event: Event,
    ) -> None:
        event.status = Event.EVENT_HANDLER_STARTED
        event.save(update_fields=["status"])

        try:
            func(stripe_object, event.content_object)
        except BillingError as e:
            message = (
                "BillingError in %s event handler: %s. stripe_object_id=%s, customer_id=%s metadata=%s",
                event.type,
                e.error_description,
                stripe_object.id,
                stripe_object.customer,
                stripe_object.metadata,
            )
            billing_logger.warning(message)
            event.status = Event.EVENT_HANDLER_FAILED
            event.handler_error = {
                "message": e.msg,
                "description": e.error_description,
            }
            event.save(update_fields=["status", "handler_error"])
            if isinstance(stripe_object, stripe.Invoice):
                # For Invoice processing errors, send email to billing support.
                send_email(
                    "zerver/emails/error_processing_invoice",
                    to_emails=[BILLING_SUPPORT_EMAIL],
                    from_address=FromAddress.tokenized_no_reply_address(),
                    context={
                        "message": message,
                    },
                )
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
    customer: Customer, user_id: str | None
) -> RealmBillingSession | RemoteRealmBillingSession | RemoteServerBillingSession:
    if customer.remote_realm is not None:
        return RemoteRealmBillingSession(customer.remote_realm)
    elif customer.remote_server is not None:
        return RemoteServerBillingSession(customer.remote_server)
    else:
        assert customer.realm is not None
        if user_id:
            user = get_active_user_profile_by_id_in_realm(int(user_id), customer.realm)
            return RealmBillingSession(user)
        else:
            return RealmBillingSession(user=None, realm=customer.realm)  # nocoverage


@stripe_event_handler_decorator
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
    assert isinstance(payment_method, str | None)

    if session.type in [
        Session.CARD_UPDATE_FROM_BILLING_PAGE,
        Session.CARD_UPDATE_FROM_UPGRADE_PAGE,
    ]:
        billing_session.update_or_create_stripe_customer(payment_method)


@stripe_event_handler_decorator
def handle_invoice_paid_event(stripe_invoice: stripe.Invoice, invoice: Invoice) -> None:
    invoice.status = Invoice.PAID
    invoice.save(update_fields=["status"])

    customer = invoice.customer

    configured_fixed_price_plan = None
    if customer.required_plan_tier:
        configured_fixed_price_plan = get_configured_fixed_price_plan_offer(
            customer, customer.required_plan_tier
        )

    if (
        stripe_invoice.collection_method == "send_invoice"
        and configured_fixed_price_plan
        and configured_fixed_price_plan.sent_invoice_id == invoice.stripe_invoice_id
    ):
        billing_session = get_billing_session_for_stripe_webhook(customer, user_id=None)
        complimentary_access_plan = billing_session.get_complimentary_access_plan(customer)
        assert customer.required_plan_tier is not None
        billing_session.process_initial_upgrade(
            plan_tier=customer.required_plan_tier,
            # TODO: Currently licenses don't play any role for fixed price plan.
            # We plan to introduce max_licenses allowed soon.
            licenses=0,
            automanage_licenses=True,
            billing_schedule=CustomerPlan.BILLING_SCHEDULE_ANNUAL,
            charge_automatically=False,
            free_trial=False,
            complimentary_access_plan=complimentary_access_plan,
            stripe_invoice_paid=True,
        )
    else:
        metadata = stripe_invoice.metadata
        # Only process upgrade required if metadata has the required keys.
        # This is a safeguard to avoid processing custom invoices.
        if (
            metadata is None
            or metadata.get("billing_schedule") is None
            or metadata.get("plan_tier") is None
        ):  # nocoverage
            return

        billing_session = get_billing_session_for_stripe_webhook(customer, metadata.get("user_id"))
        complimentary_access_plan = billing_session.get_complimentary_access_plan(customer)
        billing_schedule = int(metadata["billing_schedule"])
        plan_tier = int(metadata["plan_tier"])
        charge_automatically = stripe_invoice.collection_method != "send_invoice"
        if configured_fixed_price_plan and customer.required_plan_tier == plan_tier:
            assert customer.required_plan_tier is not None
            billing_session.process_initial_upgrade(
                plan_tier=customer.required_plan_tier,
                # TODO: Currently licenses don't play any role for fixed price plan.
                # We plan to introduce max_licenses allowed soon.
                licenses=0,
                automanage_licenses=True,
                billing_schedule=billing_schedule,
                charge_automatically=charge_automatically,
                free_trial=False,
                complimentary_access_plan=complimentary_access_plan,
                stripe_invoice_paid=True,
            )
            return
        elif metadata.get("on_free_trial") and invoice.is_created_for_free_trial_upgrade:
            free_trial_plan = invoice.plan
            assert free_trial_plan is not None
            if free_trial_plan.is_free_trial():
                # We don't need to do anything here. When the free trial ends we will
                # check if user has paid the invoice, if not we downgrade the user.
                return

            # If customer paid after end of free trial, we just upgrade via default method below.
            assert free_trial_plan.status == CustomerPlan.ENDED
            # Also check if customer is not on any other active plan.
            assert get_current_plan_by_customer(customer) is None

        billing_session.process_initial_upgrade(
            plan_tier,
            int(metadata["licenses"]),
            metadata["license_management"] == "automatic",
            billing_schedule=billing_schedule,
            charge_automatically=charge_automatically,
            free_trial=False,
            complimentary_access_plan=complimentary_access_plan,
            stripe_invoice_paid=True,
        )
