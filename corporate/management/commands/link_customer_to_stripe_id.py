from typing import Any

from django.conf import settings
from django.core.management.base import CommandError, CommandParser
from typing_extensions import override

from zerver.lib.management import ZulipBaseCommand

if settings.BILLING_ENABLED:
    from corporate.models.customers import Customer
    from corporate.models.plans import get_current_plan_by_customer


class Command(ZulipBaseCommand):
    help = """Link a Customer object to a Stripe customer ID."""

    @override
    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--stripe-id",
            dest="stripe_id",
            required=True,
            help="The ID of the customer in Stripe.",
        )
        parser.add_argument(
            "--customer-id",
            dest="customer_id",
            required=True,
            help="The ID of the Customer object in the database.",
        )

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        if not settings.BILLING_ENABLED:
            raise CommandError("Billing system not enabled.")

        stripe_id = options["stripe_id"]
        customer_id = options["customer_id"]

        try:
            customer = Customer.objects.get(id=customer_id)
        except Customer.DoesNotExist:
            raise CommandError(f"Customer object with ID {customer_id} does not exist. Aborting.")

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
                # Exit without registering; no need to print anything
                # special, as the "n" reply to the query is clear
                # enough about what happened.
                return

        print(f"Linking {customer} to Stripe customer with ID {stripe_id}...")
        customer.stripe_customer_id = stripe_id
        customer.save(update_fields=["stripe_customer_id"])
        print("Done!")
