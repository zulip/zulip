from typing import Any

from django.conf import settings
from django.core.management.base import CommandError, CommandParser
from typing_extensions import override

from zerver.lib.timestamp import timestamp_to_datetime

if settings.BILLING_ENABLED:
    from corporate.lib.billing_management import BillingSessionCommand
    from corporate.lib.stripe import BillingError, get_configured_fixed_price_plan_offer
    from corporate.models.plans import CustomerPlan


class Command(BillingSessionCommand):
    help = """
    Initialize a paid fixed-price plan for a billing customer (Realm, RemoteRealm or RemoteZulipServer).
    Defaults to `--dry-run=True` so that the billing changes are run in preview mode first.
    """

    @override
    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--plan-tier",
            dest="plan_tier",
            type=int,
            required=True,
            help="The CustomerPlan tier for the fixed-price plan.",
        )
        parser.add_argument(
            "--billing-anchor",
            dest="billing_cycle_anchor",
            type=float,
            required=False,
            help="Adjusted billing cycle anchor timestamp. Must be in the past.",
        )
        self.add_billing_entity_args(parser)
        parser.add_argument(
            "--dry-run",
            dest="dry_run",
            action="store_true",
            default=True,
            required=False,
            help="Check for errors before initializing paid fixed-price plan. Default value is True.",
        )

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        if not settings.BILLING_ENABLED:
            raise CommandError("Billing system not enabled.")

        plan_tier = options["plan_tier"]
        if plan_tier not in CustomerPlan.PAID_PLAN_TIERS:
            raise CommandError("Invalid tier for paid plan.")

        billing_cycle_anchor = None
        if options["billing_cycle_anchor"]:
            anchor_timestamp = options["billing_cycle_anchor"]
            billing_cycle_anchor = timestamp_to_datetime(anchor_timestamp)

        billing_session = self.get_billing_session_from_args(options)

        if options["dry_run"]:
            try:
                billing_session.check_can_configure_prepaid_fixed_price_plan(plan_tier)
                customer = billing_session.get_customer()
                assert customer is not None
                fixed_price_plan_offer = get_configured_fixed_price_plan_offer(customer, plan_tier)
                assert fixed_price_plan_offer is not None
                anchor_date_string = (
                    billing_cycle_anchor.strftime("%B %d, %Y") if billing_cycle_anchor else "today"
                )
                print(
                    f"Will initialize {fixed_price_plan_offer} with anchor date of {anchor_date_string}."
                )
                return
            except BillingError as e:
                raise CommandError(e.msg)
            except AssertionError as e:
                raise CommandError(e)
        else:
            try:
                billing_session.initialize_prepaid_fixed_price_plan(plan_tier, billing_cycle_anchor)
                print("Done! Check support panel for customer to review active fixed-price plan.")
            except BillingError as e:
                raise CommandError(e.msg)
            except AssertionError as e:
                raise CommandError(e)
