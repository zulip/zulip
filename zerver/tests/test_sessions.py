from collections.abc import Callable
from datetime import timedelta
from typing import Any

import time_machine
from django.utils.timezone import now as timezone_now
from typing_extensions import override

from zerver.actions.realm_settings import do_set_realm_property
from zerver.actions.users import change_user_is_active
from zerver.lib.sessions import (
    delete_all_deactivated_user_sessions,
    delete_all_user_sessions,
    delete_realm_sessions,
    delete_session,
    delete_user_sessions,
    get_expirable_session_var,
    set_expirable_session_var,
)
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import Realm, RealmSession, UserProfile
from zerver.models.realms import get_realm
from zerver.models.sessions import SessionStore


class TestSessions(ZulipTestCase):
    def do_test_session(
        self, user: UserProfile, action: Callable[[], Any], realm: Realm, expected_result: bool
    ) -> None:
        self.login_user_hits_home(user)
        self.assertIn("_auth_user_id", self.client.session)
        action()
        if expected_result:
            result = self.client_get("/", subdomain=realm.subdomain)
            self.assertEqual(200, result.status_code)
            self.assertTrue('is_spectator":true' in str(result.content))
        else:
            self.assertIn("_auth_user_id", self.client.session)

    def test_sessionstore_create_model_instance(self) -> None:
        sesssion_store = SessionStore()
        session_data: dict[str, int | str] = {
            "ip_address": "127.0.0.1",
            "realm_id": 2,
            "_auth_user_id": "1",
        }

        realm_session = sesssion_store.create_model_instance(data=session_data)

        self.assertIsInstance(realm_session, RealmSession)
        self.assertEqual(realm_session.user_id, int(session_data["_auth_user_id"]))
        self.assertEqual(realm_session.realm_id, session_data["realm_id"])
        self.assertEqual(realm_session.ip_address, session_data["ip_address"])

    def test_user_session_ip_address(self) -> None:
        user_profile = self.example_user("hamlet")
        self.login_user_hits_home(user_profile)
        self.assertIn("_auth_user_id", self.client.session)

        # check if only one session is created, this shouldn't have any filters.
        self.assertEqual(RealmSession.objects.count(), 1)

        # check if that session has the correct user and ip_address.
        session = RealmSession.objects.get(user=user_profile, ip_address="127.0.0.1")

        # make a request with different IP
        self.client_get("/", REMOTE_ADDR="127.0.0.2")

        # check if ip_address is updated in that same session.
        self.assertEqual(
            RealmSession.objects.get(session_key=session.session_key).ip_address, "127.0.0.2"
        )

    def test_user_session_with_realm(self) -> None:
        user_profile = self.example_user("hamlet")
        self.login_user_hits_home(user_profile)
        self.assertIn("_auth_user_id", self.client.session)

        # check if only one session is created, this shouldn't have any filters.
        self.assertEqual(RealmSession.objects.count(), 1)

        # check if that session has the correct user and realm.
        self.assertEqual(
            RealmSession.objects.filter(realm=get_realm("zulip"), user=user_profile).count(), 1
        )

        # logout the user
        self.client_post("/accounts/logout/")
        result = self.client_get("/")
        self.assertEqual(result.status_code, 200)
        self.assertTrue('is_spectator":true' in str(result.content))

        # check if the session is deleted.
        self.assertEqual(RealmSession.objects.count(), 0)

    def test_delete_session(self) -> None:
        user_profile = self.example_user("hamlet")
        self.login_user_hits_home(user_profile)
        self.assertIn("_auth_user_id", self.client.session)
        for session in RealmSession.objects.filter(user=user_profile):
            delete_session(session)
        result = self.client_get("/")
        self.assertEqual(result.status_code, 200)
        self.assertTrue('is_spectator":true' in str(result.content))

    def test_delete_user_sessions(self) -> None:
        user_profile = self.example_user("hamlet")
        self.do_test_session(
            user_profile, lambda: delete_user_sessions(user_profile), get_realm("zulip"), True
        )
        self.do_test_session(
            self.example_user("othello"),
            lambda: delete_user_sessions(user_profile),
            get_realm("zulip"),
            False,
        )

    def test_delete_realm_sessions(self) -> None:
        realm = get_realm("zulip")
        self.do_test_session(
            self.example_user("hamlet"),
            lambda: delete_realm_sessions(realm),
            get_realm("zulip"),
            True,
        )
        self.do_test_session(
            self.mit_user("sipbtest"),
            lambda: delete_realm_sessions(realm),
            get_realm("zephyr"),
            False,
        )

    def test_delete_all_user_sessions(self) -> None:
        self.do_test_session(
            self.example_user("hamlet"),
            delete_all_user_sessions,
            get_realm("zulip"),
            True,
        )

        lear_realm = get_realm("lear")
        do_set_realm_property(lear_realm, "enable_spectator_access", True, acting_user=None)
        self.make_stream(
            "web_public_stream",
            realm=lear_realm,
            is_web_public=True,
        )
        self.do_test_session(
            self.lear_user("cordelia"),
            delete_all_user_sessions,
            lear_realm,
            True,
        )

    def test_delete_all_deactivated_user_sessions(self) -> None:
        # Test that no exception is thrown with a logged-out session
        self.login("othello")
        self.assertIn("_auth_user_id", self.client.session)
        self.client_post("/accounts/logout/")
        delete_all_deactivated_user_sessions()
        result = self.client_get("/")
        self.assertEqual(result.status_code, 200)
        self.assertTrue('is_spectator":true' in str(result.content))

        # Test nothing happens to an active user's session
        self.login("othello")
        self.assertIn("_auth_user_id", self.client.session)
        delete_all_deactivated_user_sessions()
        self.assertIn("_auth_user_id", self.client.session)

        # Test that a deactivated session gets logged out
        user_profile_3 = self.example_user("cordelia")
        self.login_user(user_profile_3)
        self.assertIn("_auth_user_id", self.client.session)
        change_user_is_active(user_profile_3, False)
        delete_all_deactivated_user_sessions()
        result = self.client_get("/")
        self.assertEqual(result.status_code, 200)
        self.assertTrue('is_spectator":true' in str(result.content))


class TestExpirableSessionVars(ZulipTestCase):
    @override
    def setUp(self) -> None:
        self.session = self.client.session
        super().setUp()

    def test_set_and_get_basic(self) -> None:
        start_time = timezone_now()
        with time_machine.travel(start_time, tick=False):
            set_expirable_session_var(
                self.session, "test_set_and_get_basic", "some_value", expiry_seconds=10
            )
            value = get_expirable_session_var(self.session, "test_set_and_get_basic")
            self.assertEqual(value, "some_value")
        with time_machine.travel((start_time + timedelta(seconds=11)), tick=False):
            value = get_expirable_session_var(self.session, "test_set_and_get_basic")
            self.assertEqual(value, None)

    def test_set_and_get_with_delete(self) -> None:
        set_expirable_session_var(
            self.session, "test_set_and_get_with_delete", "some_value", expiry_seconds=10
        )
        value = get_expirable_session_var(self.session, "test_set_and_get_with_delete", delete=True)
        self.assertEqual(value, "some_value")
        self.assertEqual(
            get_expirable_session_var(self.session, "test_set_and_get_with_delete"), None
        )

    def test_get_var_not_set(self) -> None:
        value = get_expirable_session_var(
            self.session, "test_get_var_not_set", default_value="default"
        )
        self.assertEqual(value, "default")

    def test_get_var_is_not_expirable(self) -> None:
        self.session["test_get_var_is_not_expirable"] = 0
        with self.assertLogs(level="WARNING") as m:
            value = get_expirable_session_var(
                self.session, "test_get_var_is_not_expirable", default_value="default"
            )
            self.assertEqual(value, "default")
            self.assertIn(
                "WARNING:root:get_expirable_session_var: error getting test_get_var_is_not_expirable",
                m.output[0],
            )
