from __future__ import absolute_import
from __future__ import print_function

import os
import sys
from scripts.lib.zulip_tools import ENDC, WARNING

from argparse import ArgumentParser
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.conf import settings

from analytics.models import RealmCount, UserCount
from analytics.lib.counts import COUNT_STATS, logger, process_count_stat
from zerver.models import UserProfile, Message

from typing import Any

class Command(BaseCommand):
    help = """Fills Analytics tables.

    Run as a cron job that runs every hour."""

    def add_arguments(self, parser):
        # type: (ArgumentParser) -> None
        parser.add_argument('--time', '-t',
                            type=str,
                            help='Update stat tables from current state to --time. Defaults to the current time.',
                            default=timezone.now().isoformat())
        parser.add_argument('--utc',
                            type=bool,
                            help="Interpret --time in UTC.",
                            default=False)
        parser.add_argument('--stat', '-s',
                            type=str,
                            help="CountStat to process. If omitted, all stats are processed.")
        parser.add_argument('--quiet', '-q',
                            type=str,
                            help="Suppress output to stdout.")

    def handle(self, *args, **options):
        # type: (*Any, **Any) -> None
        try:
            os.mkdir(settings.ANALYTICS_LOCK_DIR)
        except OSError:
            print(WARNING + "Analytics lock %s is unavailable; exiting... " + ENDC)
            return

        try:
            self.run_update_analytics_counts(options)
        finally:
            os.rmdir(settings.ANALYTICS_LOCK_DIR)

    def run_update_analytics_counts(self, options):
        # type: (Dict[str, Any]) -> None
        fill_to_time = parse_datetime(options['time'])
        if options['utc']:
            fill_to_time = fill_to_time.replace(tzinfo=timezone.utc)

        if fill_to_time.tzinfo is None:
            raise ValueError("--time must be timezone aware. Maybe you meant to use the --utc option?")

        logger.info("Starting updating analytics counts through %s" % (fill_to_time,))

        if options['stat'] is not None:
            process_count_stat(COUNT_STATS[options['stat']], fill_to_time)
        else:
            for stat in COUNT_STATS.values():
                process_count_stat(stat, fill_to_time)

        logger.info("Finished updating analytics counts through %s" % (fill_to_time,))
