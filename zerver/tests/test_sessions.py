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
    get_realm, Realm
)

from zerver.lib.test_classes import ZulipTestCase


class TestSessions(ZulipTestCase):

    def do_test_session(self, user: str,
                        action: Callable[[], Any],
                        realm: Realm,
                        expected_result: bool) -> None:
        self.login(user, realm=realm)
        self.assertIn('_auth_user_id', self.client.session)
        action()
        if expected_result:
            result = self.client_get('/', subdomain=realm.subdomain)
            self.assertEqual('/login/', result.url)
        else:
            self.assertIn('_auth_user_id', self.client.session)

    def test_delete_session(self) -> None:
        user_profile = self.example_user('hamlet')
        email = user_profile.email
        self.login(email)
        self.assertIn('_auth_user_id', self.client.session)
        for session in user_sessions(user_profile):
            delete_session(session)
        result = self.client_get("/")
        self.assertEqual('/login/', result.url)

    def test_delete_user_sessions(self) -> None:
        user_profile = self.example_user('hamlet')
        email = user_profile.email
        self.do_test_session(str(email), lambda: delete_user_sessions(user_profile),
                             get_realm("zulip"), True)
        self.do_test_session(str(self.example_email("othello")),
                             lambda: delete_user_sessions(user_profile),
                             get_realm("zulip"), False)

    def test_delete_realm_user_sessions(self) -> None:
        realm = get_realm('zulip')
        self.do_test_session(self.example_email("hamlet"),
                             lambda: delete_realm_user_sessions(realm),
                             get_realm("zulip"), True)
        self.do_test_session(self.mit_email("sipbtest"),
                             lambda: delete_realm_user_sessions(realm),
                             get_realm("zephyr"), False)

    def test_delete_all_user_sessions(self) -> None:
        self.do_test_session(self.example_email("hamlet"),
                             lambda: delete_all_user_sessions(),
                             get_realm("zulip"), True)
        self.do_test_session(self.mit_email("sipbtest"),
                             lambda: delete_all_user_sessions(),
                             get_realm("zephyr"), True)

    def test_delete_all_deactivated_user_sessions(self) -> None:

        # Test that no exception is thrown with a logged-out session
        self.login(self.example_email("othello"))
        self.assertIn('_auth_user_id', self.client.session)
        self.client_post('/accounts/logout/')
        delete_all_deactivated_user_sessions()
        result = self.client_get("/")
        self.assertEqual('/login/', result.url)

        # Test nothing happens to an active user's session
        self.login(self.example_email("othello"))
        self.assertIn('_auth_user_id', self.client.session)
        delete_all_deactivated_user_sessions()
        self.assertIn('_auth_user_id', self.client.session)

        # Test that a deactivated session gets logged out
        user_profile_3 = self.example_user('cordelia')
        email_3 = user_profile_3.email
        self.login(email_3)
        self.assertIn('_auth_user_id', self.client.session)
        user_profile_3.is_active = False
        user_profile_3.save()
        delete_all_deactivated_user_sessions()
        result = self.client_get("/")
        self.assertEqual('/login/', result.url)
