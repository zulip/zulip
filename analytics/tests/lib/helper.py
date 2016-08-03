from django.db.models import F, Count, Sum

from zerver.models import Realm, UserProfile, Message

from datetime import datetime, timedelta

# Name isn't great .. fixedinterval? timerange? Trying to distinguish
# generic intervals like 'hour' or 'quarter' from fixed intervals like
# 'Aug 3 2016 from 9-10am'
class TimeInterval:
    def __init__(self, interval, end = datetime.utcnow(), floor_to_boundary = 'hour'):
        # Not the best logic for when we have intervals like 'quarter', but okay for now
        if floor_to_boundary is not None:
            self.end = floor_to_interval_boundary(end, floor_to_boundary)
        self.interval = interval
        if interval == 'gauge':
            self.start = datetime(year = datetime.MINYEAR)
        else:
            self.start = subtract_interval(self.end, interval)
    # add way to init with start_time and end_time, and no interval

# I think the right way to do the next two is to have an interval class
# (subclassed to hourinterval, dayinterval, etc) with methods like floor and
# subtract. Seems like overkill for now, though.
def floor_to_interval_boundary(datetime_object, interval):
    # type: (datetime, text_type) -> datetime
    # datetime objects are (year, month, day, hour, minutes, seconds, microseconds)
    if interval == 'hour':
        return datetime(*datetime_object.timetuple()[:4])
    elif interval == 'day':
        return datetime(*datetime_object.timetuple()[:3])
    else:
        raise ValueError("Unknown interval", interval)

# don't have to worry about leap seconds, since datetime doesn't support it
def subtract_interval(datetime_object, interval):
    if interval == 'hour':
        return datetime_object - timedelta(seconds = 3600)
    if interval == 'day':
        return datetime_object - timedelta(days = 1)
    else:
        raise ValueError("Unknown interval", interval)

def timeinterval_range(first, last, interval, step_interval):
    end = floor_to_interval_boundary(last, step_interval)
    ans = []
    while end >= first:
        ans.append(TimeInterval(interval, end, floor_to_boundary = None))
        end = subtract_interval(end, step_interval)
    ans.reverse()
    return ans

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

##### generic aggregators

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

def get_message_counts_by_realm(time_interval):



def get_active_user_count_by_realm(time_interval):
    pass

def get_active_users_by_realm(self, start_time, interval):
    pass

def get_at_risk_count_by_realm(self, gauge_time):
    pass
