import itertools
import time
from collections import defaultdict
from contextlib import suppress
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Optional, Sequence, Tuple, Union

from django.conf import settings
from django.db import connection
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.template import loader
from django.utils.timezone import now as timezone_now
from markupsafe import Markup
from psycopg2.sql import SQL, Composable, Literal

from analytics.lib.counts import COUNT_STATS
from analytics.views.activity_common import (
    dictfetchall,
    format_date_for_activity_reports,
    make_table,
    realm_activity_link,
    realm_stats_link,
    realm_support_link,
    realm_url_link,
    remote_installation_stats_link,
)
from analytics.views.support import get_plan_name
from zerver.decorator import require_server_admin
from zerver.lib.request import has_request_variables
from zerver.lib.timestamp import timestamp_to_datetime
from zerver.models import Realm, UserActivityInterval, get_org_type_display_name

if settings.BILLING_ENABLED:
    from corporate.lib.stripe import (
        estimate_annual_recurring_revenue_by_realm,
        get_realms_to_default_discount_dict,
    )


def get_realm_day_counts() -> Dict[str, Dict[str, Markup]]:
    # Uses index: zerver_message_date_sent_3b5b05d8
    query = SQL(
        """
        select
            r.string_id,
            (now()::date - date_sent::date) age,
            count(*) cnt
        from zerver_message m
        join zerver_userprofile up on up.id = m.sender_id
        join zerver_realm r on r.id = up.realm_id
        join zerver_client c on c.id = m.sending_client_id
        where
            (not up.is_bot)
        and
            date_sent > now()::date - interval '8 day'
        and
            c.name not in ('zephyr_mirror', 'ZulipMonitoring')
        group by
            r.string_id,
            age
        order by
            r.string_id,
            age
    """
    )
    cursor = connection.cursor()
    cursor.execute(query)
    rows = dictfetchall(cursor)
    cursor.close()

    counts: Dict[str, Dict[int, int]] = defaultdict(dict)
    for row in rows:
        counts[row["string_id"]][row["age"]] = row["cnt"]

    def format_count(cnt: int, style: Optional[str] = None) -> Markup:
        if style is not None:
            good_bad = style
        elif cnt == min_cnt:
            good_bad = "bad"
        elif cnt == max_cnt:
            good_bad = "good"
        else:
            good_bad = "neutral"

        return Markup('<td class="number {good_bad}">{cnt}</td>').format(good_bad=good_bad, cnt=cnt)

    result = {}
    for string_id in counts:
        raw_cnts = [counts[string_id].get(age, 0) for age in range(8)]
        min_cnt = min(raw_cnts[1:])
        max_cnt = max(raw_cnts[1:])

        cnts = format_count(raw_cnts[0], "neutral") + Markup().join(map(format_count, raw_cnts[1:]))
        result[string_id] = dict(cnts=cnts)

    return result


def realm_summary_table(realm_minutes: Dict[str, float]) -> str:
    now = timezone_now()

    query = SQL(
        """
        SELECT
            realm.string_id,
            realm.date_created,
            realm.plan_type,
            realm.org_type,
            coalesce(wau_table.value, 0) wau_count,
            coalesce(dau_table.value, 0) dau_count,
            coalesce(user_count_table.value, 0) user_profile_count,
            coalesce(bot_count_table.value, 0) bot_count
        FROM
            zerver_realm as realm
            LEFT OUTER JOIN (
                SELECT
                    value _14day_active_humans,
                    realm_id
                from
                    analytics_realmcount
                WHERE
                    property = 'realm_active_humans::day'
                    AND end_time = %(realm_active_humans_end_time)s
            ) as _14day_active_humans_table ON realm.id = _14day_active_humans_table.realm_id
            LEFT OUTER JOIN (
                SELECT
                    value,
                    realm_id
                from
                    analytics_realmcount
                WHERE
                    property = '7day_actives::day'
                    AND end_time = %(seven_day_actives_end_time)s
            ) as wau_table ON realm.id = wau_table.realm_id
            LEFT OUTER JOIN (
                SELECT
                    value,
                    realm_id
                from
                    analytics_realmcount
                WHERE
                    property = '1day_actives::day'
                    AND end_time = %(one_day_actives_end_time)s
            ) as dau_table ON realm.id = dau_table.realm_id
            LEFT OUTER JOIN (
                SELECT
                    value,
                    realm_id
                from
                    analytics_realmcount
                WHERE
                    property = 'active_users_audit:is_bot:day'
                    AND subgroup = 'false'
                    AND end_time = %(active_users_audit_end_time)s
            ) as user_count_table ON realm.id = user_count_table.realm_id
            LEFT OUTER JOIN (
                SELECT
                    value,
                    realm_id
                from
                    analytics_realmcount
                WHERE
                    property = 'active_users_audit:is_bot:day'
                    AND subgroup = 'true'
                    AND end_time = %(active_users_audit_end_time)s
            ) as bot_count_table ON realm.id = bot_count_table.realm_id
        WHERE
            _14day_active_humans IS NOT NULL
            or realm.plan_type = 3
        ORDER BY
            dau_count DESC,
            string_id ASC
    """
    )

    cursor = connection.cursor()
    cursor.execute(
        query,
        {
            "realm_active_humans_end_time": COUNT_STATS[
                "realm_active_humans::day"
            ].last_successful_fill(),
            "seven_day_actives_end_time": COUNT_STATS["7day_actives::day"].last_successful_fill(),
            "one_day_actives_end_time": COUNT_STATS["1day_actives::day"].last_successful_fill(),
            "active_users_audit_end_time": COUNT_STATS[
                "active_users_audit:is_bot:day"
            ].last_successful_fill(),
        },
    )
    rows = dictfetchall(cursor)
    cursor.close()

    for row in rows:
        row["date_created_day"] = row["date_created"].strftime("%Y-%m-%d")
        row["age_days"] = int((now - row["date_created"]).total_seconds() / 86400)
        row["is_new"] = row["age_days"] < 12 * 7

    # get messages sent per day
    counts = get_realm_day_counts()
    for row in rows:
        try:
            row["history"] = counts[row["string_id"]]["cnts"]
        except Exception:
            row["history"] = ""

    # estimate annual subscription revenue
    total_arr = 0
    if settings.BILLING_ENABLED:
        estimated_arrs = estimate_annual_recurring_revenue_by_realm()
        realms_to_default_discount = get_realms_to_default_discount_dict()

        for row in rows:
            row["plan_type_string"] = get_plan_name(row["plan_type"])

            string_id = row["string_id"]

            if string_id in estimated_arrs:
                row["arr"] = estimated_arrs[string_id]

            if row["plan_type"] in [Realm.PLAN_TYPE_STANDARD, Realm.PLAN_TYPE_PLUS]:
                row["effective_rate"] = 100 - int(realms_to_default_discount.get(string_id, 0))
            elif row["plan_type"] == Realm.PLAN_TYPE_STANDARD_FREE:
                row["effective_rate"] = 0
            elif (
                row["plan_type"] == Realm.PLAN_TYPE_LIMITED
                and string_id in realms_to_default_discount
            ):
                row["effective_rate"] = 100 - int(realms_to_default_discount[string_id])
            else:
                row["effective_rate"] = ""

        total_arr += sum(estimated_arrs.values())

    for row in rows:
        row["org_type_string"] = get_org_type_display_name(row["org_type"])

    # augment data with realm_minutes
    total_hours = 0.0
    for row in rows:
        string_id = row["string_id"]
        minutes = realm_minutes.get(string_id, 0.0)
        hours = minutes / 60.0
        total_hours += hours
        row["hours"] = str(int(hours))
        with suppress(Exception):
            row["hours_per_user"] = "{:.1f}".format(hours / row["dau_count"])

    # formatting
    for row in rows:
        row["realm_url"] = realm_url_link(row["string_id"])
        row["stats_link"] = realm_stats_link(row["string_id"])
        row["support_link"] = realm_support_link(row["string_id"])
        row["string_id"] = realm_activity_link(row["string_id"])

    # Count active sites
    num_active_sites = sum(row["dau_count"] >= 5 for row in rows)

    # create totals
    total_dau_count = 0
    total_user_profile_count = 0
    total_bot_count = 0
    total_wau_count = 0
    for row in rows:
        total_dau_count += int(row["dau_count"])
        total_user_profile_count += int(row["user_profile_count"])
        total_bot_count += int(row["bot_count"])
        total_wau_count += int(row["wau_count"])

    total_row = dict(
        string_id="Total",
        plan_type_string="",
        org_type_string="",
        effective_rate="",
        arr=total_arr,
        realm_url="",
        stats_link="",
        support_link="",
        date_created_day="",
        dau_count=total_dau_count,
        user_profile_count=total_user_profile_count,
        bot_count=total_bot_count,
        hours=int(total_hours),
        wau_count=total_wau_count,
    )

    rows.insert(0, total_row)

    content = loader.render_to_string(
        "analytics/realm_summary_table.html",
        dict(
            rows=rows,
            num_active_sites=num_active_sites,
            utctime=now.strftime("%Y-%m-%d %H:%M %Z"),
            billing_enabled=settings.BILLING_ENABLED,
        ),
    )
    return content


def user_activity_intervals() -> Tuple[Markup, Dict[str, float]]:
    day_end = timestamp_to_datetime(time.time())
    day_start = day_end - timedelta(hours=24)

    output = Markup()
    output += "Per-user online duration for the last 24 hours:\n"
    total_duration = timedelta(0)

    all_intervals = (
        UserActivityInterval.objects.filter(
            end__gte=day_start,
            start__lte=day_end,
        )
        .select_related(
            "user_profile",
            "user_profile__realm",
        )
        .only(
            "start",
            "end",
            "user_profile__delivery_email",
            "user_profile__realm__string_id",
        )
        .order_by(
            "user_profile__realm__string_id",
            "user_profile__delivery_email",
        )
    )

    by_string_id = lambda row: row.user_profile.realm.string_id
    by_email = lambda row: row.user_profile.delivery_email

    realm_minutes = {}

    for string_id, realm_intervals in itertools.groupby(all_intervals, by_string_id):
        realm_duration = timedelta(0)
        output += Markup("<hr>") + f"{string_id}\n"
        for email, intervals in itertools.groupby(realm_intervals, by_email):
            duration = timedelta(0)
            for interval in intervals:
                start = max(day_start, interval.start)
                end = min(day_end, interval.end)
                duration += end - start

            total_duration += duration
            realm_duration += duration
            output += f"  {email:<37}{duration}\n"

        realm_minutes[string_id] = realm_duration.total_seconds() / 60

    output += f"\nTotal duration:                      {total_duration}\n"
    output += f"\nTotal duration in minutes:           {total_duration.total_seconds() / 60.}\n"
    output += f"Total duration amortized to a month: {total_duration.total_seconds() * 30. / 60.}"
    content = Markup("<pre>{}</pre>").format(output)
    return content, realm_minutes


def ad_hoc_queries() -> List[Dict[str, str]]:
    def get_page(
        query: Composable, cols: Sequence[str], title: str, totals_columns: Sequence[int] = []
    ) -> Dict[str, str]:
        cursor = connection.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        rows = list(map(list, rows))
        cursor.close()

        def fix_rows(
            i: int, fixup_func: Union[Callable[[str], Markup], Callable[[datetime], str]]
        ) -> None:
            for row in rows:
                row[i] = fixup_func(row[i])

        total_row = []
        for i, col in enumerate(cols):
            if col == "Realm":
                fix_rows(i, realm_activity_link)
            elif col in ["Last time", "Last visit"]:
                fix_rows(i, format_date_for_activity_reports)
            elif col == "Hostname":
                for row in rows:
                    row[i] = remote_installation_stats_link(row[0], row[i])
            if len(totals_columns) > 0:
                if i == 0:
                    total_row.append("Total")
                elif i in totals_columns:
                    total_row.append(str(sum(row[i] for row in rows if row[i] is not None)))
                else:
                    total_row.append("")
        if len(totals_columns) > 0:
            rows.insert(0, total_row)

        content = make_table(title, cols, rows)

        return dict(
            content=content,
            title=title,
        )

    pages = []

    ###

    for mobile_type in ["Android", "ZulipiOS"]:
        title = f"{mobile_type} usage"

        query: Composable = SQL(
            """
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
                client.name like {mobile_type}
            group by string_id, up.id, client.name
            having max(last_visit) > now() - interval '2 week'
            order by string_id, up.id, client.name
        """
        ).format(
            mobile_type=Literal(mobile_type),
        )

        cols = [
            "Realm",
            "User id",
            "Name",
            "Hits",
            "Last time",
        ]

        pages.append(get_page(query, cols, title))

    ###

    title = "Desktop users"

    query = SQL(
        """
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
    """
    )

    cols = [
        "Realm",
        "Client",
        "Hits",
        "Last time",
    ]

    pages.append(get_page(query, cols, title))

    ###

    title = "Integrations by realm"

    query = SQL(
        """
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
    """
    )

    cols = [
        "Realm",
        "Client",
        "Hits",
        "Last time",
    ]

    pages.append(get_page(query, cols, title))

    ###

    title = "Integrations by client"

    query = SQL(
        """
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
    """
    )

    cols = [
        "Client",
        "Realm",
        "Hits",
        "Last time",
    ]

    pages.append(get_page(query, cols, title))

    title = "Remote Zulip servers"

    query = SQL(
        """
        with icount as (
            select
                server_id,
                max(value) as max_value,
                max(end_time) as max_end_time
            from zilencer_remoteinstallationcount
            where
                property='active_users:is_bot:day'
                and subgroup='false'
            group by server_id
            ),
        remote_push_devices as (
            select server_id, count(distinct(user_id)) as push_user_count from zilencer_remotepushdevicetoken
            group by server_id
        )
        select
            rserver.id,
            rserver.hostname,
            rserver.contact_email,
            max_value,
            push_user_count,
            max_end_time
        from zilencer_remotezulipserver rserver
        left join icount on icount.server_id = rserver.id
        left join remote_push_devices on remote_push_devices.server_id = rserver.id
        order by max_value DESC NULLS LAST, push_user_count DESC NULLS LAST
    """
    )

    cols = [
        "ID",
        "Hostname",
        "Contact email",
        "Analytics users",
        "Mobile users",
        "Last update time",
    ]

    pages.append(get_page(query, cols, title, totals_columns=[3, 4]))

    return pages


@require_server_admin
@has_request_variables
def get_installation_activity(request: HttpRequest) -> HttpResponse:
    duration_content, realm_minutes = user_activity_intervals()
    counts_content: str = realm_summary_table(realm_minutes)
    data = [
        ("Counts", counts_content),
        ("Durations", duration_content),
        *((page["title"], page["content"]) for page in ad_hoc_queries()),
    ]

    title = "Activity"

    return render(
        request,
        "analytics/activity.html",
        context=dict(data=data, title=title, is_home=True),
    )
