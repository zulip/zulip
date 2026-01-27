from typing import Any

from django.conf import settings
from django.core.management.base import CommandError, CommandParser
from typing_extensions import override

from zerver.lib.management import ZulipBaseCommand
from zerver.lib.timestamp import timestamp_to_datetime
from zerver.models.realms import Realm
from zilencer.models import RemoteRealm, RemoteZulipServer

if settings.BILLING_ENABLED:
    from corporate.lib.stripe import BillingError, initialize_fixed_price_plan
    from corporate.models.plans import CustomerPlan


class Command(ZulipBaseCommand):
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

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        if settings.BILLING_ENABLED:
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
            if options["realm_id"]:
                realm = self.get_realm(options)
                if not realm:
                    raise CommandError("No realm found.")
            elif options["remote_realm_uuid"]:
                remote_realm_uuid = options["remote_realm_uuid"]
                try:
                    remote_realm = RemoteRealm.objects.get(uuid=remote_realm_uuid)
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
                except RemoteZulipServer.DoesNotExist:
                    raise CommandError(
                        "There is no remote server with uuid '{}'. Aborting.".format(
                            options["remote_server_uuid"]
                        )
                    )

            if realm is None and remote_realm is None and remote_server is None:
                raise CommandError(
                    "No billing entity (realm, remote realm or remote server) specified."
                )

            try:
                initialize_fixed_price_plan(
                    plan_tier,
                    billing_cycle_anchor,
                    realm=realm,
                    remote_realm=remote_realm,
                    remote_server=remote_server,
                )
            except BillingError as e:
                raise CommandError(e.msg)
            except AssertionError as e:
                raise CommandError(e)
