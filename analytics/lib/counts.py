import logging
import time
from collections import OrderedDict, defaultdict
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Optional, Sequence, Tuple, Type, Union

from django.conf import settings
from django.db import connection, models
from psycopg2.sql import SQL, Composable, Identifier, Literal
from typing_extensions import TypeAlias, override

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
from zerver.models import Message, Realm, RealmAuditLog, Stream, UserActivityInterval, UserProfile

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
        interval: Optional[timedelta] = None,
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

    def last_successful_fill(self) -> Optional[datetime]:
        fillstate = FillState.objects.filter(property=self.property).first()
        if fillstate is None:
            return None
        if fillstate.state == FillState.DONE:
            return fillstate.end_time
        return fillstate.end_time - self.time_increment


class LoggingCountStat(CountStat):
    def __init__(self, property: str, output_table: Type[BaseCount], frequency: str) -> None:
        CountStat.__init__(self, property, DataCollector(output_table, None), frequency)


class DependentCountStat(CountStat):
    def __init__(
        self,
        property: str,
        data_collector: "DataCollector",
        frequency: str,
        interval: Optional[timedelta] = None,
        dependencies: Sequence[str] = [],
    ) -> None:
        CountStat.__init__(self, property, data_collector, frequency, interval=interval)
        self.dependencies = dependencies


class DataCollector:
    def __init__(
        self,
        output_table: Type[BaseCount],
        pull_function: Optional[Callable[[str, datetime, datetime, Optional[Realm]], int]],
    ) -> None:
        self.output_table = output_table
        self.pull_function = pull_function

    def depends_on_realm(self) -> bool:
        return self.output_table in (UserCount, StreamCount)


## CountStat-level operations ##


def process_count_stat(
    stat: CountStat, fill_to_time: datetime, realm: Optional[Realm] = None
) -> None:
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

    currently_filled = currently_filled + stat.time_increment
    while currently_filled <= fill_to_time:
        logger.info("START %s %s", stat.property, currently_filled)
        start = time.time()
        do_update_fill_state(fill_state, currently_filled, FillState.STARTED)
        do_fill_count_stat_at_hour(stat, currently_filled, realm)
        do_update_fill_state(fill_state, currently_filled, FillState.DONE)
        end = time.time()
        currently_filled = currently_filled + stat.time_increment
        logger.info("DONE %s (%dms)", stat.property, (end - start) * 1000)


def do_update_fill_state(fill_state: FillState, end_time: datetime, state: int) -> None:
    fill_state.end_time = end_time
    fill_state.state = state
    fill_state.save()


# We assume end_time is valid (e.g. is on a day or hour boundary as appropriate)
# and is time-zone-aware. It is the caller's responsibility to enforce this!
def do_fill_count_stat_at_hour(
    stat: CountStat, end_time: datetime, realm: Optional[Realm] = None
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
    stat: CountStat, end_time: datetime, realm: Optional[Realm] = None
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
    subgroup: Optional[Union[str, int, bool]],
    event_time: datetime,
    increment: int = 1,
) -> None:
    if not increment:
        return

    table = stat.data_collector.output_table
    id_args: Dict[str, Union[int, None]] = {}
    conflict_args: List[str] = []
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

QueryFn: TypeAlias = Callable[[Dict[str, Composable]], Composable]


def do_pull_by_sql_query(
    property: str,
    start_time: datetime,
    end_time: datetime,
    query: QueryFn,
    group_by: Optional[Tuple[Type[models.Model], str]],
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
    output_table: Type[BaseCount],
    query: QueryFn,
    group_by: Optional[Tuple[Type[models.Model], str]],
) -> DataCollector:
    def pull_function(
        property: str, start_time: datetime, end_time: datetime, realm: Optional[Realm] = None
    ) -> int:
        # The pull function type needs to accept a Realm argument
        # because the 'minutes_active::day' CountStat uses
        # DataCollector directly for do_pull_minutes_active, which
        # requires the realm argument.  We ignore it here, because the
        # realm should have been already encoded in the `query` we're
        # passed.
        return do_pull_by_sql_query(property, start_time, end_time, query, group_by)

    return DataCollector(output_table, pull_function)


def do_pull_minutes_active(
    property: str, start_time: datetime, end_time: datetime, realm: Optional[Realm] = None
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

    seconds_active: Dict[Tuple[int, int], float] = defaultdict(float)
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


def count_message_by_user_query(realm: Optional[Realm]) -> QueryFn:
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
def count_message_type_by_user_query(realm: Optional[Realm]) -> QueryFn:
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
                  zerver_recipient.type = 1 THEN 'private_message'
             WHEN
                  zerver_recipient.type = 3 THEN 'huddle_message'
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
        LEFT JOIN zerver_stream
        ON
            zerver_recipient.type_id = zerver_stream.id
        GROUP BY
            zerver_userprofile.realm_id, zerver_userprofile.id,
            zerver_recipient.type, zerver_stream.invite_only
    ) AS subquery
    GROUP BY realm_id, id, message_type
"""
    ).format(**kwargs, realm_clause=realm_clause)


# This query joins to the UserProfile table since all current queries that
# use this also subgroup on UserProfile.is_bot. If in the future there is a
# stat that counts messages by stream and doesn't need the UserProfile
# table, consider writing a new query for efficiency.
def count_message_by_stream_query(realm: Optional[Realm]) -> QueryFn:
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


# Hardcodes the query needed by active_users:is_bot:day, since that is
# currently the only stat that uses this.
def count_user_by_realm_query(realm: Optional[Realm]) -> QueryFn:
    if realm is None:
        realm_clause: Composable = SQL("")
    else:
        realm_clause = SQL("zerver_userprofile.realm_id = {} AND").format(Literal(realm.id))
    return lambda kwargs: SQL(
        """
    INSERT INTO analytics_realmcount
        (realm_id, value, property, subgroup, end_time)
    SELECT
        zerver_realm.id, count(*), %(property)s, {subgroup}, %(time_end)s
    FROM zerver_realm
    JOIN zerver_userprofile
    ON
        zerver_realm.id = zerver_userprofile.realm_id
    WHERE
        zerver_realm.date_created < %(time_end)s AND
        zerver_userprofile.date_joined >= %(time_start)s AND
        zerver_userprofile.date_joined < %(time_end)s AND
        {realm_clause}
        zerver_userprofile.is_active = TRUE
    GROUP BY zerver_realm.id {group_by_clause}
"""
    ).format(**kwargs, realm_clause=realm_clause)


# Currently hardcodes the query needed for active_users_audit:is_bot:day.
# Assumes that a user cannot have two RealmAuditLog entries with the same event_time and
# event_type in [RealmAuditLog.USER_CREATED, USER_DEACTIVATED, etc].
# In particular, it's important to ensure that migrations don't cause that to happen.
def check_realmauditlog_by_user_query(realm: Optional[Realm]) -> QueryFn:
    if realm is None:
        realm_clause: Composable = SQL("")
    else:
        realm_clause = SQL("realm_id = {} AND").format(Literal(realm.id))
    return lambda kwargs: SQL(
        """
    INSERT INTO analytics_usercount
        (user_id, realm_id, value, property, subgroup, end_time)
    SELECT
        ral1.modified_user_id, ral1.realm_id, 1, %(property)s, {subgroup}, %(time_end)s
    FROM zerver_realmauditlog ral1
    JOIN (
        SELECT modified_user_id, max(event_time) AS max_event_time
        FROM zerver_realmauditlog
        WHERE
            event_type in ({user_created}, {user_activated}, {user_deactivated}, {user_reactivated}) AND
            {realm_clause}
            event_time < %(time_end)s
        GROUP BY modified_user_id
    ) ral2
    ON
        ral1.event_time = max_event_time AND
        ral1.modified_user_id = ral2.modified_user_id
    JOIN zerver_userprofile
    ON
        ral1.modified_user_id = zerver_userprofile.id
    WHERE
        ral1.event_type in ({user_created}, {user_activated}, {user_reactivated})
    """
    ).format(
        **kwargs,
        user_created=Literal(RealmAuditLog.USER_CREATED),
        user_activated=Literal(RealmAuditLog.USER_ACTIVATED),
        user_deactivated=Literal(RealmAuditLog.USER_DEACTIVATED),
        user_reactivated=Literal(RealmAuditLog.USER_REACTIVATED),
        realm_clause=realm_clause,
    )


def check_useractivityinterval_by_user_query(realm: Optional[Realm]) -> QueryFn:
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


def count_realm_active_humans_query(realm: Optional[Realm]) -> QueryFn:
    if realm is None:
        realm_clause: Composable = SQL("")
    else:
        realm_clause = SQL("realm_id = {} AND").format(Literal(realm.id))
    return lambda kwargs: SQL(
        """
    INSERT INTO analytics_realmcount
        (realm_id, value, property, subgroup, end_time)
    SELECT
        usercount1.realm_id, count(*), %(property)s, NULL, %(time_end)s
    FROM (
        SELECT realm_id, user_id
        FROM analytics_usercount
        WHERE
            property = 'active_users_audit:is_bot:day' AND
            subgroup = 'false' AND
            {realm_clause}
            end_time = %(time_end)s
    ) usercount1
    JOIN (
        SELECT realm_id, user_id
        FROM analytics_usercount
        WHERE
            property = '15day_actives::day' AND
            {realm_clause}
            end_time = %(time_end)s
    ) usercount2
    ON
        usercount1.user_id = usercount2.user_id
    GROUP BY usercount1.realm_id
"""
    ).format(**kwargs, realm_clause=realm_clause)


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


def get_count_stats(realm: Optional[Realm] = None) -> Dict[str, CountStat]:
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
        # Number of users stats
        # Stats that count the number of active users in the UserProfile.is_active sense.
        # 'active_users_audit:is_bot:day' is the canonical record of which users were
        # active on which days (in the UserProfile.is_active sense).
        # Important that this stay a daily stat, so that 'realm_active_humans::day' works as expected.
        CountStat(
            "active_users_audit:is_bot:day",
            sql_data_collector(
                UserCount, check_realmauditlog_by_user_query(realm), (UserProfile, "is_bot")
            ),
            CountStat.DAY,
        ),
        # Important note: LoggingCountStat objects aren't passed the
        # Realm argument, because by nature they have a logging
        # structure, not a pull-from-database structure, so there's no
        # way to compute them for a single realm after the fact (the
        # use case for passing a Realm argument).
        # Sanity check on 'active_users_audit:is_bot:day', and a archetype for future LoggingCountStats.
        # In RealmCount, 'active_users_audit:is_bot:day' should be the partial
        # sum sequence of 'active_users_log:is_bot:day', for any realm that
        # started after the latter stat was introduced.
        # Included in LOGGING_COUNT_STAT_PROPERTIES_NOT_SENT_TO_BOUNCER.
        LoggingCountStat("active_users_log:is_bot:day", RealmCount, CountStat.DAY),
        # Another sanity check on 'active_users_audit:is_bot:day'. Is only an
        # approximation, e.g. if a user is deactivated between the end of the
        # day and when this stat is run, they won't be counted. However, is the
        # simplest of the three to inspect by hand.
        CountStat(
            "active_users:is_bot:day",
            sql_data_collector(
                RealmCount, count_user_by_realm_query(realm), (UserProfile, "is_bot")
            ),
            CountStat.DAY,
            interval=TIMEDELTA_MAX,
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
            dependencies=["active_users_audit:is_bot:day", "15day_actives::day"],
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
LOGGING_COUNT_STAT_PROPERTIES_NOT_SENT_TO_BOUNCER = [
    "invites_sent::day",
    "mobile_pushes_sent::day",
    "active_users_log:is_bot:day",
]

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
