# -*- coding: utf-8 -*-
from django.conf import settings
from django.http import HttpResponse
from django.test import TestCase, override_settings
from django_auth_ldap.backend import _LDAPUser
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
from zerver.lib.actions import do_deactivate_realm, do_deactivate_user, \
    do_reactivate_realm, do_reactivate_user, do_set_realm_authentication_methods
from zerver.lib.initial_password import initial_password
from zerver.lib.sessions import get_session_dict_user
from zerver.lib.test_classes import (
    ZulipTestCase,
)
from zerver.models import \
    get_realm, get_user_profile_by_email, email_to_username, UserProfile, \
    PreregistrationUser, Realm

from confirmation.models import Confirmation

from zproject.backends import ZulipDummyBackend, EmailAuthBackend, \
    GoogleMobileOauth2Backend, ZulipRemoteUserBackend, ZulipLDAPAuthBackend, \
    ZulipLDAPUserPopulator, DevAuthBackend, GitHubAuthBackend, ZulipAuthMixin, \
    dev_auth_enabled, password_auth_enabled, github_auth_enabled, \
    SocialAuthMixin, AUTH_BACKEND_NAME_MAP

from zerver.views.auth import maybe_send_to_registration
from version import ZULIP_VERSION

from social_core.exceptions import AuthFailed, AuthStateForbidden
from social_django.strategy import DjangoStrategy
from social_django.storage import BaseDjangoStorage
from social_core.backends.github import GithubOrganizationOAuth2, GithubTeamOAuth2, \
    GithubOAuth2

from six.moves import urllib
from six.moves.http_cookies import SimpleCookie
import ujson
from zerver.lib.test_helpers import MockLDAP

class AuthBackendTest(TestCase):
    def verify_backend(self, backend, good_args=None,
                       good_kwargs=None, bad_kwargs=None,
                       email_to_username=None):
        # type: (Any, List[Any], Dict[str, Any], Dict[str, Any], Callable[[Text], Text]) -> None
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

        # ZulipDummyBackend isn't a real backend so the remainder
        # doesn't make sense for it
        if isinstance(backend, ZulipDummyBackend):
            return

        # Verify auth fails if the auth backend is disabled on server
        with self.settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipDummyBackend',)):
            self.assertIsNone(backend.authenticate(username, *good_args, **good_kwargs))

        # Verify auth fails if the auth backend is disabled for the realm
        for backend_name in AUTH_BACKEND_NAME_MAP.keys():
            if isinstance(backend, AUTH_BACKEND_NAME_MAP[backend_name]):
                break

        index = getattr(user_profile.realm.authentication_methods, backend_name).number
        user_profile.realm.authentication_methods.set_bit(index, False)
        user_profile.realm.save()
        self.assertIsNone(backend.authenticate(username, *good_args, **good_kwargs))
        user_profile.realm.authentication_methods.set_bit(index, True)
        user_profile.realm.save()

    def test_dummy_backend(self):
        # type: () -> None
        self.verify_backend(ZulipDummyBackend(),
                            good_kwargs=dict(use_dummy_backend=True),
                            bad_kwargs=dict(use_dummy_backend=False))

    def setup_subdomain(self, user_profile):
        # type: (UserProfile) -> None
        realm = user_profile.realm
        realm.string_id = 'zulip'
        realm.save()

    def test_email_auth_backend(self):
        # type: () -> None
        email = "hamlet@zulip.com"
        user_profile = get_user_profile_by_email(email)
        password = "testpassword"
        user_profile.set_password(password)
        user_profile.save()
        self.setup_subdomain(user_profile)

        self.verify_backend(EmailAuthBackend(),
                            bad_kwargs=dict(password=''),
                            good_kwargs=dict(password=password))

        # Subdomain is ignored when feature is not enabled
        self.verify_backend(EmailAuthBackend(),
                            good_kwargs=dict(password=password,
                                             realm_subdomain='acme',
                                             return_data=dict()))

        with self.settings(REALMS_HAVE_SUBDOMAINS=True):
            # With subdomains, authenticating with the right subdomain
            # works; using the wrong subdomain doesn't
            self.verify_backend(EmailAuthBackend(),
                                good_kwargs=dict(password=password,
                                                 realm_subdomain='zulip',
                                                 return_data=dict()),
                                bad_kwargs=dict(password=password,
                                                realm_subdomain='acme',
                                                return_data=dict()))
            # Things work normally in the event that we're using a
            # non-subdomain login page, even if subdomains are enabled
            self.verify_backend(EmailAuthBackend(),
                                bad_kwargs=dict(password="wrong"),
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

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.GoogleMobileOauth2Backend',))
    def test_google_backend(self):
        # type: () -> None
        email = "hamlet@zulip.com"
        backend = GoogleMobileOauth2Backend()
        payload = dict(email_verified=True,
                       email=email)
        user_profile = get_user_profile_by_email(email)
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
        with mock.patch('apiclient.sample_tools.client.verify_id_token',
                        side_effect=AppIdentityError):
            ret = dict()
            result = backend.authenticate(return_data=ret)
            self.assertIsNone(result)

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_ldap_backend(self):
        # type: () -> None
        email = "hamlet@zulip.com"
        password = "test_password"
        user_profile = get_user_profile_by_email(email)
        self.setup_subdomain(user_profile)

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
            self.verify_backend(backend, good_kwargs=dict(password=password))

        with mock.patch('django_auth_ldap.backend._LDAPUser._authenticate_user_dn'), (
            mock.patch('django_auth_ldap.backend._LDAPUser._check_requirements')), (
            mock.patch('django_auth_ldap.backend._LDAPUser._get_user_attrs',
                       return_value=dict(full_name=['Hamlet']))):
            self.verify_backend(backend, good_kwargs=dict(password=password,
                                                          realm_subdomain='acme'))

        with self.settings(REALMS_HAVE_SUBDOMAINS=True):
            # With subdomains, authenticating with the right subdomain
            # works; using the wrong subdomain doesn't
            with mock.patch('django_auth_ldap.backend._LDAPUser._authenticate_user_dn'), (
                mock.patch('django_auth_ldap.backend._LDAPUser._check_requirements')), (
                mock.patch('django_auth_ldap.backend._LDAPUser._get_user_attrs',
                           return_value=dict(full_name=['Hamlet']))):
                self.verify_backend(backend,
                                    bad_kwargs=dict(password=password,
                                                    realm_subdomain='acme'),
                                    good_kwargs=dict(password=password,
                                                     realm_subdomain='zulip'))

    def test_devauth_backend(self):
        # type: () -> None
        self.verify_backend(DevAuthBackend())

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipRemoteUserBackend',))
    def test_remote_user_backend(self):
        # type: () -> None
        self.setup_subdomain(get_user_profile_by_email(u'hamlet@zulip.com'))
        self.verify_backend(ZulipRemoteUserBackend(),
                            good_kwargs=dict(realm_subdomain='acme'))

        with self.settings(REALMS_HAVE_SUBDOMAINS=True):
            # With subdomains, authenticating with the right subdomain
            # works; using the wrong subdomain doesn't
            self.verify_backend(ZulipRemoteUserBackend(),
                                good_kwargs=dict(realm_subdomain='zulip'),
                                bad_kwargs=dict(realm_subdomain='acme'))

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipRemoteUserBackend',))
    def test_remote_user_backend_sso_append_domain(self):
        # type: () -> None
        self.setup_subdomain(get_user_profile_by_email(u'hamlet@zulip.com'))
        with self.settings(SSO_APPEND_DOMAIN='zulip.com'):
            self.verify_backend(ZulipRemoteUserBackend(),
                                email_to_username=email_to_username,
                                good_kwargs=dict(realm_subdomain='acme'))

        with self.settings(REALMS_HAVE_SUBDOMAINS=True):
            # With subdomains, authenticating with the right subdomain
            # works; using the wrong subdomain doesn't
            with self.settings(SSO_APPEND_DOMAIN='zulip.com'):
                self.verify_backend(ZulipRemoteUserBackend(),
                                    email_to_username=email_to_username,
                                    good_kwargs=dict(realm_subdomain='zulip'),
                                    bad_kwargs=dict(realm_subdomain='acme'))

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.GitHubAuthBackend',))
    def test_github_backend(self):
        # type: () -> None
        email = 'hamlet@zulip.com'
        self.setup_subdomain(get_user_profile_by_email(email))
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
        self.email = 'hamlet@zulip.com'
        self.name = 'Hamlet'
        self.backend = GitHubAuthBackend()
        self.backend.strategy = DjangoStrategy(storage=BaseDjangoStorage())
        self.user_profile = get_user_profile_by_email(self.email)
        self.user_profile.backend = self.backend

        rf = RequestFactory()
        request = rf.get('/complete')
        request.session = {}
        request.get_host = lambda: 'acme.testserver'
        request.user = self.user_profile
        self.backend.strategy.request = request

    def do_auth(self, *args, **kwargs):
        # type: (*Any, **Any) -> UserProfile
        with self.settings(AUTHENTICATION_BACKENDS=('zproject.backends.GitHubAuthBackend',)):
            return self.backend.authenticate(*args, **kwargs)

    def test_github_auth_enabled(self):
        # type: () -> None
        with self.settings(AUTHENTICATION_BACKENDS=('zproject.backends.GitHubAuthBackend',)):
            self.assertTrue(github_auth_enabled())

    def test_full_name_with_missing_key(self):
        # type: () -> None
        self.assertEqual(self.backend.get_full_name(), '')

    def test_github_backend_do_auth_without_subdomains(self):
        # type: () -> None
        with mock.patch('social_core.backends.github.GithubOAuth2.do_auth',
                        side_effect=self.do_auth), \
                mock.patch('zerver.views.auth.login'):
            response = dict(email=self.email, name=self.name)
            result = self.backend.do_auth(response=response)
            self.assertNotIn('subdomain=1', result.url)

    def test_github_backend_do_auth_with_non_existing_subdomain(self):
        # type: () -> None
        with mock.patch('social_core.backends.github.GithubOAuth2.do_auth',
                        side_effect=self.do_auth):
            with self.settings(REALMS_HAVE_SUBDOMAINS=True):
                self.backend.strategy.session_set('subdomain', 'test')
                response = dict(email=self.email, name=self.name)
                result = self.backend.do_auth(response=response)
                self.assertIn('subdomain=1', result.url)

    def test_github_backend_do_auth_with_subdomains(self):
        # type: () -> None
        with mock.patch('social_core.backends.github.GithubOAuth2.do_auth',
                        side_effect=self.do_auth):
            with self.settings(REALMS_HAVE_SUBDOMAINS=True):
                self.backend.strategy.session_set('subdomain', 'zulip')
                response = dict(email=self.email, name=self.name)
                result = self.backend.do_auth(response=response)
                self.assertEqual('http://zulip.testserver/accounts/login/subdomain/', result.url)

    def test_github_backend_do_auth_for_default(self):
        # type: () -> None
        with mock.patch('social_core.backends.github.GithubOAuth2.do_auth',
                        side_effect=self.do_auth), \
                mock.patch('zproject.backends.SocialAuthMixin.process_do_auth') as result:
            response = dict(email=self.email, name=self.name)
            self.backend.do_auth('fake-access-token', response=response)

            kwargs = {'realm_subdomain': 'acme',
                      'response': response,
                      'return_data': {}}
            result.assert_called_with(self.user_profile, 'fake-access-token', **kwargs)

    def test_github_backend_do_auth_for_team(self):
        # type: () -> None
        with mock.patch('social_core.backends.github.GithubTeamOAuth2.do_auth',
                        side_effect=self.do_auth), \
                mock.patch('zproject.backends.SocialAuthMixin.process_do_auth') as result:
            response = dict(email=self.email, name=self.name)
            with self.settings(SOCIAL_AUTH_GITHUB_TEAM_ID='zulip-webapp'):
                self.backend.do_auth('fake-access-token', response=response)

                kwargs = {'realm_subdomain': 'acme',
                          'response': response,
                          'return_data': {}}
                result.assert_called_with(self.user_profile, 'fake-access-token', **kwargs)

    def test_github_backend_do_auth_for_team_auth_failed(self):
        # type: () -> None
        with mock.patch('social_core.backends.github.GithubTeamOAuth2.do_auth',
                        side_effect=AuthFailed('Not found')), \
                mock.patch('logging.info'), \
                mock.patch('zproject.backends.SocialAuthMixin.process_do_auth') as result:
            response = dict(email=self.email, name=self.name)
            with self.settings(SOCIAL_AUTH_GITHUB_TEAM_ID='zulip-webapp'):
                self.backend.do_auth('fake-access-token', response=response)
                kwargs = {'realm_subdomain': 'acme',
                          'response': response,
                          'return_data': {}}
                result.assert_called_with(None, 'fake-access-token', **kwargs)

    def test_github_backend_do_auth_for_org(self):
        # type: () -> None
        with mock.patch('social_core.backends.github.GithubOrganizationOAuth2.do_auth',
                        side_effect=self.do_auth), \
                mock.patch('zproject.backends.SocialAuthMixin.process_do_auth') as result:
            response = dict(email=self.email, name=self.name)
            with self.settings(SOCIAL_AUTH_GITHUB_ORG_NAME='Zulip'):
                self.backend.do_auth('fake-access-token', response=response)

                kwargs = {'realm_subdomain': 'acme',
                          'response': response,
                          'return_data': {}}
                result.assert_called_with(self.user_profile, 'fake-access-token', **kwargs)

    def test_github_backend_do_auth_for_org_auth_failed(self):
        # type: () -> None
        with mock.patch('social_core.backends.github.GithubOrganizationOAuth2.do_auth',
                        side_effect=AuthFailed('Not found')), \
                mock.patch('logging.info'), \
                mock.patch('zproject.backends.SocialAuthMixin.process_do_auth') as result:
            response = dict(email=self.email, name=self.name)
            with self.settings(SOCIAL_AUTH_GITHUB_ORG_NAME='Zulip'):
                self.backend.do_auth('fake-access-token', response=response)
                kwargs = {'realm_subdomain': 'acme',
                          'response': response,
                          'return_data': {}}
                result.assert_called_with(None, 'fake-access-token', **kwargs)

    def test_github_backend_authenticate_nonexisting_user(self):
        # type: () -> None
        with mock.patch('zproject.backends.get_user_profile_by_email',
                        side_effect=UserProfile.DoesNotExist("Do not exist")):
            response = dict(email=self.email, name=self.name)
            return_data = dict() # type: Dict[str, Any]
            user = self.backend.authenticate(return_data=return_data, response=response)
            self.assertIs(user, None)
            self.assertTrue(return_data['valid_attestation'])

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

        with mock.patch('social_core.backends.github.GithubOAuth2.do_auth',
                        side_effect=do_auth):
            response = dict(email='nonexisting@phantom.com', name='Ghost')
            result = self.backend.do_auth(response=response)
            self.assert_in_response('action="/register/"', result)
            self.assert_in_response('Your email address does not correspond to any '
                                    'existing organization.', result)

    def test_login_url(self):
        # type: () -> None
        result = self.client_get('/accounts/login/social/github')
        self.assertIn(reverse('social:begin', args=['github']), result.url)

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
    def google_oauth2_test(self, token_response, account_response, subdomain=None):
        # type: (ResponseMock, ResponseMock, Optional[str]) -> HttpResponse
        url = "/accounts/login/google/send/"
        if subdomain is not None:
            url += "?subdomain=" + subdomain

        result = self.client_get(url)
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
                                     dict(state=csrf_state))
        return result

class GoogleSubdomainLoginTest(GoogleOAuthTest):
    def get_signed_subdomain_cookie(self, data):
        # type: (Dict[str, str]) -> Dict[str, str]
        key = 'subdomain.signature'
        salt = key + 'zerver.views.auth'
        value = ujson.dumps(data)
        return {key: signing.get_cookie_signer(salt=salt).sign(value)}

    def unsign_subdomain_cookie(self, result):
        # type: (HttpResponse) -> Dict[str, Any]
        key = 'subdomain.signature'
        salt = key + 'zerver.views.auth'
        cookie = result.cookies.get(key)
        value = signing.get_cookie_signer(salt=salt).unsign(cookie.value, max_age=15)
        return ujson.loads(value)

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
                                         value="hamlet@zulip.com")])
        account_response = ResponseMock(200, account_data)
        with self.settings(REALMS_HAVE_SUBDOMAINS=True):
            result = self.google_oauth2_test(token_response, account_response, 'zulip')

        data = self.unsign_subdomain_cookie(result)
        self.assertEqual(data['email'], 'hamlet@zulip.com')
        self.assertEqual(data['name'], 'Full Name')
        self.assertEqual(data['subdomain'], 'zulip')
        self.assertEqual(result.status_code, 302)
        parsed_url = urllib.parse.urlparse(result.url)
        uri = "{}://{}{}".format(parsed_url.scheme, parsed_url.netloc,
                                 parsed_url.path)
        self.assertEqual(uri, 'http://zulip.testserver/accounts/login/subdomain/')

    def test_log_into_subdomain(self):
        # type: () -> None
        data = {'name': 'Full Name',
                'email': 'hamlet@zulip.com',
                'subdomain': 'zulip'}

        self.client.cookies = SimpleCookie(self.get_signed_subdomain_cookie(data))
        with mock.patch('zerver.views.auth.get_subdomain', return_value='zulip'):
            result = self.client_get('/accounts/login/subdomain/')
            self.assertEqual(result.status_code, 302)
            user_profile = get_user_profile_by_email('hamlet@zulip.com')
            self.assertEqual(get_session_dict_user(self.client.session), user_profile.id)

    def test_user_cannot_log_into_nonexisting_realm(self):
        # type: () -> None
        token_response = ResponseMock(200, {'access_token': "unique_token"})
        account_data = dict(name=dict(formatted="Full Name"),
                            emails=[dict(type="account",
                                         value="hamlet@zulip.com")])
        account_response = ResponseMock(200, account_data)
        result = self.google_oauth2_test(token_response, account_response, 'acme')
        self.assertEqual(result.status_code, 302)
        self.assertIn('subdomain=1', result.url)

    def test_user_cannot_log_into_wrong_subdomain(self):
        # type: () -> None
        data = {'name': 'Full Name',
                'email': 'hamlet@zulip.com',
                'subdomain': 'acme'}

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
            token_response = ResponseMock(200, {'access_token': "unique_token"})
            account_data = dict(name=dict(formatted="Full Name"),
                                emails=[dict(type="account",
                                             value=email)])
            account_response = ResponseMock(200, account_data)
            result = self.google_oauth2_test(token_response, account_response, 'zulip')

            data = self.unsign_subdomain_cookie(result)
            self.assertEqual(data['email'], email)
            self.assertEqual(data['name'], 'Full Name')
            self.assertEqual(data['subdomain'], 'zulip')
            self.assertEqual(result.status_code, 302)
            parsed_url = urllib.parse.urlparse(result.url)
            uri = "{}://{}{}".format(parsed_url.scheme, parsed_url.netloc,
                                     parsed_url.path)
            self.assertEqual(uri, 'http://zulip.testserver/accounts/login/subdomain/')

            result = self.client_get(result.url)
            result = self.client_get(result.url)  # Call the confirmation url.
            key_match = re.search('value="(?P<key>[0-9a-f]+)" name="key"', result.content.decode("utf-8"))
            name_match = re.search('value="(?P<name>[^"]+)" name="full_name"', result.content.decode("utf-8"))

            # This goes through a brief stop on a page that auto-submits via JS
            result = self.client_post('/accounts/register/',
                                      {'full_name': name_match.group("name"),
                                       'key': key_match.group("key"),
                                       'from_confirmation': "1"})
            self.assertEqual(result.status_code, 200)
            result = self.client_post('/accounts/register/',
                                      {'full_name': "New User",
                                       'password': 'test_password',
                                       'key': key_match.group("key"),
                                       'terms': True})
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result.url, "http://zulip.testserver/")
            user_profile = get_user_profile_by_email(email)
            self.assertEqual(get_session_dict_user(self.client.session), user_profile.id)

class GoogleLoginTest(GoogleOAuthTest):
    def test_google_oauth2_success(self):
        # type: () -> None
        token_response = ResponseMock(200, {'access_token': "unique_token"})
        account_data = dict(name=dict(formatted="Full Name"),
                            emails=[dict(type="account",
                                         value="hamlet@zulip.com")])
        account_response = ResponseMock(200, account_data)
        self.google_oauth2_test(token_response, account_response)

        user_profile = get_user_profile_by_email('hamlet@zulip.com')
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
        result = self.google_oauth2_test(token_response, account_response)
        self.assertEqual(result.status_code, 302)

        result = self.client_get(result.url)
        key_match = re.search('value="(?P<key>[0-9a-f]+)" name="key"', result.content.decode("utf-8"))
        name_match = re.search('value="(?P<name>[^"]+)" name="full_name"', result.content.decode("utf-8"))

        # This goes through a brief stop on a page that auto-submits via JS
        result = self.client_post('/accounts/register/',
                                  {'full_name': name_match.group("name"),
                                   'key': key_match.group("key"),
                                   'from_confirmation': "1"})
        self.assertEqual(result.status_code, 200)
        result = self.client_post('/accounts/register/',
                                  {'full_name': "New User",
                                   'password': 'test_password',
                                   'key': key_match.group("key"),
                                   'terms': True})
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result.url, "http://testserver/")

    def test_google_oauth2_wrong_subdomain(self):
        # type: () -> None
        token_response = ResponseMock(200, {'access_token': "unique_token"})
        account_data = dict(name=dict(formatted="Full Name"),
                            emails=[dict(type="account",
                                         value="hamlet@zulip.com")])
        account_response = ResponseMock(200, account_data)
        with self.settings(REALMS_HAVE_SUBDOMAINS=True):
            result = self.google_oauth2_test(token_response, account_response)
            self.assertIn('subdomain=1', result.url)

    def test_google_oauth2_400_token_response(self):
        # type: () -> None
        token_response = ResponseMock(400, {})
        with mock.patch("logging.warning") as m:
            result = self.google_oauth2_test(token_response, None)
        self.assertEqual(result.status_code, 400)
        self.assertEqual(m.call_args_list[0][0][0],
                         "User error converting Google oauth2 login to token: Response text")

    def test_google_oauth2_500_token_response(self):
        # type: () -> None
        token_response = ResponseMock(500, {})
        with mock.patch("logging.error") as m:
            result = self.google_oauth2_test(token_response, None)
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

    def test_google_oauth2_no_fullname(self):
        # type: () -> None
        token_response = ResponseMock(200, {'access_token': "unique_token"})
        account_data = dict(name=dict(givenName="Test", familyName="User"),
                            emails=[dict(type="account",
                                         value="hamlet@zulip.com")])
        account_response = ResponseMock(200, account_data)
        self.google_oauth2_test(token_response, account_response)

        user_profile = get_user_profile_by_email('hamlet@zulip.com')
        self.assertEqual(get_session_dict_user(self.client.session), user_profile.id)

    def test_google_oauth2_account_response_no_email(self):
        # type: () -> None
        token_response = ResponseMock(200, {'access_token': "unique_token"})
        account_data = dict(name=dict(formatted="Full Name"),
                            emails=[])
        account_response = ResponseMock(200, account_data)
        with mock.patch("logging.error") as m:
            result = self.google_oauth2_test(token_response, account_response)
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
            result = self.client_get("/accounts/login/google/done/?state=badstate:otherbadstate:")
        self.assertEqual(result.status_code, 400)
        self.assertEqual(m.call_args_list[0][0][0],
                         'Google oauth2 CSRF error')

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
    def test_fetch_auth_backend_format(self):
        # type: () -> None
        result = self.client_get("/api/v1/get_auth_backends")
        self.assert_json_success(result)
        data = ujson.loads(result.content)
        self.assertEqual(set(data.keys()),
                         {'msg', 'password', 'google', 'dev', 'result', 'zulip_version'})
        for backend in set(data.keys()) - {'msg', 'result', 'zulip_version'}:
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
                'zulip_version': ZULIP_VERSION,
            })

            # Test subdomains cases
            with self.settings(REALMS_HAVE_SUBDOMAINS=True,
                               SUBDOMAINS_HOMEPAGE=False):
                result = self.client_get("/api/v1/get_auth_backends")
                self.assert_json_success(result)
                data = ujson.loads(result.content)
                self.assertEqual(data, {
                    'msg': '',
                    'password': False,
                    'google': True,
                    'dev': True,
                    'result': 'success',
                    'zulip_version': ZULIP_VERSION,
                })

                # Verify invalid subdomain
                result = self.client_get("/api/v1/get_auth_backends",
                                         HTTP_HOST="invalid.testserver")
                self.assert_json_error_contains(result, "Invalid subdomain", 400)

                # Verify correct behavior with a valid subdomain with
                # some backends disabled for the realm
                realm = get_realm("zulip")
                do_set_realm_authentication_methods(realm, dict(Google=False,
                                                                Email=False,
                                                                Dev=True))
                result = self.client_get("/api/v1/get_auth_backends",
                                         HTTP_HOST="zulip.testserver")
                self.assert_json_success(result)
                data = ujson.loads(result.content)
                self.assertEqual(data, {
                    'msg': '',
                    'password': False,
                    'google': False,
                    'dev': True,
                    'result': 'success',
                    'zulip_version': ZULIP_VERSION,
                })
            with self.settings(REALMS_HAVE_SUBDOMAINS=True,
                               SUBDOMAINS_HOMEPAGE=True):
                # With SUBDOMAINS_HOMEPAGE, homepage fails
                result = self.client_get("/api/v1/get_auth_backends",
                                         HTTP_HOST="testserver")
                self.assert_json_error_contains(result, "Subdomain required", 400)

                # With SUBDOMAINS_HOMEPAGE, subdomain pages succeed
                result = self.client_get("/api/v1/get_auth_backends",
                                         HTTP_HOST="zulip.testserver")
                self.assert_json_success(result)
                data = ujson.loads(result.content)
                self.assertEqual(data, {
                    'msg': '',
                    'password': False,
                    'google': False,
                    'dev': True,
                    'result': 'success',
                    'zulip_version': ZULIP_VERSION,
                })

class TestDevAuthBackend(ZulipTestCase):
    def test_login_success(self):
        # type: () -> None
        email = 'hamlet@zulip.com'
        user_profile = get_user_profile_by_email(email)
        data = {'direct_email': email}
        result = self.client_post('/accounts/login/local/', data)
        self.assertEqual(result.status_code, 302)
        self.assertEqual(get_session_dict_user(self.client.session), user_profile.id)

    def test_login_failure(self):
        # type: () -> None
        email = 'hamlet@zulip.com'
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
        email = 'hamlet@zulip.com'
        user_profile = get_user_profile_by_email(email)
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
        email = 'hamlet@zulip.com'
        user_profile = get_user_profile_by_email(email)
        with self.settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipRemoteUserBackend',),
                           SSO_APPEND_DOMAIN='zulip.com'):
            result = self.client_post('/accounts/login/sso/', REMOTE_USER=username)
            self.assertEqual(result.status_code, 302)
            self.assertEqual(get_session_dict_user(self.client.session), user_profile.id)

    def test_login_failure(self):
        # type: () -> None
        email = 'hamlet@zulip.com'
        result = self.client_post('/accounts/login/sso/', REMOTE_USER=email)
        self.assertEqual(result.status_code, 200) # This should ideally be not 200.
        self.assertIs(get_session_dict_user(self.client.session), None)

    def test_login_failure_due_to_nonexisting_user(self):
        # type: () -> None
        email = 'nonexisting@zulip.com'
        with self.settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipRemoteUserBackend',)):
            result = self.client_post('/accounts/login/sso/', REMOTE_USER=email)
            self.assertEqual(result.status_code, 302)
            self.assertIs(get_session_dict_user(self.client.session), None)

    def test_login_failure_due_to_missing_field(self):
        # type: () -> None
        with self.settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipRemoteUserBackend',)):
            result = self.client_post('/accounts/login/sso/')
            self.assert_json_error_contains(result, "No REMOTE_USER set.", 400)

    def test_login_failure_due_to_wrong_subdomain(self):
        # type: () -> None
        email = 'hamlet@zulip.com'
        with self.settings(REALMS_HAVE_SUBDOMAINS=True,
                           AUTHENTICATION_BACKENDS=('zproject.backends.ZulipRemoteUserBackend',)):
            with mock.patch('zerver.views.auth.get_subdomain', return_value='acme'):
                result = self.client_post('http://testserver:9080/accounts/login/sso/',
                                          REMOTE_USER=email)
                self.assertEqual(result.status_code, 200)
                self.assertIs(get_session_dict_user(self.client.session), None)
                self.assertIn(b"Let's get started", result.content)

    def test_login_failure_due_to_empty_subdomain(self):
        # type: () -> None
        email = 'hamlet@zulip.com'
        with self.settings(REALMS_HAVE_SUBDOMAINS=True,
                           AUTHENTICATION_BACKENDS=('zproject.backends.ZulipRemoteUserBackend',)):
            with mock.patch('zerver.views.auth.get_subdomain', return_value=''):
                result = self.client_post('http://testserver:9080/accounts/login/sso/',
                                          REMOTE_USER=email)
                self.assertEqual(result.status_code, 200)
                self.assertIs(get_session_dict_user(self.client.session), None)
                self.assertIn(b"Let's get started", result.content)

    def test_login_success_under_subdomains(self):
        # type: () -> None
        email = 'hamlet@zulip.com'
        user_profile = get_user_profile_by_email(email)
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
        with self.settings(JWT_AUTH_KEYS={'': 'key'}):
            email = 'hamlet@zulip.com'
            auth_key = settings.JWT_AUTH_KEYS['']
            web_token = jwt.encode(payload, auth_key).decode('utf8')

            user_profile = get_user_profile_by_email(email)
            data = {'json_web_token': web_token}
            result = self.client_post('/accounts/login/jwt/', data)
            self.assertEqual(result.status_code, 302)
            self.assertEqual(get_session_dict_user(self.client.session), user_profile.id)

    def test_login_failure_when_user_is_missing(self):
        # type: () -> None
        payload = {'realm': 'zulip.com'}
        with self.settings(JWT_AUTH_KEYS={'': 'key'}):
            auth_key = settings.JWT_AUTH_KEYS['']
            web_token = jwt.encode(payload, auth_key).decode('utf8')
            data = {'json_web_token': web_token}
            result = self.client_post('/accounts/login/jwt/', data)
            self.assert_json_error_contains(result, "No user specified in JSON web token claims", 400)

    def test_login_failure_when_realm_is_missing(self):
        # type: () -> None
        payload = {'user': 'hamlet'}
        with self.settings(JWT_AUTH_KEYS={'': 'key'}):
            auth_key = settings.JWT_AUTH_KEYS['']
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
        with self.settings(JWT_AUTH_KEYS={'': 'key'}):
            result = self.client_post('/accounts/login/jwt/')
            self.assert_json_error_contains(result, "No JSON web token passed in request", 400)

    def test_login_failure_when_bad_token_is_passed(self):
        # type: () -> None
        with self.settings(JWT_AUTH_KEYS={'': 'key'}):
            result = self.client_post('/accounts/login/jwt/')
            self.assert_json_error_contains(result, "No JSON web token passed in request", 400)
            data = {'json_web_token': 'bad token'}
            result = self.client_post('/accounts/login/jwt/', data)
            self.assert_json_error_contains(result, "Bad JSON web token", 400)

    def test_login_failure_when_user_does_not_exist(self):
        # type: () -> None
        payload = {'user': 'nonexisting', 'realm': 'zulip.com'}
        with self.settings(JWT_AUTH_KEYS={'': 'key'}):
            auth_key = settings.JWT_AUTH_KEYS['']
            web_token = jwt.encode(payload, auth_key).decode('utf8')
            data = {'json_web_token': web_token}
            result = self.client_post('/accounts/login/jwt/', data)
            self.assertEqual(result.status_code, 302) # This should ideally be not 200.
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
                email = 'hamlet@zulip.com'
                auth_key = settings.JWT_AUTH_KEYS['zulip']
                web_token = jwt.encode(payload, auth_key).decode('utf8')

                data = {'json_web_token': web_token}
                result = self.client_post('/accounts/login/jwt/', data)
                self.assertEqual(result.status_code, 302)
                user_profile = get_user_profile_by_email(email)
                self.assertEqual(get_session_dict_user(self.client.session), user_profile.id)

class TestLDAP(ZulipTestCase):
    def setUp(self):
        # type: () -> None
        email = "hamlet@zulip.com"
        user_profile = get_user_profile_by_email(email)
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
            user_profile = self.backend.authenticate('hamlet@zulip.com', 'testing')
            self.assertEqual(user_profile.email, 'hamlet@zulip.com')

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
                user = self.backend.authenticate('hamlet@zulip.com', 'wrong')
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
        email = 'hamlet@zulip.com'
        user_profile, created = backend.get_or_create_user(email, _LDAPUser())
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
    def test_django_to_ldap_username_when_domain_does_not_match(self):
        # type: () -> None
        backend = self.backend
        email = 'hamlet@zulip.com'
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
            user_profile = self.backend.authenticate('hamlet@zulip.com', 'testing',
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
            user_profile = self.backend.authenticate('hamlet@zulip.com', 'testing',
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
            user_profile = self.backend.authenticate('hamlet@zulip.com', 'testing',
                                                     realm_subdomain=None)
            self.assertEqual(user_profile.email, 'hamlet@zulip.com')

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
            user_profile = self.backend.authenticate('hamlet@zulip.com', 'testing',
                                                     realm_subdomain='zulip')
            self.assertEqual(user_profile.email, 'hamlet@zulip.com')

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
            self.assertEqual(user_profile.email, 'nonexisting@acme.com')
            self.assertEqual(user_profile.full_name, 'NonExisting')
            self.assertEqual(user_profile.realm.string_id, 'zulip')

class TestZulipLDAPUserPopulator(ZulipTestCase):
    def test_authenticate(self):
        # type: () -> None
        backend = ZulipLDAPUserPopulator()
        result = backend.authenticate('hamlet@zulip.com', 'testing')  # type: ignore # complains that the function does not return any value!
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
                result = maybe_send_to_registration(request, 'hamlet@zulip.com')
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

        email = 'hamlet@zulip.com'
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
        self.login("iago@zulip.com")
        result = self.client_patch("/json/realm", {
            'authentication_methods': ujson.dumps({u'Email': False, u'Dev': True})})
        self.assert_json_success(result)
        realm = get_realm('zulip')
        self.assertFalse(password_auth_enabled(realm))
        self.assertTrue(dev_auth_enabled(realm))

    def test_disable_all_backends(self):
        # type: () -> None
        # Log in as admin
        self.login("iago@zulip.com")
        result = self.client_patch("/json/realm", {
            'authentication_methods': ujson.dumps({u'Email': False, u'Dev': False})})
        self.assert_json_error(result, 'At least one authentication method must be enabled.', status_code=403)
        realm = get_realm('zulip')
        self.assertTrue(password_auth_enabled(realm))
        self.assertTrue(dev_auth_enabled(realm))

    def test_supported_backends_only_updated(self):
        # type: () -> None
        # Log in as admin
        self.login("iago@zulip.com")
        # Set some supported and unsupported backends
        result = self.client_patch("/json/realm", {
            'authentication_methods': ujson.dumps({u'Email': False, u'Dev': True, u'GitHub': False})})
        self.assert_json_success(result)
        realm = get_realm('zulip')
        # Check that unsupported backend is not enabled
        self.assertFalse(github_auth_enabled(realm))
        self.assertTrue(dev_auth_enabled(realm))
        self.assertFalse(password_auth_enabled(realm))
