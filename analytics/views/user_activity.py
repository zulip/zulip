from typing import Any, List

from django.conf import settings
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from analytics.views.activity_common import format_date_for_activity_reports, make_table
from zerver.decorator import require_server_admin
from zerver.models import UserActivity, UserProfile
from zerver.models.users import get_user_profile_by_id

if settings.BILLING_ENABLED:
    pass


def get_user_activity_records(
    user_profile: UserProfile,
) -> QuerySet[UserActivity]:
    fields = [
        "query",
        "client__name",
        "count",
        "last_visit",
    ]

    records = (
        UserActivity.objects.filter(
            user_profile=user_profile,
        )
        .order_by("-last_visit")
        .select_related("client")
        .only(*fields)
    )
    return records


@require_server_admin
def get_user_activity(request: HttpRequest, user_profile_id: int) -> HttpResponse:
    user_profile = get_user_profile_by_id(user_profile_id)
    records = get_user_activity_records(user_profile)

    cols = [
        "Query",
        "Client",
        "Count",
        "Last visit",
    ]

    def row(record: UserActivity) -> List[Any]:
        return [
            record.query,
            record.client.name,
            record.count,
            format_date_for_activity_reports(record.last_visit),
        ]

    rows = list(map(row, records))
    title = f"{user_profile.delivery_email} ({user_profile.realm.name})"
    content = make_table(title, cols, rows)

    return render(
        request,
        "analytics/activity_details_template.html",
        context=dict(
            data=content,
            title=title,
            is_home=False,
        ),
    )
