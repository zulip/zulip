from django.db import connection
from django.template import RequestContext, loader
from django.utils.html import mark_safe
from django.shortcuts import render_to_response

from zerver.decorator import has_request_variables, REQ, zulip_internal
from zerver.models import get_realm, UserActivity, UserActivityInterval
from zerver.lib.timestamp import timestamp_to_datetime

import datetime
import itertools
import time

def dictfetchall(cursor):
    "Returns all rows from a cursor as a dict"
    desc = cursor.description
    return [
        dict(zip([col[0] for col in desc], row))
        for row in cursor.fetchall()
    ]

def realm_summary_table(realm_minutes):
    query = '''
        SELECT
            realm.domain,
            coalesce(user_counts.active_user_count, 0) active_user_count,
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
                        '/json/update_pointer'
                    )
                AND
                    last_visit > now() - interval '1 day'
                GROUP BY realm_id
            ) user_counts
            ON user_counts.realm_id = realm.id
        WHERE
            realm.domain not in ('zulip.com', 'customer4.invalid')
        AND EXISTS (
                SELECT *
                FROM zerver_useractivity ua
                JOIN zerver_userprofile up
                    ON up.id = ua.user_profile_id
                WHERE
                    query in (
                        '/json/send_message',
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


    def meets_goal(row):
        # We don't count toward company goals for obvious reasons, and
        # customer4.invalid is essentially a dup for users.customer4.invalid.
        if row['domain'] in ['zulip.com', 'customer4.invalid']:
            return False
        return row['active_user_count'] >= 5

    num_active_sites = len(filter(meets_goal, rows))

    content = loader.render_to_string(
        'analytics/realm_summary_table.html',
        dict(rows=rows, num_active_sites=num_active_sites)
    )
    return dict(content=content)


def user_activity_intervals():
    day_end = timestamp_to_datetime(time.time())
    day_start = day_end - datetime.timedelta(hours=24)

    output = "Per-user online duration for the last 24 hours:\n"
    total_duration = datetime.timedelta(0)

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
        realm_duration = datetime.timedelta(0)
        output += '<hr>%s\n' % (domain,)
        for email, intervals in itertools.groupby(realm_intervals, by_email):
            duration = datetime.timedelta(0)
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
    return dict(content=content), realm_minutes

def sent_messages_report(realm):
    title = 'Recently sent messages for ' + realm

    cols = [
        'Date',
        'Count'
    ]

    query = '''
        select
            series.day::date,
            q.cnt
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
                pub_date > now() - interval '2 week'
            group by
                pub_date::date
            order by
                pub_date::date
        ) q on
            series.day = q.pub_date
    '''
    cursor = connection.cursor()
    cursor.execute(query, [realm])
    rows = cursor.fetchall()
    cursor.close()

    data = dict(
        rows=rows,
        cols=cols,
        title=title
    )

    content = loader.render_to_string(
        'analytics/ad_hoc_query.html',
        dict(data=data)
    )

    return content

def ad_hoc_queries():
    def get_page(query, cols, title):
        cursor = connection.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        cursor.close()

        data = dict(
            rows=rows,
            cols=cols,
            title=title
        )

        content = loader.render_to_string(
            'analytics/ad_hoc_query.html',
            dict(data=data)
        )

        return dict(
            content=content,
            title=title
        )

    pages = []

    ###

    title = 'At risk users'

    query = '''
        select
            realm.domain,
            cast(floor(extract(epoch from age(now(), max(last_visit))) / 3600) as int) as age,
            up.email,
            sum(count) as hits,
            max(last_visit) as last_time
        from zerver_useractivity ua
        join zerver_userprofile up on up.id = ua.user_profile_id
        join zerver_realm realm on realm.id = up.realm_id
        where up.is_active
        and (not up.is_bot)
        and domain not in (
            'users.customer4.invalid',
            'ios_appreview.zulip.com',
            'mit.edu'
        )
        and email not like '%%+%%'
        group by up.email, realm.domain
        having max(last_visit) between
            now() - interval '7 day' and
            now() - interval '1 day'
        order by domain, max(last_visit)
    '''

    cols = [
        'Domain',
        'Hours since activity',
        'Email',
        'Hits',
        'Last visit'
    ]

    pages.append(get_page(query, cols, title))

    ###

    title = 'Android usage'

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
            client.name like 'Android'
        and
            query = 'send_message_backend'
        group by domain, up.id, client.name
        having max(last_visit) > now() - interval '2 week'
        order by domain, up.id, client.name
    '''

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

    title = 'Pure API'

    query = '''
        select
            realm.domain,
            sum(count) as hits,
            max(last_visit) as last_time
        from zerver_useractivity ua
        join zerver_client client on client.id = ua.client_id
        join zerver_userprofile up on up.id = ua.user_profile_id
        join zerver_realm realm on realm.id = up.realm_id
        where
            query = '/api/v1/send_message'
        and
            client.name = 'API'
        and
            domain != 'zulip.com'
        group by domain
        having max(last_visit) > now() - interval '2 week'
        order by domain
    '''

    cols = [
        'Domain',
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
            (query = 'send_message_backend'
            and client.name not in ('Android', 'API', 'API: Python')
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
            (query = 'send_message_backend'
            and client.name not in ('Android', 'API', 'API: Python')
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
def get_activity(request, realm=REQ(default=None)):
    duration_content, realm_minutes = user_activity_intervals()
    counts_content = realm_summary_table(realm_minutes)
    data = [
        ('Counts', counts_content),
        ('Durations', duration_content),
    ]
    for page in ad_hoc_queries():
        data.append((page['title'], page))

    title = 'Activity'

    return render_to_response(
        'analytics/activity.html',
        dict(data=data, realm=realm, title=title, is_home=True),
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

    rows = map(row, records)

    title = 'Raw Data'

    data = dict(
        rows=rows,
        cols=cols,
        title=title
    )

    content = loader.render_to_string(
        'analytics/ad_hoc_query.html',
        dict(data=data)
    )
    return content

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

        if client.startswith('desktop'):
            update('desktop', record)
        if client == 'website':
            update('website', record)
        if 'send_message' in query:
            update('send', record)
        if query in ['/json/update_pointer', '/api/v1/update_pointer']:
            update('pointer', record)
        update(client, record)


    return summary

def format_date_for_activity_reports(date):
    if date:
        return date.strftime('%Y-%m-%d %H:%M')
    else:
        return ''

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
        email_link = '<a href="/user_activity/%s/">%s</a>' % (email, email)
        email_link = mark_safe(email_link)
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

    data = dict(
        rows=rows,
        cols=cols,
        title=title
    )

    content = loader.render_to_string(
        'analytics/ad_hoc_query.html',
        dict(data=data)
    )
    return content

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

    data = dict(
        rows=rows,
        cols=cols,
        title=title
    )

    content = loader.render_to_string(
        'analytics/ad_hoc_query.html',
        dict(data=data)
    )
    return content

def realm_user_summary_table(all_records):
    user_records = {}

    def by_email(record):
        return record.user_profile.email

    for email, records in itertools.groupby(all_records, by_email):
        user_records[email] = get_user_activity_summary(list(records))

    def get_last_visit(user_summary, k):
        if k in user_summary:
            return user_summary[k]['last_visit'].strftime('%Y-%m-%d %H:%M')
        else:
            return ''

    def get_count(user_summary, k):
        if k in user_summary:
            return user_summary[k]['count']
        else:
            return ''

    rows = []
    for email, user_summary in user_records.items():
        email_link = '<a href="/user_activity/%s/">%s</a>' % (email, email)
        email_link = mark_safe(email_link)
        sent_count = get_count(user_summary, 'send')
        row = [user_summary['name'], email_link, sent_count]
        for field in ['use', 'send', 'pointer', 'desktop', 'iPhone', 'Android']:
            val = get_last_visit(user_summary, field)
            row.append(val)
        rows.append(row)

    def by_used_time(row):
        return row[3]

    rows = sorted(rows, key=by_used_time, reverse=True)

    cols = [
            'Name',
            'Email',
            'Total sent',
            'Heard from',
            'Message sent',
            'Pointer motion',
            'Desktop',
            'iPhone',
            'Android'
    ]

    title = 'Summary'

    data = dict(
        rows=rows,
        cols=cols,
        title=title
    )

    content = loader.render_to_string(
        'analytics/ad_hoc_query.html',
        dict(data=data)
    )

    return user_records, content

@zulip_internal
def get_realm_activity(request, realm):
    data = []
    all_records = {}
    all_user_records = {}

    for is_bot, page_title in [(False,  'Humans'), (True, 'Bots')]:
        all_records = get_user_activity_records_for_realm(realm, is_bot)
        all_records = list(all_records)

        user_records, content = realm_user_summary_table(all_records)
        all_user_records.update(user_records)

        user_content = dict(content=content)

        data += [(page_title, user_content)]

    page_title = 'Clients'
    content = realm_client_table(all_user_records)
    data += [(page_title, dict(content=content))]


    page_title = 'History'
    content = sent_messages_report(realm)
    data += [(page_title, dict(content=content))]

    title = realm
    return render_to_response(
        'analytics/activity.html',
        dict(data=data, realm=realm, title=title),
        context_instance=RequestContext(request)
    )

@zulip_internal
def get_user_activity(request, email):
    records = get_user_activity_records_for_email(email)

    data = []
    user_summary = get_user_activity_summary(records)
    content = user_activity_summary_table(user_summary)

    user_content = dict(content=content)
    data += [('Summary', user_content)]

    content = raw_user_activity_table(records)
    user_content = dict(content=content)
    data += [('Info', user_content)]

    realm = None
    title = email
    return render_to_response(
        'analytics/activity.html',
        dict(data=data, realm=realm, title=title),
        context_instance=RequestContext(request)
    )
