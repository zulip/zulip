from django.db import connection
from django.db.models import F, Count, Sum
from zerver.models import Realm, UserProfile, Message
from analytics.lib.interval import TimeInterval
from datetime import timedelta

class AnalyticsStat:
    def __init__(self, property, zerver_table, filter_args, analytics_table, smallest_interval, frequency):
        self.property = property
        self.zerver_table = zerver_table
        # might have to do something different for bitfields
        self.filter_args = filter_args
        self.analytics_table = analytics_table
        self.smallest_interval = smallest_interval
        self.frequency = frequency

COUNT_TYPES = frozenset(['zerver_pull', 'time_aggregate', 'cross_table_aggregate'])

# todo: incorporate these two arguments into a universal do_pull function.
def count_query(stat):
    return {(UserProfile, RealmCount) : count_user_by_realm_query,
            (Message, UserCount) : count_message_by_user_query,
            (Message, StreamCount) : count_message_by_stream_query,
            (Stream, RealmCount) : count_stream_by_realm_query}[(stat.zerver_table, stat.analytics_table)]

# todo: collapse these three?
def process_count(table, count_type, stat, time_interval, **kwargs):
    # what happens if there are 0 users, or 0 streams, or 0 realms?
    if not table.object.filter(property = stat.property,
                               end_time = time_interval.end,
                               interval = time_interval.interval).exists():
        if count_type == 'zerver_pull':
            kwargs['query'] = count_query(stat)
            action = do_pull_from_zerver
        elif count_type == 'time_aggregate':
            action = do_aggregate_hour_to_day
        elif count_type == 'cross_table_aggregate':
            action = do_aggregate_to_summary_table
        else:
            raise ValueError('Unknown count_type')
        action(stat, time_interval, **kwargs)

# only two summary tables at the moment: RealmCount and InstallationCount.
# will have to generalize this a bit if more are added
def do_aggregate_to_summary_table(stat, time_interval, table, to_table):
    if to_table == RealmTable:
        id_cols = 'realm_id,'
        group_by = 'GROUP BY realm_id'
    elif to_table = InstallationTable:
        id_cols = ''
        group_by = ''
    else:
        raise ValueError("%s is not a summary table" % (to_table,))

    query = """
        INSERT INTO %(to_table)s (%(id_cols)s value, property, end_time, interval)
        SELECT %(id_cols)s sum(value), property, end_time, interval
        FROM %(from_table)s WHERE
        (
            property = '%(property)s' AND
            end_time = %%s AND
            interval = %(interval)s
        )
        %(group_by)s
    """ % {'to_table': to_table._meta.db_table,
           'id_cols' : id_cols,
           'from_table' : from_table._meta.db_table,
           'property' : stat.property,
           'interval' : time_interval.interval,
           'group_by' : group_by}
    cursor = connection.cursor()
    # todo: check if cursor supports the %(key)s syntax
    cursor.execute(query, (time_interval.end,))
    cursor.close()

def do_aggregate_hour_to_day(stat, end_time):
    table = stat.analytics_table
    id_cols = ''.join([col + ', ' for col in table.extended_id()])
    group_by = 'GROUP BY %s' % table.extended_id()[0] if id_cols else ''
    query = """
        INSERT INTO %(table)s (%(id_cols)s value, property, end_time, interval)
        SELECT %(id_cols)s sum(value), property, %%s, 'day'
        FROM %(table)s WHERE
        (
            property = '%(property)s' AND
            end_time > %%s AND
            end_time <= %%s AND
            interval = hour
        )
        %(group_by)s
    """ % {'table': table._meta.db_table,
           'id_cols' : id_cols,
           'property' : stat.
           'group_by' : group_by}
    cursor = connection.cursor()
    cursor.execute(query, (end_time, end_time - timedelta(days = 1), end_time))
    cursor.close()

## methods that hit the prod databases directly
# No left joins in Django ORM yet, so have to use raw SQL :(
# written in slightly more than needed generality, to reduce copy-paste errors
# as more of these are made / make it easy to extend to a pull_X_by_realm

def do_pull_from_zerver(stat, time_interval, query):
    zerver_table = stat.zerver_table._meta.db_table
    join_args = ' '.join('AND %s.%s = %s' % (zerver_table, key, value) \
                         for key, value in stat.filter_args.items())
    query_ = query % {'zerver_table' : zerver_table,
                      'property' : stat.property,
                      'interval' : time_interval.interval,
                      'join_args' : join_args}
    cursor = connection.cursor()
    cursor.execute(query_, {'time_start' : time_interval.start}, 'time_end' : time_interval.end)
    cursor.close()

count_user_by_realm_query = """
    INSERT INTO analytics_realmcount
        (realm_id, value, property, end_time, interval)
    SELECT
        zerver_realm.id, count(*), '%(property)s', %%(time_end)s, '%(interval)s'
    FROM zerver_realm
    LEFT JOIN %(zerver_table)s
    ON
    (
        %(zerver_table)s.realm_id = zerver_realm.id AND
        %(zerver_table)s.date_joined >= %%(time_start)s AND
        %(zerver_table)s.date_joined < %%(time_end)s AND
        zerver_realm.date_created < %%(time_end)s
        %(join_args)s
    )
    GROUP BY zerver_realm.id
"""

# currently .sender_id is only Message specific thing
count_message_by_user_query = """
    INSERT INTO analytics_usercount
        (user_id, realm_id, value, property, end_time, interval)
    SELECT
        zerver_userprofile.id, zerver_userprofile.realm_id, count(*), '%(property)s', %%(time_end)s, '%(interval)s'
    FROM zerver_userprofile
    LEFT JOIN %(zerver_table)s
    ON
    (
        %(zerver_table)s.sender_id = zerver_userprofile.id AND
        %(zerver_table)s.pub_date >= %%(time_start)s AND
        %(zerver_table)s.pub_date < %%(time_end)s AND
        zerver_userprofile.date_joined < %%(time_end)s
        %(join_args)s
    )
    GROUP BY zerver_userprofile.id
"""

count_message_by_stream_query = """
    INSERT INTO analytics_streamcount
        (stream_id, realm_id, value, property, end_time, interval)
    SELECT
        zerver_stream.id, zerver_stream.realm_id, count(*), '%(property)s', %%(time_end)s, '%(interval)s'
    FROM zerver_stream
    INNER JOIN zerver_recipient
    ON
    (
        zerver_recipient.type = STREAM AND
        zerver_stream.id = zerver_recipient.type_id
    )
    LEFT JOIN %(zerver_table)s
    ON
    (
        %(zerver_table)s.recipient_id = zerver_recipient.id AND
        %(zerver_table)s.pub_date >= %%(time_start)s AND
        %(zerver_table)s.pub_date < %%(time_end)s AND
        zerver_stream.date_created < %%(time_end)s
        %(join_args)s
    )
    GROUP BY zerver_stream.id
"""
