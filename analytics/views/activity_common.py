import re
import sys
from datetime import datetime
from html import escape
from typing import Any, Collection, Dict, List, Optional, Sequence

from django.conf import settings
from django.db.backends.utils import CursorWrapper
from django.template import loader
from django.urls import reverse
from markupsafe import Markup

from zerver.models import UserActivity

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


def dictfetchall(cursor: CursorWrapper) -> List[Dict[str, Any]]:
    "Returns all rows from a cursor as a dict"
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
    email_link = f'<a href="{escape(url)}">{escape(email)}</a>'
    return Markup(email_link)


def realm_activity_link(realm_str: str) -> Markup:
    from analytics.views.realm_activity import get_realm_activity

    url = reverse(get_realm_activity, kwargs=dict(realm_str=realm_str))
    realm_link = f'<a href="{escape(url)}">{escape(realm_str)}</a>'
    return Markup(realm_link)


def realm_stats_link(realm_str: str) -> Markup:
    from analytics.views.stats import stats_for_realm

    url = reverse(stats_for_realm, kwargs=dict(realm_str=realm_str))
    stats_link = f'<a href="{escape(url)}"><i class="fa fa-pie-chart"></i>{escape(realm_str)}</a>'
    return Markup(stats_link)


def remote_installation_stats_link(server_id: int, hostname: str) -> Markup:
    from analytics.views.stats import stats_for_remote_installation

    url = reverse(stats_for_remote_installation, kwargs=dict(remote_server_id=server_id))
    stats_link = f'<a href="{escape(url)}"><i class="fa fa-pie-chart"></i>{escape(hostname)}</a>'
    return Markup(stats_link)


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
