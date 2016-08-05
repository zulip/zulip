from django.db.models import F, Count, Sum
from zerver.models import Realm, UserProfile, Message
from analytics.lib.interval import TimeInterval

##### put stuff into the analytics databases

# it seems likely that it is possible to do the whole process at the
# database level using F expressions (namely, without pulling anything into
# python). Currently the 'for row in rows ..' is the only place stuff is
# being pulled out of the db.

# TODO: need to insert valid_ids that don't show up!!

def process_count(table, valid_ids, id_field, value_function, property, time_interval):
    # check if there is at least one row with the filter args
    # note that this will create problems for aborted jobs, since e.g. there will be rows for
    # for some but not all realms, say
    if not table.object.filter(property = property,
                               end_time = time_interval.end,
                               interval = time_interval.interval).exists():
        # collect the data from zerver and/or analytics tables
        rows = value_function(time_interval)
        # insert all the rows into the appropriate analytics table
        table.objects.bulk_create([table(property = property,
                                         end_time = time_interval.end,
                                         interval = time_interval.interval,
                                         **row)
                                   for row in rows if row[id_field] in valid_ids])


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

# # possibly should do it this way instead? I didn't realize how many of our
# # stats could be written as a single filter! This would also work well with
# # an AnalyticsStat class.
# def usertable_count(time_interval, **kwargs):
#     return UserProfile.objects \
#                       .filter(date_joined__gte = time_interval.start,
#                               date_joined__lt = time_interval.end,
#                               **kwargs) \
#                       .values('realm') \
#                       .annotate(realm_id=F('realm'), value=Count('realm')) \
#                       .values('realm_id', 'value')
# def messagetable_count, realmtable_count, etc
# might need a messagetable_count_by_realm, if there are message stats we collect at a
# realm but not user level
#
# # and then ..
# def get_human_count_by_realm(time_interval):
#     return usertable_count(time_interval, is_bot = False, is_active = True)
# def get_bot_count, get_messages_sent_count, etc

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
