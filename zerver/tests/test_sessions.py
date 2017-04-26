from __future__ import absolute_import
from typing import Any, Callable

from zerver.lib.sessions import (
    user_sessions,
    delete_session,
    delete_user_sessions,
    delete_realm_user_sessions,
    delete_all_user_sessions,
    delete_all_deactivated_user_sessions,
)

from zerver.models import (
    UserProfile, get_user_profile_by_id,
    get_user_profile_by_email, get_realm
)

from zerver.lib.test_classes import ZulipTestCase


class TestSessions(ZulipTestCase):

    def do_test_session(self, user, action, expected_result):
        # type: (str, Callable[[], Any], bool) -> None
        self.login(user)
        self.assertIn('_auth_user_id', self.client.session)
        action()
        if expected_result:
            result = self.client_get('/')
            self.assertEqual('/login', result.url)
        else:
            self.assertIn('_auth_user_id', self.client.session)

    def test_delete_session(self):
        # type: () -> None
        self.login('hamlet@zulip.com')
        self.assertIn('_auth_user_id', self.client.session)
        user_profile = get_user_profile_by_email('hamlet@zulip.com')
        for session in user_sessions(user_profile):
            delete_session(session)
        result = self.client_get("/")
        self.assertEqual('/login', result.url)

    def test_delete_user_sessions(self):
        # type: () -> None
        user_profile = get_user_profile_by_email('hamlet@zulip.com')
        self.do_test_session('hamlet@zulip.com', lambda: delete_user_sessions(user_profile), True)
        self.do_test_session('othello@zulip.com', lambda: delete_user_sessions(user_profile), False)

    def test_delete_realm_user_sessions(self):
        # type: () -> None
        realm = get_realm('zulip')
        self.do_test_session('hamlet@zulip.com', lambda: delete_realm_user_sessions(realm), True)
        self.do_test_session('sipbtest@mit.edu', lambda: delete_realm_user_sessions(realm), False)

    def test_delete_all_user_sessions(self):
        # type: () -> None
        self.do_test_session('hamlet@zulip.com', lambda: delete_all_user_sessions(), True)
        self.do_test_session('sipbtest@mit.edu', lambda: delete_all_user_sessions(), True)

    def test_delete_all_deactivated_user_sessions(self):
        # type: () -> None
        self.login('hamlet@zulip.com')
        self.assertIn('_auth_user_id', self.client.session)
        user_profile_1 = get_user_profile_by_email('hamlet@zulip.com')
        user_profile_1.is_active = False
        self.client_post('/accounts/logout/')
        delete_all_deactivated_user_sessions()
        result = self.client_get("/")
        self.assertEqual('/login', result.url)

        self.login('othello@zulip.com')
        self.assertIn('_auth_user_id', self.client.session)
        user_profile_2 = get_user_profile_by_email('othello@zulip.com')
        user_profile_2.is_active = True
        delete_all_deactivated_user_sessions()
        self.assertIn('_auth_user_id', self.client.session)
