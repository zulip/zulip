from django.conf import settings
from django.db import connection, models
from django.db.models import F
from django.utils import timezone

from analytics.models import InstallationCount, RealmCount, \
    UserCount, StreamCount, BaseCount, FillState, Anomaly, installation_epoch
from zerver.models import Realm, UserProfile, Message, Stream, models
from zerver.lib.timestamp import floor_to_day, floor_to_hour, ceiling_to_day, \
    ceiling_to_hour

from typing import Any, Dict, Optional, Text, Tuple, Type, Union

from datetime import timedelta, datetime
import logging
import time

## Logging setup ##
log_format = '%(asctime)s %(levelname)-8s %(message)s'
logging.basicConfig(format=log_format)

formatter = logging.Formatter(log_format)
file_handler = logging.FileHandler(settings.ANALYTICS_LOG_PATH)
file_handler.setFormatter(formatter)

logger = logging.getLogger("zulip.management")
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)

# First post office in Boston
MIN_TIME = datetime(1639, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

class CountStat(object):
    HOUR = 'hour'
    DAY = 'day'
    FREQUENCIES = frozenset([HOUR, DAY])
    # Allowed intervals are HOUR, DAY, and, GAUGE
    GAUGE = 'gauge'

    def __init__(self, property, zerver_count_query, filter_args, group_by, frequency, is_gauge):
        # type: (str, ZerverCountQuery, Dict[str, bool], Optional[Tuple[models.Model, str]], str, bool) -> None
        self.property = property
        self.zerver_count_query = zerver_count_query
        # might have to do something different for bitfields
        self.filter_args = filter_args
        self.group_by = group_by
        if frequency not in self.FREQUENCIES:
            raise AssertionError("Unknown frequency: %s" % (frequency,))
        self.frequency = frequency
        self.interval = self.GAUGE if is_gauge else frequency
        self.is_logging = False

    def __unicode__(self):
        # type: () -> Text
        return u"<CountStat: %s>" % (self.property,)

class LoggingCountStat(CountStat):
    def __init__(self, property, analytics_table, frequency):
        # type: (str, Type[BaseCount], str) -> None
        CountStat.__init__(self, property, ZerverCountQuery(None, analytics_table, None), {}, None,
                           frequency, False)
        self.is_logging = True

class ZerverCountQuery(object):
    def __init__(self, zerver_table, analytics_table, query):
        # type: (Type[models.Model], Type[BaseCount], Text) -> None
        self.zerver_table = zerver_table
        self.analytics_table = analytics_table
        self.query = query

def do_update_fill_state(fill_state, end_time, state):
    # type: (FillState, datetime, int) -> None
    fill_state.end_time = end_time
    fill_state.state = state
    fill_state.save()

def process_count_stat(stat, fill_to_time):
    # type: (CountStat, datetime) -> None
    fill_state = FillState.objects.filter(property=stat.property).first()
    if fill_state is None:
        currently_filled = installation_epoch()
        fill_state = FillState.objects.create(property=stat.property,
                                              end_time=currently_filled,
                                              state=FillState.DONE)
        logger.info("INITIALIZED %s %s" % (stat.property, currently_filled))
    elif fill_state.state == FillState.STARTED:
        logger.info("UNDO START %s %s" % (stat.property, fill_state.end_time))
        do_delete_counts_at_hour(stat, fill_state.end_time)
        currently_filled = fill_state.end_time - timedelta(hours = 1)
        do_update_fill_state(fill_state, currently_filled, FillState.DONE)
        logger.info("UNDO DONE %s" % (stat.property,))
    elif fill_state.state == FillState.DONE:
        currently_filled = fill_state.end_time
    else:
        raise AssertionError("Unknown value for FillState.state: %s." % (fill_state.state,))

    currently_filled = currently_filled + timedelta(hours = 1)
    while currently_filled <= fill_to_time:
        logger.info("START %s %s %s" % (stat.property, stat.interval, currently_filled))
        start = time.time()
        do_update_fill_state(fill_state, currently_filled, FillState.STARTED)
        do_fill_count_stat_at_hour(stat, currently_filled)
        do_update_fill_state(fill_state, currently_filled, FillState.DONE)
        end = time.time()
        currently_filled = currently_filled + timedelta(hours = 1)
        logger.info("DONE %s %s (%dms)" % (stat.property, stat.interval, (end-start)*1000))

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

    if not stat.is_logging:
        do_pull_from_zerver(stat, start_time, end_time)
    do_aggregate_to_summary_table(stat, end_time)

def do_delete_counts_at_hour(stat, end_time):
    # type: (CountStat, datetime) -> None
    if stat.is_logging:
        InstallationCount.objects.filter(property=stat.property, end_time=end_time).delete()
        if stat.zerver_count_query.analytics_table in [UserCount, StreamCount]:
            RealmCount.objects.filter(property=stat.property, end_time=end_time).delete()
    else:
        UserCount.objects.filter(property=stat.property, end_time=end_time).delete()
        StreamCount.objects.filter(property=stat.property, end_time=end_time).delete()
        RealmCount.objects.filter(property=stat.property, end_time=end_time).delete()
        InstallationCount.objects.filter(property=stat.property, end_time=end_time).delete()

def do_drop_all_analytics_tables():
    # type: () -> None
    UserCount.objects.all().delete()
    StreamCount.objects.all().delete()
    RealmCount.objects.all().delete()
    InstallationCount.objects.all().delete()
    FillState.objects.all().delete()
    Anomaly.objects.all().delete()

def do_aggregate_to_summary_table(stat, end_time):
    # type: (CountStat, datetime) -> None
    cursor = connection.cursor()

    # Aggregate into RealmCount
    analytics_table = stat.zerver_count_query.analytics_table
    if analytics_table in (UserCount, StreamCount):
        realmcount_query = """
            INSERT INTO analytics_realmcount
                (realm_id, value, property, subgroup, end_time)
            SELECT
                zerver_realm.id, COALESCE(sum(%(analytics_table)s.value), 0), '%(property)s',
                %(analytics_table)s.subgroup, %%(end_time)s
            FROM zerver_realm
            JOIN %(analytics_table)s
            ON
                zerver_realm.id = %(analytics_table)s.realm_id
            WHERE
                %(analytics_table)s.property = '%(property)s' AND
                %(analytics_table)s.end_time = %%(end_time)s
            GROUP BY zerver_realm.id, %(analytics_table)s.subgroup
        """ % {'analytics_table': analytics_table._meta.db_table,
               'property': stat.property}
        start = time.time()
        cursor.execute(realmcount_query, {'end_time': end_time})
        end = time.time()
        logger.info("%s RealmCount aggregation (%dms/%sr)" % (stat.property, (end-start)*1000, cursor.rowcount))

    # Aggregate into InstallationCount
    installationcount_query = """
        INSERT INTO analytics_installationcount
            (value, property, subgroup, end_time)
        SELECT
            sum(value), '%(property)s', analytics_realmcount.subgroup, %%(end_time)s
        FROM analytics_realmcount
        WHERE
            property = '%(property)s' AND
            end_time = %%(end_time)s
        GROUP BY analytics_realmcount.subgroup
    """ % {'property': stat.property}
    start = time.time()
    cursor.execute(installationcount_query, {'end_time': end_time})
    end = time.time()
    logger.info("%s InstallationCount aggregation (%dms/%sr)" % (stat.property, (end-start)*1000, cursor.rowcount))
    cursor.close()

# This is the only method that hits the prod databases directly.
def do_pull_from_zerver(stat, start_time, end_time):
    # type: (CountStat, datetime, datetime) -> None
    zerver_table = stat.zerver_count_query.zerver_table._meta.db_table # type: ignore
    join_args = ' '.join('AND %s.%s = %s' % (zerver_table, key, value)
                         for key, value in stat.filter_args.items())
    if stat.group_by is None:
        subgroup = 'NULL'
        group_by_clause  = ''
    else:
        subgroup = '%s.%s' % (stat.group_by[0]._meta.db_table, stat.group_by[1])
        group_by_clause = ', ' + subgroup

    # We do string replacement here because passing join_args as a param
    # may result in problems when running cursor.execute; we do
    # the string formatting prior so that cursor.execute runs it as sql
    query_ = stat.zerver_count_query.query % {'zerver_table': zerver_table,
                                              'property': stat.property,
                                              'join_args': join_args,
                                              'subgroup': subgroup,
                                              'group_by_clause': group_by_clause}
    cursor = connection.cursor()
    start = time.time()
    cursor.execute(query_, {'time_start': start_time, 'time_end': end_time})
    end = time.time()
    logger.info("%s do_pull_from_zerver (%dms/%sr)" % (stat.property, (end-start)*1000, cursor.rowcount))
    cursor.close()

# called from zerver/lib/actions.py; should not throw any errors
def do_increment_logging_stat(zerver_object, stat, subgroup, event_time, increment=1):
    # type: (Union[Realm, UserProfile, Stream], CountStat, Optional[Union[str, int, bool]], datetime, int) -> None
    table = stat.zerver_count_query.analytics_table
    if table == RealmCount:
        id_args = {'realm': zerver_object}
    elif table == UserCount:
        id_args = {'realm': zerver_object.realm, 'user': zerver_object}
    else: # StreamCount
        id_args = {'realm': zerver_object.realm, 'stream': zerver_object}

    if stat.frequency == CountStat.DAY:
        end_time = ceiling_to_day(event_time)
    else: # CountStat.HOUR:
        end_time = ceiling_to_hour(event_time)

    row, created = table.objects.get_or_create(
        property=stat.property, subgroup=subgroup, end_time=end_time,
        defaults={'value': increment}, **id_args)
    if not created:
        row.value = F('value') + increment
        row.save(update_fields=['value'])

count_user_by_realm_query = """
    INSERT INTO analytics_realmcount
        (realm_id, value, property, subgroup, end_time)
    SELECT
        zerver_realm.id, count(%(zerver_table)s),'%(property)s', %(subgroup)s, %%(time_end)s
    FROM zerver_realm
    JOIN zerver_userprofile
    ON
        zerver_realm.id = zerver_userprofile.realm_id
    WHERE
        zerver_realm.date_created < %%(time_end)s AND
        zerver_userprofile.date_joined >= %%(time_start)s AND
        zerver_userprofile.date_joined < %%(time_end)s
        %(join_args)s
    GROUP BY zerver_realm.id %(group_by_clause)s
"""
zerver_count_user_by_realm = ZerverCountQuery(UserProfile, RealmCount, count_user_by_realm_query)

# currently .sender_id is only Message specific thing
count_message_by_user_query = """
    INSERT INTO analytics_usercount
        (user_id, realm_id, value, property, subgroup, end_time)
    SELECT
        zerver_userprofile.id, zerver_userprofile.realm_id, count(*), '%(property)s', %(subgroup)s, %%(time_end)s
    FROM zerver_userprofile
    JOIN zerver_message
    ON
        zerver_userprofile.id = zerver_message.sender_id
    WHERE
        zerver_userprofile.date_joined < %%(time_end)s AND
        zerver_message.pub_date >= %%(time_start)s AND
        zerver_message.pub_date < %%(time_end)s
        %(join_args)s
    GROUP BY zerver_userprofile.id %(group_by_clause)s
"""
zerver_count_message_by_user = ZerverCountQuery(Message, UserCount, count_message_by_user_query)

# Currently unused and untested
count_stream_by_realm_query = """
    INSERT INTO analytics_realmcount
        (realm_id, value, property, subgroup, end_time)
    SELECT
        zerver_realm.id, count(*), '%(property)s', %(subgroup)s, %%(time_end)s
    FROM zerver_realm
    JOIN zerver_stream
    ON
        zerver_realm.id = zerver_stream.realm_id AND
    WHERE
        zerver_realm.date_created < %%(time_end)s AND
        zerver_stream.date_created >= %%(time_start)s AND
        zerver_stream.date_created < %%(time_end)s
        %(join_args)s
    GROUP BY zerver_realm.id %(group_by_clause)s
"""
zerver_count_stream_by_realm = ZerverCountQuery(Stream, RealmCount, count_stream_by_realm_query)

# This query violates the count_X_by_Y_query conventions in several ways. One,
# the X table is not specified by the query name; MessageType is not a zerver
# table. Two, it ignores the subgroup column in the CountStat object; instead,
# it uses 'message_type' from the subquery to fill in the subgroup column.
count_message_type_by_user_query = """
    INSERT INTO analytics_usercount
            (realm_id, user_id, value, property, subgroup, end_time)
    SELECT realm_id, id, SUM(count) AS value, '%(property)s', message_type, %%(time_end)s
    FROM
    (
        SELECT zerver_userprofile.realm_id, zerver_userprofile.id, count(*),
        CASE WHEN
                  zerver_recipient.type != 2 THEN 'private_message'
             WHEN
                  zerver_stream.invite_only = TRUE THEN 'private_stream'
             ELSE 'public_stream'
        END
        message_type

        FROM zerver_userprofile
        JOIN zerver_message
        ON
            zerver_userprofile.id = zerver_message.sender_id AND
            zerver_message.pub_date >= %%(time_start)s AND
            zerver_message.pub_date < %%(time_end)s
            %(join_args)s
        JOIN zerver_recipient
        ON
            zerver_message.recipient_id = zerver_recipient.id
        LEFT JOIN zerver_stream
        ON
            zerver_recipient.type_id = zerver_stream.id
        GROUP BY zerver_userprofile.realm_id, zerver_userprofile.id, zerver_recipient.type, zerver_stream.invite_only
    ) AS subquery
    GROUP BY realm_id, id, message_type
"""
zerver_count_message_type_by_user = ZerverCountQuery(Message, UserCount, count_message_type_by_user_query)

# Note that this query also joins to the UserProfile table, since all
# current queries that use this also subgroup on UserProfile.is_bot. If in
# the future there is a query that counts messages by stream and doesn't need
# the UserProfile table, consider writing a new query for efficiency.
count_message_by_stream_query = """
    INSERT INTO analytics_streamcount
        (stream_id, realm_id, value, property, subgroup, end_time)
    SELECT
        zerver_stream.id, zerver_stream.realm_id, count(*), '%(property)s', %(subgroup)s, %%(time_end)s
    FROM zerver_stream
    JOIN zerver_recipient
    ON
        zerver_stream.id = zerver_recipient.type_id
    JOIN zerver_message
    ON
        zerver_recipient.id = zerver_message.recipient_id
    JOIN zerver_userprofile
    ON
        zerver_message.sender_id = zerver_userprofile.id
    WHERE
        zerver_stream.date_created < %%(time_end)s AND
        zerver_recipient.type = 2 AND
        zerver_message.pub_date >= %%(time_start)s AND
        zerver_message.pub_date < %%(time_end)s
        %(join_args)s
    GROUP BY zerver_stream.id %(group_by_clause)s
"""
zerver_count_message_by_stream = ZerverCountQuery(Message, StreamCount, count_message_by_stream_query)

count_stats_ = [
    CountStat('active_users:is_bot:day', zerver_count_user_by_realm, {'is_active': True},
              (UserProfile, 'is_bot'), CountStat.DAY, True),
    CountStat('messages_sent:is_bot:hour', zerver_count_message_by_user, {},
              (UserProfile, 'is_bot'), CountStat.HOUR, False),
    CountStat('messages_sent:message_type:day', zerver_count_message_type_by_user, {},
              None, CountStat.DAY, False),
    CountStat('messages_sent:client:day', zerver_count_message_by_user, {},
              (Message, 'sending_client_id'), CountStat.DAY, False),
    CountStat('messages_in_stream:is_bot:day', zerver_count_message_by_stream, {},
              (UserProfile, 'is_bot'), CountStat.DAY, False),
    LoggingCountStat('active_users_log:is_bot:day', RealmCount, CountStat.DAY),
]

COUNT_STATS = {stat.property: stat for stat in count_stats_}
