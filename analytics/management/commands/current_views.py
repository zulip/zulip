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

        last = options.get('last', datetime.utcnow())
        first = options.get('first', last - timedelta(hour=1))

        # note that this includes deactivated ones, and we'll have to further filter for intervals
        realms = Realm.objects.values('id', 'date_created')

        # note that gauge measurements will never be truly accurate (without extra work)
        for interval in compute_intervals(first, last, 'gauge', 'day'):
            realm_ids = frozenset([realm['id'] for realm in realms if realm['date_created'] < interval.end])3
            process_realmcount(realm_ids, 'user_profile_count', get_user_profile_count_by_realm, interval)
            process(realm_ids, 'bot_count', get_bot_count_by_realm, interval)

        for interval in compute_intervals(first, last, 'hour', 'hour'):
            realm_ids = [realm['id'] for realm in realms if realm['date_created'] < interval.end]
            process(realm_ids, 'user_profile_count', get_user_profile_count_by_realm, interval)
            process(realm_ids, 'bot_count', get_bot_count_by_realm, interval)
