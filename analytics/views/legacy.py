import itertools
import re
import time
import urllib
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from html import escape
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple, Union
from urllib.parse import urlencode

import pytz
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import connection
from django.db.models.query import QuerySet
from django.http import HttpRequest, HttpResponse, HttpResponseNotFound, HttpResponseRedirect
from django.shortcuts import render
from django.template import loader
from django.urls import reverse
from django.utils.timesince import timesince
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _
from jinja2 import Markup as mark_safe
from psycopg2.sql import SQL, Composable, Literal

from analytics.lib.counts import COUNT_STATS
from analytics.views.stats import stats_for_realm, stats_for_remote_installation
from confirmation.models import Confirmation, _properties, confirmation_url
from confirmation.settings import STATUS_ACTIVE
from zerver.decorator import require_server_admin
from zerver.forms import check_subdomain_available
from zerver.lib.actions import (
    do_change_plan_type,
    do_change_realm_subdomain,
    do_deactivate_realm,
    do_scrub_realm,
    do_send_realm_reactivation_email,
)
from zerver.lib.realm_icon import realm_icon_url
from zerver.lib.request import has_request_variables
from zerver.lib.response import json_error
from zerver.lib.subdomains import get_subdomain_from_hostname
from zerver.lib.timestamp import timestamp_to_datetime
from zerver.models import (
    MultiuseInvite,
    PreregistrationUser,
    Realm,
    UserActivity,
    UserActivityInterval,
    UserProfile,
    get_realm,
)
from zerver.views.invite import get_invitee_emails_set

if settings.BILLING_ENABLED:
    from corporate.lib.stripe import (
        approve_sponsorship,
        attach_discount_to_realm,
        downgrade_at_the_end_of_billing_cycle,
        downgrade_now_without_creating_additional_invoices,
        estimate_annual_recurring_revenue_by_realm,
        get_current_plan_by_realm,
        get_customer_by_realm,
        get_discount_for_realm,
        get_latest_seat_count,
        get_realms_to_default_discount_dict,
        make_end_of_cycle_updates_if_needed,
        update_billing_method_of_current_plan,
        update_sponsorship_status,
        void_all_open_invoices,
    )


eastern_tz = pytz.timezone("US/Eastern")


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


def get_realm_day_counts() -> Dict[str, Dict[str, str]]:
    query = SQL(
        """
        select
            r.string_id,
            (now()::date - date_sent::date) age,
            count(*) cnt
        from zerver_message m
        join zerver_userprofile up on up.id = m.sender_id
        join zerver_realm r on r.id = up.realm_id
        join zerver_client c on c.id = m.sending_client_id
        where
            (not up.is_bot)
        and
            date_sent > now()::date - interval '8 day'
        and
            c.name not in ('zephyr_mirror', 'ZulipMonitoring')
        group by
            r.string_id,
            age
        order by
            r.string_id,
            age
    """
    )
    cursor = connection.cursor()
    cursor.execute(query)
    rows = dictfetchall(cursor)
    cursor.close()

    counts: Dict[str, Dict[int, int]] = defaultdict(dict)
    for row in rows:
        counts[row["string_id"]][row["age"]] = row["cnt"]

    result = {}
    for string_id in counts:
        raw_cnts = [counts[string_id].get(age, 0) for age in range(8)]
        min_cnt = min(raw_cnts[1:])
        max_cnt = max(raw_cnts[1:])

        def format_count(cnt: int, style: Optional[str] = None) -> str:
            if style is not None:
                good_bad = style
            elif cnt == min_cnt:
                good_bad = "bad"
            elif cnt == max_cnt:
                good_bad = "good"
            else:
                good_bad = "neutral"

            return f'<td class="number {good_bad}">{cnt}</td>'

        cnts = format_count(raw_cnts[0], "neutral") + "".join(map(format_count, raw_cnts[1:]))
        result[string_id] = dict(cnts=cnts)

    return result


def get_plan_name(plan_type: int) -> str:
    return ["", "self hosted", "limited", "standard", "open source"][plan_type]


def realm_summary_table(realm_minutes: Dict[str, float]) -> str:
    now = timezone_now()

    query = SQL(
        """
        SELECT
            realm.string_id,
            realm.date_created,
            realm.plan_type,
            coalesce(wau_table.value, 0) wau_count,
            coalesce(dau_table.value, 0) dau_count,
            coalesce(user_count_table.value, 0) user_profile_count,
            coalesce(bot_count_table.value, 0) bot_count
        FROM
            zerver_realm as realm
            LEFT OUTER JOIN (
                SELECT
                    value _14day_active_humans,
                    realm_id
                from
                    analytics_realmcount
                WHERE
                    property = 'realm_active_humans::day'
                    AND end_time = %(realm_active_humans_end_time)s
            ) as _14day_active_humans_table ON realm.id = _14day_active_humans_table.realm_id
            LEFT OUTER JOIN (
                SELECT
                    value,
                    realm_id
                from
                    analytics_realmcount
                WHERE
                    property = '7day_actives::day'
                    AND end_time = %(seven_day_actives_end_time)s
            ) as wau_table ON realm.id = wau_table.realm_id
            LEFT OUTER JOIN (
                SELECT
                    value,
                    realm_id
                from
                    analytics_realmcount
                WHERE
                    property = '1day_actives::day'
                    AND end_time = %(one_day_actives_end_time)s
            ) as dau_table ON realm.id = dau_table.realm_id
            LEFT OUTER JOIN (
                SELECT
                    value,
                    realm_id
                from
                    analytics_realmcount
                WHERE
                    property = 'active_users_audit:is_bot:day'
                    AND subgroup = 'false'
                    AND end_time = %(active_users_audit_end_time)s
            ) as user_count_table ON realm.id = user_count_table.realm_id
            LEFT OUTER JOIN (
                SELECT
                    value,
                    realm_id
                from
                    analytics_realmcount
                WHERE
                    property = 'active_users_audit:is_bot:day'
                    AND subgroup = 'true'
                    AND end_time = %(active_users_audit_end_time)s
            ) as bot_count_table ON realm.id = bot_count_table.realm_id
        WHERE
            _14day_active_humans IS NOT NULL
            or realm.plan_type = 3
        ORDER BY
            dau_count DESC,
            string_id ASC
    """
    )

    cursor = connection.cursor()
    cursor.execute(
        query,
        {
            "realm_active_humans_end_time": COUNT_STATS[
                "realm_active_humans::day"
            ].last_successful_fill(),
            "seven_day_actives_end_time": COUNT_STATS["7day_actives::day"].last_successful_fill(),
            "one_day_actives_end_time": COUNT_STATS["1day_actives::day"].last_successful_fill(),
            "active_users_audit_end_time": COUNT_STATS[
                "active_users_audit:is_bot:day"
            ].last_successful_fill(),
        },
    )
    rows = dictfetchall(cursor)
    cursor.close()

    # Fetch all the realm administrator users
    realm_owners: Dict[str, List[str]] = defaultdict(list)
    for up in UserProfile.objects.select_related("realm").filter(
        role=UserProfile.ROLE_REALM_OWNER,
        is_active=True,
    ):
        realm_owners[up.realm.string_id].append(up.delivery_email)

    for row in rows:
        row["date_created_day"] = row["date_created"].strftime("%Y-%m-%d")
        row["age_days"] = int((now - row["date_created"]).total_seconds() / 86400)
        row["is_new"] = row["age_days"] < 12 * 7
        row["realm_owner_emails"] = ", ".join(realm_owners[row["string_id"]])

    # get messages sent per day
    counts = get_realm_day_counts()
    for row in rows:
        try:
            row["history"] = counts[row["string_id"]]["cnts"]
        except Exception:
            row["history"] = ""

    # estimate annual subscription revenue
    total_arr = 0
    if settings.BILLING_ENABLED:
        estimated_arrs = estimate_annual_recurring_revenue_by_realm()
        realms_to_default_discount = get_realms_to_default_discount_dict()

        for row in rows:
            row["plan_type_string"] = get_plan_name(row["plan_type"])

            string_id = row["string_id"]

            if string_id in estimated_arrs:
                row["arr"] = estimated_arrs[string_id]

            if row["plan_type"] == Realm.STANDARD:
                row["effective_rate"] = 100 - int(realms_to_default_discount.get(string_id, 0))
            elif row["plan_type"] == Realm.STANDARD_FREE:
                row["effective_rate"] = 0
            elif row["plan_type"] == Realm.LIMITED and string_id in realms_to_default_discount:
                row["effective_rate"] = 100 - int(realms_to_default_discount[string_id])
            else:
                row["effective_rate"] = ""

        total_arr += sum(estimated_arrs.values())

    # augment data with realm_minutes
    total_hours = 0.0
    for row in rows:
        string_id = row["string_id"]
        minutes = realm_minutes.get(string_id, 0.0)
        hours = minutes / 60.0
        total_hours += hours
        row["hours"] = str(int(hours))
        try:
            row["hours_per_user"] = "{:.1f}".format(hours / row["dau_count"])
        except Exception:
            pass

    # formatting
    for row in rows:
        row["stats_link"] = realm_stats_link(row["string_id"])
        row["string_id"] = realm_activity_link(row["string_id"])

    # Count active sites
    def meets_goal(row: Dict[str, int]) -> bool:
        return row["dau_count"] >= 5

    num_active_sites = len(list(filter(meets_goal, rows)))

    # create totals
    total_dau_count = 0
    total_user_profile_count = 0
    total_bot_count = 0
    total_wau_count = 0
    for row in rows:
        total_dau_count += int(row["dau_count"])
        total_user_profile_count += int(row["user_profile_count"])
        total_bot_count += int(row["bot_count"])
        total_wau_count += int(row["wau_count"])

    total_row = dict(
        string_id="Total",
        plan_type_string="",
        effective_rate="",
        arr=total_arr,
        stats_link="",
        date_created_day="",
        realm_owner_emails="",
        dau_count=total_dau_count,
        user_profile_count=total_user_profile_count,
        bot_count=total_bot_count,
        hours=int(total_hours),
        wau_count=total_wau_count,
    )

    rows.insert(0, total_row)

    content = loader.render_to_string(
        "analytics/realm_summary_table.html",
        dict(
            rows=rows,
            num_active_sites=num_active_sites,
            utctime=now.strftime("%Y-%m-%d %H:%MZ"),
            billing_enabled=settings.BILLING_ENABLED,
        ),
    )
    return content


def user_activity_intervals() -> Tuple[mark_safe, Dict[str, float]]:
    day_end = timestamp_to_datetime(time.time())
    day_start = day_end - timedelta(hours=24)

    output = "Per-user online duration for the last 24 hours:\n"
    total_duration = timedelta(0)

    all_intervals = (
        UserActivityInterval.objects.filter(
            end__gte=day_start,
            start__lte=day_end,
        )
        .select_related(
            "user_profile",
            "user_profile__realm",
        )
        .only(
            "start",
            "end",
            "user_profile__delivery_email",
            "user_profile__realm__string_id",
        )
        .order_by(
            "user_profile__realm__string_id",
            "user_profile__delivery_email",
        )
    )

    by_string_id = lambda row: row.user_profile.realm.string_id
    by_email = lambda row: row.user_profile.delivery_email

    realm_minutes = {}

    for string_id, realm_intervals in itertools.groupby(all_intervals, by_string_id):
        realm_duration = timedelta(0)
        output += f"<hr>{string_id}\n"
        for email, intervals in itertools.groupby(realm_intervals, by_email):
            duration = timedelta(0)
            for interval in intervals:
                start = max(day_start, interval.start)
                end = min(day_end, interval.end)
                duration += end - start

            total_duration += duration
            realm_duration += duration
            output += f"  {email:<37}{duration}\n"

        realm_minutes[string_id] = realm_duration.total_seconds() / 60

    output += f"\nTotal duration:                      {total_duration}\n"
    output += f"\nTotal duration in minutes:           {total_duration.total_seconds() / 60.}\n"
    output += f"Total duration amortized to a month: {total_duration.total_seconds() * 30. / 60.}"
    content = mark_safe("<pre>" + output + "</pre>")
    return content, realm_minutes


def sent_messages_report(realm: str) -> str:
    title = "Recently sent messages for " + realm

    cols = [
        "Date",
        "Humans",
        "Bots",
    ]

    query = SQL(
        """
        select
            series.day::date,
            humans.cnt,
            bots.cnt
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
                count(*) cnt
            from zerver_message m
            join zerver_userprofile up on up.id = m.sender_id
            join zerver_realm r on r.id = up.realm_id
            where
                r.string_id = %s
            and
                (not up.is_bot)
            and
                date_sent > now() - interval '2 week'
            group by
                date_sent::date
            order by
                date_sent::date
        ) humans on
            series.day = humans.date_sent
        left join (
            select
                date_sent::date date_sent,
                count(*) cnt
            from zerver_message m
            join zerver_userprofile up on up.id = m.sender_id
            join zerver_realm r on r.id = up.realm_id
            where
                r.string_id = %s
            and
                up.is_bot
            and
                date_sent > now() - interval '2 week'
            group by
                date_sent::date
            order by
                date_sent::date
        ) bots on
            series.day = bots.date_sent
    """
    )
    cursor = connection.cursor()
    cursor.execute(query, [realm, realm])
    rows = cursor.fetchall()
    cursor.close()

    return make_table(title, cols, rows)


def ad_hoc_queries() -> List[Dict[str, str]]:
    def get_page(
        query: Composable, cols: Sequence[str], title: str, totals_columns: Sequence[int] = []
    ) -> Dict[str, str]:
        cursor = connection.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        rows = list(map(list, rows))
        cursor.close()

        def fix_rows(
            i: int, fixup_func: Union[Callable[[Realm], mark_safe], Callable[[datetime], str]]
        ) -> None:
            for row in rows:
                row[i] = fixup_func(row[i])

        total_row = []
        for i, col in enumerate(cols):
            if col == "Realm":
                fix_rows(i, realm_activity_link)
            elif col in ["Last time", "Last visit"]:
                fix_rows(i, format_date_for_activity_reports)
            elif col == "Hostname":
                for row in rows:
                    row[i] = remote_installation_stats_link(row[0], row[i])
            if len(totals_columns) > 0:
                if i == 0:
                    total_row.append("Total")
                elif i in totals_columns:
                    total_row.append(str(sum(row[i] for row in rows if row[i] is not None)))
                else:
                    total_row.append("")
        if len(totals_columns) > 0:
            rows.insert(0, total_row)

        content = make_table(title, cols, rows)

        return dict(
            content=content,
            title=title,
        )

    pages = []

    ###

    for mobile_type in ["Android", "ZulipiOS"]:
        title = f"{mobile_type} usage"

        query = SQL(
            """
            select
                realm.string_id,
                up.id user_id,
                client.name,
                sum(count) as hits,
                max(last_visit) as last_time
            from zerver_useractivity ua
            join zerver_client client on client.id = ua.client_id
            join zerver_userprofile up on up.id = ua.user_profile_id
            join zerver_realm realm on realm.id = up.realm_id
            where
                client.name like {mobile_type}
            group by string_id, up.id, client.name
            having max(last_visit) > now() - interval '2 week'
            order by string_id, up.id, client.name
        """
        ).format(
            mobile_type=Literal(mobile_type),
        )

        cols = [
            "Realm",
            "User id",
            "Name",
            "Hits",
            "Last time",
        ]

        pages.append(get_page(query, cols, title))

    ###

    title = "Desktop users"

    query = SQL(
        """
        select
            realm.string_id,
            client.name,
            sum(count) as hits,
            max(last_visit) as last_time
        from zerver_useractivity ua
        join zerver_client client on client.id = ua.client_id
        join zerver_userprofile up on up.id = ua.user_profile_id
        join zerver_realm realm on realm.id = up.realm_id
        where
            client.name like 'desktop%%'
        group by string_id, client.name
        having max(last_visit) > now() - interval '2 week'
        order by string_id, client.name
    """
    )

    cols = [
        "Realm",
        "Client",
        "Hits",
        "Last time",
    ]

    pages.append(get_page(query, cols, title))

    ###

    title = "Integrations by realm"

    query = SQL(
        """
        select
            realm.string_id,
            case
                when query like '%%external%%' then split_part(query, '/', 5)
                else client.name
            end client_name,
            sum(count) as hits,
            max(last_visit) as last_time
        from zerver_useractivity ua
        join zerver_client client on client.id = ua.client_id
        join zerver_userprofile up on up.id = ua.user_profile_id
        join zerver_realm realm on realm.id = up.realm_id
        where
            (query in ('send_message_backend', '/api/v1/send_message')
            and client.name not in ('Android', 'ZulipiOS')
            and client.name not like 'test: Zulip%%'
            )
        or
            query like '%%external%%'
        group by string_id, client_name
        having max(last_visit) > now() - interval '2 week'
        order by string_id, client_name
    """
    )

    cols = [
        "Realm",
        "Client",
        "Hits",
        "Last time",
    ]

    pages.append(get_page(query, cols, title))

    ###

    title = "Integrations by client"

    query = SQL(
        """
        select
            case
                when query like '%%external%%' then split_part(query, '/', 5)
                else client.name
            end client_name,
            realm.string_id,
            sum(count) as hits,
            max(last_visit) as last_time
        from zerver_useractivity ua
        join zerver_client client on client.id = ua.client_id
        join zerver_userprofile up on up.id = ua.user_profile_id
        join zerver_realm realm on realm.id = up.realm_id
        where
            (query in ('send_message_backend', '/api/v1/send_message')
            and client.name not in ('Android', 'ZulipiOS')
            and client.name not like 'test: Zulip%%'
            )
        or
            query like '%%external%%'
        group by client_name, string_id
        having max(last_visit) > now() - interval '2 week'
        order by client_name, string_id
    """
    )

    cols = [
        "Client",
        "Realm",
        "Hits",
        "Last time",
    ]

    pages.append(get_page(query, cols, title))

    title = "Remote Zulip servers"

    query = SQL(
        """
        with icount as (
            select
                server_id,
                max(value) as max_value,
                max(end_time) as max_end_time
            from zilencer_remoteinstallationcount
            where
                property='active_users:is_bot:day'
                and subgroup='false'
            group by server_id
            ),
        remote_push_devices as (
            select server_id, count(distinct(user_id)) as push_user_count from zilencer_remotepushdevicetoken
            group by server_id
        )
        select
            rserver.id,
            rserver.hostname,
            rserver.contact_email,
            max_value,
            push_user_count,
            max_end_time
        from zilencer_remotezulipserver rserver
        left join icount on icount.server_id = rserver.id
        left join remote_push_devices on remote_push_devices.server_id = rserver.id
        order by max_value DESC NULLS LAST, push_user_count DESC NULLS LAST
    """
    )

    cols = [
        "ID",
        "Hostname",
        "Contact email",
        "Analytics users",
        "Mobile users",
        "Last update time",
    ]

    pages.append(get_page(query, cols, title, totals_columns=[3, 4]))

    return pages


@require_server_admin
@has_request_variables
def get_activity(request: HttpRequest) -> HttpResponse:
    duration_content, realm_minutes = user_activity_intervals()
    counts_content: str = realm_summary_table(realm_minutes)
    data = [
        ("Counts", counts_content),
        ("Durations", duration_content),
    ]
    for page in ad_hoc_queries():
        data.append((page["title"], page["content"]))

    title = "Activity"

    return render(
        request,
        "analytics/activity.html",
        context=dict(data=data, title=title, is_home=True),
    )


def get_confirmations(
    types: List[int], object_ids: List[int], hostname: Optional[str] = None
) -> List[Dict[str, Any]]:
    lowest_datetime = timezone_now() - timedelta(days=30)
    confirmations = Confirmation.objects.filter(
        type__in=types, object_id__in=object_ids, date_sent__gte=lowest_datetime
    )
    confirmation_dicts = []
    for confirmation in confirmations:
        realm = confirmation.realm
        content_object = confirmation.content_object

        type = confirmation.type
        days_to_activate = _properties[type].validity_in_days
        expiry_date = confirmation.date_sent + timedelta(days=days_to_activate)

        if hasattr(content_object, "status"):
            if content_object.status == STATUS_ACTIVE:
                link_status = "Link has been clicked"
            else:
                link_status = "Link has never been clicked"
        else:
            link_status = ""

        now = timezone_now()
        if now < expiry_date:
            expires_in = timesince(now, expiry_date)
        else:
            expires_in = "Expired"

        url = confirmation_url(confirmation.confirmation_key, realm, type)
        confirmation_dicts.append(
            {
                "object": confirmation.content_object,
                "url": url,
                "type": type,
                "link_status": link_status,
                "expires_in": expires_in,
            }
        )
    return confirmation_dicts


@require_server_admin
def support(request: HttpRequest) -> HttpResponse:
    context: Dict[str, Any] = {}

    if "success_message" in request.session:
        context["success_message"] = request.session["success_message"]
        del request.session["success_message"]

    if settings.BILLING_ENABLED and request.method == "POST":
        # We check that request.POST only has two keys in it: The
        # realm_id and a field to change.
        keys = set(request.POST.keys())
        if "csrfmiddlewaretoken" in keys:
            keys.remove("csrfmiddlewaretoken")
        if len(keys) != 2:
            return json_error(_("Invalid parameters"))

        realm_id = request.POST.get("realm_id")
        realm = Realm.objects.get(id=realm_id)

        if request.POST.get("plan_type", None) is not None:
            new_plan_type = int(request.POST.get("plan_type"))
            current_plan_type = realm.plan_type
            do_change_plan_type(realm, new_plan_type, acting_user=request.user)
            msg = f"Plan type of {realm.string_id} changed from {get_plan_name(current_plan_type)} to {get_plan_name(new_plan_type)} "
            context["success_message"] = msg
        elif request.POST.get("discount", None) is not None:
            new_discount = Decimal(request.POST.get("discount"))
            current_discount = get_discount_for_realm(realm) or 0
            attach_discount_to_realm(realm, new_discount, acting_user=request.user)
            context[
                "success_message"
            ] = f"Discount of {realm.string_id} changed to {new_discount}% from {current_discount}%."
        elif request.POST.get("new_subdomain", None) is not None:
            new_subdomain = request.POST.get("new_subdomain")
            old_subdomain = realm.string_id
            try:
                check_subdomain_available(new_subdomain)
            except ValidationError as error:
                context["error_message"] = error.message
            else:
                do_change_realm_subdomain(realm, new_subdomain, acting_user=request.user)
                request.session[
                    "success_message"
                ] = f"Subdomain changed from {old_subdomain} to {new_subdomain}"
                return HttpResponseRedirect(
                    reverse("support") + "?" + urlencode({"q": new_subdomain})
                )
        elif request.POST.get("status", None) is not None:
            status = request.POST.get("status")
            if status == "active":
                do_send_realm_reactivation_email(realm, acting_user=request.user)
                context[
                    "success_message"
                ] = f"Realm reactivation email sent to admins of {realm.string_id}."
            elif status == "deactivated":
                do_deactivate_realm(realm, acting_user=request.user)
                context["success_message"] = f"{realm.string_id} deactivated."
        elif request.POST.get("billing_method", None) is not None:
            billing_method = request.POST.get("billing_method")
            if billing_method == "send_invoice":
                update_billing_method_of_current_plan(
                    realm, charge_automatically=False, acting_user=request.user
                )
                context[
                    "success_message"
                ] = f"Billing method of {realm.string_id} updated to pay by invoice."
            elif billing_method == "charge_automatically":
                update_billing_method_of_current_plan(
                    realm, charge_automatically=True, acting_user=request.user
                )
                context[
                    "success_message"
                ] = f"Billing method of {realm.string_id} updated to charge automatically."
        elif request.POST.get("sponsorship_pending", None) is not None:
            sponsorship_pending = request.POST.get("sponsorship_pending")
            if sponsorship_pending == "true":
                update_sponsorship_status(realm, True, acting_user=request.user)
                context["success_message"] = f"{realm.string_id} marked as pending sponsorship."
            elif sponsorship_pending == "false":
                update_sponsorship_status(realm, False, acting_user=request.user)
                context["success_message"] = f"{realm.string_id} is no longer pending sponsorship."
        elif request.POST.get("approve_sponsorship") is not None:
            if request.POST.get("approve_sponsorship") == "approve_sponsorship":
                approve_sponsorship(realm, acting_user=request.user)
                context["success_message"] = f"Sponsorship approved for {realm.string_id}"
        elif request.POST.get("downgrade_method", None) is not None:
            downgrade_method = request.POST.get("downgrade_method")
            if downgrade_method == "downgrade_at_billing_cycle_end":
                downgrade_at_the_end_of_billing_cycle(realm)
                context[
                    "success_message"
                ] = f"{realm.string_id} marked for downgrade at the end of billing cycle"
            elif downgrade_method == "downgrade_now_without_additional_licenses":
                downgrade_now_without_creating_additional_invoices(realm)
                context[
                    "success_message"
                ] = f"{realm.string_id} downgraded without creating additional invoices"
            elif downgrade_method == "downgrade_now_void_open_invoices":
                downgrade_now_without_creating_additional_invoices(realm)
                voided_invoices_count = void_all_open_invoices(realm)
                context[
                    "success_message"
                ] = f"{realm.string_id} downgraded and voided {voided_invoices_count} open invoices"
        elif request.POST.get("scrub_realm", None) is not None:
            if request.POST.get("scrub_realm") == "scrub_realm":
                do_scrub_realm(realm, acting_user=request.user)
                context["success_message"] = f"{realm.string_id} scrubbed."

    query = request.GET.get("q", None)
    if query:
        key_words = get_invitee_emails_set(query)

        users = set(UserProfile.objects.filter(delivery_email__in=key_words))
        realms = set(Realm.objects.filter(string_id__in=key_words))

        for key_word in key_words:
            try:
                URLValidator()(key_word)
                parse_result = urllib.parse.urlparse(key_word)
                hostname = parse_result.hostname
                assert hostname is not None
                if parse_result.port:
                    hostname = f"{hostname}:{parse_result.port}"
                subdomain = get_subdomain_from_hostname(hostname)
                try:
                    realms.add(get_realm(subdomain))
                except Realm.DoesNotExist:
                    pass
            except ValidationError:
                users.update(UserProfile.objects.filter(full_name__iexact=key_word))

        for realm in realms:
            realm.customer = get_customer_by_realm(realm)

            current_plan = get_current_plan_by_realm(realm)
            if current_plan is not None:
                new_plan, last_ledger_entry = make_end_of_cycle_updates_if_needed(
                    current_plan, timezone_now()
                )
                if last_ledger_entry is not None:
                    if new_plan is not None:
                        realm.current_plan = new_plan
                    else:
                        realm.current_plan = current_plan
                    realm.current_plan.licenses = last_ledger_entry.licenses
                    realm.current_plan.licenses_used = get_latest_seat_count(realm)

        # full_names can have , in them
        users.update(UserProfile.objects.filter(full_name__iexact=query))

        context["users"] = users
        context["realms"] = realms

        confirmations: List[Dict[str, Any]] = []

        preregistration_users = PreregistrationUser.objects.filter(email__in=key_words)
        confirmations += get_confirmations(
            [Confirmation.USER_REGISTRATION, Confirmation.INVITATION, Confirmation.REALM_CREATION],
            preregistration_users,
            hostname=request.get_host(),
        )

        multiuse_invites = MultiuseInvite.objects.filter(realm__in=realms)
        confirmations += get_confirmations([Confirmation.MULTIUSE_INVITE], multiuse_invites)

        confirmations += get_confirmations(
            [Confirmation.REALM_REACTIVATION], [realm.id for realm in realms]
        )

        context["confirmations"] = confirmations

    def get_realm_owner_emails_as_string(realm: Realm) -> str:
        return ", ".join(
            realm.get_human_owner_users()
            .order_by("delivery_email")
            .values_list("delivery_email", flat=True)
        )

    def get_realm_admin_emails_as_string(realm: Realm) -> str:
        return ", ".join(
            realm.get_human_admin_users(include_realm_owners=False)
            .order_by("delivery_email")
            .values_list("delivery_email", flat=True)
        )

    context["get_realm_owner_emails_as_string"] = get_realm_owner_emails_as_string
    context["get_realm_admin_emails_as_string"] = get_realm_admin_emails_as_string
    context["get_discount_for_realm"] = get_discount_for_realm
    context["realm_icon_url"] = realm_icon_url
    context["Confirmation"] = Confirmation
    return render(request, "analytics/support.html", context=context)


def get_user_activity_records_for_realm(realm: str, is_bot: bool) -> QuerySet:
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


def get_user_activity_summary(records: List[QuerySet]) -> Dict[str, Dict[str, Any]]:
    #: `Any` used above should be `Union(int, datetime)`.
    #: However current version of `Union` does not work inside other function.
    #: We could use something like:
    # `Union[Dict[str, Dict[str, int]], Dict[str, Dict[str, datetime]]]`
    #: but that would require this long `Union` to carry on throughout inner functions.
    summary: Dict[str, Dict[str, Any]] = {}

    def update(action: str, record: QuerySet) -> None:
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
        summary["name"] = records[0].user_profile.full_name

    for record in records:
        client = record.client.name
        query = record.query

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


def format_date_for_activity_reports(date: Optional[datetime]) -> str:
    if date:
        return date.astimezone(eastern_tz).strftime("%Y-%m-%d %H:%M")
    else:
        return ""


def user_activity_link(email: str) -> mark_safe:
    url = reverse(get_user_activity, kwargs=dict(email=email))
    email_link = f'<a href="{escape(url)}">{escape(email)}</a>'
    return mark_safe(email_link)


def realm_activity_link(realm_str: str) -> mark_safe:
    url = reverse(get_realm_activity, kwargs=dict(realm_str=realm_str))
    realm_link = f'<a href="{escape(url)}">{escape(realm_str)}</a>'
    return mark_safe(realm_link)


def realm_stats_link(realm_str: str) -> mark_safe:
    url = reverse(stats_for_realm, kwargs=dict(realm_str=realm_str))
    stats_link = f'<a href="{escape(url)}"><i class="fa fa-pie-chart"></i>{escape(realm_str)}</a>'
    return mark_safe(stats_link)


def remote_installation_stats_link(server_id: int, hostname: str) -> mark_safe:
    url = reverse(stats_for_remote_installation, kwargs=dict(remote_server_id=server_id))
    stats_link = f'<a href="{escape(url)}"><i class="fa fa-pie-chart"></i>{escape(hostname)}</a>'
    return mark_safe(stats_link)


def realm_client_table(user_summaries: Dict[str, Dict[str, Dict[str, Any]]]) -> str:
    exclude_keys = [
        "internal",
        "name",
        "use",
        "send",
        "pointer",
        "website",
        "desktop",
    ]

    rows = []
    for email, user_summary in user_summaries.items():
        email_link = user_activity_link(email)
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


def realm_user_summary_table(
    all_records: List[QuerySet], admin_emails: Set[str]
) -> Tuple[Dict[str, Dict[str, Any]], str]:
    user_records = {}

    def by_email(record: QuerySet) -> str:
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

    def is_recent(val: Optional[datetime]) -> bool:
        age = timezone_now() - val
        return age.total_seconds() < 5 * 60

    rows = []
    for email, user_summary in user_records.items():
        email_link = user_activity_link(email)
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
        all_records = list(get_user_activity_records_for_realm(realm_str, is_bot))

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
    return render(
        request,
        "analytics/activity.html",
        context=dict(data=data, realm_link=None, title=title),
    )


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
