from typing import Any

from django.conf import settings
from django.core.management.base import CommandError, CommandParser
from typing_extensions import override

if settings.BILLING_ENABLED:
    from corporate.lib.billing_management import BillingSessionCommand
    from corporate.lib.stripe import BillingError, stripe_get_customer
    from corporate.models.plans import get_current_plan_by_customer


class Command(BillingSessionCommand):
    help = """Link a Customer object to a Stripe customer ID."""

    @override
    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--stripe-id",
            dest="stripe_id",
            required=True,
            help="The ID of the customer in Stripe.",
        )
        self.add_billing_entity_args(parser)

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        if not settings.BILLING_ENABLED:
            raise CommandError("Billing system not enabled.")

        stripe_id = options["stripe_id"]
        try:
            stripe_get_customer(stripe_id)
        except BillingError:
            raise CommandError(f"Error checking for Stripe Customer with ID {stripe_id}. Aborting.")

        billing_session = self.get_billing_session_from_args(options)
        customer = billing_session.get_customer()

        if customer is None:
            print(f"No Customer object for {billing_session.billing_entity_display_name}.")
            no_customer_object_prompt = input(
                f"Do you want to create one and link it to Stripe customer with ID {stripe_id}? [Y/n]"
            )
            print()
            if not (
                no_customer_object_prompt.lower() == "y"
                or no_customer_object_prompt.lower() == ""
                or no_customer_object_prompt.lower() == "yes"
            ):
                return

            print("Creating Customer object...")
            customer = billing_session.update_or_create_customer()
            print(f"Linking {customer} to Stripe customer with ID {stripe_id}...")
            billing_session.link_stripe_customer_id(stripe_id)
            print("Done!")
            return

        plan = get_current_plan_by_customer(customer)
        if plan is not None and plan.is_a_paid_plan():
            raise CommandError(f"{customer} has an active paid plan! Aborting.")

        if customer.stripe_customer_id is not None:
            existing_id_prompt = input(
                f"Do you want to overwrite the current stripe_customer_id for {customer}? [Y/n]"
            )
            print()
            if not (
                existing_id_prompt.lower() == "y"
                or existing_id_prompt.lower() == ""
                or existing_id_prompt.lower() == "yes"
            ):
                return

        print(f"Linking {customer} to Stripe customer with ID {stripe_id}...")
        billing_session.link_stripe_customer_id(stripe_id)
        print("Done!")
