from collections import defaultdict
from typing import Dict, Optional

from django.conf import settings
from django.db import connection
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.template import loader
from django.utils.timezone import now as timezone_now
from markupsafe import Markup
from psycopg2.sql import SQL

from analytics.lib.counts import COUNT_STATS
from corporate.lib.activity import (
    dictfetchall,
    estimate_annual_recurring_revenue_by_realm,
    fix_rows,
    format_datetime_as_date,
    format_optional_datetime,
    get_query_data,
    get_realms_with_default_discount_dict,
    make_table,
    realm_activity_link,
    realm_stats_link,
    realm_support_link,
    realm_url_link,
)
from corporate.lib.stripe import cents_to_dollar_string
from corporate.views.support import get_plan_type_string
from zerver.decorator import require_server_admin
from zerver.lib.request import has_request_variables
from zerver.models import Realm
from zerver.models.realm_audit_logs import RealmAuditLog
from zerver.models.realms import get_org_type_display_name


def get_realm_day_counts() -> Dict[str, Dict[str, Markup]]:
    # To align with UTC days, we subtract an hour from end_time to
    # get the start_time, since the hour that starts at midnight was
    # on the previous day.
    query = SQL(
        """
        select
            r.string_id,
            (now()::date - (end_time - interval '1 hour')::date) age,
            coalesce(sum(value), 0) cnt
        from zerver_realm r
        join analytics_realmcount rc on r.id = rc.realm_id
        where
            property = 'messages_sent:is_bot:hour'
        and
            subgroup = 'false'
        and
            end_time > now()::date - interval '8 day' - interval '1 hour'
        group by
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


def realm_summary_table() -> str:
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
            coalesce(bot_count_table.value, 0) bot_count,
            coalesce(realm_audit_log_table.how_realm_creator_found_zulip, '') how_realm_creator_found_zulip
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
            LEFT OUTER JOIN (
                SELECT
                    extra_data->>'how_realm_creator_found_zulip' as how_realm_creator_found_zulip,
                    realm_id
                from
                    zerver_realmauditlog
                WHERE
                    event_type = %(realm_creation_event_type)s
            ) as realm_audit_log_table ON realm.id = realm_audit_log_table.realm_id
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
            "realm_creation_event_type": RealmAuditLog.REALM_CREATED,
        },
    )
    rows = dictfetchall(cursor)
    cursor.close()

    for row in rows:
        row["date_created_day"] = format_datetime_as_date(row["date_created"])
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
        realms_with_default_discount = get_realms_with_default_discount_dict()

        for row in rows:
            row["plan_type_string"] = get_plan_type_string(row["plan_type"])

            string_id = row["string_id"]

            if string_id in estimated_arrs:
                row["arr"] = f"${cents_to_dollar_string(estimated_arrs[string_id])}"

            if row["plan_type"] in [Realm.PLAN_TYPE_STANDARD, Realm.PLAN_TYPE_PLUS]:
                row["effective_rate"] = 100 - int(realms_with_default_discount.get(string_id, 0))
            elif row["plan_type"] == Realm.PLAN_TYPE_STANDARD_FREE:
                row["effective_rate"] = 0
            elif (
                row["plan_type"] == Realm.PLAN_TYPE_LIMITED
                and string_id in realms_with_default_discount
            ):
                row["effective_rate"] = 100 - int(realms_with_default_discount[string_id])
            else:
                row["effective_rate"] = ""

        total_arr += sum(estimated_arrs.values())

    for row in rows:
        row["org_type_string"] = get_org_type_display_name(row["org_type"])

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

    total_row = [
        "Total",
        "",
        "",
        "",
        f"${cents_to_dollar_string(total_arr)}",
        "",
        "",
        "",
        total_dau_count,
        total_wau_count,
        total_user_profile_count,
        total_bot_count,
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
    ]

    content = loader.render_to_string(
        "corporate/activity/installation_activity_table.html",
        dict(
            rows=rows,
            totals=total_row,
            num_active_sites=num_active_sites,
            utctime=now.strftime("%Y-%m-%d %H:%M %Z"),
            billing_enabled=settings.BILLING_ENABLED,
        ),
    )
    return content


@require_server_admin
@has_request_variables
def get_installation_activity(request: HttpRequest) -> HttpResponse:
    content: str = realm_summary_table()
    title = "Installation activity"

    return render(
        request,
        "corporate/activity/activity.html",
        context=dict(data=content, title=title, is_home=True),
    )


@require_server_admin
def get_integrations_activity(request: HttpRequest) -> HttpResponse:
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
        "Last time (UTC)",
    ]

    rows = get_query_data(query)
    for i, col in enumerate(cols):
        if col == "Realm":
            fix_rows(rows, i, realm_activity_link)
        elif col == "Last time (UTC)":
            fix_rows(rows, i, format_optional_datetime)

    content = make_table(title, cols, rows)
    return render(
        request,
        "corporate/activity/activity.html",
        context=dict(
            data=content,
            title=title,
            is_home=False,
        ),
    )
