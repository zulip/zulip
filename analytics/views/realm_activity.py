import itertools
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from django.db import connection
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse, HttpResponseNotFound
from django.shortcuts import render
from django.utils.timezone import now as timezone_now
from psycopg2.sql import SQL

from analytics.views.activity_common import (
    format_date_for_activity_reports,
    get_user_activity_summary,
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


def realm_client_table(user_summaries: Dict[str, Dict[str, Any]]) -> str:
    exclude_keys = [
        "internal",
        "name",
        "user_profile_id",
        "use",
        "send",
        "pointer",
        "website",
        "desktop",
    ]

    rows = []
    for email, user_summary in user_summaries.items():
        email_link = user_activity_link(email, user_summary["user_profile_id"])
        name = user_summary["name"]
        for k, v in user_summary.items():
            if k in exclude_keys:
                continue
            client = k
            count = v["count"]
            last_visit = v["last_visit"]
            row = [
                format_date_for_activity_reports(last_visit),
                client,
                name,
                email_link,
                count,
            ]
            rows.append(row)

    rows = sorted(rows, key=lambda r: r[0], reverse=True)

    cols = [
        "Last visit",
        "Client",
        "Name",
        "Email",
        "Count",
    ]

    title = "Clients"

    return make_table(title, cols, rows)


def sent_messages_report(realm: str) -> str:
    title = "Recently sent messages for " + realm

    cols = [
        "Date",
        "Humans",
        "Bots",
    ]

    # Uses index: zerver_message_realm_date_sent
    query = SQL(
        """
        select
            series.day::date,
            user_messages.humans,
            user_messages.bots
        from (
            select generate_series(
                (now()::date - interval '2 week'),
                now()::date,
                interval '1 day'
            ) as day
        ) as series
        left join (
            select
                date_sent::date date_sent,
                count(*) filter (where not up.is_bot) as humans,
                count(*) filter (where up.is_bot) as bots
            from zerver_message m
            join zerver_userprofile up on up.id = m.sender_id
            join zerver_realm r on r.id = up.realm_id
            where
                r.string_id = %s
            and
                date_sent > now() - interval '2 week'
            and
                m.realm_id = r.id
            group by
                date_sent::date
            order by
                date_sent::date
        ) user_messages on
            series.day = user_messages.date_sent
    """
    )
    cursor = connection.cursor()
    cursor.execute(query, [realm])
    rows = cursor.fetchall()
    cursor.close()

    return make_table(title, cols, rows)


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

    page_title = "Clients"
    content = realm_client_table(all_user_records)
    data += [(page_title, content)]

    page_title = "History"
    content = sent_messages_report(realm_str)
    data += [(page_title, content)]

    title = realm_str
    realm_stats = realm_stats_link(realm_str)

    return render(
        request,
        "analytics/activity.html",
        context=dict(data=data, realm_stats_link=realm_stats, title=title),
    )
