from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from psycopg2.sql import SQL

from corporate.lib.activity import (
    fix_rows,
    format_datetime_as_date,
    format_none_as_zero,
    format_optional_datetime,
    get_plan_data_by_remote_realm,
    get_plan_data_by_remote_server,
    get_query_data,
    get_remote_realm_user_counts,
    get_remote_server_audit_logs,
    make_table,
    remote_installation_stats_link,
    remote_installation_support_link,
)
from zerver.decorator import require_server_admin
from zerver.models.realms import get_org_type_display_name
from zilencer.models import get_remote_customer_user_count


@require_server_admin
def get_remote_server_activity(request: HttpRequest) -> HttpResponse:
    from corporate.lib.stripe import cents_to_dollar_string

    title = "Remote servers"

    query = SQL(
        """
        with remote_server_push_forwarded_count as (
            select
                server_id,
                sum(coalesce(value, 0)) as server_push_forwarded_count
            from zilencer_remoteinstallationcount
            where
                property = 'mobile_pushes_forwarded::day'
                and end_time >= current_timestamp(0) - interval '7 days'
            group by server_id
        ),
        remote_server_push_devices as (
            select
                server_id,
                count(distinct(user_id, user_uuid)) as server_push_user_count
            from zilencer_remotepushdevicetoken
            group by server_id
        ),
        remote_server_audit_log as (
            select
                server_id,
                event_time as server_created
            from zilencer_remotezulipserverauditlog
            where
                event_type = 10215
            group by server_id, event_time
        ),
        remote_realms as (
            select
                server_id,
                id as realm_id,
                name as realm_name,
                org_type as realm_type,
                host as realm_host,
                realm_date_created as realm_created
            from zilencer_remoterealm
            where
                is_system_bot_realm = False
                and realm_deactivated = False
            group by server_id, id, name, org_type
        ),
        remote_realm_push_devices as (
            select
                remote_realm_id,
                count(distinct(user_id, user_uuid)) as realm_push_user_count
            from zilencer_remotepushdevicetoken
            group by remote_realm_id
        ),
        remote_realm_push_forwarded_count as (
            select
                remote_realm_id,
                sum(coalesce(value, 0)) as realm_push_forwarded_count
            from zilencer_remoterealmcount
            where
                property = 'mobile_pushes_forwarded::day'
                and end_time >= current_timestamp(0) - interval '7 days'
            group by remote_realm_id
        )
        select
            rserver.id,
            realm_id,
            server_created,
            realm_created,
            realm_name,
            rserver.hostname,
            realm_host,
            rserver.contact_email,
            rserver.last_version,
            rserver.last_audit_log_update,
            server_push_user_count,
            realm_push_user_count,
            server_push_forwarded_count,
            realm_push_forwarded_count,
            realm_type
        from zilencer_remotezulipserver rserver
        left join remote_server_push_forwarded_count on remote_server_push_forwarded_count.server_id = rserver.id
        left join remote_server_push_devices on remote_server_push_devices.server_id = rserver.id
        left join remote_realms on remote_realms.server_id = rserver.id
        left join remote_server_audit_log on remote_server_audit_log.server_id = rserver.id
        left join remote_realm_push_devices on remote_realm_push_devices.remote_realm_id = realm_id
        left join remote_realm_push_forwarded_count on remote_realm_push_forwarded_count.remote_realm_id = realm_id
        where not deactivated
        order by server_push_user_count DESC NULLS LAST
    """
    )

    cols = [
        "Links",
        "IDs",
        "Date created",
        "Realm name",
        "Realm host or server hostname",
        "Server contact email",
        "Server Zulip version",
        "Server last audit log update (UTC)",
        "Mobile users",
        "Mobile pushes",
        "Realm organization type",
        "Plan name",
        "Plan status",
        "ARR",
        "Rate",
        "Total users",
        "Guest users",
    ]

    # If the query or column order above changes, update the constants below
    # Query constants:
    SERVER_AND_REALM_IDS = 0
    SERVER_CREATED = 1
    REALM_CREATED = 2
    SERVER_HOST = 3
    REALM_HOST = 4
    SERVER_PUSH_USER_COUNT = 9
    REALM_PUSH_USER_COUNT = 10
    SERVER_PUSH_FORWARDED = 11
    REALM_PUSH_FORWARDED = 12

    # Column constants:
    DATE_CREATED = 2
    LAST_AUDIT_LOG_DATE = 7
    MOBILE_USER_COUNT = 8
    MOBILE_PUSH_COUNT = 9
    ORG_TYPE = 10
    ARR = 13
    TOTAL_USER_COUNT = 15
    GUEST_COUNT = 16

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

        # Remove extra mobile user/push data and set created date
        # For remote realm row, remove server push data and created date;
        # for remote server row, remove realm push data and created date.
        if realm_id is not None:
            row.pop(SERVER_PUSH_FORWARDED)
            row.pop(SERVER_PUSH_USER_COUNT)
            row.pop(SERVER_CREATED)
        else:
            row.pop(REALM_PUSH_FORWARDED)
            row.pop(REALM_PUSH_USER_COUNT)
            row.pop(REALM_CREATED)

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
    for i in range(len(cols)):
        if i == LAST_AUDIT_LOG_DATE:
            fix_rows(rows, i, format_optional_datetime)
        if i in [MOBILE_USER_COUNT, MOBILE_PUSH_COUNT]:
            fix_rows(rows, i, format_none_as_zero)
        if i == DATE_CREATED:
            fix_rows(rows, i, format_datetime_as_date)
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
