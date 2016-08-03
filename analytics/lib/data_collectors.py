from django.db.models import F, Count, Sum
from zerver.models import Realm, UserProfile, Message
from analytics.lib.interval import TimeInterval

##### put stuff into the analytics databases

def exists_row_with_values(table, **filter_args):
    return len(table.objects.filter(**filter_args)[:1]) > 0

def insert_count(table, valid_ids, id_field, rows, property, time_interval):
    table.objects.bulk_create([table(property = property,
                                     end_time = time_interval.end,
                                     interval = time_interval.interval,
                                     **row)
                               for row in rows if row[id_field] in valid_ids])

def process_count(table, valid_ids, id_field, value_function, property, time_interval):
    if not exists_row_with_values(table,
                                  property =  property,
                                  end_time = time_interval.end,
                                  interval = time_interval.interval):
        rows = value_function(time_interval)
        insert_count(table, valid_ids, id_field, rows, property, time_interval)

def process_aggregate_count(table, valid_ids, id_field, aggregate_function, property, time_interval):
    return process_count(table, valid_ids, id_field,
                         aggregate_function(property, time_interval),
                         property, time_interval)

## aggregators

def aggregate_user_to_realm(property, time_interval):
    return UserCount.objects \
                    .filter(end_time = time_interval.end,
                            interval = time_interval.interval,
                            property = property) \
                    .annotate(realm_id=F('realm'), value=Sum('value')) \
                    .values('realm_id', 'value')

def aggregate_realm_hour_to_day(property, time_interval):
    return RealmCount.objects \
                     .filter(end_time__gt = time_interval.end - timedelta(days=1),
                             end_time__lte = time_interval.end,
                             interval = 'hour',
                             property = property) \
                     .annotate(realm_id=F('realm'), value=Sum('value')) \
                     .values('realm_id', 'value')

def aggregate_user_hour_to_day(property, time_interval):
    return UserCount.objects \
                    .filter(end_time__gt = time_interval.end - timedelta(days=1),
                            end_time__lte = time_interval.end,
                            interval = 'hour',
                            property = property) \
                     .annotate(userprofile_id=F('user'), realm_id=F('realm'), value=Sum('value')) \
                     .values('userprofile_id', 'realm_id', 'value')

## methods that hit the prod databases directly

# gauge, realm
def get_human_count_by_realm(time_interval):
    return UserProfile.objects \
                      .filter(is_bot = False,
                              is_active = True,
                              date_joined__lt = time_interval.end) \
                      .annotate(realm_id=F('realm'), value=Count('realm')) \
                      .values('realm_id', 'value')

# gauge, realm
def get_bot_count_by_realm(time_interval):
    return UserProfile.objects \
                      .filter(is_bot = True,
                              is_active = True,
                              date_joined__lt = time_interval.end) \
                      .annotate(realm_id=F('realm'), value=Count('realm')) \
                      .values('realm_id', 'value')


# hour, user
def get_messages_sent_count_by_user(time_interval):
    return Message.objects \
                  .filter(pub_date__gte = time_interval.start,
                          pub_date__lt = time_interval.end) \
                  .annotate(userprofile_id=F('sender_id'), realm_id=F('sender_id__realm'), value=Count('sender_id')) \
                  .values('userprofile_id', 'realm_id', 'value')
