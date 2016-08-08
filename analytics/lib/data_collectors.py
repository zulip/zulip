from django.db import connection
from django.db.models import F, Count, Sum
from zerver.models import Realm, UserProfile, Message
from analytics.lib.interval import TimeInterval

##### put stuff into the analytics databases

# it seems likely that it is possible to do the whole process at the
# database level using F expressions (namely, without pulling anything into
# python). Currently the 'for row in rows ..' is the only place stuff is
# being pulled out of the db.

# TODO: need to insert valid_ids that don't show up!!

class AnalyticsStat:
    def __init__(self, property, zerver_table, filter_args, aggregate_by, smallest_interval, frequency):
        self.property = property
        self.zerver_table = zerver_table
        self.filter_args = filter_args
        self.aggregate_by = aggregate_by
        self.smallest_interval = smallest_interval
        self.frequency = frequency

count_tables = {'realm' : RealmCount, 'user' : UserCount, 'stream' : StreamCount}
count_functions = {(UserProfile, 'realm') : count_user_by_realm,
                   (Message, 'user') : count_message_by_user,
                   (Message, 'stream') : count_message_by_stream,
                   (Stream, 'realm') : count_stream_by_realm}

def process_count(stat, time_interval):
    table = count_tables[stat.aggregate_by]
    # check if there is at least one row with the filter args
    # note that this will create problems for aborted jobs, since e.g. there will be rows for
    # for some but not all realms, say
    if not table.object.filter(property = stat.property,
                               end_time = time_interval.end,
                               interval = time_interval.interval).exists():
        count_functions[(stat.zerver_table, stat.aggregate_by)](stat, time_interval)

def process_aggregate_count(table, valid_ids, id_field, aggregate_function, property, time_interval):
    return process_count(table, valid_ids, id_field,
                         aggregate_function(property, time_interval),
                         property, time_interval)

## aggregators. Possibly to be written more generally once we have a StreamCount, and more intervals

def aggregate_user_to_realm(property, time_interval):
    return UserCount.objects \
                    .filter(property = property,
                            end_time = time_interval.end,
                            interval = time_interval.interval) \
                    .values('realm') \
                    .annotate(realm_id=F('realm'), value=Sum('value')) \
                    .values('realm_id', 'value')

def aggregate_realm_hour_to_day(property, time_interval):
    return RealmCount.objects \
                     .filter(interval = 'hour',
                             property = property,
                             end_time__gt = time_interval.end - timedelta(days=1),
                             end_time__lte = time_interval.end) \
                     .values('realm') \
                     .annotate(realm_id=F('realm'), value=Sum('value')) \
                     .values('realm_id', 'value')

def aggregate_user_hour_to_day(property, time_interval):
    return UserCount.objects \
                    .filter(interval = 'hour',
                            property = property,
                            end_time__gt = time_interval.end - timedelta(days=1),
                            end_time__lte = time_interval.end) \
                     .values('user', 'realm') \
                     .annotate(userprofile_id=F('user'), realm_id=F('realm'), value=Sum('value')) \
                     .values('userprofile_id', 'realm_id', 'value')

## methods that hit the prod databases directly
# No left joins in Django ORM yet, so have to use raw SQL :(
def count_user_by_realm(stat, time_interval):
    join_args = ' '.join('AND user_.%s = %s' % (key, value) for
                         key, value in stat.filter_args.items())
    query = """
        INSERT INTO analytics_realmcount
            (realm_id, value, property, end_time, interval)
        SELECT
            realm.id, count(user_.id), %s, %s, %s
        FROM zerver_realm as realm
        LEFT JOIN zerver_userprofile as user_
        ON
        (
            user_.realm_id = realm.id AND
            user_.date_joined >= %s AND
            user_.date_joined < %s AND
            realm.date_created < %s
            %s
        )
        GROUP BY realm.id
        """
    cursor = connection.cursor()
    cursor.execute(query, (stat.property, time_interval.end, time_interval.interval, \
                           time_interval.start, time_interval.end, time_interval.end, join_args))
    rows = cursor.fetchall()
    cursor.close()



###

def count_message_by_user(time_interval, **filter_args):
    return Message.objects \
                  .filter(date_joined__gte = time_interval.start,
                          date_joined__lt = time_interval.end,
                          **filter_args) \
                  .values('sender') \
                  .annotate(userprofile_id=F('sender_id'), realm_id=F('sender_id__realm'), value=Count('sender_id')) \
                  .values('userprofile_id', 'realm_id', 'value')

def get_human_count_by_realm(time_interval):
    return UserProfile.objects \
                      .filter(is_bot = False,
                              is_active = True,
                              date_joined__gte = time_interval.start,
                              date_joined__lt = time_interval.end) \
                      .values('realm') \
                      .annotate(realm_id=F('realm'), value=Count('realm')) \
                      .values('realm_id', 'value')

def get_bot_count_by_realm(time_interval):
    return UserProfile.objects \
                      .filter(is_bot = True,
                              is_active = True,
                              date_joined__gte = time_interval.start,
                              date_joined__lt = time_interval.end) \
                      .values('realm') \
                      .annotate(realm_id=F('realm'), value=Count('realm')) \
                      .values('realm_id', 'value')

def get_messages_sent_count_by_user(time_interval):
    return Message.objects \
                  .filter(pub_date__gte = time_interval.start,
                          pub_date__lt = time_interval.end) \
                  .values('sender') \
                  .annotate(userprofile_id=F('sender_id'), realm_id=F('sender_id__realm'), value=Count('sender_id')) \
                  .values('userprofile_id', 'realm_id', 'value')
