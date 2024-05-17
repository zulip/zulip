import hashlib
import time
from argparse import ArgumentParser
from datetime import timezone
from typing import Any, Dict

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_datetime
from django.utils.timezone import now as timezone_now
from typing_extensions import override

from analytics.lib.counts import ALL_COUNT_STATS, logger, process_count_stat
from zerver.lib.management import abort_unless_locked
from zerver.lib.remote_server import send_server_data_to_push_bouncer
from zerver.lib.timestamp import floor_to_hour
from zerver.models import Realm


class Command(BaseCommand):
    help = """Fills Analytics tables.

    Run as a cron job that runs every hour."""

    @override
    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--time",
            "-t",
            help="Update stat tables from current state to "
            "--time. Defaults to the current time.",
            default=timezone_now().isoformat(),
        )
        parser.add_argument("--utc", action="store_true", help="Interpret --time in UTC.")
        parser.add_argument(
            "--stat", "-s", help="CountStat to process. If omitted, all stats are processed."
        )
        parser.add_argument(
            "--verbose", action="store_true", help="Print timing information to stdout."
        )

    @override
    @abort_unless_locked
    def handle(self, *args: Any, **options: Any) -> None:
        self.run_update_analytics_counts(options)

    def run_update_analytics_counts(self, options: Dict[str, Any]) -> None:
        # installation_epoch relies on there being at least one realm; we
        # shouldn't run the analytics code if that condition isn't satisfied
        if not Realm.objects.exists():
            logger.info("No realms, stopping update_analytics_counts")
            return

        fill_to_time = parse_datetime(options["time"])
        assert fill_to_time is not None
        if options["utc"]:
            fill_to_time = fill_to_time.replace(tzinfo=timezone.utc)
        if fill_to_time.tzinfo is None:
            raise ValueError(
                "--time must be time-zone-aware. Maybe you meant to use the --utc option?"
            )

        fill_to_time = floor_to_hour(fill_to_time.astimezone(timezone.utc))

        if options["stat"] is not None:
            stats = [ALL_COUNT_STATS[options["stat"]]]
        else:
            stats = list(ALL_COUNT_STATS.values())

        logger.info("Starting updating analytics counts through %s", fill_to_time)
        if options["verbose"]:
            start = time.time()
            last = start

        for stat in stats:
            process_count_stat(stat, fill_to_time)
            if options["verbose"]:
                print(f"Updated {stat.property} in {time.time() - last:.3f}s")
                last = time.time()

        if options["verbose"]:
            print(
                f"Finished updating analytics counts through {fill_to_time} in {time.time() - start:.3f}s"
            )
        logger.info("Finished updating analytics counts through %s", fill_to_time)

        if settings.PUSH_NOTIFICATION_BOUNCER_URL:
            # Skew 0-10 minutes based on a hash of settings.ZULIP_ORG_ID, so
            # that each server will report in at a somewhat consistent time.
            assert settings.ZULIP_ORG_ID
            delay = int.from_bytes(
                hashlib.sha256(settings.ZULIP_ORG_ID.encode()).digest(), byteorder="big"
            ) % (60 * 10)
            logger.info("Sleeping %d seconds before reporting...", delay)
            time.sleep(delay)

            send_server_data_to_push_bouncer(consider_usage_statistics=True)
