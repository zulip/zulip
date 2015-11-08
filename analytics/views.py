from __future__ import absolute_import
from django.db import connection
from django.template import RequestContext, loader
from django.utils.html import mark_safe
from django.shortcuts import render_to_response
from django.core import urlresolvers
from django.http import HttpResponseNotFound

from zerver.decorator import has_request_variables, REQ, zulip_internal
from zerver.models import get_realm, UserActivity, UserActivityInterval, Realm
from zerver.lib.timestamp import timestamp_to_datetime

from collections import defaultdict
from datetime import datetime, timedelta
import itertools
import time
import re
import pytz
from six.moves import filter
from six.moves import map
from six.moves import range
from six.moves import zip
eastern_tz = pytz.timezone('US/Eastern')

def make_table(title, cols, rows, has_row_class=False):

    if not has_row_class:
        def fix_row(row):
            return dict(cells=row, row_class=None)
        rows = list(map(fix_row, rows))

    data = dict(title=title, cols=cols, rows=rows)

    content = loader.render_to_string(
        'analytics/ad_hoc_query.html',
        dict(data=data)
    )

    return content

def dictfetchall(cursor):
    "Returns all rows from a cursor as a dict"
    desc = cursor.description
    return [
        dict(list(zip([col[0] for col in desc], row)))
        for row in cursor.fetchall()
    ]


def get_realm_day_counts():
    query = '''
        select
            r.domain,
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
            r.domain,
            age
        order by
            r.domain,
            age
    '''
    cursor = connection.cursor()
    cursor.execute(query)
    rows = dictfetchall(cursor)
    cursor.close()

    counts = defaultdict(dict)
    for row in rows:
        counts[row['domain']][row['age']] = row['cnt']


    result = {}
    for domain in counts:
        cnts = [counts[domain].get(age, 0) for age in range(8)]
        min_cnt = min(cnts)
        max_cnt = max(cnts)

        def format_count(cnt):
            if cnt == min_cnt:
                good_bad = 'bad'
            elif cnt == max_cnt:
                good_bad = 'good'
            else:
                good_bad = 'neutral'

            return '<td class="number %s">%s</td>' % (good_bad, cnt)

        cnts = ''.join(map(format_count, cnts))
        result[domain] = dict(cnts=cnts)

    return result

def realm_summary_table(realm_minutes):
    query = '''
        SELECT
            realm.domain,
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
                        '/json/update_pointer'
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
                            '/json/update_pointer'
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
                        '/json/update_pointer'
                    )
                AND
                    up.realm_id = realm.id
                AND
                    last_visit > now() - interval '2 week'
        )
        ORDER BY active_user_count DESC, domain ASC
        '''

    cursor = connection.cursor()
    cursor.execute(query)
    rows = dictfetchall(cursor)
    cursor.close()

    # get messages sent per day
    counts = get_realm_day_counts()
    for row in rows:
        try:
            row['history'] = counts[row['domain']]['cnts']
        except:
            row['history'] = ''

    # augment data with realm_minutes
    total_hours = 0
    for row in rows:
        domain = row['domain']
        minutes = realm_minutes.get(domain, 0)
        hours = minutes / 60.0
        total_hours += hours
        row['hours'] = str(int(hours))
        try:
            row['hours_per_user'] = '%.1f' % (hours / row['active_user_count'],)
        except:
            pass

    # formatting
    for row in rows:
        row['domain'] = realm_activity_link(row['domain'])

    # Count active sites
    def meets_goal(row):
        return row['active_user_count'] >= 5

    num_active_sites = len(list(filter(meets_goal, rows)))

    # create totals
    total_active_user_count = 0
    total_user_profile_count = 0
    total_bot_count = 0
    for row in rows:
        total_active_user_count += int(row['active_user_count'])
        total_user_profile_count += int(row['user_profile_count'])
        total_bot_count += int(row['bot_count'])


    rows.append(dict(
        domain='Total',
        active_user_count=total_active_user_count,
        user_profile_count=total_user_profile_count,
        bot_count=total_bot_count,
        hours=int(total_hours)
    ))

    content = loader.render_to_string(
        'analytics/realm_summary_table.html',
        dict(rows=rows, num_active_sites=num_active_sites)
    )
    return content


def user_activity_intervals():
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
        'user_profile__realm__domain'
    ).order_by(
        'user_profile__realm__domain',
        'user_profile__email'
    )

    by_domain = lambda row: row.user_profile.realm.domain
    by_email = lambda row: row.user_profile.email

    realm_minutes = {}

    for domain, realm_intervals in itertools.groupby(all_intervals, by_domain):
        realm_duration = timedelta(0)
        output += '<hr>%s\n' % (domain,)
        for email, intervals in itertools.groupby(realm_intervals, by_email):
            duration = timedelta(0)
            for interval in intervals:
                start = max(day_start, interval.start)
                end = min(day_end, interval.end)
                duration += end - start

            total_duration += duration
            realm_duration += duration
            output += "  %-*s%s\n" % (37, email, duration, )

        realm_minutes[domain] = realm_duration.total_seconds() / 60

    output += "\nTotal Duration:                      %s\n" % (total_duration,)
    output += "\nTotal Duration in minutes:           %s\n" % (total_duration.total_seconds() / 60.,)
    output += "Total Duration amortized to a month: %s" % (total_duration.total_seconds() * 30. / 60.,)
    content = mark_safe('<pre>' + output + '</pre>')
    return content, realm_minutes

def sent_messages_report(realm):
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
                r.domain = %s
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
                r.domain = %s
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
    def get_page(query, cols, title):
        cursor = connection.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        rows = list(map(list, rows))
        cursor.close()

        def fix_rows(i, fixup_func):
            for row in rows:
                row[i] = fixup_func(row[i])

        for i, col in enumerate(cols):
            if col == 'Domain':
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
                realm.domain,
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
            group by domain, up.id, client.name
            having max(last_visit) > now() - interval '2 week'
            order by domain, up.id, client.name
        ''' % (mobile_type,)

        cols = [
            'Domain',
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
            realm.domain,
            client.name,
            sum(count) as hits,
            max(last_visit) as last_time
        from zerver_useractivity ua
        join zerver_client client on client.id = ua.client_id
        join zerver_userprofile up on up.id = ua.user_profile_id
        join zerver_realm realm on realm.id = up.realm_id
        where
            client.name like 'desktop%%'
        group by domain, client.name
        having max(last_visit) > now() - interval '2 week'
        order by domain, client.name
    '''

    cols = [
        'Domain',
        'Client',
        'Hits',
        'Last time'
    ]

    pages.append(get_page(query, cols, title))

    ###

    title = 'Integrations by domain'

    query = '''
        select
            realm.domain,
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
        group by domain, client_name
        having max(last_visit) > now() - interval '2 week'
        order by domain, client_name
    '''

    cols = [
        'Domain',
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
            realm.domain,
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
        group by client_name, domain
        having max(last_visit) > now() - interval '2 week'
        order by client_name, domain
    '''

    cols = [
        'Client',
        'Domain',
        'Hits',
        'Last time'
    ]

    pages.append(get_page(query, cols, title))

    return pages

@zulip_internal
@has_request_variables
def get_activity(request):
    duration_content, realm_minutes = user_activity_intervals()
    counts_content = realm_summary_table(realm_minutes)
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
        context_instance=RequestContext(request)
    )

def get_user_activity_records_for_realm(realm, is_bot):
    fields = [
        'user_profile__full_name',
        'user_profile__email',
        'query',
        'client__name',
        'count',
        'last_visit',
    ]

    records = UserActivity.objects.filter(
            user_profile__realm__domain=realm,
            user_profile__is_active=True,
            user_profile__is_bot=is_bot
    )
    records = records.order_by("user_profile__email", "-last_visit")
    records = records.select_related('user_profile', 'client').only(*fields)
    return records

def get_user_activity_records_for_email(email):
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
    cols = [
        'query',
        'client',
        'count',
        'last_visit'
    ]

    def row(record):
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
    summary = {}
    def update(action, record):
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
        if query in ['/json/update_pointer', '/api/v1/update_pointer']:
            update('pointer', record)
        update(client, record)


    return summary

def format_date_for_activity_reports(date):
    if date:
        return date.astimezone(eastern_tz).strftime('%Y-%m-%d %H:%M')
    else:
        return ''

def user_activity_link(email):
    url_name = 'analytics.views.get_user_activity'
    url = urlresolvers.reverse(url_name, kwargs=dict(email=email))
    email_link = '<a href="%s">%s</a>' % (url, email)
    return mark_safe(email_link)

def realm_activity_link(realm):
    url_name = 'analytics.views.get_realm_activity'
    url = urlresolvers.reverse(url_name, kwargs=dict(realm=realm))
    realm_link = '<a href="%s">%s</a>' % (url, realm)
    return mark_safe(realm_link)

def realm_client_table(user_summaries):
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
    user_records = {}

    def by_email(record):
        return record.user_profile.email

    for email, records in itertools.groupby(all_records, by_email):
        user_records[email] = get_user_activity_summary(list(records))

    def get_last_visit(user_summary, k):
        if k in user_summary:
            return user_summary[k]['last_visit']
        else:
            return None

    def get_count(user_summary, k):
        if k in user_summary:
            return user_summary[k]['count']
        else:
            return ''

    def is_recent(val):
        age = datetime.now(val.tzinfo) - val
        return age.total_seconds() < 5 * 60

    rows = []
    for email, user_summary in user_records.items():
        email_link = user_activity_link(email)
        sent_count = get_count(user_summary, 'send')
        cells = [user_summary['name'], email_link, sent_count]
        row_class = ''
        for field in ['use', 'send', 'pointer', 'desktop', 'ZulipiOS', 'Android']:
            val = get_last_visit(user_summary, field)
            if field == 'use':
                if val and is_recent(val):
                    row_class += ' recently_active'
                if email in admin_emails:
                    row_class += ' admin'
            val = format_date_for_activity_reports(val)
            cells.append(val)
        row = dict(cells=cells, row_class=row_class)
        rows.append(row)

    def by_used_time(row):
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
            'Android'
    ]

    title = 'Summary'

    content = make_table(title, cols, rows, has_row_class=True)
    return user_records, content

@zulip_internal
def get_realm_activity(request, realm):
    data = []
    all_records = {}
    all_user_records = {}

    try:
        admins = get_realm(realm).get_admin_users()
    except Realm.DoesNotExist:
        return HttpResponseNotFound("Realm %s does not exist" % (realm,))

    admin_emails = {admin.email for admin in admins}

    for is_bot, page_title in [(False,  'Humans'), (True, 'Bots')]:
        all_records = get_user_activity_records_for_realm(realm, is_bot)
        all_records = list(all_records)

        user_records, content = realm_user_summary_table(all_records, admin_emails)
        all_user_records.update(user_records)

        data += [(page_title, content)]

    page_title = 'Clients'
    content = realm_client_table(all_user_records)
    data += [(page_title, content)]


    page_title = 'History'
    content = sent_messages_report(realm)
    data += [(page_title, content)]

    fix_name = lambda realm: realm.replace('.', '_')

    realm_link = 'https://stats1.zulip.net:444/render/?from=-7days'
    realm_link += '&target=stats.gauges.staging.users.active.%s.0_16hr' % (fix_name(realm),)

    title = realm
    return render_to_response(
        'analytics/activity.html',
        dict(data=data, realm_link=realm_link, title=title),
        context_instance=RequestContext(request)
    )

@zulip_internal
def get_user_activity(request, email):
    records = get_user_activity_records_for_email(email)

    data = []
    user_summary = get_user_activity_summary(records)
    content = user_activity_summary_table(user_summary)

    data += [('Summary', content)]

    content = raw_user_activity_table(records)
    data += [('Info', content)]

    title = email
    return render_to_response(
        'analytics/activity.html',
        dict(data=data, title=title),
        context_instance=RequestContext(request)
    )
