import itertools
import re
from datetime import datetime
from typing import Any, Collection, Dict, List, Optional, Set, Tuple

from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse, HttpResponseNotFound
from django.shortcuts import render
from django.utils.timezone import now as timezone_now

from analytics.views.activity_common import (
    format_date_for_activity_reports,
    make_table,
    realm_stats_link,
    user_activity_link,
)
from zerver.decorator import require_server_admin
from zerver.models import Realm, UserActivity


def get_user_activity_records_for_realm(realm: str, is_bot: bool) -> QuerySet[UserActivity]:
    fields = [
        "user_profile__full_name",
        "user_profile__delivery_email",
        "query",
        "client__name",
        "count",
        "last_visit",
    ]

    records = UserActivity.objects.filter(
        user_profile__realm__string_id=realm,
        user_profile__is_active=True,
        user_profile__is_bot=is_bot,
    )
    records = records.order_by("user_profile__delivery_email", "-last_visit")
    records = records.select_related("user_profile", "client").only(*fields)
    return records


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


def realm_user_summary_table(
    all_records: QuerySet[UserActivity], admin_emails: Set[str]
) -> Tuple[Dict[str, Any], str]:
    user_records = {}

    def by_email(record: UserActivity) -> str:
        return record.user_profile.delivery_email

    for email, records in itertools.groupby(all_records, by_email):
        user_records[email] = get_user_activity_summary(list(records))

    def get_last_visit(user_summary: Dict[str, Dict[str, datetime]], k: str) -> Optional[datetime]:
        if k in user_summary:
            return user_summary[k]["last_visit"]
        else:
            return None

    def get_count(user_summary: Dict[str, Dict[str, str]], k: str) -> str:
        if k in user_summary:
            return user_summary[k]["count"]
        else:
            return ""

    def is_recent(val: datetime) -> bool:
        age = timezone_now() - val
        return age.total_seconds() < 5 * 60

    rows = []
    for email, user_summary in user_records.items():
        email_link = user_activity_link(email, user_summary["user_profile_id"])
        sent_count = get_count(user_summary, "send")
        cells = [user_summary["name"], email_link, sent_count]
        row_class = ""
        for field in ["use", "send", "pointer", "desktop", "ZulipiOS", "Android"]:
            visit = get_last_visit(user_summary, field)
            if field == "use":
                if visit and is_recent(visit):
                    row_class += " recently_active"
                if email in admin_emails:
                    row_class += " admin"
            val = format_date_for_activity_reports(visit)
            cells.append(val)
        row = dict(cells=cells, row_class=row_class)
        rows.append(row)

    def by_used_time(row: Dict[str, Any]) -> str:
        return row["cells"][3]

    rows = sorted(rows, key=by_used_time, reverse=True)

    cols = [
        "Name",
        "Email",
        "Total sent",
        "Heard from",
        "Message sent",
        "Pointer motion",
        "Desktop",
        "ZulipiOS",
        "Android",
    ]

    title = "Summary"

    content = make_table(title, cols, rows, has_row_class=True)
    return user_records, content


@require_server_admin
def get_realm_activity(request: HttpRequest, realm_str: str) -> HttpResponse:
    data: List[Tuple[str, str]] = []
    all_user_records: Dict[str, Any] = {}

    try:
        admins = Realm.objects.get(string_id=realm_str).get_human_admin_users()
    except Realm.DoesNotExist:
        return HttpResponseNotFound()

    admin_emails = {admin.delivery_email for admin in admins}

    for is_bot, page_title in [(False, "Humans"), (True, "Bots")]:
        all_records = get_user_activity_records_for_realm(realm_str, is_bot)

        user_records, content = realm_user_summary_table(all_records, admin_emails)
        all_user_records.update(user_records)

        data += [(page_title, content)]

    title = realm_str
    realm_stats = realm_stats_link(realm_str)

    return render(
        request,
        "analytics/activity.html",
        context=dict(data=data, realm_stats_link=realm_stats, title=title),
    )
