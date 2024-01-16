import sys
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Sequence, Union
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
from zerver.models import Realm

if sys.version_info < (3, 9):  # nocoverage
    from backports import zoneinfo
else:  # nocoverage
    import zoneinfo

eastern_tz = zoneinfo.ZoneInfo("America/New_York")


if settings.BILLING_ENABLED:
    pass


def make_table(
    title: str,
    cols: Sequence[str],
    rows: Sequence[Any],
    stats_link: Optional[Markup] = None,
    has_row_class: bool = False,
) -> str:
    if not has_row_class:

        def fix_row(row: Any) -> Dict[str, Any]:
            return dict(cells=row, row_class=None)

        rows = list(map(fix_row, rows))

    data = dict(title=title, cols=cols, rows=rows, stats_link=stats_link)

    content = loader.render_to_string(
        "analytics/ad_hoc_query.html",
        dict(data=data),
    )

    return content


def fix_rows(
    rows: List[List[Any]],
    i: int,
    fixup_func: Union[Callable[[str], Markup], Callable[[datetime], str], Callable[[int], int]],
) -> None:
    for row in rows:
        row[i] = fixup_func(row[i])


def get_query_data(query: Composable) -> List[List[Any]]:
    cursor = connection.cursor()
    cursor.execute(query)
    rows = cursor.fetchall()
    rows = list(map(list, rows))
    cursor.close()
    return rows


def dictfetchall(cursor: CursorWrapper) -> List[Dict[str, Any]]:
    """Returns all rows from a cursor as a dict"""
    desc = cursor.description
    return [dict(zip((col[0] for col in desc), row)) for row in cursor.fetchall()]


def format_date_for_activity_reports(date: Optional[datetime]) -> str:
    if date:
        return date.astimezone(eastern_tz).strftime("%Y-%m-%d %H:%M")
    else:
        return ""


def format_none_as_zero(value: Optional[int]) -> int:
    if value:
        return value
    else:
        return 0


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


def remote_installation_stats_link(server_id: int) -> Markup:
    from analytics.views.stats import stats_for_remote_installation

    url = reverse(stats_for_remote_installation, kwargs=dict(remote_server_id=server_id))
    return Markup('<a href="{url}"><i class="fa fa-pie-chart"></i></a>').format(url=url)


def remote_installation_support_link(hostname: str) -> Markup:
    support_url = reverse("remote_servers_support")
    query = urlencode({"q": hostname})
    url = append_url_query_string(support_url, query)
    return Markup('<a href="{url}"><i class="fa fa-gear"></i></a>').format(url=url)
