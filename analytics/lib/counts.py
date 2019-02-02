import time
from collections import OrderedDict, defaultdict
from datetime import datetime, timedelta
import logging
from typing import Callable, Dict, List, \
    Optional, Tuple, Type, Union

from django.conf import settings
from django.db import connection
from django.db.models import F

from analytics.models import BaseCount, \
    FillState, InstallationCount, RealmCount, StreamCount, \
    UserCount, installation_epoch, last_successful_fill
from zerver.lib.logging_util import log_to_file
from zerver.lib.timestamp import ceiling_to_day, \
    ceiling_to_hour, floor_to_hour, verify_UTC
from zerver.models import Message, Realm, \
    Stream, UserActivityInterval, UserProfile, models

## Logging setup ##

logger = logging.getLogger('zulip.management')
log_to_file(logger, settings.ANALYTICS_LOG_PATH)

# You can't subtract timedelta.max from a datetime, so use this instead
TIMEDELTA_MAX = timedelta(days=365*1000)

## Class definitions ##

class CountStat:
    HOUR = 'hour'
    DAY = 'day'
    FREQUENCIES = frozenset([HOUR, DAY])

    def __init__(self, property: str, data_collector: 'DataCollector', frequency: str,
                 interval: Optional[timedelta]=None) -> None:
        self.property = property
        self.data_collector = data_collector
        # might have to do something different for bitfields
        if frequency not in self.FREQUENCIES:
            raise AssertionError("Unknown frequency: %s" % (frequency,))
        self.frequency = frequency
        if interval is not None:
            self.interval = interval
        elif frequency == CountStat.HOUR:
            self.interval = timedelta(hours=1)
        else:  # frequency == CountStat.DAY
            self.interval = timedelta(days=1)

    def __str__(self) -> str:
        return "<CountStat: %s>" % (self.property,)

class LoggingCountStat(CountStat):
    def __init__(self, property: str, output_table: Type[BaseCount], frequency: str) -> None:
        CountStat.__init__(self, property, DataCollector(output_table, None), frequency)

class DependentCountStat(CountStat):
    def __init__(self, property: str, data_collector: 'DataCollector', frequency: str,
                 interval: Optional[timedelta]=None, dependencies: List[str]=[]) -> None:
        CountStat.__init__(self, property, data_collector, frequency, interval=interval)
        self.dependencies = dependencies

class DataCollector:
    def __init__(self, output_table: Type[BaseCount],
                 pull_function: Optional[Callable[[str, datetime, datetime], int]]) -> None:
        self.output_table = output_table
        self.pull_function = pull_function

## CountStat-level operations ##

def process_count_stat(stat: CountStat, fill_to_time: datetime) -> None:
    if stat.frequency == CountStat.HOUR:
        time_increment = timedelta(hours=1)
    elif stat.frequency == CountStat.DAY:
        time_increment = timedelta(days=1)
    else:
        raise AssertionError("Unknown frequency: %s" % (stat.frequency,))

    verify_UTC(fill_to_time)
    if floor_to_hour(fill_to_time) != fill_to_time:
        raise ValueError("fill_to_time must be on an hour boundary: %s" % (fill_to_time,))

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
        currently_filled = fill_state.end_time - time_increment
        do_update_fill_state(fill_state, currently_filled, FillState.DONE)
        logger.info("UNDO DONE %s" % (stat.property,))
    elif fill_state.state == FillState.DONE:
        currently_filled = fill_state.end_time
    else:
        raise AssertionError("Unknown value for FillState.state: %s." % (fill_state.state,))

    if isinstance(stat, DependentCountStat):
        for dependency in stat.dependencies:
            dependency_fill_time = last_successful_fill(dependency)
            if dependency_fill_time is None:
                logger.warning("DependentCountStat %s run before dependency %s." %
                               (stat.property, dependency))
                return
            fill_to_time = min(fill_to_time, dependency_fill_time)

    currently_filled = currently_filled + time_increment
    while currently_filled <= fill_to_time:
        logger.info("START %s %s" % (stat.property, currently_filled))
        start = time.time()
        do_update_fill_state(fill_state, currently_filled, FillState.STARTED)
        do_fill_count_stat_at_hour(stat, currently_filled)
        do_update_fill_state(fill_state, currently_filled, FillState.DONE)
        end = time.time()
        currently_filled = currently_filled + time_increment
        logger.info("DONE %s (%dms)" % (stat.property, (end-start)*1000))

def do_update_fill_state(fill_state: FillState, end_time: datetime, state: int) -> None:
    fill_state.end_time = end_time
    fill_state.state = state
    fill_state.save()

# We assume end_time is valid (e.g. is on a day or hour boundary as appropriate)
# and is timezone aware. It is the caller's responsibility to enforce this!
def do_fill_count_stat_at_hour(stat: CountStat, end_time: datetime) -> None:
    start_time = end_time - stat.interval
    if not isinstance(stat, LoggingCountStat):
        timer = time.time()
        assert(stat.data_collector.pull_function is not None)
        rows_added = stat.data_collector.pull_function(stat.property, start_time, end_time)
        logger.info("%s run pull_function (%dms/%sr)" %
                    (stat.property, (time.time()-timer)*1000, rows_added))
    do_aggregate_to_summary_table(stat, end_time)

def do_delete_counts_at_hour(stat: CountStat, end_time: datetime) -> None:
    if isinstance(stat, LoggingCountStat):
        InstallationCount.objects.filter(property=stat.property, end_time=end_time).delete()
        if stat.data_collector.output_table in [UserCount, StreamCount]:
            RealmCount.objects.filter(property=stat.property, end_time=end_time).delete()
    else:
        UserCount.objects.filter(property=stat.property, end_time=end_time).delete()
        StreamCount.objects.filter(property=stat.property, end_time=end_time).delete()
        RealmCount.objects.filter(property=stat.property, end_time=end_time).delete()
        InstallationCount.objects.filter(property=stat.property, end_time=end_time).delete()

def do_aggregate_to_summary_table(stat: CountStat, end_time: datetime) -> None:
    cursor = connection.cursor()

    # Aggregate into RealmCount
    output_table = stat.data_collector.output_table
    if output_table in (UserCount, StreamCount):
        realmcount_query = """
            INSERT INTO analytics_realmcount
                (realm_id, value, property, subgroup, end_time)
            SELECT
                zerver_realm.id, COALESCE(sum(%(output_table)s.value), 0), '%(property)s',
                %(output_table)s.subgroup, %%(end_time)s
            FROM zerver_realm
            JOIN %(output_table)s
            ON
                zerver_realm.id = %(output_table)s.realm_id
            WHERE
                %(output_table)s.property = '%(property)s' AND
                %(output_table)s.end_time = %%(end_time)s
            GROUP BY zerver_realm.id, %(output_table)s.subgroup
        """ % {'output_table': output_table._meta.db_table,
               'property': stat.property}
        start = time.time()
        cursor.execute(realmcount_query, {'end_time': end_time})
        end = time.time()
        logger.info("%s RealmCount aggregation (%dms/%sr)" % (
            stat.property, (end - start) * 1000, cursor.rowcount))

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
    logger.info("%s InstallationCount aggregation (%dms/%sr)" % (
        stat.property, (end - start) * 1000, cursor.rowcount))
    cursor.close()

## Utility functions called from outside counts.py ##

# called from zerver/lib/actions.py; should not throw any errors
def do_increment_logging_stat(zerver_object: Union[Realm, UserProfile, Stream], stat: CountStat,
                              subgroup: Optional[Union[str, int, bool]], event_time: datetime,
                              increment: int=1) -> None:
    table = stat.data_collector.output_table
    if table == RealmCount:
        id_args = {'realm': zerver_object}
    elif table == UserCount:
        id_args = {'realm': zerver_object.realm, 'user': zerver_object}
    else:  # StreamCount
        id_args = {'realm': zerver_object.realm, 'stream': zerver_object}

    if stat.frequency == CountStat.DAY:
        end_time = ceiling_to_day(event_time)
    else:  # CountStat.HOUR:
        end_time = ceiling_to_hour(event_time)

    row, created = table.objects.get_or_create(
        property=stat.property, subgroup=subgroup, end_time=end_time,
        defaults={'value': increment}, **id_args)
    if not created:
        row.value = F('value') + increment
        row.save(update_fields=['value'])

def do_drop_all_analytics_tables() -> None:
    UserCount.objects.all().delete()
    StreamCount.objects.all().delete()
    RealmCount.objects.all().delete()
    InstallationCount.objects.all().delete()
    FillState.objects.all().delete()

def do_drop_single_stat(property: str) -> None:
    UserCount.objects.filter(property=property).delete()
    StreamCount.objects.filter(property=property).delete()
    RealmCount.objects.filter(property=property).delete()
    InstallationCount.objects.filter(property=property).delete()
    FillState.objects.filter(property=property).delete()

## DataCollector-level operations ##

def do_pull_by_sql_query(property: str, start_time: datetime, end_time: datetime, query: str,
                         group_by: Optional[Tuple[models.Model, str]]) -> int:
    if group_by is None:
        subgroup = 'NULL'
        group_by_clause  = ''
    else:
        subgroup = '%s.%s' % (group_by[0]._meta.db_table, group_by[1])
        group_by_clause = ', ' + subgroup

    # We do string replacement here because cursor.execute will reject a
    # group_by_clause given as a param.
    # We pass in the datetimes as params to cursor.execute so that we don't have to
    # think about how to convert python datetimes to SQL datetimes.
    query_ = query % {'property': property, 'subgroup': subgroup,
                      'group_by_clause': group_by_clause}
    cursor = connection.cursor()
    cursor.execute(query_, {'time_start': start_time, 'time_end': end_time})
    rowcount = cursor.rowcount
    cursor.close()
    return rowcount

def sql_data_collector(output_table: Type[BaseCount], query: str,
                       group_by: Optional[Tuple[models.Model, str]]) -> DataCollector:
    def pull_function(property: str, start_time: datetime, end_time: datetime) -> int:
        return do_pull_by_sql_query(property, start_time, end_time, query, group_by)
    return DataCollector(output_table, pull_function)

def do_pull_minutes_active(property: str, start_time: datetime, end_time: datetime) -> int:
    user_activity_intervals = UserActivityInterval.objects.filter(
        end__gt=start_time, start__lt=end_time
    ).select_related(
        'user_profile'
    ).values_list(
        'user_profile_id', 'user_profile__realm_id', 'start', 'end')

    seconds_active = defaultdict(float)  # type: Dict[Tuple[int, int], float]
    for user_id, realm_id, interval_start, interval_end in user_activity_intervals:
        start = max(start_time, interval_start)
        end = min(end_time, interval_end)
        seconds_active[(user_id, realm_id)] += (end - start).total_seconds()

    rows = [UserCount(user_id=ids[0], realm_id=ids[1], property=property,
                      end_time=end_time, value=int(seconds // 60))
            for ids, seconds in seconds_active.items() if seconds >= 60]
    UserCount.objects.bulk_create(rows)
    return len(rows)

count_message_by_user_query = """
    INSERT INTO analytics_usercount
        (user_id, realm_id, value, property, subgroup, end_time)
    SELECT
        zerver_userprofile.id, zerver_userprofile.realm_id, count(*),
        '%(property)s', %(subgroup)s, %%(time_end)s
    FROM zerver_userprofile
    JOIN zerver_message
    ON
        zerver_userprofile.id = zerver_message.sender_id
    WHERE
        zerver_userprofile.date_joined < %%(time_end)s AND
        zerver_message.pub_date >= %%(time_start)s AND
        zerver_message.pub_date < %%(time_end)s
    GROUP BY zerver_userprofile.id %(group_by_clause)s
"""

# Note: ignores the group_by / group_by_clause.
count_message_type_by_user_query = """
    INSERT INTO analytics_usercount
            (realm_id, user_id, value, property, subgroup, end_time)
    SELECT realm_id, id, SUM(count) AS value, '%(property)s', message_type, %%(time_end)s
    FROM
    (
        SELECT zerver_userprofile.realm_id, zerver_userprofile.id, count(*),
        CASE WHEN
                  zerver_recipient.type = 1 THEN 'private_message'
             WHEN
                  zerver_recipient.type = 3 THEN 'huddle_message'
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
        JOIN zerver_recipient
        ON
            zerver_message.recipient_id = zerver_recipient.id
        LEFT JOIN zerver_stream
        ON
            zerver_recipient.type_id = zerver_stream.id
        GROUP BY
            zerver_userprofile.realm_id, zerver_userprofile.id,
            zerver_recipient.type, zerver_stream.invite_only
    ) AS subquery
    GROUP BY realm_id, id, message_type
"""

# This query joins to the UserProfile table since all current queries that
# use this also subgroup on UserProfile.is_bot. If in the future there is a
# stat that counts messages by stream and doesn't need the UserProfile
# table, consider writing a new query for efficiency.
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
    GROUP BY zerver_stream.id %(group_by_clause)s
"""

# Hardcodes the query needed by active_users:is_bot:day, since that is
# currently the only stat that uses this.
count_user_by_realm_query = """
    INSERT INTO analytics_realmcount
        (realm_id, value, property, subgroup, end_time)
    SELECT
        zerver_realm.id, count(*),'%(property)s', %(subgroup)s, %%(time_end)s
    FROM zerver_realm
    JOIN zerver_userprofile
    ON
        zerver_realm.id = zerver_userprofile.realm_id
    WHERE
        zerver_realm.date_created < %%(time_end)s AND
        zerver_userprofile.date_joined >= %%(time_start)s AND
        zerver_userprofile.date_joined < %%(time_end)s AND
        zerver_userprofile.is_active = TRUE
    GROUP BY zerver_realm.id %(group_by_clause)s
"""

# Currently hardcodes the query needed for active_users_audit:is_bot:day.
# Assumes that a user cannot have two RealmAuditLog entries with the same event_time and
# event_type in ['user_created', 'user_deactivated', etc].
# In particular, it's important to ensure that migrations don't cause that to happen.
check_realmauditlog_by_user_query = """
    INSERT INTO analytics_usercount
        (user_id, realm_id, value, property, subgroup, end_time)
    SELECT
        ral1.modified_user_id, ral1.realm_id, 1, '%(property)s', %(subgroup)s, %%(time_end)s
    FROM zerver_realmauditlog ral1
    JOIN (
        SELECT modified_user_id, max(event_time) AS max_event_time
        FROM zerver_realmauditlog
        WHERE
            event_type in ('user_created', 'user_deactivated', 'user_activated', 'user_reactivated') AND
            event_time < %%(time_end)s
        GROUP BY modified_user_id
    ) ral2
    ON
        ral1.event_time = max_event_time AND
        ral1.modified_user_id = ral2.modified_user_id
    JOIN zerver_userprofile
    ON
        ral1.modified_user_id = zerver_userprofile.id
    WHERE
        ral1.event_type in ('user_created', 'user_activated', 'user_reactivated')
"""

check_useractivityinterval_by_user_query = """
    INSERT INTO analytics_usercount
        (user_id, realm_id, value, property, subgroup, end_time)
    SELECT
        zerver_userprofile.id, zerver_userprofile.realm_id, 1, '%(property)s', %(subgroup)s, %%(time_end)s
    FROM zerver_userprofile
    JOIN zerver_useractivityinterval
    ON
        zerver_userprofile.id = zerver_useractivityinterval.user_profile_id
    WHERE
        zerver_useractivityinterval.end >= %%(time_start)s AND
        zerver_useractivityinterval.start < %%(time_end)s
    GROUP BY zerver_userprofile.id %(group_by_clause)s
"""

count_realm_active_humans_query = """
    INSERT INTO analytics_realmcount
        (realm_id, value, property, subgroup, end_time)
    SELECT
        usercount1.realm_id, count(*), '%(property)s', NULL, %%(time_end)s
    FROM (
        SELECT realm_id, user_id
        FROM analytics_usercount
        WHERE
            property = 'active_users_audit:is_bot:day' AND
            subgroup = 'false' AND
            end_time = %%(time_end)s
    ) usercount1
    JOIN (
        SELECT realm_id, user_id
        FROM analytics_usercount
        WHERE
            property = '15day_actives::day' AND
            end_time = %%(time_end)s
    ) usercount2
    ON
        usercount1.user_id = usercount2.user_id
    GROUP BY usercount1.realm_id
"""

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
    GROUP BY zerver_realm.id %(group_by_clause)s
"""

## CountStat declarations ##

count_stats_ = [
    # Messages Sent stats
    # Stats that count the number of messages sent in various ways.
    # These are also the set of stats that read from the Message table.

    CountStat('messages_sent:is_bot:hour',
              sql_data_collector(UserCount, count_message_by_user_query, (UserProfile, 'is_bot')),
              CountStat.HOUR),
    CountStat('messages_sent:message_type:day',
              sql_data_collector(UserCount, count_message_type_by_user_query, None), CountStat.DAY),
    CountStat('messages_sent:client:day',
              sql_data_collector(UserCount, count_message_by_user_query, (Message, 'sending_client_id')),
              CountStat.DAY),
    CountStat('messages_in_stream:is_bot:day',
              sql_data_collector(StreamCount, count_message_by_stream_query, (UserProfile, 'is_bot')),
              CountStat.DAY),

    # Number of Users stats
    # Stats that count the number of active users in the UserProfile.is_active sense.

    # 'active_users_audit:is_bot:day' is the canonical record of which users were
    # active on which days (in the UserProfile.is_active sense).
    # Important that this stay a daily stat, so that 'realm_active_humans::day' works as expected.
    CountStat('active_users_audit:is_bot:day',
              sql_data_collector(UserCount, check_realmauditlog_by_user_query, (UserProfile, 'is_bot')),
              CountStat.DAY),
    # Sanity check on 'active_users_audit:is_bot:day', and a archetype for future LoggingCountStats.
    # In RealmCount, 'active_users_audit:is_bot:day' should be the partial
    # sum sequence of 'active_users_log:is_bot:day', for any realm that
    # started after the latter stat was introduced.
    LoggingCountStat('active_users_log:is_bot:day', RealmCount, CountStat.DAY),
    # Another sanity check on 'active_users_audit:is_bot:day'. Is only an
    # approximation, e.g. if a user is deactivated between the end of the
    # day and when this stat is run, they won't be counted. However, is the
    # simplest of the three to inspect by hand.
    CountStat('active_users:is_bot:day',
              sql_data_collector(RealmCount, count_user_by_realm_query, (UserProfile, 'is_bot')),
              CountStat.DAY, interval=TIMEDELTA_MAX),

    # User Activity stats
    # Stats that measure user activity in the UserActivityInterval sense.

    CountStat('1day_actives::day',
              sql_data_collector(UserCount, check_useractivityinterval_by_user_query, None),
              CountStat.DAY, interval=timedelta(days=1)-UserActivityInterval.MIN_INTERVAL_LENGTH),
    CountStat('15day_actives::day',
              sql_data_collector(UserCount, check_useractivityinterval_by_user_query, None),
              CountStat.DAY, interval=timedelta(days=15)-UserActivityInterval.MIN_INTERVAL_LENGTH),
    CountStat('minutes_active::day', DataCollector(UserCount, do_pull_minutes_active), CountStat.DAY),

    # Rate limiting stats

    # Used to limit the number of invitation emails sent by a realm
    LoggingCountStat('invites_sent::day', RealmCount, CountStat.DAY),

    # Dependent stats
    # Must come after their dependencies.

    # Canonical account of the number of active humans in a realm on each day.
    DependentCountStat('realm_active_humans::day',
                       sql_data_collector(RealmCount, count_realm_active_humans_query, None),
                       CountStat.DAY,
                       dependencies=['active_users_audit:is_bot:day', '15day_actives::day'])
]

COUNT_STATS = OrderedDict([(stat.property, stat) for stat in count_stats_])
