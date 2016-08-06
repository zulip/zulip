from django.db.models import F, Count, Sum
from zerver.models import Realm, UserProfile, Message
from analytics.lib.interval import TimeInterval

##### put stuff into the analytics databases

# it seems likely that it is possible to do the whole process at the
# database level using F expressions (namely, without pulling anything into
# python). Currently the 'for row in rows ..' is the only place stuff is
# being pulled out of the db.

# TODO: need to insert valid_ids that don't show up!!

count_tables = {'realm' : RealmCount, 'user' : UserCount, 'stream' : StreamCount}
count_functions = {(UserProfile, 'realm') : count_user_by_realm,
                   (Message, 'user') : count_message_by_user,
                   (Message, 'stream') : count_message_by_stream,
                   (Stream, 'realm') : count_stream_by_realm}

def process_count(stat, time_interval):
    table = count_tables[stat.aggregate_by]
    if not table.object.filter(property = stat.property,
                               end_time = time_interval.end,
                               interval = time_interval.interval).exists():
        data = count_functions[(stat.zerver_table, stat.aggregate_by)](time_interval, **stat.filter_args)
        table.objects.bulk_create([table(property = stat.property,
                                         end_time = time_interval.end,
                                         interval = time_interval.interval,
                                         **row)
                                   for row in rows if row[id_field] in valid_ids])


def process_count(stat, rows, time_interval):
    count_table = count_tables[stat.aggregate_by]
    if not count_table.object.filter(property = stat.property,
                                     end_time = time_interval.end,
                                     interval = time_interval.interval).exists():
        data = count_functions[(stat.zerver_table, stat.aggregate_by)](time_interval, **stat.filter_args)
        count_table.objects.bulk_create([count_table(property = stat.property,
                                                     end_time = time_interval.end,
                                                     interval = time_interval.interval,
                                                     **row)
                                         for row in rows if row[id_field] in valid_ids])



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
# No left joins in Django ORM yet, so have to use raw SQL :(
def count_user_by_realm(time_interval, **filter_args):

    query = """
SELECT
    realm.id AS realm_id,
    Count(realm_id) AS value
FROM zerver_realm AS realm
LEFT JOIN zerver_userprofile AS user
    ON user.realm_id = realm.id

GROUP BY realm.id
"""

Out[51]: 'SELECT "zerver_realm"."id", COUNT("zerver_realm"."id") AS "a" FROM "zerver_realm" INNER JOIN "zerver_userprofile" ON ( "zerver_realm"."id" = "zerver_userprofile"."realm_id" ) WHERE "zerver_userprofile"."is_bot" = True GROUP BY "zerver_realm"."id", "zerver_realm"."domain", "zerver_realm"."name", "zerver_realm"."restricted_to_domain", "zerver_realm"."invite_required", "zerver_realm"."invite_by_admins_only", "zerver_realm"."create_stream_by_admins_only", "zerver_realm"."mandatory_topics", "zerver_realm"."show_digest_email", "zerver_realm"."name_changes_disabled", "zerver_realm"."allow_message_editing", "zerver_realm"."message_content_edit_limit_seconds", "zerver_realm"."date_created", "zerver_realm"."notifications_stream_id", "zerver_realm"."deactivated"'


    select zerver_realm

    related_args = {'userprofile__' + key : value for (key, value) in filter_args}
    return Realm.objects \
                .filter(date_created__lt = time_interval.end, \
                        userprofile__date_joined__gte = time_interval.start, \
                        userprofile__date_joined__lt = time_interval.end, \
                        **related_args) \
                .annotate(realm_id = 'id', value = Count('id')) \
                .values('realm_id', 'value')


    return UserProfile.objects \
                      .filter(date_joined__gte = time_interval.start,
                              date_joined__lt = time_interval.end,
                              **filter_args) \
                      .values('realm') \
                      .annotate(realm_id=F('realm'), value=Count('realm')) \
                      .values('realm_id', 'value')

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
