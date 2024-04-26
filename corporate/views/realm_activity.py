import itertools
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Collection, Dict, Optional, Set

from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse, HttpResponseNotFound
from django.shortcuts import render
from django.utils.timezone import now as timezone_now
from markupsafe import Markup

from corporate.lib.activity import (
    format_optional_datetime,
    make_table,
    realm_stats_link,
    user_activity_link,
)
from zerver.decorator import require_server_admin
from zerver.models import Realm, UserActivity
from zerver.models.users import UserProfile


@dataclass
class UserActivitySummary:
    user_name: str
    user_id: int
    user_type: str
    messages_sent: int
    last_heard_from: Optional[datetime]
    last_message_sent: Optional[datetime]


def get_user_activity_records_for_realm(realm: str) -> QuerySet[UserActivity]:
    fields = [
        "user_profile__full_name",
        "user_profile__delivery_email",
        "user_profile__is_bot",
        "user_profile__bot_type",
        "query",
        "count",
        "last_visit",
    ]

    records = (
        UserActivity.objects.filter(
            user_profile__realm__string_id=realm,
            user_profile__is_active=True,
        )
        .order_by("user_profile__delivery_email", "-last_visit")
        .select_related("user_profile")
        .only(*fields)
    )
    return records


def get_user_activity_summary(records: Collection[UserActivity]) -> UserActivitySummary:
    if records:
        first_record = next(iter(records))
        name = first_record.user_profile.full_name
        user_profile_id = first_record.user_profile.id
        if not first_record.user_profile.is_bot:
            user_type = "Human"
        else:
            assert first_record.user_profile.bot_type is not None
            bot_type = first_record.user_profile.bot_type
            user_type = UserProfile.BOT_TYPES[bot_type]

    messages = 0
    heard_from: Optional[datetime] = None
    last_sent: Optional[datetime] = None

    for record in records:
        query = str(record.query)
        visit = record.last_visit

        if heard_from is None:
            heard_from = visit
        else:
            heard_from = max(visit, heard_from)

        if ("send_message" in query) or re.search(r"/api/.*/external/.*", query):
            messages += record.count
            if last_sent is None:
                last_sent = visit
            else:
                last_sent = max(visit, last_sent)

    return UserActivitySummary(
        user_name=name,
        user_id=user_profile_id,
        user_type=user_type,
        messages_sent=messages,
        last_heard_from=heard_from,
        last_message_sent=last_sent,
    )


def realm_user_summary_table(
    all_records: QuerySet[UserActivity], admin_emails: Set[str], title: str, stats_link: Markup
) -> str:
    user_records: Dict[str, UserActivitySummary] = {}

    def by_email(record: UserActivity) -> str:
        return record.user_profile.delivery_email

    for email, records in itertools.groupby(all_records, by_email):
        user_records[email] = get_user_activity_summary(list(records))

    def is_recent(val: datetime) -> bool:
        age = timezone_now() - val
        return age.total_seconds() < 5 * 60

    cols = [
        "Name",
        "Email",
        "User type",
        "Messages sent",
        "Last heard from (UTC)",
        "Last message sent (UTC)",
    ]

    rows = []
    for email, user_summary in user_records.items():
        email_link = user_activity_link(email, user_summary.user_id)
        cells = [
            user_summary.user_name,
            email_link,
            user_summary.user_type,
            user_summary.messages_sent,
        ]
        cells.append(format_optional_datetime(user_summary.last_heard_from))
        cells.append(format_optional_datetime(user_summary.last_message_sent))

        row_class = ""
        if user_summary.last_heard_from and is_recent(user_summary.last_heard_from):
            row_class += " recently_active"
        if email in admin_emails:
            row_class += " admin"

        row = dict(cells=cells, row_class=row_class)
        rows.append(row)

    def by_last_heard_from(row: Dict[str, Any]) -> str:
        return row["cells"][4]

    rows = sorted(rows, key=by_last_heard_from, reverse=True)
    content = make_table(title, cols, rows, stats_link=stats_link, has_row_class=True)
    return content


@require_server_admin
def get_realm_activity(request: HttpRequest, realm_str: str) -> HttpResponse:
    try:
        admins = Realm.objects.get(string_id=realm_str).get_human_admin_users()
    except Realm.DoesNotExist:
        return HttpResponseNotFound()

    admin_emails = {admin.delivery_email for admin in admins}
    all_records = get_user_activity_records_for_realm(realm_str)
    realm_stats = realm_stats_link(realm_str)
    title = realm_str
    content = realm_user_summary_table(all_records, admin_emails, title, realm_stats)

    return render(
        request,
        "corporate/activity/activity.html",
        context=dict(
            data=content,
            title=title,
            is_home=False,
        ),
    )
