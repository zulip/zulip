from django.db import connection, models
from django.utils import timezone
from datetime import timedelta, datetime

from analytics.models import InstallationCount, RealmCount, \
    UserCount, StreamCount, BaseCount, FillState, get_fill_state, installation_epoch
from zerver.models import Realm, UserProfile, Message, Stream, models
from zerver.lib.timestamp import floor_to_day

from typing import Any, Optional, Type
from six import text_type

# First post office in Boston
MIN_TIME = datetime(1639, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

class CountStat(object):
    HOUR = 'hour'
    DAY = 'day'
    FREQUENCIES = frozenset([HOUR, DAY])
    # Allowed intervals are HOUR, DAY, and, GAUGE
    GAUGE = 'gauge'

    def __init__(self, property, zerver_count_query, filter_args, frequency, is_gauge):
        # type: (text_type, ZerverCountQuery, Dict[str, bool], str, bool) -> None
        self.property = property
        self.zerver_count_query = zerver_count_query
        # might have to do something different for bitfields
        self.filter_args = filter_args
        if frequency not in self.FREQUENCIES:
            raise ValueError("Unknown frequency: %s" % (frequency,))
        self.frequency = frequency
        self.interval = self.GAUGE if is_gauge else frequency

class ZerverCountQuery(object):
    def __init__(self, zerver_table, analytics_table, query):
        # type: (Type[models.Model], Type[BaseCount], text_type) -> None
        self.zerver_table = zerver_table
        self.analytics_table = analytics_table
        self.query = query

def process_count_stat(stat, fill_to_time):
    # type: (CountStat, datetime) -> None
    fill_state = get_fill_state(stat.property)
    if fill_state is None:
        currently_filled = installation_epoch()
        FillState.objects.create(property = stat.property,
                                 end_time = currently_filled,
                                 state = FillState.DONE)
    elif fill_state['state'] == FillState.STARTED:
        do_delete_count_stat_at_hour(stat, fill_state['end_time'])
        currently_filled = fill_state['end_time'] - timedelta(hours = 1)
        FillState.objects.filter(property = stat.property). \
            update(end_time = currently_filled, state = FillState.DONE)
    elif fill_state['state'] == FillState.DONE:
        currently_filled = fill_state['end_time']
    else:
        raise ValueError("Unknown value for FillState.state: %s." % fill_state['state'])

    currently_filled = currently_filled + timedelta(hours = 1)
    while currently_filled <= fill_to_time:
        FillState.objects.filter(property = stat.property) \
                     .update(end_time = currently_filled, state = FillState.STARTED)
        do_fill_count_stat_at_hour(stat, currently_filled)
        FillState.objects.filter(property = stat.property).update(state = FillState.DONE)
        currently_filled = currently_filled + timedelta(hours = 1)

# We assume end_time is on an hour boundary, and is timezone aware.
# It is the caller's responsibility to enforce this!
def do_fill_count_stat_at_hour(stat, end_time):
    # type: (CountStat, datetime) -> None
    if stat.frequency == CountStat.DAY and (end_time != floor_to_day(end_time)):
        return

    if stat.interval == CountStat.HOUR:
        start_time = end_time - timedelta(hours = 1)
    elif stat.interval == CountStat.DAY:
        start_time = end_time - timedelta(days = 1)
    else: # stat.interval == CountStat.GAUGE
        start_time = MIN_TIME

    do_pull_from_zerver(stat, start_time, end_time, stat.interval)
    do_aggregate_to_summary_table(stat, end_time, stat.interval)

def do_delete_count_stat_at_hour(stat, end_time):
    # type: (CountStat, datetime) -> None
    UserCount.objects.filter(property = stat.property, end_time = end_time).delete()
    StreamCount.objects.filter(property = stat.property, end_time = end_time).delete()
    RealmCount.objects.filter(property = stat.property, end_time = end_time).delete()
    InstallationCount.objects.filter(property = stat.property, end_time = end_time).delete()

def do_aggregate_to_summary_table(stat, end_time, interval):
    # type: (CountStat, datetime, str) -> None
    cursor = connection.cursor()

    # Aggregate into RealmCount
    analytics_table = stat.zerver_count_query.analytics_table
    if analytics_table in (UserCount, StreamCount):
        realmcount_query = """
            INSERT INTO analytics_realmcount
                (realm_id, value, property, end_time, interval)
            SELECT
                zerver_realm.id, COALESCE(sum(%(analytics_table)s.value), 0), '%(property)s', %%(end_time)s, '%(interval)s'
            FROM zerver_realm
            LEFT JOIN %(analytics_table)s
            ON
            (
                %(analytics_table)s.realm_id = zerver_realm.id AND
                %(analytics_table)s.property = '%(property)s' AND
                %(analytics_table)s.end_time = %%(end_time)s AND
                %(analytics_table)s.interval = '%(interval)s'
            )
            GROUP BY zerver_realm.id
        """ % {'analytics_table' : analytics_table._meta.db_table,
               'property' : stat.property,
               'interval' : interval}

        cursor.execute(realmcount_query, {'end_time': end_time})

    # Aggregate into InstallationCount
    installationcount_query = """
        INSERT INTO analytics_installationcount
            (value, property, end_time, interval)
        SELECT
            COALESCE(sum(value), 0), '%(property)s', %%(end_time)s, '%(interval)s'
        FROM analytics_realmcount
        WHERE
        (
            property = '%(property)s' AND
            end_time = %%(end_time)s AND
            interval = '%(interval)s'
        )
    """ % {'property': stat.property,
           'interval': interval}

    cursor.execute(installationcount_query, {'end_time': end_time})
    cursor.close()

## methods that hit the prod databases directly
# No left joins in Django ORM yet, so have to use raw SQL :(
# written in slightly more than needed generality, to reduce copy-paste errors
# as more of these are made / make it easy to extend to a pull_X_by_realm

def do_pull_from_zerver(stat, start_time, end_time, interval):
    # type: (CountStat, datetime, datetime, str) -> None
    zerver_table = stat.zerver_count_query.zerver_table._meta.db_table # type: ignore
    join_args = ' '.join('AND %s.%s = %s' % (zerver_table, key, value) \
                         for key, value in stat.filter_args.items())
    # We do string replacement here because passing join_args as a param
    # may result in problems when running cursor.execute; we do
    # the string formatting prior so that cursor.execute runs it as sql
    query_ = stat.zerver_count_query.query % {'zerver_table' : zerver_table,
                                              'property' : stat.property,
                                              'interval' : interval,
                                              'join_args' : join_args}
    cursor = connection.cursor()
    cursor.execute(query_, {'time_start': start_time, 'time_end': end_time})
    cursor.close()

count_user_by_realm_query = """
    INSERT INTO analytics_realmcount
        (realm_id, value, property, end_time, interval)
    SELECT
        zerver_realm.id, count(%(zerver_table)s),'%(property)s', %%(time_end)s, '%(interval)s'
    FROM zerver_realm
    LEFT JOIN zerver_userprofile
    ON
    (
        zerver_userprofile.realm_id = zerver_realm.id AND
        zerver_userprofile.date_joined >= %%(time_start)s AND
        zerver_userprofile.date_joined < %%(time_end)s
        %(join_args)s
    )
    WHERE
        zerver_realm.date_created < %%(time_end)s
    GROUP BY zerver_realm.id
"""
zerver_count_user_by_realm = ZerverCountQuery(UserProfile, RealmCount, count_user_by_realm_query)

# currently .sender_id is only Message specific thing
count_message_by_user_query = """
    INSERT INTO analytics_usercount
        (user_id, realm_id, value, property, end_time, interval)
    SELECT
        zerver_userprofile.id, zerver_userprofile.realm_id, count(*), '%(property)s', %%(time_end)s, '%(interval)s'
    FROM zerver_userprofile
    JOIN zerver_message
    ON
    (
        zerver_message.sender_id = zerver_userprofile.id AND
        zerver_message.pub_date >= %%(time_start)s AND
        zerver_message.pub_date < %%(time_end)s
        %(join_args)s
    )
    WHERE
            zerver_userprofile.date_joined < %%(time_end)s
    GROUP BY zerver_userprofile.id
"""
zerver_count_message_by_user = ZerverCountQuery(Message, UserCount, count_message_by_user_query)

count_message_by_stream_query = """
    INSERT INTO analytics_streamcount
        (stream_id, realm_id, value, property, end_time, interval)
    SELECT
        zerver_stream.id, zerver_stream.realm_id, count(*), '%(property)s', %%(time_end)s, '%(interval)s'
    FROM zerver_stream
    INNER JOIN zerver_recipient
    ON
    (
        zerver_recipient.type = 2 AND
        zerver_stream.id = zerver_recipient.type_id
    )
    INNER JOIN zerver_message
    ON
    (
        zerver_message.recipient_id = zerver_recipient.id AND
        zerver_message.pub_date >= %%(time_start)s AND
        zerver_message.pub_date < %%(time_end)s AND
        zerver_stream.date_created < %%(time_end)s
        %(join_args)s
    )
    GROUP BY zerver_stream.id
"""
zerver_count_message_by_stream = ZerverCountQuery(Message, StreamCount, count_message_by_stream_query)

count_stream_by_realm_query = """
        INSERT INTO analytics_realmcount
            (realm_id, value, property, end_time, interval)
    SELECT
        zerver_stream.realm_id, count(*), '%(property)s', %%(time_end)s, '%(interval)s'
    FROM zerver_stream
    LEFT JOIN zerver_recipient
    ON
    (
        zerver_recipient.type = 2 AND
        zerver_stream.id = zerver_recipient.type_id
    )
    GROUP BY zerver_stream.realm_id
"""
zerver_count_stream_by_realm = ZerverCountQuery(Stream, RealmCount, count_stream_by_realm_query)

COUNT_STATS = {
    'active_humans': CountStat('active_humans', zerver_count_user_by_realm,
                               {'is_bot': False, 'is_active': True}, CountStat.DAY, True),
    'active_bots': CountStat('active_bots', zerver_count_user_by_realm,
                             {'is_bot': True, 'is_active': True}, CountStat.DAY, True),
    'messages_sent': CountStat('messages_sent', zerver_count_message_by_user, {}, CountStat.HOUR, False)}
