from django.core.management.base import BaseCommand
from django.db import connection
from django.db.models import Sum, Count
from django.utils import timezone

from datetime import datetime
from optparse import make_option

from zerver.models import Realm, UserProfile, Stream
from zerver.lib.timestamp import string_to_datetime
from analytics.models import RealmCount
from analytics.views import get_realm_day_counts, dictfetchall
from django.template import loader

from collections import Counter, defaultdict

class Command(BaseCommand):
    help = """Fills RealmCount table.

    Run as a cron job that runs every hour."""

    option_list = BaseCommand.option_list + (
        make_option('-f', '--first',
                    dest='first',
                    type='str',
                    help="The analytics suite will run for every interval which has an end time in [first, last]. Both first and last should be str(datetime)'s, interpreted in UTC. Both arguments are optional; first defaults to last-1hr, and end defaults to datetime.utcnow()."),
        make_option('-l', '--last',
                    dest='last',
                    type='str',
                    help="See help for 'first'."),
    )

    def handle(self, *args, **options):
        # type: (*Any, **Any) -> None
        last = options.get(string_to_datetime('last'), timezone.now())
        first = options.get(string_to_datetime('first'), last - timedelta(seconds=3600))

        stats = [
            AnalyticsStat('active_humans', UserProfile, {'is_bot':False, 'is_active':True},
                          RealmCount, 'gauge', 'day'),
            AnalyticsStat('active_bots', UserProfile, {'is_bot':True, 'is_active':True},
                          RealmCount, 'gauge', 'day'),
            AnalyticsStat('messages_sent', Message, {}, UserCount, 'hour', 'hour')]

        # stats that hit the prod database
        for smallest_interval in ['hour', 'day', 'gauge']:
            for frequency in ['hour', 'day']:
                for time_interval in timeinterval_range(first, last, smallest_interval, frequency):
                    for stat in stats:
                        if stat.smallest_interval == smallest_interval and stat.frequency == frequency:
                            process_pull_count(stat, time_interval)

        # aggregate hour to day
        for frequency in ['hour', 'day']:
            for time_interval in timeinterval_range(first, last, 'day', frequency):
                for stat in stats:
                    if stat.smallest_interval == 'hour' and stat.frequency == frequency:
                        process_day_count(stat, time_interval)

        # aggregate StreamCount and UserCount to RealmCount
        for interval in ['hour', 'day', 'gauge']:
            for frequency in ['hour', 'day']:
                for time_interval in timeinterval_range(first, last, smallest_interval, frequency):
                    for stat in stats:
                        if stat.smallest_interval <= interval and stat.frequency == frequency and \
                           stat.analytics_table in (UserCount, StreamCount):
                            process_summary_count(stat, time_interval, stat.analytics_table, RealmCount)
                        process_summary_count(stat, time_interval, RealmCount, DeploymentCount)
