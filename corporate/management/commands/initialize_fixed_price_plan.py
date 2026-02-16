from typing import Any

from django.conf import settings
from django.core.management.base import CommandError, CommandParser
from typing_extensions import override

from zerver.lib.management import ZulipBaseCommand
from zerver.lib.timestamp import timestamp_to_datetime
from zerver.models.realms import Realm
from zilencer.models import RemoteRealm, RemoteZulipServer

if settings.BILLING_ENABLED:
    from corporate.lib.stripe import (
        BillingError,
        BillingSession,
        RealmBillingSession,
        RemoteRealmBillingSession,
        RemoteServerBillingSession,
        get_configured_fixed_price_plan_offer,
    )
    from corporate.models.plans import CustomerPlan


class Command(ZulipBaseCommand):
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
        parser.add_argument(
            "--remote-server",
            dest="remote_server_uuid",
            required=False,
            help="The UUID of the registered remote Zulip server to modify.",
        )
        parser.add_argument(
            "--remote-realm",
            dest="remote_realm_uuid",
            required=False,
            help="The UUID of the remote realm to modify.",
        )
        self.add_realm_args(parser)
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

        realm: Realm | None = None
        remote_realm: RemoteRealm | None = None
        remote_server: RemoteZulipServer | None = None
        billing_session: BillingSession | None = None
        if options["realm_id"]:
            realm = self.get_realm(options)
            if realm is None:
                raise CommandError("No realm found.")
            billing_session = RealmBillingSession(user=None, realm=realm)
        elif options["remote_realm_uuid"]:
            remote_realm_uuid = options["remote_realm_uuid"]
            try:
                remote_realm = RemoteRealm.objects.get(uuid=remote_realm_uuid)
                billing_session = RemoteRealmBillingSession(remote_realm=remote_realm)
            except RemoteRealm.DoesNotExist:
                raise CommandError(
                    "There is no remote realm with uuid '{}'. Aborting.".format(
                        options["remote_realm_uuid"]
                    )
                )
        elif options["remote_server_uuid"]:
            remote_server_uuid = options["remote_server_uuid"]
            try:
                remote_server = RemoteZulipServer.objects.get(uuid=remote_server_uuid)
                billing_session = RemoteServerBillingSession(remote_server=remote_server)
            except RemoteZulipServer.DoesNotExist:
                raise CommandError(
                    "There is no remote server with uuid '{}'. Aborting.".format(
                        options["remote_server_uuid"]
                    )
                )

        if realm is None and remote_realm is None and remote_server is None:
            raise CommandError(
                "No billing entity (Realm, RemoteRealm or RemoteZulipServer) specified."
            )

        assert billing_session is not None
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
