from datetime import datetime, timezone
from typing import Any

from django.core.management.base import CommandParser
from django.utils.timezone import now as timezone_now
from typing_extensions import override

from corporate.lib.stripe import RemoteServerBillingSession
from scripts.lib.zulip_tools import TIMESTAMP_FORMAT
from zerver.lib.management import ZulipBaseCommand
from zilencer.models import RemoteZulipServer


class Command(ZulipBaseCommand):
    help = "Assigns an existing RemoteZulipServer to the legacy plan"

    @override
    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "server_id",
            type=int,
            help="ID of the RemoteZulipServer to be assigned to the legacy plan",
        )
        parser.add_argument(
            "renewal_date",
            type=str,
            help="Billing cycle renewal date in the format YYYY-MM-DD-HH-MM-SS",
        )
        parser.add_argument(
            "end_date",
            type=str,
            help="Billing cycle end date in the format YYYY-MM-DD-HH-MM-SS",
        )

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        server_id = options["server_id"]
        renewal_date_str = options.get("renewal_date")
        if renewal_date_str is None:
            renewal_date = timezone_now()
        else:
            renewal_date = datetime.strptime(renewal_date_str, TIMESTAMP_FORMAT).replace(
                tzinfo=timezone.utc
            )

        end_date_str = options.get("end_date")
        if end_date_str is None:
            raise ValueError("end_date must be provided")

        end_date = datetime.strptime(end_date_str, TIMESTAMP_FORMAT).replace(tzinfo=timezone.utc)

        server = RemoteZulipServer.objects.get(id=server_id)
        self.migrate_customer_to_legacy_plan(server, renewal_date, end_date)

    def migrate_customer_to_legacy_plan(
        self,
        server: RemoteZulipServer,
        renewal_date: datetime,
        end_date: datetime,
    ) -> None:
        billing_schedule = RemoteServerBillingSession(server)
        billing_schedule.migrate_customer_to_legacy_plan(renewal_date, end_date)
