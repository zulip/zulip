
import itertools
import json
import logging
import re
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, \
    Optional, Set, Text, Tuple, Type, Union

import pytz
from django.conf import settings
from django.urls import reverse
from django.db import connection
from django.db.models import Sum
from django.db.models.query import QuerySet
from django.http import HttpRequest, HttpResponse, HttpResponseNotFound
from django.shortcuts import render
from django.template import RequestContext, loader
from django.utils.timezone import now as timezone_now, utc as timezone_utc
from django.utils.translation import ugettext as _
from jinja2 import Markup as mark_safe

from analytics.lib.counts import COUNT_STATS, CountStat, process_count_stat
from analytics.lib.time_utils import time_range
from analytics.models import BaseCount, InstallationCount, \
    RealmCount, StreamCount, UserCount, last_successful_fill
from zerver.decorator import require_server_admin, \
    to_non_negative_int, to_utc_datetime, zulip_login_required
from zerver.lib.exceptions import JsonableError
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.timestamp import ceiling_to_day, \
    ceiling_to_hour, convert_to_UTC, timestamp_to_datetime
from zerver.models import Client, get_realm, Realm, \
    UserActivity, UserActivityInterval, UserProfile

@zulip_login_required
def stats(request: HttpRequest) -> HttpResponse:
    return render(request,
                  'analytics/stats.html',
                  context=dict(realm_name = request.user.realm.name))

@has_request_variables
def get_chart_data(request: HttpRequest, user_profile: UserProfile, chart_name: Text=REQ(),
                   min_length: Optional[int]=REQ(converter=to_non_negative_int, default=None),
                   start: Optional[datetime]=REQ(converter=to_utc_datetime, default=None),
                   end: Optional[datetime]=REQ(converter=to_utc_datetime, default=None)) -> HttpResponse:
    if chart_name == 'number_of_humans':
        stat = COUNT_STATS['realm_active_humans::day']
        tables = [RealmCount]
        subgroup_to_label = {None: 'human'}  # type: Dict[Optional[str], str]
        labels_sort_function = None
        include_empty_subgroups = True
    elif chart_name == 'messages_sent_over_time':
        stat = COUNT_STATS['messages_sent:is_bot:hour']
        tables = [RealmCount, UserCount]
        subgroup_to_label = {'false': 'human', 'true': 'bot'}
        labels_sort_function = None
        include_empty_subgroups = True
    elif chart_name == 'messages_sent_by_message_type':
        stat = COUNT_STATS['messages_sent:message_type:day']
        tables = [RealmCount, UserCount]
        subgroup_to_label = {'public_stream': 'Public streams',
                             'private_stream': 'Private streams',
                             'private_message': 'Private messages',
                             'huddle_message': 'Group private messages'}
        labels_sort_function = lambda data: sort_by_totals(data['realm'])
        include_empty_subgroups = True
    elif chart_name == 'messages_sent_by_client':
        stat = COUNT_STATS['messages_sent:client:day']
        tables = [RealmCount, UserCount]
        # Note that the labels are further re-written by client_label_map
        subgroup_to_label = {str(id): name for id, name in Client.objects.values_list('id', 'name')}
        labels_sort_function = sort_client_labels
        include_empty_subgroups = False
    else:
        raise JsonableError(_("Unknown chart name: %s") % (chart_name,))

    # Most likely someone using our API endpoint. The /stats page does not
    # pass a start or end in its requests.
    if start is not None:
        start = convert_to_UTC(start)
    if end is not None:
        end = convert_to_UTC(end)
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
    data = {'end_times': end_times, 'frequency': stat.frequency}
    for table in tables:
        if table == RealmCount:
            data['realm'] = get_time_series_by_subgroup(
                stat, RealmCount, realm.id, end_times, subgroup_to_label, include_empty_subgroups)
        if table == UserCount:
            data['user'] = get_time_series_by_subgroup(
                stat, UserCount, user_profile.id, end_times, subgroup_to_label, include_empty_subgroups)
    if labels_sort_function is not None:
        data['display_order'] = labels_sort_function(data)
    else:
        data['display_order'] = None
    return json_success(data=data)

def sort_by_totals(value_arrays: Dict[str, List[int]]) -> List[str]:
    totals = [(sum(values), label) for label, values in value_arrays.items()]
    totals.sort(reverse=True)
    return [label for total, label in totals]

# For any given user, we want to show a fixed set of clients in the chart,
# regardless of the time aggregation or whether we're looking at realm or
# user data. This fixed set ideally includes the clients most important in
# understanding the realm's traffic and the user's traffic. This function
# tries to rank the clients so that taking the first N elements of the
# sorted list has a reasonable chance of doing so.
def sort_client_labels(data: Dict[str, Dict[str, List[int]]]) -> List[str]:
    realm_order = sort_by_totals(data['realm'])
    user_order = sort_by_totals(data['user'])
    label_sort_values = {}  # type: Dict[str, float]
    for i, label in enumerate(realm_order):
        label_sort_values[label] = i
    for i, label in enumerate(user_order):
        label_sort_values[label] = min(i-.1, label_sort_values.get(label, i))
    return [label for label, sort_value in sorted(label_sort_values.items(),
                                                  key=lambda x: x[1])]

def table_filtered_to_id(table: Type[BaseCount], key_id: int) -> QuerySet:
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

def client_label_map(name: str) -> str:
    if name == "website":
        return "Website"
    if name.startswith("desktop app"):
        return "Old desktop app"
    if name == "ZulipElectron":
        return "Desktop app"
    if name == "ZulipAndroid":
        return "Old Android app"
    if name == "ZulipiOS":
        return "Old iOS app"
    if name == "ZulipMobile":
        return "Mobile app"
    if name in ["ZulipPython", "API: Python"]:
        return "Python API"
    if name.startswith("Zulip") and name.endswith("Webhook"):
        return name[len("Zulip"):-len("Webhook")] + " webhook"
    return name

def rewrite_client_arrays(value_arrays: Dict[str, List[int]]) -> Dict[str, List[int]]:
    mapped_arrays = {}  # type: Dict[str, List[int]]
    for label, array in value_arrays.items():
        mapped_label = client_label_map(label)
        if mapped_label in mapped_arrays:
            for i in range(0, len(array)):
                mapped_arrays[mapped_label][i] += value_arrays[label][i]
        else:
            mapped_arrays[mapped_label] = [value_arrays[label][i] for i in range(0, len(array))]
    return mapped_arrays

def get_time_series_by_subgroup(stat: CountStat,
                                table: Type[BaseCount],
                                key_id: int,
                                end_times: List[datetime],
                                subgroup_to_label: Dict[Optional[str], str],
                                include_empty_subgroups: bool) -> Dict[str, List[int]]:
    queryset = table_filtered_to_id(table, key_id).filter(property=stat.property) \
                                                  .values_list('subgroup', 'end_time', 'value')
    value_dicts = defaultdict(lambda: defaultdict(int))  # type: Dict[Optional[str], Dict[datetime, int]]
    for subgroup, end_time, value in queryset:
        value_dicts[subgroup][end_time] = value
    value_arrays = {}
    for subgroup, label in subgroup_to_label.items():
        if (subgroup in value_dicts) or include_empty_subgroups:
            value_arrays[label] = [value_dicts[subgroup][end_time] for end_time in end_times]

    if stat == COUNT_STATS['messages_sent:client:day']:
        # HACK: We rewrite these arrays to collapse the Client objects
        # with similar names into a single sum, and generally give
        # them better names
        return rewrite_client_arrays(value_arrays)
    return value_arrays


eastern_tz = pytz.timezone('US/Eastern')

def make_table(title: str, cols: List[str], rows: List[Any], has_row_class: bool=False) -> str:

    if not has_row_class:
        def fix_row(row: Any) -> Dict[str, Any]:
            return dict(cells=row, row_class=None)
        rows = list(map(fix_row, rows))

    data = dict(title=title, cols=cols, rows=rows)

    content = loader.render_to_string(
        'analytics/ad_hoc_query.html',
        dict(data=data)
    )

    return content

def dictfetchall(cursor: connection.cursor) -> List[Dict[str, Any]]:
    "Returns all rows from a cursor as a dict"
    desc = cursor.description
    return [
        dict(list(zip([col[0] for col in desc], row)))
        for row in cursor.fetchall()
    ]


def get_realm_day_counts() -> Dict[str, Dict[str, str]]:
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

    counts = defaultdict(dict)  # type: Dict[str, Dict[int, int]]
    for row in rows:
        counts[row['string_id']][row['age']] = row['cnt']

    result = {}
    for string_id in counts:
        raw_cnts = [counts[string_id].get(age, 0) for age in range(8)]
        min_cnt = min(raw_cnts[1:])
        max_cnt = max(raw_cnts[1:])

        def format_count(cnt: int, style: Optional[str]=None) -> str:
            if style is not None:
                good_bad = style
            elif cnt == min_cnt:
                good_bad = 'bad'
            elif cnt == max_cnt:
                good_bad = 'good'
            else:
                good_bad = 'neutral'

            return '<td class="number %s">%s</td>' % (good_bad, cnt)

        cnts = (format_count(raw_cnts[0], 'neutral')
                + ''.join(map(format_count, raw_cnts[1:])))
        result[string_id] = dict(cnts=cnts)

    return result

def realm_summary_table(realm_minutes: Dict[str, float]) -> str:
    now = timezone_now()

    query = '''
        SELECT
            realm.string_id,
            realm.date_created,
            coalesce(user_counts.dau_count, 0) dau_count,
            coalesce(wau_counts.wau_count, 0) wau_count,
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
                    count(distinct(ua.user_profile_id)) dau_count
                FROM zerver_useractivity ua
                JOIN zerver_userprofile up
                    ON up.id = ua.user_profile_id
                WHERE
                    up.is_active
                AND (not up.is_bot)
                AND
                    query in (
                        '/json/send_message',
                        'send_message_backend',
                        '/api/v1/send_message',
                        '/json/update_pointer',
                        '/json/users/me/pointer',
                        'update_pointer_backend'
                    )
                AND
                    last_visit > now() - interval '1 day'
                GROUP BY realm_id
            ) user_counts
            ON user_counts.realm_id = realm.id
        LEFT OUTER JOIN
            (
                SELECT
                    realm_id,
                    count(*) wau_count
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
                            '/json/users/me/pointer',
                            'update_pointer_backend'
                        )
                    GROUP by realm.id, up.email
                    HAVING max(last_visit) > now() - interval '7 day'
                ) as wau_users
                GROUP BY realm_id
            ) wau_counts
            ON wau_counts.realm_id = realm.id
        WHERE EXISTS (
                SELECT *
                FROM zerver_useractivity ua
                JOIN zerver_userprofile up
                    ON up.id = ua.user_profile_id
                WHERE
                    up.realm_id = realm.id
                AND up.is_active
                AND (not up.is_bot)
                AND
                    query in (
                        '/json/send_message',
                        '/api/v1/send_message',
                        'send_message_backend',
                        '/json/update_pointer',
                        '/json/users/me/pointer',
                        'update_pointer_backend'
                    )
                AND
                    last_visit > now() - interval '2 week'
        )
        ORDER BY dau_count DESC, string_id ASC
        '''

    cursor = connection.cursor()
    cursor.execute(query)
    rows = dictfetchall(cursor)
    cursor.close()

    # Fetch all the realm administrator users
    realm_admins = defaultdict(list)  # type: Dict[str, List[str]]
    for up in UserProfile.objects.select_related("realm").filter(
        is_realm_admin=True,
        is_active=True
    ):
        realm_admins[up.realm.string_id].append(up.email)

    for row in rows:
        row['date_created_day'] = row['date_created'].strftime('%Y-%m-%d')
        row['age_days'] = int((now - row['date_created']).total_seconds()
                              / 86400)
        row['is_new'] = row['age_days'] < 12 * 7
        row['realm_admin_email'] = ', '.join(realm_admins[row['string_id']])

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
            row['hours_per_user'] = '%.1f' % (hours / row['dau_count'],)
        except Exception:
            pass

    # formatting
    for row in rows:
        row['string_id'] = realm_activity_link(row['string_id'])

    # Count active sites
    def meets_goal(row: Dict[str, int]) -> bool:
        return row['dau_count'] >= 5

    num_active_sites = len(list(filter(meets_goal, rows)))

    # create totals
    total_dau_count = 0
    total_user_profile_count = 0
    total_bot_count = 0
    total_wau_count = 0
    for row in rows:
        total_dau_count += int(row['dau_count'])
        total_user_profile_count += int(row['user_profile_count'])
        total_bot_count += int(row['bot_count'])
        total_wau_count += int(row['wau_count'])

    rows.append(dict(
        string_id='Total',
        date_created_day='',
        realm_admin_email='',
        dau_count=total_dau_count,
        user_profile_count=total_user_profile_count,
        bot_count=total_bot_count,
        hours=int(total_hours),
        wau_count=total_wau_count,
    ))

    content = loader.render_to_string(
        'analytics/realm_summary_table.html',
        dict(rows=rows, num_active_sites=num_active_sites,
             now=now.strftime('%Y-%m-%dT%H:%M:%SZ'))
    )
    return content


def user_activity_intervals() -> Tuple[mark_safe, Dict[str, float]]:
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

def sent_messages_report(realm: str) -> str:
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

def ad_hoc_queries() -> List[Dict[str, str]]:
    def get_page(query: str, cols: List[str], title: str) -> Dict[str, str]:
        cursor = connection.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        rows = list(map(list, rows))
        cursor.close()

        def fix_rows(i: int,
                     fixup_func: Union[Callable[[Realm], mark_safe], Callable[[datetime], str]]) -> None:
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

@require_server_admin
@has_request_variables
def get_activity(request: HttpRequest) -> HttpResponse:
    duration_content, realm_minutes = user_activity_intervals()  # type: Tuple[mark_safe, Dict[str, float]]
    counts_content = realm_summary_table(realm_minutes)  # type: str
    data = [
        ('Counts', counts_content),
        ('Durations', duration_content),
    ]
    for page in ad_hoc_queries():
        data.append((page['title'], page['content']))

    title = 'Activity'

    return render(
        request,
        'analytics/activity.html',
        context=dict(data=data, title=title, is_home=True),
    )

def get_user_activity_records_for_realm(realm: str, is_bot: bool) -> QuerySet:
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

def get_user_activity_records_for_email(email: str) -> List[QuerySet]:
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

def raw_user_activity_table(records: List[QuerySet]) -> str:
    cols = [
        'query',
        'client',
        'count',
        'last_visit'
    ]

    def row(record: QuerySet) -> List[Any]:
        return [
            record.query,
            record.client.name,
            record.count,
            format_date_for_activity_reports(record.last_visit)
        ]

    rows = list(map(row, records))
    title = 'Raw Data'
    return make_table(title, cols, rows)

def get_user_activity_summary(records: List[QuerySet]) -> Dict[str, Dict[str, Any]]:
    #: `Any` used above should be `Union(int, datetime)`.
    #: However current version of `Union` does not work inside other function.
    #: We could use something like:
    # `Union[Dict[str, Dict[str, int]], Dict[str, Dict[str, datetime]]]`
    #: but that would require this long `Union` to carry on throughout inner functions.
    summary = {}  # type: Dict[str, Dict[str, Any]]

    def update(action: str, record: QuerySet) -> None:
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
        if query in ['/json/update_pointer', '/json/users/me/pointer', '/api/v1/update_pointer',
                     'update_pointer_backend']:
            update('pointer', record)
        update(client, record)

    return summary

def format_date_for_activity_reports(date: Optional[datetime]) -> str:
    if date:
        return date.astimezone(eastern_tz).strftime('%Y-%m-%d %H:%M')
    else:
        return ''

def user_activity_link(email: str) -> mark_safe:
    url_name = 'analytics.views.get_user_activity'
    url = reverse(url_name, kwargs=dict(email=email))
    email_link = '<a href="%s">%s</a>' % (url, email)
    return mark_safe(email_link)

def realm_activity_link(realm_str: str) -> mark_safe:
    url_name = 'analytics.views.get_realm_activity'
    url = reverse(url_name, kwargs=dict(realm_str=realm_str))
    realm_link = '<a href="%s">%s</a>' % (url, realm_str)
    return mark_safe(realm_link)

def realm_client_table(user_summaries: Dict[str, Dict[str, Dict[str, Any]]]) -> str:
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

def user_activity_summary_table(user_summary: Dict[str, Dict[str, Any]]) -> str:
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

def realm_user_summary_table(all_records: List[QuerySet],
                             admin_emails: Set[Text]) -> Tuple[Dict[str, Dict[str, Any]], str]:
    user_records = {}

    def by_email(record: QuerySet) -> str:
        return record.user_profile.email

    for email, records in itertools.groupby(all_records, by_email):
        user_records[email] = get_user_activity_summary(list(records))

    def get_last_visit(user_summary: Dict[str, Dict[str, datetime]], k: str) -> Optional[datetime]:
        if k in user_summary:
            return user_summary[k]['last_visit']
        else:
            return None

    def get_count(user_summary: Dict[str, Dict[str, str]], k: str) -> str:
        if k in user_summary:
            return user_summary[k]['count']
        else:
            return ''

    def is_recent(val: Optional[datetime]) -> bool:
        age = timezone_now() - val
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

    def by_used_time(row: Dict[str, Any]) -> str:
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

@require_server_admin
def get_realm_activity(request: HttpRequest, realm_str: str) -> HttpResponse:
    data = []  # type: List[Tuple[str, str]]
    all_user_records = {}  # type: Dict[str, Any]

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

    title = realm_str
    return render(
        request,
        'analytics/activity.html',
        context=dict(data=data, realm_link=None, title=title),
    )

@require_server_admin
def get_user_activity(request: HttpRequest, email: str) -> HttpResponse:
    records = get_user_activity_records_for_email(email)

    data = []  # type: List[Tuple[str, str]]
    user_summary = get_user_activity_summary(records)
    content = user_activity_summary_table(user_summary)

    data += [('Summary', content)]

    content = raw_user_activity_table(records)
    data += [('Info', content)]

    title = email
    return render(
        request,
        'analytics/activity.html',
        context=dict(data=data, title=title),
    )
