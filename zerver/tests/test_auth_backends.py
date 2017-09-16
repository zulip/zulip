# -*- coding: utf-8 -*-
from django.conf import settings
from django.core import mail
from django.http import HttpResponse
from django.test import override_settings
from django_auth_ldap.backend import _LDAPUser
from django.contrib.auth import authenticate
from django.test.client import RequestFactory
from typing import Any, Callable, Dict, List, Optional, Text
from builtins import object
from oauth2client.crypt import AppIdentityError
from django.core import signing
from django.core.urlresolvers import reverse

import jwt
import mock
import re

from zerver.forms import HomepageForm
from zerver.lib.actions import (
    do_deactivate_realm,
    do_deactivate_user,
    do_reactivate_realm,
    do_reactivate_user,
    do_set_realm_authentication_methods,
)
from zerver.lib.mobile_auth_otp import otp_decrypt_api_key
from zerver.lib.validator import validate_login_email, \
    check_bool, check_dict_only, check_string
from zerver.lib.request import JsonableError
from zerver.lib.initial_password import initial_password
from zerver.lib.sessions import get_session_dict_user
from zerver.lib.test_classes import (
    ZulipTestCase,
)
from zerver.lib.test_helpers import POSTRequestMock
from zerver.models import \
    get_realm, email_to_username, UserProfile, \
    PreregistrationUser, Realm, get_user

from confirmation.models import Confirmation, confirmation_url

from zproject.backends import ZulipDummyBackend, EmailAuthBackend, \
    GoogleMobileOauth2Backend, ZulipRemoteUserBackend, ZulipLDAPAuthBackend, \
    ZulipLDAPUserPopulator, DevAuthBackend, GitHubAuthBackend, ZulipAuthMixin, \
    dev_auth_enabled, password_auth_enabled, github_auth_enabled, \
    require_email_format_usernames, SocialAuthMixin, AUTH_BACKEND_NAME_MAP

from zerver.views.auth import (maybe_send_to_registration,
                               login_or_register_remote_user)
from version import ZULIP_VERSION

from social_core.exceptions import AuthFailed, AuthStateForbidden
from social_django.strategy import DjangoStrategy
from social_django.storage import BaseDjangoStorage
from social_core.backends.github import GithubOrganizationOAuth2, GithubTeamOAuth2, \
    GithubOAuth2

from six.moves import urllib
from six.moves.http_cookies import SimpleCookie
import ujson
from zerver.lib.test_helpers import MockLDAP, unsign_subdomain_cookie

class AuthBackendTest(ZulipTestCase):
    def get_username(self, email_to_username=None):
        # type: (Optional[Callable[[Text], Text]]) -> Text
        username = self.example_email('hamlet')
        if email_to_username is not None:
            username = email_to_username(self.example_email('hamlet'))

        return username

    def verify_backend(self, backend, good_kwargs=None, bad_kwargs=None):
        # type: (Any, Optional[Dict[str, Any]], Optional[Dict[str, Any]]) -> None

        user_profile = self.example_user('hamlet')

        if good_kwargs is None:
            good_kwargs = {}

        # If bad_kwargs was specified, verify auth fails in that case
        if bad_kwargs is not None:
            self.assertIsNone(backend.authenticate(**bad_kwargs))

        # Verify auth works
        result = backend.authenticate(**good_kwargs)
        self.assertEqual(user_profile, result)

        # Verify auth fails with a deactivated user
        do_deactivate_user(user_profile)
        self.assertIsNone(backend.authenticate(**good_kwargs))

        # Reactivate the user and verify auth works again
        do_reactivate_user(user_profile)
        result = backend.authenticate(**good_kwargs)
        self.assertEqual(user_profile, result)

        # Verify auth fails with a deactivated realm
        do_deactivate_realm(user_profile.realm)
        self.assertIsNone(backend.authenticate(**good_kwargs))

        # Verify auth works again after reactivating the realm
        do_reactivate_realm(user_profile.realm)
        result = backend.authenticate(**good_kwargs)
        self.assertEqual(user_profile, result)

        # ZulipDummyBackend isn't a real backend so the remainder
        # doesn't make sense for it
        if isinstance(backend, ZulipDummyBackend):
            return

        # Verify auth fails if the auth backend is disabled on server
        with self.settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipDummyBackend',)):
            self.assertIsNone(backend.authenticate(**good_kwargs))

        # Verify auth fails if the auth backend is disabled for the realm
        for backend_name in AUTH_BACKEND_NAME_MAP.keys():
            if isinstance(backend, AUTH_BACKEND_NAME_MAP[backend_name]):
                break

        index = getattr(user_profile.realm.authentication_methods, backend_name).number
        user_profile.realm.authentication_methods.set_bit(index, False)
        user_profile.realm.save()
        self.assertIsNone(backend.authenticate(**good_kwargs))
        user_profile.realm.authentication_methods.set_bit(index, True)
        user_profile.realm.save()

    def test_dummy_backend(self):
        # type: () -> None
        username = self.get_username()
        self.verify_backend(ZulipDummyBackend(),
                            good_kwargs=dict(username=username,
                                             use_dummy_backend=True),
                            bad_kwargs=dict(username=username,
                                            use_dummy_backend=False))

    def setup_subdomain(self, user_profile):
        # type: (UserProfile) -> None
        realm = user_profile.realm
        realm.string_id = 'zulip'
        realm.save()

    def test_email_auth_backend(self):
        # type: () -> None
        username = self.get_username()
        user_profile = self.example_user('hamlet')
        password = "testpassword"
        user_profile.set_password(password)
        user_profile.save()
        self.setup_subdomain(user_profile)

        self.verify_backend(EmailAuthBackend(),
                            bad_kwargs=dict(username=username,
                                            password=''),
                            good_kwargs=dict(username=username,
                                             password=password))

        with mock.patch('zproject.backends.email_auth_enabled',
                        return_value=False), \
                mock.patch('zproject.backends.password_auth_enabled',
                           return_value=True):
            return_data = {}  # type: Dict[str, bool]
            user = EmailAuthBackend().authenticate(self.example_email('hamlet'),
                                                   password=password,
                                                   return_data=return_data)
            self.assertEqual(user, None)
            self.assertTrue(return_data['email_auth_disabled'])

        # Subdomain is ignored when feature is not enabled
        self.verify_backend(EmailAuthBackend(),
                            good_kwargs=dict(password=password,
                                             username=username,
                                             realm_subdomain='acme',
                                             return_data=dict()))

        with self.settings(REALMS_HAVE_SUBDOMAINS=True):
            # With subdomains, authenticating with the right subdomain
            # works; using the wrong subdomain doesn't
            self.verify_backend(EmailAuthBackend(),
                                good_kwargs=dict(password=password,
                                                 username=username,
                                                 realm_subdomain='zulip',
                                                 return_data=dict()),
                                bad_kwargs=dict(password=password,
                                                username=username,
                                                realm_subdomain='acme',
                                                return_data=dict()))
            # Things work normally in the event that we're using a
            # non-subdomain login page, even if subdomains are enabled
            self.verify_backend(EmailAuthBackend(),
                                bad_kwargs=dict(password="wrong",
                                                username=username),
                                good_kwargs=dict(password=password,
                                                 username=username))

    def test_email_auth_backend_disabled_password_auth(self):
        # type: () -> None
        user_profile = self.example_user('hamlet')
        password = "testpassword"
        user_profile.set_password(password)
        user_profile.save()
        # Verify if a realm has password auth disabled, correct password is rejected
        with mock.patch('zproject.backends.password_auth_enabled', return_value=False):
            self.assertIsNone(EmailAuthBackend().authenticate(self.example_email('hamlet'), password))

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipDummyBackend',))
    def test_no_backend_enabled(self):
        # type: () -> None
        result = self.client_get('/login/')
        self.assert_in_success_response(["No authentication backends are enabled"], result)

        result = self.client_get('/register/')
        self.assert_in_success_response(["No authentication backends are enabled"], result)

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.GoogleMobileOauth2Backend',))
    def test_any_backend_enabled(self):
        # type: () -> None

        # testing to avoid false error messages.
        result = self.client_get('/login/')
        self.assert_not_in_success_response(["No Authentication Backend is enabled."], result)

        result = self.client_get('/register/')
        self.assert_not_in_success_response(["No Authentication Backend is enabled."], result)

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.GoogleMobileOauth2Backend',))
    def test_google_backend(self):
        # type: () -> None
        user_profile = self.example_user('hamlet')
        email = user_profile.email
        backend = GoogleMobileOauth2Backend()
        payload = dict(email_verified=True,
                       email=email)
        self.setup_subdomain(user_profile)

        with mock.patch('apiclient.sample_tools.client.verify_id_token', return_value=payload):
            self.verify_backend(backend)

        # With REALMS_HAVE_SUBDOMAINS off, subdomain is ignored
        with mock.patch('apiclient.sample_tools.client.verify_id_token', return_value=payload):
            self.verify_backend(backend,
                                good_kwargs=dict(realm_subdomain='acme'))

        with self.settings(REALMS_HAVE_SUBDOMAINS=True):
            # With subdomains, authenticating with the right subdomain
            # works; using the wrong subdomain doesn't
            with mock.patch('apiclient.sample_tools.client.verify_id_token', return_value=payload):
                self.verify_backend(backend,
                                    good_kwargs=dict(realm_subdomain="zulip"),
                                    bad_kwargs=dict(realm_subdomain='acme'))

        # Verify valid_attestation parameter is set correctly
        unverified_payload = dict(email_verified=False)
        with mock.patch('apiclient.sample_tools.client.verify_id_token', return_value=unverified_payload):
            ret = dict()  # type: Dict[str, str]
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
        with mock.patch('apiclient.sample_tools.client.verify_id_token',
                        side_effect=AppIdentityError):
            ret = dict()
            result = backend.authenticate(return_data=ret)
            self.assertIsNone(result)

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_ldap_backend(self):
        # type: () -> None
        user_profile = self.example_user('hamlet')
        email = user_profile.email
        password = "test_password"
        self.setup_subdomain(user_profile)

        username = self.get_username()
        backend = ZulipLDAPAuthBackend()

        # Test LDAP auth fails when LDAP server rejects password
        with mock.patch('django_auth_ldap.backend._LDAPUser._authenticate_user_dn',
                        side_effect=_LDAPUser.AuthenticationFailed("Failed")), (
            mock.patch('django_auth_ldap.backend._LDAPUser._check_requirements')), (
            mock.patch('django_auth_ldap.backend._LDAPUser._get_user_attrs',
                       return_value=dict(full_name=['Hamlet']))):
            self.assertIsNone(backend.authenticate(email, password))

        # For this backend, we mock the internals of django_auth_ldap
        with mock.patch('django_auth_ldap.backend._LDAPUser._authenticate_user_dn'), (
            mock.patch('django_auth_ldap.backend._LDAPUser._check_requirements')), (
            mock.patch('django_auth_ldap.backend._LDAPUser._get_user_attrs',
                       return_value=dict(full_name=['Hamlet']))):
            self.verify_backend(backend, good_kwargs=dict(username=username,
                                                          password=password))

        with mock.patch('django_auth_ldap.backend._LDAPUser._authenticate_user_dn'), (
            mock.patch('django_auth_ldap.backend._LDAPUser._check_requirements')), (
            mock.patch('django_auth_ldap.backend._LDAPUser._get_user_attrs',
                       return_value=dict(full_name=['Hamlet']))):
            self.verify_backend(backend,
                                good_kwargs=dict(username=username,
                                                 password=password,
                                                 realm_subdomain='acme'))

        with self.settings(REALMS_HAVE_SUBDOMAINS=True):
            # With subdomains, authenticating with the right subdomain
            # works; using the wrong subdomain doesn't
            with mock.patch('django_auth_ldap.backend._LDAPUser._authenticate_user_dn'), (
                mock.patch('django_auth_ldap.backend._LDAPUser._check_requirements')), (
                mock.patch('django_auth_ldap.backend._LDAPUser._get_user_attrs',
                           return_value=dict(full_name=['Hamlet']))):
                self.verify_backend(backend,
                                    bad_kwargs=dict(username=username,
                                                    password=password,
                                                    realm_subdomain='acme'),
                                    good_kwargs=dict(username=username,
                                                     password=password,
                                                     realm_subdomain='zulip'))

        with self.settings(REALMS_HAVE_SUBDOMAINS=True):
            # With subdomains, authenticating with the right subdomain
            # works; using the wrong subdomain doesn't
            with mock.patch('django_auth_ldap.backend._LDAPUser._authenticate_user_dn'), (
                mock.patch('django_auth_ldap.backend._LDAPUser._check_requirements')), (
                mock.patch('zproject.backends.get_realm', side_effect=Realm.DoesNotExist)), (
                mock.patch('django_auth_ldap.backend._LDAPUser._get_user_attrs',
                           return_value=dict(full_name=['Hamlet']))):

                user = backend.authenticate(email,
                                            password=password,
                                            realm_subdomain='zulip')
                self.assertEqual(user, None)

    def test_devauth_backend(self):
        # type: () -> None
        self.verify_backend(DevAuthBackend(),
                            good_kwargs=dict(username=self.get_username()))

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipRemoteUserBackend',))
    def test_remote_user_backend(self):
        # type: () -> None
        self.setup_subdomain(self.example_user('hamlet'))
        username = self.get_username()
        self.verify_backend(ZulipRemoteUserBackend(),
                            good_kwargs=dict(remote_user=username,
                                             realm_subdomain='acme'))

        with self.settings(REALMS_HAVE_SUBDOMAINS=True):
            # With subdomains, authenticating with the right subdomain
            # works; using the wrong subdomain doesn't
            self.verify_backend(ZulipRemoteUserBackend(),
                                good_kwargs=dict(remote_user=username,
                                                 realm_subdomain='zulip'),
                                bad_kwargs=dict(remote_user=username,
                                                realm_subdomain='acme'))

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipRemoteUserBackend',))
    def test_remote_user_backend_sso_append_domain(self):
        # type: () -> None
        self.setup_subdomain(self.example_user('hamlet'))
        username = self.get_username(email_to_username)
        with self.settings(SSO_APPEND_DOMAIN='zulip.com'):
            self.verify_backend(ZulipRemoteUserBackend(),
                                good_kwargs=dict(remote_user=username,
                                                 realm_subdomain='acme'))

        with self.settings(REALMS_HAVE_SUBDOMAINS=True):
            # With subdomains, authenticating with the right subdomain
            # works; using the wrong subdomain doesn't
            with self.settings(SSO_APPEND_DOMAIN='zulip.com'):
                self.verify_backend(ZulipRemoteUserBackend(),
                                    good_kwargs=dict(remote_user=username,
                                                     realm_subdomain='zulip'),
                                    bad_kwargs=dict(remote_user=username,
                                                    realm_subdomain='acme'))

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.GitHubAuthBackend',))
    def test_github_backend(self):
        # type: () -> None
        user = self.example_user('hamlet')
        email = user.email
        self.setup_subdomain(user)
        good_kwargs = dict(response=dict(email=email), return_data=dict(),
                           realm_subdomain='acme')
        self.verify_backend(GitHubAuthBackend(),
                            good_kwargs=good_kwargs,
                            bad_kwargs=dict())
        with self.settings(REALMS_HAVE_SUBDOMAINS=True):
            # With subdomains, authenticating with the right subdomain
            # works; using the wrong subdomain doesn't
            good_kwargs = dict(response=dict(email=email), return_data=dict(),
                               realm_subdomain='zulip')
            bad_kwargs = dict(response=dict(email=email), return_data=dict(),
                              realm_subdomain='acme')
            self.verify_backend(GitHubAuthBackend(),
                                good_kwargs=good_kwargs,
                                bad_kwargs=bad_kwargs)

class SocialAuthMixinTest(ZulipTestCase):
    def test_social_auth_mixing(self):
        # type: () -> None
        mixin = SocialAuthMixin()
        with self.assertRaises(NotImplementedError):
            mixin.get_email_address()
        with self.assertRaises(NotImplementedError):
            mixin.get_full_name()

class GitHubAuthBackendTest(ZulipTestCase):
    def setUp(self):
        # type: () -> None
        self.user_profile = self.example_user('hamlet')
        self.email = self.user_profile.email
        self.name = 'Hamlet'
        self.backend = GitHubAuthBackend()
        self.backend.strategy = DjangoStrategy(storage=BaseDjangoStorage())
        self.user_profile.backend = self.backend

        rf = RequestFactory()
        request = rf.get('/complete')
        request.session = {}
        request.get_host = lambda: 'zulip.testserver'
        request.user = self.user_profile
        self.backend.strategy.request = request

    def do_auth(self, *args, **kwargs):
        # type: (*Any, **Any) -> UserProfile
        with self.settings(AUTHENTICATION_BACKENDS=('zproject.backends.GitHubAuthBackend',)):
            return authenticate(**kwargs)

    def test_github_auth_enabled(self):
        # type: () -> None
        with self.settings(AUTHENTICATION_BACKENDS=('zproject.backends.GitHubAuthBackend',)):
            self.assertTrue(github_auth_enabled())

    def test_full_name_with_missing_key(self):
        # type: () -> None
        self.assertEqual(self.backend.get_full_name(), '')
        self.assertEqual(self.backend.get_full_name(response={'name': None}), '')

    def test_full_name_with_none(self):
        # type: () -> None
        self.assertEqual(self.backend.get_full_name(response={'email': None}), '')

    def test_github_backend_do_auth_without_subdomains(self):
        # type: () -> None
        with mock.patch('social_core.backends.github.GithubOAuth2.do_auth',
                        side_effect=self.do_auth), \
                mock.patch('zerver.views.auth.do_login'):
            response = dict(email=self.email, name=self.name)
            result = self.backend.do_auth(response=response)
            assert(result is not None)
            self.assertNotIn('subdomain=1', result.url)

    def test_github_backend_do_auth_with_non_existing_subdomain(self):
        # type: () -> None
        with mock.patch('social_core.backends.github.GithubOAuth2.do_auth',
                        side_effect=self.do_auth):
            with self.settings(REALMS_HAVE_SUBDOMAINS=True):
                self.backend.strategy.session_set('subdomain', 'test')
                response = dict(email=self.email, name=self.name)
                result = self.backend.do_auth(response=response)
                assert(result is not None)
                self.assertIn('subdomain=1', result.url)

    @override_settings(REALMS_HAVE_SUBDOMAINS=True)
    def test_github_backend_do_auth_with_subdomains(self):
        # type: () -> None
        with mock.patch('social_core.backends.github.GithubOAuth2.do_auth',
                        side_effect=self.do_auth):
            self.backend.strategy.session_set('subdomain', 'zulip')
            response = dict(email=self.email, name=self.name)
            result = self.backend.do_auth(response=response)
            assert(result is not None)
            self.assertEqual('http://zulip.testserver/accounts/login/subdomain/', result.url)

    def test_github_backend_do_auth_for_default(self):
        # type: () -> None
        with mock.patch('social_core.backends.github.GithubOAuth2.do_auth',
                        side_effect=self.do_auth), \
                mock.patch('zproject.backends.SocialAuthMixin.process_do_auth') as result:
            response = dict(email=self.email, name=self.name)
            self.backend.do_auth('fake-access-token', response=response)

            kwargs = {'realm_subdomain': 'zulip',
                      'response': response,
                      'return_data': {}}
            result.assert_called_with(self.user_profile, 'fake-access-token', **kwargs)

    def test_github_backend_do_auth_for_default_auth_failed(self):
        # type: () -> None
        with mock.patch('social_core.backends.github.GithubOAuth2.do_auth',
                        side_effect=AuthFailed('Not found')), \
                mock.patch('logging.info'), \
                mock.patch('zproject.backends.SocialAuthMixin.process_do_auth') as result:
            response = dict(email=self.email, name=self.name)

            self.backend.do_auth('fake-access-token', response=response)
            kwargs = {'realm_subdomain': 'zulip',
                      'response': response,
                      'return_data': {}}
            result.assert_called_with(None, 'fake-access-token', **kwargs)

    @override_settings(REALMS_HAVE_SUBDOMAINS=True)
    def test_github_backend_do_auth_for_team(self):
        # type: () -> None
        with mock.patch('social_core.backends.github.GithubTeamOAuth2.do_auth',
                        side_effect=self.do_auth), \
                mock.patch('zproject.backends.SocialAuthMixin.process_do_auth') as result:
            self.backend.strategy.session_set('subdomain', 'zulip')
            response = dict(email=self.email, name=self.name)
            with self.settings(SOCIAL_AUTH_GITHUB_TEAM_ID='zulip-webapp'):
                self.backend.do_auth('fake-access-token', response=response)

                kwargs = {'realm_subdomain': 'zulip',
                          'response': response,
                          'return_data': {}}
                result.assert_called_with(self.user_profile, 'fake-access-token', **kwargs)

    @override_settings(REALMS_HAVE_SUBDOMAINS=True)
    def test_github_backend_do_auth_for_team_auth_failed(self):
        # type: () -> None
        with mock.patch('social_core.backends.github.GithubTeamOAuth2.do_auth',
                        side_effect=AuthFailed('Not found')), \
                mock.patch('logging.info'), \
                mock.patch('zproject.backends.SocialAuthMixin.process_do_auth') as result:
            self.backend.strategy.session_set('subdomain', 'zulip')
            response = dict(email=self.email, name=self.name)
            with self.settings(SOCIAL_AUTH_GITHUB_TEAM_ID='zulip-webapp'):
                self.backend.do_auth('fake-access-token', response=response)
                kwargs = {'realm_subdomain': 'zulip',
                          'response': response,
                          'return_data': {}}
                result.assert_called_with(None, 'fake-access-token', **kwargs)

    @override_settings(REALMS_HAVE_SUBDOMAINS=True)
    def test_github_backend_do_auth_for_org(self):
        # type: () -> None
        with mock.patch('social_core.backends.github.GithubOrganizationOAuth2.do_auth',
                        side_effect=self.do_auth), \
                mock.patch('zproject.backends.SocialAuthMixin.process_do_auth') as result:
            self.backend.strategy.session_set('subdomain', 'zulip')
            response = dict(email=self.email, name=self.name)
            with self.settings(SOCIAL_AUTH_GITHUB_ORG_NAME='Zulip'):
                self.backend.do_auth('fake-access-token', response=response)

                kwargs = {'realm_subdomain': 'zulip',
                          'response': response,
                          'return_data': {}}
                result.assert_called_with(self.user_profile, 'fake-access-token', **kwargs)

    @override_settings(REALMS_HAVE_SUBDOMAINS=True)
    def test_github_backend_do_auth_for_org_auth_failed(self):
        # type: () -> None
        with mock.patch('social_core.backends.github.GithubOrganizationOAuth2.do_auth',
                        side_effect=AuthFailed('Not found')), \
                mock.patch('logging.info'), \
                mock.patch('zproject.backends.SocialAuthMixin.process_do_auth') as result:
            self.backend.strategy.session_set('subdomain', 'zulip')
            response = dict(email=self.email, name=self.name)
            with self.settings(SOCIAL_AUTH_GITHUB_ORG_NAME='Zulip'):
                self.backend.do_auth('fake-access-token', response=response)
                kwargs = {'realm_subdomain': 'zulip',
                          'response': response,
                          'return_data': {}}
                result.assert_called_with(None, 'fake-access-token', **kwargs)

    def test_github_backend_authenticate_nonexisting_user(self):
        # type: () -> None
        with mock.patch('zproject.backends.get_user_profile_by_email',
                        side_effect=UserProfile.DoesNotExist("Do not exist")):
            response = dict(email=self.email, name=self.name)
            return_data = dict()  # type: Dict[str, Any]
            user = self.backend.authenticate(return_data=return_data, response=response)
            self.assertIs(user, None)
            self.assertTrue(return_data['valid_attestation'])

    def test_github_backend_authenticate_invalid_email(self):
        # type: () -> None
        response = dict(email=None, name=self.name)
        return_data = dict()  # type: Dict[str, Any]
        user = self.backend.authenticate(return_data=return_data, response=response)
        self.assertIs(user, None)
        self.assertTrue(return_data['invalid_email'])

    def test_github_backend_inactive_user(self):
        # type: () -> None
        def do_auth_inactive(*args, **kwargs):
            # type: (*Any, **Any) -> UserProfile
            return_data = kwargs['return_data']
            return_data['inactive_user'] = True
            return self.user_profile

        with mock.patch('zerver.views.auth.login_or_register_remote_user') as result, \
                mock.patch('social_core.backends.github.GithubOAuth2.do_auth',
                           side_effect=do_auth_inactive):
            response = dict(email=self.email, name=self.name)
            user = self.backend.do_auth(response=response)
            result.assert_not_called()
            self.assertIs(user, None)

    def test_github_backend_new_user_wrong_domain(self):
        # type: () -> None
        rf = RequestFactory()
        request = rf.get('/complete')
        request.session = {}
        request.user = self.user_profile
        self.backend.strategy.request = request
        session_data = {'subdomain': False, 'is_signup': '1'}
        self.backend.strategy.session_get = lambda k: session_data.get(k)

        def do_auth(*args, **kwargs):
            # type: (*Any, **Any) -> None
            return_data = kwargs['return_data']
            return_data['valid_attestation'] = True
            return None

        with mock.patch('social_core.backends.github.GithubOAuth2.do_auth',
                        side_effect=do_auth):
            email = 'nonexisting@phantom.com'
            response = dict(email=email, name='Ghost')
            result = self.backend.do_auth(response=response)
            self.assert_in_response('action="/register/"', result)
            self.assert_in_response('Your email address, {}, does not '
                                    'correspond to any existing '
                                    'organization.'.format(email), result)

    def test_github_backend_new_user(self):
        # type: () -> None
        rf = RequestFactory()
        request = rf.get('/complete')
        request.session = {}
        request.user = self.user_profile
        self.backend.strategy.request = request
        session_data = {'subdomain': False, 'is_signup': '1'}
        self.backend.strategy.session_get = lambda k: session_data.get(k)

        def do_auth(*args, **kwargs):
            # type: (*Any, **Any) -> None
            return_data = kwargs['return_data']
            return_data['valid_attestation'] = True
            return None

        with mock.patch('social_core.backends.github.GithubOAuth2.do_auth',
                        side_effect=do_auth):
            email = self.nonreg_email('newuser')
            name = "Ghost"
            response = dict(email=email, name=name)
            result = self.backend.do_auth(response=response)
            confirmation = Confirmation.objects.all().first()
            confirmation_key = confirmation.confirmation_key
            self.assertIn('do_confirm/' + confirmation_key, result.url)
            result = self.client_get(result.url)
            self.assert_in_response('action="/accounts/register/"', result)
            data = {"from_confirmation": "1",
                    "full_name": name,
                    "key": confirmation_key}
            result = self.client_post('/accounts/register/', data)
            self.assert_in_response("You're almost there", result)
            # Verify that the user is asked for name but not password
            self.assert_not_in_success_response(['id_password'], result)
            self.assert_in_success_response(['id_full_name'], result)

            result = self.client_post(
                '/accounts/register/',
                {'full_name': name,
                 'key': confirmation_key,
                 'terms': True})

        self.assertEqual(result.status_code, 302)
        user_profile = self.nonreg_user('newuser')
        self.assertEqual(get_session_dict_user(self.client.session), user_profile.id)

    def test_github_backend_existing_user(self):
        # type: () -> None
        rf = RequestFactory()
        request = rf.get('/complete')
        request.session = {}
        request.user = self.user_profile
        self.backend.strategy.request = request
        session_data = {'subdomain': False, 'is_signup': '1'}
        self.backend.strategy.session_get = lambda k: session_data.get(k)

        def do_auth(*args, **kwargs):
            # type: (*Any, **Any) -> None
            return_data = kwargs['return_data']
            return_data['valid_attestation'] = True
            return None

        with mock.patch('social_core.backends.github.GithubOAuth2.do_auth',
                        side_effect=do_auth):
            email = self.example_email("hamlet")
            response = dict(email=email, name='Hamlet')
            result = self.backend.do_auth(response=response)
            self.assert_in_response('action="/register/"', result)
            self.assert_in_response('hamlet@zulip.com already has an account',
                                    result)

    def test_github_backend_new_user_when_is_signup_is_false(self):
        # type: () -> None
        rf = RequestFactory()
        request = rf.get('/complete')
        request.session = {}
        request.user = self.user_profile
        self.backend.strategy.request = request
        session_data = {'subdomain': False, 'is_signup': '0'}
        self.backend.strategy.session_get = lambda k: session_data.get(k)

        def do_auth(*args, **kwargs):
            # type: (*Any, **Any) -> None
            return_data = kwargs['return_data']
            return_data['valid_attestation'] = True
            return None

        with mock.patch('social_core.backends.github.GithubOAuth2.do_auth',
                        side_effect=do_auth):
            email = 'nonexisting@phantom.com'
            response = dict(email=email, name='Ghost')
            result = self.backend.do_auth(response=response)
            self.assert_in_response(
                'action="/register/"', result)
            self.assert_in_response('No account found for',
                                    result)
            self.assert_in_response('nonexisting@phantom.com. Would you like to register instead?',
                                    result)

    def test_login_url(self):
        # type: () -> None
        result = self.client_get('/accounts/login/social/github')
        self.assertIn(reverse('social:begin', args=['github']), result.url)
        self.assertIn('is_signup=0', result.url)

    def test_signup_url(self):
        # type: () -> None
        result = self.client_get('/accounts/register/social/github')
        self.assertIn(reverse('social:begin', args=['github']), result.url)
        self.assertIn('is_signup=1', result.url)

    def test_github_complete(self):
        # type: () -> None
        from social_django import utils
        utils.BACKENDS = ('zproject.backends.GitHubAuthBackend',)
        with mock.patch('social_core.backends.oauth.BaseOAuth2.process_error',
                        side_effect=AuthFailed('Not found')):
            result = self.client_get(reverse('social:complete', args=['github']))
            self.assertEqual(result.status_code, 302)
            self.assertIn('login', result.url)

        utils.BACKENDS = settings.AUTHENTICATION_BACKENDS

    def test_github_complete_when_base_exc_is_raised(self):
        # type: () -> None
        from social_django import utils
        utils.BACKENDS = ('zproject.backends.GitHubAuthBackend',)
        with mock.patch('social_core.backends.oauth.BaseOAuth2.auth_complete',
                        side_effect=AuthStateForbidden('State forbidden')), \
                mock.patch('zproject.backends.logging.exception'):
            result = self.client_get(reverse('social:complete', args=['github']))
            self.assertEqual(result.status_code, 302)
            self.assertIn('login', result.url)

        utils.BACKENDS = settings.AUTHENTICATION_BACKENDS

    def test_github_complete_when_email_is_invalid(self):
        # type: () -> None
        from social_django import utils
        utils.BACKENDS = ('zproject.backends.GitHubAuthBackend',)
        with mock.patch('zproject.backends.GitHubAuthBackend.get_email_address',
                        return_value=None) as mock_get_email_address, \
                mock.patch('social_core.backends.oauth.OAuthAuth.validate_state',
                           return_value='state'), \
                mock.patch('social_core.backends.oauth.BaseOAuth2.request_access_token',
                           return_value={'access_token': 'token'}), \
                mock.patch('social_core.backends.github.GithubOAuth2.do_auth',
                           side_effect=self.do_auth), \
                mock.patch('zproject.backends.logging.warning'):
            result = self.client_get(reverse('social:complete', args=['github']),
                                     info={'state': 'state'})
            self.assertEqual(result.status_code, 200)
            self.assert_in_response("Please click the following button "
                                    "if you wish to register.", result)
            self.assertEqual(mock_get_email_address.call_count, 2)

        utils.BACKENDS = settings.AUTHENTICATION_BACKENDS


class ResponseMock(object):
    def __init__(self, status_code, data):
        # type: (int, Any) -> None
        self.status_code = status_code
        self.data = data

    def json(self):
        # type: () -> str
        return self.data

    @property
    def text(self):
        # type: () -> str
        return "Response text"

class GoogleOAuthTest(ZulipTestCase):
    def google_oauth2_test(self, token_response, account_response, *, subdomain=None,
                           mobile_flow_otp=None, is_signup=None):
        # type: (ResponseMock, ResponseMock, Optional[str], Optional[str], Optional[str]) -> HttpResponse
        url = "/accounts/login/google/"
        params = {}
        headers = {}
        if subdomain is not None:
            headers['HTTP_HOST'] = subdomain + ".testserver"
        if mobile_flow_otp is not None:
            params['mobile_flow_otp'] = mobile_flow_otp
            headers['HTTP_USER_AGENT'] = "ZulipAndroid"
        if is_signup is not None:
            params['is_signup'] = is_signup
        if len(params) > 0:
            url += "?%s" % (urllib.parse.urlencode(params))

        result = self.client_get(url, **headers)
        if result.status_code != 302 or '/accounts/login/google/send/' not in result.url:
            return result

        # Now do the /google/send/ request
        result = self.client_get(result.url, **headers)
        self.assertEqual(result.status_code, 302)
        if 'google' not in result.url:
            return result

        self.client.cookies = result.cookies
        # Now extract the CSRF token from the redirect URL
        parsed_url = urllib.parse.urlparse(result.url)
        csrf_state = urllib.parse.parse_qs(parsed_url.query)['state']

        with mock.patch("requests.post", return_value=token_response), (
                mock.patch("requests.get", return_value=account_response)):
            result = self.client_get("/accounts/login/google/done/",
                                     dict(state=csrf_state), **headers)
        return result

class GoogleSubdomainLoginTest(GoogleOAuthTest):
    def get_signed_subdomain_cookie(self, data):
        # type: (Dict[str, Any]) -> Dict[str, str]
        key = 'subdomain.signature'
        salt = key + 'zerver.views.auth'
        value = ujson.dumps(data)
        return {key: signing.get_cookie_signer(salt=salt).sign(value)}

    def test_google_oauth2_start(self):
        # type: () -> None
        with mock.patch('zerver.views.auth.get_subdomain', return_value='zulip'):
            result = self.client_get('/accounts/login/google/')
            self.assertEqual(result.status_code, 302)
            parsed_url = urllib.parse.urlparse(result.url)
            subdomain = urllib.parse.parse_qs(parsed_url.query)['subdomain']
            self.assertEqual(subdomain, ['zulip'])

    def test_google_oauth2_success(self):
        # type: () -> None
        token_response = ResponseMock(200, {'access_token': "unique_token"})
        account_data = dict(name=dict(formatted="Full Name"),
                            emails=[dict(type="account",
                                         value=self.example_email("hamlet"))])
        account_response = ResponseMock(200, account_data)
        with self.settings(REALMS_HAVE_SUBDOMAINS=True):
            result = self.google_oauth2_test(token_response, account_response, subdomain='zulip')

        data = unsign_subdomain_cookie(result)
        self.assertEqual(data['email'], self.example_email("hamlet"))
        self.assertEqual(data['name'], 'Full Name')
        self.assertEqual(data['subdomain'], 'zulip')
        self.assertEqual(result.status_code, 302)
        parsed_url = urllib.parse.urlparse(result.url)
        uri = "{}://{}{}".format(parsed_url.scheme, parsed_url.netloc,
                                 parsed_url.path)
        self.assertEqual(uri, 'http://zulip.testserver/accounts/login/subdomain/')

    @override_settings(REALMS_HAVE_SUBDOMAINS=True)
    def test_google_oauth2_no_fullname(self):
        # type: () -> None
        token_response = ResponseMock(200, {'access_token': "unique_token"})
        account_data = dict(name=dict(givenName="Test", familyName="User"),
                            emails=[dict(type="account",
                                         value=self.example_email("hamlet"))])
        account_response = ResponseMock(200, account_data)
        result = self.google_oauth2_test(token_response, account_response, subdomain='zulip')

        data = unsign_subdomain_cookie(result)
        self.assertEqual(data['email'], self.example_email("hamlet"))
        self.assertEqual(data['name'], 'Test User')
        self.assertEqual(data['subdomain'], 'zulip')
        self.assertEqual(result.status_code, 302)
        parsed_url = urllib.parse.urlparse(result.url)
        uri = "{}://{}{}".format(parsed_url.scheme, parsed_url.netloc,
                                 parsed_url.path)
        self.assertEqual(uri, 'http://zulip.testserver/accounts/login/subdomain/')

    def test_google_oauth2_mobile_success(self):
        # type: () -> None
        mobile_flow_otp = '1234abcd' * 8
        token_response = ResponseMock(200, {'access_token': "unique_token"})
        account_data = dict(name=dict(formatted="Full Name"),
                            emails=[dict(type="account",
                                         value=self.example_email("hamlet"))])
        account_response = ResponseMock(200, account_data)
        self.assertEqual(len(mail.outbox), 0)
        with self.settings(REALMS_HAVE_SUBDOMAINS=True,
                           SEND_LOGIN_EMAILS=True):
            # Verify that the right thing happens with an invalid-format OTP
            result = self.google_oauth2_test(token_response, account_response, subdomain='zulip',
                                             mobile_flow_otp="1234")
            self.assert_json_error(result, "Invalid OTP")
            result = self.google_oauth2_test(token_response, account_response, subdomain='zulip',
                                             mobile_flow_otp="invalido" * 8)
            self.assert_json_error(result, "Invalid OTP")

            # Now do it correctly
            result = self.google_oauth2_test(token_response, account_response, subdomain='zulip',
                                             mobile_flow_otp=mobile_flow_otp)
        self.assertEqual(result.status_code, 302)
        redirect_url = result['Location']
        parsed_url = urllib.parse.urlparse(redirect_url)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        self.assertEqual(parsed_url.scheme, 'zulip')
        self.assertEqual(query_params["realm"], ['http://zulip.testserver'])
        self.assertEqual(query_params["email"], [self.example_email("hamlet")])
        encrypted_api_key = query_params["otp_encrypted_api_key"][0]
        self.assertEqual(self.example_user('hamlet').api_key,
                         otp_decrypt_api_key(encrypted_api_key, mobile_flow_otp))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Zulip on Android', mail.outbox[0].body)

    def test_log_into_subdomain(self):
        # type: () -> None
        data = {'name': 'Full Name',
                'email': self.example_email("hamlet"),
                'subdomain': 'zulip',
                'is_signup': False}

        self.client.cookies = SimpleCookie(self.get_signed_subdomain_cookie(data))
        with mock.patch('zerver.views.auth.get_subdomain', return_value='zulip'):
            result = self.client_get('/accounts/login/subdomain/')
            self.assertEqual(result.status_code, 302)
            user_profile = self.example_user('hamlet')
            self.assertEqual(get_session_dict_user(self.client.session), user_profile.id)

            # If authenticate_remote_user detects a subdomain mismatch, then
            # the result should redirect to the login page.
            with mock.patch(
                    'zerver.views.auth.authenticate_remote_user',
                    return_value=(None, {'invalid_subdomain': True})):
                result = self.client_get('/accounts/login/subdomain/')
                self.assertEqual(result.status_code, 302)
                self.assertTrue(result['Location'].endswith, '?subdomain=1')

    def test_log_into_subdomain_when_is_signup_is_true(self):
        # type: () -> None
        data = {'name': 'Full Name',
                'email': self.example_email("hamlet"),
                'subdomain': 'zulip',
                'is_signup': True}

        self.client.cookies = SimpleCookie(self.get_signed_subdomain_cookie(data))
        with mock.patch('zerver.views.auth.get_subdomain', return_value='zulip'):
            result = self.client_get('/accounts/login/subdomain/')
            self.assertEqual(result.status_code, 200)
            self.assert_in_response('hamlet@zulip.com already has an account', result)

    def test_log_into_subdomain_when_is_signup_is_true_and_new_user(self):
        # type: () -> None
        data = {'name': 'New User Name',
                'email': 'new@zulip.com',
                'subdomain': 'zulip',
                'is_signup': True}

        self.client.cookies = SimpleCookie(self.get_signed_subdomain_cookie(data))
        with mock.patch('zerver.views.auth.get_subdomain', return_value='zulip'):
            result = self.client_get('/accounts/login/subdomain/')
            self.assertEqual(result.status_code, 302)
            confirmation = Confirmation.objects.all().first()
            confirmation_key = confirmation.confirmation_key
            self.assertIn('do_confirm/' + confirmation_key, result.url)
            result = self.client_get(result.url)
            self.assert_in_response('action="/accounts/register/"', result)
            data = {"from_confirmation": "1",
                    "full_name": data['name'],
                    "key": confirmation_key}
            result = self.client_post('/accounts/register/', data)
            self.assert_in_response("You're almost there", result)

            # Verify that the user is asked for name but not password
            self.assert_not_in_success_response(['id_password'], result)
            self.assert_in_success_response(['id_full_name'], result)

    def test_log_into_subdomain_when_email_is_none(self):
        # type: () -> None
        data = {'name': None,
                'email': None,
                'subdomain': 'zulip',
                'is_signup': False}

        self.client.cookies = SimpleCookie(self.get_signed_subdomain_cookie(data))
        with mock.patch('zerver.views.auth.get_subdomain', return_value='zulip'), \
                mock.patch('logging.warning'):
            result = self.client_get('/accounts/login/subdomain/')
            self.assertEqual(result.status_code, 200)
            self.assert_in_response("Please click the following button if you "
                                    "wish to register", result)

    @override_settings(REALMS_HAVE_SUBDOMAINS=True)
    def test_user_cannot_log_into_nonexisting_realm(self):
        # type: () -> None
        token_response = ResponseMock(200, {'access_token': "unique_token"})
        account_data = dict(name=dict(formatted="Full Name"),
                            emails=[dict(type="account",
                                         value=self.example_email("hamlet"))])
        account_response = ResponseMock(200, account_data)
        result = self.google_oauth2_test(token_response, account_response,
                                         subdomain='nonexistent')
        self.assert_in_success_response(["There is no Zulip organization hosted at this subdomain."],
                                        result)

    @override_settings(REALMS_HAVE_SUBDOMAINS=True)
    def test_user_cannot_log_into_wrong_subdomain(self):
        # type: () -> None
        token_response = ResponseMock(200, {'access_token': "unique_token"})
        account_data = dict(name=dict(formatted="Full Name"),
                            emails=[dict(type="account",
                                         value=self.example_email("hamlet"))])
        account_response = ResponseMock(200, account_data)
        result = self.google_oauth2_test(token_response, account_response,
                                         subdomain='zephyr')
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result.url, "http://zephyr.testserver/accounts/login/subdomain/")
        result = self.client_get('/accounts/login/subdomain/', subdomain="zephyr")
        self.assertEqual(result.status_code, 302)
        result = self.client_get('/accounts/login/?subdomain=1', subdomain="zephyr")
        self.assert_in_success_response(["Your Zulip account is not a member of the organization associated with this subdomain."],
                                        result)

    def test_user_cannot_log_into_wrong_subdomain_with_cookie(self):
        # type: () -> None
        data = {'name': 'Full Name',
                'email': self.example_email("hamlet"),
                'subdomain': 'zephyr'}

        self.client.cookies = SimpleCookie(self.get_signed_subdomain_cookie(data))
        with mock.patch('zerver.views.auth.get_subdomain', return_value='zulip'):
            result = self.client_get('/accounts/login/subdomain/')
            self.assertEqual(result.status_code, 400)

    def test_log_into_subdomain_when_signature_is_bad(self):
        # type: () -> None
        self.client.cookies = SimpleCookie({'subdomain.signature': 'invlaid'})
        with mock.patch('zerver.views.auth.get_subdomain', return_value='zulip'):
            result = self.client_get('/accounts/login/subdomain/')
            self.assertEqual(result.status_code, 400)

    def test_log_into_subdomain_when_state_is_not_passed(self):
        # type: () -> None
        with mock.patch('zerver.views.auth.get_subdomain', return_value='zulip'):
            result = self.client_get('/accounts/login/subdomain/')
            self.assertEqual(result.status_code, 400)

    def test_google_oauth2_registration(self):
        # type: () -> None
        """If the user doesn't exist yet, Google auth can be used to register an account"""
        with self.settings(REALMS_HAVE_SUBDOMAINS=True), (
                mock.patch('zerver.views.auth.get_subdomain', return_value='zulip')), (
                mock.patch('zerver.views.registration.get_subdomain', return_value='zulip')):

            email = "newuser@zulip.com"
            realm = get_realm("zulip")
            token_response = ResponseMock(200, {'access_token': "unique_token"})
            account_data = dict(name=dict(formatted="Full Name"),
                                emails=[dict(type="account",
                                             value=email)])
            account_response = ResponseMock(200, account_data)
            result = self.google_oauth2_test(token_response, account_response, subdomain='zulip',
                                             is_signup='1')

            data = unsign_subdomain_cookie(result)
            name = 'Full Name'
            self.assertEqual(data['email'], email)
            self.assertEqual(data['name'], name)
            self.assertEqual(data['subdomain'], 'zulip')
            self.assertEqual(result.status_code, 302)
            parsed_url = urllib.parse.urlparse(result.url)
            uri = "{}://{}{}".format(parsed_url.scheme, parsed_url.netloc,
                                     parsed_url.path)
            self.assertEqual(uri, 'http://zulip.testserver/accounts/login/subdomain/')

            result = self.client_get(result.url)
            self.assertEqual(result.status_code, 302)
            confirmation = Confirmation.objects.all().first()
            confirmation_key = confirmation.confirmation_key
            self.assertIn('do_confirm/' + confirmation_key, result.url)
            result = self.client_get(result.url)
            self.assert_in_response('action="/accounts/register/"', result)
            data = {"from_confirmation": "1",
                    "full_name": name,
                    "key": confirmation_key}
            result = self.client_post('/accounts/register/', data)
            self.assert_in_response("You're almost there", result)

            # Verify that the user is asked for name but not password
            self.assert_not_in_success_response(['id_password'], result)
            self.assert_in_success_response(['id_full_name'], result)

            # Click confirm registration button.
            result = self.client_post(
                '/accounts/register/',
                {'full_name': name,
                 'key': confirmation_key,
                 'terms': True})

            self.assertEqual(result.status_code, 302)
            user_profile = get_user(email, realm)
            self.assertEqual(get_session_dict_user(self.client.session), user_profile.id)

class GoogleLoginTest(GoogleOAuthTest):
    def test_google_oauth2_success(self):
        # type: () -> None
        token_response = ResponseMock(200, {'access_token': "unique_token"})
        account_data = dict(name=dict(formatted="Full Name"),
                            emails=[dict(type="account",
                                         value=self.example_email("hamlet"))])
        account_response = ResponseMock(200, account_data)
        self.google_oauth2_test(token_response, account_response, subdomain="")

        user_profile = self.example_user('hamlet')
        self.assertEqual(get_session_dict_user(self.client.session), user_profile.id)

    def test_google_oauth2_registration(self):
        # type: () -> None
        """If the user doesn't exist yet, Google auth can be used to register an account"""
        email = "newuser@zulip.com"
        token_response = ResponseMock(200, {'access_token': "unique_token"})
        account_data = dict(name=dict(formatted="Full Name"),
                            emails=[dict(type="account",
                                         value=email)])
        account_response = ResponseMock(200, account_data)
        result = self.google_oauth2_test(token_response, account_response, subdomain="")
        self.assert_in_response('No account found for',
                                result)
        self.assert_in_response('newuser@zulip.com. Would you like to register instead?',
                                result)
        # Click confirm registration button.
        result = self.client_post('/register/',
                                  {'email': email})
        self.assertEqual(result.status_code, 302)
        self.client_get(result.url)
        assert Confirmation.objects.all().count() == 1
        confirmation = Confirmation.objects.all().first()
        url = confirmation_url(confirmation.confirmation_key,
                               settings.EXTERNAL_HOST, Confirmation.USER_REGISTRATION)
        result = self.client_get(url)
        key_match = re.search('value="(?P<key>[0-9a-z]+)" name="key"', result.content.decode("utf-8"))
        result = self.client_post('/accounts/register/',
                                  {'full_name': "New User",
                                   'password': 'test_password',
                                   'key': key_match.group("key"),
                                   'terms': True})
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result.url, "http://testserver/")

    def test_google_oauth2_subdomains_homepage(self):
        # type: () -> None
        token_response = ResponseMock(200, {'access_token': "unique_token"})
        account_data = dict(name=dict(formatted="Full Name"),
                            emails=[dict(type="account",
                                         value=self.example_email("hamlet"))])
        account_response = ResponseMock(200, account_data)
        with self.settings(REALMS_HAVE_SUBDOMAINS=True,
                           ROOT_DOMAIN_LANDING_PAGE=True):
            result = self.google_oauth2_test(token_response, account_response, subdomain="")
            self.assertEqual(result.status_code, 302)
            self.assertIn('subdomain=1', result.url)

    def test_google_oauth2_400_token_response(self):
        # type: () -> None
        token_response = ResponseMock(400, {})
        with mock.patch("logging.warning") as m:
            result = self.google_oauth2_test(token_response, ResponseMock(500, {}))
        self.assertEqual(result.status_code, 400)
        self.assertEqual(m.call_args_list[0][0][0],
                         "User error converting Google oauth2 login to token: Response text")

    def test_google_oauth2_500_token_response(self):
        # type: () -> None
        token_response = ResponseMock(500, {})
        with mock.patch("logging.error") as m:
            result = self.google_oauth2_test(token_response, ResponseMock(500, {}))
        self.assertEqual(result.status_code, 400)
        self.assertEqual(m.call_args_list[0][0][0],
                         "Could not convert google oauth2 code to access_token: Response text")

    def test_google_oauth2_400_account_response(self):
        # type: () -> None
        token_response = ResponseMock(200, {'access_token': "unique_token"})
        account_response = ResponseMock(400, {})
        with mock.patch("logging.warning") as m:
            result = self.google_oauth2_test(token_response, account_response)
        self.assertEqual(result.status_code, 400)
        self.assertEqual(m.call_args_list[0][0][0],
                         "Google login failed making info API call: Response text")

    def test_google_oauth2_500_account_response(self):
        # type: () -> None
        token_response = ResponseMock(200, {'access_token': "unique_token"})
        account_response = ResponseMock(500, {})
        with mock.patch("logging.error") as m:
            result = self.google_oauth2_test(token_response, account_response)
        self.assertEqual(result.status_code, 400)
        self.assertEqual(m.call_args_list[0][0][0],
                         "Google login failed making API call: Response text")

    def test_google_oauth2_account_response_no_email(self):
        # type: () -> None
        token_response = ResponseMock(200, {'access_token': "unique_token"})
        account_data = dict(name=dict(formatted="Full Name"),
                            emails=[])
        account_response = ResponseMock(200, account_data)
        with mock.patch("logging.error") as m:
            result = self.google_oauth2_test(token_response, account_response,
                                             subdomain="zulip")
        self.assertEqual(result.status_code, 400)
        self.assertIn("Google oauth2 account email not found:", m.call_args_list[0][0][0])

    def test_google_oauth2_error_access_denied(self):
        # type: () -> None
        result = self.client_get("/accounts/login/google/done/?error=access_denied")
        self.assertEqual(result.status_code, 302)
        path = urllib.parse.urlparse(result.url).path
        self.assertEqual(path, "/")

    def test_google_oauth2_error_other(self):
        # type: () -> None
        with mock.patch("logging.warning") as m:
            result = self.client_get("/accounts/login/google/done/?error=some_other_error")
        self.assertEqual(result.status_code, 400)
        self.assertEqual(m.call_args_list[0][0][0],
                         "Error from google oauth2 login: some_other_error")

    def test_google_oauth2_missing_csrf(self):
        # type: () -> None
        with mock.patch("logging.warning") as m:
            result = self.client_get("/accounts/login/google/done/")
        self.assertEqual(result.status_code, 400)
        self.assertEqual(m.call_args_list[0][0][0],
                         'Missing Google oauth2 CSRF state')

    def test_google_oauth2_csrf_malformed(self):
        # type: () -> None
        with mock.patch("logging.warning") as m:
            result = self.client_get("/accounts/login/google/done/?state=badstate")
        self.assertEqual(result.status_code, 400)
        self.assertEqual(m.call_args_list[0][0][0],
                         'Missing Google oauth2 CSRF state')

    def test_google_oauth2_csrf_badstate(self):
        # type: () -> None
        with mock.patch("logging.warning") as m:
            result = self.client_get("/accounts/login/google/done/?state=badstate:otherbadstate:more::")
        self.assertEqual(result.status_code, 400)
        self.assertEqual(m.call_args_list[0][0][0],
                         'Google oauth2 CSRF error')

class FetchAPIKeyTest(ZulipTestCase):
    def setUp(self):
        # type: () -> None
        self.user_profile = self.example_user('hamlet')
        self.email = self.user_profile.email

    def test_success(self):
        # type: () -> None
        result = self.client_post("/api/v1/fetch_api_key",
                                  dict(username=self.email,
                                       password=initial_password(self.email)))
        self.assert_json_success(result)

    def test_invalid_email(self):
        # type: () -> None
        result = self.client_post("/api/v1/fetch_api_key",
                                  dict(username='hamlet',
                                       password=initial_password(self.email)))
        self.assert_json_error(result, "Enter a valid email address.", 400)

    def test_wrong_password(self):
        # type: () -> None
        result = self.client_post("/api/v1/fetch_api_key",
                                  dict(username=self.email,
                                       password="wrong"))
        self.assert_json_error(result, "Your username or password is incorrect.", 403)

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.GoogleMobileOauth2Backend',),
                       SEND_LOGIN_EMAILS=True)
    def test_google_oauth2_token_success(self):
        # type: () -> None
        self.assertEqual(len(mail.outbox), 0)
        with mock.patch(
                'apiclient.sample_tools.client.verify_id_token',
                return_value={
                    "email_verified": True,
                    "email": self.example_email("hamlet"),
                }):
            result = self.client_post("/api/v1/fetch_api_key",
                                      dict(username="google-oauth2-token",
                                           password="token"))
        self.assert_json_success(result)
        self.assertEqual(len(mail.outbox), 1)

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.GoogleMobileOauth2Backend',))
    def test_google_oauth2_token_failure(self):
        # type: () -> None
        payload = dict(email_verified=False)
        with mock.patch('apiclient.sample_tools.client.verify_id_token', return_value=payload):
            result = self.client_post("/api/v1/fetch_api_key",
                                      dict(username="google-oauth2-token",
                                           password="token"))
            self.assert_json_error(result, "Your username or password is incorrect.", 403)

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.GoogleMobileOauth2Backend',))
    def test_google_oauth2_token_unregistered(self):
        # type: () -> None
        with mock.patch(
                'apiclient.sample_tools.client.verify_id_token',
                return_value={
                    "email_verified": True,
                    "email": "nobody@zulip.com",
                }):
            result = self.client_post("/api/v1/fetch_api_key",
                                      dict(username="google-oauth2-token",
                                           password="token"))
        self.assert_json_error(
            result,
            "This user is not registered; do so from a browser.",
            403)

    def test_password_auth_disabled(self):
        # type: () -> None
        with mock.patch('zproject.backends.password_auth_enabled', return_value=False):
            result = self.client_post("/api/v1/fetch_api_key",
                                      dict(username=self.email,
                                           password=initial_password(self.email)))
            self.assert_json_error_contains(result, "Password auth is disabled", 403)

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_ldap_auth_email_auth_disabled_success(self):
        # type: () -> None
        ldap_patcher = mock.patch('django_auth_ldap.config.ldap.initialize')
        self.mock_initialize = ldap_patcher.start()
        self.mock_ldap = MockLDAP()
        self.mock_initialize.return_value = self.mock_ldap
        self.backend = ZulipLDAPAuthBackend()

        self.mock_ldap.directory = {
            'uid=hamlet,ou=users,dc=zulip,dc=com': {
                'userPassword': 'testing'
            }
        }
        with self.settings(
                LDAP_APPEND_DOMAIN='zulip.com',
                AUTH_LDAP_BIND_PASSWORD='',
                AUTH_LDAP_USER_DN_TEMPLATE='uid=%(user)s,ou=users,dc=zulip,dc=com'):
            result = self.client_post("/api/v1/fetch_api_key",
                                      dict(username=self.email,
                                           password="testing"))
        self.assert_json_success(result)
        self.mock_ldap.reset()
        self.mock_initialize.stop()

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
        self.user_profile = self.example_user('hamlet')
        self.email = self.user_profile.email

    def test_success(self):
        # type: () -> None
        result = self.client_post("/api/v1/dev_fetch_api_key",
                                  dict(username=self.email))
        self.assert_json_success(result)
        data = result.json()
        self.assertEqual(data["email"], self.email)
        self.assertEqual(data['api_key'], self.user_profile.api_key)

    def test_invalid_email(self):
        # type: () -> None
        email = 'hamlet'
        result = self.client_post("/api/v1/dev_fetch_api_key",
                                  dict(username=email))
        self.assert_json_error_contains(result, "Enter a valid email address.", 400)

    def test_unregistered_user(self):
        # type: () -> None
        email = 'foo@zulip.com'
        result = self.client_post("/api/v1/dev_fetch_api_key",
                                  dict(username=email))
        self.assert_json_error_contains(result, "This user is not registered.", 403)

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
        with mock.patch('zerver.views.auth.dev_auth_enabled', return_value=False):
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
        with mock.patch('zerver.views.auth.dev_auth_enabled', return_value=False):
            result = self.client_get("/api/v1/dev_get_emails")
            self.assert_json_error_contains(result, "Dev environment not enabled.", 400)

class FetchAuthBackends(ZulipTestCase):
    def assert_on_error(self, error):
        # type: (Optional[str]) -> None
        if error:
            raise AssertionError(error)

    def test_get_server_settings(self):
        # type: () -> None
        result = self.client_get("/api/v1/server_settings",
                                 subdomain="")
        self.assert_json_success(result)
        data = result.json()
        schema_checker = check_dict_only([
            ('authentication_methods', check_dict_only([
                ('google', check_bool),
                ('github', check_bool),
                ('dev', check_bool),
                ('password', check_bool),
            ])),
            ('email_auth_enabled', check_bool),
            ('require_email_format_usernames', check_bool),
            ('realm_uri', check_string),
            ('zulip_version', check_string),
            ('msg', check_string),
            ('result', check_string),
        ])
        self.assert_on_error(schema_checker("data", data))

        with self.settings(REALMS_HAVE_SUBDOMAINS=True,
                           ROOT_DOMAIN_LANDING_PAGE=False):
            result = self.client_get("/api/v1/server_settings",
                                     subdomain="")
            self.assert_json_success(result)
            data = result.json()
            schema_checker = check_dict_only([
                ('authentication_methods', check_dict_only([
                    ('google', check_bool),
                    ('github', check_bool),
                    ('dev', check_bool),
                    ('password', check_bool),
                ])),
                ('email_auth_enabled', check_bool),
                ('require_email_format_usernames', check_bool),
                ('realm_uri', check_string),
                ('zulip_version', check_string),
                ('msg', check_string),
                ('result', check_string),
            ])
            self.assert_on_error(schema_checker("data", data))

        with self.settings(REALMS_HAVE_SUBDOMAINS=True,
                           ROOT_DOMAIN_LANDING_PAGE=False):
            result = self.client_get("/api/v1/server_settings",
                                     subdomain="zulip")
        self.assert_json_success(result)
        data = result.json()
        with_realm_schema_checker = check_dict_only([
            ('zulip_version', check_string),
            ('realm_uri', check_string),
            ('realm_name', check_string),
            ('realm_description', check_string),
            ('realm_icon', check_string),
            ('email_auth_enabled', check_bool),
            ('require_email_format_usernames', check_bool),
            ('authentication_methods', check_dict_only([
                ('google', check_bool),
                ('github', check_bool),
                ('dev', check_bool),
                ('password', check_bool),
            ])),
            ('msg', check_string),
            ('result', check_string),
        ])
        self.assert_on_error(with_realm_schema_checker("data", data))

    def test_fetch_auth_backend_format(self):
        # type: () -> None
        result = self.client_get("/api/v1/get_auth_backends")
        self.assert_json_success(result)
        data = result.json()
        self.assertEqual(set(data.keys()),
                         {'msg', 'password', 'github', 'google', 'dev', 'result', 'zulip_version'})
        for backend in set(data.keys()) - {'msg', 'result', 'zulip_version'}:
            self.assertTrue(isinstance(data[backend], bool))

    def test_fetch_auth_backend(self):
        # type: () -> None
        backends = [GoogleMobileOauth2Backend(), DevAuthBackend()]
        with mock.patch('django.contrib.auth.get_backends', return_value=backends):
            result = self.client_get("/api/v1/get_auth_backends")
            self.assert_json_success(result)
            data = result.json()
            self.assertEqual(data, {
                'msg': '',
                'password': False,
                'github': False,
                'google': True,
                'dev': True,
                'result': 'success',
                'zulip_version': ZULIP_VERSION,
            })

            # Test subdomains cases
            with self.settings(REALMS_HAVE_SUBDOMAINS=True,
                               ROOT_DOMAIN_LANDING_PAGE=False):
                result = self.client_get("/api/v1/get_auth_backends")
                self.assert_json_success(result)
                data = result.json()
                self.assertEqual(data, {
                    'msg': '',
                    'password': False,
                    'github': False,
                    'google': True,
                    'dev': True,
                    'result': 'success',
                    'zulip_version': ZULIP_VERSION,
                })

                # Verify invalid subdomain
                result = self.client_get("/api/v1/get_auth_backends",
                                         subdomain="invalid")
                self.assert_json_error_contains(result, "Invalid subdomain", 400)

                # Verify correct behavior with a valid subdomain with
                # some backends disabled for the realm
                realm = get_realm("zulip")
                do_set_realm_authentication_methods(realm, dict(Google=False, Email=False, Dev=True))
                result = self.client_get("/api/v1/get_auth_backends",
                                         subdomain="zulip")
                self.assert_json_success(result)
                data = result.json()
                self.assertEqual(data, {
                    'msg': '',
                    'password': False,
                    'github': False,
                    'google': False,
                    'dev': True,
                    'result': 'success',
                    'zulip_version': ZULIP_VERSION,
                })
            with self.settings(REALMS_HAVE_SUBDOMAINS=True,
                               ROOT_DOMAIN_LANDING_PAGE=True):
                # With ROOT_DOMAIN_LANDING_PAGE, homepage fails
                result = self.client_get("/api/v1/get_auth_backends",
                                         subdomain="")
                self.assert_json_error_contains(result, "Subdomain required", 400)

                # With ROOT_DOMAIN_LANDING_PAGE, subdomain pages succeed
                result = self.client_get("/api/v1/get_auth_backends",
                                         subdomain="zulip")
                self.assert_json_success(result)
                data = result.json()
                self.assertEqual(data, {
                    'msg': '',
                    'password': False,
                    'github': False,
                    'google': False,
                    'dev': True,
                    'result': 'success',
                    'zulip_version': ZULIP_VERSION,
                })

class TestDevAuthBackend(ZulipTestCase):
    def test_login_success(self):
        # type: () -> None
        user_profile = self.example_user('hamlet')
        email = user_profile.email
        data = {'direct_email': email}
        result = self.client_post('/accounts/login/local/', data)
        self.assertEqual(result.status_code, 302)
        self.assertEqual(get_session_dict_user(self.client.session), user_profile.id)

    def test_login_with_subdomain(self):
        # type: () -> None
        user_profile = self.example_user('hamlet')
        email = user_profile.email
        data = {'direct_email': email}
        with self.settings(REALMS_HAVE_SUBDOMAINS=True):
            result = self.client_post('/accounts/login/local/', data)
        self.assertEqual(result.status_code, 302)
        self.assertEqual(get_session_dict_user(self.client.session), user_profile.id)

    @override_settings(REALMS_HAVE_SUBDOMAINS=True)
    def test_choose_realm(self):
        # type: () -> None
        result = self.client_post('/devlogin/', subdomain="zulip")
        self.assert_in_success_response(["Click on a user to log in to Zulip Dev!"], result)
        self.assert_in_success_response(["iago@zulip.com", "hamlet@zulip.com"], result)

        result = self.client_post('/devlogin/', subdomain="")
        self.assert_in_success_response(["Click on a user to log in!"], result)
        self.assert_in_success_response(["iago@zulip.com", "hamlet@zulip.com"], result)
        self.assert_in_success_response(["starnine@mit.edu", "espuser@mit.edu"], result)

        data = {'new_realm': 'zephyr'}
        result = self.client_post('/devlogin/', data, subdomain="zulip")
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result.url, "http://zephyr.testserver")
        result = self.client_get('/devlogin/', subdomain="zephyr")
        self.assert_in_success_response(["starnine@mit.edu", "espuser@mit.edu"], result)
        self.assert_in_success_response(["Click on a user to log in to MIT!"], result)
        self.assert_not_in_success_response(["iago@zulip.com", "hamlet@zulip.com"], result)

    def test_choose_realm_with_subdomains_enabled(self):
        # type: () -> None
        with mock.patch('zerver.views.auth.is_subdomain_root_or_alias', return_value=False):
            with mock.patch('zerver.views.auth.get_realm_from_request', return_value=get_realm('zulip')):
                with self.settings(REALMS_HAVE_SUBDOMAINS=True):
                    result = self.client_get("http://zulip.testserver/devlogin/")
                    self.assert_in_success_response(["iago@zulip.com", "hamlet@zulip.com"], result)
                    self.assert_not_in_success_response(["starnine@mit.edu", "espuser@mit.edu"], result)
                    self.assert_in_success_response(["Click on a user to log in to Zulip Dev!"], result)

            with mock.patch('zerver.views.auth.get_realm_from_request', return_value=get_realm('zephyr')):
                with self.settings(REALMS_HAVE_SUBDOMAINS=True):
                    result = self.client_post("http://zulip.testserver/devlogin/", {'new_realm': 'zephyr'})
                    self.assertEqual(result["Location"], "http://zephyr.testserver")

                    result = self.client_get("http://zephyr.testserver/devlogin/")
                    self.assert_not_in_success_response(["iago@zulip.com", "hamlet@zulip.com"], result)
                    self.assert_in_success_response(["starnine@mit.edu", "espuser@mit.edu"], result)
                    self.assert_in_success_response(["Click on a user to log in to MIT!"], result)

    def test_login_failure(self):
        # type: () -> None
        email = self.example_email("hamlet")
        data = {'direct_email': email}
        with self.settings(AUTHENTICATION_BACKENDS=('zproject.backends.EmailAuthBackend',)):
            with self.assertRaisesRegex(Exception, 'Direct login not supported.'):
                with mock.patch('django.core.handlers.exception.logger'):
                    self.client_post('/accounts/login/local/', data)

    def test_login_failure_due_to_nonexistent_user(self):
        # type: () -> None
        email = 'nonexisting@zulip.com'
        data = {'direct_email': email}
        with self.assertRaisesRegex(Exception, 'User cannot login'):
            with mock.patch('django.core.handlers.exception.logger'):
                self.client_post('/accounts/login/local/', data)

class TestZulipRemoteUserBackend(ZulipTestCase):
    def test_login_success(self):
        # type: () -> None
        user_profile = self.example_user('hamlet')
        email = user_profile.email
        with self.settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipRemoteUserBackend',)):
            result = self.client_post('/accounts/login/sso/', REMOTE_USER=email)
            self.assertEqual(result.status_code, 302)
            self.assertEqual(get_session_dict_user(self.client.session), user_profile.id)

    def test_authenticate_with_missing_user(self):
        # type: () -> None
        backend = ZulipRemoteUserBackend()
        self.assertIs(backend.authenticate(None), None)

    def test_login_success_with_sso_append_domain(self):
        # type: () -> None
        username = 'hamlet'
        user_profile = self.example_user('hamlet')
        with self.settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipRemoteUserBackend',),
                           SSO_APPEND_DOMAIN='zulip.com'):
            result = self.client_post('/accounts/login/sso/', REMOTE_USER=username)
            self.assertEqual(result.status_code, 302)
            self.assertEqual(get_session_dict_user(self.client.session), user_profile.id)

    def test_login_failure(self):
        # type: () -> None
        email = self.example_email("hamlet")
        result = self.client_post('/accounts/login/sso/', REMOTE_USER=email)
        self.assertEqual(result.status_code, 200)  # This should ideally be not 200.
        self.assertIs(get_session_dict_user(self.client.session), None)

    def test_login_failure_due_to_nonexisting_user(self):
        # type: () -> None
        email = 'nonexisting@zulip.com'
        with self.settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipRemoteUserBackend',)):
            result = self.client_post('/accounts/login/sso/', REMOTE_USER=email)
            self.assertEqual(result.status_code, 200)
            self.assertIs(get_session_dict_user(self.client.session), None)
            self.assert_in_response("No account found for", result)

    def test_login_failure_due_to_invalid_email(self):
        # type: () -> None
        email = 'hamlet'
        with self.settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipRemoteUserBackend',)):
            result = self.client_post('/accounts/login/sso/', REMOTE_USER=email)
            self.assert_json_error_contains(result, "Enter a valid email address.", 400)

    def test_login_failure_due_to_missing_field(self):
        # type: () -> None
        with self.settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipRemoteUserBackend',)):
            result = self.client_post('/accounts/login/sso/')
            self.assert_json_error_contains(result, "No REMOTE_USER set.", 400)

    def test_login_failure_due_to_wrong_subdomain(self):
        # type: () -> None
        email = self.example_email("hamlet")
        with self.settings(REALMS_HAVE_SUBDOMAINS=True,
                           AUTHENTICATION_BACKENDS=('zproject.backends.ZulipRemoteUserBackend',)):
            with mock.patch('zerver.views.auth.get_subdomain', return_value='acme'):
                result = self.client_post('http://testserver:9080/accounts/login/sso/',
                                          REMOTE_USER=email)
                self.assertEqual(result.status_code, 200)
                self.assertIs(get_session_dict_user(self.client.session), None)
                self.assert_in_response("No account found for", result)

    def test_login_failure_due_to_empty_subdomain(self):
        # type: () -> None
        email = self.example_email("hamlet")
        with self.settings(REALMS_HAVE_SUBDOMAINS=True,
                           AUTHENTICATION_BACKENDS=('zproject.backends.ZulipRemoteUserBackend',)):
            with mock.patch('zerver.views.auth.get_subdomain', return_value=''):
                result = self.client_post('http://testserver:9080/accounts/login/sso/',
                                          REMOTE_USER=email)
                self.assertEqual(result.status_code, 200)
                self.assertIs(get_session_dict_user(self.client.session), None)
                self.assert_in_response("No account found for", result)

    def test_login_success_under_subdomains(self):
        # type: () -> None
        user_profile = self.example_user('hamlet')
        email = user_profile.email
        with mock.patch('zerver.views.auth.get_subdomain', return_value='zulip'):
            with self.settings(
                    REALMS_HAVE_SUBDOMAINS=True,
                    AUTHENTICATION_BACKENDS=('zproject.backends.ZulipRemoteUserBackend',)):
                result = self.client_post('/accounts/login/sso/', REMOTE_USER=email)
                self.assertEqual(result.status_code, 302)
                self.assertIs(get_session_dict_user(self.client.session), user_profile.id)

class TestJWTLogin(ZulipTestCase):
    """
    JWT uses ZulipDummyBackend.
    """

    def test_login_success(self):
        # type: () -> None
        payload = {'user': 'hamlet', 'realm': 'zulip.com'}
        with self.settings(JWT_AUTH_KEYS={'zulip': 'key'}):
            email = self.example_email("hamlet")
            realm = get_realm('zulip')
            auth_key = settings.JWT_AUTH_KEYS['zulip']
            web_token = jwt.encode(payload, auth_key).decode('utf8')

            user_profile = get_user(email, realm)
            data = {'json_web_token': web_token}
            result = self.client_post('/accounts/login/jwt/', data)
            self.assertEqual(result.status_code, 302)
            self.assertEqual(get_session_dict_user(self.client.session), user_profile.id)

    def test_login_failure_when_user_is_missing(self):
        # type: () -> None
        payload = {'realm': 'zulip.com'}
        with self.settings(JWT_AUTH_KEYS={'zulip': 'key'}):
            auth_key = settings.JWT_AUTH_KEYS['zulip']
            web_token = jwt.encode(payload, auth_key).decode('utf8')
            data = {'json_web_token': web_token}
            result = self.client_post('/accounts/login/jwt/', data)
            self.assert_json_error_contains(result, "No user specified in JSON web token claims", 400)

    def test_login_failure_when_realm_is_missing(self):
        # type: () -> None
        payload = {'user': 'hamlet'}
        with self.settings(JWT_AUTH_KEYS={'zulip': 'key'}):
            auth_key = settings.JWT_AUTH_KEYS['zulip']
            web_token = jwt.encode(payload, auth_key).decode('utf8')
            data = {'json_web_token': web_token}
            result = self.client_post('/accounts/login/jwt/', data)
            self.assert_json_error_contains(result, "No realm specified in JSON web token claims", 400)

    def test_login_failure_when_key_does_not_exist(self):
        # type: () -> None
        data = {'json_web_token': 'not relevant'}
        result = self.client_post('/accounts/login/jwt/', data)
        self.assert_json_error_contains(result, "Auth key for this subdomain not found.", 400)

    def test_login_failure_when_key_is_missing(self):
        # type: () -> None
        with self.settings(JWT_AUTH_KEYS={'zulip': 'key'}):
            result = self.client_post('/accounts/login/jwt/')
            self.assert_json_error_contains(result, "No JSON web token passed in request", 400)

    def test_login_failure_when_bad_token_is_passed(self):
        # type: () -> None
        with self.settings(JWT_AUTH_KEYS={'zulip': 'key'}):
            result = self.client_post('/accounts/login/jwt/')
            self.assert_json_error_contains(result, "No JSON web token passed in request", 400)
            data = {'json_web_token': 'bad token'}
            result = self.client_post('/accounts/login/jwt/', data)
            self.assert_json_error_contains(result, "Bad JSON web token", 400)

    def test_login_failure_when_user_does_not_exist(self):
        # type: () -> None
        payload = {'user': 'nonexisting', 'realm': 'zulip.com'}
        with self.settings(JWT_AUTH_KEYS={'zulip': 'key'}):
            auth_key = settings.JWT_AUTH_KEYS['zulip']
            web_token = jwt.encode(payload, auth_key).decode('utf8')
            data = {'json_web_token': web_token}
            result = self.client_post('/accounts/login/jwt/', data)
            self.assertEqual(result.status_code, 200)  # This should ideally be not 200.
            self.assertIs(get_session_dict_user(self.client.session), None)

            # The /accounts/login/jwt/ endpoint should also handle the case
            # where the authentication attempt throws UserProfile.DoesNotExist.
            with mock.patch(
                    'zerver.views.auth.authenticate',
                    side_effect=UserProfile.DoesNotExist("Do not exist")):
                result = self.client_post('/accounts/login/jwt/', data)
            self.assertEqual(result.status_code, 200)  # This should ideally be not 200.
            self.assertIs(get_session_dict_user(self.client.session), None)

    def test_login_failure_due_to_wrong_subdomain(self):
        # type: () -> None
        payload = {'user': 'hamlet', 'realm': 'zulip.com'}
        with self.settings(REALMS_HAVE_SUBDOMAINS=True, JWT_AUTH_KEYS={'acme': 'key'}):
            with mock.patch('zerver.views.auth.get_subdomain', return_value='acme'):
                auth_key = settings.JWT_AUTH_KEYS['acme']
                web_token = jwt.encode(payload, auth_key).decode('utf8')

                data = {'json_web_token': web_token}
                result = self.client_post('/accounts/login/jwt/', data)
                self.assert_json_error_contains(result, "Wrong subdomain", 400)
                self.assertEqual(get_session_dict_user(self.client.session), None)

    def test_login_failure_due_to_empty_subdomain(self):
        # type: () -> None
        payload = {'user': 'hamlet', 'realm': 'zulip.com'}
        with self.settings(REALMS_HAVE_SUBDOMAINS=True, JWT_AUTH_KEYS={'': 'key'}):
            with mock.patch('zerver.views.auth.get_subdomain', return_value=''):
                auth_key = settings.JWT_AUTH_KEYS['']
                web_token = jwt.encode(payload, auth_key).decode('utf8')

                data = {'json_web_token': web_token}
                result = self.client_post('/accounts/login/jwt/', data)
                self.assert_json_error_contains(result, "Wrong subdomain", 400)
                self.assertEqual(get_session_dict_user(self.client.session), None)

    def test_login_success_under_subdomains(self):
        # type: () -> None
        payload = {'user': 'hamlet', 'realm': 'zulip.com'}
        with self.settings(REALMS_HAVE_SUBDOMAINS=True, JWT_AUTH_KEYS={'zulip': 'key'}):
            with mock.patch('zerver.views.auth.get_subdomain', return_value='zulip'):
                auth_key = settings.JWT_AUTH_KEYS['zulip']
                web_token = jwt.encode(payload, auth_key).decode('utf8')

                data = {'json_web_token': web_token}
                result = self.client_post('/accounts/login/jwt/', data)
                self.assertEqual(result.status_code, 302)
                user_profile = self.example_user('hamlet')
                self.assertEqual(get_session_dict_user(self.client.session), user_profile.id)

class TestLDAP(ZulipTestCase):
    def setUp(self):
        # type: () -> None
        user_profile = self.example_user('hamlet')
        self.setup_subdomain(user_profile)

        ldap_patcher = mock.patch('django_auth_ldap.config.ldap.initialize')
        self.mock_initialize = ldap_patcher.start()
        self.mock_ldap = MockLDAP()
        self.mock_initialize.return_value = self.mock_ldap
        self.backend = ZulipLDAPAuthBackend()
        # Internally `_realm` attribute is automatically set by the
        # `authenticate()` method. But for testing the `get_or_create_user()`
        # method separately, we need to set it manually.
        self.backend._realm = get_realm('zulip')

    def tearDown(self):
        # type: () -> None
        self.mock_ldap.reset()
        self.mock_initialize.stop()

    def setup_subdomain(self, user_profile):
        # type: (UserProfile) -> None
        realm = user_profile.realm
        realm.string_id = 'zulip'
        realm.save()

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_login_success(self):
        # type: () -> None
        self.mock_ldap.directory = {
            'uid=hamlet,ou=users,dc=zulip,dc=com': {
                'userPassword': 'testing'
            }
        }
        with self.settings(
                LDAP_APPEND_DOMAIN='zulip.com',
                AUTH_LDAP_BIND_PASSWORD='',
                AUTH_LDAP_USER_DN_TEMPLATE='uid=%(user)s,ou=users,dc=zulip,dc=com'):
            user_profile = self.backend.authenticate(self.example_email("hamlet"), 'testing')

            assert(user_profile is not None)
            self.assertEqual(user_profile.email, self.example_email("hamlet"))

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_login_success_with_email_attr(self):
        # type: () -> None
        self.mock_ldap.directory = {
            'uid=letham,ou=users,dc=zulip,dc=com': {
                'userPassword': 'testing',
                'email': ['hamlet@zulip.com'],
            }
        }
        with self.settings(LDAP_EMAIL_ATTR='email',
                           AUTH_LDAP_BIND_PASSWORD='',
                           AUTH_LDAP_USER_DN_TEMPLATE='uid=%(user)s,ou=users,dc=zulip,dc=com'):
            user_profile = self.backend.authenticate("letham", 'testing')

            assert (user_profile is not None)
            self.assertEqual(user_profile.email, self.example_email("hamlet"))

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_login_failure_due_to_wrong_password(self):
        # type: () -> None
        self.mock_ldap.directory = {
            'uid=hamlet,ou=users,dc=zulip,dc=com': {
                'userPassword': 'testing'
            }
        }
        with self.settings(
                LDAP_APPEND_DOMAIN='zulip.com',
                AUTH_LDAP_BIND_PASSWORD='',
                AUTH_LDAP_USER_DN_TEMPLATE='uid=%(user)s,ou=users,dc=zulip,dc=com'):
            user = self.backend.authenticate(self.example_email("hamlet"), 'wrong')
            self.assertIs(user, None)

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_login_failure_due_to_nonexistent_user(self):
        # type: () -> None
        self.mock_ldap.directory = {
            'uid=hamlet,ou=users,dc=zulip,dc=com': {
                'userPassword': 'testing'
            }
        }
        with self.settings(
                LDAP_APPEND_DOMAIN='zulip.com',
                AUTH_LDAP_BIND_PASSWORD='',
                AUTH_LDAP_USER_DN_TEMPLATE='uid=%(user)s,ou=users,dc=zulip,dc=com'):
            user = self.backend.authenticate('nonexistent@zulip.com', 'testing')
            self.assertIs(user, None)

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_ldap_permissions(self):
        # type: () -> None
        backend = self.backend
        self.assertFalse(backend.has_perm(None, None))
        self.assertFalse(backend.has_module_perms(None, None))
        self.assertTrue(backend.get_all_permissions(None, None) == set())
        self.assertTrue(backend.get_group_permissions(None, None) == set())

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_django_to_ldap_username(self):
        # type: () -> None
        backend = self.backend
        with self.settings(LDAP_APPEND_DOMAIN='zulip.com'):
            username = backend.django_to_ldap_username('"hamlet@test"@zulip.com')
            self.assertEqual(username, '"hamlet@test"')

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_ldap_to_django_username(self):
        # type: () -> None
        backend = self.backend
        with self.settings(LDAP_APPEND_DOMAIN='zulip.com'):
            username = backend.ldap_to_django_username('"hamlet@test"')
            self.assertEqual(username, '"hamlet@test"@zulip.com')

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_get_or_create_user_when_user_exists(self):
        # type: () -> None
        class _LDAPUser(object):
            attrs = {'fn': ['Full Name'], 'sn': ['Short Name']}

        backend = self.backend
        email = self.example_email("hamlet")
        user_profile, created = backend.get_or_create_user(str(email), _LDAPUser())
        self.assertFalse(created)
        self.assertEqual(user_profile.email, email)

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_get_or_create_user_when_user_does_not_exist(self):
        # type: () -> None
        class _LDAPUser(object):
            attrs = {'fn': ['Full Name'], 'sn': ['Short Name']}

        ldap_user_attr_map = {'full_name': 'fn', 'short_name': 'sn'}

        with self.settings(AUTH_LDAP_USER_ATTR_MAP=ldap_user_attr_map):
            backend = self.backend
            email = 'nonexisting@zulip.com'
            user_profile, created = backend.get_or_create_user(email, _LDAPUser())
            self.assertTrue(created)
            self.assertEqual(user_profile.email, email)
            self.assertEqual(user_profile.full_name, 'Full Name')

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_get_or_create_user_when_user_has_invalid_name(self):
        # type: () -> None
        class _LDAPUser(object):
            attrs = {'fn': ['<invalid name>'], 'sn': ['Short Name']}

        ldap_user_attr_map = {'full_name': 'fn', 'short_name': 'sn'}

        with self.settings(AUTH_LDAP_USER_ATTR_MAP=ldap_user_attr_map):
            backend = self.backend
            email = 'nonexisting@zulip.com'
            with self.assertRaisesRegex(Exception, "Invalid characters in name!"):
                backend.get_or_create_user(email, _LDAPUser())

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_get_or_create_user_when_realm_is_deactivated(self):
        # type: () -> None
        class _LDAPUser(object):
            attrs = {'fn': ['Full Name'], 'sn': ['Short Name']}

        ldap_user_attr_map = {'full_name': 'fn', 'short_name': 'sn'}

        with self.settings(AUTH_LDAP_USER_ATTR_MAP=ldap_user_attr_map):
            backend = self.backend
            email = 'nonexisting@zulip.com'
            do_deactivate_realm(backend._realm)
            with self.assertRaisesRegex(Exception, 'Realm has been deactivated'):
                backend.get_or_create_user(email, _LDAPUser())

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_get_or_create_user_when_realm_is_none(self):
        # type: () -> None
        class _LDAPUser(object):
            attrs = {'fn': ['Full Name'], 'sn': ['Short Name']}

        ldap_user_attr_map = {'full_name': 'fn', 'short_name': 'sn'}

        with self.settings(AUTH_LDAP_USER_ATTR_MAP=ldap_user_attr_map):
            backend = self.backend
            email = 'nonexisting@zulip.com'
            backend._realm = None
            with self.assertRaisesRegex(Exception, 'Realm is None'):
                backend.get_or_create_user(email, _LDAPUser())

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_get_or_create_user_when_ldap_has_no_email_attr(self):
        # type: () -> None
        class _LDAPUser(object):
            attrs = {'fn': ['Full Name'], 'sn': ['Short Name']}

        nonexisting_attr = 'email'
        with self.settings(LDAP_EMAIL_ATTR=nonexisting_attr):
            backend = self.backend
            email = 'nonexisting@zulip.com'
            with self.assertRaisesRegex(Exception, 'LDAP user doesn\'t have the needed email attribute'):
                backend.get_or_create_user(email, _LDAPUser())

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_django_to_ldap_username_when_domain_does_not_match(self):
        # type: () -> None
        backend = self.backend
        email = self.example_email("hamlet")
        with self.assertRaisesRegex(Exception, 'Username does not match LDAP domain.'):
            with self.settings(LDAP_APPEND_DOMAIN='acme.com'):
                backend.django_to_ldap_username(email)

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_login_failure_due_to_wrong_subdomain(self):
        # type: () -> None
        self.mock_ldap.directory = {
            'uid=hamlet,ou=users,dc=zulip,dc=com': {
                'userPassword': 'testing'
            }
        }
        with self.settings(
                REALMS_HAVE_SUBDOMAINS=True,
                LDAP_APPEND_DOMAIN='zulip.com',
                AUTH_LDAP_BIND_PASSWORD='',
                AUTH_LDAP_USER_DN_TEMPLATE='uid=%(user)s,ou=users,dc=zulip,dc=com'):
            user_profile = self.backend.authenticate(self.example_email("hamlet"), 'testing',
                                                     realm_subdomain='acme')
            self.assertIs(user_profile, None)

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_login_failure_due_to_empty_subdomain(self):
        # type: () -> None
        self.mock_ldap.directory = {
            'uid=hamlet,ou=users,dc=zulip,dc=com': {
                'userPassword': 'testing'
            }
        }
        with self.settings(
                REALMS_HAVE_SUBDOMAINS=True,
                LDAP_APPEND_DOMAIN='zulip.com',
                AUTH_LDAP_BIND_PASSWORD='',
                AUTH_LDAP_USER_DN_TEMPLATE='uid=%(user)s,ou=users,dc=zulip,dc=com'):
            user_profile = self.backend.authenticate(self.example_email("hamlet"), 'testing',
                                                     realm_subdomain='')
            self.assertIs(user_profile, None)

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_login_success_when_subdomain_is_none(self):
        # type: () -> None
        self.mock_ldap.directory = {
            'uid=hamlet,ou=users,dc=zulip,dc=com': {
                'userPassword': 'testing'
            }
        }
        with self.settings(
                REALMS_HAVE_SUBDOMAINS=True,
                LDAP_APPEND_DOMAIN='zulip.com',
                AUTH_LDAP_BIND_PASSWORD='',
                AUTH_LDAP_USER_DN_TEMPLATE='uid=%(user)s,ou=users,dc=zulip,dc=com'):
            user_profile = self.backend.authenticate(self.example_email("hamlet"), 'testing',
                                                     realm_subdomain=None)
            assert(user_profile is not None)
            self.assertEqual(user_profile.email, self.example_email("hamlet"))

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_login_success_with_valid_subdomain(self):
        # type: () -> None
        self.mock_ldap.directory = {
            'uid=hamlet,ou=users,dc=zulip,dc=com': {
                'userPassword': 'testing'
            }
        }
        with self.settings(
                REALMS_HAVE_SUBDOMAINS=True,
                LDAP_APPEND_DOMAIN='zulip.com',
                AUTH_LDAP_BIND_PASSWORD='',
                AUTH_LDAP_USER_DN_TEMPLATE='uid=%(user)s,ou=users,dc=zulip,dc=com'):
            user_profile = self.backend.authenticate(self.example_email("hamlet"), 'testing',
                                                     realm_subdomain='zulip')
            assert(user_profile is not None)
            self.assertEqual(user_profile.email, self.example_email("hamlet"))

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_login_success_when_user_does_not_exist_with_valid_subdomain(self):
        # type: () -> None
        self.mock_ldap.directory = {
            'uid=nonexisting,ou=users,dc=acme,dc=com': {
                'cn': ['NonExisting', ],
                'userPassword': 'testing'
            }
        }
        with self.settings(
                REALMS_HAVE_SUBDOMAINS=True,
                LDAP_APPEND_DOMAIN='acme.com',
                AUTH_LDAP_BIND_PASSWORD='',
                AUTH_LDAP_USER_DN_TEMPLATE='uid=%(user)s,ou=users,dc=acme,dc=com'):
            user_profile = self.backend.authenticate('nonexisting@acme.com', 'testing',
                                                     realm_subdomain='zulip')
            assert(user_profile is not None)
            self.assertEqual(user_profile.email, 'nonexisting@acme.com')
            self.assertEqual(user_profile.full_name, 'NonExisting')
            self.assertEqual(user_profile.realm.string_id, 'zulip')

class TestZulipLDAPUserPopulator(ZulipTestCase):
    def test_authenticate(self):
        # type: () -> None
        backend = ZulipLDAPUserPopulator()
        result = backend.authenticate(self.example_email("hamlet"), 'testing')  # type: ignore # complains that the function does not return any value!
        self.assertIs(result, None)

class TestZulipAuthMixin(ZulipTestCase):
    def test_get_user(self):
        # type: () -> None
        backend = ZulipAuthMixin()
        result = backend.get_user(11111)
        self.assertIs(result, None)

class TestPasswordAuthEnabled(ZulipTestCase):
    def test_password_auth_enabled_for_ldap(self):
        # type: () -> None
        with self.settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',)):
            realm = Realm.objects.get(string_id='zulip')
            self.assertTrue(password_auth_enabled(realm))

class TestRequireEmailFormatUsernames(ZulipTestCase):
    def test_require_email_format_usernames_for_ldap_with_append_domain(self):
        # type: () -> None
        with self.settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',),
                           LDAP_APPEND_DOMAIN="zulip.com"):
            realm = Realm.objects.get(string_id='zulip')
            self.assertFalse(require_email_format_usernames(realm))

    def test_require_email_format_usernames_for_ldap_with_email_attr(self):
        # type: () -> None
        with self.settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',),
                           LDAP_EMAIL_ATTR="email"):
            realm = Realm.objects.get(string_id='zulip')
            self.assertFalse(require_email_format_usernames(realm))

    def test_require_email_format_usernames_for_email_only(self):
        # type: () -> None
        with self.settings(AUTHENTICATION_BACKENDS=('zproject.backends.EmailAuthBackend',)):
            realm = Realm.objects.get(string_id='zulip')
            self.assertTrue(require_email_format_usernames(realm))

    def test_require_email_format_usernames_for_email_and_ldap_with_email_attr(self):
        # type: () -> None
        with self.settings(AUTHENTICATION_BACKENDS=('zproject.backends.EmailAuthBackend',
                                                    'zproject.backends.ZulipLDAPAuthBackend'),
                           LDAP_EMAIL_ATTR="email"):
            realm = Realm.objects.get(string_id='zulip')
            self.assertFalse(require_email_format_usernames(realm))

    def test_require_email_format_usernames_for_email_and_ldap_with_append_email(self):
        # type: () -> None
        with self.settings(AUTHENTICATION_BACKENDS=('zproject.backends.EmailAuthBackend',
                                                    'zproject.backends.ZulipLDAPAuthBackend'),
                           LDAP_APPEND_DOMAIN="zulip.com"):
            realm = Realm.objects.get(string_id='zulip')
            self.assertFalse(require_email_format_usernames(realm))

class TestMaybeSendToRegistration(ZulipTestCase):
    def test_sso_only_when_preregistration_user_does_not_exist(self):
        # type: () -> None
        rf = RequestFactory()
        request = rf.get('/')
        request.session = {}
        request.user = None

        # Creating a mock Django form in order to keep the test simple.
        # This form will be returned by the create_hompage_form function
        # and will always be valid so that the code that we want to test
        # actually runs.
        class Form(object):
            def is_valid(self):
                # type: () -> bool
                return True

        with self.settings(ONLY_SSO=True):
            with mock.patch('zerver.views.auth.HomepageForm', return_value=Form()):
                self.assertEqual(PreregistrationUser.objects.all().count(), 0)
                result = maybe_send_to_registration(request, self.example_email("hamlet"))
                self.assertEqual(result.status_code, 302)
                confirmation = Confirmation.objects.all().first()
                confirmation_key = confirmation.confirmation_key
                self.assertIn('do_confirm/' + confirmation_key, result.url)
                self.assertEqual(PreregistrationUser.objects.all().count(), 1)

        result = self.client_get(result.url)
        self.assert_in_response('action="/accounts/register/"', result)
        self.assert_in_response('value="{0}" name="key"'.format(confirmation_key), result)

    def test_sso_only_when_preregistration_user_exists(self):
        # type: () -> None
        rf = RequestFactory()
        request = rf.get('/')
        request.session = {}
        request.user = None

        # Creating a mock Django form in order to keep the test simple.
        # This form will be returned by the create_hompage_form function
        # and will always be valid so that the code that we want to test
        # actually runs.
        class Form(object):
            def is_valid(self):
                # type: () -> bool
                return True

        email = self.example_email("hamlet")
        user = PreregistrationUser(email=email)
        user.save()

        with self.settings(ONLY_SSO=True):
            with mock.patch('zerver.views.auth.HomepageForm', return_value=Form()):
                self.assertEqual(PreregistrationUser.objects.all().count(), 1)
                result = maybe_send_to_registration(request, email)
                self.assertEqual(result.status_code, 302)
                confirmation = Confirmation.objects.all().first()
                confirmation_key = confirmation.confirmation_key
                self.assertIn('do_confirm/' + confirmation_key, result.url)
                self.assertEqual(PreregistrationUser.objects.all().count(), 1)

class TestAdminSetBackends(ZulipTestCase):

    def test_change_enabled_backends(self):
        # type: () -> None
        # Log in as admin
        self.login(self.example_email("iago"))
        result = self.client_patch("/json/realm", {
            'authentication_methods': ujson.dumps({u'Email': False, u'Dev': True})})
        self.assert_json_success(result)
        realm = get_realm('zulip')
        self.assertFalse(password_auth_enabled(realm))
        self.assertTrue(dev_auth_enabled(realm))

    def test_disable_all_backends(self):
        # type: () -> None
        # Log in as admin
        self.login(self.example_email("iago"))
        result = self.client_patch("/json/realm", {
            'authentication_methods': ujson.dumps({u'Email': False, u'Dev': False})})
        self.assert_json_error(result, 'At least one authentication method must be enabled.')
        realm = get_realm('zulip')
        self.assertTrue(password_auth_enabled(realm))
        self.assertTrue(dev_auth_enabled(realm))

    def test_supported_backends_only_updated(self):
        # type: () -> None
        # Log in as admin
        self.login(self.example_email("iago"))
        # Set some supported and unsupported backends
        result = self.client_patch("/json/realm", {
            'authentication_methods': ujson.dumps({u'Email': False, u'Dev': True, u'GitHub': False})})
        self.assert_json_success(result)
        realm = get_realm('zulip')
        # Check that unsupported backend is not enabled
        self.assertFalse(github_auth_enabled(realm))
        self.assertTrue(dev_auth_enabled(realm))
        self.assertFalse(password_auth_enabled(realm))

class LoginEmailValidatorTestCase(ZulipTestCase):
    def test_valid_email(self):
        # type: () -> None
        validate_login_email(self.example_email("hamlet"))

    def test_invalid_email(self):
        # type: () -> None
        with self.assertRaises(JsonableError):
            validate_login_email(u'hamlet')

class LoginOrRegisterRemoteUserTestCase(ZulipTestCase):
    def test_invalid_subdomain(self):
        # type: () -> None
        full_name = 'Hamlet'
        invalid_subdomain = True
        user_profile = self.example_user('hamlet')
        request = POSTRequestMock({}, user_profile)
        response = login_or_register_remote_user(
            request,
            self.example_email('hamlet'),
            user_profile,
            full_name=full_name,
            invalid_subdomain=invalid_subdomain)
        self.assertIn('/accounts/login/?subdomain=1', response.url)
