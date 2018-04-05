# -*- coding: utf-8 -*-
from django.conf import settings
from django.core import mail
from django.http import HttpResponse
from django.test import override_settings
from django_auth_ldap.backend import _LDAPUser
from django.contrib.auth import authenticate
from django.test.client import RequestFactory
from typing import Any, Callable, Dict, List, Optional, Text, Tuple
from builtins import object
from oauth2client.crypt import AppIdentityError
from django.core import signing
from django.urls import reverse

import jwt
import mock
import re
import time

from zerver.forms import HomepageForm
from zerver.lib.actions import (
    do_deactivate_realm,
    do_deactivate_user,
    do_reactivate_realm,
    do_reactivate_user,
    do_set_realm_authentication_methods,
    ensure_stream,
)
from zerver.lib.mobile_auth_otp import otp_decrypt_api_key
from zerver.lib.validator import validate_login_email, \
    check_bool, check_dict_only, check_string, Validator
from zerver.lib.request import JsonableError
from zerver.lib.initial_password import initial_password
from zerver.lib.sessions import get_session_dict_user
from zerver.lib.test_classes import (
    ZulipTestCase,
)
from zerver.lib.test_helpers import POSTRequestMock, HostRequestMock
from zerver.models import \
    get_realm, email_to_username, UserProfile, \
    PreregistrationUser, Realm, get_user, MultiuseInvite

from confirmation.models import Confirmation, confirmation_url, create_confirmation_link

from zproject.backends import ZulipDummyBackend, EmailAuthBackend, \
    GoogleMobileOauth2Backend, ZulipRemoteUserBackend, ZulipLDAPAuthBackend, \
    ZulipLDAPUserPopulator, DevAuthBackend, GitHubAuthBackend, ZulipAuthMixin, \
    dev_auth_enabled, password_auth_enabled, github_auth_enabled, \
    require_email_format_usernames, SocialAuthMixin, AUTH_BACKEND_NAME_MAP, \
    ZulipLDAPConfigurationError

from zerver.views.auth import (maybe_send_to_registration,
                               login_or_register_remote_user,
                               _subdomain_token_salt)
from version import ZULIP_VERSION

from social_core.exceptions import AuthFailed, AuthStateForbidden
from social_django.strategy import DjangoStrategy
from social_django.storage import BaseDjangoStorage
from social_core.backends.github import GithubOrganizationOAuth2, GithubTeamOAuth2, \
    GithubOAuth2

import urllib
from http.cookies import SimpleCookie
import ujson
from zerver.lib.test_helpers import MockLDAP, load_subdomain_token

class AuthBackendTest(ZulipTestCase):
    def get_username(self, email_to_username: Optional[Callable[[Text], Text]]=None) -> Text:
        username = self.example_email('hamlet')
        if email_to_username is not None:
            username = email_to_username(self.example_email('hamlet'))

        return username

    def verify_backend(self, backend: Any, good_kwargs: Optional[Dict[str, Any]]=None, bad_kwargs: Optional[Dict[str, Any]]=None) -> None:

        user_profile = self.example_user('hamlet')

        assert good_kwargs is not None

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
        if 'realm' in good_kwargs:
            # Because this test is a little unfaithful to the ordering
            # (i.e. we fetched the realm object before this function
            # was called, when in fact it should be fetched after we
            # changed the allowed authentication methods), we need to
            # propagate the changes we just made to the actual realm
            # object in good_kwargs.
            good_kwargs['realm'] = user_profile.realm
        self.assertIsNone(backend.authenticate(**good_kwargs))
        user_profile.realm.authentication_methods.set_bit(index, True)
        user_profile.realm.save()

    def test_dummy_backend(self) -> None:
        realm = get_realm("zulip")
        username = self.get_username()
        self.verify_backend(ZulipDummyBackend(),
                            good_kwargs=dict(username=username,
                                             realm=realm,
                                             use_dummy_backend=True),
                            bad_kwargs=dict(username=username,
                                            realm=realm,
                                            use_dummy_backend=False))

    def setup_subdomain(self, user_profile: UserProfile) -> None:
        realm = user_profile.realm
        realm.string_id = 'zulip'
        realm.save()

    def test_email_auth_backend(self) -> None:
        username = self.get_username()
        user_profile = self.example_user('hamlet')
        password = "testpassword"
        user_profile.set_password(password)
        user_profile.save()

        with mock.patch('zproject.backends.email_auth_enabled',
                        return_value=False), \
                mock.patch('zproject.backends.password_auth_enabled',
                           return_value=True):
            return_data = {}  # type: Dict[str, bool]
            user = EmailAuthBackend().authenticate(self.example_email('hamlet'),
                                                   realm=get_realm("zulip"),
                                                   password=password,
                                                   return_data=return_data)
            self.assertEqual(user, None)
            self.assertTrue(return_data['email_auth_disabled'])

        self.verify_backend(EmailAuthBackend(),
                            good_kwargs=dict(password=password,
                                             username=username,
                                             realm=get_realm('zulip'),
                                             return_data=dict()),
                            bad_kwargs=dict(password=password,
                                            username=username,
                                            realm=get_realm('zephyr'),
                                            return_data=dict()))
        self.verify_backend(EmailAuthBackend(),
                            good_kwargs=dict(password=password,
                                             username=username,
                                             realm=get_realm('zulip'),
                                             return_data=dict()),
                            bad_kwargs=dict(password=password,
                                            username=username,
                                            realm=None,
                                            return_data=dict()))

    def test_email_auth_backend_disabled_password_auth(self) -> None:
        user_profile = self.example_user('hamlet')
        password = "testpassword"
        user_profile.set_password(password)
        user_profile.save()
        # Verify if a realm has password auth disabled, correct password is rejected
        with mock.patch('zproject.backends.password_auth_enabled', return_value=False):
            self.assertIsNone(EmailAuthBackend().authenticate(self.example_email('hamlet'),
                                                              password,
                                                              realm=get_realm("zulip")))

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipDummyBackend',))
    def test_no_backend_enabled(self) -> None:
        result = self.client_get('/login/')
        self.assert_in_success_response(["No authentication backends are enabled"], result)

        result = self.client_get('/register/')
        self.assert_in_success_response(["No authentication backends are enabled"], result)

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.GoogleMobileOauth2Backend',))
    def test_any_backend_enabled(self) -> None:

        # testing to avoid false error messages.
        result = self.client_get('/login/')
        self.assert_not_in_success_response(["No Authentication Backend is enabled."], result)

        result = self.client_get('/register/')
        self.assert_not_in_success_response(["No Authentication Backend is enabled."], result)

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.GoogleMobileOauth2Backend',))
    def test_google_backend(self) -> None:
        user_profile = self.example_user('hamlet')
        email = user_profile.email
        backend = GoogleMobileOauth2Backend()
        payload = dict(email_verified=True,
                       email=email)

        with mock.patch('apiclient.sample_tools.client.verify_id_token', return_value=payload):
            self.verify_backend(backend,
                                good_kwargs=dict(realm=get_realm("zulip")),
                                bad_kwargs=dict(realm=get_realm('invalid')))

        # Verify valid_attestation parameter is set correctly
        unverified_payload = dict(email_verified=False)
        with mock.patch('apiclient.sample_tools.client.verify_id_token',
                        return_value=unverified_payload):
            ret = dict()  # type: Dict[str, str]
            result = backend.authenticate(realm=get_realm("zulip"), return_data=ret)
            self.assertIsNone(result)
            self.assertFalse(ret["valid_attestation"])

        nonexistent_user_payload = dict(email_verified=True, email="invalid@zulip.com")
        with mock.patch('apiclient.sample_tools.client.verify_id_token',
                        return_value=nonexistent_user_payload):
            ret = dict()
            result = backend.authenticate(realm=get_realm("zulip"), return_data=ret)
            self.assertIsNone(result)
            self.assertTrue(ret["valid_attestation"])
        with mock.patch('apiclient.sample_tools.client.verify_id_token',
                        side_effect=AppIdentityError):
            ret = dict()
            result = backend.authenticate(realm=get_realm("zulip"), return_data=ret)
            self.assertIsNone(result)

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_ldap_backend(self) -> None:
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
            mock.patch('django_auth_ldap.backend._LDAPUser.attrs',
                       return_value=dict(full_name=['Hamlet']))):
            self.assertIsNone(backend.authenticate(email, password, realm=get_realm("zulip")))

        with mock.patch('django_auth_ldap.backend._LDAPUser._authenticate_user_dn'), (
            mock.patch('django_auth_ldap.backend._LDAPUser._check_requirements')), (
            mock.patch('django_auth_ldap.backend._LDAPUser.attrs',
                       return_value=dict(full_name=['Hamlet']))):
            self.verify_backend(backend,
                                bad_kwargs=dict(username=username,
                                                password=password,
                                                realm=get_realm('zephyr')),
                                good_kwargs=dict(username=username,
                                                 password=password,
                                                 realm=get_realm('zulip')))
            self.verify_backend(backend,
                                bad_kwargs=dict(username=username,
                                                password=password,
                                                realm=get_realm('acme')),
                                good_kwargs=dict(username=username,
                                                 password=password,
                                                 realm=get_realm('zulip')))

    def test_devauth_backend(self) -> None:
        self.verify_backend(DevAuthBackend(),
                            good_kwargs=dict(dev_auth_username=self.get_username(),
                                             realm=get_realm("zulip")),
                            bad_kwargs=dict(dev_auth_username=self.get_username(),
                                            realm=get_realm("invalid")))

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipRemoteUserBackend',))
    def test_remote_user_backend(self) -> None:
        username = self.get_username()
        self.verify_backend(ZulipRemoteUserBackend(),
                            good_kwargs=dict(remote_user=username,
                                             realm=get_realm('zulip')),
                            bad_kwargs=dict(remote_user=username,
                                            realm=get_realm('zephyr')))

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipRemoteUserBackend',))
    def test_remote_user_backend_invalid_realm(self) -> None:
        username = self.get_username()
        self.verify_backend(ZulipRemoteUserBackend(),
                            good_kwargs=dict(remote_user=username,
                                             realm=get_realm('zulip')),
                            bad_kwargs=dict(remote_user=username,
                                            realm=None))

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipRemoteUserBackend',))
    @override_settings(SSO_APPEND_DOMAIN='zulip.com')
    def test_remote_user_backend_sso_append_domain(self) -> None:
        username = self.get_username(email_to_username)
        self.verify_backend(ZulipRemoteUserBackend(),
                            good_kwargs=dict(remote_user=username,
                                             realm=get_realm("zulip")),
                            bad_kwargs=dict(remote_user=username,
                                            realm=get_realm('zephyr')))

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.GitHubAuthBackend',))
    def test_github_backend(self) -> None:
        user = self.example_user('hamlet')
        email = user.email
        good_kwargs = dict(response=dict(email=email), return_data=dict(),
                           realm=get_realm('zulip'))
        bad_kwargs = dict(response=dict(email=email), return_data=dict(),
                          realm=None)
        self.verify_backend(GitHubAuthBackend(),
                            good_kwargs=good_kwargs,
                            bad_kwargs=bad_kwargs)
        bad_kwargs['realm'] = get_realm("zephyr")
        self.verify_backend(GitHubAuthBackend(),
                            good_kwargs=good_kwargs,
                            bad_kwargs=bad_kwargs)

class SocialAuthMixinTest(ZulipTestCase):
    def test_social_auth_mixing(self) -> None:
        mixin = SocialAuthMixin()
        with self.assertRaises(NotImplementedError):
            mixin.get_email_address()
        with self.assertRaises(NotImplementedError):
            mixin.get_full_name()

class GitHubAuthBackendTest(ZulipTestCase):
    def setUp(self) -> None:
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

    def do_auth(self, *args: Any, **kwargs: Any) -> UserProfile:
        with self.settings(AUTHENTICATION_BACKENDS=('zproject.backends.GitHubAuthBackend',)):
            return authenticate(**kwargs)

    def test_github_auth_enabled(self) -> None:
        with self.settings(AUTHENTICATION_BACKENDS=('zproject.backends.GitHubAuthBackend',)):
            self.assertTrue(github_auth_enabled())

    def test_full_name_with_missing_key(self) -> None:
        self.assertEqual(self.backend.get_full_name(), '')
        self.assertEqual(self.backend.get_full_name(response={'name': None}), '')

    def test_full_name_with_none(self) -> None:
        self.assertEqual(self.backend.get_full_name(response={'email': None}), '')

    def test_github_backend_do_auth_with_non_existing_subdomain(self) -> None:
        with mock.patch('social_core.backends.github.GithubOAuth2.do_auth',
                        side_effect=self.do_auth):
            self.backend.strategy.session_set('subdomain', 'test')
            response = dict(email=self.email, name=self.name)
            result = self.backend.do_auth(response=response)
            assert(result is not None)
            self.assertIn('subdomain=1', result.url)

    def test_github_backend_do_auth_with_subdomains(self) -> None:
        with mock.patch('social_core.backends.github.GithubOAuth2.do_auth',
                        side_effect=self.do_auth):
            self.backend.strategy.session_set('subdomain', 'zulip')
            response = dict(email=self.email, name=self.name)
            result = self.backend.do_auth(response=response)
            assert(result is not None)
            self.assertTrue(result.url.startswith('http://zulip.testserver/accounts/login/subdomain/'))

    def test_github_backend_do_auth_for_default(self) -> None:
        with mock.patch('social_core.backends.github.GithubOAuth2.do_auth',
                        side_effect=self.do_auth), \
                mock.patch('zproject.backends.SocialAuthMixin.process_do_auth') as result:
            self.backend.strategy.session_set('subdomain', 'zulip')
            response = dict(email=self.email, name=self.name)
            self.backend.do_auth('fake-access-token', response=response)

            kwargs = {'realm': get_realm('zulip'),
                      'response': response,
                      'return_data': {'valid_attestation': True}}
            result.assert_called_with(self.user_profile, 'fake-access-token', **kwargs)

    def test_github_backend_do_auth_for_default_auth_failed(self) -> None:
        with mock.patch('social_core.backends.github.GithubOAuth2.do_auth',
                        side_effect=AuthFailed('Not found')), \
                mock.patch('logging.info'), \
                mock.patch('zproject.backends.SocialAuthMixin.process_do_auth') as result:
            self.backend.strategy.session_set('subdomain', 'zulip')
            response = dict(email=self.email, name=self.name)

            self.backend.do_auth('fake-access-token', response=response)
            kwargs = {'realm': get_realm('zulip'),
                      'response': response,
                      'return_data': {}}
            result.assert_called_with(None, 'fake-access-token', **kwargs)

    def test_github_backend_do_auth_for_team(self) -> None:
        with mock.patch('social_core.backends.github.GithubTeamOAuth2.do_auth',
                        side_effect=self.do_auth), \
                mock.patch('zproject.backends.SocialAuthMixin.process_do_auth') as result:
            self.backend.strategy.session_set('subdomain', 'zulip')
            response = dict(email=self.email, name=self.name)
            with self.settings(SOCIAL_AUTH_GITHUB_TEAM_ID='zulip-webapp'):
                self.backend.do_auth('fake-access-token', response=response)

                kwargs = {'realm': get_realm('zulip'),
                          'response': response,
                          'return_data': {'valid_attestation': True}}
                result.assert_called_with(self.user_profile, 'fake-access-token', **kwargs)

    def test_github_backend_do_auth_for_team_auth_failed(self) -> None:
        with mock.patch('social_core.backends.github.GithubTeamOAuth2.do_auth',
                        side_effect=AuthFailed('Not found')), \
                mock.patch('logging.info'), \
                mock.patch('zproject.backends.SocialAuthMixin.process_do_auth') as result:
            self.backend.strategy.session_set('subdomain', 'zulip')
            response = dict(email=self.email, name=self.name)
            with self.settings(SOCIAL_AUTH_GITHUB_TEAM_ID='zulip-webapp'):
                self.backend.do_auth('fake-access-token', response=response)
                kwargs = {'realm': get_realm('zulip'),
                          'response': response,
                          'return_data': {}}
                result.assert_called_with(None, 'fake-access-token', **kwargs)

    def test_github_backend_do_auth_for_org(self) -> None:
        with mock.patch('social_core.backends.github.GithubOrganizationOAuth2.do_auth',
                        side_effect=self.do_auth), \
                mock.patch('zproject.backends.SocialAuthMixin.process_do_auth') as result:
            self.backend.strategy.session_set('subdomain', 'zulip')
            response = dict(email=self.email, name=self.name)
            with self.settings(SOCIAL_AUTH_GITHUB_ORG_NAME='Zulip'):
                self.backend.do_auth('fake-access-token', response=response)

                kwargs = {'realm': get_realm('zulip'),
                          'response': response,
                          'return_data': {'valid_attestation': True}}
                result.assert_called_with(self.user_profile, 'fake-access-token', **kwargs)

    def test_github_backend_do_auth_for_org_auth_failed(self) -> None:
        with mock.patch('social_core.backends.github.GithubOrganizationOAuth2.do_auth',
                        side_effect=AuthFailed('Not found')), \
                mock.patch('logging.info'), \
                mock.patch('zproject.backends.SocialAuthMixin.process_do_auth') as result:
            self.backend.strategy.session_set('subdomain', 'zulip')
            response = dict(email=self.email, name=self.name)
            with self.settings(SOCIAL_AUTH_GITHUB_ORG_NAME='Zulip'):
                self.backend.do_auth('fake-access-token', response=response)
                kwargs = {'realm': get_realm('zulip'),
                          'response': response,
                          'return_data': {}}
                result.assert_called_with(None, 'fake-access-token', **kwargs)

    def test_github_backend_authenticate_nonexisting_user(self) -> None:
        self.backend.strategy.session_set('subdomain', 'zulip')
        response = dict(email="invalid@zulip.com", name=self.name)
        return_data = dict()  # type: Dict[str, Any]
        user = self.backend.authenticate(return_data=return_data, response=response,
                                         realm=get_realm("zulip"))
        self.assertIs(user, None)
        self.assertTrue(return_data['valid_attestation'])

    def test_github_backend_authenticate_invalid_email(self) -> None:
        response = dict(email=None, name=self.name)
        return_data = dict()  # type: Dict[str, Any]
        user = self.backend.authenticate(return_data=return_data, response=response,
                                         realm=get_realm("zulip"))
        self.assertIs(user, None)
        self.assertTrue(return_data['invalid_email'])
        result = self.backend.process_do_auth(user, return_data=return_data, response=response)
        self.assertIs(result, None)

    def test_github_backend_inactive_user(self) -> None:
        def do_auth_inactive(*args: Any, **kwargs: Any) -> UserProfile:
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

    def test_github_backend_new_user_wrong_domain(self) -> None:
        rf = RequestFactory()
        request = rf.get('/complete')
        request.session = {}
        request.user = self.user_profile
        self.backend.strategy.request = request
        session_data = {'subdomain': Realm.SUBDOMAIN_FOR_ROOT_DOMAIN, 'is_signup': '1'}
        self.backend.strategy.session_get = lambda k: session_data.get(k)

        def do_auth(*args: Any, **kwargs: Any) -> None:
            return_data = kwargs['return_data']
            return_data['valid_attestation'] = True
            return None

        with mock.patch('social_core.backends.github.GithubOAuth2.do_auth',
                        side_effect=do_auth):
            email = 'nonexisting@phantom.com'
            response = dict(email=email, name='Ghost')
            result = self.backend.do_auth(response=response)
            self.assert_in_response('action="/register/"', result)
            self.assert_in_response('Your email address, {}, is not '
                                    'in one of the domains that are allowed to register '
                                    'for accounts in this organization.'.format(email), result)

    def test_github_backend_new_user(self) -> None:
        rf = RequestFactory()
        request = rf.get('/complete', HTTP_HOST=self.user_profile.realm.host)
        request.session = {}
        request.user = self.user_profile
        self.backend.strategy.request = request
        session_data = {'subdomain': Realm.SUBDOMAIN_FOR_ROOT_DOMAIN, 'is_signup': '1'}
        self.backend.strategy.session_get = lambda k: session_data.get(k)

        def do_auth(*args: Any, **kwargs: Any) -> None:
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

    def test_github_backend_existing_user(self) -> None:
        rf = RequestFactory()
        request = rf.get('/complete')
        request.session = {}
        request.user = self.user_profile
        self.backend.strategy.request = request
        session_data = {'subdomain': Realm.SUBDOMAIN_FOR_ROOT_DOMAIN, 'is_signup': '1'}
        self.backend.strategy.session_get = lambda k: session_data.get(k)

        def do_auth(*args: Any, **kwargs: Any) -> None:
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

    def test_github_backend_new_user_when_is_signup_is_false(self) -> None:
        rf = RequestFactory()
        request = rf.get('/complete')
        request.session = {}
        request.user = self.user_profile
        self.backend.strategy.request = request
        session_data = {'subdomain': Realm.SUBDOMAIN_FOR_ROOT_DOMAIN, 'is_signup': '0'}
        self.backend.strategy.session_get = lambda k: session_data.get(k)

        def do_auth(*args: Any, **kwargs: Any) -> None:
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

    def test_login_url(self) -> None:
        result = self.client_get('/accounts/login/social/github')
        self.assertIn(reverse('social:begin', args=['github']), result.url)
        self.assertIn('is_signup=0', result.url)

    def test_login_url_with_next_param(self) -> None:
        result = self.client_get('/accounts/login/social/github',
                                 {'next': "/image_path"})
        self.assertIn(reverse('social:begin', args=['github']), result.url)
        self.assertIn('is_signup=0', result.url)
        self.assertIn('image_path', result.url)

        result = self.client_get('/accounts/login/social/github',
                                 {'next': '/#narrow/stream/7-test-here'})
        self.assertIn(reverse('social:begin', args=['github']), result.url)
        self.assertIn('is_signup=0', result.url)
        self.assertIn('narrow', result.url)

    def test_signup_url(self) -> None:
        result = self.client_get('/accounts/register/social/github')
        self.assertIn(reverse('social:begin', args=['github']), result.url)
        self.assertIn('is_signup=1', result.url)

    def test_github_complete(self) -> None:
        from social_django import utils
        utils.BACKENDS = ('zproject.backends.GitHubAuthBackend',)
        with mock.patch('social_core.backends.oauth.BaseOAuth2.process_error',
                        side_effect=AuthFailed('Not found')):
            result = self.client_get(reverse('social:complete', args=['github']))
            self.assertEqual(result.status_code, 302)
            self.assertIn('login', result.url)

        utils.BACKENDS = settings.AUTHENTICATION_BACKENDS

    def test_github_complete_when_base_exc_is_raised(self) -> None:
        from social_django import utils
        utils.BACKENDS = ('zproject.backends.GitHubAuthBackend',)
        with mock.patch('social_core.backends.oauth.BaseOAuth2.auth_complete',
                        side_effect=AuthStateForbidden('State forbidden')), \
                mock.patch('zproject.backends.logging.warning'):
            result = self.client_get(reverse('social:complete', args=['github']))
            self.assertEqual(result.status_code, 302)
            self.assertIn('login', result.url)

        utils.BACKENDS = settings.AUTHENTICATION_BACKENDS

class ResponseMock:
    def __init__(self, status_code: int, data: Any) -> None:
        self.status_code = status_code
        self.data = data

    def json(self) -> str:
        return self.data

    @property
    def text(self) -> str:
        return "Response text"

class GoogleOAuthTest(ZulipTestCase):
    def google_oauth2_test(self, token_response: ResponseMock, account_response: ResponseMock,
                           *, subdomain: Optional[str]=None,
                           mobile_flow_otp: Optional[str]=None,
                           is_signup: Optional[str]=None,
                           next: Text='') -> HttpResponse:
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
        params['next'] = next
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
    def test_google_oauth2_start(self) -> None:
        result = self.client_get('/accounts/login/google/', subdomain="zulip")
        self.assertEqual(result.status_code, 302)
        parsed_url = urllib.parse.urlparse(result.url)
        subdomain = urllib.parse.parse_qs(parsed_url.query)['subdomain']
        self.assertEqual(subdomain, ['zulip'])

    def test_google_oauth2_success(self) -> None:
        token_response = ResponseMock(200, {'access_token': "unique_token"})
        account_data = dict(name=dict(formatted="Full Name"),
                            emails=[dict(type="account",
                                         value=self.example_email("hamlet"))])
        account_response = ResponseMock(200, account_data)
        result = self.google_oauth2_test(token_response, account_response,
                                         subdomain='zulip', next='/user_uploads/image')

        data = load_subdomain_token(result)
        self.assertEqual(data['email'], self.example_email("hamlet"))
        self.assertEqual(data['name'], 'Full Name')
        self.assertEqual(data['subdomain'], 'zulip')
        self.assertEqual(data['next'], '/user_uploads/image')
        self.assertEqual(result.status_code, 302)
        parsed_url = urllib.parse.urlparse(result.url)
        uri = "{}://{}{}".format(parsed_url.scheme, parsed_url.netloc,
                                 parsed_url.path)
        self.assertTrue(uri.startswith('http://zulip.testserver/accounts/login/subdomain/'))

    def test_google_oauth2_no_fullname(self) -> None:
        token_response = ResponseMock(200, {'access_token': "unique_token"})
        account_data = dict(name=dict(givenName="Test", familyName="User"),
                            emails=[dict(type="account",
                                         value=self.example_email("hamlet"))])
        account_response = ResponseMock(200, account_data)
        result = self.google_oauth2_test(token_response, account_response, subdomain='zulip')

        data = load_subdomain_token(result)
        self.assertEqual(data['email'], self.example_email("hamlet"))
        self.assertEqual(data['name'], 'Test User')
        self.assertEqual(data['subdomain'], 'zulip')
        self.assertEqual(data['next'], '')
        self.assertEqual(result.status_code, 302)
        parsed_url = urllib.parse.urlparse(result.url)
        uri = "{}://{}{}".format(parsed_url.scheme, parsed_url.netloc,
                                 parsed_url.path)
        self.assertTrue(uri.startswith('http://zulip.testserver/accounts/login/subdomain/'))

    def test_google_oauth2_mobile_success(self) -> None:
        mobile_flow_otp = '1234abcd' * 8
        token_response = ResponseMock(200, {'access_token': "unique_token"})
        account_data = dict(name=dict(formatted="Full Name"),
                            emails=[dict(type="account",
                                         value=self.example_email("hamlet"))])
        account_response = ResponseMock(200, account_data)
        self.assertEqual(len(mail.outbox), 0)
        with self.settings(SEND_LOGIN_EMAILS=True):
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

    def get_log_into_subdomain(self, data: Dict[str, Any], *, key: Optional[str]=None, subdomain: str='zulip') -> HttpResponse:
        token = signing.dumps(data, salt=_subdomain_token_salt, key=key)
        url_path = reverse('zerver.views.auth.log_into_subdomain', args=[token])
        return self.client_get(url_path, subdomain=subdomain)

    def test_redirect_to_next_url_for_log_into_subdomain(self) -> None:
        def test_redirect_to_next_url(next: Text='') -> HttpResponse:
            data = {'name': 'Hamlet',
                    'email': self.example_email("hamlet"),
                    'subdomain': 'zulip',
                    'is_signup': False,
                    'next': next}
            user_profile = self.example_user('hamlet')
            with mock.patch(
                    'zerver.views.auth.authenticate_remote_user',
                    return_value=(user_profile, {'invalid_subdomain': False})):
                with mock.patch('zerver.views.auth.do_login'):
                    result = self.get_log_into_subdomain(data)
            return result

        res = test_redirect_to_next_url()
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, 'http://zulip.testserver')
        res = test_redirect_to_next_url('/user_uploads/path_to_image')
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, 'http://zulip.testserver/user_uploads/path_to_image')

        res = test_redirect_to_next_url('/#narrow/stream/7-test-here')
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, 'http://zulip.testserver/#narrow/stream/7-test-here')

    def test_log_into_subdomain(self) -> None:
        data = {'name': 'Full Name',
                'email': self.example_email("hamlet"),
                'subdomain': 'zulip',
                'is_signup': False,
                'next': ''}
        result = self.get_log_into_subdomain(data)
        self.assertEqual(result.status_code, 302)
        user_profile = self.example_user('hamlet')
        self.assertEqual(get_session_dict_user(self.client.session), user_profile.id)

        with mock.patch(
                'zerver.views.auth.authenticate_remote_user',
                return_value=(None, {'invalid_subdomain': True})):
            result = self.get_log_into_subdomain(data)
            self.assert_in_success_response(['Would you like to register instead?'],
                                            result)

    def test_log_into_subdomain_when_signature_is_bad(self) -> None:
        data = {'name': 'Full Name',
                'email': self.example_email("hamlet"),
                'subdomain': 'zulip',
                'is_signup': False,
                'next': ''}
        with mock.patch('logging.warning') as mock_warning:
            result = self.get_log_into_subdomain(data, key='nonsense')
            mock_warning.assert_called_with("Subdomain cookie: Bad signature.")
        self.assertEqual(result.status_code, 400)

    def test_log_into_subdomain_when_signature_is_expired(self) -> None:
        data = {'name': 'Full Name',
                'email': self.example_email("hamlet"),
                'subdomain': 'zulip',
                'is_signup': False,
                'next': ''}
        with mock.patch('django.core.signing.time.time', return_value=time.time() - 45):
            token = signing.dumps(data, salt=_subdomain_token_salt)
        url_path = reverse('zerver.views.auth.log_into_subdomain', args=[token])
        with mock.patch('logging.warning') as mock_warning:
            result = self.client_get(url_path, subdomain='zulip')
            mock_warning.assert_called_once()
        self.assertEqual(result.status_code, 400)

    def test_log_into_subdomain_when_is_signup_is_true(self) -> None:
        data = {'name': 'Full Name',
                'email': self.example_email("hamlet"),
                'subdomain': 'zulip',
                'is_signup': True,
                'next': ''}
        result = self.get_log_into_subdomain(data)
        self.assertEqual(result.status_code, 200)
        self.assert_in_response('hamlet@zulip.com already has an account', result)

    def test_log_into_subdomain_when_is_signup_is_true_and_new_user(
            self) -> None:
        data = {'name': 'New User Name',
                'email': 'new@zulip.com',
                'subdomain': 'zulip',
                'is_signup': True,
                'next': ''}
        result = self.get_log_into_subdomain(data)
        self.assertEqual(result.status_code, 302)
        confirmation = Confirmation.objects.all().first()
        confirmation_key = confirmation.confirmation_key
        self.assertIn('do_confirm/' + confirmation_key, result.url)
        result = self.client_get(result.url)
        self.assert_in_response('action="/accounts/register/"', result)
        data = {"from_confirmation": "1",
                "full_name": data['name'],
                "key": confirmation_key}
        result = self.client_post('/accounts/register/', data, subdomain="zulip")
        self.assert_in_response("You're almost there", result)

        # Verify that the user is asked for name but not password
        self.assert_not_in_success_response(['id_password'], result)
        self.assert_in_success_response(['id_full_name'], result)

    def test_log_into_subdomain_when_using_invite_link(self) -> None:
        data = {'name': 'New User Name',
                'email': 'new@zulip.com',
                'subdomain': 'zulip',
                'is_signup': True,
                'next': ''}

        realm = get_realm("zulip")
        realm.invite_required = True
        realm.save()

        stream_names = ["new_stream_1", "new_stream_2"]
        streams = []
        for stream_name in set(stream_names):
            stream = ensure_stream(realm, stream_name)
            streams.append(stream)

        # Without the invite link, we can't create an account due to invite_required
        result = self.get_log_into_subdomain(data)
        self.assertEqual(result.status_code, 200)
        self.assert_in_success_response(['Sign up for Zulip'], result)

        # Now confirm an invitation link works
        referrer = self.example_user("hamlet")
        multiuse_obj = MultiuseInvite.objects.create(realm=realm, referred_by=referrer)
        multiuse_obj.streams.set(streams)
        invite_link = create_confirmation_link(multiuse_obj, realm.host,
                                               Confirmation.MULTIUSE_INVITE)

        result = self.client_get(invite_link, subdomain="zulip")
        self.assert_in_success_response(['Sign up for Zulip'], result)

        result = self.get_log_into_subdomain(data)
        self.assertEqual(result.status_code, 302)

        confirmation = Confirmation.objects.all().last()
        confirmation_key = confirmation.confirmation_key
        self.assertIn('do_confirm/' + confirmation_key, result.url)
        result = self.client_get(result.url)
        self.assert_in_response('action="/accounts/register/"', result)
        data2 = {"from_confirmation": "1",
                 "full_name": data['name'],
                 "key": confirmation_key}
        result = self.client_post('/accounts/register/', data2, subdomain="zulip")
        self.assert_in_response("You're almost there", result)

        # Verify that the user is asked for name but not password
        self.assert_not_in_success_response(['id_password'], result)
        self.assert_in_success_response(['id_full_name'], result)

        # Click confirm registration button.
        result = self.client_post(
            '/accounts/register/',
            {'full_name': 'New User Name',
             'key': confirmation_key,
             'terms': True})
        self.assertEqual(result.status_code, 302)
        self.assertEqual(sorted(self.get_streams('new@zulip.com', realm)), stream_names)

    def test_log_into_subdomain_when_email_is_none(self) -> None:
        data = {'name': None,
                'email': None,
                'subdomain': 'zulip',
                'is_signup': False,
                'next': ''}

        with mock.patch('logging.warning'):
            result = self.get_log_into_subdomain(data)
            self.assertEqual(result.status_code, 200)
            self.assert_in_response("Please click the following button if you "
                                    "wish to register", result)

    def test_user_cannot_log_into_nonexisting_realm(self) -> None:
        token_response = ResponseMock(200, {'access_token': "unique_token"})
        account_data = dict(name=dict(formatted="Full Name"),
                            emails=[dict(type="account",
                                         value=self.example_email("hamlet"))])
        account_response = ResponseMock(200, account_data)
        result = self.google_oauth2_test(token_response, account_response,
                                         subdomain='nonexistent')
        self.assert_in_success_response(["There is no Zulip organization hosted at this subdomain."],
                                        result)

    def test_user_cannot_log_into_wrong_subdomain(self) -> None:
        token_response = ResponseMock(200, {'access_token': "unique_token"})
        account_data = dict(name=dict(formatted="Full Name"),
                            emails=[dict(type="account",
                                         value=self.example_email("hamlet"))])
        account_response = ResponseMock(200, account_data)
        result = self.google_oauth2_test(token_response, account_response,
                                         subdomain='zephyr')
        self.assertEqual(result.status_code, 302)
        self.assertTrue(result.url.startswith("http://zephyr.testserver/accounts/login/subdomain/"))
        result = self.client_get(result.url.replace('http://zephyr.testserver', ''),
                                 subdomain="zephyr")
        self.assert_in_success_response(['Would you like to register instead?'], result)

    def test_user_cannot_log_into_wrong_subdomain_with_cookie(self) -> None:
        data = {'name': 'Full Name',
                'email': self.example_email("hamlet"),
                'subdomain': 'zephyr'}
        with mock.patch('logging.warning') as mock_warning:
            result = self.get_log_into_subdomain(data)
            mock_warning.assert_called_with("Login attempt on invalid subdomain")
        self.assertEqual(result.status_code, 400)

    def test_google_oauth2_registration(self) -> None:
        """If the user doesn't exist yet, Google auth can be used to register an account"""
        email = "newuser@zulip.com"
        realm = get_realm("zulip")
        token_response = ResponseMock(200, {'access_token': "unique_token"})
        account_data = dict(name=dict(formatted="Full Name"),
                            emails=[dict(type="account",
                                         value=email)])
        account_response = ResponseMock(200, account_data)
        result = self.google_oauth2_test(token_response, account_response, subdomain='zulip',
                                         is_signup='1')

        data = load_subdomain_token(result)
        name = 'Full Name'
        self.assertEqual(data['email'], email)
        self.assertEqual(data['name'], name)
        self.assertEqual(data['subdomain'], 'zulip')
        self.assertEqual(result.status_code, 302)
        parsed_url = urllib.parse.urlparse(result.url)
        uri = "{}://{}{}".format(parsed_url.scheme, parsed_url.netloc,
                                 parsed_url.path)
        self.assertTrue(uri.startswith('http://zulip.testserver/accounts/login/subdomain/'))

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
    @override_settings(ROOT_DOMAIN_LANDING_PAGE=True)
    def test_google_oauth2_subdomains_homepage(self) -> None:
        token_response = ResponseMock(200, {'access_token': "unique_token"})
        account_data = dict(name=dict(formatted="Full Name"),
                            emails=[dict(type="account",
                                         value=self.example_email("hamlet"))])
        account_response = ResponseMock(200, account_data)
        result = self.google_oauth2_test(token_response, account_response, subdomain="")
        self.assertEqual(result.status_code, 302)
        self.assertIn('subdomain=1', result.url)

    def test_google_oauth2_400_token_response(self) -> None:
        token_response = ResponseMock(400, {})
        with mock.patch("logging.warning") as m:
            result = self.google_oauth2_test(token_response, ResponseMock(500, {}))
        self.assertEqual(result.status_code, 400)
        self.assertEqual(m.call_args_list[0][0][0],
                         "User error converting Google oauth2 login to token: Response text")

    def test_google_oauth2_500_token_response(self) -> None:
        token_response = ResponseMock(500, {})
        with mock.patch("logging.error") as m:
            result = self.google_oauth2_test(token_response, ResponseMock(500, {}))
        self.assertEqual(result.status_code, 400)
        self.assertEqual(m.call_args_list[0][0][0],
                         "Could not convert google oauth2 code to access_token: Response text")

    def test_google_oauth2_400_account_response(self) -> None:
        token_response = ResponseMock(200, {'access_token': "unique_token"})
        account_response = ResponseMock(400, {})
        with mock.patch("logging.warning") as m:
            result = self.google_oauth2_test(token_response, account_response)
        self.assertEqual(result.status_code, 400)
        self.assertEqual(m.call_args_list[0][0][0],
                         "Google login failed making info API call: Response text")

    def test_google_oauth2_500_account_response(self) -> None:
        token_response = ResponseMock(200, {'access_token': "unique_token"})
        account_response = ResponseMock(500, {})
        with mock.patch("logging.error") as m:
            result = self.google_oauth2_test(token_response, account_response)
        self.assertEqual(result.status_code, 400)
        self.assertEqual(m.call_args_list[0][0][0],
                         "Google login failed making API call: Response text")

    def test_google_oauth2_account_response_no_email(self) -> None:
        token_response = ResponseMock(200, {'access_token': "unique_token"})
        account_data = dict(name=dict(formatted="Full Name"),
                            emails=[])
        account_response = ResponseMock(200, account_data)
        with mock.patch("logging.error") as m:
            result = self.google_oauth2_test(token_response, account_response,
                                             subdomain="zulip")
        self.assertEqual(result.status_code, 400)
        self.assertIn("Google oauth2 account email not found:", m.call_args_list[0][0][0])

    def test_google_oauth2_error_access_denied(self) -> None:
        result = self.client_get("/accounts/login/google/done/?error=access_denied")
        self.assertEqual(result.status_code, 302)
        path = urllib.parse.urlparse(result.url).path
        self.assertEqual(path, "/")

    def test_google_oauth2_error_other(self) -> None:
        with mock.patch("logging.warning") as m:
            result = self.client_get("/accounts/login/google/done/?error=some_other_error")
        self.assertEqual(result.status_code, 400)
        self.assertEqual(m.call_args_list[0][0][0],
                         "Error from google oauth2 login: some_other_error")

    def test_google_oauth2_missing_csrf(self) -> None:
        with mock.patch("logging.warning") as m:
            result = self.client_get("/accounts/login/google/done/")
        self.assertEqual(result.status_code, 400)
        self.assertEqual(m.call_args_list[0][0][0],
                         'Missing Google oauth2 CSRF state')

    def test_google_oauth2_csrf_malformed(self) -> None:
        with mock.patch("logging.warning") as m:
            result = self.client_get("/accounts/login/google/done/?state=badstate")
        self.assertEqual(result.status_code, 400)
        self.assertEqual(m.call_args_list[0][0][0],
                         'Missing Google oauth2 CSRF state')

    def test_google_oauth2_csrf_badstate(self) -> None:
        with mock.patch("logging.warning") as m:
            result = self.client_get("/accounts/login/google/done/?state=badstate:otherbadstate:more:::")
        self.assertEqual(result.status_code, 400)
        self.assertEqual(m.call_args_list[0][0][0],
                         'Google oauth2 CSRF error')

class JSONFetchAPIKeyTest(ZulipTestCase):
    def setUp(self) -> None:
        self.user_profile = self.example_user('hamlet')
        self.email = self.user_profile.email

    def test_success(self) -> None:
        self.login(self.email)
        result = self.client_post("/json/fetch_api_key",
                                  dict(user_profile=self.user_profile,
                                       password=initial_password(self.email)))
        self.assert_json_success(result)

    def test_not_loggedin(self) -> None:
        result = self.client_post("/json/fetch_api_key",
                                  dict(user_profile=self.user_profile,
                                       password=initial_password(self.email)))
        self.assert_json_error(result,
                               "Not logged in: API authentication or user session required", 401)

    def test_wrong_password(self) -> None:
        self.login(self.email)
        result = self.client_post("/json/fetch_api_key",
                                  dict(user_profile=self.user_profile,
                                       password="wrong"))
        self.assert_json_error(result, "Your username or password is incorrect.", 400)

class FetchAPIKeyTest(ZulipTestCase):
    def setUp(self) -> None:
        self.user_profile = self.example_user('hamlet')
        self.email = self.user_profile.email

    def test_success(self) -> None:
        result = self.client_post("/api/v1/fetch_api_key",
                                  dict(username=self.email,
                                       password=initial_password(self.email)))
        self.assert_json_success(result)

    def test_invalid_email(self) -> None:
        result = self.client_post("/api/v1/fetch_api_key",
                                  dict(username='hamlet',
                                       password=initial_password(self.email)))
        self.assert_json_error(result, "Enter a valid email address.", 400)

    def test_wrong_password(self) -> None:
        result = self.client_post("/api/v1/fetch_api_key",
                                  dict(username=self.email,
                                       password="wrong"))
        self.assert_json_error(result, "Your username or password is incorrect.", 403)

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.GoogleMobileOauth2Backend',),
                       SEND_LOGIN_EMAILS=True)
    def test_google_oauth2_token_success(self) -> None:
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
    def test_google_oauth2_token_failure(self) -> None:
        payload = dict(email_verified=False)
        with mock.patch('apiclient.sample_tools.client.verify_id_token', return_value=payload):
            result = self.client_post("/api/v1/fetch_api_key",
                                      dict(username="google-oauth2-token",
                                           password="token"))
            self.assert_json_error(result, "Your username or password is incorrect.", 403)

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.GoogleMobileOauth2Backend',))
    def test_google_oauth2_token_unregistered(self) -> None:
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

    def test_password_auth_disabled(self) -> None:
        with mock.patch('zproject.backends.password_auth_enabled', return_value=False):
            result = self.client_post("/api/v1/fetch_api_key",
                                      dict(username=self.email,
                                           password=initial_password(self.email)))
            self.assert_json_error_contains(result, "Password auth is disabled", 403)

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_ldap_auth_email_auth_disabled_success(self) -> None:
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

    def test_inactive_user(self) -> None:
        do_deactivate_user(self.user_profile)
        result = self.client_post("/api/v1/fetch_api_key",
                                  dict(username=self.email,
                                       password=initial_password(self.email)))
        self.assert_json_error_contains(result, "Your account has been disabled", 403)

    def test_deactivated_realm(self) -> None:
        do_deactivate_realm(self.user_profile.realm)
        result = self.client_post("/api/v1/fetch_api_key",
                                  dict(username=self.email,
                                       password=initial_password(self.email)))
        self.assert_json_error_contains(result, "This organization has been deactivated", 403)

class DevFetchAPIKeyTest(ZulipTestCase):
    def setUp(self) -> None:
        self.user_profile = self.example_user('hamlet')
        self.email = self.user_profile.email

    def test_success(self) -> None:
        result = self.client_post("/api/v1/dev_fetch_api_key",
                                  dict(username=self.email))
        self.assert_json_success(result)
        data = result.json()
        self.assertEqual(data["email"], self.email)
        self.assertEqual(data['api_key'], self.user_profile.api_key)

    def test_invalid_email(self) -> None:
        email = 'hamlet'
        result = self.client_post("/api/v1/dev_fetch_api_key",
                                  dict(username=email))
        self.assert_json_error_contains(result, "Enter a valid email address.", 400)

    def test_unregistered_user(self) -> None:
        email = 'foo@zulip.com'
        result = self.client_post("/api/v1/dev_fetch_api_key",
                                  dict(username=email))
        self.assert_json_error_contains(result, "This user is not registered.", 403)

    def test_inactive_user(self) -> None:
        do_deactivate_user(self.user_profile)
        result = self.client_post("/api/v1/dev_fetch_api_key",
                                  dict(username=self.email))
        self.assert_json_error_contains(result, "Your account has been disabled", 403)

    def test_deactivated_realm(self) -> None:
        do_deactivate_realm(self.user_profile.realm)
        result = self.client_post("/api/v1/dev_fetch_api_key",
                                  dict(username=self.email))
        self.assert_json_error_contains(result, "This organization has been deactivated", 403)

    def test_dev_auth_disabled(self) -> None:
        with mock.patch('zerver.views.auth.dev_auth_enabled', return_value=False):
            result = self.client_post("/api/v1/dev_fetch_api_key",
                                      dict(username=self.email))
            self.assert_json_error_contains(result, "Dev environment not enabled.", 400)

class DevGetEmailsTest(ZulipTestCase):
    def test_success(self) -> None:
        result = self.client_get("/api/v1/dev_list_users")
        self.assert_json_success(result)
        self.assert_in_response("direct_admins", result)
        self.assert_in_response("direct_users", result)

    def test_dev_auth_disabled(self) -> None:
        with mock.patch('zerver.views.auth.dev_auth_enabled', return_value=False):
            result = self.client_get("/api/v1/dev_list_users")
            self.assert_json_error_contains(result, "Dev environment not enabled.", 400)

class FetchAuthBackends(ZulipTestCase):
    def assert_on_error(self, error: Optional[str]) -> None:
        if error:
            raise AssertionError(error)

    def test_get_server_settings(self) -> None:
        def check_result(result: HttpResponse, extra_fields: List[Tuple[str, Validator]]=[]) -> None:
            self.assert_json_success(result)
            checker = check_dict_only([
                ('authentication_methods', check_dict_only([
                    ('google', check_bool),
                    ('github', check_bool),
                    ('email', check_bool),
                    ('ldap', check_bool),
                    ('dev', check_bool),
                    ('remoteuser', check_bool),
                    ('password', check_bool),
                ])),
                ('email_auth_enabled', check_bool),
                ('require_email_format_usernames', check_bool),
                ('realm_uri', check_string),
                ('zulip_version', check_string),
                ('push_notifications_enabled', check_bool),
                ('msg', check_string),
                ('result', check_string),
            ] + extra_fields)
            self.assert_on_error(checker("data", result.json()))

        result = self.client_get("/api/v1/server_settings", subdomain="")
        check_result(result)

        with self.settings(ROOT_DOMAIN_LANDING_PAGE=False):
            result = self.client_get("/api/v1/server_settings", subdomain="")
        check_result(result)

        with self.settings(ROOT_DOMAIN_LANDING_PAGE=False):
            result = self.client_get("/api/v1/server_settings", subdomain="zulip")
        check_result(result, [
            ('realm_name', check_string),
            ('realm_description', check_string),
            ('realm_icon', check_string),
        ])

    def test_fetch_auth_backend_format(self) -> None:
        result = self.client_get("/api/v1/get_auth_backends")
        self.assert_json_success(result)
        data = result.json()
        self.assertEqual(set(data.keys()),
                         {'msg', 'password', 'github', 'google', 'email', 'ldap',
                          'dev', 'result', 'remoteuser', 'zulip_version'})
        for backend in set(data.keys()) - {'msg', 'result', 'zulip_version'}:
            self.assertTrue(isinstance(data[backend], bool))

    def test_fetch_auth_backend(self) -> None:
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
                'email': False,
                'ldap': False,
                'remoteuser': False,
                'result': 'success',
                'zulip_version': ZULIP_VERSION,
            })

            # Test subdomains cases
            with self.settings(ROOT_DOMAIN_LANDING_PAGE=False):
                result = self.client_get("/api/v1/get_auth_backends")
                self.assert_json_success(result)
                data = result.json()
                self.assertEqual(data, {
                    'msg': '',
                    'password': False,
                    'github': False,
                    'google': True,
                    'email': False,
                    'ldap': False,
                    'remoteuser': False,
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
                    'email': False,
                    'ldap': False,
                    'remoteuser': False,
                    'dev': True,
                    'result': 'success',
                    'zulip_version': ZULIP_VERSION,
                })
            with self.settings(ROOT_DOMAIN_LANDING_PAGE=True):
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
                    'email': False,
                    'remoteuser': False,
                    'ldap': False,
                    'dev': True,
                    'result': 'success',
                    'zulip_version': ZULIP_VERSION,
                })

class TestDevAuthBackend(ZulipTestCase):
    def test_login_success(self) -> None:
        user_profile = self.example_user('hamlet')
        email = user_profile.email
        data = {'direct_email': email}
        result = self.client_post('/accounts/login/local/', data)
        self.assertEqual(result.status_code, 302)
        self.assertEqual(get_session_dict_user(self.client.session), user_profile.id)

    def test_redirect_to_next_url(self) -> None:
        def do_local_login(formaction: Text) -> HttpResponse:
            user_email = self.example_email('hamlet')
            data = {'direct_email': user_email}
            return self.client_post(formaction, data)

        res = do_local_login('/accounts/login/local/')
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, 'http://zulip.testserver')

        res = do_local_login('/accounts/login/local/?next=/user_uploads/path_to_image')
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, 'http://zulip.testserver/user_uploads/path_to_image')

        # In local Email based authentication we never make browser send the hash
        # to the backend. Rather we depend upon the browser's behaviour of persisting
        # hash anchors in between redirect requests. See below stackoverflow conversation
        # https://stackoverflow.com/questions/5283395/url-hash-is-persisting-between-redirects
        res = do_local_login('/accounts/login/local/?next=#narrow/stream/7-test-here')
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, 'http://zulip.testserver')

    def test_login_with_subdomain(self) -> None:
        user_profile = self.example_user('hamlet')
        email = user_profile.email
        data = {'direct_email': email}

        result = self.client_post('/accounts/login/local/', data)
        self.assertEqual(result.status_code, 302)
        self.assertEqual(get_session_dict_user(self.client.session), user_profile.id)

    def test_choose_realm(self) -> None:
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

    def test_choose_realm_with_subdomains_enabled(self) -> None:
        with mock.patch('zerver.views.auth.is_subdomain_root_or_alias', return_value=False):
            with mock.patch('zerver.views.auth.get_realm_from_request', return_value=get_realm('zulip')):
                result = self.client_get("http://zulip.testserver/devlogin/")
                self.assert_in_success_response(["iago@zulip.com", "hamlet@zulip.com"], result)
                self.assert_not_in_success_response(["starnine@mit.edu", "espuser@mit.edu"], result)
                self.assert_in_success_response(["Click on a user to log in to Zulip Dev!"], result)

            with mock.patch('zerver.views.auth.get_realm_from_request', return_value=get_realm('zephyr')):
                result = self.client_post("http://zulip.testserver/devlogin/", {'new_realm': 'zephyr'})
                self.assertEqual(result["Location"], "http://zephyr.testserver")

                result = self.client_get("http://zephyr.testserver/devlogin/")
                self.assert_not_in_success_response(["iago@zulip.com", "hamlet@zulip.com"], result)
                self.assert_in_success_response(["starnine@mit.edu", "espuser@mit.edu"], result)
                self.assert_in_success_response(["Click on a user to log in to MIT!"], result)

    def test_login_failure(self) -> None:
        email = self.example_email("hamlet")
        data = {'direct_email': email}
        with self.settings(AUTHENTICATION_BACKENDS=('zproject.backends.EmailAuthBackend',)):
            with mock.patch('django.core.handlers.exception.logger'):
                response = self.client_post('/accounts/login/local/', data)
                self.assertRedirects(response, reverse('dev_not_supported'))

    def test_login_failure_due_to_nonexistent_user(self) -> None:
        email = 'nonexisting@zulip.com'
        data = {'direct_email': email}
        with mock.patch('django.core.handlers.exception.logger'):
            response = self.client_post('/accounts/login/local/', data)
            self.assertRedirects(response, reverse('dev_not_supported'))

class TestZulipRemoteUserBackend(ZulipTestCase):
    def test_login_success(self) -> None:
        user_profile = self.example_user('hamlet')
        email = user_profile.email
        with self.settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipRemoteUserBackend',)):
            result = self.client_post('/accounts/login/sso/', REMOTE_USER=email)
            self.assertEqual(result.status_code, 302)
            self.assertEqual(get_session_dict_user(self.client.session), user_profile.id)

    def test_login_success_with_sso_append_domain(self) -> None:
        username = 'hamlet'
        user_profile = self.example_user('hamlet')
        with self.settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipRemoteUserBackend',),
                           SSO_APPEND_DOMAIN='zulip.com'):
            result = self.client_post('/accounts/login/sso/', REMOTE_USER=username)
            self.assertEqual(result.status_code, 302)
            self.assertEqual(get_session_dict_user(self.client.session), user_profile.id)

    def test_login_failure(self) -> None:
        email = self.example_email("hamlet")
        result = self.client_post('/accounts/login/sso/', REMOTE_USER=email)
        self.assertEqual(result.status_code, 200)  # This should ideally be not 200.
        self.assertIs(get_session_dict_user(self.client.session), None)

    def test_login_failure_due_to_nonexisting_user(self) -> None:
        email = 'nonexisting@zulip.com'
        with self.settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipRemoteUserBackend',)):
            result = self.client_post('/accounts/login/sso/', REMOTE_USER=email)
            self.assertEqual(result.status_code, 200)
            self.assertIs(get_session_dict_user(self.client.session), None)
            self.assert_in_response("No account found for", result)

    def test_login_failure_due_to_invalid_email(self) -> None:
        email = 'hamlet'
        with self.settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipRemoteUserBackend',)):
            result = self.client_post('/accounts/login/sso/', REMOTE_USER=email)
            self.assert_json_error_contains(result, "Enter a valid email address.", 400)

    def test_login_failure_due_to_missing_field(self) -> None:
        with self.settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipRemoteUserBackend',)):
            result = self.client_post('/accounts/login/sso/')
            self.assert_json_error_contains(result, "No REMOTE_USER set.", 400)

    def test_login_failure_due_to_wrong_subdomain(self) -> None:
        email = self.example_email("hamlet")
        with self.settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipRemoteUserBackend',)):
            with mock.patch('zerver.views.auth.get_subdomain', return_value='acme'):
                result = self.client_post('http://testserver:9080/accounts/login/sso/',
                                          REMOTE_USER=email)
                self.assertEqual(result.status_code, 200)
                self.assertIs(get_session_dict_user(self.client.session), None)
                self.assert_in_response("No account found for", result)

    def test_login_failure_due_to_empty_subdomain(self) -> None:
        email = self.example_email("hamlet")
        with self.settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipRemoteUserBackend',)):
            with mock.patch('zerver.views.auth.get_subdomain', return_value=''):
                result = self.client_post('http://testserver:9080/accounts/login/sso/',
                                          REMOTE_USER=email)
                self.assertEqual(result.status_code, 200)
                self.assertIs(get_session_dict_user(self.client.session), None)
                self.assert_in_response("No account found for", result)

    def test_login_success_under_subdomains(self) -> None:
        user_profile = self.example_user('hamlet')
        email = user_profile.email
        with mock.patch('zerver.views.auth.get_subdomain', return_value='zulip'):
            with self.settings(
                    AUTHENTICATION_BACKENDS=('zproject.backends.ZulipRemoteUserBackend',)):
                result = self.client_post('/accounts/login/sso/', REMOTE_USER=email)
                self.assertEqual(result.status_code, 302)
                self.assertIs(get_session_dict_user(self.client.session), user_profile.id)

    @override_settings(SEND_LOGIN_EMAILS=True)
    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipRemoteUserBackend',))
    def test_login_mobile_flow_otp_success(self) -> None:
        user_profile = self.example_user('hamlet')
        email = user_profile.email
        mobile_flow_otp = '1234abcd' * 8
        # Verify that the right thing happens with an invalid-format OTP

        result = self.client_post('/accounts/login/sso/',
                                  dict(mobile_flow_otp="1234"),
                                  REMOTE_USER=email,
                                  HTTP_USER_AGENT = "ZulipAndroid")
        self.assertIs(get_session_dict_user(self.client.session), None)
        self.assert_json_error_contains(result, "Invalid OTP", 400)

        result = self.client_post('/accounts/login/sso/',
                                  dict(mobile_flow_otp="invalido" * 8),
                                  REMOTE_USER=email,
                                  HTTP_USER_AGENT = "ZulipAndroid")
        self.assertIs(get_session_dict_user(self.client.session), None)
        self.assert_json_error_contains(result, "Invalid OTP", 400)

        result = self.client_post('/accounts/login/sso/',
                                  dict(mobile_flow_otp=mobile_flow_otp),
                                  REMOTE_USER=email,
                                  HTTP_USER_AGENT = "ZulipAndroid")
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

    def test_redirect_to(self) -> None:
        def test_with_redirect_to_param_set_as_next(next: Text='') -> HttpResponse:
            user_profile = self.example_user('hamlet')
            email = user_profile.email
            with self.settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipRemoteUserBackend',)):
                result = self.client_post('/accounts/login/sso/?next=' + next, REMOTE_USER=email)
            return result

        res = test_with_redirect_to_param_set_as_next()
        self.assertEqual('http://zulip.testserver', res.url)
        res = test_with_redirect_to_param_set_as_next('/user_uploads/image_path')
        self.assertEqual('http://zulip.testserver/user_uploads/image_path', res.url)

        # In SSO based auth we never make browser send the hash to the backend.
        # Rather we depend upon the browser's behaviour of persisting hash anchors
        # in between redirect requests. See below stackoverflow conversation
        # https://stackoverflow.com/questions/5283395/url-hash-is-persisting-between-redirects
        res = test_with_redirect_to_param_set_as_next('#narrow/stream/7-test-here')
        self.assertEqual('http://zulip.testserver', res.url)

class TestJWTLogin(ZulipTestCase):
    """
    JWT uses ZulipDummyBackend.
    """

    def test_login_success(self) -> None:
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

    def test_login_failure_when_user_is_missing(self) -> None:
        payload = {'realm': 'zulip.com'}
        with self.settings(JWT_AUTH_KEYS={'zulip': 'key'}):
            auth_key = settings.JWT_AUTH_KEYS['zulip']
            web_token = jwt.encode(payload, auth_key).decode('utf8')
            data = {'json_web_token': web_token}
            result = self.client_post('/accounts/login/jwt/', data)
            self.assert_json_error_contains(result, "No user specified in JSON web token claims", 400)

    def test_login_failure_when_realm_is_missing(self) -> None:
        payload = {'user': 'hamlet'}
        with self.settings(JWT_AUTH_KEYS={'zulip': 'key'}):
            auth_key = settings.JWT_AUTH_KEYS['zulip']
            web_token = jwt.encode(payload, auth_key).decode('utf8')
            data = {'json_web_token': web_token}
            result = self.client_post('/accounts/login/jwt/', data)
            self.assert_json_error_contains(result, "No organization specified in JSON web token claims", 400)

    def test_login_failure_when_key_does_not_exist(self) -> None:
        data = {'json_web_token': 'not relevant'}
        result = self.client_post('/accounts/login/jwt/', data)
        self.assert_json_error_contains(result, "Auth key for this subdomain not found.", 400)

    def test_login_failure_when_key_is_missing(self) -> None:
        with self.settings(JWT_AUTH_KEYS={'zulip': 'key'}):
            result = self.client_post('/accounts/login/jwt/')
            self.assert_json_error_contains(result, "No JSON web token passed in request", 400)

    def test_login_failure_when_bad_token_is_passed(self) -> None:
        with self.settings(JWT_AUTH_KEYS={'zulip': 'key'}):
            result = self.client_post('/accounts/login/jwt/')
            self.assert_json_error_contains(result, "No JSON web token passed in request", 400)
            data = {'json_web_token': 'bad token'}
            result = self.client_post('/accounts/login/jwt/', data)
            self.assert_json_error_contains(result, "Bad JSON web token", 400)

    def test_login_failure_when_user_does_not_exist(self) -> None:
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

    def test_login_failure_due_to_wrong_subdomain(self) -> None:
        payload = {'user': 'hamlet', 'realm': 'zulip.com'}
        with self.settings(JWT_AUTH_KEYS={'acme': 'key'}):
            with mock.patch('zerver.views.auth.get_subdomain', return_value='acme'), \
                    mock.patch('logging.warning'):
                auth_key = settings.JWT_AUTH_KEYS['acme']
                web_token = jwt.encode(payload, auth_key).decode('utf8')

                data = {'json_web_token': web_token}
                result = self.client_post('/accounts/login/jwt/', data)
                self.assert_json_error_contains(result, "Wrong subdomain", 400)
                self.assertEqual(get_session_dict_user(self.client.session), None)

    def test_login_failure_due_to_empty_subdomain(self) -> None:
        payload = {'user': 'hamlet', 'realm': 'zulip.com'}
        with self.settings(JWT_AUTH_KEYS={'': 'key'}):
            with mock.patch('zerver.views.auth.get_subdomain', return_value=''), \
                    mock.patch('logging.warning'):
                auth_key = settings.JWT_AUTH_KEYS['']
                web_token = jwt.encode(payload, auth_key).decode('utf8')

                data = {'json_web_token': web_token}
                result = self.client_post('/accounts/login/jwt/', data)
                self.assert_json_error_contains(result, "Wrong subdomain", 400)
                self.assertEqual(get_session_dict_user(self.client.session), None)

    def test_login_success_under_subdomains(self) -> None:
        payload = {'user': 'hamlet', 'realm': 'zulip.com'}
        with self.settings(JWT_AUTH_KEYS={'zulip': 'key'}):
            with mock.patch('zerver.views.auth.get_subdomain', return_value='zulip'):
                auth_key = settings.JWT_AUTH_KEYS['zulip']
                web_token = jwt.encode(payload, auth_key).decode('utf8')

                data = {'json_web_token': web_token}
                result = self.client_post('/accounts/login/jwt/', data)
                self.assertEqual(result.status_code, 302)
                user_profile = self.example_user('hamlet')
                self.assertEqual(get_session_dict_user(self.client.session), user_profile.id)

class TestLDAP(ZulipTestCase):
    def setUp(self) -> None:
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

    def tearDown(self) -> None:
        self.mock_ldap.reset()
        self.mock_initialize.stop()

    def setup_subdomain(self, user_profile: UserProfile) -> None:
        realm = user_profile.realm
        realm.string_id = 'zulip'
        realm.save()

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_login_success(self) -> None:
        self.mock_ldap.directory = {
            'uid=hamlet,ou=users,dc=zulip,dc=com': {
                'userPassword': 'testing'
            }
        }
        with self.settings(
                LDAP_APPEND_DOMAIN='zulip.com',
                AUTH_LDAP_BIND_PASSWORD='',
                AUTH_LDAP_USER_DN_TEMPLATE='uid=%(user)s,ou=users,dc=zulip,dc=com'):
            user_profile = self.backend.authenticate(self.example_email("hamlet"), 'testing',
                                                     realm=get_realm('zulip'))

            assert(user_profile is not None)
            self.assertEqual(user_profile.email, self.example_email("hamlet"))

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_login_success_with_email_attr(self) -> None:
        self.mock_ldap.directory = {
            'uid=letham,ou=users,dc=zulip,dc=com': {
                'userPassword': 'testing',
                'email': ['hamlet@zulip.com'],
            }
        }
        with self.settings(LDAP_EMAIL_ATTR='email',
                           AUTH_LDAP_BIND_PASSWORD='',
                           AUTH_LDAP_USER_DN_TEMPLATE='uid=%(user)s,ou=users,dc=zulip,dc=com'):
            user_profile = self.backend.authenticate("letham", 'testing',
                                                     realm=get_realm('zulip'))

            assert (user_profile is not None)
            self.assertEqual(user_profile.email, self.example_email("hamlet"))

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_login_failure_due_to_wrong_password(self) -> None:
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
    def test_login_failure_due_to_nonexistent_user(self) -> None:
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
    def test_ldap_permissions(self) -> None:
        backend = self.backend
        self.assertFalse(backend.has_perm(None, None))
        self.assertFalse(backend.has_module_perms(None, None))
        self.assertTrue(backend.get_all_permissions(None, None) == set())
        self.assertTrue(backend.get_group_permissions(None, None) == set())

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_django_to_ldap_username(self) -> None:
        backend = self.backend
        with self.settings(LDAP_APPEND_DOMAIN='zulip.com'):
            username = backend.django_to_ldap_username('"hamlet@test"@zulip.com')
            self.assertEqual(username, '"hamlet@test"')

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_ldap_to_django_username(self) -> None:
        backend = self.backend
        with self.settings(LDAP_APPEND_DOMAIN='zulip.com'):
            username = backend.ldap_to_django_username('"hamlet@test"')
            self.assertEqual(username, '"hamlet@test"@zulip.com')

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_get_or_create_user_when_user_exists(self) -> None:
        class _LDAPUser:
            attrs = {'fn': ['Full Name'], 'sn': ['Short Name']}

        backend = self.backend
        email = self.example_email("hamlet")
        user_profile, created = backend.get_or_create_user(str(email), _LDAPUser())
        self.assertFalse(created)
        self.assertEqual(user_profile.email, email)

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_get_or_create_user_when_user_does_not_exist(self) -> None:
        class _LDAPUser:
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
    def test_get_or_create_user_when_user_has_invalid_name(self) -> None:
        class _LDAPUser:
            attrs = {'fn': ['<invalid name>'], 'sn': ['Short Name']}

        ldap_user_attr_map = {'full_name': 'fn', 'short_name': 'sn'}

        with self.settings(AUTH_LDAP_USER_ATTR_MAP=ldap_user_attr_map):
            backend = self.backend
            email = 'nonexisting@zulip.com'
            with self.assertRaisesRegex(Exception, "Invalid characters in name!"):
                backend.get_or_create_user(email, _LDAPUser())

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_get_or_create_user_when_realm_is_deactivated(self) -> None:
        class _LDAPUser:
            attrs = {'fn': ['Full Name'], 'sn': ['Short Name']}

        ldap_user_attr_map = {'full_name': 'fn', 'short_name': 'sn'}

        with self.settings(AUTH_LDAP_USER_ATTR_MAP=ldap_user_attr_map):
            backend = self.backend
            email = 'nonexisting@zulip.com'
            do_deactivate_realm(backend._realm)
            with self.assertRaisesRegex(Exception, 'Realm has been deactivated'):
                backend.get_or_create_user(email, _LDAPUser())

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_get_or_create_user_when_ldap_has_no_email_attr(self) -> None:
        class _LDAPUser:
            attrs = {'fn': ['Full Name'], 'sn': ['Short Name']}

        nonexisting_attr = 'email'
        with self.settings(LDAP_EMAIL_ATTR=nonexisting_attr):
            backend = self.backend
            email = 'nonexisting@zulip.com'
            with self.assertRaisesRegex(Exception, 'LDAP user doesn\'t have the needed email attribute'):
                backend.get_or_create_user(email, _LDAPUser())

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_django_to_ldap_username_when_domain_does_not_match(self) -> None:
        backend = self.backend
        email = self.example_email("hamlet")
        with self.assertRaisesRegex(Exception, 'Username does not match LDAP domain.'):
            with self.settings(LDAP_APPEND_DOMAIN='acme.com'):
                backend.django_to_ldap_username(email)

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_login_failure_when_domain_does_not_match(self) -> None:
        with self.settings(LDAP_APPEND_DOMAIN='acme.com'):
            user_profile = self.backend.authenticate(self.example_email("hamlet"), 'pass')
            self.assertIs(user_profile, None)

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_login_failure_due_to_wrong_subdomain(self) -> None:
        self.mock_ldap.directory = {
            'uid=hamlet,ou=users,dc=zulip,dc=com': {
                'userPassword': 'testing'
            }
        }
        with self.settings(
                LDAP_APPEND_DOMAIN='zulip.com',
                AUTH_LDAP_BIND_PASSWORD='',
                AUTH_LDAP_USER_DN_TEMPLATE='uid=%(user)s,ou=users,dc=zulip,dc=com'):
            user_profile = self.backend.authenticate(self.example_email("hamlet"), 'testing',
                                                     realm=get_realm('zephyr'))
            self.assertIs(user_profile, None)

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_login_failure_due_to_invalid_subdomain(self) -> None:
        self.mock_ldap.directory = {
            'uid=hamlet,ou=users,dc=zulip,dc=com': {
                'userPassword': 'testing'
            }
        }
        with self.settings(
                LDAP_APPEND_DOMAIN='zulip.com',
                AUTH_LDAP_BIND_PASSWORD='',
                AUTH_LDAP_USER_DN_TEMPLATE='uid=%(user)s,ou=users,dc=zulip,dc=com'):
            user_profile = self.backend.authenticate(self.example_email("hamlet"), 'testing',
                                                     realm=None)
            self.assertIs(user_profile, None)

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_login_success_with_valid_subdomain(self) -> None:
        self.mock_ldap.directory = {
            'uid=hamlet,ou=users,dc=zulip,dc=com': {
                'userPassword': 'testing'
            }
        }
        with self.settings(
                LDAP_APPEND_DOMAIN='zulip.com',
                AUTH_LDAP_BIND_PASSWORD='',
                AUTH_LDAP_USER_DN_TEMPLATE='uid=%(user)s,ou=users,dc=zulip,dc=com'):
            user_profile = self.backend.authenticate(self.example_email("hamlet"), 'testing',
                                                     realm=get_realm('zulip'))
            assert(user_profile is not None)
            self.assertEqual(user_profile.email, self.example_email("hamlet"))

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_login_failure_due_to_deactivated_user(self) -> None:
        self.mock_ldap.directory = {
            'uid=hamlet,ou=users,dc=zulip,dc=com': {
                'userPassword': 'testing'
            }
        }
        user_profile = self.example_user("hamlet")
        do_deactivate_user(user_profile)
        with self.settings(
                LDAP_APPEND_DOMAIN='zulip.com',
                AUTH_LDAP_BIND_PASSWORD='',
                AUTH_LDAP_USER_DN_TEMPLATE='uid=%(user)s,ou=users,dc=zulip,dc=com'):
            user_profile = self.backend.authenticate(self.example_email("hamlet"), 'testing',
                                                     realm=get_realm('zulip'))
            self.assertIs(user_profile, None)

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_login_success_when_user_does_not_exist_with_valid_subdomain(
            self) -> None:
        self.mock_ldap.directory = {
            'uid=nonexisting,ou=users,dc=acme,dc=com': {
                'cn': ['NonExisting', ],
                'userPassword': 'testing'
            }
        }
        with self.settings(
                LDAP_APPEND_DOMAIN='acme.com',
                AUTH_LDAP_BIND_PASSWORD='',
                AUTH_LDAP_USER_DN_TEMPLATE='uid=%(user)s,ou=users,dc=acme,dc=com'):
            user_profile = self.backend.authenticate('nonexisting@acme.com', 'testing',
                                                     realm=get_realm('zulip'))
            assert(user_profile is not None)
            self.assertEqual(user_profile.email, 'nonexisting@acme.com')
            self.assertEqual(user_profile.full_name, 'NonExisting')
            self.assertEqual(user_profile.realm.string_id, 'zulip')

class TestZulipLDAPUserPopulator(ZulipTestCase):
    def test_authenticate(self) -> None:
        backend = ZulipLDAPUserPopulator()
        result = backend.authenticate(self.example_email("hamlet"), 'testing')  # type: ignore # complains that the function does not return any value!
        self.assertIs(result, None)

class TestZulipAuthMixin(ZulipTestCase):
    def test_get_user(self) -> None:
        backend = ZulipAuthMixin()
        result = backend.get_user(11111)
        self.assertIs(result, None)

class TestPasswordAuthEnabled(ZulipTestCase):
    def test_password_auth_enabled_for_ldap(self) -> None:
        with self.settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',)):
            realm = Realm.objects.get(string_id='zulip')
            self.assertTrue(password_auth_enabled(realm))

class TestRequireEmailFormatUsernames(ZulipTestCase):
    def test_require_email_format_usernames_for_ldap_with_append_domain(
            self) -> None:
        with self.settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',),
                           LDAP_APPEND_DOMAIN="zulip.com"):
            realm = Realm.objects.get(string_id='zulip')
            self.assertFalse(require_email_format_usernames(realm))

    def test_require_email_format_usernames_for_ldap_with_email_attr(
            self) -> None:
        with self.settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',),
                           LDAP_EMAIL_ATTR="email"):
            realm = Realm.objects.get(string_id='zulip')
            self.assertFalse(require_email_format_usernames(realm))

    def test_require_email_format_usernames_for_email_only(self) -> None:
        with self.settings(AUTHENTICATION_BACKENDS=('zproject.backends.EmailAuthBackend',)):
            realm = Realm.objects.get(string_id='zulip')
            self.assertTrue(require_email_format_usernames(realm))

    def test_require_email_format_usernames_for_email_and_ldap_with_email_attr(
            self) -> None:
        with self.settings(AUTHENTICATION_BACKENDS=('zproject.backends.EmailAuthBackend',
                                                    'zproject.backends.ZulipLDAPAuthBackend'),
                           LDAP_EMAIL_ATTR="email"):
            realm = Realm.objects.get(string_id='zulip')
            self.assertFalse(require_email_format_usernames(realm))

    def test_require_email_format_usernames_for_email_and_ldap_with_append_email(
            self) -> None:
        with self.settings(AUTHENTICATION_BACKENDS=('zproject.backends.EmailAuthBackend',
                                                    'zproject.backends.ZulipLDAPAuthBackend'),
                           LDAP_APPEND_DOMAIN="zulip.com"):
            realm = Realm.objects.get(string_id='zulip')
            self.assertFalse(require_email_format_usernames(realm))

class TestMaybeSendToRegistration(ZulipTestCase):
    def test_sso_only_when_preregistration_user_does_not_exist(self) -> None:
        rf = RequestFactory()
        request = rf.get('/')
        request.session = {}
        request.user = None

        # Creating a mock Django form in order to keep the test simple.
        # This form will be returned by the create_hompage_form function
        # and will always be valid so that the code that we want to test
        # actually runs.
        class Form:
            def is_valid(self) -> bool:
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

    def test_sso_only_when_preregistration_user_exists(self) -> None:
        rf = RequestFactory()
        request = rf.get('/')
        request.session = {}
        request.user = None

        # Creating a mock Django form in order to keep the test simple.
        # This form will be returned by the create_hompage_form function
        # and will always be valid so that the code that we want to test
        # actually runs.
        class Form:
            def is_valid(self) -> bool:
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

    def test_change_enabled_backends(self) -> None:
        # Log in as admin
        self.login(self.example_email("iago"))
        result = self.client_patch("/json/realm", {
            'authentication_methods': ujson.dumps({u'Email': False, u'Dev': True})})
        self.assert_json_success(result)
        realm = get_realm('zulip')
        self.assertFalse(password_auth_enabled(realm))
        self.assertTrue(dev_auth_enabled(realm))

    def test_disable_all_backends(self) -> None:
        # Log in as admin
        self.login(self.example_email("iago"))
        result = self.client_patch("/json/realm", {
            'authentication_methods': ujson.dumps({u'Email': False, u'Dev': False})})
        self.assert_json_error(result, 'At least one authentication method must be enabled.')
        realm = get_realm('zulip')
        self.assertTrue(password_auth_enabled(realm))
        self.assertTrue(dev_auth_enabled(realm))

    def test_supported_backends_only_updated(self) -> None:
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
    def test_valid_email(self) -> None:
        validate_login_email(self.example_email("hamlet"))

    def test_invalid_email(self) -> None:
        with self.assertRaises(JsonableError):
            validate_login_email(u'hamlet')

class LoginOrRegisterRemoteUserTestCase(ZulipTestCase):
    def test_invalid_subdomain(self) -> None:
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

    def test_redirect_to(self) -> None:
        def test_with_redirect_to_param_set_as_next(next: Text='') -> HttpResponse:
            full_name = 'Hamlet'
            user_profile = self.example_user('hamlet')
            request = HostRequestMock(user_profile)
            with mock.patch('zerver.views.auth.do_login'):
                response = login_or_register_remote_user(
                    request,
                    self.example_email('hamlet'),
                    user_profile,
                    full_name=full_name,
                    invalid_subdomain=False,
                    redirect_to=next)
            return response

        res = test_with_redirect_to_param_set_as_next()
        self.assertEqual('http://zulip.testserver', res.url)
        res = test_with_redirect_to_param_set_as_next('/user_uploads/image_path')
        self.assertEqual('http://zulip.testserver/user_uploads/image_path', res.url)
        # We test with a rogue next URL and redirect URL must be towards root zulip uri.
        res = test_with_redirect_to_param_set_as_next('https://rogue.zulip-like.server/login')
        self.assertEqual('http://zulip.testserver', res.url)

class LDAPBackendTest(ZulipTestCase):
    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_non_existing_realm(self) -> None:
        email = self.example_email('hamlet')
        data = {'username': email, 'password': initial_password(email)}
        error_type = ZulipLDAPAuthBackend.REALM_IS_NONE_ERROR
        error = ZulipLDAPConfigurationError('Realm is None', error_type)
        with mock.patch('zproject.backends.ZulipLDAPAuthBackend.get_or_create_user',
                        side_effect=error), \
                mock.patch('django_auth_ldap.backend._LDAPUser._authenticate_user_dn'):
            response = self.client_post('/login/', data)
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, reverse('ldap_error_realm_is_none'))
            response = self.client_get(response.url)
            self.assert_in_response('You are trying to login using LDAP '
                                    'without creating an',
                                    response)
