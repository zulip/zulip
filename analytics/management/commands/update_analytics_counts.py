from argparse import ArgumentParser
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from analytics.lib.counts import process_count_stat, CountStat
from analytics.models import RealmCount, UserCount
from zerver.lib.timestamp import datetime_to_string, assert_timezone_aware
from zerver.models import UserProfile, Message

from typing import Any


class Command(BaseCommand):
    help = """Fills Analytics tables.

    Run as a cron job that runs every hour."""

    def add_arguments(self, parser):
        # type: (ArgumentParser) -> None
        parser.add_argument('--range-start', '-s',
                            type=str,
                            help="date to backfill from",
                            default=datetime_to_string(timezone.now() - timedelta(seconds=3600)))
        parser.add_argument('--range-end', '-e',
                            type=str,
                            help='date to backfill to',
                            default=datetime_to_string(timezone.now()))
        parser.add_argument('--utc',
                           type=bool,
                           help="make arguments utc time",
                           default=False)

    def handle(self, *args, **options):
        # type: (*Any, **Any) -> None
        # throw error if start time is greater than end time
        if parse_datetime(options['range_start']) > parse_datetime(options['range_end']):
            raise ValueError("start time should not be greater than end time")

        range_start = parse_datetime(options['range_start'])
        if options['utc'] is True:
            range_start = range_start.replace(tzinfo=timezone.utc)
        assert_timezone_aware(range_start)

        range_end = parse_datetime(options['range_end'])
        if options['utc'] is True:
            range_end = range_end.replace(tzinfo=timezone.utc)
        assert_timezone_aware(range_end)

        stats = [
            CountStat('active_humans', UserProfile, {'is_bot': False, 'is_active': True},
                      RealmCount, 'gauge', 'day'),
            CountStat('active_bots', UserProfile, {'is_bot': True, 'is_active': True},
                      RealmCount, 'gauge', 'day'),
            CountStat('messages_sent', Message, {}, UserCount, 'hour', 'hour')]

        # process analytics counts for stats
        for stat in stats:
            process_count_stat(stat, range_start, range_end)
