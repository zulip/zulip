from typing import Any, Dict, List, Tuple

from django.conf import settings
from django.db.models.query import QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from analytics.views.activity_common import (
    format_date_for_activity_reports,
    get_user_activity_summary,
    make_table,
)
from zerver.decorator import require_server_admin
from zerver.models import UserActivity

if settings.BILLING_ENABLED:
    pass


def get_user_activity_records_for_email(email: str) -> List[QuerySet]:
    fields = [
        "user_profile__full_name",
        "query",
        "client__name",
        "count",
        "last_visit",
    ]

    records = UserActivity.objects.filter(
        user_profile__delivery_email=email,
    )
    records = records.order_by("-last_visit")
    records = records.select_related("user_profile", "client").only(*fields)
    return records


def raw_user_activity_table(records: List[QuerySet]) -> str:
    cols = [
        "query",
        "client",
        "count",
        "last_visit",
    ]

    def row(record: QuerySet) -> List[Any]:
        return [
            record.query,
            record.client.name,
            record.count,
            format_date_for_activity_reports(record.last_visit),
        ]

    rows = list(map(row, records))
    title = "Raw data"
    return make_table(title, cols, rows)


def user_activity_summary_table(user_summary: Dict[str, Dict[str, Any]]) -> str:
    rows = []
    for k, v in user_summary.items():
        if k == "name":
            continue
        client = k
        count = v["count"]
        last_visit = v["last_visit"]
        row = [
            format_date_for_activity_reports(last_visit),
            client,
            count,
        ]
        rows.append(row)

    rows = sorted(rows, key=lambda r: r[0], reverse=True)

    cols = [
        "last_visit",
        "client",
        "count",
    ]

    title = "User activity"
    return make_table(title, cols, rows)


@require_server_admin
def get_user_activity(request: HttpRequest, email: str) -> HttpResponse:
    records = get_user_activity_records_for_email(email)

    data: List[Tuple[str, str]] = []
    user_summary = get_user_activity_summary(records)
    content = user_activity_summary_table(user_summary)

    data += [("Summary", content)]

    content = raw_user_activity_table(records)
    data += [("Info", content)]

    title = email
    return render(
        request,
        "analytics/activity.html",
        context=dict(data=data, title=title),
    )
