from datetime import datetime, timedelta
from typing import Any
from unittest import mock

import time_machine
from django.conf import settings
from django.db import connection
from django.utils.timezone import now as timezone_now
from typing_extensions import override

from zerver.actions.user_settings import do_change_user_setting
from zerver.actions.users import do_deactivate_user
from zerver.lib.presence import format_legacy_presence_dict, get_presence_dict_by_realm
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import make_client, reset_email_visibility_to_everyone_in_zulip_realm
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.models import (
    PushDeviceToken,
    UserActivity,
    UserActivityInterval,
    UserPresence,
    UserProfile,
)
from zerver.models.realms import get_realm


class TestClientModel(ZulipTestCase):
    def test_client_stringification(self) -> None:
        """
        This test is designed to cover __str__ method for Client.
        """
        client = make_client("some_client")
        self.assertEqual(repr(client), "<Client: some_client>")


class UserPresenceModelTests(ZulipTestCase):
    def test_date_logic(self) -> None:
        UserPresence.objects.all().delete()

        user_profile = self.example_user("hamlet")
        email = user_profile.email
        presence_dct, last_update_id = get_presence_dict_by_realm(user_profile.realm)
        self.assert_length(presence_dct, 0)
        self.assertEqual(last_update_id, -1)

        self.login_user(user_profile)
        result = self.client_post("/json/users/me/presence", {"status": "active"})
        self.assert_json_success(result)

        actual_last_update_id = UserPresence.objects.all().latest("last_update_id").last_update_id

        slim_presence = False
        presence_dct, last_update_id = get_presence_dict_by_realm(user_profile.realm, slim_presence)
        self.assert_length(presence_dct, 1)
        self.assertEqual(presence_dct[email]["website"]["status"], "active")
        self.assertEqual(last_update_id, actual_last_update_id)

        slim_presence = True
        presence_dct, last_update_id = get_presence_dict_by_realm(user_profile.realm, slim_presence)
        self.assert_length(presence_dct, 1)
        info = presence_dct[str(user_profile.id)]
        self.assertEqual(set(info.keys()), {"active_timestamp", "idle_timestamp"})
        self.assertEqual(last_update_id, actual_last_update_id)

        def back_date(num_weeks: int) -> None:
            user_presence = UserPresence.objects.get(user_profile=user_profile)
            backdated_timestamp = timezone_now() - timedelta(weeks=num_weeks)
            user_presence.last_active_time = backdated_timestamp
            user_presence.last_connected_time = backdated_timestamp
            user_presence.save()

        # Simulate the presence being a week old first.  Nothing should change.
        back_date(num_weeks=1)
        presence_dct, last_update_id = get_presence_dict_by_realm(user_profile.realm)
        self.assert_length(presence_dct, 1)
        self.assertEqual(last_update_id, actual_last_update_id)

        # If the UserPresence row is three weeks old, we ignore it.
        back_date(num_weeks=3)
        presence_dct, last_update_id = get_presence_dict_by_realm(user_profile.realm)
        self.assert_length(presence_dct, 0)
        self.assertEqual(last_update_id, -1)

        # If the values are set to "never", ignore it just like for sufficiently old presence rows.
        UserPresence.objects.filter(id=user_profile.id).update(
            last_active_time=None, last_connected_time=None
        )
        presence_dct, last_update_id = get_presence_dict_by_realm(user_profile.realm)
        self.assert_length(presence_dct, 0)
        self.assertEqual(last_update_id, -1)

    def test_user_presence_row_creation_simulated_race(self) -> None:
        """
        There is a theoretical race condition, where while a UserPresence
        row is being created for a user, a concurrent process creates it first,
        right before we execute our INSERT. This conflict is handled with
        ON CONFLICT DO NOTHING in the SQL query and an early return
        if that happens.
        """

        user_profile = self.example_user("hamlet")

        UserPresence.objects.filter(user_profile=user_profile).delete()

        self.login_user(user_profile)

        def insert_row_and_return_cursor() -> Any:
            # This is the function we will inject into connection.cursor
            # to simulate the race condition.
            # When the underlying code requests a cursor, we will create
            # the UserPresence row for the user, before returning a real
            # cursor to the caller. This ensures the caller will hit the
            # INSERT conflict when it tries to execute its query.
            UserPresence.objects.create(user_profile=user_profile, realm=user_profile.realm)

            cursor = connection.cursor()
            return cursor

        with (
            mock.patch("zerver.actions.presence.connection") as mock_connection,
            self.assertLogs("zerver.actions.presence", level="INFO") as mock_logs,
        ):
            # This is a tricky mock. We need to set things up so that connection.cursor()
            # in do_update_user_presence runs our custom code when the caller tries to
            # enter the context manager.
            # We also need to take care to only affect the connection that exists in
            # zerver.actions.presence rather than affecting the entire django.db.connection,
            # as that would break code higher up in the stack.
            mock_connection.cursor.return_value.__enter__.side_effect = insert_row_and_return_cursor

            result = self.client_post("/json/users/me/presence", {"status": "active"})

        # The request finished gracefully and the situation was logged:
        self.assert_json_success(result)
        self.assertEqual(
            mock_logs.output,
            [
                f"INFO:zerver.actions.presence:UserPresence row already created for {user_profile.id}, returning."
            ],
        )

    def test_last_update_id_logic(self) -> None:
        slim_presence = True
        UserPresence.objects.all().delete()

        user_profile = self.example_user("hamlet")
        presence_dct, last_update_id = get_presence_dict_by_realm(
            user_profile.realm, slim_presence, last_update_id_fetched_by_client=-1
        )
        self.assert_length(presence_dct, 0)
        self.assertEqual(last_update_id, -1)

        self.login_user(user_profile)
        result = self.client_post("/json/users/me/presence", {"status": "active"})
        self.assert_json_success(result)

        actual_last_update_id = UserPresence.objects.all().latest("last_update_id").last_update_id

        presence_dct, last_update_id = get_presence_dict_by_realm(
            user_profile.realm, slim_presence, last_update_id_fetched_by_client=-1
        )
        self.assert_length(presence_dct, 1)
        self.assertEqual(last_update_id, actual_last_update_id)

        # Now pass last_update_id as of this latest fetch. The server should only query for data
        # updated after that. There's no such data, so we get no presence data back and the
        # returned last_update_id remains the same.
        presence_dct, last_update_id = get_presence_dict_by_realm(
            user_profile.realm,
            slim_presence,
            last_update_id_fetched_by_client=actual_last_update_id,
        )
        self.assert_length(presence_dct, 0)
        self.assertEqual(last_update_id, actual_last_update_id)

        # Now generate a new update in the realm.
        iago = self.example_user("iago")
        self.login_user(iago)
        result = self.client_post("/json/users/me/presence", {"status": "active"})

        # There's a new update now, so we can expect it to be fetched; and no older data.
        presence_dct, last_update_id = get_presence_dict_by_realm(
            user_profile.realm,
            slim_presence,
            last_update_id_fetched_by_client=actual_last_update_id,
        )
        self.assert_length(presence_dct, 1)
        self.assertEqual(presence_dct.keys(), {str(iago.id)})
        # last_update_id is incremented due to the new update.
        self.assertEqual(last_update_id, actual_last_update_id + 1)

    def test_pushable_always_false(self) -> None:
        # This field was never used by clients of the legacy API, so we
        # just want to have it always set to False for API format compatibility.
        UserPresence.objects.all().delete()

        user_profile = self.example_user("hamlet")
        email = user_profile.email

        self.login_user(user_profile)
        result = self.client_post("/json/users/me/presence", {"status": "active"})
        self.assert_json_success(result)

        def pushable() -> bool:
            presence_dct, _ = get_presence_dict_by_realm(user_profile.realm)
            self.assert_length(presence_dct, 1)
            return presence_dct[email]["website"]["pushable"]

        self.assertFalse(pushable())

        user_profile.enable_offline_push_notifications = True
        user_profile.save()

        self.assertFalse(pushable())

        PushDeviceToken.objects.create(
            user=user_profile,
            kind=PushDeviceToken.APNS,
        )
        self.assertFalse(pushable())


class UserPresenceTests(ZulipTestCase):
    @override
    def setUp(self) -> None:
        """
        Create some initial, old presence data to make the intended set up
        simpler for the tests.
        """
        super().setUp()
        realm = get_realm("zulip")
        now = timezone_now()
        initial_presence = now - timedelta(days=365)
        UserPresence.objects.bulk_create(
            [
                UserPresence(
                    user_profile=user_profile,
                    realm=user_profile.realm,
                    last_active_time=initial_presence,
                    last_connected_time=initial_presence,
                )
                for user_profile in UserProfile.objects.filter(realm=realm)
            ]
        )

    def test_invalid_presence(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        result = self.client_post("/json/users/me/presence", {"status": "foo"})
        self.assert_json_error(result, "Invalid status: foo")

    def test_history_limit_days_api(self) -> None:
        UserPresence.objects.all().delete()

        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")
        iago = self.example_user("iago")

        self.login_user(hamlet)

        params = dict(status="idle", last_update_id=-1)
        result = self.client_post("/json/users/me/presence", params)
        self.assert_json_success(result)

        self.login_user(othello)
        params = dict(status="idle", last_update_id=-1)
        result = self.client_post("/json/users/me/presence", params)
        self.assert_json_success(result)

        othello_presence = UserPresence.objects.get(user_profile=othello)
        assert othello_presence.last_connected_time is not None
        othello_presence.last_connected_time = othello_presence.last_connected_time - timedelta(
            days=100
        )
        othello_presence.save()

        # The initial presence state has been set up for the test. Now we can proceed with verifying
        # the behavior of the history_limit_days parameter.
        self.login_user(iago)
        params = dict(status="idle", last_update_id=-1, history_limit_days=50)
        result = self.client_post("/json/users/me/presence", params)
        json = self.assert_json_success(result)
        presences = json["presences"]
        self.assertEqual(set(presences.keys()), {str(hamlet.id), str(iago.id)})

        params = dict(status="idle", last_update_id=-1, history_limit_days=101)
        result = self.client_post("/json/users/me/presence", params)
        json = self.assert_json_success(result)
        presences = json["presences"]
        self.assertEqual(set(presences.keys()), {str(hamlet.id), str(iago.id), str(othello.id)})

        # history_limit_days=0 means the client doesn't want any presence data.
        params = dict(status="idle", last_update_id=-1, history_limit_days=0)
        result = self.client_post("/json/users/me/presence", params)
        json = self.assert_json_success(result)
        presences = json["presences"]
        self.assertEqual(set(presences.keys()), set())

    def test_last_update_id_api(self) -> None:
        UserPresence.objects.all().delete()

        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")

        self.login_user(hamlet)

        params = dict(status="idle", last_update_id=-1)
        result = self.client_post("/json/users/me/presence", params)
        json = self.assert_json_success(result)
        self.assertEqual(set(json["presences"].keys()), {str(hamlet.id)})

        # In tests, the presence update is processed immediately rather than in the background
        # in the queue worker, so we see it reflected immediately.
        last_update_id = UserPresence.objects.latest("last_update_id").last_update_id
        self.assertEqual(json["presence_last_update_id"], last_update_id)

        # Briefly test that we include presence_last_update_id in the response
        # also in the legacy format API with slim_presence=False.
        # Re-doing an idle status so soon doesn't cause updates
        # so this doesn't mutate any state.
        params = dict(status="idle", slim_presence="false")
        result = self.client_post("/json/users/me/presence", params)
        json = self.assert_json_success(result)
        self.assertEqual(json["presence_last_update_id"], last_update_id)

        self.login_user(othello)
        params = dict(status="idle", last_update_id=-1)
        result = self.client_post("/json/users/me/presence", params)
        json = self.assert_json_success(result)
        self.assertEqual(set(json["presences"].keys()), {str(hamlet.id), str(othello.id)})
        self.assertEqual(json["presence_last_update_id"], last_update_id + 1)

        last_update_id += 1
        # Immediately sending an idle status again doesn't cause updates, so the server
        # doesn't have any new data since last_update_id to return.
        params = dict(status="idle", last_update_id=last_update_id)
        result = self.client_post("/json/users/me/presence", params)
        json = self.assert_json_success(result)
        self.assertEqual(set(json["presences"].keys()), set())
        # No new data, so the last_update_id is returned back.
        self.assertEqual(json["presence_last_update_id"], last_update_id)

        # hamlet sends an active status. othello will next check presence and we'll
        # want to verify he gets hamlet's update and nothing else.
        self.login_user(hamlet)
        params = dict(status="active", last_update_id=-1)
        result = self.client_post("/json/users/me/presence", params)
        json = self.assert_json_success(result)

        # Make sure UserPresence.last_update_id is incremented.
        self.assertEqual(
            UserPresence.objects.latest("last_update_id").last_update_id, last_update_id + 1
        )

        # Now othello checks presence and should get hamlet's update.
        self.login_user(othello)
        params = dict(status="idle", last_update_id=last_update_id)
        result = self.client_post("/json/users/me/presence", params)
        json = self.assert_json_success(result)
        self.assertEqual(set(json["presences"].keys()), {str(hamlet.id)})
        self.assertEqual(json["presence_last_update_id"], last_update_id + 1)

    def test_last_update_id_api_no_data_edge_cases(self) -> None:
        hamlet = self.example_user("hamlet")

        self.login_user(hamlet)

        UserPresence.objects.all().delete()

        params = dict(status="idle", last_update_id=-1)
        # Make do_update_user_presence a noop. This simulates a scenario as if there
        # is no presence data.
        # This is not a realistic situation, because the presence update that the user
        # is making will by itself bump the last_update_id which will be reflected
        # here in the response - but it's still good to test the code is robust
        # and works fine in such an edge case.
        # In such a situation, he should get his last_update_id=-1 back.
        with mock.patch("zerver.actions.presence.do_update_user_presence"):
            result = self.client_post("/json/users/me/presence", params)
        json = self.assert_json_success(result)

        self.assertEqual(set(json["presences"].keys()), set())
        self.assertEqual(json["presence_last_update_id"], -1)
        self.assertFalse(UserPresence.objects.exists())

        # Now check the same, but hamlet doesn't pass last_update_id at all,
        # like an old slim_presence client would due to an implementation
        # prior to the introduction of last_update_id.
        params = dict(status="idle")
        with mock.patch("zerver.actions.presence.do_update_user_presence"):
            result = self.client_post("/json/users/me/presence", params)
        json = self.assert_json_success(result)
        self.assertEqual(set(json["presences"].keys()), set())

        # When there's no data and the client didn't provide a last_update_id
        # value that we could reflect back to it, we fall back to -1.
        self.assertEqual(json["presence_last_update_id"], -1)
        self.assertFalse(UserPresence.objects.exists())

    def test_set_idle(self) -> None:
        client = "website"

        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")

        self.login_user(hamlet)

        params = dict(status="idle")
        result = self.client_post("/json/users/me/presence", params)
        json = self.assert_json_success(result)
        self.assertEqual(json["presences"][hamlet.email][client]["status"], "idle")
        self.assertIn("timestamp", json["presences"][hamlet.email][client])
        self.assertIsInstance(json["presences"][hamlet.email][client]["timestamp"], int)
        self.assertEqual(set(json["presences"].keys()), {hamlet.email})

        self.login_user(othello)
        params = dict(status="idle", slim_presence="true")
        result = self.client_post("/json/users/me/presence", params)
        json = self.assert_json_success(result)
        presences = json["presences"]
        self.assertEqual(
            set(presences.keys()),
            {str(hamlet.id), str(othello.id)},
        )
        hamlet_info = presences[str(hamlet.id)]
        othello_info = presences[str(othello.id)]

        self.assertEqual(set(hamlet_info.keys()), {"idle_timestamp", "active_timestamp"})
        self.assertEqual(set(othello_info.keys()), {"idle_timestamp", "active_timestamp"})

        self.assertGreaterEqual(
            othello_info["idle_timestamp"],
            hamlet_info["idle_timestamp"],
        )

    def test_set_active(self) -> None:
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")

        self.login_user(hamlet)
        client = "website"

        params = dict(status="idle")
        result = self.client_post("/json/users/me/presence", params)
        response_dict = self.assert_json_success(result)

        self.assertEqual(response_dict["presences"][hamlet.email][client]["status"], "idle")

        self.login("othello")
        params = dict(status="idle")
        result = self.client_post("/json/users/me/presence", params)
        json = self.assert_json_success(result)

        self.assertEqual(json["presences"][othello.email][client]["status"], "idle")
        self.assertEqual(json["presences"][hamlet.email][client]["status"], "idle")

        params = dict(status="active")
        result = self.client_post("/json/users/me/presence", params)
        json = self.assert_json_success(result)

        self.assertEqual(json["presences"][othello.email][client]["status"], "active")
        self.assertEqual(json["presences"][hamlet.email][client]["status"], "idle")

        self.login_user(hamlet)
        params = dict(status="active", slim_presence="true")
        result = self.client_post("/json/users/me/presence", params)
        json = self.assert_json_success(result)

        presences = json["presences"]
        self.assertEqual(
            set(presences.keys()),
            {str(hamlet.id), str(othello.id)},
        )
        othello_info = presences[str(othello.id)]
        hamlet_info = presences[str(hamlet.id)]

        self.assertEqual(
            set(othello_info.keys()),
            {"active_timestamp", "idle_timestamp"},
        )

        self.assertEqual(
            set(hamlet_info.keys()),
            {"active_timestamp", "idle_timestamp"},
        )

        self.assertGreaterEqual(
            hamlet_info["active_timestamp"],
            othello_info["active_timestamp"],
        )

    @mock.patch("stripe.Customer.list", return_value=[])
    def test_new_user_input(self, unused_mock: mock.Mock) -> None:
        """Mostly a test for UserActivityInterval"""
        user_profile = self.example_user("hamlet")
        self.login("hamlet")
        self.assertEqual(UserActivityInterval.objects.filter(user_profile=user_profile).count(), 0)
        time_zero = timezone_now().replace(microsecond=0)
        with time_machine.travel(time_zero, tick=False):
            result = self.client_post(
                "/json/users/me/presence", {"status": "active", "new_user_input": "true"}
            )
        self.assert_json_success(result)
        self.assertEqual(UserActivityInterval.objects.filter(user_profile=user_profile).count(), 1)
        interval = UserActivityInterval.objects.get(user_profile=user_profile)
        self.assertEqual(interval.start, time_zero)
        self.assertEqual(interval.end, time_zero + UserActivityInterval.MIN_INTERVAL_LENGTH)

        second_time = time_zero + timedelta(seconds=600)
        # Extent the interval
        with time_machine.travel(second_time, tick=False):
            result = self.client_post(
                "/json/users/me/presence", {"status": "active", "new_user_input": "true"}
            )
        self.assert_json_success(result)
        self.assertEqual(UserActivityInterval.objects.filter(user_profile=user_profile).count(), 1)
        interval = UserActivityInterval.objects.get(user_profile=user_profile)
        self.assertEqual(interval.start, time_zero)
        self.assertEqual(interval.end, second_time + UserActivityInterval.MIN_INTERVAL_LENGTH)

        third_time = time_zero + timedelta(seconds=6000)
        with time_machine.travel(third_time, tick=False):
            result = self.client_post(
                "/json/users/me/presence", {"status": "active", "new_user_input": "true"}
            )
        self.assert_json_success(result)
        self.assertEqual(UserActivityInterval.objects.filter(user_profile=user_profile).count(), 2)
        interval = UserActivityInterval.objects.filter(user_profile=user_profile).order_by("start")[
            0
        ]
        self.assertEqual(interval.start, time_zero)
        self.assertEqual(interval.end, second_time + UserActivityInterval.MIN_INTERVAL_LENGTH)
        interval = UserActivityInterval.objects.filter(user_profile=user_profile).order_by("start")[
            1
        ]
        self.assertEqual(interval.start, third_time)
        self.assertEqual(interval.end, third_time + UserActivityInterval.MIN_INTERVAL_LENGTH)

        # Now test /activity with actual data
        user_profile.is_staff = True
        user_profile.save()
        result = self.client_get("/activity")
        self.assertEqual(result.status_code, 200)

    def test_filter_presence_idle_user_ids(self) -> None:
        user_profile = self.example_user("hamlet")
        from zerver.actions.message_send import filter_presence_idle_user_ids

        self.login("hamlet")

        # Ensure we're starting with a clean slate.
        UserPresence.objects.all().delete()
        self.assertEqual(filter_presence_idle_user_ids({user_profile.id}), [user_profile.id])

        # Create a first presence for the user. It's the first one and has status idle,
        # so it'll initialize just last_connected time with the current time and last_active_time with None.
        # Thus the user will be considered idle.
        self.client_post("/json/users/me/presence", {"status": "idle"})
        self.assertEqual(filter_presence_idle_user_ids({user_profile.id}), [user_profile.id])

        # Now create a first presence with active status and check that the user is not filtered.
        # This initializes the presence with both last_connected_time and last_active_time set to
        # current time.
        self.client_post("/json/users/me/presence", {"status": "active"})
        self.assertEqual(filter_presence_idle_user_ids({user_profile.id}), [])

        # Make last_active_time be older than OFFLINE_THRESHOLD_SECS. That should
        # get the user filtered.
        UserPresence.objects.filter(user_profile=user_profile).update(
            last_active_time=timezone_now() - timedelta(seconds=settings.OFFLINE_THRESHOLD_SECS + 1)
        )
        self.assertEqual(filter_presence_idle_user_ids({user_profile.id}), [user_profile.id])

        # Sending an idle presence doesn't change anything for filtering.
        self.client_post("/json/users/me/presence", {"status": "idle"})
        self.assertEqual(filter_presence_idle_user_ids({user_profile.id}), [user_profile.id])

        # Active presence from the mobile app should count (in the old API it didn't)
        self.client_post(
            "/json/users/me/presence", {"status": "active"}, HTTP_USER_AGENT="ZulipMobile/1.0"
        )
        self.assertEqual(filter_presence_idle_user_ids({user_profile.id}), [])

    def test_no_mit(self) -> None:
        """Zephyr mirror realms such as MIT never get a list of users"""
        user = self.mit_user("espuser")
        self.login_user(user)
        result = self.client_post("/json/users/me/presence", {"status": "idle"}, subdomain="zephyr")
        response_dict = self.assert_json_success(result)
        self.assertEqual(response_dict["presences"], {})
        self.assertEqual(response_dict["presence_last_update_id"], -1)

    def test_mirror_presence(self) -> None:
        """Zephyr mirror realms find out the status of their mirror bot"""
        user_profile = self.mit_user("espuser")
        self.login_user(user_profile)

        def post_presence() -> dict[str, Any]:
            result = self.client_post(
                "/json/users/me/presence", {"status": "idle"}, subdomain="zephyr"
            )
            json = self.assert_json_success(result)
            return json

        json = post_presence()
        self.assertEqual(json["zephyr_mirror_active"], False)

        self._simulate_mirror_activity_for_user(user_profile)
        json = post_presence()
        self.assertEqual(json["zephyr_mirror_active"], True)

    def _simulate_mirror_activity_for_user(self, user_profile: UserProfile) -> None:
        last_visit = timezone_now()
        client = make_client("zephyr_mirror")

        UserActivity.objects.get_or_create(
            user_profile=user_profile,
            client=client,
            query="get_events",
            count=2,
            last_visit=last_visit,
        )

    def test_same_realm(self) -> None:
        espuser = self.mit_user("espuser")
        self.login_user(espuser)
        self.client_post("/json/users/me/presence", {"status": "idle"}, subdomain="zephyr")
        self.logout()

        # Ensure we don't see hamlet@zulip.com information leakage
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)
        result = self.client_post("/json/users/me/presence", {"status": "idle"})
        json = self.assert_json_success(result)
        self.assertEqual(json["presences"][hamlet.email]["website"]["status"], "idle")
        self.assertEqual(
            json["presences"].keys(),
            {hamlet.email},
        )

    def test_null_timestamps_handling(self) -> None:
        """
        Checks that the API handles presences with null presence timestamps correctly.
        The data model now supports them being null, but the API should still return
        valid timestamps for backwards compatibility - using date_joined as the default
        to fall back on. Also it should correctly filter out users with null presence
        just like it would have filtered them out if they had very old presence.
        """
        self.login("hamlet")

        othello = self.example_user("othello")
        # Set a predictable value for date_joined
        othello.date_joined = timezone_now() - timedelta(days=1)
        othello.save()
        UserPresence.objects.filter(user_profile=othello).update(
            last_active_time=None, last_connected_time=None
        )

        result = self.client_get(f"/json/users/{othello.id}/presence")
        result_dict = self.assert_json_success(result)

        # Ensure date_joined was used as the fallback.
        self.assertEqual(
            result_dict["presence"]["website"]["timestamp"],
            datetime_to_timestamp(othello.date_joined),
        )

        # Othello has null presence values, so should not appear in the /realm/presence response
        # just like a user with over two weeks old presence.
        result = self.client_get("/json/realm/presence")
        result_dict = self.assert_json_success(result)
        self.assertEqual(result_dict["presences"], {})

        # If othello's presence is fresh however, it should appear in the response.
        now = timezone_now()
        UserPresence.objects.filter(user_profile=othello).update(
            last_active_time=now, last_connected_time=now
        )
        result = self.client_get("/json/realm/presence")
        result_dict = self.assert_json_success(result)
        self.assertEqual(set(result_dict["presences"].keys()), {othello.email})

    def test_query_counts(self) -> None:
        self.login("hamlet")
        with self.assert_database_query_count(6):
            # 1. session
            # 2. narrow user cache
            # 3. client
            # 4. lock the userpresence row
            # 5. update the userpresence row
            # 6. select other userpresence data
            self.assert_json_success(
                self.client_post("/json/users/me/presence", {"status": "active"})
            )

        with self.assert_database_query_count(3, keep_cache_warm=True):
            # With a warm cache, we skip the first three queries
            self.assert_json_success(
                self.client_post("/json/users/me/presence", {"status": "active"})
            )

        with self.assert_database_query_count(3, keep_cache_warm=True):
            # It's the same story if we're becoming idle, as well
            self.assert_json_success(
                self.client_post("/json/users/me/presence", {"status": "idle"})
            )


class SingleUserPresenceTests(ZulipTestCase):
    def test_email_access(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)

        other_user = self.example_user("othello")
        other_user.email = "email@zulip.com"
        other_user.delivery_email = "delivery_email@zulip.com"
        other_user.save()

        # Note that we don't leak any info on delivery emails.
        result = self.client_get("/json/users/delivery_email@zulip.com/presence")
        self.assert_json_error(result, "No such user")

        result = self.client_get("/json/users/not_even_in_realm@zulip.com/presence")
        self.assert_json_error(result, "No such user")

        # For a known email, we may simply complain about lack of presence info.
        result = self.client_get("/json/users/email@zulip.com/presence")
        self.assert_json_error(result, "No presence data for email@zulip.com")

    def test_single_user_get(self) -> None:
        reset_email_visibility_to_everyone_in_zulip_realm()

        # First, we set up the test with some data
        user = self.example_user("othello")
        self.login_user(user)
        result = self.client_post("/json/users/me/presence", {"status": "active"})
        result = self.client_post(
            "/json/users/me/presence", {"status": "active"}, HTTP_USER_AGENT="ZulipDesktop/1.0"
        )
        result = self.api_post(
            user,
            "/api/v1/users/me/presence",
            {"status": "idle"},
            HTTP_USER_AGENT="ZulipAndroid/1.0",
        )
        self.assert_json_success(result)

        # Check some error conditions
        result = self.client_get("/json/users/nonexistence@zulip.com/presence")
        self.assert_json_error(result, "No such user")

        result = self.client_get("/json/users/cordelia@zulip.com/presence")
        self.assert_json_error(result, "No presence data for cordelia@zulip.com")

        cordelia = self.example_user("cordelia")
        result = self.client_get(f"/json/users/{cordelia.id}/presence")
        self.assert_json_error(result, f"No presence data for {cordelia.id}")

        do_deactivate_user(self.example_user("cordelia"), acting_user=None)
        result = self.client_get("/json/users/cordelia@zulip.com/presence")
        self.assert_json_error(result, "No such user")

        result = self.client_get(f"/json/users/{cordelia.id}/presence")
        self.assert_json_error(result, "No such user")

        result = self.client_get("/json/users/default-bot@zulip.com/presence")
        self.assert_json_error(result, "Presence is not supported for bot users.")

        sipbtest = self.mit_user("sipbtest")
        self.login_user(sipbtest)
        result = self.client_get("/json/users/othello@zulip.com/presence", subdomain="zephyr")
        self.assert_json_error(result, "No such user")

        othello = self.example_user("othello")
        result = self.client_get(f"/json/users/{othello.id}/presence", subdomain="zephyr")
        self.assert_json_error(result, "No such user")

        self.set_up_db_for_testing_user_access()
        self.login("polonius")
        with self.settings(CAN_ACCESS_ALL_USERS_GROUP_LIMITS_PRESENCE=True):
            result = self.client_get(f"/json/users/{othello.id}/presence")
        self.assert_json_error(result, "Insufficient permission")

        result = self.client_get(f"/json/users/{othello.id}/presence")
        result_dict = self.assert_json_success(result)
        self.assertEqual(set(result_dict["presence"].keys()), {"website", "aggregated"})
        self.assertEqual(set(result_dict["presence"]["website"].keys()), {"status", "timestamp"})

        # Then, we check everything works
        self.login("hamlet")
        result = self.client_get("/json/users/othello@zulip.com/presence")
        result_dict = self.assert_json_success(result)
        self.assertEqual(set(result_dict["presence"].keys()), {"website", "aggregated"})
        self.assertEqual(set(result_dict["presence"]["website"].keys()), {"status", "timestamp"})

        result = self.client_get(f"/json/users/{othello.id}/presence")
        result_dict = self.assert_json_success(result)
        self.assertEqual(set(result_dict["presence"].keys()), {"website", "aggregated"})
        self.assertEqual(set(result_dict["presence"]["website"].keys()), {"status", "timestamp"})

    def test_ping_only(self) -> None:
        self.login("othello")
        req = dict(
            status="active",
            ping_only="true",
        )
        result = self.client_post("/json/users/me/presence", req)
        self.assertEqual(self.assert_json_success(result)["msg"], "")


class UserPresenceAggregationTests(ZulipTestCase):
    def _send_presence_for_aggregated_tests(
        self, user: UserProfile, status: str, validate_time: datetime
    ) -> dict[str, dict[str, Any]]:
        self.login_user(user)
        # First create some initial, old presence to avoid the details of the edge case of initial
        # presence creation messing with the intended setup.
        with time_machine.travel((validate_time - timedelta(days=365)), tick=False):
            self.client_post("/json/users/me/presence", {"status": status})

        with time_machine.travel((validate_time - timedelta(seconds=5)), tick=False):
            self.client_post("/json/users/me/presence", {"status": status})
        with time_machine.travel((validate_time - timedelta(seconds=2)), tick=False):
            self.api_post(
                user,
                "/api/v1/users/me/presence",
                {"status": status},
                HTTP_USER_AGENT="ZulipAndroid/1.0",
            )
        with time_machine.travel((validate_time - timedelta(seconds=7)), tick=False):
            latest_result = self.api_post(
                user,
                "/api/v1/users/me/presence",
                {"status": status},
                HTTP_USER_AGENT="ZulipIOS/1.0",
            )
        latest_result_dict = self.assert_json_success(latest_result)
        self.assertDictEqual(
            latest_result_dict["presences"][user.email]["aggregated"],
            {
                "status": status,
                "timestamp": datetime_to_timestamp(validate_time - timedelta(seconds=5)),
                # We no longer store the client information, but keep the field in these dicts,
                # with the value 'website' for backwards compatibility.
                "client": "website",
            },
        )

        result = self.client_get(f"/json/users/{user.email}/presence")
        return self.assert_json_success(result)

    def test_aggregated_info(self) -> None:
        user = self.example_user("othello")
        offset = timedelta(seconds=settings.PRESENCE_UPDATE_MIN_FREQ_SECONDS + 1)
        validate_time = timezone_now() - offset
        self._send_presence_for_aggregated_tests(user, "active", validate_time)
        with time_machine.travel((validate_time + offset), tick=False):
            result = self.api_post(
                user,
                "/api/v1/users/me/presence",
                {"status": "active"},
                HTTP_USER_AGENT="ZulipTestDev/1.0",
            )
        result_dict = self.assert_json_success(result)
        self.assertDictEqual(
            result_dict["presences"][user.email]["aggregated"],
            {
                "status": "active",
                "timestamp": datetime_to_timestamp(validate_time + offset),
                "client": "website",  # This fields is no longer used and is permamenently set to 'website'.
            },
        )

    def test_aggregated_presence_active(self) -> None:
        user = self.example_user("othello")
        validate_time = timezone_now()
        result_dict = self._send_presence_for_aggregated_tests(user, "active", validate_time)
        self.assertDictEqual(
            result_dict["presence"]["aggregated"],
            {
                "status": "active",
                "timestamp": datetime_to_timestamp(validate_time - timedelta(seconds=5)),
            },
        )

    def test_aggregated_presence_idle(self) -> None:
        user = self.example_user("othello")
        validate_time = timezone_now()
        result_dict = self._send_presence_for_aggregated_tests(user, "idle", validate_time)
        self.assertDictEqual(
            result_dict["presence"]["aggregated"],
            {
                "status": "idle",
                "timestamp": datetime_to_timestamp(validate_time - timedelta(seconds=5)),
            },
        )

    def test_aggregated_presence_mixed(self) -> None:
        user = self.example_user("othello")
        self.login_user(user)
        validate_time = timezone_now()
        self._send_presence_for_aggregated_tests(user, "idle", validate_time)
        with time_machine.travel((validate_time - timedelta(seconds=3)), tick=False):
            result_dict = self.api_post(
                user,
                "/api/v1/users/me/presence",
                {"status": "active"},
                HTTP_USER_AGENT="ZulipTestDev/1.0",
            ).json()

        self.assertDictEqual(
            result_dict["presences"][user.email]["aggregated"],
            {
                "client": "website",
                "status": "active",
                "timestamp": datetime_to_timestamp(validate_time - timedelta(seconds=3)),
            },
        )

    def test_aggregated_presence_offline(self) -> None:
        user = self.example_user("othello")
        self.login_user(user)
        validate_time = timezone_now()
        result_dict = self._send_presence_for_aggregated_tests(user, "idle", validate_time)

        with time_machine.travel(
            (validate_time + timedelta(seconds=settings.OFFLINE_THRESHOLD_SECS + 1)),
            tick=False,
        ):
            # After settings.OFFLINE_THRESHOLD_SECS + 1 this generated, recent presence data
            # will count as offline.
            result = self.client_get(f"/json/users/{user.email}/presence")
        result_dict = self.assert_json_success(result)

        self.assertDictEqual(
            result_dict["presence"]["aggregated"],
            {
                "status": "offline",
                "timestamp": datetime_to_timestamp(validate_time - timedelta(seconds=5)),
            },
        )


class GetRealmStatusesTest(ZulipTestCase):
    def test_get_statuses(self) -> None:
        # Set up the test by simulating users reporting their presence data.
        othello = self.example_user("othello")
        hamlet = self.example_user("hamlet")
        self.example_user("cordelia")

        result = self.api_post(
            othello,
            "/api/v1/users/me/presence",
            dict(status="active"),
            HTTP_USER_AGENT="ZulipAndroid/1.0",
        )

        result = self.api_post(
            hamlet,
            "/api/v1/users/me/presence",
            dict(status="idle"),
            HTTP_USER_AGENT="ZulipDesktop/1.0",
        )
        json = self.assert_json_success(result)
        self.assertEqual(set(json["presences"].keys()), {hamlet.email, othello.email})

        result = self.api_post(
            hamlet,
            "/api/v1/users/me/presence",
            dict(status="active", slim_presence="true"),
            HTTP_USER_AGENT="ZulipDesktop/1.0",
        )
        json = self.assert_json_success(result)
        self.assertEqual(set(json["presences"].keys()), {str(hamlet.id), str(othello.id)})

        # Check that a bot can fetch the presence data for the realm.
        result = self.api_get(self.example_user("default_bot"), "/api/v1/realm/presence")
        json = self.assert_json_success(result)
        self.assertEqual(set(json["presences"].keys()), {hamlet.email, othello.email})

        # Check that polonius cannot fetch presence data for inaccessible user Othello
        # if CAN_ACCESS_ALL_USERS_GROUP_LIMITS_PRESENCE is set to True.
        self.set_up_db_for_testing_user_access()
        polonius = self.example_user("polonius")
        with self.settings(CAN_ACCESS_ALL_USERS_GROUP_LIMITS_PRESENCE=True):
            result = self.api_get(polonius, "/api/v1/realm/presence")
        json = self.assert_json_success(result)
        self.assertEqual(set(json["presences"].keys()), {hamlet.email})

        result = self.api_get(polonius, "/api/v1/realm/presence")
        json = self.assert_json_success(result)
        self.assertEqual(set(json["presences"].keys()), {hamlet.email, othello.email})

        with self.settings(CAN_ACCESS_ALL_USERS_GROUP_LIMITS_PRESENCE=True):
            result = self.api_post(
                polonius,
                "/api/v1/users/me/presence",
                dict(status="idle"),
                HTTP_USER_AGENT="ZulipDesktop/1.0",
            )
        json = self.assert_json_success(result)
        self.assertEqual(set(json["presences"].keys()), {hamlet.email, polonius.email})

        result = self.api_post(
            polonius,
            "/api/v1/users/me/presence",
            dict(status="idle"),
            HTTP_USER_AGENT="ZulipDesktop/1.0",
        )
        json = self.assert_json_success(result)
        self.assertEqual(
            set(json["presences"].keys()), {hamlet.email, polonius.email, othello.email}
        )

    def test_do_change_user_setting_presence_enabled(self) -> None:
        """
        Tests the logic for backdating user's presence
        """
        hamlet = self.example_user("hamlet")
        UserPresence.objects.filter(user_profile=hamlet).delete()
        now = timezone_now()

        # If the user has no presence at all, disabling presence_enabled should not change that state.
        with time_machine.travel(now, tick=False), self.captureOnCommitCallbacks(execute=True):
            do_change_user_setting(hamlet, "presence_enabled", False, acting_user=hamlet)
        self.assertFalse(UserPresence.objects.filter(user_profile=hamlet).exists())

        # Enabling presence_enabled creates a new, current presence record.
        with time_machine.travel(now, tick=False), self.captureOnCommitCallbacks(execute=True):
            do_change_user_setting(hamlet, "presence_enabled", True, acting_user=hamlet)

        presence = UserPresence.objects.get(user_profile=hamlet)
        self.assertEqual(presence.last_connected_time, now)
        self.assertEqual(presence.last_active_time, now)

        # Disabling presence_enabled with a very recent presence record will cause it to get backdated
        # by some minutes to make the user immediately appear offline.
        with time_machine.travel(now, tick=False), self.captureOnCommitCallbacks(execute=True):
            do_change_user_setting(hamlet, "presence_enabled", False, acting_user=hamlet)
        presence = UserPresence.objects.get(user_profile=hamlet)
        self.assertEqual(
            presence.last_connected_time,
            now
            - timedelta(
                seconds=settings.OFFLINE_THRESHOLD_SECS
                + settings.PRESENCE_UPDATE_MIN_FREQ_SECONDS
                + 10
            ),
        )
        self.assertEqual(
            presence.last_active_time,
            now
            - timedelta(
                seconds=settings.OFFLINE_THRESHOLD_SECS
                + settings.PRESENCE_UPDATE_MIN_FREQ_SECONDS
                + 10
            ),
        )

        # Now we set up a very old presence record.
        hamlet.presence_enabled = True
        hamlet.save()
        presence.last_connected_time = now - timedelta(days=100)
        presence.last_active_time = now - timedelta(days=100)
        presence.save()

        # With a very old presence record, disabling presence_enabled should not change that.
        with time_machine.travel(now, tick=False), self.captureOnCommitCallbacks(execute=True):
            do_change_user_setting(hamlet, "presence_enabled", False, acting_user=hamlet)
        presence = UserPresence.objects.get(user_profile=hamlet)
        self.assertEqual(presence.last_connected_time, now - timedelta(days=100))
        self.assertEqual(presence.last_active_time, now - timedelta(days=100))

        hamlet.presence_enabled = True
        hamlet.save()
        # Now set up the final edge case - a very old last_active_time and a recent last_connected_time.
        # In this case, last_connected_time should get backdated (to ensure the user appears offline),
        # without pushing last_active_time forward.
        presence.last_active_time = now - timedelta(days=100)
        presence.last_connected_time = now - timedelta(seconds=1)
        presence.save()

        with time_machine.travel(now, tick=False), self.captureOnCommitCallbacks(execute=True):
            do_change_user_setting(hamlet, "presence_enabled", False, acting_user=hamlet)
        presence = UserPresence.objects.get(user_profile=hamlet)
        self.assertEqual(
            presence.last_connected_time,
            now
            - timedelta(
                seconds=settings.OFFLINE_THRESHOLD_SECS
                + settings.PRESENCE_UPDATE_MIN_FREQ_SECONDS
                + 10
            ),
        )
        self.assertEqual(presence.last_active_time, now - timedelta(days=100))

    def test_presence_disabled(self) -> None:
        # Disable presence status and test whether the presence
        # is reported or not.
        othello = self.example_user("othello")
        hamlet = self.example_user("hamlet")
        othello.presence_enabled = False
        hamlet.presence_enabled = True
        othello.save(update_fields=["presence_enabled"])
        hamlet.save(update_fields=["presence_enabled"])

        # Verify the initial UserActivityInterval state is as expected.
        self.assertEqual(UserActivityInterval.objects.filter(user_profile=othello).count(), 0)

        result = self.api_post(
            othello,
            "/api/v1/users/me/presence",
            # Include new_user_input=true to test the UserActivityInterval update
            # codepath.
            dict(status="active", new_user_input="true"),
            HTTP_USER_AGENT="ZulipAndroid/1.0",
        )
        result = self.api_post(
            hamlet,
            "/api/v1/users/me/presence",
            dict(status="idle"),
            HTTP_USER_AGENT="ZulipDesktop/1.0",
        )

        json = self.assert_json_success(result)

        # Othello's presence status is disabled so it won't be reported.
        self.assertEqual(set(json["presences"].keys()), {hamlet.email})
        # However, the UserActivityInterval still gets updated.
        self.assertEqual(UserActivityInterval.objects.filter(user_profile=othello).count(), 1)

        result = self.api_post(
            hamlet,
            "/api/v1/users/me/presence",
            dict(status="active", slim_presence="true"),
            HTTP_USER_AGENT="ZulipDesktop/1.0",
        )
        json = self.assert_json_success(result)
        self.assertEqual(set(json["presences"].keys()), {str(hamlet.id)})


class FormatLegacyPresenceDictTest(ZulipTestCase):
    def test_format_legacy_presence_dict(self) -> None:
        hamlet = self.example_user("hamlet")
        now = timezone_now()
        recently = now - timedelta(seconds=50)
        a_while_ago = now - timedelta(minutes=3)
        presence = UserPresence(
            user_profile=hamlet, realm=hamlet.realm, last_active_time=now, last_connected_time=now
        )
        assert presence.last_active_time is not None and presence.last_connected_time is not None
        self.assertEqual(
            format_legacy_presence_dict(presence.last_active_time, presence.last_connected_time),
            dict(
                client="website",
                status=UserPresence.LEGACY_STATUS_ACTIVE,
                timestamp=datetime_to_timestamp(now),
                pushable=False,
            ),
        )

        presence = UserPresence(
            user_profile=hamlet,
            realm=hamlet.realm,
            last_active_time=recently,
            last_connected_time=now,
        )
        assert presence.last_active_time is not None and presence.last_connected_time is not None
        self.assertEqual(
            format_legacy_presence_dict(presence.last_active_time, presence.last_connected_time),
            dict(
                client="website",
                status=UserPresence.LEGACY_STATUS_ACTIVE,
                timestamp=datetime_to_timestamp(recently),
                pushable=False,
            ),
        )

        presence = UserPresence(
            user_profile=hamlet,
            realm=hamlet.realm,
            last_active_time=a_while_ago,
            last_connected_time=now,
        )
        assert presence.last_active_time is not None and presence.last_connected_time is not None
        self.assertEqual(
            format_legacy_presence_dict(presence.last_active_time, presence.last_connected_time),
            dict(
                client="website",
                status=UserPresence.LEGACY_STATUS_IDLE,
                timestamp=datetime_to_timestamp(now),
                pushable=False,
            ),
        )
