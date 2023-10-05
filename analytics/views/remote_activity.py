from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from psycopg2.sql import SQL

from analytics.views.activity_common import get_page
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

    remote_servers = get_page(query, cols, title, totals_columns=[3, 4])

    return render(
        request,
        "analytics/activity_details_template.html",
        context=dict(data=remote_servers["content"], title=remote_servers["title"], is_home=False),
    )
