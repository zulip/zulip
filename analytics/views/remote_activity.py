from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from psycopg2.sql import SQL

from analytics.views.activity_common import (
    fix_rows,
    format_date_for_activity_reports,
    get_query_data,
    make_table,
    remote_installation_stats_link,
    remote_installation_support_link,
)
from zerver.decorator import require_server_admin


@require_server_admin
def get_remote_server_activity(request: HttpRequest) -> HttpResponse:
    title = "Remote servers"

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
        mobile_push_forwarded_count as (
            select
                server_id,
                sum(coalesce(value, 0)) as push_forwarded_count
            from zilencer_remoteinstallationcount
            where
                property = 'mobile_pushes_forwarded::day'
                and end_time >= current_timestamp(0) - interval '7 days'
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
            rserver.last_version,
            max_value,
            push_user_count,
            max_end_time,
            push_forwarded_count
        from zilencer_remotezulipserver rserver
        left join icount on icount.server_id = rserver.id
        left join mobile_push_forwarded_count on mobile_push_forwarded_count.server_id = rserver.id
        left join remote_push_devices on remote_push_devices.server_id = rserver.id
        order by max_value DESC NULLS LAST, push_user_count DESC NULLS LAST
    """
    )

    cols = [
        "ID",
        "Hostname",
        "Contact email",
        "Zulip version",
        "Analytics users",
        "Mobile users",
        "Last update time",
        "7 day count of mobile pushes forwarded (includes today's current count)",
        "Analytics",
        "Support",
    ]

    rows = get_query_data(query)
    total_row = []
    totals_columns = [4, 5]
    for row in rows:
        stats = remote_installation_stats_link(row[0])
        row.append(stats)
    for i, col in enumerate(cols):
        if col == "Last update time":
            fix_rows(rows, i, format_date_for_activity_reports)
        if col == "Hostname":
            for row in rows:
                support = remote_installation_support_link(row[i])
                row.append(support)
        if i == 0:
            total_row.append("Total")
        elif i in totals_columns:
            total_row.append(str(sum(row[i] for row in rows if row[i] is not None)))
        else:
            total_row.append("")
    rows.insert(0, total_row)

    content = make_table(title, cols, rows)
    return render(
        request,
        "analytics/activity_details_template.html",
        context=dict(data=content, title=title, is_home=False),
    )
