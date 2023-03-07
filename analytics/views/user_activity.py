from typing import Any, Dict, List, Tuple

from django.conf import settings
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from analytics.views.activity_common import (
    format_date_for_activity_reports,
    get_user_activity_summary,
    make_table,
)
from zerver.decorator import require_server_admin
from zerver.models import UserActivity, UserProfile, get_user_profile_by_id

if settings.BILLING_ENABLED:
    pass


def get_user_activity_records(
    user_profile: UserProfile,
) -> QuerySet[UserActivity]:
    fields = [
        "user_profile__full_name",
        "query",
        "client__name",
        "count",
        "last_visit",
    ]

    records = UserActivity.objects.filter(
        user_profile=user_profile,
    )
    records = records.order_by("-last_visit")
    records = records.select_related("user_profile", "client").only(*fields)
    return records


def raw_user_activity_table(records: QuerySet[UserActivity]) -> str:
    cols = [
        "query",
        "client",
        "count",
        "last_visit",
    ]

    def row(record: UserActivity) -> List[Any]:
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
        if k == "name" or k == "user_profile_id":
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
def get_user_activity(request: HttpRequest, user_profile_id: int) -> HttpResponse:
    user_profile = get_user_profile_by_id(user_profile_id)
    records = get_user_activity_records(user_profile)

    data: List[Tuple[str, str]] = []
    user_summary = get_user_activity_summary(records)
    content = user_activity_summary_table(user_summary)

    data += [("Summary", content)]

    content = raw_user_activity_table(records)
    data += [("Info", content)]

    title = user_profile.delivery_email
    return render(
        request,
        "analytics/activity.html",
        context=dict(data=data, title=title),
    )
