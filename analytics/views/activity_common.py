from datetime import datetime
from html import escape
from typing import Any, Dict, List, Optional, Sequence

import pytz
from django.conf import settings
from django.db import connection
from django.template import loader
from django.urls import reverse
from jinja2 import Markup as mark_safe

eastern_tz = pytz.timezone("US/Eastern")


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


def dictfetchall(cursor: connection.cursor) -> List[Dict[str, Any]]:
    "Returns all rows from a cursor as a dict"
    desc = cursor.description
    return [dict(zip((col[0] for col in desc), row)) for row in cursor.fetchall()]


def format_date_for_activity_reports(date: Optional[datetime]) -> str:
    if date:
        return date.astimezone(eastern_tz).strftime("%Y-%m-%d %H:%M")
    else:
        return ""


def user_activity_link(email: str) -> mark_safe:
    from analytics.views.legacy import get_user_activity

    url = reverse(get_user_activity, kwargs=dict(email=email))
    email_link = f'<a href="{escape(url)}">{escape(email)}</a>'
    return mark_safe(email_link)


def realm_activity_link(realm_str: str) -> mark_safe:
    from analytics.views.legacy import get_realm_activity

    url = reverse(get_realm_activity, kwargs=dict(realm_str=realm_str))
    realm_link = f'<a href="{escape(url)}">{escape(realm_str)}</a>'
    return mark_safe(realm_link)


def realm_stats_link(realm_str: str) -> mark_safe:
    from analytics.views.stats import stats_for_realm

    url = reverse(stats_for_realm, kwargs=dict(realm_str=realm_str))
    stats_link = f'<a href="{escape(url)}"><i class="fa fa-pie-chart"></i>{escape(realm_str)}</a>'
    return mark_safe(stats_link)


def remote_installation_stats_link(server_id: int, hostname: str) -> mark_safe:
    from analytics.views.stats import stats_for_remote_installation

    url = reverse(stats_for_remote_installation, kwargs=dict(remote_server_id=server_id))
    stats_link = f'<a href="{escape(url)}"><i class="fa fa-pie-chart"></i>{escape(hostname)}</a>'
    return mark_safe(stats_link)
