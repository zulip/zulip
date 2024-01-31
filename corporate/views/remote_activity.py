from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from psycopg2.sql import SQL

from corporate.lib.activity import (
    fix_rows,
    format_date_for_activity_reports,
    format_none_as_zero,
    get_plan_data_by_remote_realm,
    get_plan_data_by_remote_server,
    get_query_data,
    get_remote_realm_user_counts,
    get_remote_server_audit_logs,
    make_table,
    remote_installation_stats_link,
    remote_installation_support_link,
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
                org_type as realm_type,
                host as realm_host
            from zilencer_remoterealm
            where
                is_system_bot_realm = False
                and realm_deactivated = False
            group by server_id, id, name, org_type
        )
        select
            rserver.id,
            realm_id,
            realm_name,
            rserver.hostname,
            realm_host,
            rserver.contact_email,
            rserver.last_version,
            rserver.last_audit_log_update,
            push_user_count,
            push_forwarded_count,
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
        "Links",
        "IDs",
        "Realm name",
        "Realm host or server hostname",
        "Server contact email",
        "Server Zulip version",
        "Server last audit log update",
        "Server mobile users",
        "Server mobile pushes",
        "Realm organization type",
        "Plan name",
        "Plan status",
        "ARR",
        "Rate",
        "Total users",
        "Guest users",
    ]

    # If the query or column order above changes, update the constants below
    SERVER_AND_REALM_IDS = 0
    SERVER_HOST = 2
    REALM_HOST = 3
    LAST_AUDIT_LOG_DATE = 6
    MOBILE_USER_COUNT = 7
    MOBILE_PUSH_COUNT = 8
    ORG_TYPE = 9
    ARR = 12
    TOTAL_USER_COUNT = 14
    GUEST_COUNT = 15

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
        # Create combined IDs column with server and realm IDs
        server_id = row.pop(SERVER_AND_REALM_IDS)
        realm_id = row.pop(SERVER_AND_REALM_IDS)
        if realm_id is not None:
            ids_string = f"{server_id}/{realm_id}"
        else:
            ids_string = f"{server_id}"
        row.insert(SERVER_AND_REALM_IDS, ids_string)

        # Get server_host for support link
        # For remote realm row, remove server hostname value;
        # for remote server row, remove None realm host value
        if realm_id is not None:
            server_host = row.pop(SERVER_HOST)
        else:
            row.pop(REALM_HOST)
            server_host = row[SERVER_HOST]

        # Add server links
        stats = remote_installation_stats_link(server_id)
        support = remote_installation_support_link(server_host)
        links = stats + " " + support
        row.insert(0, links)

        # Count mobile users and pushes forwarded, once per server
        if server_id not in remote_server_mobile_data_counted:
            if row[MOBILE_USER_COUNT] is not None:
                total_mobile_users += row[MOBILE_USER_COUNT]  # nocoverage
            if row[MOBILE_PUSH_COUNT] is not None:
                total_pushes += row[MOBILE_PUSH_COUNT]  # nocoverage
            remote_server_mobile_data_counted.add(server_id)

        # Get plan, revenue and user count data for row
        if realm_id is None:
            plan_data = plan_data_by_remote_server.get(server_id)
            audit_log_list = audit_logs_by_remote_server.get(server_id)
            if audit_log_list is None:
                user_counts = None  # nocoverage
            else:
                user_counts = get_remote_customer_user_count(audit_log_list)
        else:
            server_remote_realms_data = plan_data_by_remote_server_and_realm.get(server_id)
            if server_remote_realms_data is not None:
                plan_data = server_remote_realms_data.get(realm_id)
            else:
                plan_data = None  # nocoverage
            user_counts = remote_realm_user_counts.get(realm_id)
            # Format organization type for realm
            org_type = row[ORG_TYPE]
            row[ORG_TYPE] = get_org_type_display_name(org_type)

        # Add estimated annual revenue and plan data
        if plan_data is None:
            row.append("---")
            row.append("---")
            row.append("---")
            row.append("---")
        else:
            total_revenue += plan_data.annual_revenue
            revenue = cents_to_dollar_string(plan_data.annual_revenue)
            row.append(plan_data.current_plan_name)
            row.append(plan_data.current_status)
            row.append(f"${revenue}")
            row.append(plan_data.rate)

        # Add user counts
        if user_counts is None:
            row.append(0)
            row.append(0)
        else:
            total_users = user_counts.non_guest_user_count + user_counts.guest_user_count
            row.append(total_users)
            row.append(user_counts.guest_user_count)

    # Format column data and add total row
    for i, col in enumerate(cols):
        if i == LAST_AUDIT_LOG_DATE:
            fix_rows(rows, i, format_date_for_activity_reports)
        if i in [MOBILE_USER_COUNT, MOBILE_PUSH_COUNT]:
            fix_rows(rows, i, format_none_as_zero)
        if i == SERVER_AND_REALM_IDS:
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

    content = make_table(title, cols, rows, totals=total_row)
    return render(
        request,
        "corporate/activity/activity.html",
        context=dict(data=content, title=title, is_home=False),
    )
