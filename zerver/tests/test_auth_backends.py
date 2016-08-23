# -*- coding: utf-8 -*-
from django.conf import settings
from django.test import TestCase
from django_auth_ldap.backend import _LDAPUser
from django.test.client import RequestFactory
from typing import Any, Callable, Dict

import mock

from zerver.lib.actions import do_deactivate_realm, do_deactivate_user, \
    do_reactivate_realm, do_reactivate_user
from zerver.lib.initial_password import initial_password
from zerver.lib.test_helpers import (
    ZulipTestCase
)
from zerver.models import \
    get_realm, get_user_profile_by_email, email_to_username, UserProfile

from zproject.backends import ZulipDummyBackend, EmailAuthBackend, \
    GoogleMobileOauth2Backend, ZulipRemoteUserBackend, ZulipLDAPAuthBackend, \
    ZulipLDAPUserPopulator, DevAuthBackend, GitHubAuthBackend

from social.strategies.django_strategy import DjangoStrategy
from social.storage.django_orm import BaseDjangoStorage
from social.backends.github import GithubOrganizationOAuth2, GithubTeamOAuth2, \
    GithubOAuth2

from six import text_type
import ujson

class AuthBackendTest(TestCase):
    def verify_backend(self, backend, good_args=None,
                       good_kwargs=None, bad_kwargs=None,
                       email_to_username=None):
        # type: (Any, List[Any], Dict[str, Any], Dict[str, Any], Callable[[text_type], text_type]) -> None
        if good_args is None:
            good_args = []
        if good_kwargs is None:
            good_kwargs = {}
        email = u"hamlet@zulip.com"
        user_profile = get_user_profile_by_email(email)

        username = email
        if email_to_username is not None:
            username = email_to_username(email)

        # If bad_kwargs was specified, verify auth fails in that case
        if bad_kwargs is not None:
            self.assertIsNone(backend.authenticate(username, **bad_kwargs))

        # Verify auth works
        result = backend.authenticate(username, *good_args, **good_kwargs)
        self.assertEqual(user_profile, result)

        # Verify auth fails with a deactivated user
        do_deactivate_user(user_profile)
        self.assertIsNone(backend.authenticate(username, *good_args, **good_kwargs))

        # Reactivate the user and verify auth works again
        do_reactivate_user(user_profile)
        result = backend.authenticate(username, *good_args, **good_kwargs)
        self.assertEqual(user_profile, result)

        # Verify auth fails with a deactivated realm
        do_deactivate_realm(user_profile.realm)
        self.assertIsNone(backend.authenticate(username, *good_args, **good_kwargs))

        # Verify auth works again after reactivating the realm
        do_reactivate_realm(user_profile.realm)
        result = backend.authenticate(username, *good_args, **good_kwargs)
        self.assertEqual(user_profile, result)

    def test_dummy_backend(self):
        # type: () -> None
        self.verify_backend(ZulipDummyBackend(),
                            good_kwargs=dict(use_dummy_backend=True),
                            bad_kwargs=dict(use_dummy_backend=False))

    def test_email_auth_backend(self):
        # type: () -> None
        email = "hamlet@zulip.com"
        user_profile = get_user_profile_by_email(email)
        password = "testpassword"
        user_profile.set_password(password)
        user_profile.save()
        self.verify_backend(EmailAuthBackend(),
                            bad_kwargs=dict(password=''),
                            good_kwargs=dict(password=password))

    def test_email_auth_backend_disabled_password_auth(self):
        # type: () -> None
        email = u"hamlet@zulip.com"
        user_profile = get_user_profile_by_email(email)
        password = "testpassword"
        user_profile.set_password(password)
        user_profile.save()
        # Verify if a realm has password auth disabled, correct password is rejected
        with mock.patch('zproject.backends.password_auth_enabled', return_value=False):
            self.assertIsNone(EmailAuthBackend().authenticate(email, password))

    def test_google_backend(self):
        # type: () -> None
        email = "hamlet@zulip.com"
        backend = GoogleMobileOauth2Backend()
        payload = dict(email_verified=True,
                       email=email)
        with mock.patch('apiclient.sample_tools.client.verify_id_token', return_value=payload):
            self.verify_backend(backend)

        # Verify valid_attestation parameter is set correctly
        unverified_payload = dict(email_verified=False)
        with mock.patch('apiclient.sample_tools.client.verify_id_token', return_value=unverified_payload):
            ret = dict() # type: Dict[str, str]
            result = backend.authenticate(return_data=ret)
            self.assertIsNone(result)
            self.assertFalse(ret["valid_attestation"])

        nonexistent_user_payload = dict(email_verified=True, email="invalid@zulip.com")
        with mock.patch('apiclient.sample_tools.client.verify_id_token',
                        return_value=nonexistent_user_payload):
            ret = dict()
            result = backend.authenticate(return_data=ret)
            self.assertIsNone(result)
            self.assertTrue(ret["valid_attestation"])

    def test_ldap_backend(self):
        # type: () -> None
        email = "hamlet@zulip.com"
        password = "test_password"
        backend = ZulipLDAPAuthBackend()

        # Test LDAP auth fails when LDAP server rejects password
        with mock.patch('django_auth_ldap.backend._LDAPUser._authenticate_user_dn', \
                        side_effect=_LDAPUser.AuthenticationFailed("Failed")), \
             mock.patch('django_auth_ldap.backend._LDAPUser._check_requirements'), \
             mock.patch('django_auth_ldap.backend._LDAPUser._get_user_attrs',
                        return_value=dict(full_name=['Hamlet'])):
            self.assertIsNone(backend.authenticate(email, password))

        # For this backend, we mock the internals of django_auth_ldap
        with mock.patch('django_auth_ldap.backend._LDAPUser._authenticate_user_dn'), \
             mock.patch('django_auth_ldap.backend._LDAPUser._check_requirements'), \
             mock.patch('django_auth_ldap.backend._LDAPUser._get_user_attrs',
                        return_value=dict(full_name=['Hamlet'])):
            self.verify_backend(backend, good_kwargs=dict(password=password))

    def test_devauth_backend(self):
        # type: () -> None
        self.verify_backend(DevAuthBackend())

    def test_remote_user_backend(self):
        # type: () -> None
        self.verify_backend(ZulipRemoteUserBackend())

    def test_remote_user_backend_sso_append_domain(self):
        # type: () -> None
        with self.settings(SSO_APPEND_DOMAIN='zulip.com'):
            self.verify_backend(ZulipRemoteUserBackend(),
                                email_to_username=email_to_username)

    def test_github_backend(self):
        # type: () -> None
        email = 'hamlet@zulip.com'
        good_kwargs = dict(response=dict(email=email), return_data=dict())
        bad_kwargs = dict()  # type: Dict[str, str]
        self.verify_backend(GitHubAuthBackend(),
                            good_kwargs=good_kwargs,
                            bad_kwargs=bad_kwargs)

class GitHubAuthBackendTest(ZulipTestCase):
    def setUp(self):
        # type: () -> None
        self.email = 'hamlet@zulip.com'
        self.name = 'Hamlet'
        self.backend = GitHubAuthBackend()
        self.backend.strategy = DjangoStrategy(storage=BaseDjangoStorage())
        self.user_profile = get_user_profile_by_email(self.email)
        self.user_profile.backend = self.backend

    def test_github_backend_do_auth(self):
        # type: () -> None
        def do_auth(*args, **kwargs):
            # type: (*Any, **Any) -> UserProfile
            return self.user_profile

        with mock.patch('zerver.views.login_or_register_remote_user') as result, \
                 mock.patch('social.backends.github.GithubOAuth2.do_auth',
                            side_effect=do_auth):
            response=dict(email=self.email, name=self.name)
            self.backend.do_auth(response=response)
            result.assert_called_with(None, self.email, self.user_profile,
                                      self.name)

    def test_github_backend_do_auth_for_default(self):
        # type: () -> None
        def authenticate(*args, **kwargs):
            # type: (*Any, **Any) -> None
            assert isinstance(kwargs['backend'], GithubOAuth2) == True

        with mock.patch('social.backends.github.GithubOAuth2.user_data',
                         return_value=dict()), \
                mock.patch('zproject.backends.SocialAuthMixin.process_do_auth'), \
                mock.patch('social.strategies.django_strategy.'
                           'DjangoStrategy.authenticate', side_effect=authenticate):
            response=dict(email=self.email, name=self.name)
            self.backend.do_auth('fake-access-token', response=response)

    def test_github_backend_do_auth_for_team(self):
        # type: () -> None
        def authenticate(*args, **kwargs):
            # type: (*Any, **Any) -> None
            assert isinstance(kwargs['backend'], GithubTeamOAuth2) == True

        with mock.patch('social.backends.github.GithubTeamOAuth2.user_data',
                         return_value=dict()), \
                mock.patch('zproject.backends.SocialAuthMixin.process_do_auth'), \
                mock.patch('social.strategies.django_strategy.'
                           'DjangoStrategy.authenticate', side_effect=authenticate):
            response=dict(email=self.email, name=self.name)
            with self.settings(SOCIAL_AUTH_GITHUB_TEAM_ID='zulip-webapp'):
                self.backend.do_auth('fake-access-token', response=response)

    def test_github_backend_do_auth_for_org(self):
        # type: () -> None
        def authenticate(*args, **kwargs):
            # type: (*Any, **Any) -> None
            assert isinstance(kwargs['backend'], GithubOrganizationOAuth2) == True

        with mock.patch('social.backends.github.GithubOrganizationOAuth2.user_data',
                         return_value=dict()), \
                mock.patch('zproject.backends.SocialAuthMixin.process_do_auth'), \
                mock.patch('social.strategies.django_strategy.'
                           'DjangoStrategy.authenticate', side_effect=authenticate):
            response=dict(email=self.email, name=self.name)
            with self.settings(SOCIAL_AUTH_GITHUB_ORG_NAME='Zulip'):
                self.backend.do_auth('fake-access-token', response=response)

    def test_github_backend_inactive_user(self):
        # type: () -> None
        def do_auth_inactive(*args, **kwargs):
            # type: (*Any, **Any) -> UserProfile
            return_data = kwargs['return_data']
            return_data['inactive_user'] = True
            return self.user_profile

        with mock.patch('zerver.views.login_or_register_remote_user') as result, \
                mock.patch('social.backends.github.GithubOAuth2.do_auth',
                           side_effect=do_auth_inactive):
            response=dict(email=self.email, name=self.name)
            user = self.backend.do_auth(response=response)
            result.assert_not_called()
            self.assertIs(user, None)

    def test_github_backend_new_user(self):
        # type: () -> None
        rf = RequestFactory()
        request = rf.get('/complete')
        request.session = {}
        request.user = self.user_profile
        self.backend.strategy.request = request

        def do_auth(*args, **kwargs):
            # type: (*Any, **Any) -> UserProfile
            return_data = kwargs['return_data']
            return_data['valid_attestation'] = True
            return None

        with mock.patch('social.backends.github.GithubOAuth2.do_auth',
                        side_effect=do_auth):
            response=dict(email='nonexisting@phantom.com', name='Ghost')
            result = self.backend.do_auth(response=response)
            self.assert_in_response('action="/register/"', result)
            self.assert_in_response('Your e-mail does not match any '
                                    'existing open organization.', result)

class FetchAPIKeyTest(ZulipTestCase):
    def setUp(self):
        # type: () -> None
        self.email = "hamlet@zulip.com"
        self.user_profile = get_user_profile_by_email(self.email)

    def test_success(self):
        # type: () -> None
        result = self.client_post("/api/v1/fetch_api_key",
                                  dict(username=self.email,
                                       password=initial_password(self.email)))
        self.assert_json_success(result)

    def test_wrong_password(self):
        # type: () -> None
        result = self.client_post("/api/v1/fetch_api_key",
                                  dict(username=self.email,
                                       password="wrong"))
        self.assert_json_error(result, "Your username or password is incorrect.", 403)

    def test_password_auth_disabled(self):
        # type: () -> None
        with mock.patch('zproject.backends.password_auth_enabled', return_value=False):
            result = self.client_post("/api/v1/fetch_api_key",
                                      dict(username=self.email,
                                           password=initial_password(self.email)))
            self.assert_json_error_contains(result, "Password auth is disabled", 403)

    def test_inactive_user(self):
        # type: () -> None
        do_deactivate_user(self.user_profile)
        result = self.client_post("/api/v1/fetch_api_key",
                                  dict(username=self.email,
                                       password=initial_password(self.email)))
        self.assert_json_error_contains(result, "Your account has been disabled", 403)

    def test_deactivated_realm(self):
        # type: () -> None
        do_deactivate_realm(self.user_profile.realm)
        result = self.client_post("/api/v1/fetch_api_key",
                                  dict(username=self.email,
                                       password=initial_password(self.email)))
        self.assert_json_error_contains(result, "Your realm has been deactivated", 403)

class DevFetchAPIKeyTest(ZulipTestCase):
    def setUp(self):
        # type: () -> None
        self.email = "hamlet@zulip.com"
        self.user_profile = get_user_profile_by_email(self.email)

    def test_success(self):
        # type: () -> None
        result = self.client_post("/api/v1/dev_fetch_api_key",
                                  dict(username=self.email))
        self.assert_json_success(result)
        data = ujson.loads(result.content)
        self.assertEqual(data["email"], self.email)
        self.assertEqual(data['api_key'], self.user_profile.api_key)

    def test_inactive_user(self):
        # type: () -> None
        do_deactivate_user(self.user_profile)
        result = self.client_post("/api/v1/dev_fetch_api_key",
                                  dict(username=self.email))
        self.assert_json_error_contains(result, "Your account has been disabled", 403)

    def test_deactivated_realm(self):
        # type: () -> None
        do_deactivate_realm(self.user_profile.realm)
        result = self.client_post("/api/v1/dev_fetch_api_key",
                                  dict(username=self.email))
        self.assert_json_error_contains(result, "Your realm has been deactivated", 403)

    def test_dev_auth_disabled(self):
        # type: () -> None
        with mock.patch('zerver.views.dev_auth_enabled', return_value=False):
            result = self.client_post("/api/v1/dev_fetch_api_key",
                                      dict(username=self.email))
            self.assert_json_error_contains(result, "Dev environment not enabled.", 400)

class DevGetEmailsTest(ZulipTestCase):
    def test_success(self):
        # type: () -> None
        result = self.client_get("/api/v1/dev_get_emails")
        self.assert_json_success(result)
        self.assert_in_response("direct_admins", result)
        self.assert_in_response("direct_users", result)

    def test_dev_auth_disabled(self):
        # type: () -> None
        with mock.patch('zerver.views.dev_auth_enabled', return_value=False):
            result = self.client_get("/api/v1/dev_get_emails")
            self.assert_json_error_contains(result, "Dev environment not enabled.", 400)

class FetchAuthBackends(ZulipTestCase):
    def test_fetch_auth_backend_format(self):
        # type: () -> None
        result = self.client_get("/api/v1/get_auth_backends")
        self.assert_json_success(result)
        data = ujson.loads(result.content)
        self.assertEqual(set(data.keys()),
                         {'msg', 'password', 'google', 'dev', 'result'})
        for backend in set(data.keys()) - {'msg', 'result'}:
            self.assertTrue(isinstance(data[backend], bool))

    def test_fetch_auth_backend(self):
        # type: () -> None
        backends = [GoogleMobileOauth2Backend(), DevAuthBackend()]
        with mock.patch('django.contrib.auth.get_backends', return_value=backends):
            result = self.client_get("/api/v1/get_auth_backends")
            self.assert_json_success(result)
            data = ujson.loads(result.content)
            self.assertEqual(data, {
                'msg': '',
                'password': False,
                'google': True,
                'dev': True,
                'result': 'success',
            })
