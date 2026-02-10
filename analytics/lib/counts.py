import logging
import time
from collections import OrderedDict, defaultdict
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta, timezone
from typing import TypeAlias, Union

from django.conf import settings
from django.db import connection, models
from django.utils.timezone import now as timezone_now
from psycopg2.sql import SQL, Composable, Identifier, Literal
from typing_extensions import override

from analytics.models import (
    BaseCount,
    FillState,
    InstallationCount,
    RealmCount,
    StreamCount,
    UserCount,
    installation_epoch,
)
from zerver.lib.timestamp import ceiling_to_day, ceiling_to_hour, floor_to_hour, verify_UTC
from zerver.models import Message, Realm, Stream, UserActivityInterval, UserProfile
from zerver.models.realm_audit_logs import AuditLogEventType

if settings.ZILENCER_ENABLED:
    from zilencer.models import (
        RemoteInstallationCount,
        RemoteRealm,
        RemoteRealmCount,
        RemoteZulipServer,
    )


logger = logging.getLogger("zulip.analytics")


# You can't subtract timedelta.max from a datetime, so use this instead
TIMEDELTA_MAX = timedelta(days=365 * 1000)


## Class definitions ##


class CountStat:
    HOUR = "hour"
    DAY = "day"
    FREQUENCIES = frozenset([HOUR, DAY])

    @property
    def time_increment(self) -> timedelta:
        if self.frequency == CountStat.HOUR:
            return timedelta(hours=1)
        return timedelta(days=1)

    def __init__(
        self,
        property: str,
        data_collector: "DataCollector",
        frequency: str,
        interval: timedelta | None = None,
    ) -> None:
        self.property = property
        self.data_collector = data_collector
        # might have to do something different for bitfields
        if frequency not in self.FREQUENCIES:
            raise AssertionError(f"Unknown frequency: {frequency}")
        self.frequency = frequency
        if interval is not None:
            self.interval = interval
        else:
            self.interval = self.time_increment

    @override
    def __repr__(self) -> str:
        return f"<CountStat: {self.property}>"

    def last_successful_fill(self) -> datetime | None:
        fillstate = FillState.objects.filter(property=self.property).first()
        if fillstate is None:
            return None
        if fillstate.state == FillState.DONE:
            return fillstate.end_time
        return fillstate.end_time - self.time_increment

    def current_month_accumulated_count_for_user(self, user: UserProfile) -> int:
        now = timezone_now()
        start_of_month = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
        if now.month == 12:  # nocoverage
            start_of_next_month = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
        else:  # nocoverage
            start_of_next_month = datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc)

        # We just want to check we are not using BaseCount, otherwise all
        # `output_table` have `objects` property.
        assert self.data_collector.output_table == UserCount
        result = self.data_collector.output_table.objects.filter(  # type: ignore[attr-defined] # see above
            user=user,
            property=self.property,
            end_time__gt=start_of_month,
            end_time__lte=start_of_next_month,
        ).aggregate(models.Sum("value"))

        total_value = result["value__sum"] or 0
        return total_value


class LoggingCountStat(CountStat):
    def __init__(self, property: str, output_table: type[BaseCount], frequency: str) -> None:
        CountStat.__init__(self, property, DataCollector(output_table, None), frequency)


class DependentCountStat(CountStat):
    def __init__(
        self,
        property: str,
        data_collector: "DataCollector",
        frequency: str,
        interval: timedelta | None = None,
        dependencies: Sequence[str] = [],
    ) -> None:
        CountStat.__init__(self, property, data_collector, frequency, interval=interval)
        self.dependencies = dependencies


class DataCollector:
    def __init__(
        self,
        output_table: type[BaseCount],
        pull_function: Callable[[str, datetime, datetime, Realm | None], int] | None,
    ) -> None:
        self.output_table = output_table
        self.pull_function = pull_function

    def depends_on_realm(self) -> bool:
        return self.output_table in (UserCount, StreamCount)


## CountStat-level operations ##


def process_count_stat(stat: CountStat, fill_to_time: datetime, realm: Realm | None = None) -> None:
    # TODO: The realm argument is not yet supported, in that we don't
    # have a solution for how to update FillState if it is passed.  It
    # exists solely as partial plumbing for when we do fully implement
    # doing single-realm analytics runs for use cases like data import.
    #
    # Also, note that for the realm argument to be properly supported,
    # the CountStat object passed in needs to have come from
    # E.g. get_count_stats(realm), i.e. have the realm_id already
    # entered into the SQL query defined by the CountState object.
    verify_UTC(fill_to_time)
    if floor_to_hour(fill_to_time) != fill_to_time:
        raise ValueError(f"fill_to_time must be on an hour boundary: {fill_to_time}")

    fill_state = FillState.objects.filter(property=stat.property).first()
    if fill_state is None:
        currently_filled = installation_epoch()
        fill_state = FillState.objects.create(
            property=stat.property, end_time=currently_filled, state=FillState.DONE
        )
        logger.info("INITIALIZED %s %s", stat.property, currently_filled)
    elif fill_state.state == FillState.STARTED:
        logger.info("UNDO START %s %s", stat.property, fill_state.end_time)
        do_delete_counts_at_hour(stat, fill_state.end_time)
        currently_filled = fill_state.end_time - stat.time_increment
        do_update_fill_state(fill_state, currently_filled, FillState.DONE)
        logger.info("UNDO DONE %s", stat.property)
    elif fill_state.state == FillState.DONE:
        currently_filled = fill_state.end_time
    else:
        raise AssertionError(f"Unknown value for FillState.state: {fill_state.state}.")

    if isinstance(stat, DependentCountStat):
        for dependency in stat.dependencies:
            dependency_fill_time = COUNT_STATS[dependency].last_successful_fill()
            if dependency_fill_time is None:
                logger.warning(
                    "DependentCountStat %s run before dependency %s.", stat.property, dependency
                )
                return
            fill_to_time = min(fill_to_time, dependency_fill_time)

    currently_filled += stat.time_increment
    while currently_filled <= fill_to_time:
        logger.info("START %s %s", stat.property, currently_filled)
        start = time.time()
        do_update_fill_state(fill_state, currently_filled, FillState.STARTED)
        do_fill_count_stat_at_hour(stat, currently_filled, realm)
        do_update_fill_state(fill_state, currently_filled, FillState.DONE)
        end = time.time()
        currently_filled += stat.time_increment
        logger.info("DONE %s (%dms)", stat.property, (end - start) * 1000)


def do_update_fill_state(fill_state: FillState, end_time: datetime, state: int) -> None:
    fill_state.end_time = end_time
    fill_state.state = state
    fill_state.save()


# We assume end_time is valid (e.g. is on a day or hour boundary as appropriate)
# and is time-zone-aware. It is the caller's responsibility to enforce this!
def do_fill_count_stat_at_hour(
    stat: CountStat, end_time: datetime, realm: Realm | None = None
) -> None:
    start_time = end_time - stat.interval
    if not isinstance(stat, LoggingCountStat):
        timer = time.time()
        assert stat.data_collector.pull_function is not None
        rows_added = stat.data_collector.pull_function(stat.property, start_time, end_time, realm)
        logger.info(
            "%s run pull_function (%dms/%sr)",
            stat.property,
            (time.time() - timer) * 1000,
            rows_added,
        )
    do_aggregate_to_summary_table(stat, end_time, realm)


def do_delete_counts_at_hour(stat: CountStat, end_time: datetime) -> None:
    if isinstance(stat, LoggingCountStat):
        InstallationCount.objects.filter(property=stat.property, end_time=end_time).delete()
        if stat.data_collector.depends_on_realm():
            RealmCount.objects.filter(property=stat.property, end_time=end_time).delete()
    else:
        UserCount.objects.filter(property=stat.property, end_time=end_time).delete()
        StreamCount.objects.filter(property=stat.property, end_time=end_time).delete()
        RealmCount.objects.filter(property=stat.property, end_time=end_time).delete()
        InstallationCount.objects.filter(property=stat.property, end_time=end_time).delete()


def do_aggregate_to_summary_table(
    stat: CountStat, end_time: datetime, realm: Realm | None = None
) -> None:
    cursor = connection.cursor()

    # Aggregate into RealmCount
    output_table = stat.data_collector.output_table
    if realm is not None:
        realm_clause: Composable = SQL("AND zerver_realm.id = {}").format(Literal(realm.id))
    else:
        realm_clause = SQL("")

    if stat.data_collector.depends_on_realm():
        realmcount_query = SQL(
            """
            INSERT INTO analytics_realmcount
                (realm_id, value, property, subgroup, end_time)
            SELECT
                zerver_realm.id, COALESCE(sum({output_table}.value), 0), %(property)s,
                {output_table}.subgroup, %(end_time)s
            FROM zerver_realm
            JOIN {output_table}
            ON
                zerver_realm.id = {output_table}.realm_id
            WHERE
                {output_table}.property = %(property)s AND
                {output_table}.end_time = %(end_time)s
                {realm_clause}
            GROUP BY zerver_realm.id, {output_table}.subgroup
        """
        ).format(
            output_table=Identifier(output_table._meta.db_table),
            realm_clause=realm_clause,
        )
        start = time.time()
        cursor.execute(
            realmcount_query,
            {
                "property": stat.property,
                "end_time": end_time,
            },
        )
        end = time.time()
        logger.info(
            "%s RealmCount aggregation (%dms/%sr)",
            stat.property,
            (end - start) * 1000,
            cursor.rowcount,
        )

    if realm is None:
        # Aggregate into InstallationCount.  Only run if we just
        # processed counts for all realms.
        #
        # TODO: Add support for updating installation data after
        # changing an individual realm's values.
        installationcount_query = SQL(
            """
            INSERT INTO analytics_installationcount
                (value, property, subgroup, end_time)
            SELECT
                sum(value), %(property)s, analytics_realmcount.subgroup, %(end_time)s
            FROM analytics_realmcount
            WHERE
                property = %(property)s AND
                end_time = %(end_time)s
            GROUP BY analytics_realmcount.subgroup
        """
        )
        start = time.time()
        cursor.execute(
            installationcount_query,
            {
                "property": stat.property,
                "end_time": end_time,
            },
        )
        end = time.time()
        logger.info(
            "%s InstallationCount aggregation (%dms/%sr)",
            stat.property,
            (end - start) * 1000,
            cursor.rowcount,
        )

    cursor.close()


## Utility functions called from outside counts.py ##


# called from zerver.actions; should not throw any errors
def do_increment_logging_stat(
    model_object_for_bucket: Union[Realm, UserProfile, Stream, "RemoteRealm", "RemoteZulipServer"],
    stat: CountStat,
    subgroup: str | int | bool | None,
    event_time: datetime,
    increment: int = 1,
) -> None:
    if not increment:
        return

    table = stat.data_collector.output_table
    id_args: dict[str, int | None] = {}
    conflict_args: list[str] = []
    if table == RealmCount:
        assert isinstance(model_object_for_bucket, Realm)
        id_args = {"realm_id": model_object_for_bucket.id}
        conflict_args = ["realm_id"]
    elif table == UserCount:
        assert isinstance(model_object_for_bucket, UserProfile)
        id_args = {
            "realm_id": model_object_for_bucket.realm_id,
            "user_id": model_object_for_bucket.id,
        }
        conflict_args = ["user_id"]
    elif table == StreamCount:
        assert isinstance(model_object_for_bucket, Stream)
        id_args = {
            "realm_id": model_object_for_bucket.realm_id,
            "stream_id": model_object_for_bucket.id,
        }
        conflict_args = ["stream_id"]
    elif table == RemoteInstallationCount:
        assert isinstance(model_object_for_bucket, RemoteZulipServer)
        id_args = {"server_id": model_object_for_bucket.id, "remote_id": None}
        conflict_args = ["server_id"]
    elif table == RemoteRealmCount:
        assert isinstance(model_object_for_bucket, RemoteRealm)
        # For RemoteRealmCount (e.g. `mobile_pushes_forwarded::day`),
        # we have no `remote_id` nor `realm_id`, since they are not
        # imported from the remote server, which is the source of
        # truth of those two columns.  Their "ON CONFLICT" is thus the
        # only unique key we have, which is `remote_realm_id`, and not
        # `server_id` / `realm_id`.
        id_args = {
            "server_id": model_object_for_bucket.server_id,
            "remote_realm_id": model_object_for_bucket.id,
            "remote_id": None,
            "realm_id": None,
        }
        conflict_args = [
            "remote_realm_id",
        ]
    else:
        raise AssertionError("Unsupported CountStat output_table")

    if stat.frequency == CountStat.DAY:
        end_time = ceiling_to_day(event_time)
    elif stat.frequency == CountStat.HOUR:
        end_time = ceiling_to_hour(event_time)
    else:
        raise AssertionError("Unsupported CountStat frequency")

    is_subgroup: SQL = SQL("NULL")
    if subgroup is not None:
        is_subgroup = SQL("NOT NULL")
        # For backwards consistency, we cast the subgroup to a string
        # in Python; this emulates the behaviour of `get_or_create`,
        # which was previously used in this function, and performed
        # this cast because the `subgroup` column is defined as a
        # `CharField`.  Omitting this explicit cast causes a subgroup
        # of the boolean False to be passed as the PostgreSQL false,
        # which it stringifies as the lower-case `'false'`, not the
        # initial-case `'False'` if Python stringifies it.
        #
        # Other parts of the system (e.g. count_message_by_user_query)
        # already use PostgreSQL to cast bools to strings, resulting
        # in `subgroup` values of lower-case `'false'` -- for example
        # in `messages_sent:is_bot:hour`.  Fixing this inconsistency
        # via a migration is complicated by these records being
        # exchanged over the wire from remote servers.
        subgroup = str(subgroup)
        conflict_args.append("subgroup")

    id_column_names = SQL(", ").join(map(Identifier, id_args.keys()))
    id_values = SQL(", ").join(map(Literal, id_args.values()))
    conflict_columns = SQL(", ").join(map(Identifier, conflict_args))

    sql_query = SQL(
        """
        INSERT INTO {table_name}(property, subgroup, end_time, value, {id_column_names})
        VALUES (%s, %s, %s, %s, {id_values})
        ON CONFLICT (property, end_time, {conflict_columns})
        WHERE subgroup IS {is_subgroup}
        DO UPDATE SET
            value = {table_name}.value + EXCLUDED.value
        """
    ).format(
        table_name=Identifier(table._meta.db_table),
        id_column_names=id_column_names,
        id_values=id_values,
        conflict_columns=conflict_columns,
        is_subgroup=is_subgroup,
    )
    with connection.cursor() as cursor:
        cursor.execute(sql_query, [stat.property, subgroup, end_time, increment])


def do_drop_all_analytics_tables() -> None:
    UserCount.objects.all().delete()
    StreamCount.objects.all().delete()
    RealmCount.objects.all().delete()
    InstallationCount.objects.all().delete()
    FillState.objects.all().delete()


def do_drop_single_stat(property: str) -> None:
    UserCount.objects.filter(property=property).delete()
    StreamCount.objects.filter(property=property).delete()
    RealmCount.objects.filter(property=property).delete()
    InstallationCount.objects.filter(property=property).delete()
    FillState.objects.filter(property=property).delete()


## DataCollector-level operations ##

QueryFn: TypeAlias = Callable[[dict[str, Composable]], Composable]


def do_pull_by_sql_query(
    property: str,
    start_time: datetime,
    end_time: datetime,
    query: QueryFn,
    group_by: tuple[type[models.Model], str] | None,
) -> int:
    if group_by is None:
        subgroup: Composable = SQL("NULL")
        group_by_clause: Composable = SQL("")
    else:
        subgroup = Identifier(group_by[0]._meta.db_table, group_by[1])
        group_by_clause = SQL(", {}").format(subgroup)

    # We do string replacement here because cursor.execute will reject a
    # group_by_clause given as a param.
    # We pass in the datetimes as params to cursor.execute so that we don't have to
    # think about how to convert python datetimes to SQL datetimes.
    query_ = query(
        {
            "subgroup": subgroup,
            "group_by_clause": group_by_clause,
        }
    )
    cursor = connection.cursor()
    cursor.execute(
        query_,
        {
            "property": property,
            "time_start": start_time,
            "time_end": end_time,
        },
    )
    rowcount = cursor.rowcount
    cursor.close()
    return rowcount


def sql_data_collector(
    output_table: type[BaseCount],
    query: QueryFn,
    group_by: tuple[type[models.Model], str] | None,
) -> DataCollector:
    def pull_function(
        property: str, start_time: datetime, end_time: datetime, realm: Realm | None = None
    ) -> int:
        # The pull function type needs to accept a Realm argument
        # because the 'minutes_active::day' CountStat uses
        # DataCollector directly for do_pull_minutes_active, which
        # requires the realm argument.  We ignore it here, because the
        # realm should have been already encoded in the `query` we're
        # passed.
        return do_pull_by_sql_query(property, start_time, end_time, query, group_by)

    return DataCollector(output_table, pull_function)


def count_upload_space_used_by_realm_query(realm: Realm | None) -> QueryFn:
    if realm is None:
        realm_clause: Composable = SQL("")
    else:
        realm_clause = SQL("zerver_attachment.realm_id = {} AND").format(Literal(realm.id))

    # Note: This query currently has to go through the entire table,
    # summing all the sizes of attachments for every realm. This can be improved
    # by having a query which looks at the latest CountStat for each realm,
    # and sums it with only the new attachments.
    # There'd be additional complexity added by the fact that attachments can
    # also be deleted. Partially this can be accounted for by subtracting
    # ArchivedAttachment sizes, but there's still the issue of attachments
    # which can be directly deleted via the API.

    return lambda kwargs: SQL(
        """
            INSERT INTO analytics_realmcount (realm_id, property, end_time, value)
            SELECT
                zerver_attachment.realm_id,
                %(property)s,
                %(time_end)s,
                COALESCE(SUM(zerver_attachment.size), 0)
            FROM
                zerver_attachment
            WHERE
                {realm_clause}
                zerver_attachment.create_time < %(time_end)s
            GROUP BY
                zerver_attachment.realm_id
        """
    ).format(**kwargs, realm_clause=realm_clause)


def do_pull_minutes_active(
    property: str, start_time: datetime, end_time: datetime, realm: Realm | None = None
) -> int:
    user_activity_intervals = (
        UserActivityInterval.objects.filter(
            end__gt=start_time,
            start__lt=end_time,
        )
        .select_related(
            "user_profile",
        )
        .values_list("user_profile_id", "user_profile__realm_id", "start", "end")
    )

    seconds_active: dict[tuple[int, int], float] = defaultdict(float)
    for user_id, realm_id, interval_start, interval_end in user_activity_intervals:
        if realm is None or realm.id == realm_id:
            start = max(start_time, interval_start)
            end = min(end_time, interval_end)
            seconds_active[(user_id, realm_id)] += (end - start).total_seconds()

    rows = [
        UserCount(
            user_id=ids[0],
            realm_id=ids[1],
            property=property,
            end_time=end_time,
            value=int(seconds // 60),
        )
        for ids, seconds in seconds_active.items()
        if seconds >= 60
    ]
    UserCount.objects.bulk_create(rows)
    return len(rows)


def count_message_by_user_query(realm: Realm | None) -> QueryFn:
    if realm is None:
        realm_clause: Composable = SQL("")
    else:
        # We limit both userprofile and message so that we only see
        # users from this realm, but also get the performance speedup
        # of limiting messages by realm.
        realm_clause = SQL(
            "zerver_userprofile.realm_id = {} AND zerver_message.realm_id = {} AND"
        ).format(Literal(realm.id), Literal(realm.id))
    # Uses index: zerver_message_realm_date_sent (or the only-date index)
    return lambda kwargs: SQL(
        """
    INSERT INTO analytics_usercount
        (user_id, realm_id, value, property, subgroup, end_time)
    SELECT
        zerver_userprofile.id, zerver_userprofile.realm_id, count(*),
        %(property)s, {subgroup}, %(time_end)s
    FROM zerver_userprofile
    JOIN zerver_message
    ON
        zerver_userprofile.id = zerver_message.sender_id
    WHERE
        zerver_userprofile.date_joined < %(time_end)s AND
        zerver_message.date_sent >= %(time_start)s AND
        {realm_clause}
        zerver_message.date_sent < %(time_end)s
    GROUP BY zerver_userprofile.id {group_by_clause}
"""
    ).format(**kwargs, realm_clause=realm_clause)


# Note: ignores the group_by / group_by_clause.
def count_message_type_by_user_query(realm: Realm | None) -> QueryFn:
    if realm is None:
        realm_clause: Composable = SQL("")
    else:
        # We limit both userprofile and message so that we only see
        # users from this realm, but also get the performance speedup
        # of limiting messages by realm.
        realm_clause = SQL(
            "zerver_userprofile.realm_id = {} AND zerver_message.realm_id = {} AND"
        ).format(Literal(realm.id), Literal(realm.id))
    # Uses index: zerver_message_realm_date_sent (or the only-date index)
    return lambda kwargs: SQL(
        """
    INSERT INTO analytics_usercount
            (realm_id, user_id, value, property, subgroup, end_time)
    SELECT realm_id, id, SUM(count) AS value, %(property)s, message_type, %(time_end)s
    FROM
    (
        SELECT zerver_userprofile.realm_id, zerver_userprofile.id, count(*),
        CASE WHEN
                  zerver_recipient.type = 1 OR (zerver_recipient.type = 3 AND zerver_huddle.group_size <= 2) THEN 'private_message'
             WHEN
                  zerver_recipient.type = 3 AND zerver_huddle.group_size > 2 THEN 'huddle_message'
             WHEN
                  zerver_stream.invite_only = TRUE THEN 'private_stream'
             ELSE 'public_stream'
        END
        message_type

        FROM zerver_userprofile
        JOIN zerver_message
        ON
            zerver_userprofile.id = zerver_message.sender_id AND
            zerver_message.date_sent >= %(time_start)s AND
            {realm_clause}
            zerver_message.date_sent < %(time_end)s
        JOIN zerver_recipient
        ON
            zerver_message.recipient_id = zerver_recipient.id
        LEFT JOIN zerver_huddle
        ON
            zerver_recipient.type_id = zerver_huddle.id
        LEFT JOIN zerver_stream
        ON
            zerver_recipient.type_id = zerver_stream.id
        GROUP BY
            zerver_userprofile.realm_id, zerver_userprofile.id,
            zerver_recipient.type, zerver_stream.invite_only, zerver_huddle.group_size
    ) AS subquery
    GROUP BY realm_id, id, message_type
"""
    ).format(**kwargs, realm_clause=realm_clause)


# This query joins to the UserProfile table since all current queries that
# use this also subgroup on UserProfile.is_bot. If in the future there is a
# stat that counts messages by stream and doesn't need the UserProfile
# table, consider writing a new query for efficiency.
def count_message_by_stream_query(realm: Realm | None) -> QueryFn:
    if realm is None:
        realm_clause: Composable = SQL("")
    else:
        realm_clause = SQL(
            "zerver_stream.realm_id = {} AND zerver_message.realm_id = {} AND"
        ).format(Literal(realm.id), Literal(realm.id))
    # Uses index: zerver_message_realm_date_sent (or the only-date index)
    return lambda kwargs: SQL(
        """
    INSERT INTO analytics_streamcount
        (stream_id, realm_id, value, property, subgroup, end_time)
    SELECT
        zerver_stream.id, zerver_stream.realm_id, count(*), %(property)s, {subgroup}, %(time_end)s
    FROM zerver_stream
    JOIN zerver_recipient
    ON
        zerver_stream.id = zerver_recipient.type_id
    JOIN zerver_message
    ON
        zerver_recipient.id = zerver_message.recipient_id
    JOIN zerver_userprofile
    ON
        zerver_message.sender_id = zerver_userprofile.id
    WHERE
        zerver_stream.date_created < %(time_end)s AND
        zerver_recipient.type = 2 AND
        zerver_message.date_sent >= %(time_start)s AND
        {realm_clause}
        zerver_message.date_sent < %(time_end)s
    GROUP BY zerver_stream.id {group_by_clause}
"""
    ).format(**kwargs, realm_clause=realm_clause)


# Hardcodes the query needed for active_users_audit:is_bot:day.
# Assumes that a user cannot have two RealmAuditLog entries with the
# same event_time and event_type in [AuditLogEventType.USER_CREATED,
# USER_DEACTIVATED, etc].  In particular, it's important to ensure
# that migrations don't cause that to happen.
def check_realmauditlog_by_user_query(realm: Realm | None) -> QueryFn:
    if realm is None:
        realm_clause: Composable = SQL("")
    else:
        realm_clause = SQL("realm_id = {} AND").format(Literal(realm.id))
    return lambda kwargs: SQL(
        """
    INSERT INTO analytics_realmcount
        (realm_id, value, property, subgroup, end_time)
    SELECT
        zerver_userprofile.realm_id, count(*), %(property)s, {subgroup}, %(time_end)s
    FROM zerver_userprofile
    JOIN (
            SELECT DISTINCT ON (modified_user_id)
                    modified_user_id, event_type
            FROM
                    zerver_realmauditlog
            WHERE
                    event_type IN ({user_created}, {user_activated}, {user_deactivated}, {user_reactivated}) AND
                    {realm_clause}
                    event_time < %(time_end)s
            ORDER BY
                    modified_user_id,
                    event_time DESC
    ) last_user_event ON last_user_event.modified_user_id = zerver_userprofile.id
    WHERE
        last_user_event.event_type in ({user_created}, {user_activated}, {user_reactivated})
    GROUP BY zerver_userprofile.realm_id {group_by_clause}
    """
    ).format(
        **kwargs,
        user_created=Literal(AuditLogEventType.USER_CREATED),
        user_activated=Literal(AuditLogEventType.USER_ACTIVATED),
        user_deactivated=Literal(AuditLogEventType.USER_DEACTIVATED),
        user_reactivated=Literal(AuditLogEventType.USER_REACTIVATED),
        realm_clause=realm_clause,
    )


def check_useractivityinterval_by_user_query(realm: Realm | None) -> QueryFn:
    if realm is None:
        realm_clause: Composable = SQL("")
    else:
        realm_clause = SQL("zerver_userprofile.realm_id = {} AND").format(Literal(realm.id))
    return lambda kwargs: SQL(
        """
    INSERT INTO analytics_usercount
        (user_id, realm_id, value, property, subgroup, end_time)
    SELECT
        zerver_userprofile.id, zerver_userprofile.realm_id, 1, %(property)s, {subgroup}, %(time_end)s
    FROM zerver_userprofile
    JOIN zerver_useractivityinterval
    ON
        zerver_userprofile.id = zerver_useractivityinterval.user_profile_id
    WHERE
        zerver_useractivityinterval.end >= %(time_start)s AND
        {realm_clause}
        zerver_useractivityinterval.start < %(time_end)s
    GROUP BY zerver_userprofile.id {group_by_clause}
"""
    ).format(**kwargs, realm_clause=realm_clause)


def count_realm_active_humans_query(realm: Realm | None) -> QueryFn:
    if realm is None:
        realm_clause: Composable = SQL("")
    else:
        realm_clause = SQL("realm_id = {} AND").format(Literal(realm.id))
    return lambda kwargs: SQL(
        """
    INSERT INTO analytics_realmcount
        (realm_id, value, property, subgroup, end_time)
    SELECT
            active_usercount.realm_id, count(*), %(property)s, NULL, %(time_end)s
    FROM (
            SELECT
                    realm_id,
                    user_id
            FROM
                    analytics_usercount
            WHERE
                    property = '15day_actives::day'
                    {realm_clause}
                    AND end_time = %(time_end)s
    ) active_usercount
    JOIN zerver_userprofile ON active_usercount.user_id = zerver_userprofile.id
     AND active_usercount.realm_id = zerver_userprofile.realm_id
    JOIN (
            SELECT DISTINCT ON (modified_user_id)
                    modified_user_id, event_type
            FROM
                    zerver_realmauditlog
            WHERE
                    event_type IN ({user_created}, {user_activated}, {user_deactivated}, {user_reactivated})
                    AND event_time < %(time_end)s
            ORDER BY
                    modified_user_id,
                    event_time DESC
    ) last_user_event ON last_user_event.modified_user_id = active_usercount.user_id
    WHERE
            NOT zerver_userprofile.is_bot
            AND event_type IN ({user_created}, {user_activated}, {user_reactivated})
    GROUP BY
            active_usercount.realm_id
"""
    ).format(
        **kwargs,
        user_created=Literal(AuditLogEventType.USER_CREATED),
        user_activated=Literal(AuditLogEventType.USER_ACTIVATED),
        user_deactivated=Literal(AuditLogEventType.USER_DEACTIVATED),
        user_reactivated=Literal(AuditLogEventType.USER_REACTIVATED),
        realm_clause=realm_clause,
    )


# Currently unused and untested
count_stream_by_realm_query = lambda kwargs: SQL(
    """
    INSERT INTO analytics_realmcount
        (realm_id, value, property, subgroup, end_time)
    SELECT
        zerver_realm.id, count(*), %(property)s, {subgroup}, %(time_end)s
    FROM zerver_realm
    JOIN zerver_stream
    ON
        zerver_realm.id = zerver_stream.realm_id AND
    WHERE
        zerver_realm.date_created < %(time_end)s AND
        zerver_stream.date_created >= %(time_start)s AND
        zerver_stream.date_created < %(time_end)s
    GROUP BY zerver_realm.id {group_by_clause}
"""
).format(**kwargs)


def get_count_stats(realm: Realm | None = None) -> dict[str, CountStat]:
    ## CountStat declarations ##

    count_stats_ = [
        # Messages sent stats
        # Stats that count the number of messages sent in various ways.
        # These are also the set of stats that read from the Message table.
        CountStat(
            "messages_sent:is_bot:hour",
            sql_data_collector(
                UserCount, count_message_by_user_query(realm), (UserProfile, "is_bot")
            ),
            CountStat.HOUR,
        ),
        CountStat(
            "messages_sent:message_type:day",
            sql_data_collector(UserCount, count_message_type_by_user_query(realm), None),
            CountStat.DAY,
        ),
        CountStat(
            "messages_sent:client:day",
            sql_data_collector(
                UserCount, count_message_by_user_query(realm), (Message, "sending_client_id")
            ),
            CountStat.DAY,
        ),
        CountStat(
            "messages_in_stream:is_bot:day",
            sql_data_collector(
                StreamCount, count_message_by_stream_query(realm), (UserProfile, "is_bot")
            ),
            CountStat.DAY,
        ),
        # AI credit usage stats for users, in units of $1/10^9, which is safe for
        # aggregation because we're using bigints for the values.
        LoggingCountStat("ai_credit_usage::day", UserCount, CountStat.DAY),
        # Counts the number of active users in the UserProfile.is_active sense.
        # Important that this stay a daily stat, so that 'realm_active_humans::day' works as expected.
        CountStat(
            "active_users_audit:is_bot:day",
            sql_data_collector(
                RealmCount, check_realmauditlog_by_user_query(realm), (UserProfile, "is_bot")
            ),
            CountStat.DAY,
        ),
        CountStat(
            "upload_quota_used_bytes::day",
            sql_data_collector(RealmCount, count_upload_space_used_by_realm_query(realm), None),
            CountStat.DAY,
        ),
        # Messages read stats.  messages_read::hour is the total
        # number of messages read, whereas
        # messages_read_interactions::hour tries to count the total
        # number of UI interactions resulting in messages being marked
        # as read (imperfect because of batching of some request
        # types, but less likely to be overwhelmed by a single bulk
        # operation).
        LoggingCountStat("messages_read::hour", UserCount, CountStat.HOUR),
        LoggingCountStat("messages_read_interactions::hour", UserCount, CountStat.HOUR),
        # User activity stats
        # Stats that measure user activity in the UserActivityInterval sense.
        CountStat(
            "1day_actives::day",
            sql_data_collector(UserCount, check_useractivityinterval_by_user_query(realm), None),
            CountStat.DAY,
            interval=timedelta(days=1) - UserActivityInterval.MIN_INTERVAL_LENGTH,
        ),
        CountStat(
            "7day_actives::day",
            sql_data_collector(UserCount, check_useractivityinterval_by_user_query(realm), None),
            CountStat.DAY,
            interval=timedelta(days=7) - UserActivityInterval.MIN_INTERVAL_LENGTH,
        ),
        CountStat(
            "15day_actives::day",
            sql_data_collector(UserCount, check_useractivityinterval_by_user_query(realm), None),
            CountStat.DAY,
            interval=timedelta(days=15) - UserActivityInterval.MIN_INTERVAL_LENGTH,
        ),
        CountStat(
            "minutes_active::day", DataCollector(UserCount, do_pull_minutes_active), CountStat.DAY
        ),
        # Tracks the number of push notifications requested by the server.
        # Included in LOGGING_COUNT_STAT_PROPERTIES_NOT_SENT_TO_BOUNCER.
        LoggingCountStat(
            "mobile_pushes_sent::day",
            RealmCount,
            CountStat.DAY,
        ),
        # Rate limiting stats
        # Used to limit the number of invitation emails sent by a realm.
        # Included in LOGGING_COUNT_STAT_PROPERTIES_NOT_SENT_TO_BOUNCER.
        LoggingCountStat("invites_sent::day", RealmCount, CountStat.DAY),
        # Dependent stats
        # Must come after their dependencies.
        # Canonical account of the number of active humans in a realm on each day.
        DependentCountStat(
            "realm_active_humans::day",
            sql_data_collector(RealmCount, count_realm_active_humans_query(realm), None),
            CountStat.DAY,
            dependencies=["15day_actives::day"],
        ),
    ]

    if settings.ZILENCER_ENABLED:
        # See also the remote_installation versions of these in REMOTE_INSTALLATION_COUNT_STATS.
        count_stats_.append(
            LoggingCountStat(
                "mobile_pushes_received::day",
                RemoteRealmCount,
                CountStat.DAY,
            )
        )
        count_stats_.append(
            LoggingCountStat(
                "mobile_pushes_forwarded::day",
                RemoteRealmCount,
                CountStat.DAY,
            )
        )

    return OrderedDict((stat.property, stat) for stat in count_stats_)


# These properties are tracked by the bouncer itself and therefore syncing them
# from a remote server should not be allowed - or the server would be able to interfere
# with our data.
BOUNCER_ONLY_REMOTE_COUNT_STAT_PROPERTIES = [
    "mobile_pushes_received::day",
    "mobile_pushes_forwarded::day",
]

# LoggingCountStats with a daily duration and that are directly stored on
# the RealmCount table (instead of via aggregation in process_count_stat),
# can be in a state, after the hourly cron job to update analytics counts,
# where the logged value will be live-updated later (as the end time for
# the stat is still in the future). As these logging counts are designed
# to be used on the self-hosted installation for either debugging or rate
# limiting, sending these incomplete counts to the bouncer has low value.
LOGGING_COUNT_STAT_PROPERTIES_NOT_SENT_TO_BOUNCER = {
    "invites_sent::day",
    "mobile_pushes_sent::day",
    "active_users_log:is_bot:day",
    "active_users:is_bot:day",
}

# To avoid refactoring for now COUNT_STATS can be used as before
COUNT_STATS = get_count_stats()

REMOTE_INSTALLATION_COUNT_STATS = OrderedDict()

if settings.ZILENCER_ENABLED:
    # REMOTE_INSTALLATION_COUNT_STATS contains duplicates of the
    # RemoteRealmCount stats declared above; it is necessary because
    # pre-8.0 servers do not send the fields required to identify a
    # RemoteRealm.

    # Tracks the number of push notifications requested to be sent
    # by a remote server.
    REMOTE_INSTALLATION_COUNT_STATS["mobile_pushes_received::day"] = LoggingCountStat(
        "mobile_pushes_received::day",
        RemoteInstallationCount,
        CountStat.DAY,
    )
    # Tracks the number of push notifications successfully sent to
    # mobile devices, as requested by the remote server. Therefore
    # this should be less than or equal to mobile_pushes_received -
    # with potential tiny offsets resulting from a request being
    # *received* by the bouncer right before midnight, but *sent* to
    # the mobile device right after midnight. This would cause the
    # increments to happen to CountStat records for different days.
    REMOTE_INSTALLATION_COUNT_STATS["mobile_pushes_forwarded::day"] = LoggingCountStat(
        "mobile_pushes_forwarded::day",
        RemoteInstallationCount,
        CountStat.DAY,
    )

ALL_COUNT_STATS = OrderedDict(
    list(COUNT_STATS.items()) + list(REMOTE_INSTALLATION_COUNT_STATS.items())
)
