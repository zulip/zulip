from datetime import timedelta
from typing import Any, Callable
from unittest import mock

from django.utils.timezone import now as timezone_now

from zerver.lib.sessions import (
    delete_all_deactivated_user_sessions,
    delete_all_user_sessions,
    delete_realm_user_sessions,
    delete_session,
    delete_user_sessions,
    get_expirable_session_var,
    set_expirable_session_var,
    user_sessions,
)
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import Realm, UserProfile, get_realm


class TestSessions(ZulipTestCase):

    def do_test_session(self, user: UserProfile,
                        action: Callable[[], Any],
                        realm: Realm,
                        expected_result: bool) -> None:
        self.login_user(user)
        self.assertIn('_auth_user_id', self.client.session)
        action()
        if expected_result:
            result = self.client_get('/', subdomain=realm.subdomain)
            self.check_rendered_web_public_visitor(result)
        else:
            self.assertIn('_auth_user_id', self.client.session)

    def test_delete_session(self) -> None:
        user_profile = self.example_user('hamlet')
        self.login_user(user_profile)
        self.assertIn('_auth_user_id', self.client.session)
        for session in user_sessions(user_profile):
            delete_session(session)
        result = self.client_get("/")
        self.check_rendered_web_public_visitor(result)

    def test_delete_user_sessions(self) -> None:
        user_profile = self.example_user('hamlet')
        self.do_test_session(user_profile, lambda: delete_user_sessions(user_profile),
                             get_realm("zulip"), True)
        self.do_test_session(self.example_user("othello"),
                             lambda: delete_user_sessions(user_profile),
                             get_realm("zulip"), False)

    def test_delete_realm_user_sessions(self) -> None:
        realm = get_realm('zulip')
        self.do_test_session(self.example_user("hamlet"),
                             lambda: delete_realm_user_sessions(realm),
                             get_realm("zulip"), True)
        self.do_test_session(self.mit_user("sipbtest"),
                             lambda: delete_realm_user_sessions(realm),
                             get_realm("zephyr"), False)

    def test_delete_all_user_sessions(self) -> None:
        self.do_test_session(self.example_user("hamlet"),
                             lambda: delete_all_user_sessions(),
                             get_realm("zulip"), True)
        self.do_test_session(self.mit_user("sipbtest"),
                             lambda: delete_all_user_sessions(),
                             get_realm("zephyr"), True)

    def test_delete_all_deactivated_user_sessions(self) -> None:

        # Test that no exception is thrown with a logged-out session
        self.login('othello')
        self.assertIn('_auth_user_id', self.client.session)
        self.client_post('/accounts/logout/')
        delete_all_deactivated_user_sessions()
        result = self.client_get("/")
        self.check_rendered_web_public_visitor(result)

        # Test nothing happens to an active user's session
        self.login('othello')
        self.assertIn('_auth_user_id', self.client.session)
        delete_all_deactivated_user_sessions()
        self.assertIn('_auth_user_id', self.client.session)

        # Test that a deactivated session gets logged out
        user_profile_3 = self.example_user('cordelia')
        self.login_user(user_profile_3)
        self.assertIn('_auth_user_id', self.client.session)
        user_profile_3.is_active = False
        user_profile_3.save()
        with self.assertLogs(level='INFO') as info_logs:
            delete_all_deactivated_user_sessions()
        self.assertEqual(info_logs.output, [
            'INFO:root:Deactivating session for deactivated user 8'
        ])
        result = self.client_get("/")
        self.check_rendered_web_public_visitor(result)

class TestExpirableSessionVars(ZulipTestCase):
    def setUp(self) -> None:
        self.session = self.client.session
        super().setUp()

    def test_set_and_get_basic(self) -> None:
        start_time = timezone_now()
        with mock.patch('zerver.lib.sessions.timezone_now', return_value=start_time):
            set_expirable_session_var(self.session, 'test_set_and_get_basic', 'some_value', expiry_seconds=10)
            value = get_expirable_session_var(self.session, 'test_set_and_get_basic')
            self.assertEqual(value, 'some_value')
        with mock.patch('zerver.lib.sessions.timezone_now', return_value=start_time + timedelta(seconds=11)):
            value = get_expirable_session_var(self.session, 'test_set_and_get_basic')
            self.assertEqual(value, None)

    def test_set_and_get_with_delete(self) -> None:
        set_expirable_session_var(self.session, 'test_set_and_get_with_delete', 'some_value', expiry_seconds=10)
        value = get_expirable_session_var(self.session, 'test_set_and_get_with_delete', delete=True)
        self.assertEqual(value, 'some_value')
        self.assertEqual(get_expirable_session_var(self.session, 'test_set_and_get_with_delete'), None)

    def test_get_var_not_set(self) -> None:
        value = get_expirable_session_var(self.session, 'test_get_var_not_set', default_value='default')
        self.assertEqual(value, 'default')

    def test_get_var_is_not_expirable(self) -> None:
        self.session["test_get_var_is_not_expirable"] = 0
        with self.assertLogs(level='WARNING') as m:
            value = get_expirable_session_var(self.session, 'test_get_var_is_not_expirable', default_value='default')
            self.assertEqual(value, 'default')
            self.assertIn('WARNING:root:get_expirable_session_var: error getting test_get_var_is_not_expirable', m.output[0])
