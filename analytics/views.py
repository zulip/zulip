from __future__ import absolute_import, division

from django.conf import settings
from django.core import urlresolvers
from django.db import connection
from django.db.models import Sum
from django.db.models.query import QuerySet
from django.http import HttpResponseNotFound, HttpRequest, HttpResponse
from django.template import RequestContext, loader
from django.utils import timezone
from django.utils.translation import ugettext as _
from jinja2 import Markup as mark_safe

from analytics.lib.counts import CountStat, process_count_stat, COUNT_STATS
from analytics.lib.time_utils import time_range
from analytics.models import BaseCount, InstallationCount, RealmCount, \
    UserCount, StreamCount, last_successful_fill

from zerver.decorator import has_request_variables, REQ, zulip_internal, \
    zulip_login_required, to_non_negative_int, to_utc_datetime
from zerver.lib.request import JsonableError
from zerver.lib.response import json_success
from zerver.lib.timestamp import ceiling_to_hour, ceiling_to_day, timestamp_to_datetime
from zerver.models import Realm, UserProfile, UserActivity, \
    UserActivityInterval, Client
from zproject.jinja2 import render_to_response

from collections import defaultdict
from datetime import datetime, timedelta
import itertools
import json
import logging
import pytz
import re
import time

from six.moves import filter, map, range, zip
from typing import Any, Callable, Dict, List, Optional, Set, Text, \
    Tuple, Type, Union

@zulip_login_required
def stats(request):
    # type: (HttpRequest) -> HttpResponse
    return render_to_response('analytics/stats.html',
                              context=dict(realm_name = request.user.realm.name))

@has_request_variables
def get_chart_data(request, user_profile, chart_name=REQ(),
                   min_length=REQ(converter=to_non_negative_int, default=None),
                   start=REQ(converter=to_utc_datetime, default=None),
                   end=REQ(converter=to_utc_datetime, default=None)):
    # type: (HttpRequest, UserProfile, Text, Optional[int], Optional[datetime], Optional[datetime]) -> HttpResponse
    if chart_name == 'number_of_humans':
        stat = COUNT_STATS['active_users:is_bot:day']
        tables = [RealmCount]
        subgroups = ['false', 'true']
        labels = ['human', 'bot']
        labels_sort_function = None
        include_empty_subgroups = [True]
    elif chart_name == 'messages_sent_over_time':
        stat = COUNT_STATS['messages_sent:is_bot:hour']
        tables = [RealmCount, UserCount]
        subgroups = ['false', 'true']
        labels = ['human', 'bot']
        labels_sort_function = None
        include_empty_subgroups = [True, False]
    elif chart_name == 'messages_sent_by_message_type':
        stat = COUNT_STATS['messages_sent:message_type:day']
        tables = [RealmCount, UserCount]
        subgroups = ['public_stream', 'private_stream', 'private_message']
        labels = ['Public Streams', 'Private Streams', 'PMs & Group PMs']
        labels_sort_function = lambda data: sort_by_totals(data['realm'])
        include_empty_subgroups = [True, True]
    elif chart_name == 'messages_sent_by_client':
        stat = COUNT_STATS['messages_sent:client:day']
        tables = [RealmCount, UserCount]
        subgroups = [str(x) for x in Client.objects.values_list('id', flat=True).order_by('id')]
        # these are further re-written by client_label_map
        labels = list(Client.objects.values_list('name', flat=True).order_by('id'))
        labels_sort_function = sort_client_labels
        include_empty_subgroups = [False, False]
    else:
        raise JsonableError(_("Unknown chart name: %s") % (chart_name,))

    # Most likely someone using our API endpoint. The /stats page does not
    # pass a start or end in its requests.
    if start is not None and end is not None and start > end:
        raise JsonableError(_("Start time is later than end time. Start: %(start)s, End: %(end)s") %
                            {'start': start, 'end': end})

    realm = user_profile.realm
    if start is None:
        start = realm.date_created
    if end is None:
        end = last_successful_fill(stat.property)
    if end is None or start > end:
        logging.warning("User from realm %s attempted to access /stats, but the computed "
                        "start time: %s (creation time of realm) is later than the computed "
                        "end time: %s (last successful analytics update). Is the "
                        "analytics cron job running?" % (realm.string_id, start, end))
        raise JsonableError(_("No analytics data available. Please contact your server administrator."))

    end_times = time_range(start, end, stat.frequency, min_length)
    data = {'end_times': end_times, 'frequency': stat.frequency, 'interval': stat.interval}
    for table, include_empty_subgroups_ in zip(tables, include_empty_subgroups):
        if table == RealmCount:
            data['realm'] = get_time_series_by_subgroup(
                stat, RealmCount, realm.id, end_times, subgroups, labels, include_empty_subgroups_)
        if table == UserCount:
            data['user'] = get_time_series_by_subgroup(
                stat, UserCount, user_profile.id, end_times, subgroups, labels, include_empty_subgroups_)
    if labels_sort_function is not None:
        data['display_order'] = labels_sort_function(data)
    else:
        data['display_order'] = None
    return json_success(data=data)

def sort_by_totals(value_arrays):
    # type: (Dict[str, List[int]]) -> List[str]
    totals = []
    for label, values in value_arrays.items():
        totals.append((label, sum(values)))
    totals.sort(key=lambda label_total: label_total[1], reverse=True)
    return [label for label, total in totals]

# For any given user, we want to show a fixed set of clients in the chart,
# regardless of the time aggregation or whether we're looking at realm or
# user data. This fixed set ideally includes the clients most important in
# understanding the realm's traffic and the user's traffic. This function
# tries to rank the clients so that taking the first N elements of the
# sorted list has a reasonable chance of doing so.
def sort_client_labels(data):
    # type: (Dict[str, Dict[str, List[int]]]) -> List[str]
    realm_order = sort_by_totals(data['realm'])
    user_order = sort_by_totals(data['user'])
    label_sort_values = {} # type: Dict[str, float]
    for i, label in enumerate(realm_order):
        label_sort_values[label] = i
    for i, label in enumerate(user_order):
        label_sort_values[label] = min(i-.1, label_sort_values.get(label, i))
    return [label for label, sort_value in sorted(label_sort_values.items(),
                                                  key=lambda x: x[1])]

def table_filtered_to_id(table, key_id):
    # type: (Type[BaseCount], int) -> QuerySet
    if table == RealmCount:
        return RealmCount.objects.filter(realm_id=key_id)
    elif table == UserCount:
        return UserCount.objects.filter(user_id=key_id)
    elif table == StreamCount:
        return StreamCount.objects.filter(stream_id=key_id)
    elif table == InstallationCount:
        return InstallationCount.objects.all()
    else:
        raise AssertionError("Unknown table: %s" % (table,))

def client_label_map(name):
    # type: (str) -> str
    if name == "website":
        return "Website"
    if name.startswith("desktop app"):
        return "Old desktop app"
    if name == "ZulipAndroid":
        return "Android app"
    if name == "ZulipiOS":
        return "Old iOS app"
    if name == "ZulipMobile":
        return "New iOS app"
    if name in ["ZulipPython", "API: Python"]:
        return "Python API"
    if name.startswith("Zulip") and name.endswith("Webhook"):
        return name[len("Zulip"):-len("Webhook")] + " webhook"
    # Clients in dev environment autogenerated data start with _ so
    # that it's easy to manually drop without affecting other data.
    if settings.DEVELOPMENT and name.startswith("_"):
        return name[1:]
    return name

def rewrite_client_arrays(value_arrays):
    # type: (Dict[str, List[int]]) -> Dict[str, List[int]]
    mapped_arrays = {} # type: Dict[str, List[int]]
    for label, array in value_arrays.items():
        mapped_label = client_label_map(label)
        if mapped_label in mapped_arrays:
            for i in range(0, len(array)):
                mapped_arrays[mapped_label][i] += value_arrays[label][i]
        else:
            mapped_arrays[mapped_label] = [value_arrays[label][i] for i in range(0, len(array))]
    return mapped_arrays

def get_time_series_by_subgroup(stat, table, key_id, end_times, subgroups, labels, include_empty_subgroups):
    # type: (CountStat, Type[BaseCount], Optional[int], List[datetime], List[str], List[str], bool) -> Dict[str, List[int]]
    if len(subgroups) != len(labels):
        raise AssertionError("subgroups and labels have lengths %s and %s, which are different." %
                             (len(subgroups), len(labels)))
    queryset = table_filtered_to_id(table, key_id).filter(property=stat.property) \
                                                  .values_list('subgroup', 'end_time', 'value')
    value_dicts = defaultdict(lambda: defaultdict(int)) # type: Dict[Optional[str], Dict[datetime, int]]
    for subgroup, end_time, value in queryset:
        value_dicts[subgroup][end_time] = value
    value_arrays = {}
    for subgroup, label in zip(subgroups, labels):
        if (subgroup in value_dicts) or include_empty_subgroups:
            value_arrays[label] = [value_dicts[subgroup][end_time] for end_time in end_times]

    if stat == COUNT_STATS['messages_sent:client:day']:
        # HACK: We rewrite these arrays to collapse the Client objects
        # with similar names into a single sum, and generally give
        # them better names
        return rewrite_client_arrays(value_arrays)
    return value_arrays


eastern_tz = pytz.timezone('US/Eastern')

def make_table(title, cols, rows, has_row_class=False):
    # type: (str, List[str], List[Any], bool) -> str

    if not has_row_class:
        def fix_row(row):
            # type: (Any) -> Dict[str, Any]
            return dict(cells=row, row_class=None)
        rows = list(map(fix_row, rows))

    data = dict(title=title, cols=cols, rows=rows)

    content = loader.render_to_string(
        'analytics/ad_hoc_query.html',
        dict(data=data)
    )

    return content

def dictfetchall(cursor):
    # type: (connection.cursor) -> List[Dict[str, Any]]
    "Returns all rows from a cursor as a dict"
    desc = cursor.description
    return [
        dict(list(zip([col[0] for col in desc], row)))
        for row in cursor.fetchall()
    ]


def get_realm_day_counts():
    # type: () -> Dict[str, Dict[str, str]]
    query = '''
        select
            r.string_id,
            (now()::date - pub_date::date) age,
            count(*) cnt
        from zerver_message m
        join zerver_userprofile up on up.id = m.sender_id
        join zerver_realm r on r.id = up.realm_id
        join zerver_client c on c.id = m.sending_client_id
        where
            (not up.is_bot)
        and
            pub_date > now()::date - interval '8 day'
        and
            c.name not in ('zephyr_mirror', 'ZulipMonitoring')
        group by
            r.string_id,
            age
        order by
            r.string_id,
            age
    '''
    cursor = connection.cursor()
    cursor.execute(query)
    rows = dictfetchall(cursor)
    cursor.close()

    counts = defaultdict(dict) # type: Dict[str, Dict[int, int]]
    for row in rows:
        counts[row['string_id']][row['age']] = row['cnt']

    result = {}
    for string_id in counts:
        raw_cnts = [counts[string_id].get(age, 0) for age in range(8)]
        min_cnt = min(raw_cnts)
        max_cnt = max(raw_cnts)

        def format_count(cnt):
            # type: (int) -> str
            if cnt == min_cnt:
                good_bad = 'bad'
            elif cnt == max_cnt:
                good_bad = 'good'
            else:
                good_bad = 'neutral'

            return '<td class="number %s">%s</td>' % (good_bad, cnt)

        cnts = ''.join(map(format_count, raw_cnts))
        result[string_id] = dict(cnts=cnts)

    return result

def realm_summary_table(realm_minutes):
    # type: (Dict[str, float]) -> str
    query = '''
        SELECT
            realm.string_id,
            coalesce(user_counts.active_user_count, 0) active_user_count,
            coalesce(at_risk_counts.at_risk_count, 0) at_risk_count,
            (
                SELECT
                    count(*)
                FROM zerver_userprofile up
                WHERE up.realm_id = realm.id
                AND is_active
                AND not is_bot
            ) user_profile_count,
            (
                SELECT
                    count(*)
                FROM zerver_userprofile up
                WHERE up.realm_id = realm.id
                AND is_active
                AND is_bot
            ) bot_count
        FROM zerver_realm realm
        LEFT OUTER JOIN
            (
                SELECT
                    up.realm_id realm_id,
                    count(distinct(ua.user_profile_id)) active_user_count
                FROM zerver_useractivity ua
                JOIN zerver_userprofile up
                    ON up.id = ua.user_profile_id
                WHERE
                    query in (
                        '/json/send_message',
                        'send_message_backend',
                        '/api/v1/send_message',
                        '/json/update_pointer',
                        '/json/users/me/pointer'
                    )
                AND
                    last_visit > now() - interval '1 day'
                AND
                    not is_bot
                GROUP BY realm_id
            ) user_counts
            ON user_counts.realm_id = realm.id
        LEFT OUTER JOIN
            (
                SELECT
                    realm_id,
                    count(*) at_risk_count
                FROM (
                    SELECT
                        realm.id as realm_id,
                        up.email
                    FROM zerver_useractivity ua
                    JOIN zerver_userprofile up
                        ON up.id = ua.user_profile_id
                    JOIN zerver_realm realm
                        ON realm.id = up.realm_id
                    WHERE up.is_active
                    AND (not up.is_bot)
                    AND
                        ua.query in (
                            '/json/send_message',
                            'send_message_backend',
                            '/api/v1/send_message',
                            '/json/update_pointer',
                            '/json/users/me/pointer'
                        )
                    GROUP by realm.id, up.email
                    HAVING max(last_visit) between
                        now() - interval '7 day' and
                        now() - interval '1 day'
                ) as at_risk_users
                GROUP BY realm_id
            ) at_risk_counts
            ON at_risk_counts.realm_id = realm.id
        WHERE EXISTS (
                SELECT *
                FROM zerver_useractivity ua
                JOIN zerver_userprofile up
                    ON up.id = ua.user_profile_id
                WHERE
                    query in (
                        '/json/send_message',
                        '/api/v1/send_message',
                        'send_message_backend',
                        '/json/update_pointer',
                        '/json/users/me/pointer'
                    )
                AND
                    up.realm_id = realm.id
                AND
                    last_visit > now() - interval '2 week'
        )
        ORDER BY active_user_count DESC, string_id ASC
        '''

    cursor = connection.cursor()
    cursor.execute(query)
    rows = dictfetchall(cursor)
    cursor.close()

    # get messages sent per day
    counts = get_realm_day_counts()
    for row in rows:
        try:
            row['history'] = counts[row['string_id']]['cnts']
        except Exception:
            row['history'] = ''

    # augment data with realm_minutes
    total_hours = 0.0
    for row in rows:
        string_id = row['string_id']
        minutes = realm_minutes.get(string_id, 0.0)
        hours = minutes / 60.0
        total_hours += hours
        row['hours'] = str(int(hours))
        try:
            row['hours_per_user'] = '%.1f' % (hours / row['active_user_count'],)
        except Exception:
            pass

    # formatting
    for row in rows:
        row['string_id'] = realm_activity_link(row['string_id'])

    # Count active sites
    def meets_goal(row):
        # type: (Dict[str, int]) -> bool
        return row['active_user_count'] >= 5

    num_active_sites = len(list(filter(meets_goal, rows)))

    # create totals
    total_active_user_count = 0
    total_user_profile_count = 0
    total_bot_count = 0
    total_at_risk_count = 0
    for row in rows:
        total_active_user_count += int(row['active_user_count'])
        total_user_profile_count += int(row['user_profile_count'])
        total_bot_count += int(row['bot_count'])
        total_at_risk_count += int(row['at_risk_count'])

    rows.append(dict(
        string_id='Total',
        active_user_count=total_active_user_count,
        user_profile_count=total_user_profile_count,
        bot_count=total_bot_count,
        hours=int(total_hours),
        at_risk_count=total_at_risk_count,
    ))

    content = loader.render_to_string(
        'analytics/realm_summary_table.html',
        dict(rows=rows, num_active_sites=num_active_sites)
    )
    return content


def user_activity_intervals():
    # type: () -> Tuple[mark_safe, Dict[str, float]]
    day_end = timestamp_to_datetime(time.time())
    day_start = day_end - timedelta(hours=24)

    output = "Per-user online duration for the last 24 hours:\n"
    total_duration = timedelta(0)

    all_intervals = UserActivityInterval.objects.filter(
        end__gte=day_start,
        start__lte=day_end
    ).select_related(
        'user_profile',
        'user_profile__realm'
    ).only(
        'start',
        'end',
        'user_profile__email',
        'user_profile__realm__string_id'
    ).order_by(
        'user_profile__realm__string_id',
        'user_profile__email'
    )

    by_string_id = lambda row: row.user_profile.realm.string_id
    by_email = lambda row: row.user_profile.email

    realm_minutes = {}

    for string_id, realm_intervals in itertools.groupby(all_intervals, by_string_id):
        realm_duration = timedelta(0)
        output += '<hr>%s\n' % (string_id,)
        for email, intervals in itertools.groupby(realm_intervals, by_email):
            duration = timedelta(0)
            for interval in intervals:
                start = max(day_start, interval.start)
                end = min(day_end, interval.end)
                duration += end - start

            total_duration += duration
            realm_duration += duration
            output += "  %-*s%s\n" % (37, email, duration)

        realm_minutes[string_id] = realm_duration.total_seconds() / 60

    output += "\nTotal Duration:                      %s\n" % (total_duration,)
    output += "\nTotal Duration in minutes:           %s\n" % (total_duration.total_seconds() / 60.,)
    output += "Total Duration amortized to a month: %s" % (total_duration.total_seconds() * 30. / 60.,)
    content = mark_safe('<pre>' + output + '</pre>')
    return content, realm_minutes

def sent_messages_report(realm):
    # type: (str) -> str
    title = 'Recently sent messages for ' + realm

    cols = [
        'Date',
        'Humans',
        'Bots'
    ]

    query = '''
        select
            series.day::date,
            humans.cnt,
            bots.cnt
        from (
            select generate_series(
                (now()::date - interval '2 week'),
                now()::date,
                interval '1 day'
            ) as day
        ) as series
        left join (
            select
                pub_date::date pub_date,
                count(*) cnt
            from zerver_message m
            join zerver_userprofile up on up.id = m.sender_id
            join zerver_realm r on r.id = up.realm_id
            where
                r.string_id = %s
            and
                (not up.is_bot)
            and
                pub_date > now() - interval '2 week'
            group by
                pub_date::date
            order by
                pub_date::date
        ) humans on
            series.day = humans.pub_date
        left join (
            select
                pub_date::date pub_date,
                count(*) cnt
            from zerver_message m
            join zerver_userprofile up on up.id = m.sender_id
            join zerver_realm r on r.id = up.realm_id
            where
                r.string_id = %s
            and
                up.is_bot
            and
                pub_date > now() - interval '2 week'
            group by
                pub_date::date
            order by
                pub_date::date
        ) bots on
            series.day = bots.pub_date
    '''
    cursor = connection.cursor()
    cursor.execute(query, [realm, realm])
    rows = cursor.fetchall()
    cursor.close()

    return make_table(title, cols, rows)

def ad_hoc_queries():
    # type: () -> List[Dict[str, str]]
    def get_page(query, cols, title):
        # type: (str, List[str], str) -> Dict[str, str]
        cursor = connection.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        rows = list(map(list, rows))
        cursor.close()

        def fix_rows(i, fixup_func):
            # type: (int, Union[Callable[[Realm], mark_safe], Callable[[datetime], str]]) -> None
            for row in rows:
                row[i] = fixup_func(row[i])

        for i, col in enumerate(cols):
            if col == 'Realm':
                fix_rows(i, realm_activity_link)
            elif col in ['Last time', 'Last visit']:
                fix_rows(i, format_date_for_activity_reports)

        content = make_table(title, cols, rows)

        return dict(
            content=content,
            title=title
        )

    pages = []

    ###

    for mobile_type in ['Android', 'ZulipiOS']:
        title = '%s usage' % (mobile_type,)

        query = '''
            select
                realm.string_id,
                up.id user_id,
                client.name,
                sum(count) as hits,
                max(last_visit) as last_time
            from zerver_useractivity ua
            join zerver_client client on client.id = ua.client_id
            join zerver_userprofile up on up.id = ua.user_profile_id
            join zerver_realm realm on realm.id = up.realm_id
            where
                client.name like '%s'
            group by string_id, up.id, client.name
            having max(last_visit) > now() - interval '2 week'
            order by string_id, up.id, client.name
        ''' % (mobile_type,)

        cols = [
            'Realm',
            'User id',
            'Name',
            'Hits',
            'Last time'
        ]

        pages.append(get_page(query, cols, title))

    ###

    title = 'Desktop users'

    query = '''
        select
            realm.string_id,
            client.name,
            sum(count) as hits,
            max(last_visit) as last_time
        from zerver_useractivity ua
        join zerver_client client on client.id = ua.client_id
        join zerver_userprofile up on up.id = ua.user_profile_id
        join zerver_realm realm on realm.id = up.realm_id
        where
            client.name like 'desktop%%'
        group by string_id, client.name
        having max(last_visit) > now() - interval '2 week'
        order by string_id, client.name
    '''

    cols = [
        'Realm',
        'Client',
        'Hits',
        'Last time'
    ]

    pages.append(get_page(query, cols, title))

    ###

    title = 'Integrations by realm'

    query = '''
        select
            realm.string_id,
            case
                when query like '%%external%%' then split_part(query, '/', 5)
                else client.name
            end client_name,
            sum(count) as hits,
            max(last_visit) as last_time
        from zerver_useractivity ua
        join zerver_client client on client.id = ua.client_id
        join zerver_userprofile up on up.id = ua.user_profile_id
        join zerver_realm realm on realm.id = up.realm_id
        where
            (query in ('send_message_backend', '/api/v1/send_message')
            and client.name not in ('Android', 'ZulipiOS')
            and client.name not like 'test: Zulip%%'
            )
        or
            query like '%%external%%'
        group by string_id, client_name
        having max(last_visit) > now() - interval '2 week'
        order by string_id, client_name
    '''

    cols = [
        'Realm',
        'Client',
        'Hits',
        'Last time'
    ]

    pages.append(get_page(query, cols, title))

    ###

    title = 'Integrations by client'

    query = '''
        select
            case
                when query like '%%external%%' then split_part(query, '/', 5)
                else client.name
            end client_name,
            realm.string_id,
            sum(count) as hits,
            max(last_visit) as last_time
        from zerver_useractivity ua
        join zerver_client client on client.id = ua.client_id
        join zerver_userprofile up on up.id = ua.user_profile_id
        join zerver_realm realm on realm.id = up.realm_id
        where
            (query in ('send_message_backend', '/api/v1/send_message')
            and client.name not in ('Android', 'ZulipiOS')
            and client.name not like 'test: Zulip%%'
            )
        or
            query like '%%external%%'
        group by client_name, string_id
        having max(last_visit) > now() - interval '2 week'
        order by client_name, string_id
    '''

    cols = [
        'Client',
        'Realm',
        'Hits',
        'Last time'
    ]

    pages.append(get_page(query, cols, title))

    return pages

@zulip_internal
@has_request_variables
def get_activity(request):
    # type: (HttpRequest) -> HttpResponse
    duration_content, realm_minutes = user_activity_intervals() # type: Tuple[mark_safe, Dict[str, float]]
    counts_content = realm_summary_table(realm_minutes) # type: str
    data = [
        ('Counts', counts_content),
        ('Durations', duration_content),
    ]
    for page in ad_hoc_queries():
        data.append((page['title'], page['content']))

    title = 'Activity'

    return render_to_response(
        'analytics/activity.html',
        dict(data=data, title=title, is_home=True),
        request=request
    )

def get_user_activity_records_for_realm(realm, is_bot):
    # type: (str, bool) -> QuerySet
    fields = [
        'user_profile__full_name',
        'user_profile__email',
        'query',
        'client__name',
        'count',
        'last_visit',
    ]

    records = UserActivity.objects.filter(
        user_profile__realm__string_id=realm,
        user_profile__is_active=True,
        user_profile__is_bot=is_bot
    )
    records = records.order_by("user_profile__email", "-last_visit")
    records = records.select_related('user_profile', 'client').only(*fields)
    return records

def get_user_activity_records_for_email(email):
    # type: (str) -> List[QuerySet]
    fields = [
        'user_profile__full_name',
        'query',
        'client__name',
        'count',
        'last_visit'
    ]

    records = UserActivity.objects.filter(
        user_profile__email=email
    )
    records = records.order_by("-last_visit")
    records = records.select_related('user_profile', 'client').only(*fields)
    return records

def raw_user_activity_table(records):
    # type: (List[QuerySet]) -> str
    cols = [
        'query',
        'client',
        'count',
        'last_visit'
    ]

    def row(record):
        # type: (QuerySet) -> List[Any]
        return [
            record.query,
            record.client.name,
            record.count,
            format_date_for_activity_reports(record.last_visit)
        ]

    rows = list(map(row, records))
    title = 'Raw Data'
    return make_table(title, cols, rows)

def get_user_activity_summary(records):
    # type: (List[QuerySet]) -> Dict[str, Dict[str, Any]]
    #: `Any` used above should be `Union(int, datetime)`.
    #: However current version of `Union` does not work inside other function.
    #: We could use something like:
    # `Union[Dict[str, Dict[str, int]], Dict[str, Dict[str, datetime]]]`
    #: but that would require this long `Union` to carry on throughout inner functions.
    summary = {} # type: Dict[str, Dict[str, Any]]

    def update(action, record):
        # type: (str, QuerySet) -> None
        if action not in summary:
            summary[action] = dict(
                count=record.count,
                last_visit=record.last_visit
            )
        else:
            summary[action]['count'] += record.count
            summary[action]['last_visit'] = max(
                summary[action]['last_visit'],
                record.last_visit
            )

    if records:
        summary['name'] = records[0].user_profile.full_name

    for record in records:
        client = record.client.name
        query = record.query

        update('use', record)

        if client == 'API':
            m = re.match('/api/.*/external/(.*)', query)
            if m:
                client = m.group(1)
                update(client, record)

        if client.startswith('desktop'):
            update('desktop', record)
        if client == 'website':
            update('website', record)
        if ('send_message' in query) or re.search('/api/.*/external/.*', query):
            update('send', record)
        if query in ['/json/update_pointer', '/json/users/me/pointer', '/api/v1/update_pointer']:
            update('pointer', record)
        update(client, record)

    return summary

def format_date_for_activity_reports(date):
    # type: (Optional[datetime]) -> str
    if date:
        return date.astimezone(eastern_tz).strftime('%Y-%m-%d %H:%M')
    else:
        return ''

def user_activity_link(email):
    # type: (str) -> mark_safe
    url_name = 'analytics.views.get_user_activity'
    url = urlresolvers.reverse(url_name, kwargs=dict(email=email))
    email_link = '<a href="%s">%s</a>' % (url, email)
    return mark_safe(email_link)

def realm_activity_link(realm_str):
    # type: (str) -> mark_safe
    url_name = 'analytics.views.get_realm_activity'
    url = urlresolvers.reverse(url_name, kwargs=dict(realm_str=realm_str))
    realm_link = '<a href="%s">%s</a>' % (url, realm_str)
    return mark_safe(realm_link)

def realm_client_table(user_summaries):
    # type: (Dict[str, Dict[str, Dict[str, Any]]]) -> str
    exclude_keys = [
        'internal',
        'name',
        'use',
        'send',
        'pointer',
        'website',
        'desktop',
    ]

    rows = []
    for email, user_summary in user_summaries.items():
        email_link = user_activity_link(email)
        name = user_summary['name']
        for k, v in user_summary.items():
            if k in exclude_keys:
                continue
            client = k
            count = v['count']
            last_visit = v['last_visit']
            row = [
                format_date_for_activity_reports(last_visit),
                client,
                name,
                email_link,
                count,
            ]
            rows.append(row)

    rows = sorted(rows, key=lambda r: r[0], reverse=True)

    cols = [
        'Last visit',
        'Client',
        'Name',
        'Email',
        'Count',
    ]

    title = 'Clients'

    return make_table(title, cols, rows)

def user_activity_summary_table(user_summary):
    # type: (Dict[str, Dict[str, Any]]) -> str
    rows = []
    for k, v in user_summary.items():
        if k == 'name':
            continue
        client = k
        count = v['count']
        last_visit = v['last_visit']
        row = [
            format_date_for_activity_reports(last_visit),
            client,
            count,
        ]
        rows.append(row)

    rows = sorted(rows, key=lambda r: r[0], reverse=True)

    cols = [
        'last_visit',
        'client',
        'count',
    ]

    title = 'User Activity'
    return make_table(title, cols, rows)

def realm_user_summary_table(all_records, admin_emails):
    # type: (List[QuerySet], Set[Text]) -> Tuple[Dict[str, Dict[str, Any]], str]
    user_records = {}

    def by_email(record):
        # type: (QuerySet) -> str
        return record.user_profile.email

    for email, records in itertools.groupby(all_records, by_email):
        user_records[email] = get_user_activity_summary(list(records))

    def get_last_visit(user_summary, k):
        # type: (Dict[str, Dict[str, datetime]], str) -> Optional[datetime]
        if k in user_summary:
            return user_summary[k]['last_visit']
        else:
            return None

    def get_count(user_summary, k):
        # type: (Dict[str, Dict[str, str]], str) -> str
        if k in user_summary:
            return user_summary[k]['count']
        else:
            return ''

    def is_recent(val):
        # type: (Optional[datetime]) -> bool
        age = timezone.now() - val
        return age.total_seconds() < 5 * 60

    rows = []
    for email, user_summary in user_records.items():
        email_link = user_activity_link(email)
        sent_count = get_count(user_summary, 'send')
        cells = [user_summary['name'], email_link, sent_count]
        row_class = ''
        for field in ['use', 'send', 'pointer', 'desktop', 'ZulipiOS', 'Android']:
            visit = get_last_visit(user_summary, field)
            if field == 'use':
                if visit and is_recent(visit):
                    row_class += ' recently_active'
                if email in admin_emails:
                    row_class += ' admin'
            val = format_date_for_activity_reports(visit)
            cells.append(val)
        row = dict(cells=cells, row_class=row_class)
        rows.append(row)

    def by_used_time(row):
        # type: (Dict[str, Any]) -> str
        return row['cells'][3]

    rows = sorted(rows, key=by_used_time, reverse=True)

    cols = [
        'Name',
        'Email',
        'Total sent',
        'Heard from',
        'Message sent',
        'Pointer motion',
        'Desktop',
        'ZulipiOS',
        'Android',
    ]

    title = 'Summary'

    content = make_table(title, cols, rows, has_row_class=True)
    return user_records, content

@zulip_internal
def get_realm_activity(request, realm_str):
    # type: (HttpRequest, str) -> HttpResponse
    data = [] # type: List[Tuple[str, str]]
    all_user_records = {} # type: Dict[str, Any]

    try:
        admins = Realm.objects.get(string_id=realm_str).get_admin_users()
    except Realm.DoesNotExist:
        return HttpResponseNotFound("Realm %s does not exist" % (realm_str,))

    admin_emails = {admin.email for admin in admins}

    for is_bot, page_title in [(False, 'Humans'), (True, 'Bots')]:
        all_records = list(get_user_activity_records_for_realm(realm_str, is_bot))

        user_records, content = realm_user_summary_table(all_records, admin_emails)
        all_user_records.update(user_records)

        data += [(page_title, content)]

    page_title = 'Clients'
    content = realm_client_table(all_user_records)
    data += [(page_title, content)]

    page_title = 'History'
    content = sent_messages_report(realm_str)
    data += [(page_title, content)]

    realm_link = 'https://stats1.zulip.net:444/render/?from=-7days'
    realm_link += '&target=stats.gauges.staging.users.active.%s.0_16hr' % (realm_str,)

    title = realm_str
    return render_to_response(
        'analytics/activity.html',
        dict(data=data, realm_link=realm_link, title=title),
        request=request
    )

@zulip_internal
def get_user_activity(request, email):
    # type: (HttpRequest, str) -> HttpResponse
    records = get_user_activity_records_for_email(email)

    data = [] # type: List[Tuple[str, str]]
    user_summary = get_user_activity_summary(records)
    content = user_activity_summary_table(user_summary)

    data += [('Summary', content)]

    content = raw_user_activity_table(records)
    data += [('Info', content)]

    title = email
    return render_to_response(
        'analytics/activity.html',
        dict(data=data, title=title),
        request=request
    )
