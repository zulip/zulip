import datetime
from datetime import timedelta
from typing import Any, Dict
from unittest import mock

from django.utils.timezone import now as timezone_now

from zerver.actions.users import do_deactivate_user
from zerver.lib.presence import get_presence_dict_by_realm
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import make_client, reset_emails_in_zulip_realm
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.models import (
    PushDeviceToken,
    UserActivity,
    UserActivityInterval,
    UserPresence,
    UserProfile,
)


class TestClientModel(ZulipTestCase):
    def test_client_stringification(self) -> None:
        """
        This test is designed to cover __str__ method for Client.
        """
        client = make_client("some_client")
        self.assertEqual(str(client), "<Client: some_client>")


class UserPresenceModelTests(ZulipTestCase):
    def test_date_logic(self) -> None:
        UserPresence.objects.all().delete()

        user_profile = self.example_user("hamlet")
        email = user_profile.email
        presence_dct = get_presence_dict_by_realm(user_profile.realm_id)
        self.assert_length(presence_dct, 0)

        self.login_user(user_profile)
        result = self.client_post("/json/users/me/presence", {"status": "active"})
        self.assert_json_success(result)

        slim_presence = False
        presence_dct = get_presence_dict_by_realm(user_profile.realm_id, slim_presence)
        self.assert_length(presence_dct, 1)
        self.assertEqual(presence_dct[email]["website"]["status"], "active")

        slim_presence = True
        presence_dct = get_presence_dict_by_realm(user_profile.realm_id, slim_presence)
        self.assert_length(presence_dct, 1)
        info = presence_dct[str(user_profile.id)]
        self.assertEqual(set(info.keys()), {"active_timestamp"})

        def back_date(num_weeks: int) -> None:
            user_presence = UserPresence.objects.filter(user_profile=user_profile)[0]
            user_presence.timestamp = timezone_now() - datetime.timedelta(weeks=num_weeks)
            user_presence.save()

        # Simulate the presence being a week old first.  Nothing should change.
        back_date(num_weeks=1)
        presence_dct = get_presence_dict_by_realm(user_profile.realm_id)
        self.assert_length(presence_dct, 1)

        # If the UserPresence row is three weeks old, we ignore it.
        back_date(num_weeks=3)
        presence_dct = get_presence_dict_by_realm(user_profile.realm_id)
        self.assert_length(presence_dct, 0)

    def test_push_tokens(self) -> None:
        UserPresence.objects.all().delete()

        user_profile = self.example_user("hamlet")
        email = user_profile.email

        self.login_user(user_profile)
        result = self.client_post("/json/users/me/presence", {"status": "active"})
        self.assert_json_success(result)

        def pushable() -> bool:
            presence_dct = get_presence_dict_by_realm(user_profile.realm_id)
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
        self.assertTrue(pushable())


class UserPresenceTests(ZulipTestCase):
    def test_invalid_presence(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        result = self.client_post("/json/users/me/presence", {"status": "foo"})
        self.assert_json_error(result, "Invalid status: foo")

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

        self.assertEqual(set(hamlet_info.keys()), {"idle_timestamp"})
        self.assertEqual(set(othello_info.keys()), {"idle_timestamp"})

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
            {"active_timestamp"},
        )

        self.assertEqual(
            set(hamlet_info.keys()),
            {"active_timestamp"},
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
        with mock.patch("zerver.views.presence.timezone_now", return_value=time_zero):
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
        with mock.patch("zerver.views.presence.timezone_now", return_value=second_time):
            result = self.client_post(
                "/json/users/me/presence", {"status": "active", "new_user_input": "true"}
            )
        self.assert_json_success(result)
        self.assertEqual(UserActivityInterval.objects.filter(user_profile=user_profile).count(), 1)
        interval = UserActivityInterval.objects.get(user_profile=user_profile)
        self.assertEqual(interval.start, time_zero)
        self.assertEqual(interval.end, second_time + UserActivityInterval.MIN_INTERVAL_LENGTH)

        third_time = time_zero + timedelta(seconds=6000)
        with mock.patch("zerver.views.presence.timezone_now", return_value=third_time):
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

        self.assertEqual(filter_presence_idle_user_ids({user_profile.id}), [user_profile.id])
        self.client_post("/json/users/me/presence", {"status": "idle"})
        self.assertEqual(filter_presence_idle_user_ids({user_profile.id}), [user_profile.id])

        # Active presence from the mobile app doesn't count
        self.client_post(
            "/json/users/me/presence", {"status": "active"}, HTTP_USER_AGENT="ZulipMobile/1.0"
        )
        self.assertEqual(filter_presence_idle_user_ids({user_profile.id}), [user_profile.id])

        self.client_post("/json/users/me/presence", {"status": "active"})
        self.assertEqual(filter_presence_idle_user_ids({user_profile.id}), [])

    def test_no_mit(self) -> None:
        """Zephyr mirror realms such as MIT never get a list of users"""
        user = self.mit_user("espuser")
        self.login_user(user)
        result = self.client_post("/json/users/me/presence", {"status": "idle"}, subdomain="zephyr")
        response_dict = self.assert_json_success(result)
        self.assertEqual(response_dict["presences"], {})

    def test_mirror_presence(self) -> None:
        """Zephyr mirror realms find out the status of their mirror bot"""
        user_profile = self.mit_user("espuser")
        self.login_user(user_profile)

        def post_presence() -> Dict[str, Any]:
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
        reset_emails_in_zulip_realm()

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

        # Then, we check everything works
        self.login("hamlet")
        result = self.client_get("/json/users/othello@zulip.com/presence")
        result_dict = self.assert_json_success(result)
        self.assertEqual(
            set(result_dict["presence"].keys()), {"ZulipAndroid", "website", "aggregated"}
        )
        self.assertEqual(set(result_dict["presence"]["website"].keys()), {"status", "timestamp"})

        result = self.client_get(f"/json/users/{othello.id}/presence")
        result_dict = self.assert_json_success(result)
        self.assertEqual(
            set(result_dict["presence"].keys()), {"ZulipAndroid", "website", "aggregated"}
        )
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
        self, user: UserProfile, status: str, validate_time: datetime.datetime
    ) -> Dict[str, Dict[str, Any]]:
        self.login_user(user)
        timezone_util = "zerver.views.presence.timezone_now"
        with mock.patch(timezone_util, return_value=validate_time - datetime.timedelta(seconds=5)):
            self.client_post("/json/users/me/presence", {"status": status})
        with mock.patch(timezone_util, return_value=validate_time - datetime.timedelta(seconds=2)):
            self.api_post(
                user,
                "/api/v1/users/me/presence",
                {"status": status},
                HTTP_USER_AGENT="ZulipAndroid/1.0",
            )
        with mock.patch(timezone_util, return_value=validate_time - datetime.timedelta(seconds=7)):
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
                "timestamp": datetime_to_timestamp(validate_time - datetime.timedelta(seconds=2)),
                "client": "ZulipAndroid",
            },
        )

        result = self.client_get(f"/json/users/{user.email}/presence")
        return self.assert_json_success(result)

    def test_aggregated_info(self) -> None:
        user = self.example_user("othello")
        validate_time = timezone_now()
        self._send_presence_for_aggregated_tests(user, "active", validate_time)
        with mock.patch(
            "zerver.views.presence.timezone_now",
            return_value=validate_time - datetime.timedelta(seconds=1),
        ):
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
                "timestamp": datetime_to_timestamp(validate_time - datetime.timedelta(seconds=1)),
                "client": "ZulipTestDev",
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
                "timestamp": datetime_to_timestamp(validate_time - datetime.timedelta(seconds=2)),
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
                "timestamp": datetime_to_timestamp(validate_time - datetime.timedelta(seconds=2)),
            },
        )

    def test_aggregated_presence_mixed(self) -> None:
        user = self.example_user("othello")
        self.login_user(user)
        validate_time = timezone_now()
        with mock.patch(
            "zerver.views.presence.timezone_now",
            return_value=validate_time - datetime.timedelta(seconds=3),
        ):
            self.api_post(
                user,
                "/api/v1/users/me/presence",
                {"status": "active"},
                HTTP_USER_AGENT="ZulipTestDev/1.0",
            )
        result_dict = self._send_presence_for_aggregated_tests(user, "idle", validate_time)
        self.assertDictEqual(
            result_dict["presence"]["aggregated"],
            {
                "status": "idle",
                "timestamp": datetime_to_timestamp(validate_time - datetime.timedelta(seconds=2)),
            },
        )

    def test_aggregated_presence_offline(self) -> None:
        user = self.example_user("othello")
        self.login_user(user)
        validate_time = timezone_now()
        with self.settings(OFFLINE_THRESHOLD_SECS=1):
            result_dict = self._send_presence_for_aggregated_tests(user, "idle", validate_time)
        self.assertDictEqual(
            result_dict["presence"]["aggregated"],
            {
                "status": "offline",
                "timestamp": datetime_to_timestamp(validate_time - datetime.timedelta(seconds=2)),
            },
        )


class GetRealmStatusesTest(ZulipTestCase):
    def test_get_statuses(self) -> None:
        # Set up the test by simulating users reporting their presence data.
        othello = self.example_user("othello")
        hamlet = self.example_user("hamlet")

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

    def test_presence_disabled(self) -> None:
        # Disable presence status and test whether the presence
        # is reported or not.
        othello = self.example_user("othello")
        hamlet = self.example_user("hamlet")
        othello.presence_enabled = False
        hamlet.presence_enabled = True
        othello.save(update_fields=["presence_enabled"])
        hamlet.save(update_fields=["presence_enabled"])

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

        # Othello's presence status is disabled so it won't be reported.
        self.assertEqual(set(json["presences"].keys()), {hamlet.email})

        result = self.api_post(
            hamlet,
            "/api/v1/users/me/presence",
            dict(status="active", slim_presence="true"),
            HTTP_USER_AGENT="ZulipDesktop/1.0",
        )
        json = self.assert_json_success(result)
        self.assertEqual(set(json["presences"].keys()), {str(hamlet.id)})
