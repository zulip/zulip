# -*- coding: utf-8 -*-
from django.conf import settings
from django.http import HttpResponse
from django.test import TestCase
from django_auth_ldap.backend import _LDAPUser
from django.test.client import RequestFactory
from typing import Any, Callable, Dict

import jwt
import mock
import re

from zerver.lib.actions import do_deactivate_realm, do_deactivate_user, \
    do_reactivate_realm, do_reactivate_user
from zerver.lib.initial_password import initial_password
from zerver.lib.session_user import get_session_dict_user
from zerver.lib.test_helpers import (
    ZulipTestCase
)
from zerver.models import \
    get_realm, get_user_profile_by_email, email_to_username, UserProfile

from zproject.backends import ZulipDummyBackend, EmailAuthBackend, \
    GoogleMobileOauth2Backend, ZulipRemoteUserBackend, ZulipLDAPAuthBackend, \
    ZulipLDAPUserPopulator, DevAuthBackend, GitHubAuthBackend

from social.exceptions import AuthFailed
from social.strategies.django_strategy import DjangoStrategy
from social.storage.django_orm import BaseDjangoStorage
from social.backends.github import GithubOrganizationOAuth2, GithubTeamOAuth2, \
    GithubOAuth2

from six import text_type
from six.moves import urllib
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

    def setup_subdomain(self, user_profile):
        # type: (UserProfile) -> None
        realm = user_profile.realm
        realm.subdomain = 'zulip'
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

    def test_ldap_backend(self):
        # type: () -> None
        email = "hamlet@zulip.com"
        password = "test_password"
        user_profile = get_user_profile_by_email(email)
        self.setup_subdomain(user_profile)

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

        with mock.patch('django_auth_ldap.backend._LDAPUser._authenticate_user_dn'), \
             mock.patch('django_auth_ldap.backend._LDAPUser._check_requirements'), \
             mock.patch('django_auth_ldap.backend._LDAPUser._get_user_attrs',
                        return_value=dict(full_name=['Hamlet'])):
            self.verify_backend(backend, good_kwargs=dict(password=password,
                                                          realm_subdomain='acme'))

        with self.settings(REALMS_HAVE_SUBDOMAINS=True):
            # With subdomains, authenticating with the right subdomain
            # works; using the wrong subdomain doesn't
            with mock.patch('django_auth_ldap.backend._LDAPUser._authenticate_user_dn'), \
                 mock.patch('django_auth_ldap.backend._LDAPUser._check_requirements'), \
                 mock.patch('django_auth_ldap.backend._LDAPUser._get_user_attrs',
                            return_value=dict(full_name=['Hamlet'])):
                self.verify_backend(backend,
                                    bad_kwargs=dict(password=password,
                                                    realm_subdomain='acme'),
                                    good_kwargs=dict(password=password,
                                                     realm_subdomain='zulip'))

    def test_devauth_backend(self):
        # type: () -> None
        self.verify_backend(DevAuthBackend())

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

    def test_github_backend_do_auth_without_subdomains(self):
        # type: () -> None
        def do_auth(*args, **kwargs):
            # type: (*Any, **Any) -> UserProfile
            return self.backend.authenticate(*args, **kwargs)

        with mock.patch('social.backends.github.GithubOAuth2.do_auth',
                        side_effect=do_auth), \
                mock.patch('zerver.views.auth.login'):
            response=dict(email=self.email, name=self.name)
            result = self.backend.do_auth(response=response)
            self.assertNotIn('subdomain=1', result.url)

    def test_github_backend_do_auth_with_subdomains(self):
        # type: () -> None
        def do_auth(*args, **kwargs):
            # type: (*Any, **Any) -> UserProfile
            return self.backend.authenticate(*args, **kwargs)

        with mock.patch('social.backends.github.GithubOAuth2.do_auth',
                        side_effect=do_auth):
            with self.settings(REALMS_HAVE_SUBDOMAINS=True):
                response=dict(email=self.email, name=self.name)
                result = self.backend.do_auth(response=response)
                self.assertIn('subdomain=1', result.url)

    def test_github_backend_do_auth_for_default(self):
        # type: () -> None
        def do_auth(*args, **kwargs):
            # type: (*Any, **Any) -> UserProfile
            return self.backend.authenticate(*args, **kwargs)

        with mock.patch('social.backends.github.GithubOAuth2.do_auth',
                        side_effect=do_auth), \
                mock.patch('zproject.backends.SocialAuthMixin.process_do_auth') as result:
            response=dict(email=self.email, name=self.name)
            self.backend.do_auth('fake-access-token', response=response)

            kwargs = {'realm_subdomain': 'acme',
                      'response': response,
                      'return_data': {}}
            result.assert_called_with(self.user_profile, 'fake-access-token', **kwargs)

    def test_github_backend_do_auth_for_team(self):
        # type: () -> None
        def do_auth(*args, **kwargs):
            # type: (*Any, **Any) -> UserProfile
            return self.backend.authenticate(*args, **kwargs)

        with mock.patch('social.backends.github.GithubTeamOAuth2.do_auth',
                        side_effect=do_auth), \
                mock.patch('zproject.backends.SocialAuthMixin.process_do_auth') as result:
            response=dict(email=self.email, name=self.name)
            with self.settings(SOCIAL_AUTH_GITHUB_TEAM_ID='zulip-webapp'):
                self.backend.do_auth('fake-access-token', response=response)

                kwargs = {'realm_subdomain': 'acme',
                          'response': response,
                          'return_data': {}}
                result.assert_called_with(self.user_profile, 'fake-access-token', **kwargs)

    def test_github_backend_do_auth_for_team_auth_failed(self):
        # type: () -> None
        with mock.patch('social.backends.github.GithubTeamOAuth2.do_auth',
                        side_effect=AuthFailed('Not found')), \
                mock.patch('logging.info'), \
                mock.patch('zproject.backends.SocialAuthMixin.process_do_auth') as result:
            response=dict(email=self.email, name=self.name)
            with self.settings(SOCIAL_AUTH_GITHUB_TEAM_ID='zulip-webapp'):
                self.backend.do_auth('fake-access-token', response=response)
                kwargs = {'realm_subdomain': 'acme',
                          'response': response,
                          'return_data': {}}
                result.assert_called_with(None, 'fake-access-token', **kwargs)

    def test_github_backend_do_auth_for_org(self):
        # type: () -> None
        def do_auth(*args, **kwargs):
            # type: (*Any, **Any) -> UserProfile
            return self.backend.authenticate(*args, **kwargs)

        with mock.patch('social.backends.github.GithubOrganizationOAuth2.do_auth',
                        side_effect=do_auth), \
                mock.patch('zproject.backends.SocialAuthMixin.process_do_auth') as result:
            response=dict(email=self.email, name=self.name)
            with self.settings(SOCIAL_AUTH_GITHUB_ORG_NAME='Zulip'):
                self.backend.do_auth('fake-access-token', response=response)

                kwargs = {'realm_subdomain': 'acme',
                          'response': response,
                          'return_data': {}}
                result.assert_called_with(self.user_profile, 'fake-access-token', **kwargs)

    def test_github_backend_do_auth_for_org_auth_failed(self):
        # type: () -> None
        with mock.patch('social.backends.github.GithubOrganizationOAuth2.do_auth',
                        side_effect=AuthFailed('Not found')), \
                mock.patch('logging.info'), \
                mock.patch('zproject.backends.SocialAuthMixin.process_do_auth') as result:
            response=dict(email=self.email, name=self.name)
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
            response=dict(email=self.email, name=self.name)
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

class GoogleLoginTest(ZulipTestCase):
    def google_oauth2_test(self, token_response, account_response):
        # type: (ResponseMock, ResponseMock) -> HttpResponse
        result = self.client_get("/accounts/login/google/send/")
        self.assertEquals(result.status_code, 302)
        # Now extract the CSRF token from the redirect URL
        parsed_url = urllib.parse.urlparse(result.url)
        csrf_state = urllib.parse.parse_qs(parsed_url.query)['state']

        with mock.patch("requests.post", return_value=token_response), \
             mock.patch("requests.get", return_value=account_response):
            result = self.client_get("/accounts/login/google/done/",
                                     dict(state=csrf_state))
        return result

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
        self.assertEquals(result.status_code, 200)
        result = self.client_post('/accounts/register/',
                                  {'full_name': "New User",
                                   'password': 'test_password',
                                   'key': key_match.group("key"),
                                   'terms': True})
        self.assertEquals(result.status_code, 302)
        self.assertEquals(result.url, "http://testserver/")

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
        self.assertEquals(result.status_code, 400)
        self.assertEquals(m.call_args_list[0][0][0],
                          "User error converting Google oauth2 login to token: Response text")

    def test_google_oauth2_500_token_response(self):
        # type: () -> None
        token_response = ResponseMock(500, {})
        with mock.patch("logging.error") as m:
            result = self.google_oauth2_test(token_response, None)
        self.assertEquals(result.status_code, 400)
        self.assertEquals(m.call_args_list[0][0][0],
                          "Could not convert google oauth2 code to access_token: Response text")

    def test_google_oauth2_400_account_response(self):
        # type: () -> None
        token_response = ResponseMock(200, {'access_token': "unique_token"})
        account_response = ResponseMock(400, {})
        with mock.patch("logging.warning") as m:
            result = self.google_oauth2_test(token_response, account_response)
        self.assertEquals(result.status_code, 400)
        self.assertEquals(m.call_args_list[0][0][0],
                          "Google login failed making info API call: Response text")

    def test_google_oauth2_500_account_response(self):
        # type: () -> None
        token_response = ResponseMock(200, {'access_token': "unique_token"})
        account_response = ResponseMock(500, {})
        with mock.patch("logging.error") as m:
            result = self.google_oauth2_test(token_response, account_response)
        self.assertEquals(result.status_code, 400)
        self.assertEquals(m.call_args_list[0][0][0],
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
        self.assertEquals(result.status_code, 400)
        self.assertIn("Google oauth2 account email not found:", m.call_args_list[0][0][0])

    def test_google_oauth2_error_access_denied(self):
        # type: () -> None
        result = self.client_get("/accounts/login/google/done/?error=access_denied")
        self.assertEquals(result.status_code, 302)
        self.assertEquals(result.url, "http://testserver/")

    def test_google_oauth2_error_other(self):
        # type: () -> None
        with mock.patch("logging.warning") as m:
            result = self.client_get("/accounts/login/google/done/?error=some_other_error")
        self.assertEquals(result.status_code, 400)
        self.assertEquals(m.call_args_list[0][0][0],
                          "Error from google oauth2 login: some_other_error")

    def test_google_oauth2_missing_csrf(self):
        # type: () -> None
        with mock.patch("logging.warning") as m:
            result = self.client_get("/accounts/login/google/done/")
        self.assertEquals(result.status_code, 400)
        self.assertEquals(m.call_args_list[0][0][0],
                          'Missing Google oauth2 CSRF state')

    def test_google_oauth2_csrf_malformed(self):
        # type: () -> None
        with mock.patch("logging.warning") as m:
            result = self.client_get("/accounts/login/google/done/?state=badstate")
        self.assertEquals(result.status_code, 400)
        self.assertEquals(m.call_args_list[0][0][0],
                          'Missing Google oauth2 CSRF state')

    def test_google_oauth2_csrf_badstate(self):
        # type: () -> None
        with mock.patch("logging.warning") as m:
            result = self.client_get("/accounts/login/google/done/?state=badstate:otherbadstate:")
        self.assertEquals(result.status_code, 400)
        self.assertEquals(m.call_args_list[0][0][0],
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
            with self.assertRaisesRegexp(Exception, 'Direct login not supported.'):
                with mock.patch('django.core.handlers.base.logger'):
                    self.client_post('/accounts/login/local/', data)

    def test_login_failure_due_to_nonexistent_user(self):
        # type: () -> None
        email = 'nonexisting@zulip.com'
        data = {'direct_email': email}
        with self.assertRaisesRegexp(Exception, 'User cannot login'):
            with mock.patch('django.core.handlers.base.logger'):
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
                result = self.client_post('http://testserver:9080/accounts/login/sso/', REMOTE_USER=email)
                self.assertEqual(result.status_code, 200)
                self.assertIs(get_session_dict_user(self.client.session), None)
                self.assertIn(b"Let's get started", result.content)

    def test_login_failure_due_to_empty_subdomain(self):
        # type: () -> None
        email = 'hamlet@zulip.com'
        with self.settings(REALMS_HAVE_SUBDOMAINS=True,
                           AUTHENTICATION_BACKENDS=('zproject.backends.ZulipRemoteUserBackend',)):
            with mock.patch('zerver.views.auth.get_subdomain', return_value=''):
                result = self.client_post('http://testserver:9080/accounts/login/sso/', REMOTE_USER=email)
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
