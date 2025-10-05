from argparse import ArgumentParser
from datetime import timedelta
from typing import Any

from django.utils.timezone import now as timezone_now
from typing_extensions import override

from zerver.lib.management import ZulipBaseCommand
from zerver.models import IdempotentRequest


class Command(ZulipBaseCommand):
    help = """Delete expired rows from IdempotentRequest.

    Runs as a cron job."""

    @override
    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--retention_duration",
            type=int,
            default=IdempotentRequest.RETENTION_DURATION_IN_HRS,
            help="Retention duration in hours; delete rows that are older than this period.",
        )

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        retention_duration = options["retention_duration"]
        expired_rows = IdempotentRequest.objects.filter(
            timestamp__lte=timezone_now() - timedelta(hours=retention_duration)
        )

        print(f"Removing {expired_rows.count()} expired idempotency rows")
        expired_rows.delete()
