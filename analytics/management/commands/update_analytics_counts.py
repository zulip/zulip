import os
import sys
from __future__ import print_function
from scripts.lib.zulip_tools import run, ENDC, WARNING

from argparse import ArgumentParser
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.conf import settings

from analytics.models import RealmCount, UserCount
from analytics.lib.counts import COUNT_STATS, process_count_stat
from zerver.lib.timestamp import datetime_to_string, is_timezone_aware
from zerver.models import UserProfile, Message

from typing import Any

class Command(BaseCommand):
    help = """Fills Analytics tables.

    Run as a cron job that runs every hour."""

    def add_arguments(self, parser):
        # type: (ArgumentParser) -> None
        parser.add_argument('--range-start', '-s',
                            type=str,
                            help="Time to backfill from.")
        parser.add_argument('--range-end', '-e',
                            type=str,
                            help='Time to backfill to.',
                            default=datetime_to_string(timezone.now()))
        parser.add_argument('--utc',
                            type=bool,
                            help="Interpret --range-start and --range-end as times in UTC.",
                            default=False)
        parser.add_argument('--stat', '-q',
                            type=str,
                            help="CountStat to process. If omitted, all stats are processed")

    def handle(self, *args, **options):
        # type: (*Any, **Any) -> None
        try:
            os.mkdir(settings.ANALYTICS_LOCK_DIR)
        except OSError:
            print(WARNING + "cronjob in progress; waiting for lock... " + ENDC)
            return
        try:
            self.run_update_analytics_counts(options)
        finally:
            run(["sudo", "rmdir", settings.ANALYTICS_LOCK_DIR])

    def run_update_analytics_counts(self, options):
        # type: (Dict[str, Any]) -> None
        range_start = parse_datetime(options['range_start'])
        if 'range_end' in options:
            range_end = parse_datetime(options['range_end'])
        else:
            range_end = range_start - timedelta(seconds = 3600)

        # throw error if start time is greater than end time
        if range_start > range_end:
            raise ValueError("--range-start cannot be greater than --range-end.")

        if options['utc'] is True:
            range_start = range_start.replace(tzinfo=timezone.utc)
            range_end = range_end.replace(tzinfo=timezone.utc)

        if not (is_timezone_aware(range_start) and is_timezone_aware(range_end)):
            raise ValueError("--range-start and --range-end must be timezone aware. Maybe you meant to use the --utc option?")

        if 'stat' in options:
            process_count_stat(COUNT_STATS[options['stat']], range_start, range_end)
        else:
            for stat in COUNT_STATS.values():
                process_count_stat(stat, range_start, range_end)
