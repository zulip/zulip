from zerver.lib.management import ZulipBaseCommand
from zilencer.models import Plan
from zproject.settings import get_secret

from typing import Any

import stripe
stripe.api_key = get_secret('stripe_secret_key')

class Command(ZulipBaseCommand):
    help = """Script to add the appropriate products and plans to Stripe."""

    def handle(self, *args: Any, **options: Any) -> None:
        Plan.objects.all().delete()

        # Zulip Cloud offerings
        product = stripe.Product.create(
            name="Zulip Cloud Premium",
            type='service',
            statement_descriptor="Zulip Cloud Premium",
            unit_label="user")

        plan = stripe.Plan.create(
            currency='usd',
            interval='month',
            product=product.id,
            amount=800,
            billing_scheme='per_unit',
            nickname=Plan.CLOUD_MONTHLY,
            usage_type='licensed')
        Plan.objects.create(nickname=Plan.CLOUD_MONTHLY, stripe_plan_id=plan.id)

        plan = stripe.Plan.create(
            currency='usd',
            interval='year',
            product=product.id,
            amount=8000,
            billing_scheme='per_unit',
            nickname=Plan.CLOUD_ANNUAL,
            usage_type='licensed')
        Plan.objects.create(nickname=Plan.CLOUD_ANNUAL, stripe_plan_id=plan.id)
