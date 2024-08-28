from typing import Any

from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from corporate.lib.activity import (
    ActivityHeaderEntry,
    format_optional_datetime,
    make_table,
    user_support_link,
)
from zerver.decorator import require_server_admin
from zerver.models import UserActivity, UserProfile
from zerver.models.users import get_user_profile_by_id


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

    title = f"{user_profile.full_name}"
    cols = [
        "Query",
        "Client",
        "Count",
        "Last visit (UTC)",
    ]

    def row(record: UserActivity) -> list[Any]:
        return [
            record.query,
            record.client.name,
            record.count,
            format_optional_datetime(record.last_visit),
        ]

    rows = list(map(row, records))

    header_entries = []
    header_entries.append(ActivityHeaderEntry(name="Email", value=user_profile.delivery_email))
    header_entries.append(ActivityHeaderEntry(name="Realm", value=user_profile.realm.name))

    user_support = user_support_link(user_profile.delivery_email)

    content = make_table(title, cols, rows, header=header_entries, title_link=user_support)

    return render(
        request,
        "corporate/activity/activity.html",
        context=dict(
            data=content,
            title=title,
            is_home=False,
        ),
    )
