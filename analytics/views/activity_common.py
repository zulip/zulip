import re
import sys
from datetime import datetime
from typing import Any, Callable, Collection, Dict, List, Optional, Sequence, Union
from urllib.parse import urlencode

from django.conf import settings
from django.db import connection
from django.db.backends.utils import CursorWrapper
from django.template import loader
from django.urls import reverse
from markupsafe import Markup
from psycopg2.sql import Composable

from zerver.lib.pysa import mark_sanitized
from zerver.lib.url_encoding import append_url_query_string
from zerver.models import Realm, UserActivity

if sys.version_info < (3, 9):  # nocoverage
    from backports import zoneinfo
else:  # nocoverage
    import zoneinfo

eastern_tz = zoneinfo.ZoneInfo("America/New_York")


if settings.BILLING_ENABLED:
    pass


def make_table(
    title: str, cols: Sequence[str], rows: Sequence[Any], has_row_class: bool = False
) -> str:
    if not has_row_class:

        def fix_row(row: Any) -> Dict[str, Any]:
            return dict(cells=row, row_class=None)

        rows = list(map(fix_row, rows))

    data = dict(title=title, cols=cols, rows=rows)

    content = loader.render_to_string(
        "analytics/ad_hoc_query.html",
        dict(data=data),
    )

    return content


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


def dictfetchall(cursor: CursorWrapper) -> List[Dict[str, Any]]:
    """Returns all rows from a cursor as a dict"""
    desc = cursor.description
    return [dict(zip((col[0] for col in desc), row)) for row in cursor.fetchall()]


def format_date_for_activity_reports(date: Optional[datetime]) -> str:
    if date:
        return date.astimezone(eastern_tz).strftime("%Y-%m-%d %H:%M")
    else:
        return ""


def user_activity_link(email: str, user_profile_id: int) -> Markup:
    from analytics.views.user_activity import get_user_activity

    url = reverse(get_user_activity, kwargs=dict(user_profile_id=user_profile_id))
    return Markup('<a href="{url}">{email}</a>').format(url=url, email=email)


def realm_activity_link(realm_str: str) -> Markup:
    from analytics.views.realm_activity import get_realm_activity

    url = reverse(get_realm_activity, kwargs=dict(realm_str=realm_str))
    return Markup('<a href="{url}">{realm_str}</a>').format(url=url, realm_str=realm_str)


def realm_stats_link(realm_str: str) -> Markup:
    from analytics.views.stats import stats_for_realm

    url = reverse(stats_for_realm, kwargs=dict(realm_str=realm_str))
    return Markup('<a href="{url}"><i class="fa fa-pie-chart"></i></a>').format(url=url)


def realm_support_link(realm_str: str) -> Markup:
    support_url = reverse("support")
    query = urlencode({"q": realm_str})
    url = append_url_query_string(support_url, query)
    return Markup('<a href="{url}"><i class="fa fa-gear"></i></a>').format(url=url)


def realm_url_link(realm_str: str) -> Markup:
    host = Realm.host_for_subdomain(realm_str)
    url = settings.EXTERNAL_URI_SCHEME + mark_sanitized(host)
    return Markup('<a href="{url}"><i class="fa fa-home"></i></a>').format(url=url)


def remote_installation_stats_link(server_id: int, hostname: str) -> Markup:
    from analytics.views.stats import stats_for_remote_installation

    url = reverse(stats_for_remote_installation, kwargs=dict(remote_server_id=server_id))
    return Markup('<a href="{url}"><i class="fa fa-pie-chart"></i></a> {hostname}').format(
        url=url, hostname=hostname
    )


def remote_installation_support_link(hostname: str) -> Markup:
    support_url = reverse("remote_servers_support")
    query = urlencode({"q": hostname})
    url = append_url_query_string(support_url, query)
    return Markup('<a href="{url}"><i class="fa fa-gear"></i></a>').format(url=url)


def get_user_activity_summary(records: Collection[UserActivity]) -> Dict[str, Any]:
    #: The type annotation used above is clearly overly permissive.
    #: We should perhaps use TypedDict to clearly lay out the schema
    #: for the user activity summary.
    summary: Dict[str, Any] = {}

    def update(action: str, record: UserActivity) -> None:
        if action not in summary:
            summary[action] = dict(
                count=record.count,
                last_visit=record.last_visit,
            )
        else:
            summary[action]["count"] += record.count
            summary[action]["last_visit"] = max(
                summary[action]["last_visit"],
                record.last_visit,
            )

    if records:
        first_record = next(iter(records))
        summary["name"] = first_record.user_profile.full_name
        summary["user_profile_id"] = first_record.user_profile.id

    for record in records:
        client = record.client.name
        query = str(record.query)

        update("use", record)

        if client == "API":
            m = re.match("/api/.*/external/(.*)", query)
            if m:
                client = m.group(1)
                update(client, record)

        if client.startswith("desktop"):
            update("desktop", record)
        if client == "website":
            update("website", record)
        if ("send_message" in query) or re.search("/api/.*/external/.*", query):
            update("send", record)
        if query in [
            "/json/update_pointer",
            "/json/users/me/pointer",
            "/api/v1/update_pointer",
            "update_pointer_backend",
        ]:
            update("pointer", record)
        update(client, record)

    return summary
