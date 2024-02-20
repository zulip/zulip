from contextlib import AbstractContextManager, ExitStack, contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterator, List, Optional, Tuple, Type
from unittest import mock

import orjson
import time_machine
from django.apps import apps
from django.db import models
from django.db.models import Sum
from django.test import override_settings
from django.utils.timezone import now as timezone_now
from psycopg2.sql import SQL, Literal
from typing_extensions import override

from analytics.lib.counts import (
    COUNT_STATS,
    CountStat,
    DependentCountStat,
    LoggingCountStat,
    do_aggregate_to_summary_table,
    do_drop_all_analytics_tables,
    do_drop_single_stat,
    do_fill_count_stat_at_hour,
    do_increment_logging_stat,
    get_count_stats,
    process_count_stat,
    sql_data_collector,
)
from analytics.models import (
    BaseCount,
    FillState,
    InstallationCount,
    RealmCount,
    StreamCount,
    UserCount,
    installation_epoch,
)
from zerver.actions.create_realm import do_create_realm
from zerver.actions.create_user import (
    do_activate_mirror_dummy_user,
    do_create_user,
    do_reactivate_user,
)
from zerver.actions.invites import do_invite_users, do_revoke_user_invite, do_send_user_invite_email
from zerver.actions.message_flags import (
    do_mark_all_as_read,
    do_mark_stream_messages_as_read,
    do_update_message_flags,
)
from zerver.actions.user_activity import update_user_activity_interval
from zerver.actions.users import do_deactivate_user
from zerver.lib.create_user import create_user
from zerver.lib.exceptions import InvitationError
from zerver.lib.push_notifications import (
    get_message_payload_apns,
    get_message_payload_gcm,
    hex_to_b64,
)
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.timestamp import TimeZoneNotUTCError, ceiling_to_day, floor_to_day
from zerver.lib.topic import DB_TOPIC_NAME
from zerver.lib.utils import assert_is_not_none
from zerver.models import (
    Client,
    Huddle,
    Message,
    NamedUserGroup,
    PreregistrationUser,
    Realm,
    RealmAuditLog,
    Recipient,
    Stream,
    UserActivityInterval,
    UserProfile,
)
from zerver.models.clients import get_client
from zerver.models.groups import SystemGroups
from zerver.models.scheduled_jobs import NotificationTriggers
from zerver.models.users import get_user, is_cross_realm_bot_email
from zilencer.models import (
    RemoteInstallationCount,
    RemotePushDeviceToken,
    RemoteRealm,
    RemoteRealmCount,
    RemoteZulipServer,
)
from zilencer.views import get_last_id_from_server


class AnalyticsTestCase(ZulipTestCase):
    MINUTE = timedelta(seconds=60)
    HOUR = MINUTE * 60
    DAY = HOUR * 24
    TIME_ZERO = datetime(1988, 3, 14, tzinfo=timezone.utc)
    TIME_LAST_HOUR = TIME_ZERO - HOUR

    @override
    def setUp(self) -> None:
        super().setUp()
        self.default_realm = do_create_realm(
            string_id="realmtest", name="Realm Test", date_created=self.TIME_ZERO - 2 * self.DAY
        )
        self.administrators_user_group = NamedUserGroup.objects.get(
            name=SystemGroups.ADMINISTRATORS,
            realm=self.default_realm,
            is_system_group=True,
        )

        # used to generate unique names in self.create_*
        self.name_counter = 100
        # used as defaults in self.assert_table_count
        self.current_property: Optional[str] = None

        # Delete RemoteRealm registrations to have a clean slate - the relevant
        # tests want to construct this from scratch.
        RemoteRealm.objects.all().delete()

    # Lightweight creation of users, streams, and messages
    def create_user(self, **kwargs: Any) -> UserProfile:
        self.name_counter += 1
        defaults = {
            "email": f"user{self.name_counter}@domain.tld",
            "date_joined": self.TIME_LAST_HOUR,
            "full_name": "full_name",
            "is_active": True,
            "is_bot": False,
            "realm": self.default_realm,
        }
        for key, value in defaults.items():
            kwargs[key] = kwargs.get(key, value)
        kwargs["delivery_email"] = kwargs["email"]
        with time_machine.travel(kwargs["date_joined"], tick=False):
            pass_kwargs: Dict[str, Any] = {}
            if kwargs["is_bot"]:
                pass_kwargs["bot_type"] = UserProfile.DEFAULT_BOT
                pass_kwargs["bot_owner"] = None
            return create_user(
                kwargs["email"],
                "password",
                kwargs["realm"],
                active=kwargs["is_active"],
                full_name=kwargs["full_name"],
                role=UserProfile.ROLE_REALM_ADMINISTRATOR,
                **pass_kwargs,
            )

    def create_stream_with_recipient(self, **kwargs: Any) -> Tuple[Stream, Recipient]:
        self.name_counter += 1
        defaults = {
            "name": f"stream name {self.name_counter}",
            "realm": self.default_realm,
            "date_created": self.TIME_LAST_HOUR,
            "can_remove_subscribers_group": self.administrators_user_group,
        }
        for key, value in defaults.items():
            kwargs[key] = kwargs.get(key, value)
        stream = Stream.objects.create(**kwargs)
        recipient = Recipient.objects.create(type_id=stream.id, type=Recipient.STREAM)
        stream.recipient = recipient
        stream.save(update_fields=["recipient"])
        return stream, recipient

    def create_huddle_with_recipient(self, **kwargs: Any) -> Tuple[Huddle, Recipient]:
        self.name_counter += 1
        defaults = {"huddle_hash": f"hash{self.name_counter}"}
        for key, value in defaults.items():
            kwargs[key] = kwargs.get(key, value)
        huddle = Huddle.objects.create(**kwargs)
        recipient = Recipient.objects.create(type_id=huddle.id, type=Recipient.DIRECT_MESSAGE_GROUP)
        huddle.recipient = recipient
        huddle.save(update_fields=["recipient"])
        return huddle, recipient

    def create_message(self, sender: UserProfile, recipient: Recipient, **kwargs: Any) -> Message:
        defaults = {
            "sender": sender,
            "recipient": recipient,
            DB_TOPIC_NAME: "subject",
            "content": "hi",
            "date_sent": self.TIME_LAST_HOUR,
            "sending_client": get_client("website"),
            "realm_id": sender.realm_id,
        }
        # For simplicity, this helper doesn't support creating cross-realm messages
        # since it'd require adding an additional realm argument.
        assert not is_cross_realm_bot_email(sender.delivery_email)

        for key, value in defaults.items():
            kwargs[key] = kwargs.get(key, value)
        return Message.objects.create(**kwargs)

    # kwargs should only ever be a UserProfile or Stream.
    def assert_table_count(
        self,
        table: Type[BaseCount],
        value: int,
        property: Optional[str] = None,
        subgroup: Optional[str] = None,
        end_time: datetime = TIME_ZERO,
        realm: Optional[Realm] = None,
        **kwargs: models.Model,
    ) -> None:
        if property is None:
            property = self.current_property
        queryset = table._default_manager.filter(property=property, end_time=end_time).filter(
            **kwargs
        )
        if table is not InstallationCount:
            if realm is None:
                realm = self.default_realm
            queryset = queryset.filter(realm=realm)
        if subgroup is not None:
            queryset = queryset.filter(subgroup=subgroup)
        self.assertEqual(queryset.values_list("value", flat=True)[0], value)

    def assertTableState(
        self, table: Type[BaseCount], arg_keys: List[str], arg_values: List[List[object]]
    ) -> None:
        """Assert that the state of a *Count table is what it should be.

        Example usage:
            self.assertTableState(RealmCount, ['property', 'subgroup', 'realm'],
                                  [['p1', 4], ['p2', 10, self.alt_realm]])

        table -- A *Count table.
        arg_keys -- List of columns of <table>.
        arg_values -- List of "rows" of <table>.
            Each entry of arg_values (e.g. ['p1', 4]) represents a row of <table>.
            The i'th value of the entry corresponds to the i'th arg_key, so e.g.
            the first arg_values entry here corresponds to a row of RealmCount
            with property='p1' and subgroup=10.
            Any columns not specified (in this case, every column of RealmCount
            other than property and subgroup) are either set to default values,
            or are ignored.

        The function checks that every entry of arg_values matches exactly one
        row of <table>, and that no additional rows exist. Note that this means
        checking a table with duplicate rows is not supported.
        """
        defaults = {
            "property": self.current_property,
            "subgroup": None,
            "end_time": self.TIME_ZERO,
            "value": 1,
        }
        for values in arg_values:
            kwargs: Dict[str, Any] = {}
            for i in range(len(values)):
                kwargs[arg_keys[i]] = values[i]
            for key, value in defaults.items():
                kwargs[key] = kwargs.get(key, value)
            if (
                table not in [InstallationCount, RemoteInstallationCount, RemoteRealmCount]
                and "realm" not in kwargs
            ):
                if "user" in kwargs:
                    kwargs["realm"] = kwargs["user"].realm
                elif "stream" in kwargs:
                    kwargs["realm"] = kwargs["stream"].realm
                else:
                    kwargs["realm"] = self.default_realm
            self.assertEqual(table._default_manager.filter(**kwargs).count(), 1)
        self.assert_length(arg_values, table._default_manager.count())


class TestProcessCountStat(AnalyticsTestCase):
    def make_dummy_count_stat(self, property: str) -> CountStat:
        query = lambda kwargs: SQL(
            """
            INSERT INTO analytics_realmcount (realm_id, value, property, end_time)
            VALUES ({default_realm_id}, 1, {property}, %(time_end)s)
        """
        ).format(
            default_realm_id=Literal(self.default_realm.id),
            property=Literal(property),
        )
        return CountStat(property, sql_data_collector(RealmCount, query, None), CountStat.HOUR)

    def assertFillStateEquals(
        self, stat: CountStat, end_time: datetime, state: int = FillState.DONE
    ) -> None:
        fill_state = FillState.objects.filter(property=stat.property).first()
        assert fill_state is not None
        self.assertEqual(fill_state.end_time, end_time)
        self.assertEqual(fill_state.state, state)

    def test_process_stat(self) -> None:
        # process new stat
        current_time = installation_epoch() + self.HOUR
        stat = self.make_dummy_count_stat("test stat")
        process_count_stat(stat, current_time)
        self.assertFillStateEquals(stat, current_time)
        self.assertEqual(InstallationCount.objects.filter(property=stat.property).count(), 1)

        # dirty stat
        FillState.objects.filter(property=stat.property).update(state=FillState.STARTED)
        process_count_stat(stat, current_time)
        self.assertFillStateEquals(stat, current_time)
        self.assertEqual(InstallationCount.objects.filter(property=stat.property).count(), 1)

        # clean stat, no update
        process_count_stat(stat, current_time)
        self.assertFillStateEquals(stat, current_time)
        self.assertEqual(InstallationCount.objects.filter(property=stat.property).count(), 1)

        # clean stat, with update
        current_time = current_time + self.HOUR
        stat = self.make_dummy_count_stat("test stat")
        process_count_stat(stat, current_time)
        self.assertFillStateEquals(stat, current_time)
        self.assertEqual(InstallationCount.objects.filter(property=stat.property).count(), 2)

    def test_bad_fill_to_time(self) -> None:
        stat = self.make_dummy_count_stat("test stat")
        with self.assertRaises(ValueError):
            process_count_stat(stat, installation_epoch() + 65 * self.MINUTE)
        with self.assertRaises(TimeZoneNotUTCError):
            process_count_stat(stat, installation_epoch().replace(tzinfo=None))

    # This tests the LoggingCountStat branch of the code in do_delete_counts_at_hour.
    # It is important that do_delete_counts_at_hour not delete any of the collected
    # logging data!
    def test_process_logging_stat(self) -> None:
        end_time = self.TIME_ZERO

        user_stat = LoggingCountStat("user stat", UserCount, CountStat.DAY)
        stream_stat = LoggingCountStat("stream stat", StreamCount, CountStat.DAY)
        realm_stat = LoggingCountStat("realm stat", RealmCount, CountStat.DAY)
        user = self.create_user()
        stream = self.create_stream_with_recipient()[0]
        realm = self.default_realm
        UserCount.objects.create(
            user=user, realm=realm, property=user_stat.property, end_time=end_time, value=5
        )
        StreamCount.objects.create(
            stream=stream, realm=realm, property=stream_stat.property, end_time=end_time, value=5
        )
        RealmCount.objects.create(
            realm=realm, property=realm_stat.property, end_time=end_time, value=5
        )

        # Normal run of process_count_stat
        for stat in [user_stat, stream_stat, realm_stat]:
            process_count_stat(stat, end_time)
        self.assertTableState(UserCount, ["property", "value"], [[user_stat.property, 5]])
        self.assertTableState(StreamCount, ["property", "value"], [[stream_stat.property, 5]])
        self.assertTableState(
            RealmCount,
            ["property", "value"],
            [[user_stat.property, 5], [stream_stat.property, 5], [realm_stat.property, 5]],
        )
        self.assertTableState(
            InstallationCount,
            ["property", "value"],
            [[user_stat.property, 5], [stream_stat.property, 5], [realm_stat.property, 5]],
        )

        # Change the logged data and mark FillState as dirty
        UserCount.objects.update(value=6)
        StreamCount.objects.update(value=6)
        RealmCount.objects.filter(property=realm_stat.property).update(value=6)
        FillState.objects.update(state=FillState.STARTED)

        # Check that the change propagated (and the collected data wasn't deleted)
        for stat in [user_stat, stream_stat, realm_stat]:
            process_count_stat(stat, end_time)
        self.assertTableState(UserCount, ["property", "value"], [[user_stat.property, 6]])
        self.assertTableState(StreamCount, ["property", "value"], [[stream_stat.property, 6]])
        self.assertTableState(
            RealmCount,
            ["property", "value"],
            [[user_stat.property, 6], [stream_stat.property, 6], [realm_stat.property, 6]],
        )
        self.assertTableState(
            InstallationCount,
            ["property", "value"],
            [[user_stat.property, 6], [stream_stat.property, 6], [realm_stat.property, 6]],
        )

    def test_process_dependent_stat(self) -> None:
        stat1 = self.make_dummy_count_stat("stat1")
        stat2 = self.make_dummy_count_stat("stat2")
        query = lambda kwargs: SQL(
            """
            INSERT INTO analytics_realmcount (realm_id, value, property, end_time)
            VALUES ({default_realm_id}, 1, {property}, %(time_end)s)
        """
        ).format(
            default_realm_id=Literal(self.default_realm.id),
            property=Literal("stat3"),
        )
        stat3 = DependentCountStat(
            "stat3",
            sql_data_collector(RealmCount, query, None),
            CountStat.HOUR,
            dependencies=["stat1", "stat2"],
        )

        query = lambda kwargs: SQL(
            """
            INSERT INTO analytics_realmcount (realm_id, value, property, end_time)
            VALUES ({default_realm_id}, 1, {property}, %(time_end)s)
        """
        ).format(
            default_realm_id=Literal(self.default_realm.id),
            property=Literal("stat4"),
        )
        stat4 = DependentCountStat(
            "stat4",
            sql_data_collector(RealmCount, query, None),
            CountStat.DAY,
            dependencies=["stat1", "stat2"],
        )

        dummy_count_stats = {
            "stat1": stat1,
            "stat2": stat2,
            "stat3": stat3,
            "stat4": stat4,
        }
        with mock.patch("analytics.lib.counts.COUNT_STATS", dummy_count_stats):
            hour = [installation_epoch() + i * self.HOUR for i in range(5)]

            # test when one dependency has been run, and the other hasn't
            process_count_stat(stat1, hour[2])
            process_count_stat(stat3, hour[1])
            self.assertTableState(
                InstallationCount,
                ["property", "end_time"],
                [["stat1", hour[1]], ["stat1", hour[2]]],
            )
            self.assertFillStateEquals(stat3, hour[0])

            # test that we don't fill past the fill_to_time argument, even if
            # dependencies have later last_successful_fill
            process_count_stat(stat2, hour[3])
            process_count_stat(stat3, hour[1])
            self.assertTableState(
                InstallationCount,
                ["property", "end_time"],
                [
                    ["stat1", hour[1]],
                    ["stat1", hour[2]],
                    ["stat2", hour[1]],
                    ["stat2", hour[2]],
                    ["stat2", hour[3]],
                    ["stat3", hour[1]],
                ],
            )
            self.assertFillStateEquals(stat3, hour[1])

            # test that we don't fill past the dependency last_successful_fill times,
            # even if fill_to_time is later
            process_count_stat(stat3, hour[4])
            self.assertTableState(
                InstallationCount,
                ["property", "end_time"],
                [
                    ["stat1", hour[1]],
                    ["stat1", hour[2]],
                    ["stat2", hour[1]],
                    ["stat2", hour[2]],
                    ["stat2", hour[3]],
                    ["stat3", hour[1]],
                    ["stat3", hour[2]],
                ],
            )
            self.assertFillStateEquals(stat3, hour[2])

            # test daily dependent stat with hourly dependencies
            hour24 = installation_epoch() + 24 * self.HOUR
            hour25 = installation_epoch() + 25 * self.HOUR
            process_count_stat(stat1, hour25)
            process_count_stat(stat2, hour25)
            process_count_stat(stat4, hour25)
            self.assertEqual(InstallationCount.objects.filter(property="stat4").count(), 1)
            self.assertFillStateEquals(stat4, hour24)


class TestCountStats(AnalyticsTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        # This tests two things for each of the queries/CountStats: Handling
        # more than 1 realm, and the time bounds (time_start and time_end in
        # the queries).
        self.second_realm = do_create_realm(
            string_id="second-realm",
            name="Second Realm",
            date_created=self.TIME_ZERO - 2 * self.DAY,
        )

        for minutes_ago in [0, 1, 61, 60 * 24 + 1]:
            creation_time = self.TIME_ZERO - minutes_ago * self.MINUTE
            user = self.create_user(
                email=f"user-{minutes_ago}@second.analytics",
                realm=self.second_realm,
                date_joined=creation_time,
            )
            recipient = self.create_stream_with_recipient(
                name=f"stream {minutes_ago}", realm=self.second_realm, date_created=creation_time
            )[1]
            self.create_message(user, recipient, date_sent=creation_time)
        self.hourly_user = get_user("user-1@second.analytics", self.second_realm)
        self.daily_user = get_user("user-61@second.analytics", self.second_realm)

        # This realm should not show up in the *Count tables for any of the
        # messages_* CountStats
        self.no_message_realm = do_create_realm(
            string_id="no-message-realm",
            name="No Message Realm",
            date_created=self.TIME_ZERO - 2 * self.DAY,
        )

        self.create_user(realm=self.no_message_realm)
        self.create_stream_with_recipient(realm=self.no_message_realm)
        # This huddle should not show up anywhere
        self.create_huddle_with_recipient()

    def test_active_users_by_is_bot(self) -> None:
        stat = COUNT_STATS["active_users:is_bot:day"]
        self.current_property = stat.property

        # To be included
        self.create_user(is_bot=True)
        self.create_user(is_bot=True, date_joined=self.TIME_ZERO - 25 * self.HOUR)
        self.create_user(is_bot=False)

        # To be excluded
        self.create_user(is_active=False)

        do_fill_count_stat_at_hour(stat, self.TIME_ZERO)

        self.assertTableState(
            RealmCount,
            ["value", "subgroup", "realm"],
            [
                [2, "true"],
                [1, "false"],
                [3, "false", self.second_realm],
                [1, "false", self.no_message_realm],
            ],
        )
        self.assertTableState(InstallationCount, ["value", "subgroup"], [[2, "true"], [5, "false"]])
        self.assertTableState(UserCount, [], [])
        self.assertTableState(StreamCount, [], [])

    def test_active_users_by_is_bot_for_realm_constraint(self) -> None:
        # For single Realm

        COUNT_STATS = get_count_stats(self.default_realm)
        stat = COUNT_STATS["active_users:is_bot:day"]
        self.current_property = stat.property

        # To be included
        self.create_user(is_bot=True, date_joined=self.TIME_ZERO - 25 * self.HOUR)
        self.create_user(is_bot=False)

        # To be excluded
        self.create_user(
            email="test@second.analytics",
            realm=self.second_realm,
            date_joined=self.TIME_ZERO - 2 * self.DAY,
        )

        do_fill_count_stat_at_hour(stat, self.TIME_ZERO, self.default_realm)
        self.assertTableState(RealmCount, ["value", "subgroup"], [[1, "true"], [1, "false"]])
        # No aggregation to InstallationCount with realm constraint
        self.assertTableState(InstallationCount, ["value", "subgroup"], [])
        self.assertTableState(UserCount, [], [])
        self.assertTableState(StreamCount, [], [])

    def test_messages_sent_by_is_bot(self) -> None:
        stat = COUNT_STATS["messages_sent:is_bot:hour"]
        self.current_property = stat.property

        bot = self.create_user(is_bot=True)
        human1 = self.create_user()
        human2 = self.create_user()
        recipient_human1 = Recipient.objects.get(type_id=human1.id, type=Recipient.PERSONAL)

        recipient_stream = self.create_stream_with_recipient()[1]
        recipient_huddle = self.create_huddle_with_recipient()[1]

        self.create_message(bot, recipient_human1)
        self.create_message(bot, recipient_stream)
        self.create_message(bot, recipient_huddle)
        self.create_message(human1, recipient_human1)
        self.create_message(human2, recipient_human1)

        do_fill_count_stat_at_hour(stat, self.TIME_ZERO)

        self.assertTableState(
            UserCount,
            ["value", "subgroup", "user"],
            [
                [1, "false", human1],
                [1, "false", human2],
                [3, "true", bot],
                [1, "false", self.hourly_user],
            ],
        )
        self.assertTableState(
            RealmCount,
            ["value", "subgroup", "realm"],
            [[2, "false"], [3, "true"], [1, "false", self.second_realm]],
        )
        self.assertTableState(InstallationCount, ["value", "subgroup"], [[3, "false"], [3, "true"]])
        self.assertTableState(StreamCount, [], [])

    def test_messages_sent_by_is_bot_realm_constraint(self) -> None:
        # For single Realm

        COUNT_STATS = get_count_stats(self.default_realm)
        stat = COUNT_STATS["messages_sent:is_bot:hour"]
        self.current_property = stat.property

        bot = self.create_user(is_bot=True)
        human1 = self.create_user()
        human2 = self.create_user()
        recipient_human1 = Recipient.objects.get(type_id=human1.id, type=Recipient.PERSONAL)

        recipient_stream = self.create_stream_with_recipient()[1]
        recipient_huddle = self.create_huddle_with_recipient()[1]

        # To be included
        self.create_message(bot, recipient_human1)
        self.create_message(bot, recipient_stream)
        self.create_message(bot, recipient_huddle)
        self.create_message(human1, recipient_human1)
        self.create_message(human2, recipient_human1)

        # To be excluded
        self.create_message(self.hourly_user, recipient_human1)
        self.create_message(self.hourly_user, recipient_stream)
        self.create_message(self.hourly_user, recipient_huddle)

        do_fill_count_stat_at_hour(stat, self.TIME_ZERO, self.default_realm)

        self.assertTableState(
            UserCount,
            ["value", "subgroup", "user"],
            [[1, "false", human1], [1, "false", human2], [3, "true", bot]],
        )
        self.assertTableState(
            RealmCount,
            ["value", "subgroup", "realm"],
            [[2, "false", self.default_realm], [3, "true", self.default_realm]],
        )
        # No aggregation to InstallationCount with realm constraint
        self.assertTableState(InstallationCount, ["value", "subgroup"], [])
        self.assertTableState(StreamCount, [], [])

    def test_messages_sent_by_message_type(self) -> None:
        stat = COUNT_STATS["messages_sent:message_type:day"]
        self.current_property = stat.property

        # Nothing currently in this stat that is bot related, but so many of
        # the rest of our stats make the human/bot distinction that one can
        # imagine a later refactoring that will intentionally or
        # unintentionally change this. So make one of our users a bot.
        user1 = self.create_user(is_bot=True)
        user2 = self.create_user()
        user3 = self.create_user()

        # private streams
        recipient_stream1 = self.create_stream_with_recipient(invite_only=True)[1]
        recipient_stream2 = self.create_stream_with_recipient(invite_only=True)[1]
        self.create_message(user1, recipient_stream1)
        self.create_message(user2, recipient_stream1)
        self.create_message(user2, recipient_stream2)

        # public streams
        recipient_stream3 = self.create_stream_with_recipient()[1]
        recipient_stream4 = self.create_stream_with_recipient()[1]
        self.create_message(user1, recipient_stream3)
        self.create_message(user1, recipient_stream4)
        self.create_message(user2, recipient_stream3)

        # huddles
        recipient_huddle1 = self.create_huddle_with_recipient()[1]
        recipient_huddle2 = self.create_huddle_with_recipient()[1]
        self.create_message(user1, recipient_huddle1)
        self.create_message(user2, recipient_huddle2)

        # direct messages
        recipient_user1 = Recipient.objects.get(type_id=user1.id, type=Recipient.PERSONAL)
        recipient_user2 = Recipient.objects.get(type_id=user2.id, type=Recipient.PERSONAL)
        recipient_user3 = Recipient.objects.get(type_id=user3.id, type=Recipient.PERSONAL)
        self.create_message(user1, recipient_user2)
        self.create_message(user2, recipient_user1)
        self.create_message(user3, recipient_user3)

        do_fill_count_stat_at_hour(stat, self.TIME_ZERO)

        self.assertTableState(
            UserCount,
            ["value", "subgroup", "user"],
            [
                [1, "private_stream", user1],
                [2, "private_stream", user2],
                [2, "public_stream", user1],
                [1, "public_stream", user2],
                [1, "private_message", user1],
                [1, "private_message", user2],
                [1, "private_message", user3],
                [1, "huddle_message", user1],
                [1, "huddle_message", user2],
                [1, "public_stream", self.hourly_user],
                [1, "public_stream", self.daily_user],
            ],
        )
        self.assertTableState(
            RealmCount,
            ["value", "subgroup", "realm"],
            [
                [3, "private_stream"],
                [3, "public_stream"],
                [3, "private_message"],
                [2, "huddle_message"],
                [2, "public_stream", self.second_realm],
            ],
        )
        self.assertTableState(
            InstallationCount,
            ["value", "subgroup"],
            [
                [3, "private_stream"],
                [5, "public_stream"],
                [3, "private_message"],
                [2, "huddle_message"],
            ],
        )
        self.assertTableState(StreamCount, [], [])

    def test_messages_sent_by_message_type_realm_constraint(self) -> None:
        # For single Realm

        COUNT_STATS = get_count_stats(self.default_realm)
        stat = COUNT_STATS["messages_sent:message_type:day"]
        self.current_property = stat.property

        user = self.create_user()
        user_recipient = Recipient.objects.get(type_id=user.id, type=Recipient.PERSONAL)
        private_stream_recipient = self.create_stream_with_recipient(invite_only=True)[1]
        stream_recipient = self.create_stream_with_recipient()[1]
        huddle_recipient = self.create_huddle_with_recipient()[1]

        # To be included
        self.create_message(user, user_recipient)
        self.create_message(user, private_stream_recipient)
        self.create_message(user, stream_recipient)
        self.create_message(user, huddle_recipient)

        do_fill_count_stat_at_hour(stat, self.TIME_ZERO, self.default_realm)

        # To be excluded
        self.create_message(self.hourly_user, user_recipient)
        self.create_message(self.hourly_user, private_stream_recipient)
        self.create_message(self.hourly_user, stream_recipient)
        self.create_message(self.hourly_user, huddle_recipient)

        self.assertTableState(
            UserCount,
            ["value", "subgroup", "user"],
            [
                [1, "private_message", user],
                [1, "private_stream", user],
                [1, "huddle_message", user],
                [1, "public_stream", user],
            ],
        )
        self.assertTableState(
            RealmCount,
            ["value", "subgroup"],
            [
                [1, "private_message"],
                [1, "private_stream"],
                [1, "public_stream"],
                [1, "huddle_message"],
            ],
        )
        # No aggregation to InstallationCount with realm constraint
        self.assertTableState(InstallationCount, ["value", "subgroup"], [])
        self.assertTableState(StreamCount, [], [])

    def test_messages_sent_to_recipients_with_same_id(self) -> None:
        stat = COUNT_STATS["messages_sent:message_type:day"]
        self.current_property = stat.property

        user = self.create_user(id=1000)
        user_recipient = Recipient.objects.get(type_id=user.id, type=Recipient.PERSONAL)
        stream_recipient = self.create_stream_with_recipient(id=1000)[1]
        huddle_recipient = self.create_huddle_with_recipient(id=1000)[1]

        self.create_message(user, user_recipient)
        self.create_message(user, stream_recipient)
        self.create_message(user, huddle_recipient)

        do_fill_count_stat_at_hour(stat, self.TIME_ZERO)

        self.assert_table_count(UserCount, 1, subgroup="private_message")
        self.assert_table_count(UserCount, 1, subgroup="huddle_message")
        self.assert_table_count(UserCount, 1, subgroup="public_stream")

    def test_messages_sent_by_client(self) -> None:
        stat = COUNT_STATS["messages_sent:client:day"]
        self.current_property = stat.property

        user1 = self.create_user(is_bot=True)
        user2 = self.create_user()
        recipient_user2 = Recipient.objects.get(type_id=user2.id, type=Recipient.PERSONAL)

        recipient_stream = self.create_stream_with_recipient()[1]
        recipient_huddle = self.create_huddle_with_recipient()[1]

        client2 = Client.objects.create(name="client2")

        self.create_message(user1, recipient_user2, sending_client=client2)
        self.create_message(user1, recipient_stream)
        self.create_message(user1, recipient_huddle)
        self.create_message(user2, recipient_user2, sending_client=client2)
        self.create_message(user2, recipient_user2, sending_client=client2)

        do_fill_count_stat_at_hour(stat, self.TIME_ZERO)

        client2_id = str(client2.id)
        website_client_id = str(get_client("website").id)  # default for self.create_message
        self.assertTableState(
            UserCount,
            ["value", "subgroup", "user"],
            [
                [2, website_client_id, user1],
                [1, client2_id, user1],
                [2, client2_id, user2],
                [1, website_client_id, self.hourly_user],
                [1, website_client_id, self.daily_user],
            ],
        )
        self.assertTableState(
            RealmCount,
            ["value", "subgroup", "realm"],
            [[2, website_client_id], [3, client2_id], [2, website_client_id, self.second_realm]],
        )
        self.assertTableState(
            InstallationCount, ["value", "subgroup"], [[4, website_client_id], [3, client2_id]]
        )
        self.assertTableState(StreamCount, [], [])

    def test_messages_sent_by_client_realm_constraint(self) -> None:
        # For single Realm

        COUNT_STATS = get_count_stats(self.default_realm)
        stat = COUNT_STATS["messages_sent:client:day"]
        self.current_property = stat.property

        user1 = self.create_user(is_bot=True)
        user2 = self.create_user()
        recipient_user2 = Recipient.objects.get(type_id=user2.id, type=Recipient.PERSONAL)

        client2 = Client.objects.create(name="client2")

        # TO be included
        self.create_message(user1, recipient_user2, sending_client=client2)
        self.create_message(user2, recipient_user2, sending_client=client2)
        self.create_message(user2, recipient_user2)

        # To be excluded
        self.create_message(self.hourly_user, recipient_user2, sending_client=client2)
        self.create_message(self.hourly_user, recipient_user2, sending_client=client2)
        self.create_message(self.hourly_user, recipient_user2)

        do_fill_count_stat_at_hour(stat, self.TIME_ZERO, self.default_realm)

        client2_id = str(client2.id)
        website_client_id = str(get_client("website").id)  # default for self.create_message
        self.assertTableState(
            UserCount,
            ["value", "subgroup", "user"],
            [[1, client2_id, user1], [1, client2_id, user2], [1, website_client_id, user2]],
        )
        self.assertTableState(
            RealmCount, ["value", "subgroup"], [[1, website_client_id], [2, client2_id]]
        )
        # No aggregation to InstallationCount with realm constraint
        self.assertTableState(InstallationCount, ["value", "subgroup"], [])
        self.assertTableState(StreamCount, [], [])

    def test_messages_sent_to_stream_by_is_bot(self) -> None:
        stat = COUNT_STATS["messages_in_stream:is_bot:day"]
        self.current_property = stat.property

        bot = self.create_user(is_bot=True)
        human1 = self.create_user()
        human2 = self.create_user()
        recipient_human1 = Recipient.objects.get(type_id=human1.id, type=Recipient.PERSONAL)

        stream1, recipient_stream1 = self.create_stream_with_recipient()
        stream2, recipient_stream2 = self.create_stream_with_recipient()

        # To be included
        self.create_message(human1, recipient_stream1)
        self.create_message(human2, recipient_stream1)
        self.create_message(human1, recipient_stream2)
        self.create_message(bot, recipient_stream2)
        self.create_message(bot, recipient_stream2)

        # To be excluded
        self.create_message(human2, recipient_human1)
        self.create_message(bot, recipient_human1)
        recipient_huddle = self.create_huddle_with_recipient()[1]
        self.create_message(human1, recipient_huddle)

        do_fill_count_stat_at_hour(stat, self.TIME_ZERO)

        self.assertTableState(
            StreamCount,
            ["value", "subgroup", "stream"],
            [
                [2, "false", stream1],
                [1, "false", stream2],
                [2, "true", stream2],
                # "hourly" and "daily" stream, from TestCountStats.setUp
                [1, "false", Stream.objects.get(name="stream 1")],
                [1, "false", Stream.objects.get(name="stream 61")],
            ],
        )
        self.assertTableState(
            RealmCount,
            ["value", "subgroup", "realm"],
            [[3, "false"], [2, "true"], [2, "false", self.second_realm]],
        )
        self.assertTableState(InstallationCount, ["value", "subgroup"], [[5, "false"], [2, "true"]])
        self.assertTableState(UserCount, [], [])

    def test_messages_sent_to_stream_by_is_bot_realm_constraint(self) -> None:
        # For single Realm

        COUNT_STATS = get_count_stats(self.default_realm)
        stat = COUNT_STATS["messages_in_stream:is_bot:day"]
        self.current_property = stat.property

        human1 = self.create_user()
        bot = self.create_user(is_bot=True)

        realm = {"realm": self.second_realm}
        stream1, recipient_stream1 = self.create_stream_with_recipient()
        stream2, recipient_stream2 = self.create_stream_with_recipient(**realm)

        # To be included
        self.create_message(human1, recipient_stream1)
        self.create_message(bot, recipient_stream1)

        # To be excluded
        self.create_message(self.hourly_user, recipient_stream2)
        self.create_message(self.daily_user, recipient_stream2)

        do_fill_count_stat_at_hour(stat, self.TIME_ZERO, self.default_realm)

        self.assertTableState(
            StreamCount,
            ["value", "subgroup", "stream"],
            [[1, "false", stream1], [1, "true", stream1]],
        )
        self.assertTableState(
            RealmCount, ["value", "subgroup", "realm"], [[1, "false"], [1, "true"]]
        )
        # No aggregation to InstallationCount with realm constraint
        self.assertTableState(InstallationCount, ["value", "subgroup"], [])
        self.assertTableState(UserCount, [], [])

    def create_interval(
        self, user: UserProfile, start_offset: timedelta, end_offset: timedelta
    ) -> None:
        UserActivityInterval.objects.create(
            user_profile=user, start=self.TIME_ZERO - start_offset, end=self.TIME_ZERO - end_offset
        )

    def test_1day_actives(self) -> None:
        stat = COUNT_STATS["1day_actives::day"]
        self.current_property = stat.property

        _1day = 1 * self.DAY - UserActivityInterval.MIN_INTERVAL_LENGTH

        # Outside time range, should not appear. Also tests upper boundary.
        user1 = self.create_user()
        self.create_interval(user1, _1day + self.DAY, _1day + timedelta(seconds=1))
        self.create_interval(user1, timedelta(0), -self.HOUR)

        # On lower boundary, should appear
        user2 = self.create_user()
        self.create_interval(user2, _1day + self.DAY, _1day)

        # Multiple intervals, including one outside boundary
        user3 = self.create_user()
        self.create_interval(user3, 2 * self.DAY, 1 * self.DAY)
        self.create_interval(user3, 20 * self.HOUR, 19 * self.HOUR)
        self.create_interval(user3, 20 * self.MINUTE, 19 * self.MINUTE)

        # Intervals crossing boundary
        user4 = self.create_user()
        self.create_interval(user4, 1.5 * self.DAY, 0.5 * self.DAY)
        user5 = self.create_user()
        self.create_interval(user5, self.MINUTE, -self.MINUTE)

        # Interval subsuming time range
        user6 = self.create_user()
        self.create_interval(user6, 2 * self.DAY, -2 * self.DAY)

        # Second realm
        user7 = self.create_user(realm=self.second_realm)
        self.create_interval(user7, 20 * self.MINUTE, 19 * self.MINUTE)

        do_fill_count_stat_at_hour(stat, self.TIME_ZERO)
        self.assertTableState(
            UserCount,
            ["value", "user"],
            [[1, user2], [1, user3], [1, user4], [1, user5], [1, user6], [1, user7]],
        )
        self.assertTableState(
            RealmCount, ["value", "realm"], [[5, self.default_realm], [1, self.second_realm]]
        )
        self.assertTableState(InstallationCount, ["value"], [[6]])
        self.assertTableState(StreamCount, [], [])

    def test_1day_actives_realm_constraint(self) -> None:
        # For single Realm

        COUNT_STATS = get_count_stats(self.default_realm)
        stat = COUNT_STATS["1day_actives::day"]
        self.current_property = stat.property

        _1day = 1 * self.DAY - UserActivityInterval.MIN_INTERVAL_LENGTH
        user1 = self.create_user()
        user2 = self.create_user()

        # To be included
        self.create_interval(user1, 20 * self.HOUR, 19 * self.HOUR)
        self.create_interval(user2, _1day + self.DAY, _1day)

        # To be excluded
        user3 = self.create_user(realm=self.second_realm)
        self.create_interval(user3, 20 * self.MINUTE, 19 * self.MINUTE)

        do_fill_count_stat_at_hour(stat, self.TIME_ZERO, self.default_realm)
        self.assertTableState(UserCount, ["value", "user"], [[1, user2], [1, user2]])
        self.assertTableState(RealmCount, ["value", "realm"], [[2, self.default_realm]])
        # No aggregation to InstallationCount with realm constraint
        self.assertTableState(InstallationCount, ["value"], [])
        self.assertTableState(StreamCount, [], [])

    def test_15day_actives(self) -> None:
        stat = COUNT_STATS["15day_actives::day"]
        self.current_property = stat.property

        _15day = 15 * self.DAY - UserActivityInterval.MIN_INTERVAL_LENGTH

        # Outside time range, should not appear. Also tests upper boundary.
        user1 = self.create_user()
        self.create_interval(user1, _15day + self.DAY, _15day + timedelta(seconds=1))
        self.create_interval(user1, timedelta(0), -self.HOUR)

        # On lower boundary, should appear
        user2 = self.create_user()
        self.create_interval(user2, _15day + self.DAY, _15day)

        # Multiple intervals, including one outside boundary
        user3 = self.create_user()
        self.create_interval(user3, 20 * self.DAY, 19 * self.DAY)
        self.create_interval(user3, 20 * self.HOUR, 19 * self.HOUR)
        self.create_interval(user3, 20 * self.MINUTE, 19 * self.MINUTE)

        # Intervals crossing boundary
        user4 = self.create_user()
        self.create_interval(user4, 20 * self.DAY, 10 * self.DAY)
        user5 = self.create_user()
        self.create_interval(user5, self.MINUTE, -self.MINUTE)

        # Interval subsuming time range
        user6 = self.create_user()
        self.create_interval(user6, 20 * self.DAY, -2 * self.DAY)

        # Second realm
        user7 = self.create_user(realm=self.second_realm)
        self.create_interval(user7, 20 * self.MINUTE, 19 * self.MINUTE)

        do_fill_count_stat_at_hour(stat, self.TIME_ZERO)
        self.assertTableState(
            UserCount,
            ["value", "user"],
            [[1, user2], [1, user3], [1, user4], [1, user5], [1, user6], [1, user7]],
        )
        self.assertTableState(
            RealmCount, ["value", "realm"], [[5, self.default_realm], [1, self.second_realm]]
        )
        self.assertTableState(InstallationCount, ["value"], [[6]])
        self.assertTableState(StreamCount, [], [])

    def test_15day_actives_realm_constraint(self) -> None:
        # For single Realm

        COUNT_STATS = get_count_stats(self.default_realm)
        stat = COUNT_STATS["15day_actives::day"]
        self.current_property = stat.property

        _15day = 15 * self.DAY - UserActivityInterval.MIN_INTERVAL_LENGTH

        user1 = self.create_user()
        user2 = self.create_user()
        user3 = self.create_user(realm=self.second_realm)

        # To be included
        self.create_interval(user1, _15day + self.DAY, _15day)
        self.create_interval(user2, 20 * self.HOUR, 19 * self.HOUR)

        # To be excluded
        self.create_interval(user3, 20 * self.HOUR, 19 * self.HOUR)

        do_fill_count_stat_at_hour(stat, self.TIME_ZERO, self.default_realm)

        self.assertTableState(UserCount, ["value", "user"], [[1, user1], [1, user2]])
        self.assertTableState(RealmCount, ["value", "realm"], [[2, self.default_realm]])
        # No aggregation to InstallationCount with realm constraint
        self.assertTableState(InstallationCount, ["value"], [])
        self.assertTableState(StreamCount, [], [])

    def test_minutes_active(self) -> None:
        stat = COUNT_STATS["minutes_active::day"]
        self.current_property = stat.property

        # Outside time range, should not appear. Also testing for intervals
        # starting and ending on boundary
        user1 = self.create_user()
        self.create_interval(user1, 25 * self.HOUR, self.DAY)
        self.create_interval(user1, timedelta(0), -self.HOUR)

        # Multiple intervals, including one outside boundary
        user2 = self.create_user()
        self.create_interval(user2, 20 * self.DAY, 19 * self.DAY)
        self.create_interval(user2, 20 * self.HOUR, 19 * self.HOUR)
        self.create_interval(user2, 20 * self.MINUTE, 19 * self.MINUTE)

        # Intervals crossing boundary
        user3 = self.create_user()
        self.create_interval(user3, 25 * self.HOUR, 22 * self.HOUR)
        self.create_interval(user3, self.MINUTE, -self.MINUTE)

        # Interval subsuming time range
        user4 = self.create_user()
        self.create_interval(user4, 2 * self.DAY, -2 * self.DAY)

        # Less than 60 seconds, should not appear
        user5 = self.create_user()
        self.create_interval(user5, self.MINUTE, timedelta(seconds=30))
        self.create_interval(user5, timedelta(seconds=20), timedelta(seconds=10))

        # Second realm
        user6 = self.create_user(realm=self.second_realm)
        self.create_interval(user6, 20 * self.MINUTE, 19 * self.MINUTE)

        do_fill_count_stat_at_hour(stat, self.TIME_ZERO)
        self.assertTableState(
            UserCount, ["value", "user"], [[61, user2], [121, user3], [24 * 60, user4], [1, user6]]
        )
        self.assertTableState(
            RealmCount,
            ["value", "realm"],
            [[61 + 121 + 24 * 60, self.default_realm], [1, self.second_realm]],
        )
        self.assertTableState(InstallationCount, ["value"], [[61 + 121 + 24 * 60 + 1]])
        self.assertTableState(StreamCount, [], [])

    def test_minutes_active_realm_constraint(self) -> None:
        # For single Realm

        COUNT_STATS = get_count_stats(self.default_realm)
        stat = COUNT_STATS["minutes_active::day"]
        self.current_property = stat.property

        # Outside time range, should not appear. Also testing for intervals
        # starting and ending on boundary
        user1 = self.create_user()
        user2 = self.create_user()
        user3 = self.create_user(realm=self.second_realm)

        # To be included
        self.create_interval(user1, 20 * self.HOUR, 19 * self.HOUR)
        self.create_interval(user2, 20 * self.MINUTE, 19 * self.MINUTE)

        # To be excluded
        self.create_interval(user3, 20 * self.MINUTE, 19 * self.MINUTE)

        do_fill_count_stat_at_hour(stat, self.TIME_ZERO, self.default_realm)
        self.assertTableState(UserCount, ["value", "user"], [[60, user1], [1, user2]])
        self.assertTableState(RealmCount, ["value", "realm"], [[60 + 1, self.default_realm]])
        # No aggregation to InstallationCount with realm constraint
        self.assertTableState(InstallationCount, ["value"], [])
        self.assertTableState(StreamCount, [], [])

    def test_last_successful_fill(self) -> None:
        self.assertIsNone(COUNT_STATS["messages_sent:is_bot:hour"].last_successful_fill())

        a_time = datetime(2016, 3, 14, 19, tzinfo=timezone.utc)
        one_hour_before = datetime(2016, 3, 14, 18, tzinfo=timezone.utc)
        one_day_before = datetime(2016, 3, 13, 19, tzinfo=timezone.utc)

        fillstate = FillState.objects.create(
            property=COUNT_STATS["messages_sent:is_bot:hour"].property,
            end_time=a_time,
            state=FillState.DONE,
        )
        self.assertEqual(COUNT_STATS["messages_sent:is_bot:hour"].last_successful_fill(), a_time)

        fillstate.state = FillState.STARTED
        fillstate.save(update_fields=["state"])
        self.assertEqual(
            COUNT_STATS["messages_sent:is_bot:hour"].last_successful_fill(), one_hour_before
        )

        fillstate.property = COUNT_STATS["7day_actives::day"].property
        fillstate.save(update_fields=["property"])
        self.assertEqual(COUNT_STATS["7day_actives::day"].last_successful_fill(), one_day_before)


class TestDoAggregateToSummaryTable(AnalyticsTestCase):
    # do_aggregate_to_summary_table is mostly tested by the end to end
    # nature of the tests in TestCountStats. But want to highlight one
    # feature important for keeping the size of the analytics tables small,
    # which is that if there is no relevant data in the table being
    # aggregated, the aggregation table doesn't get a row with value 0.
    def test_no_aggregated_zeros(self) -> None:
        stat = LoggingCountStat("test stat", UserCount, CountStat.HOUR)
        do_aggregate_to_summary_table(stat, self.TIME_ZERO)
        self.assertFalse(RealmCount.objects.exists())
        self.assertFalse(InstallationCount.objects.exists())


class TestDoIncrementLoggingStat(AnalyticsTestCase):
    def test_table_and_id_args(self) -> None:
        # For realms, streams, and users, tests that the new rows are going to
        # the appropriate *Count table, and that using a different zerver_object
        # results in a new row being created
        self.current_property = "test"
        second_realm = do_create_realm(string_id="moo", name="moo")
        stat = LoggingCountStat("test", RealmCount, CountStat.DAY)
        do_increment_logging_stat(self.default_realm, stat, None, self.TIME_ZERO)
        do_increment_logging_stat(second_realm, stat, None, self.TIME_ZERO)
        self.assertTableState(RealmCount, ["realm"], [[self.default_realm], [second_realm]])

        user1 = self.create_user()
        user2 = self.create_user()
        stat = LoggingCountStat("test", UserCount, CountStat.DAY)
        do_increment_logging_stat(user1, stat, None, self.TIME_ZERO)
        do_increment_logging_stat(user2, stat, None, self.TIME_ZERO)
        self.assertTableState(UserCount, ["user"], [[user1], [user2]])

        stream1 = self.create_stream_with_recipient()[0]
        stream2 = self.create_stream_with_recipient()[0]
        stat = LoggingCountStat("test", StreamCount, CountStat.DAY)
        do_increment_logging_stat(stream1, stat, None, self.TIME_ZERO)
        do_increment_logging_stat(stream2, stat, None, self.TIME_ZERO)
        self.assertTableState(StreamCount, ["stream"], [[stream1], [stream2]])

    def test_frequency(self) -> None:
        times = [self.TIME_ZERO - self.MINUTE * i for i in [0, 1, 61, 24 * 60 + 1]]

        stat = LoggingCountStat("day test", RealmCount, CountStat.DAY)
        for time_ in times:
            do_increment_logging_stat(self.default_realm, stat, None, time_)
        stat = LoggingCountStat("hour test", RealmCount, CountStat.HOUR)
        for time_ in times:
            do_increment_logging_stat(self.default_realm, stat, None, time_)

        self.assertTableState(
            RealmCount,
            ["value", "property", "end_time"],
            [
                [3, "day test", self.TIME_ZERO],
                [1, "day test", self.TIME_ZERO - self.DAY],
                [2, "hour test", self.TIME_ZERO],
                [1, "hour test", self.TIME_LAST_HOUR],
                [1, "hour test", self.TIME_ZERO - self.DAY],
            ],
        )

    def test_get_or_create(self) -> None:
        stat = LoggingCountStat("test", RealmCount, CountStat.HOUR)
        # All these should trigger the create part of get_or_create.
        # property is tested in test_frequency, and id_args are tested in test_id_args,
        # so this only tests a new subgroup and end_time
        do_increment_logging_stat(self.default_realm, stat, "subgroup1", self.TIME_ZERO)
        do_increment_logging_stat(self.default_realm, stat, "subgroup2", self.TIME_ZERO)
        do_increment_logging_stat(self.default_realm, stat, "subgroup1", self.TIME_LAST_HOUR)
        self.current_property = "test"
        self.assertTableState(
            RealmCount,
            ["value", "subgroup", "end_time"],
            [
                [1, "subgroup1", self.TIME_ZERO],
                [1, "subgroup2", self.TIME_ZERO],
                [1, "subgroup1", self.TIME_LAST_HOUR],
            ],
        )
        # This should trigger the get part of get_or_create
        do_increment_logging_stat(self.default_realm, stat, "subgroup1", self.TIME_ZERO)
        self.assertTableState(
            RealmCount,
            ["value", "subgroup", "end_time"],
            [
                [2, "subgroup1", self.TIME_ZERO],
                [1, "subgroup2", self.TIME_ZERO],
                [1, "subgroup1", self.TIME_LAST_HOUR],
            ],
        )

    def test_increment(self) -> None:
        stat = LoggingCountStat("test", RealmCount, CountStat.DAY)
        self.current_property = "test"
        do_increment_logging_stat(self.default_realm, stat, None, self.TIME_ZERO, increment=-1)
        self.assertTableState(RealmCount, ["value"], [[-1]])
        do_increment_logging_stat(self.default_realm, stat, None, self.TIME_ZERO, increment=3)
        self.assertTableState(RealmCount, ["value"], [[2]])
        do_increment_logging_stat(self.default_realm, stat, None, self.TIME_ZERO)
        self.assertTableState(RealmCount, ["value"], [[3]])

    def test_do_increment_logging_start_query_count(self) -> None:
        stat = LoggingCountStat("test", RealmCount, CountStat.DAY)
        with self.assert_database_query_count(1):
            do_increment_logging_stat(self.default_realm, stat, None, self.TIME_ZERO)


class TestLoggingCountStats(AnalyticsTestCase):
    def test_aggregation(self) -> None:
        stat = LoggingCountStat("realm test", RealmCount, CountStat.DAY)
        do_increment_logging_stat(self.default_realm, stat, None, self.TIME_ZERO)
        process_count_stat(stat, self.TIME_ZERO)

        user = self.create_user()
        stat = LoggingCountStat("user test", UserCount, CountStat.DAY)
        do_increment_logging_stat(user, stat, None, self.TIME_ZERO)
        process_count_stat(stat, self.TIME_ZERO)

        stream = self.create_stream_with_recipient()[0]
        stat = LoggingCountStat("stream test", StreamCount, CountStat.DAY)
        do_increment_logging_stat(stream, stat, None, self.TIME_ZERO)
        process_count_stat(stat, self.TIME_ZERO)

        self.assertTableState(
            InstallationCount,
            ["property", "value"],
            [["realm test", 1], ["user test", 1], ["stream test", 1]],
        )
        self.assertTableState(
            RealmCount,
            ["property", "value"],
            [["realm test", 1], ["user test", 1], ["stream test", 1]],
        )
        self.assertTableState(UserCount, ["property", "value"], [["user test", 1]])
        self.assertTableState(StreamCount, ["property", "value"], [["stream test", 1]])

    def test_active_users_log_by_is_bot(self) -> None:
        property = "active_users_log:is_bot:day"
        user = do_create_user(
            "email", "password", self.default_realm, "full_name", acting_user=None
        )
        self.assertEqual(
            1,
            RealmCount.objects.filter(property=property, subgroup=False).aggregate(Sum("value"))[
                "value__sum"
            ],
        )
        do_deactivate_user(user, acting_user=None)
        self.assertEqual(
            0,
            RealmCount.objects.filter(property=property, subgroup=False).aggregate(Sum("value"))[
                "value__sum"
            ],
        )
        do_activate_mirror_dummy_user(user, acting_user=None)
        self.assertEqual(
            1,
            RealmCount.objects.filter(property=property, subgroup=False).aggregate(Sum("value"))[
                "value__sum"
            ],
        )
        do_deactivate_user(user, acting_user=None)
        self.assertEqual(
            0,
            RealmCount.objects.filter(property=property, subgroup=False).aggregate(Sum("value"))[
                "value__sum"
            ],
        )
        do_reactivate_user(user, acting_user=None)
        self.assertEqual(
            1,
            RealmCount.objects.filter(property=property, subgroup=False).aggregate(Sum("value"))[
                "value__sum"
            ],
        )

    @override_settings(PUSH_NOTIFICATION_BOUNCER_URL="https://push.zulip.org.example.com")
    def test_mobile_pushes_received_count(self) -> None:
        self.server_uuid = "6cde5f7a-1f7e-4978-9716-49f69ebfc9fe"
        self.server = RemoteZulipServer.objects.create(
            uuid=self.server_uuid,
            api_key="magic_secret_api_key",
            hostname="demo.example.com",
            last_updated=timezone_now(),
        )

        hamlet = self.example_user("hamlet")
        token = "aaaa"

        RemotePushDeviceToken.objects.create(
            kind=RemotePushDeviceToken.GCM,
            token=hex_to_b64(token),
            user_uuid=(hamlet.uuid),
            server=self.server,
        )
        RemotePushDeviceToken.objects.create(
            kind=RemotePushDeviceToken.GCM,
            token=hex_to_b64(token + "aa"),
            user_uuid=(hamlet.uuid),
            server=self.server,
        )
        RemotePushDeviceToken.objects.create(
            kind=RemotePushDeviceToken.APNS,
            token=hex_to_b64(token),
            user_uuid=str(hamlet.uuid),
            server=self.server,
        )

        message = Message(
            sender=hamlet,
            recipient=self.example_user("othello").recipient,
            realm_id=hamlet.realm_id,
            content="This is test content",
            rendered_content="This is test content",
            date_sent=timezone_now(),
            sending_client=get_client("test"),
        )
        message.set_topic_name("Test topic")
        message.save()
        gcm_payload, gcm_options = get_message_payload_gcm(hamlet, message)
        apns_payload = get_message_payload_apns(
            hamlet, message, NotificationTriggers.DIRECT_MESSAGE
        )

        # First we'll make a request without providing realm_uuid. That means
        # the bouncer can't increment the RemoteRealmCount stat, and only
        # RemoteInstallationCount will be incremented.
        payload = {
            "user_id": hamlet.id,
            "user_uuid": str(hamlet.uuid),
            "gcm_payload": gcm_payload,
            "apns_payload": apns_payload,
            "gcm_options": gcm_options,
        }
        now = timezone_now()
        with time_machine.travel(now, tick=False), mock.patch(
            "zilencer.views.send_android_push_notification", return_value=1
        ), mock.patch("zilencer.views.send_apple_push_notification", return_value=1), mock.patch(
            "corporate.lib.stripe.RemoteServerBillingSession.current_count_for_billed_licenses",
            return_value=10,
        ), self.assertLogs("zilencer.views", level="INFO"):
            result = self.uuid_post(
                self.server_uuid,
                "/api/v1/remotes/push/notify",
                payload,
                content_type="application/json",
                subdomain="",
            )
            self.assert_json_success(result)

        # There are 3 devices we created for the user:
        # 1. The mobile_pushes_received increment should match that number.
        # 2. mobile_pushes_forwarded only counts successful deliveries, and we've set up
        #    the mocks above to simulate 1 successful android and 1 successful apple delivery.
        #    Thus the increment should be just 2.
        self.assertTableState(
            RemoteInstallationCount,
            ["property", "value", "subgroup", "server", "remote_id", "end_time"],
            [
                [
                    "mobile_pushes_received::day",
                    3,
                    None,
                    self.server,
                    None,
                    ceiling_to_day(now),
                ],
                [
                    "mobile_pushes_forwarded::day",
                    2,
                    None,
                    self.server,
                    None,
                    ceiling_to_day(now),
                ],
            ],
        )
        self.assertFalse(
            RemoteRealmCount.objects.filter(property="mobile_pushes_received::day").exists()
        )
        self.assertFalse(
            RemoteRealmCount.objects.filter(property="mobile_pushes_forwarded::day").exists()
        )

        # Now provide the realm_uuid. However, the RemoteRealm record doesn't exist yet, so it'll
        # still be ignored.
        payload = {
            "user_id": hamlet.id,
            "user_uuid": str(hamlet.uuid),
            "realm_uuid": str(hamlet.realm.uuid),
            "gcm_payload": gcm_payload,
            "apns_payload": apns_payload,
            "gcm_options": gcm_options,
        }
        with time_machine.travel(now, tick=False), mock.patch(
            "zilencer.views.send_android_push_notification", return_value=1
        ), mock.patch("zilencer.views.send_apple_push_notification", return_value=1), mock.patch(
            "corporate.lib.stripe.RemoteServerBillingSession.current_count_for_billed_licenses",
            return_value=10,
        ), self.assertLogs("zilencer.views", level="INFO"):
            result = self.uuid_post(
                self.server_uuid,
                "/api/v1/remotes/push/notify",
                payload,
                content_type="application/json",
                subdomain="",
            )
            self.assert_json_success(result)

        # The RemoteInstallationCount records get incremented again, but the RemoteRealmCount
        # remains ignored due to missing RemoteRealm record.
        self.assertTableState(
            RemoteInstallationCount,
            ["property", "value", "subgroup", "server", "remote_id", "end_time"],
            [
                [
                    "mobile_pushes_received::day",
                    6,
                    None,
                    self.server,
                    None,
                    ceiling_to_day(now),
                ],
                [
                    "mobile_pushes_forwarded::day",
                    4,
                    None,
                    self.server,
                    None,
                    ceiling_to_day(now),
                ],
            ],
        )
        self.assertFalse(
            RemoteRealmCount.objects.filter(property="mobile_pushes_received::day").exists()
        )
        self.assertFalse(
            RemoteRealmCount.objects.filter(property="mobile_pushes_forwarded::day").exists()
        )

        # Create the RemoteRealm registration and repeat the above. This time RemoteRealmCount
        # stats should be collected.
        realm = hamlet.realm
        remote_realm = RemoteRealm.objects.create(
            server=self.server,
            uuid=realm.uuid,
            uuid_owner_secret=realm.uuid_owner_secret,
            host=realm.host,
            realm_deactivated=realm.deactivated,
            realm_date_created=realm.date_created,
        )

        with time_machine.travel(now, tick=False), mock.patch(
            "zilencer.views.send_android_push_notification", return_value=1
        ), mock.patch("zilencer.views.send_apple_push_notification", return_value=1), mock.patch(
            "corporate.lib.stripe.RemoteRealmBillingSession.current_count_for_billed_licenses",
            return_value=10,
        ), self.assertLogs("zilencer.views", level="INFO"):
            result = self.uuid_post(
                self.server_uuid,
                "/api/v1/remotes/push/notify",
                payload,
                content_type="application/json",
                subdomain="",
            )
            self.assert_json_success(result)

        # The RemoteInstallationCount records get incremented again, and the RemoteRealmCount
        # gets collected.
        self.assertTableState(
            RemoteInstallationCount,
            ["property", "value", "subgroup", "server", "remote_id", "end_time"],
            [
                [
                    "mobile_pushes_received::day",
                    9,
                    None,
                    self.server,
                    None,
                    ceiling_to_day(now),
                ],
                [
                    "mobile_pushes_forwarded::day",
                    6,
                    None,
                    self.server,
                    None,
                    ceiling_to_day(now),
                ],
            ],
        )
        self.assertTableState(
            RemoteRealmCount,
            ["property", "value", "subgroup", "server", "remote_realm", "remote_id", "end_time"],
            [
                [
                    "mobile_pushes_received::day",
                    3,
                    None,
                    self.server,
                    remote_realm,
                    None,
                    ceiling_to_day(now),
                ],
                [
                    "mobile_pushes_forwarded::day",
                    2,
                    None,
                    self.server,
                    remote_realm,
                    None,
                    ceiling_to_day(now),
                ],
            ],
        )

    def test_invites_sent(self) -> None:
        property = "invites_sent::day"

        @contextmanager
        def invite_context(
            too_many_recent_realm_invites: bool = False, failure: bool = False
        ) -> Iterator[None]:
            managers: List[AbstractContextManager[Any]] = [
                mock.patch(
                    "zerver.actions.invites.too_many_recent_realm_invites", return_value=False
                ),
                self.captureOnCommitCallbacks(execute=True),
            ]
            if failure:
                managers.append(self.assertRaises(InvitationError))
            with ExitStack() as stack:
                for mgr in managers:
                    stack.enter_context(mgr)
                yield

        def assertInviteCountEquals(count: int) -> None:
            self.assertEqual(
                count,
                RealmCount.objects.filter(property=property, subgroup=None).aggregate(Sum("value"))[
                    "value__sum"
                ],
            )

        user = self.create_user(email="first@domain.tld")
        stream, _ = self.create_stream_with_recipient()

        invite_expires_in_minutes = 2 * 24 * 60
        with invite_context():
            do_invite_users(
                user,
                ["user1@domain.tld", "user2@domain.tld"],
                [stream],
                invite_expires_in_minutes=invite_expires_in_minutes,
            )
        assertInviteCountEquals(2)

        # We currently send emails when re-inviting users that haven't
        # turned into accounts, so count them towards the total
        with invite_context():
            do_invite_users(
                user,
                ["user1@domain.tld", "user2@domain.tld"],
                [stream],
                invite_expires_in_minutes=invite_expires_in_minutes,
            )
        assertInviteCountEquals(4)

        # Test mix of good and malformed invite emails
        with invite_context(failure=True):
            do_invite_users(
                user,
                ["user3@domain.tld", "malformed"],
                [stream],
                invite_expires_in_minutes=invite_expires_in_minutes,
            )
        assertInviteCountEquals(4)

        # Test inviting existing users
        with invite_context():
            skipped = do_invite_users(
                user,
                ["first@domain.tld", "user4@domain.tld"],
                [stream],
                invite_expires_in_minutes=invite_expires_in_minutes,
            )
            self.assert_length(skipped, 1)
        assertInviteCountEquals(5)

        # Revoking invite should not give you credit
        do_revoke_user_invite(
            assert_is_not_none(PreregistrationUser.objects.filter(realm=user.realm).first())
        )
        assertInviteCountEquals(5)

        # Resending invite should cost you
        with invite_context():
            do_send_user_invite_email(assert_is_not_none(PreregistrationUser.objects.first()))
        assertInviteCountEquals(6)

    def test_messages_read_hour(self) -> None:
        read_count_property = "messages_read::hour"
        interactions_property = "messages_read_interactions::hour"

        user1 = self.create_user()
        user2 = self.create_user()
        stream, recipient = self.create_stream_with_recipient()
        self.subscribe(user1, stream.name)
        self.subscribe(user2, stream.name)

        self.send_personal_message(user1, user2)
        do_mark_all_as_read(user2)
        self.assertEqual(
            1,
            UserCount.objects.filter(property=read_count_property).aggregate(Sum("value"))[
                "value__sum"
            ],
        )
        self.assertEqual(
            1,
            UserCount.objects.filter(property=interactions_property).aggregate(Sum("value"))[
                "value__sum"
            ],
        )

        self.send_stream_message(user1, stream.name)
        self.send_stream_message(user1, stream.name)
        do_mark_stream_messages_as_read(user2, assert_is_not_none(stream.recipient_id))
        self.assertEqual(
            3,
            UserCount.objects.filter(property=read_count_property).aggregate(Sum("value"))[
                "value__sum"
            ],
        )
        self.assertEqual(
            2,
            UserCount.objects.filter(property=interactions_property).aggregate(Sum("value"))[
                "value__sum"
            ],
        )

        message = self.send_stream_message(user2, stream.name)
        do_update_message_flags(user1, "add", "read", [message])
        self.assertEqual(
            4,
            UserCount.objects.filter(property=read_count_property).aggregate(Sum("value"))[
                "value__sum"
            ],
        )
        self.assertEqual(
            3,
            UserCount.objects.filter(property=interactions_property).aggregate(Sum("value"))[
                "value__sum"
            ],
        )


class TestDeleteStats(AnalyticsTestCase):
    def test_do_drop_all_analytics_tables(self) -> None:
        user = self.create_user()
        stream = self.create_stream_with_recipient()[0]
        count_args = {"property": "test", "end_time": self.TIME_ZERO, "value": 10}

        UserCount.objects.create(user=user, realm=user.realm, **count_args)
        StreamCount.objects.create(stream=stream, realm=stream.realm, **count_args)
        RealmCount.objects.create(realm=user.realm, **count_args)
        InstallationCount.objects.create(**count_args)
        FillState.objects.create(property="test", end_time=self.TIME_ZERO, state=FillState.DONE)

        analytics = apps.get_app_config("analytics")
        for table in analytics.models.values():
            self.assertTrue(table._default_manager.exists())

        do_drop_all_analytics_tables()
        for table in analytics.models.values():
            self.assertFalse(table._default_manager.exists())

    def test_do_drop_single_stat(self) -> None:
        user = self.create_user()
        stream = self.create_stream_with_recipient()[0]
        count_args_to_delete = {"property": "to_delete", "end_time": self.TIME_ZERO, "value": 10}
        count_args_to_save = {"property": "to_save", "end_time": self.TIME_ZERO, "value": 10}

        for count_args in [count_args_to_delete, count_args_to_save]:
            UserCount.objects.create(user=user, realm=user.realm, **count_args)
            StreamCount.objects.create(stream=stream, realm=stream.realm, **count_args)
            RealmCount.objects.create(realm=user.realm, **count_args)
            InstallationCount.objects.create(**count_args)
        FillState.objects.create(
            property="to_delete", end_time=self.TIME_ZERO, state=FillState.DONE
        )
        FillState.objects.create(property="to_save", end_time=self.TIME_ZERO, state=FillState.DONE)

        analytics = apps.get_app_config("analytics")
        for table in analytics.models.values():
            self.assertTrue(table._default_manager.exists())

        do_drop_single_stat("to_delete")
        for table in analytics.models.values():
            self.assertFalse(table._default_manager.filter(property="to_delete").exists())
            self.assertTrue(table._default_manager.filter(property="to_save").exists())


class TestActiveUsersAudit(AnalyticsTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        self.user = self.create_user()
        self.stat = COUNT_STATS["active_users_audit:is_bot:day"]
        self.current_property = self.stat.property

    def add_event(
        self, event_type: int, days_offset: float, user: Optional[UserProfile] = None
    ) -> None:
        hours_offset = int(24 * days_offset)
        if user is None:
            user = self.user
        RealmAuditLog.objects.create(
            realm=user.realm,
            modified_user=user,
            event_type=event_type,
            event_time=self.TIME_ZERO - hours_offset * self.HOUR,
        )

    def test_user_deactivated_in_future(self) -> None:
        self.add_event(RealmAuditLog.USER_CREATED, 1)
        self.add_event(RealmAuditLog.USER_DEACTIVATED, 0)
        do_fill_count_stat_at_hour(self.stat, self.TIME_ZERO)
        self.assertTableState(UserCount, ["subgroup"], [["false"]])

    def test_user_reactivated_in_future(self) -> None:
        self.add_event(RealmAuditLog.USER_DEACTIVATED, 1)
        self.add_event(RealmAuditLog.USER_REACTIVATED, 0)
        do_fill_count_stat_at_hour(self.stat, self.TIME_ZERO)
        self.assertTableState(UserCount, [], [])

    def test_user_active_then_deactivated_same_day(self) -> None:
        self.add_event(RealmAuditLog.USER_CREATED, 1)
        self.add_event(RealmAuditLog.USER_DEACTIVATED, 0.5)
        do_fill_count_stat_at_hour(self.stat, self.TIME_ZERO)
        self.assertTableState(UserCount, [], [])

    def test_user_unactive_then_activated_same_day(self) -> None:
        self.add_event(RealmAuditLog.USER_DEACTIVATED, 1)
        self.add_event(RealmAuditLog.USER_REACTIVATED, 0.5)
        do_fill_count_stat_at_hour(self.stat, self.TIME_ZERO)
        self.assertTableState(UserCount, ["subgroup"], [["false"]])

    # Arguably these next two tests are duplicates of the _in_future tests, but are
    # a guard against future refactorings where they may no longer be duplicates
    def test_user_active_then_deactivated_with_day_gap(self) -> None:
        self.add_event(RealmAuditLog.USER_CREATED, 2)
        self.add_event(RealmAuditLog.USER_DEACTIVATED, 1)
        process_count_stat(self.stat, self.TIME_ZERO)
        self.assertTableState(
            UserCount, ["subgroup", "end_time"], [["false", self.TIME_ZERO - self.DAY]]
        )

    def test_user_deactivated_then_reactivated_with_day_gap(self) -> None:
        self.add_event(RealmAuditLog.USER_DEACTIVATED, 2)
        self.add_event(RealmAuditLog.USER_REACTIVATED, 1)
        process_count_stat(self.stat, self.TIME_ZERO)
        self.assertTableState(UserCount, ["subgroup"], [["false"]])

    def test_event_types(self) -> None:
        self.add_event(RealmAuditLog.USER_CREATED, 4)
        self.add_event(RealmAuditLog.USER_DEACTIVATED, 3)
        self.add_event(RealmAuditLog.USER_ACTIVATED, 2)
        self.add_event(RealmAuditLog.USER_REACTIVATED, 1)
        for i in range(4):
            do_fill_count_stat_at_hour(self.stat, self.TIME_ZERO - i * self.DAY)
        self.assertTableState(
            UserCount,
            ["subgroup", "end_time"],
            [["false", self.TIME_ZERO - i * self.DAY] for i in [3, 1, 0]],
        )

    # Also tests that aggregation to RealmCount and InstallationCount is
    # being done, and that we're storing the user correctly in UserCount
    def test_multiple_users_realms_and_bots(self) -> None:
        user1 = self.create_user()
        user2 = self.create_user()
        second_realm = do_create_realm(string_id="moo", name="moo")
        user3 = self.create_user(realm=second_realm)
        user4 = self.create_user(realm=second_realm, is_bot=True)
        for user in [user1, user2, user3, user4]:
            self.add_event(RealmAuditLog.USER_CREATED, 1, user=user)
        do_fill_count_stat_at_hour(self.stat, self.TIME_ZERO)
        self.assertTableState(
            UserCount,
            ["subgroup", "user"],
            [["false", user1], ["false", user2], ["false", user3], ["true", user4]],
        )
        self.assertTableState(
            RealmCount,
            ["value", "subgroup", "realm"],
            [
                [2, "false", self.default_realm],
                [1, "false", second_realm],
                [1, "true", second_realm],
            ],
        )
        self.assertTableState(InstallationCount, ["value", "subgroup"], [[3, "false"], [1, "true"]])
        self.assertTableState(StreamCount, [], [])

    # Not that interesting a test if you look at the SQL query at hand, but
    # almost all other CountStats have a start_date, so guarding against a
    # refactoring that adds that in.
    # Also tests the slightly more end-to-end process_count_stat rather than
    # do_fill_count_stat_at_hour. E.g. if one changes self.stat.frequency to
    # CountStat.HOUR from CountStat.DAY, this will fail, while many of the
    # tests above will not.
    def test_update_from_two_days_ago(self) -> None:
        self.add_event(RealmAuditLog.USER_CREATED, 2)
        process_count_stat(self.stat, self.TIME_ZERO)
        self.assertTableState(
            UserCount,
            ["subgroup", "end_time"],
            [["false", self.TIME_ZERO], ["false", self.TIME_ZERO - self.DAY]],
        )

    # User with no relevant activity could happen e.g. for a system bot that
    # doesn't go through do_create_user. Mainly just want to make sure that
    # that situation doesn't throw an error.
    def test_empty_realm_or_user_with_no_relevant_activity(self) -> None:
        self.add_event(RealmAuditLog.USER_SOFT_ACTIVATED, 1)
        self.create_user()  # also test a user with no RealmAuditLog entries
        do_create_realm(string_id="moo", name="moo")
        do_fill_count_stat_at_hour(self.stat, self.TIME_ZERO)
        self.assertTableState(UserCount, [], [])

    def test_max_audit_entry_is_unrelated(self) -> None:
        self.add_event(RealmAuditLog.USER_CREATED, 1)
        self.add_event(RealmAuditLog.USER_SOFT_ACTIVATED, 0.5)
        do_fill_count_stat_at_hour(self.stat, self.TIME_ZERO)
        self.assertTableState(UserCount, ["subgroup"], [["false"]])

    # Simultaneous related audit entries should not be allowed, and so not testing for that.
    def test_simultaneous_unrelated_audit_entry(self) -> None:
        self.add_event(RealmAuditLog.USER_CREATED, 1)
        self.add_event(RealmAuditLog.USER_SOFT_ACTIVATED, 1)
        do_fill_count_stat_at_hour(self.stat, self.TIME_ZERO)
        self.assertTableState(UserCount, ["subgroup"], [["false"]])

    def test_simultaneous_max_audit_entries_of_different_users(self) -> None:
        user1 = self.create_user()
        user2 = self.create_user()
        user3 = self.create_user()
        self.add_event(RealmAuditLog.USER_CREATED, 0.5, user=user1)
        self.add_event(RealmAuditLog.USER_CREATED, 0.5, user=user2)
        self.add_event(RealmAuditLog.USER_CREATED, 1, user=user3)
        self.add_event(RealmAuditLog.USER_DEACTIVATED, 0.5, user=user3)
        do_fill_count_stat_at_hour(self.stat, self.TIME_ZERO)
        self.assertTableState(UserCount, ["user", "subgroup"], [[user1, "false"], [user2, "false"]])

    def test_end_to_end_with_actions_dot_py(self) -> None:
        user1 = do_create_user(
            "email1", "password", self.default_realm, "full_name", acting_user=None
        )
        user2 = do_create_user(
            "email2", "password", self.default_realm, "full_name", acting_user=None
        )
        user3 = do_create_user(
            "email3", "password", self.default_realm, "full_name", acting_user=None
        )
        user4 = do_create_user(
            "email4", "password", self.default_realm, "full_name", acting_user=None
        )
        do_deactivate_user(user2, acting_user=None)
        do_activate_mirror_dummy_user(user3, acting_user=None)
        do_reactivate_user(user4, acting_user=None)
        end_time = floor_to_day(timezone_now()) + self.DAY
        do_fill_count_stat_at_hour(self.stat, end_time)
        for user in [user1, user3, user4]:
            self.assertTrue(
                UserCount.objects.filter(
                    user=user,
                    property=self.current_property,
                    subgroup="false",
                    end_time=end_time,
                    value=1,
                ).exists()
            )
        self.assertFalse(UserCount.objects.filter(user=user2, end_time=end_time).exists())


class TestRealmActiveHumans(AnalyticsTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        self.stat = COUNT_STATS["realm_active_humans::day"]
        self.current_property = self.stat.property

    def mark_audit_active(self, user: UserProfile, end_time: Optional[datetime] = None) -> None:
        if end_time is None:
            end_time = self.TIME_ZERO
        UserCount.objects.create(
            user=user,
            realm=user.realm,
            property="active_users_audit:is_bot:day",
            subgroup=orjson.dumps(user.is_bot).decode(),
            end_time=end_time,
            value=1,
        )

    def mark_15day_active(self, user: UserProfile, end_time: Optional[datetime] = None) -> None:
        if end_time is None:
            end_time = self.TIME_ZERO
        UserCount.objects.create(
            user=user, realm=user.realm, property="15day_actives::day", end_time=end_time, value=1
        )

    def test_basic_boolean_logic(self) -> None:
        user = self.create_user()
        self.mark_audit_active(user, end_time=self.TIME_ZERO - self.DAY)
        self.mark_15day_active(user, end_time=self.TIME_ZERO)
        self.mark_audit_active(user, end_time=self.TIME_ZERO + self.DAY)
        self.mark_15day_active(user, end_time=self.TIME_ZERO + self.DAY)

        for i in [-1, 0, 1]:
            do_fill_count_stat_at_hour(self.stat, self.TIME_ZERO + i * self.DAY)
        self.assertTableState(RealmCount, ["value", "end_time"], [[1, self.TIME_ZERO + self.DAY]])

    def test_bots_not_counted(self) -> None:
        bot = self.create_user(is_bot=True)
        self.mark_audit_active(bot)
        self.mark_15day_active(bot)
        do_fill_count_stat_at_hour(self.stat, self.TIME_ZERO)
        self.assertTableState(RealmCount, [], [])

    def test_multiple_users_realms_and_times(self) -> None:
        user1 = self.create_user()
        user2 = self.create_user()
        second_realm = do_create_realm(string_id="second", name="second")
        user3 = self.create_user(realm=second_realm)
        user4 = self.create_user(realm=second_realm)
        user5 = self.create_user(realm=second_realm)

        for user in [user1, user2, user3, user4, user5]:
            self.mark_audit_active(user)
            self.mark_15day_active(user)
        for user in [user1, user3, user4]:
            self.mark_audit_active(user, end_time=self.TIME_ZERO - self.DAY)
            self.mark_15day_active(user, end_time=self.TIME_ZERO - self.DAY)

        for i in [-1, 0, 1]:
            do_fill_count_stat_at_hour(self.stat, self.TIME_ZERO + i * self.DAY)
        self.assertTableState(
            RealmCount,
            ["value", "realm", "end_time"],
            [
                [2, self.default_realm, self.TIME_ZERO],
                [3, second_realm, self.TIME_ZERO],
                [1, self.default_realm, self.TIME_ZERO - self.DAY],
                [2, second_realm, self.TIME_ZERO - self.DAY],
            ],
        )

        # Check that adding spurious entries doesn't make a difference
        self.mark_audit_active(user1, end_time=self.TIME_ZERO + self.DAY)
        self.mark_15day_active(user2, end_time=self.TIME_ZERO + self.DAY)
        self.mark_15day_active(user2, end_time=self.TIME_ZERO - self.DAY)
        self.create_user()
        third_realm = do_create_realm(string_id="third", name="third")
        self.create_user(realm=third_realm)

        RealmCount.objects.all().delete()
        InstallationCount.objects.all().delete()
        for i in [-1, 0, 1]:
            do_fill_count_stat_at_hour(self.stat, self.TIME_ZERO + i * self.DAY)
        self.assertTableState(
            RealmCount,
            ["value", "realm", "end_time"],
            [
                [2, self.default_realm, self.TIME_ZERO],
                [3, second_realm, self.TIME_ZERO],
                [1, self.default_realm, self.TIME_ZERO - self.DAY],
                [2, second_realm, self.TIME_ZERO - self.DAY],
            ],
        )

    def test_end_to_end(self) -> None:
        user1 = do_create_user(
            "email1", "password", self.default_realm, "full_name", acting_user=None
        )
        user2 = do_create_user(
            "email2", "password", self.default_realm, "full_name", acting_user=None
        )
        do_create_user("email3", "password", self.default_realm, "full_name", acting_user=None)
        time_zero = floor_to_day(timezone_now()) + self.DAY
        update_user_activity_interval(user1, time_zero)
        update_user_activity_interval(user2, time_zero)
        do_deactivate_user(user2, acting_user=None)
        for property in [
            "active_users_audit:is_bot:day",
            "15day_actives::day",
            "realm_active_humans::day",
        ]:
            FillState.objects.create(property=property, state=FillState.DONE, end_time=time_zero)
            process_count_stat(COUNT_STATS[property], time_zero + self.DAY)
        self.assertEqual(
            RealmCount.objects.filter(
                property="realm_active_humans::day", end_time=time_zero + self.DAY, value=1
            ).count(),
            1,
        )
        self.assertEqual(RealmCount.objects.filter(property="realm_active_humans::day").count(), 1)


class GetLastIdFromServerTest(ZulipTestCase):
    def test_get_last_id_from_server_ignores_null(self) -> None:
        """
        Verifies that get_last_id_from_server ignores null remote_ids, since this goes
        against the default Postgres ordering behavior, which treats nulls as the largest value.
        """
        self.server_uuid = "6cde5f7a-1f7e-4978-9716-49f69ebfc9fe"
        self.server = RemoteZulipServer.objects.create(
            uuid=self.server_uuid,
            api_key="magic_secret_api_key",
            hostname="demo.example.com",
            last_updated=timezone_now(),
        )
        first = RemoteInstallationCount.objects.create(
            end_time=timezone_now(), server=self.server, property="test", value=1, remote_id=1
        )
        RemoteInstallationCount.objects.create(
            end_time=timezone_now(), server=self.server, property="test2", value=1, remote_id=None
        )
        result = get_last_id_from_server(self.server, RemoteInstallationCount)
        self.assertEqual(result, first.remote_id)
