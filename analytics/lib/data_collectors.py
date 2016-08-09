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
def pull_function(stat):
    return {(UserProfile, RealmCount) : do_pull_user_by_realm,
            (Message, UserCount) : do_pull_message_by_user,
            (Message, StreamCount) : do_pull_message_by_stream,
            (Stream, RealmCount) : do_pull_stream_by_realm}[(stat.zerver_table, stat.analytics_table)]

# todo: collapse these three?
def process_count(table, count_type, stat, time_interval, **kwargs):
    # what happens if there are 0 users, or 0 streams, or 0 realms?
    if not table.object.filter(property = stat.property,
                               end_time = time_interval.end,
                               interval = time_interval.interval).exists():
        if count_type == 'zerver_pull':
            action = pull_function(stat)
        elif count_type == 'time_aggregate':
            action = do_aggregate_hour_to_day
        elif count_type == 'cross_table_aggregate':
            action = do_aggregate_to_summary_table
        else:
            raise ValueError('Unknown count_type')
        action(stat, time_interval, **kwargs)

def process_pull_count(stat, time_interval):
    # what happens if there are 0 users, or 0 streams, or 0 realms?
    if not stat.analytics_table.object.filter(property = stat.property,
                                              end_time = time_interval.end,
                                              interval = time_interval.interval).exists():
        pull_function(stat)(stat.property, stat.filter_args, time_interval)

def process_day_count(stat, time_interval):
    if time_interval.interval != 'day':
        raise ValueError('time_interval.interval should be day')
    if not stat.analytics_table.object.filter(property = stat.property,
                                              end_time = time_interval.end,
                                              interval = time_interval.interval).exists():
        do_aggregate_hour_to_day(stat.analytics_table, stat.property, time_interval.end)

def process_summary_count(stat, time_interval, from_table, to_table)
    if not to_table.object.filter(property = stat.property,
                                  end_time = time_interval.end,
                                  interval = time_interval.interval).exists():
        do_aggregate_to_summary_table(stat.property, time_interval, from_table, to_table)



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
def do_pull_user_by_realm(stat, time_interval):
    join_args = ' '.join('AND user_.%s = %s' % (key, value) for
                         key, value in stat.filter_args.items())
    query = """
        INSERT INTO analytics_realmcount
            (realm_id, value, property, end_time, interval)
        SELECT
            realm.id, count(*), '%(property)s', %%s, '%(interval)s'
        FROM zerver_realm as realm
        LEFT JOIN zerver_userprofile as user_
        ON
        (
            user_.realm_id = realm.id AND
            user_.date_joined >= %%s AND
            user_.date_joined < %%s AND
            realm.date_created < %%s
            %(join_args)s
        )
        GROUP BY realm.id
        """ % {'property' : stat.property,
               'interval' : time_interval.interval,
               'join_args' : join_args}
    cursor = connection.cursor()
    cursor.execute(query, (time_interval.end, time_interval.start, time_interval.end, time_interval.end))
    cursor.close()

def do_pull_user_by_realm


def do_pull_message_by_user(stat, time_interval):
    join_args = ' '.join('AND user_.%s = %s' % (key, value) for
                         key, value in stat.filter_args.items())
    query = """
        INSERT INTO analytics_usercount
            (realm_id, user_id, value, property, end_time, interval)
        SELECT
            realm.id, user_.id, count(*), '%(property)s', %%s, '%(interval)s'
        FROM zerver_userprofile as user_
        LEFT JOIN zerver_message as message
        ON
        (
            message.sender_id = user_.id AND
            message.pub_date >= %%s AND
            message.pub_date < %%s AND
            user_.date_joined < %%s
            %(join_args)s
        )
        GROUP BY user_.id
        """ % {'property' : stat.property,
               'interval' : time_interval.interval,
               'join_args' : join_args}
    cursor = connection.cursor()
    cursor.execute(query, (time_interval.end, time_interval.start, time_interval.end, time_interval.end))
    cursor.close()

def do_pull_message_by_stream(stat, time_interval):
    pass


## not going to work, since need additional joins for e.g. the recipient table
def do_pull_from_zerver(property, filter_args, time_interval):
    zerver_fields = {}
    zerver_fields['created'] = {Message : 'pub_date', UserProfile : 'date_joined', Realm : 'date_created'}
    zerver_fields['realm_id'] = {Message : 'sender.realm_id', UserProfile : 'realm_id'}
    zerver_fields['user_id'] = {Message : 'sender_id'}

    extended_id = stat.analytics_table.extended_id()
    join_args = ' '.join('AND user_.%s = %s' % (key, value) for
                         key, value in filter_args.items())
    insert_str = ''.join(col + ', ' for col in extended_id)
    select_str = ''.join(zerver_fields[col][stat.zerver_table] + ', '
                         for col in extended_id)

    query = """
        INSERT INTO %(analytics_table)s
            (%(insert_str)s value, property, end_time, interval)
        SELECT
            %(select_str)s COUNT(*), '%(property)s', %%s, '%(interval)s'
        FROM %(zerver_key_table)s
        LEFT JOIN %(zerver_table)s
        ON
        (
            %(zerver_table)s.%(id)s = %(zerver_key_table)s.%(key_id)s AND
            %(zerver_table)s.%(created)s >= %%s AND
            %(zerver_table)s.%(created)s < %%s AND
            %(zerver_key_table)s.%(key_created)s < %%s
            %(join_args)s
        )
        GROUP BY %(zerver_key_table)s.%(key_id)s
        """ % {'analytics_table' : stat.analytics_table,
               'insert_str' : insert_str,
               'select_str' : select_str,
               'property' : stat.property,
               'interval' : time_interval.interval,
               'zerver_key_table' : stat.analytics_table.key_model()._meta.db_table,
               'zerver_table' : stat.zerver_table._meta.db_table,
               # possibly wrong
               'id' : zerver_fields[extended_id[0]][stat.zerver_table]
               'join_args' : join_args}
    cursor = connection.cursor()
    cursor.execute(query, (time_interval.end, time_interval.start, time_interval.end, time_interval.end))
    cursor.close()




get stream count from messages

select message.recipient, count(*), property, end_time, interval
from zerver_stream left join zerver_message on
zerver_stream.id = zerver_message.recipient.type_id
where
stream created early enough
message created early enough
etc
