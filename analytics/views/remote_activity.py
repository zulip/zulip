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
from corporate.lib.analytics import (
    get_plan_data_by_remote_realm,
    get_plan_data_by_remote_server,
    get_remote_realm_user_counts,
    get_remote_server_audit_logs,
)
from corporate.lib.stripe import cents_to_dollar_string
from zerver.decorator import require_server_admin
from zerver.models.realms import get_org_type_display_name
from zilencer.models import get_remote_customer_user_count


@require_server_admin
def get_remote_server_activity(request: HttpRequest) -> HttpResponse:
    title = "Remote servers"

    query = SQL(
        """
        with mobile_push_forwarded_count as (
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
        ),
        remote_realms as (
            select
                server_id,
                id as realm_id,
                name as realm_name,
                org_type as realm_type
            from zilencer_remoterealm
            where
                is_system_bot_realm = False
                and realm_deactivated = False
            group by server_id, id, name, org_type
        )
        select
            rserver.id,
            rserver.hostname,
            rserver.contact_email,
            rserver.last_version,
            rserver.last_audit_log_update,
            push_user_count,
            push_forwarded_count,
            realm_id,
            realm_name,
            realm_type
        from zilencer_remotezulipserver rserver
        left join mobile_push_forwarded_count on mobile_push_forwarded_count.server_id = rserver.id
        left join remote_push_devices on remote_push_devices.server_id = rserver.id
        left join remote_realms on remote_realms.server_id = rserver.id
        where not deactivated
        order by push_user_count DESC NULLS LAST
    """
    )

    cols = [
        "Server ID",
        "Server hostname",
        "Server contact email",
        "Server Zulip version",
        "Server last audit log update",
        "Server mobile users",
        "Server mobile pushes",
        "Realm ID",
        "Realm name",
        "Realm organization type",
        "Plan name",
        "Plan status",
        "ARR",
        "Total users",
        "Guest users",
        "Links",
    ]

    # If the column order above changes, update the constants below
    SERVER_ID = 0
    SERVER_HOSTNAME = 1
    LAST_AUDIT_LOG_DATE = 4
    MOBILE_USER_COUNT = 5
    MOBILE_PUSH_COUNT = 6
    REALM_ID = 7
    ORG_TYPE = 9
    ARR = 12
    TOTAL_USER_COUNT = 13
    GUEST_COUNT = 14

    rows = get_query_data(query)
    plan_data_by_remote_server = get_plan_data_by_remote_server()
    plan_data_by_remote_server_and_realm = get_plan_data_by_remote_realm()
    audit_logs_by_remote_server = get_remote_server_audit_logs()
    remote_realm_user_counts = get_remote_realm_user_counts()

    total_row = []
    remote_server_mobile_data_counted = set()
    total_revenue = 0
    total_mobile_users = 0
    total_pushes = 0

    for row in rows:
        # Count mobile users and pushes forwarded, once per server
        if row[SERVER_ID] not in remote_server_mobile_data_counted:
            if row[MOBILE_USER_COUNT] is not None:
                total_mobile_users += row[MOBILE_USER_COUNT]  # nocoverage
            if row[MOBILE_PUSH_COUNT] is not None:
                total_pushes += row[MOBILE_PUSH_COUNT]  # nocoverage
            remote_server_mobile_data_counted.add(row[SERVER_ID])
        if row[REALM_ID] is None:
            plan_data = plan_data_by_remote_server.get(row[SERVER_ID])
            audit_log_list = audit_logs_by_remote_server.get(row[SERVER_ID])
            if audit_log_list is None:
                user_counts = None  # nocoverage
            else:
                user_counts = get_remote_customer_user_count(audit_log_list)
        else:
            server_remote_realms_data = plan_data_by_remote_server_and_realm.get(row[SERVER_ID])
            if server_remote_realms_data is not None:
                plan_data = server_remote_realms_data.get(row[REALM_ID])
            else:
                plan_data = None  # nocoverage
            user_counts = remote_realm_user_counts.get(row[REALM_ID])
            # Format organization type for realm
            org_type = row[ORG_TYPE]
            row[ORG_TYPE] = get_org_type_display_name(org_type)
        # Add estimated annual revenue and plan data
        if plan_data is None:
            row.append("---")
            row.append("---")
            row.append("---")
        else:
            total_revenue += plan_data.annual_revenue
            revenue = cents_to_dollar_string(plan_data.annual_revenue)
            row.append(plan_data.current_plan_name)
            row.append(plan_data.current_status)
            row.append(f"${revenue}")
        # Add user counts
        if user_counts is None:
            row.append(0)
            row.append(0)
        else:
            total_users = user_counts.non_guest_user_count + user_counts.guest_user_count
            row.append(total_users)
            row.append(user_counts.guest_user_count)
        # Add server links
        stats = remote_installation_stats_link(row[SERVER_ID])
        support = remote_installation_support_link(row[SERVER_HOSTNAME])
        links = stats + " " + support
        row.append(links)
    # Format column data and add total row
    for i, col in enumerate(cols):
        if i == LAST_AUDIT_LOG_DATE:
            fix_rows(rows, i, format_date_for_activity_reports)
        if i in [MOBILE_USER_COUNT, MOBILE_PUSH_COUNT]:
            fix_rows(rows, i, format_none_as_zero)
        if i == SERVER_ID:
            total_row.append("Total")
        elif i == MOBILE_USER_COUNT:
            total_row.append(str(total_mobile_users))
        elif i == MOBILE_PUSH_COUNT:
            total_row.append(str(total_pushes))
        elif i == ARR:
            total_revenue_string = f"${cents_to_dollar_string(total_revenue)}"
            total_row.append(total_revenue_string)
        elif i in [TOTAL_USER_COUNT, GUEST_COUNT]:
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
