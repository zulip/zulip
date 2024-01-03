from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from psycopg2.sql import SQL

from analytics.views.activity_common import (
    fix_rows,
    format_date_for_activity_reports,
    format_none_as_zero,
    get_query_data,
    make_table,
    remote_installation_stats_link,
    remote_installation_support_link,
)
from corporate.lib.analytics import get_plan_data_by_remote_server
from corporate.lib.stripe import cents_to_dollar_string
from zerver.decorator import require_server_admin
from zilencer.models import get_remote_server_guest_and_non_guest_count


@require_server_admin
def get_remote_server_activity(request: HttpRequest) -> HttpResponse:
    title = "Remote servers"

    query = SQL(
        """
        with icount_id as (
            select
                server_id,
                max(id) as max_count_id
            from zilencer_remoteinstallationcount
            where
                property='active_users:is_bot:day'
                and subgroup='false'
            group by server_id
        ),
        icount as (
            select
                icount_id.server_id,
                value as latest_value,
                end_time as latest_end_time
            from icount_id
            join zilencer_remoteinstallationcount
            on max_count_id = zilencer_remoteinstallationcount.id
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
            select
                server_id,
                count(distinct(user_id, user_uuid)) as push_user_count
            from zilencer_remotepushdevicetoken
            group by server_id
        )
        select
            rserver.id,
            rserver.hostname,
            rserver.contact_email,
            rserver.last_version,
            latest_value,
            push_user_count,
            latest_end_time,
            push_forwarded_count
        from zilencer_remotezulipserver rserver
        left join icount on icount.server_id = rserver.id
        left join mobile_push_forwarded_count on mobile_push_forwarded_count.server_id = rserver.id
        left join remote_push_devices on remote_push_devices.server_id = rserver.id
        where not deactivated
        order by latest_value DESC NULLS LAST, push_user_count DESC NULLS LAST
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
        "Mobile pushes forwarded",
        "Plan name",
        "Plan status",
        "ARR",
        "Non guest users",
        "Guest users",
        "Links",
    ]

    rows = get_query_data(query)
    total_row = []
    totals_columns = [4, 5]
    plan_data_by_remote_server = get_plan_data_by_remote_server()

    for row in rows:
        # Add estimated revenue for server
        server_plan_data = plan_data_by_remote_server.get(row[0])
        if server_plan_data is None:
            row.append("---")
            row.append("---")
            row.append("---")
        else:
            revenue = cents_to_dollar_string(server_plan_data.annual_revenue)
            row.append(server_plan_data.current_plan_name)
            row.append(server_plan_data.current_status)
            row.append(f"${revenue}")
        # Add user counts
        remote_server_counts = get_remote_server_guest_and_non_guest_count(row[0])
        row.append(remote_server_counts.non_guest_user_count)
        row.append(remote_server_counts.guest_user_count)
        # Add links
        stats = remote_installation_stats_link(row[0])
        support = remote_installation_support_link(row[1])
        links = stats + " " + support
        row.append(links)
    for i, col in enumerate(cols):
        if col == "Last update time":
            fix_rows(rows, i, format_date_for_activity_reports)
        if col in ["Mobile users", "Mobile pushes forwarded"]:
            fix_rows(rows, i, format_none_as_zero)
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
