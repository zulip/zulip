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

        realms = RealmCount.get_extended_ids_with_creation_from_zerver()
        users = UserCount.get_extended_ids_with_creation_from_zerver()
        streams = StreamCount.get_extended_ids_with_creation_from_zerver()

        # could be made more efficient if needed
        def row_entries_to_enter(aggregate_by, time_interval):
            base_list = {'user': users, 'realm': realms, 'stream': streams}
            in_interval = [row for row in base_list[aggregate_by] if row['created'] < time_interval.end]
            for row in in_interval:
                del row['created']
            return in_interval

        def existing_ids(rows, time_interval):
            return frozenset(row['id'] for row in rows if row['created'] < time_interval.end)

        stats = [
            AnalyticsStat('active_humans', UserProfile, {'is_bot':False, 'is_active':True},
                          'realm', 'gauge', 'day'),
            AnalyticsStat('active_bots', UserProfile, {'is_bot':True, 'is_active':True},
                          'realm', 'gauge', 'day'),
            AnalyticsStat('messages_sent', Message, {}, 'user', 'hour', 'hour')]

        # gauge hour # skipping now, since don't
        # hour hour
        # gauge day
        # hour day
        # day day

        user to realm
        stream to realm

        interval day/hour/gauge, freq hour/day, realm/user/stream

        each hour interval -> day interval


        def process_hour_stats(stats, first, last, interval, step_interval):
            for stat in stats:

        # stats that hit the prod database
        for smallest_interval in ['hour', 'day', 'gauge']:
            for frequency in ['hour', 'day']:
                for time_interval in timeinterval_range(first, last, smallest_interval, frequency):
                    for stat in stats:
                        if stat.smallest_interval == smallest_interval and stat.frequency == frequency:
                            rows = row_entries_to_enter(stat.aggregate_by, time_interval)
                            process_count(stat, rows, time_interval)

        # aggregate hour to day
        for frequency in ['hour', 'day']:
            for time_interval in timeinterval_range(first, last, 'day', frequency):
                for stat in stats:
                    if stat.smallest_interval == 'hour' and stat.frequency == frequency:
                        process_aggregate_count(stat)

        # aggregate StreamCount and UserCount to RealmCount
        for smallest_interval in ['hour', 'day', 'gauge']:
            for frequency in ['hour', 'day']:
                for time_interval in timeinterval_range(first, last, smallest_interval, frequency):
                    for stat in stats:
                        if stat.smallest_interval == smallest_interval and stat.frequency == frequency and \
                           stat.aggregate_by in ('user', 'stream'):
                            process_aggregate_count(stat)



        if stat.smallest_interval == 'gauge' and stat.frequency == 'hour':
                    process_aggregate_count(stat)


        for time_interval in timeinterval_range(first, last, 'gauge', 'day'):
            realm_ids = existing_ids(realms, time_interval)
            for property, value_function in realm_gauge_day_stats.items():
                process_count(RealmCount, realm_ids, 'realm_id', value_function, property, time_interval)

        for time_interval in timeinterval_range(first, last, 'hour', 'hour'):
            realm_ids = existing_ids(realms, time_interval)
            user_ids = existing_ids(users, time_interval)
            for property, value_function in user_hour_stats.items():
                process_count(UserCount, user_ids, 'userprofile_id', value_function, property, time_interval)
                process_aggregate_count(RealmCount, realm_ids, 'realm_id', aggregate_user_to_realm, property, time_interval)

        for time_interval in timeinterval_range(first, last, 'day', 'day'):
            realm_ids = existing_ids(realms, time_interval)
            user_ids = existing_ids(users, time_interval)
            for property, value_function in user_hour_stats.items():
                process_aggregate_count(UserCount, user_ids, 'userprofile_id', aggregate_user_hour_to_day, property, time_interval)
                process_aggregate_count(RealmCount, realm_ids, 'realm_id', aggregate_user_to_realm, property, time_interval)
