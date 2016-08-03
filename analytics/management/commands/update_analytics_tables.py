from django.core.management.base import BaseCommand
from django.db import connection
from django.db.models import Sum, Count

from datetime import datetime
from optparse import make_option

from zerver.models import Realm, UserProfile
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
        last = options.get(string_to_datetime('last'), datetime.utcnow())
        first = options.get(string_to_datetime('first'), last - timedelta(seconds=3600))

        # note that this includes deactivated users and realms
        users = UserProfile.objects.annotate(created='date_joined').values('id', 'created')
        realms = Realm.objects.annotate(created='date_created').values('id', 'created')

        def existing_ids(rows, time_interval):
            return frozenset(row['id'] for row in rows if row['created'] < time_interval.end)

        realm_gauge_day_stats = {'active_humans' : get_active_humans_count_by_realm,
                                 'active_bots'   : get_active_bots_count_by_realm}

        user_hour_stats = {'messages_sent' : get_messages_sent_count_by_user}

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
