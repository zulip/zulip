from __future__ import absolute_import
from __future__ import print_function

from argparse import ArgumentParser
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from analytics.models import RealmCount, UserCount
from analytics.lib.counts import COUNT_STATS, CountStat, process_count_stat
from zerver.lib.timestamp import datetime_to_string, is_timezone_aware
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
                            default=datetime_to_string(timezone.now()))
        parser.add_argument('--utc',
                            type=bool,
                            help="Interpret --time in UTC.",
                            default=False)
        parser.add_argument('--stat', '-s',
                            type=str,
                            help="CountStat to process. If omitted, all stats are processed.")

    def handle(self, *args, **options):
        # type: (*Any, **Any) -> None
        fill_to_time = parse_datetime(options['time'])
        if options['utc']:
            fill_to_time = fill_to_time.replace(tzinfo=timezone.utc)

        if not (is_timezone_aware(fill_to_time)):
            raise ValueError("--time must be timezone aware. Maybe you meant to use the --utc option?")

        if options['stat'] is not None:
            process_count_stat(COUNT_STATS[options['stat']], fill_to_time)
        else:
            for stat in COUNT_STATS.values():
                process_count_stat(stat, fill_to_time)
