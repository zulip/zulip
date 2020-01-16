# -*- coding: utf-8 -*-
from django.conf import settings
from django.contrib.auth import authenticate
from django.core import mail
from django.http import HttpResponse
from django.test import override_settings
from django_auth_ldap.backend import LDAPSearch, _LDAPUser
from django.test.client import RequestFactory
from django.utils.timezone import now as timezone_now
from typing import Any, Callable, Dict, List, Optional, Tuple
from django.core import signing
from django.urls import reverse

import httpretty

import ldap
import jwt
import mock
import re
import time
import datetime

from zerver.lib.actions import (
    do_create_user,
    do_create_realm,
    do_deactivate_realm,
    do_deactivate_user,
    do_invite_users,
    do_reactivate_realm,
    do_reactivate_user,
    do_set_realm_property,
    ensure_stream,
    validate_email,
)
from zerver.lib.avatar import avatar_url
from zerver.lib.avatar_hash import user_avatar_path
from zerver.lib.dev_ldap_directory import generate_dev_ldap_dir
from zerver.lib.mobile_auth_otp import otp_decrypt_api_key
from zerver.lib.validator import validate_login_email, \
    check_bool, check_dict_only, check_list, check_string, Validator
from zerver.lib.request import JsonableError
from zerver.lib.storage import static_path
from zerver.lib.users import get_all_api_keys
from zerver.lib.upload import resize_avatar, MEDIUM_AVATAR_SIZE
from zerver.lib.initial_password import initial_password
from zerver.lib.test_classes import (
    ZulipTestCase,
)
from zerver.models import \
    get_realm, email_to_username, CustomProfileField, CustomProfileFieldValue, \
    UserProfile, PreregistrationUser, Realm, RealmDomain, get_user, MultiuseInvite, \
    clear_supported_auth_backends_cache, PasswordTooWeakError
from zerver.signals import JUST_CREATED_THRESHOLD

from confirmation.models import Confirmation, create_confirmation_link

from zproject.backends import ZulipDummyBackend, EmailAuthBackend, \
    GoogleAuthBackend, ZulipRemoteUserBackend, ZulipLDAPAuthBackend, \
    ZulipLDAPUserPopulator, DevAuthBackend, GitHubAuthBackend, ZulipAuthMixin, \
    dev_auth_enabled, password_auth_enabled, github_auth_enabled, google_auth_enabled, \
    require_email_format_usernames, AUTH_BACKEND_NAME_MAP, \
    ZulipLDAPConfigurationError, ZulipLDAPExceptionNoMatchingLDAPUser, ZulipLDAPExceptionOutsideDomain, \
    ZulipLDAPException, query_ldap, sync_user_from_ldap, SocialAuthMixin, \
    PopulateUserLDAPError, SAMLAuthBackend, saml_auth_enabled, email_belongs_to_ldap, \
    get_external_method_dicts, AzureADAuthBackend, check_password_strength, \
    ZulipLDAPUser

from zerver.views.auth import (maybe_send_to_registration,
                               _subdomain_token_salt)

from onelogin.saml2.auth import OneLogin_Saml2_Auth
from onelogin.saml2.response import OneLogin_Saml2_Response
from social_core.exceptions import AuthFailed, AuthStateForbidden
from social_django.strategy import DjangoStrategy
from social_django.storage import BaseDjangoStorage

import base64
import copy
import json
import urllib
import ujson
from zerver.lib.test_helpers import load_subdomain_token, \
    use_s3_backend, create_s3_buckets, get_test_image_file

class AuthBackendTest(ZulipTestCase):
    def get_username(self, email_to_username: Optional[Callable[[str], str]]=None) -> str:
        username = self.example_email('hamlet')
        if email_to_username is not None:
            username = email_to_username(self.example_email('hamlet'))

        return username

    def verify_backend(self, backend: Any, good_kwargs: Optional[Dict[str, Any]]=None, bad_kwargs: Optional[Dict[str, Any]]=None) -> None:
        clear_supported_auth_backends_cache()
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
        result = backend.authenticate(**good_kwargs)
        if isinstance(backend, SocialAuthMixin):
            # Returns a redirect to login page with an error.
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result.url, "/login/?is_deactivated=true")
        else:
            # Just takes you back to the login page treating as
            # invalid auth; this is correct because the form will
            # provide the appropriate validation error for deactivated
            # account.
            self.assertIsNone(result)

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
            clear_supported_auth_backends_cache()
            self.assertIsNone(backend.authenticate(**good_kwargs))
        clear_supported_auth_backends_cache()

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
            user = EmailAuthBackend().authenticate(username=self.example_email('hamlet'),
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
                                            realm=get_realm('zephyr'),
                                            return_data=dict()))

    def test_email_auth_backend_empty_password(self) -> None:
        user_profile = self.example_user('hamlet')
        password = "testpassword"
        user_profile.set_password(password)
        user_profile.save()

        # First, verify authentication works with the a nonempty
        # password so we know we've set up the test correctly.
        self.assertIsNotNone(EmailAuthBackend().authenticate(username=self.example_email('hamlet'),
                                                             password=password,
                                                             realm=get_realm("zulip")))

        # Now do the same test with the empty string as the password.
        password = ""
        with self.assertRaises(PasswordTooWeakError):
            # UserProfile.set_password protects against setting an empty password.
            user_profile.set_password(password)
        # We do want to force an empty password for this test, so we bypass the protection
        # by using Django's version of this method.
        super(UserProfile, user_profile).set_password(password)
        user_profile.save()
        self.assertIsNone(EmailAuthBackend().authenticate(username=self.example_email('hamlet'),
                                                          password=password,
                                                          realm=get_realm("zulip")))

    def test_email_auth_backend_disabled_password_auth(self) -> None:
        user_profile = self.example_user('hamlet')
        password = "testpassword"
        user_profile.set_password(password)
        user_profile.save()
        # Verify if a realm has password auth disabled, correct password is rejected
        with mock.patch('zproject.backends.password_auth_enabled', return_value=False):
            self.assertIsNone(EmailAuthBackend().authenticate(username=self.example_email('hamlet'),
                                                              password=password,
                                                              realm=get_realm("zulip")))

    def test_login_preview(self) -> None:
        # Test preview=true displays organization login page
        # instead of redirecting to app
        self.login(self.example_email("iago"))
        realm = get_realm("zulip")
        result = self.client_get('/login/?preview=true')
        self.assertEqual(result.status_code, 200)
        self.assert_in_response(realm.description, result)
        self.assert_in_response(realm.name, result)
        self.assert_in_response("Log in to Zulip", result)

        data = dict(description=ujson.dumps("New realm description"),
                    name=ujson.dumps("New Zulip"))
        result = self.client_patch('/json/realm', data)
        self.assert_json_success(result)

        result = self.client_get('/login/?preview=true')
        self.assertEqual(result.status_code, 200)
        self.assert_in_response("New realm description", result)
        self.assert_in_response("New Zulip", result)

        result = self.client_get('/login/')
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result.url, 'http://zulip.testserver')

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipDummyBackend',))
    def test_no_backend_enabled(self) -> None:
        result = self.client_get('/login/')
        self.assert_in_success_response(["No authentication backends are enabled"], result)

        result = self.client_get('/register/')
        self.assert_in_success_response(["No authentication backends are enabled"], result)

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.GoogleAuthBackend',))
    def test_any_backend_enabled(self) -> None:

        # testing to avoid false error messages.
        result = self.client_get('/login/')
        self.assert_not_in_success_response(["No authentication backends are enabled"], result)

        result = self.client_get('/register/')
        self.assert_not_in_success_response(["No authentication backends are enabled"], result)

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',),
                       LDAP_EMAIL_ATTR="mail")
    def test_ldap_backend(self) -> None:
        self.init_default_ldap_database()
        user_profile = self.example_user('hamlet')
        email = user_profile.email
        password = self.ldap_password()
        self.setup_subdomain(user_profile)

        username = self.get_username()
        backend = ZulipLDAPAuthBackend()

        # Test LDAP auth fails when LDAP server rejects password
        self.assertIsNone(backend.authenticate(username=email, password="wrongpass", realm=get_realm("zulip")))

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
                                            realm=get_realm('zephyr')),
                            good_kwargs=dict(username=username,
                                             password=password,
                                             realm=get_realm('zulip')))

    def test_devauth_backend(self) -> None:
        self.verify_backend(DevAuthBackend(),
                            good_kwargs=dict(dev_auth_username=self.get_username(),
                                             realm=get_realm("zulip")),
                            bad_kwargs=dict(dev_auth_username=self.get_username(),
                                            realm=get_realm("zephyr")))

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
                                            realm=get_realm('zephyr')))

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipRemoteUserBackend',))
    @override_settings(SSO_APPEND_DOMAIN='zulip.com')
    def test_remote_user_backend_sso_append_domain(self) -> None:
        username = self.get_username(email_to_username)
        self.verify_backend(ZulipRemoteUserBackend(),
                            good_kwargs=dict(remote_user=username,
                                             realm=get_realm("zulip")),
                            bad_kwargs=dict(remote_user=username,
                                            realm=get_realm('zephyr')))

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.GitHubAuthBackend',
                                                'zproject.backends.GoogleAuthBackend'))
    def test_social_auth_backends(self) -> None:
        user = self.example_user('hamlet')
        token_data_dict = {
            'access_token': 'foobar',
            'token_type': 'bearer'
        }
        github_email_data = [
            dict(email=user.email,
                 verified=True,
                 primary=True),
            dict(email="nonprimary@zulip.com",
                 verified=True),
            dict(email="ignored@example.com",
                 verified=False),
        ]
        google_email_data = dict(email=user.email,
                                 name=user.full_name,
                                 email_verified=True)
        backends_to_test = {
            'google': {
                'urls': [
                    {
                        'url': "https://accounts.google.com/o/oauth2/token",
                        'method': httpretty.POST,
                        'status': 200,
                        'body': json.dumps(token_data_dict),
                    },
                    {
                        'url': "https://www.googleapis.com/oauth2/v3/userinfo",
                        'method': httpretty.GET,
                        'status': 200,
                        'body': json.dumps(google_email_data),
                    },
                ],
                'backend': GoogleAuthBackend,
            },
            'github': {
                'urls': [
                    {
                        'url': "https://github.com/login/oauth/access_token",
                        'method': httpretty.POST,
                        'status': 200,
                        'body': json.dumps(token_data_dict),
                    },
                    {
                        'url': "https://api.github.com/user",
                        'method': httpretty.GET,
                        'status': 200,
                        'body': json.dumps(dict(email=user.email, name=user.full_name)),
                    },
                    {
                        'url': "https://api.github.com/user/emails",
                        'method': httpretty.GET,
                        'status': 200,
                        'body': json.dumps(github_email_data),
                    },
                ],
                'backend': GitHubAuthBackend,
            }
        }   # type: Dict[str, Any]

        def patched_authenticate(**kwargs: Any) -> Any:
            # This is how we pass the subdomain to the authentication
            # backend in production code, so we need to do this setup
            # here.
            if 'subdomain' in kwargs:
                backend.strategy.session_set("subdomain", kwargs["subdomain"])
                del kwargs['subdomain']

            # Because we're not simulating the full python-social-auth
            # pipeline here, we need to provide the user's choice of
            # which email to select in the partial phase of the
            # pipeline when we display an email picker for the GitHub
            # authentication backend.  We do that here.
            def return_email() -> Dict[str, str]:
                return {'email': user.email}
            backend.strategy.request_data = return_email

            result = orig_authenticate(backend, **kwargs)
            return result

        def patched_get_verified_emails(*args: Any, **kwargs: Any) -> Any:
            return google_email_data['email']

        for backend_name in backends_to_test:
            httpretty.enable(allow_net_connect=False)
            urls = backends_to_test[backend_name]['urls']   # type: List[Dict[str, Any]]
            for details in urls:
                httpretty.register_uri(
                    details['method'],
                    details['url'],
                    status=details['status'],
                    body=details['body'])
            backend_class = backends_to_test[backend_name]['backend']
            backend = backend_class()
            backend.strategy = DjangoStrategy(storage=BaseDjangoStorage())

            orig_authenticate = backend_class.authenticate
            backend.authenticate = patched_authenticate
            orig_get_verified_emails = backend_class.get_verified_emails
            if backend_name == "google":
                backend.get_verified_emails = patched_get_verified_emails

            good_kwargs = dict(backend=backend, strategy=backend.strategy,
                               storage=backend.strategy.storage,
                               response=token_data_dict,
                               subdomain='zulip')
            bad_kwargs = dict(subdomain='acme')
            with mock.patch('zerver.views.auth.redirect_and_log_into_subdomain',
                            return_value=user):
                self.verify_backend(backend,
                                    good_kwargs=good_kwargs,
                                    bad_kwargs=bad_kwargs)
                bad_kwargs['subdomain'] = "zephyr"
                self.verify_backend(backend,
                                    good_kwargs=good_kwargs,
                                    bad_kwargs=bad_kwargs)
            backend.authenticate = orig_authenticate
            backend.get_verified_emails = orig_get_verified_emails
            httpretty.disable()
            httpretty.reset()

class CheckPasswordStrengthTest(ZulipTestCase):
    def test_check_password_strength(self) -> None:
        with self.settings(PASSWORD_MIN_LENGTH=0, PASSWORD_MIN_GUESSES=0):
            # Never allow empty password.
            self.assertFalse(check_password_strength(''))

        with self.settings(PASSWORD_MIN_LENGTH=6, PASSWORD_MIN_GUESSES=1000):
            self.assertFalse(check_password_strength(''))
            self.assertFalse(check_password_strength('short'))
            # Long enough, but too easy:
            self.assertFalse(check_password_strength('longer'))
            # Good password:
            self.assertTrue(check_password_strength('f657gdGGk9'))

class SocialAuthBase(ZulipTestCase):
    """This is a base class for testing social-auth backends. These
    methods are often overriden by subclasses:

        register_extra_endpoints() - If the backend being tested calls some extra
                                     endpoints then they can be added here.

        get_account_data_dict() - Return the data returned by the user info endpoint
                                  according to the respective backend.
    """
    # Don't run base class tests, make sure to set it to False
    # in subclass otherwise its tests will not run.
    __unittest_skip__ = True

    def setUp(self) -> None:
        super().setUp()
        self.user_profile = self.example_user('hamlet')
        self.email = self.user_profile.email
        self.name = self.user_profile.full_name
        self.backend = self.BACKEND_CLASS
        self.backend.strategy = DjangoStrategy(storage=BaseDjangoStorage())
        self.user_profile.backend = self.backend

        # This is a workaround for the fact that Python social auth
        # caches the set of authentication backends that are enabled
        # the first time that `social_django.utils` is imported.  See
        # https://github.com/python-social-auth/social-app-django/pull/162
        # for details.
        from social_core.backends.utils import load_backends
        load_backends(settings.AUTHENTICATION_BACKENDS, force_load=True)

    def register_extra_endpoints(self,
                                 account_data_dict: Dict[str, str],
                                 **extra_data: Any) -> None:
        pass

    def prepare_login_url_and_headers(self,
                                      subdomain: Optional[str]=None,
                                      mobile_flow_otp: Optional[str]=None,
                                      is_signup: Optional[str]=None,
                                      next: str='',
                                      multiuse_object_key: str='',
                                      alternative_start_url: Optional[str]=None
                                      ) -> Tuple[str, Dict[str, Any]]:
        url = self.LOGIN_URL
        if alternative_start_url is not None:
            url = alternative_start_url

        params = {}
        headers = {}
        if subdomain is not None:
            headers['HTTP_HOST'] = subdomain + ".testserver"
        if mobile_flow_otp is not None:
            params['mobile_flow_otp'] = mobile_flow_otp
            headers['HTTP_USER_AGENT'] = "ZulipAndroid"
        if is_signup is not None:
            url = self.SIGNUP_URL
        params['next'] = next
        params['multiuse_object_key'] = multiuse_object_key
        if len(params) > 0:
            url += "?%s" % (urllib.parse.urlencode(params),)

        return url, headers

    def social_auth_test(self, account_data_dict: Dict[str, str],
                         *, subdomain: Optional[str]=None,
                         mobile_flow_otp: Optional[str]=None,
                         is_signup: Optional[str]=None,
                         next: str='',
                         multiuse_object_key: str='',
                         expect_choose_email_screen: bool=False,
                         alternative_start_url: Optional[str]=None,
                         **extra_data: Any) -> HttpResponse:
        url, headers = self.prepare_login_url_and_headers(
            subdomain, mobile_flow_otp, is_signup, next, multiuse_object_key, alternative_start_url
        )

        result = self.client_get(url, **headers)

        expected_result_url_prefix = 'http://testserver/login/%s/' % (self.backend.name,)
        if settings.SOCIAL_AUTH_SUBDOMAIN is not None:
            expected_result_url_prefix = ('http://%s.testserver/login/%s/' %
                                          (settings.SOCIAL_AUTH_SUBDOMAIN, self.backend.name,))

        if result.status_code != 302 or not result.url.startswith(expected_result_url_prefix):
            return result

        result = self.client_get(result.url, **headers)
        self.assertEqual(result.status_code, 302)
        assert self.AUTHORIZATION_URL in result.url

        self.client.cookies = result.cookies

        # Next, the browser requests result["Location"], and gets
        # redirected back to the registered redirect uri.

        token_data_dict = {
            'access_token': 'foobar',
            'token_type': 'bearer'
        }

        # We register callbacks for the key URLs on Identity Provider that
        # auth completion url will call
        httpretty.enable(allow_net_connect=False)
        httpretty.register_uri(
            httpretty.POST,
            self.ACCESS_TOKEN_URL,
            match_querystring=False,
            status=200,
            body=json.dumps(token_data_dict))
        httpretty.register_uri(
            httpretty.GET,
            self.USER_INFO_URL,
            status=200,
            body=json.dumps(account_data_dict)
        )
        self.register_extra_endpoints(account_data_dict, **extra_data)

        parsed_url = urllib.parse.urlparse(result.url)
        csrf_state = urllib.parse.parse_qs(parsed_url.query)['state']
        result = self.client_get(self.AUTH_FINISH_URL,
                                 dict(state=csrf_state), **headers)

        if expect_choose_email_screen and result.status_code == 200:
            # For authentication backends such as GitHub that
            # successfully authenticate multiple email addresses,
            # we'll have an additional screen where the user selects
            # which email address to login using (this screen is a
            # "partial" state of the python-social-auth pipeline).
            #
            # TODO: Generalize this testing code for use with other
            # authentication backends; for now, we just assert that
            # it's definitely the GitHub authentication backend.
            self.assert_in_success_response(["Select account"], result)
            assert self.AUTH_FINISH_URL == "/complete/github/"

            # Testing hack: When the pipeline goes to the partial
            # step, the below given URL is called again in the same
            # test. If the below URL is not registered again as done
            # below, the URL returns emails from previous tests. e.g
            # email = 'invalid' may be one of the emails in the list
            # in a test function followed by it. This is probably a
            # bug in httpretty.
            httpretty.disable()
            httpretty.enable()
            httpretty.register_uri(
                httpretty.GET,
                "https://api.github.com/user/emails",
                status=200,
                body=json.dumps(self.email_data)
            )
            result = self.client_get(self.AUTH_FINISH_URL,
                                     dict(state=csrf_state, email=account_data_dict['email']), **headers)
        elif self.AUTH_FINISH_URL == "/complete/github/":
            # We want to be explicit about when we expect a test to
            # use the "choose email" screen, but of course we should
            # only check for that screen with the GitHub backend,
            # because this test code is shared with other
            # authentication backends that structurally will never use
            # that screen.
            assert not expect_choose_email_screen

        httpretty.disable()
        return result

    def test_social_auth_no_key(self) -> None:
        account_data_dict = self.get_account_data_dict(email=self.email, name=self.name)
        with self.settings(**{self.CLIENT_KEY_SETTING: None}):
            result = self.social_auth_test(account_data_dict,
                                           subdomain='zulip', next='/user_uploads/image')
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result.url, self.CONFIG_ERROR_URL)

    def test_social_auth_success(self) -> None:
        account_data_dict = self.get_account_data_dict(email=self.email, name=self.name)
        result = self.social_auth_test(account_data_dict,
                                       expect_choose_email_screen=True,
                                       subdomain='zulip', next='/user_uploads/image')
        data = load_subdomain_token(result)
        self.assertEqual(data['email'], self.example_email("hamlet"))
        self.assertEqual(data['name'], self.name)
        self.assertEqual(data['subdomain'], 'zulip')
        self.assertEqual(data['next'], '/user_uploads/image')
        self.assertEqual(result.status_code, 302)
        parsed_url = urllib.parse.urlparse(result.url)
        uri = "{}://{}{}".format(parsed_url.scheme, parsed_url.netloc,
                                 parsed_url.path)
        self.assertTrue(uri.startswith('http://zulip.testserver/accounts/login/subdomain/'))

    @override_settings(SOCIAL_AUTH_SUBDOMAIN=None)
    def test_when_social_auth_subdomain_is_not_set(self) -> None:
        account_data_dict = self.get_account_data_dict(email=self.email, name=self.name)
        result = self.social_auth_test(account_data_dict,
                                       subdomain='zulip',
                                       expect_choose_email_screen=True,
                                       next='/user_uploads/image')
        data = load_subdomain_token(result)
        self.assertEqual(data['email'], self.example_email("hamlet"))
        self.assertEqual(data['name'], self.name)
        self.assertEqual(data['subdomain'], 'zulip')
        self.assertEqual(data['next'], '/user_uploads/image')
        self.assertEqual(result.status_code, 302)
        parsed_url = urllib.parse.urlparse(result.url)
        uri = "{}://{}{}".format(parsed_url.scheme, parsed_url.netloc,
                                 parsed_url.path)
        self.assertTrue(uri.startswith('http://zulip.testserver/accounts/login/subdomain/'))

    def test_social_auth_deactivated_user(self) -> None:
        user_profile = self.example_user("hamlet")
        do_deactivate_user(user_profile)
        account_data_dict = self.get_account_data_dict(email=self.email, name=self.name)
        # We expect to go through the "choose email" screen here,
        # because there won't be an existing user account we can
        # auto-select for the user.
        result = self.social_auth_test(account_data_dict,
                                       expect_choose_email_screen=True,
                                       subdomain='zulip')
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result.url, "/login/?is_deactivated=true")
        # TODO: verify whether we provide a clear error message

    def test_social_auth_invalid_realm(self) -> None:
        account_data_dict = self.get_account_data_dict(email=self.email, name=self.name)
        with mock.patch('zerver.middleware.get_realm', return_value=get_realm("zulip")):
            # This mock.patch case somewhat hackishly arranges it so
            # that we switch realms halfway through the test
            result = self.social_auth_test(account_data_dict,
                                           subdomain='invalid', next='/user_uploads/image')
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result.url, "/accounts/login/?subdomain=1")

    def test_social_auth_invalid_email(self) -> None:
        account_data_dict = self.get_account_data_dict(email="invalid", name=self.name)
        result = self.social_auth_test(account_data_dict,
                                       expect_choose_email_screen=True,
                                       subdomain='zulip', next='/user_uploads/image')
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result.url, "/login/?next=/user_uploads/image")

    def test_user_cannot_log_into_nonexisting_realm(self) -> None:
        account_data_dict = self.get_account_data_dict(email=self.email, name=self.name)
        result = self.social_auth_test(account_data_dict,
                                       subdomain='nonexistent')
        self.assert_in_response("There is no Zulip organization hosted at this subdomain.",
                                result)
        self.assertEqual(result.status_code, 404)

    def test_user_cannot_log_into_wrong_subdomain(self) -> None:
        account_data_dict = self.get_account_data_dict(email=self.email, name=self.name)
        result = self.social_auth_test(account_data_dict,
                                       expect_choose_email_screen=True,
                                       subdomain='zephyr')
        self.assertTrue(result.url.startswith("http://zephyr.testserver/accounts/login/subdomain/"))
        result = self.client_get(result.url.replace('http://zephyr.testserver', ''),
                                 subdomain="zephyr")
        self.assert_in_success_response(['Your email address, hamlet@zulip.com, is not in one of the domains ',
                                         'that are allowed to register for accounts in this organization.'], result)

    def test_social_auth_mobile_success(self) -> None:
        mobile_flow_otp = '1234abcd' * 8
        account_data_dict = self.get_account_data_dict(email=self.email, name='Full Name')
        self.assertEqual(len(mail.outbox), 0)
        self.user_profile.date_joined = timezone_now() - datetime.timedelta(seconds=JUST_CREATED_THRESHOLD + 1)
        self.user_profile.save()

        with self.settings(SEND_LOGIN_EMAILS=True):
            # Verify that the right thing happens with an invalid-format OTP
            result = self.social_auth_test(account_data_dict, subdomain='zulip',
                                           mobile_flow_otp="1234")
            self.assert_json_error(result, "Invalid OTP")
            result = self.social_auth_test(account_data_dict, subdomain='zulip',
                                           mobile_flow_otp="invalido" * 8)
            self.assert_json_error(result, "Invalid OTP")

            # Now do it correctly
            result = self.social_auth_test(account_data_dict, subdomain='zulip',
                                           expect_choose_email_screen=True,
                                           mobile_flow_otp=mobile_flow_otp)
        self.assertEqual(result.status_code, 302)
        redirect_url = result['Location']
        parsed_url = urllib.parse.urlparse(redirect_url)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        self.assertEqual(parsed_url.scheme, 'zulip')
        self.assertEqual(query_params["realm"], ['http://zulip.testserver'])
        self.assertEqual(query_params["email"], [self.example_email("hamlet")])
        encrypted_api_key = query_params["otp_encrypted_api_key"][0]
        hamlet_api_keys = get_all_api_keys(self.example_user('hamlet'))
        self.assertIn(otp_decrypt_api_key(encrypted_api_key, mobile_flow_otp), hamlet_api_keys)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Zulip on Android', mail.outbox[0].body)

    def test_social_auth_registration_existing_account(self) -> None:
        """If the user already exists, signup flow just logs them in"""
        email = "hamlet@zulip.com"
        name = 'Full Name'
        account_data_dict = self.get_account_data_dict(email=email, name=name)
        result = self.social_auth_test(account_data_dict,
                                       expect_choose_email_screen=True,
                                       subdomain='zulip', is_signup='1')
        data = load_subdomain_token(result)
        self.assertEqual(data['email'], self.example_email("hamlet"))
        self.assertEqual(data['name'], 'Full Name')
        self.assertEqual(data['subdomain'], 'zulip')
        self.assertEqual(result.status_code, 302)
        parsed_url = urllib.parse.urlparse(result.url)
        uri = "{}://{}{}".format(parsed_url.scheme, parsed_url.netloc,
                                 parsed_url.path)
        self.assertTrue(uri.startswith('http://zulip.testserver/accounts/login/subdomain/'))
        hamlet = self.example_user("hamlet")
        # Name wasn't changed at all
        self.assertEqual(hamlet.full_name, "King Hamlet")

    def stage_two_of_registration(self, result: HttpResponse, realm: Realm, subdomain: str,
                                  email: str, name: str, expected_final_name: str,
                                  skip_registration_form: bool) -> None:
        data = load_subdomain_token(result)
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
        confirmation = Confirmation.objects.all().last()
        confirmation_key = confirmation.confirmation_key
        self.assertIn('do_confirm/' + confirmation_key, result.url)
        result = self.client_get(result.url)
        self.assert_in_response('action="/accounts/register/"', result)
        data = {"from_confirmation": "1",
                "key": confirmation_key}
        result = self.client_post('/accounts/register/', data)
        if not skip_registration_form:
            self.assert_in_response("We just need you to do one last thing", result)

            # Verify that the user is asked for name but not password
            self.assert_not_in_success_response(['id_password'], result)
            self.assert_in_success_response(['id_full_name'], result)
            # Verify the name field gets correctly pre-populated:
            self.assert_in_success_response([expected_final_name], result)

            # Click confirm registration button.
            result = self.client_post(
                '/accounts/register/',
                {'full_name': expected_final_name,
                 'key': confirmation_key,
                 'terms': True})

        self.assertEqual(result.status_code, 302)
        user_profile = get_user(email, realm)
        self.assert_logged_in_user_id(user_profile.id)
        self.assertEqual(user_profile.full_name, expected_final_name)

        self.assertFalse(user_profile.has_usable_password())

    @override_settings(TERMS_OF_SERVICE=None)
    def test_social_auth_registration(self) -> None:
        """If the user doesn't exist yet, social auth can be used to register an account"""
        email = "newuser@zulip.com"
        name = 'Full Name'
        subdomain = 'zulip'
        realm = get_realm("zulip")
        account_data_dict = self.get_account_data_dict(email=email, name=name)
        result = self.social_auth_test(account_data_dict,
                                       expect_choose_email_screen=True,
                                       subdomain=subdomain, is_signup='1')
        self.stage_two_of_registration(result, realm, subdomain, email, name, name,
                                       self.BACKEND_CLASS.full_name_validated)

    @override_settings(TERMS_OF_SERVICE=None)
    def test_social_auth_registration_invitation_exists(self) -> None:
        """
        This tests the registration flow in the case where an invitation for the user
        was generated.
        """
        email = "newuser@zulip.com"
        name = 'Full Name'
        subdomain = 'zulip'
        realm = get_realm("zulip")

        iago = self.example_user("iago")
        do_invite_users(iago, [email], [])

        account_data_dict = self.get_account_data_dict(email=email, name=name)
        result = self.social_auth_test(account_data_dict,
                                       expect_choose_email_screen=True,
                                       subdomain=subdomain, is_signup='1')
        self.stage_two_of_registration(result, realm, subdomain, email, name, name,
                                       self.BACKEND_CLASS.full_name_validated)

    @override_settings(TERMS_OF_SERVICE=None)
    def test_social_auth_registration_using_multiuse_invite(self) -> None:
        """If the user doesn't exist yet, social auth can be used to register an account"""
        email = "newuser@zulip.com"
        name = 'Full Name'
        subdomain = 'zulip'
        realm = get_realm("zulip")
        realm.invite_required = True
        realm.save()

        stream_names = ["new_stream_1", "new_stream_2"]
        streams = []
        for stream_name in set(stream_names):
            stream = ensure_stream(realm, stream_name)
            streams.append(stream)

        referrer = self.example_user("hamlet")
        multiuse_obj = MultiuseInvite.objects.create(realm=realm, referred_by=referrer)
        multiuse_obj.streams.set(streams)
        create_confirmation_link(multiuse_obj, realm.host, Confirmation.MULTIUSE_INVITE)
        multiuse_confirmation = Confirmation.objects.all().last()
        multiuse_object_key = multiuse_confirmation.confirmation_key
        account_data_dict = self.get_account_data_dict(email=email, name=name)

        # First, try to signup for closed realm without using an invitation
        result = self.social_auth_test(account_data_dict,
                                       expect_choose_email_screen=True,
                                       subdomain=subdomain, is_signup='1')
        result = self.client_get(result.url)
        # Verify that we're unable to signup, since this is a closed realm
        self.assertEqual(result.status_code, 200)
        self.assert_in_success_response(["Sign up"], result)

        result = self.social_auth_test(account_data_dict, subdomain=subdomain, is_signup='1',
                                       expect_choose_email_screen=True,
                                       multiuse_object_key=multiuse_object_key)
        self.stage_two_of_registration(result, realm, subdomain, email, name, name,
                                       self.BACKEND_CLASS.full_name_validated)

    def test_social_auth_registration_without_is_signup(self) -> None:
        """If `is_signup` is not set then a new account isn't created"""
        email = "newuser@zulip.com"
        name = 'Full Name'
        account_data_dict = self.get_account_data_dict(email=email, name=name)
        result = self.social_auth_test(account_data_dict,
                                       expect_choose_email_screen=True,
                                       subdomain='zulip')
        self.assertEqual(result.status_code, 302)
        data = load_subdomain_token(result)
        self.assertEqual(data['email'], email)
        self.assertEqual(data['name'], name)
        self.assertEqual(data['subdomain'], 'zulip')
        self.assertEqual(result.status_code, 302)
        parsed_url = urllib.parse.urlparse(result.url)
        uri = "{}://{}{}".format(parsed_url.scheme, parsed_url.netloc,
                                 parsed_url.path)
        self.assertTrue(uri.startswith('http://zulip.testserver/accounts/login/subdomain/'))

        result = self.client_get(result.url)
        self.assertEqual(result.status_code, 200)
        self.assert_in_response("No account found for newuser@zulip.com.", result)

    def test_social_auth_registration_without_is_signup_closed_realm(self) -> None:
        """If the user doesn't exist yet in closed realm, give an error"""
        email = "nonexisting@phantom.com"
        name = 'Full Name'
        account_data_dict = self.get_account_data_dict(email=email, name=name)
        result = self.social_auth_test(account_data_dict,
                                       expect_choose_email_screen=True,
                                       subdomain='zulip')
        self.assertEqual(result.status_code, 302)
        data = load_subdomain_token(result)
        self.assertEqual(data['email'], email)
        self.assertEqual(data['name'], name)
        self.assertEqual(data['subdomain'], 'zulip')
        self.assertEqual(result.status_code, 302)
        parsed_url = urllib.parse.urlparse(result.url)
        uri = "{}://{}{}".format(parsed_url.scheme, parsed_url.netloc,
                                 parsed_url.path)
        self.assertTrue(uri.startswith('http://zulip.testserver/accounts/login/subdomain/'))

        result = self.client_get(result.url)
        self.assertEqual(result.status_code, 200)
        self.assert_in_response('action="/register/"', result)
        self.assert_in_response('Your email address, {}, is not '
                                'in one of the domains that are allowed to register '
                                'for accounts in this organization.'.format(email), result)

    @override_settings(TERMS_OF_SERVICE=None)
    def test_social_auth_with_ldap_populate_registration_from_confirmation(self) -> None:
        self.init_default_ldap_database()
        email = "newuser@zulip.com"
        name = "Full Name"
        realm = get_realm("zulip")
        subdomain = "zulip"
        ldap_user_attr_map = {'full_name': 'cn'}
        account_data_dict = self.get_account_data_dict(email=email, name=name)

        backend_path = 'zproject.backends.{}'.format(self.BACKEND_CLASS.__name__)
        with self.settings(
                POPULATE_PROFILE_VIA_LDAP=True,
                LDAP_APPEND_DOMAIN='zulip.com',
                AUTH_LDAP_USER_ATTR_MAP=ldap_user_attr_map,
                AUTHENTICATION_BACKENDS=(backend_path,
                                         'zproject.backends.ZulipLDAPUserPopulator',
                                         'zproject.backends.ZulipDummyBackend')
        ):
            result = self.social_auth_test(account_data_dict,
                                           expect_choose_email_screen=True,
                                           subdomain=subdomain, is_signup='1')
            # Full name should get populated from ldap:
            self.stage_two_of_registration(result, realm, subdomain, email, name, "New LDAP fullname",
                                           skip_registration_form=True)

            # Now try a user that doesn't exist in ldap:
            email = self.nonreg_email("alice")
            name = "Alice Social"
            account_data_dict = self.get_account_data_dict(email=email, name=name)
            result = self.social_auth_test(account_data_dict,
                                           expect_choose_email_screen=True,
                                           subdomain=subdomain, is_signup='1')
            # Full name should get populated as provided by the social backend, because
            # this user isn't in the ldap dictionary:
            self.stage_two_of_registration(result, realm, subdomain, email, name, name,
                                           skip_registration_form=self.BACKEND_CLASS.full_name_validated)

    @override_settings(TERMS_OF_SERVICE=None)
    def test_social_auth_with_ldap_auth_registration_from_confirmation(self) -> None:
        """
        This test checks that in configurations that use the ldap authentication backend
        and a social backend, it is possible to create non-ldap users via the social backend.
        """
        self.init_default_ldap_database()
        email = self.nonreg_email("alice")
        name = "Alice Social"
        realm = get_realm("zulip")
        subdomain = "zulip"
        ldap_user_attr_map = {'full_name': 'cn'}
        account_data_dict = self.get_account_data_dict(email=email, name=name)

        backend_path = 'zproject.backends.{}'.format(self.BACKEND_CLASS.__name__)
        with self.settings(
                POPULATE_PROFILE_VIA_LDAP=True,
                LDAP_EMAIL_ATTR='mail',
                AUTH_LDAP_USER_ATTR_MAP=ldap_user_attr_map,
                AUTHENTICATION_BACKENDS=(backend_path,
                                         'zproject.backends.ZulipLDAPAuthBackend',
                                         'zproject.backends.ZulipDummyBackend')
        ):
            account_data_dict = self.get_account_data_dict(email=email, name=name)
            result = self.social_auth_test(account_data_dict,
                                           expect_choose_email_screen=True,
                                           subdomain=subdomain, is_signup='1')
            # Full name should get populated as provided by the social backend, because
            # this user isn't in the ldap dictionary:
            self.stage_two_of_registration(result, realm, subdomain, email, name, name,
                                           skip_registration_form=self.BACKEND_CLASS.full_name_validated)

    def test_social_auth_complete(self) -> None:
        with mock.patch('social_core.backends.oauth.BaseOAuth2.process_error',
                        side_effect=AuthFailed('Not found')):
            result = self.client_get(reverse('social:complete', args=[self.backend.name]))
            self.assertEqual(result.status_code, 302)
            self.assertIn('login', result.url)

    def test_social_auth_complete_when_base_exc_is_raised(self) -> None:
        with mock.patch('social_core.backends.oauth.BaseOAuth2.auth_complete',
                        side_effect=AuthStateForbidden('State forbidden')), \
                mock.patch('zproject.backends.logging.warning'):
            result = self.client_get(reverse('social:complete', args=[self.backend.name]))
            self.assertEqual(result.status_code, 302)
            self.assertIn('login', result.url)

class SAMLAuthBackendTest(SocialAuthBase):
    __unittest_skip__ = False

    BACKEND_CLASS = SAMLAuthBackend
    LOGIN_URL = "/accounts/login/social/saml/test_idp"
    SIGNUP_URL = "/accounts/register/social/saml/test_idp"
    AUTHORIZATION_URL = "https://idp.testshib.org/idp/profile/SAML2/Redirect/SSO"
    AUTH_FINISH_URL = "/complete/saml/"
    CONFIG_ERROR_URL = "/config-error/saml"

    # We have to define our own social_auth_test as the flow of SAML authentication
    # is different from the other social backends.
    def social_auth_test(self, account_data_dict: Dict[str, str],
                         *, subdomain: Optional[str]=None,
                         mobile_flow_otp: Optional[str]=None,
                         is_signup: Optional[str]=None,
                         next: str='',
                         multiuse_object_key: str='',
                         **extra_data: Any) -> HttpResponse:
        url, headers = self.prepare_login_url_and_headers(
            subdomain, mobile_flow_otp, is_signup, next, multiuse_object_key
        )

        result = self.client_get(url, **headers)

        expected_result_url_prefix = 'http://testserver/login/%s/' % (self.backend.name,)
        if settings.SOCIAL_AUTH_SUBDOMAIN is not None:
            expected_result_url_prefix = (
                'http://%s.testserver/login/%s/' % (settings.SOCIAL_AUTH_SUBDOMAIN, self.backend.name)
            )

        if result.status_code != 302 or not result.url.startswith(expected_result_url_prefix):
            return result

        result = self.client_get(result.url, **headers)

        self.assertEqual(result.status_code, 302)
        assert self.AUTHORIZATION_URL in result.url
        assert "samlrequest" in result.url.lower()

        self.client.cookies = result.cookies
        parsed_url = urllib.parse.urlparse(result.url)
        relay_state = urllib.parse.parse_qs(parsed_url.query)['RelayState'][0]
        # Make sure params are getting encoded into RelayState:
        data = SAMLAuthBackend.get_data_from_redis(relay_state)
        if next:
            self.assertEqual(data['next'], next)
        if is_signup:
            self.assertEqual(data['is_signup'], is_signup)

        saml_response = self.generate_saml_response(**account_data_dict)
        post_params = {"SAMLResponse": saml_response, "RelayState": relay_state}
        # The mock below is necessary, so that python3-saml accepts our SAMLResponse,
        # and doesn't verify the cryptographic signatures etc., since generating
        # a perfectly valid SAMLResponse for the purpose of these tests would be too complex,
        # and we simply use one loaded from a fixture file.
        with mock.patch.object(OneLogin_Saml2_Response, 'is_valid', return_value=True):
            result = self.client_post(self.AUTH_FINISH_URL, post_params, **headers)

        return result

    def generate_saml_response(self, email: str, name: str) -> str:
        """
        The samlresponse.txt fixture has a pre-generated SAMLResponse,
        with {email}, {first_name}, {last_name} placeholders, that can
        be filled out with the data we want.
        """
        name_parts = name.split(' ')
        first_name = name_parts[0]
        last_name = name_parts[1]

        unencoded_saml_response = self.fixture_data("samlresponse.txt", type="saml").format(
            email=email,
            first_name=first_name,
            last_name=last_name
        )
        # SAMLResponse needs to be base64-encoded.
        saml_response = base64.b64encode(unencoded_saml_response.encode()).decode()  # type: str

        return saml_response

    def get_account_data_dict(self, email: str, name: str) -> Dict[str, Any]:
        return dict(email=email, name=name)

    def test_social_auth_no_key(self) -> None:
        """
        Since in the case of SAML there isn't a direct equivalent of CLIENT_KEY_SETTING,
        we override this test, to test for the case where the obligatory
        SOCIAL_AUTH_SAML_ENABLED_IDPS isn't configured.
        """
        account_data_dict = self.get_account_data_dict(email=self.email, name=self.name)
        with self.settings(SOCIAL_AUTH_SAML_ENABLED_IDPS=None):
            result = self.social_auth_test(account_data_dict,
                                           subdomain='zulip', next='/user_uploads/image')
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result.url, self.CONFIG_ERROR_URL)

            # Test the signup path too:
            result = self.social_auth_test(account_data_dict, is_signup='1',
                                           subdomain='zulip', next='/user_uploads/image')
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result.url, self.CONFIG_ERROR_URL)

    def test_saml_auth_works_without_private_public_keys(self) -> None:
        with self.settings(SOCIAL_AUTH_SAML_SP_PUBLIC_CERT='', SOCIAL_AUTH_SAML_SP_PRIVATE_KEY=''):
            self.test_social_auth_success()

    def test_saml_auth_enabled(self) -> None:
        with self.settings(AUTHENTICATION_BACKENDS=('zproject.backends.SAMLAuthBackend',)):
            self.assertTrue(saml_auth_enabled())
            result = self.client_get("/saml/metadata.xml")
            self.assert_in_success_response(
                ['entityID="{}"'.format(settings.SOCIAL_AUTH_SAML_SP_ENTITY_ID)], result
            )

    def test_social_auth_complete(self) -> None:
        with mock.patch.object(OneLogin_Saml2_Response, 'is_valid', return_value=True):
            with mock.patch.object(OneLogin_Saml2_Auth, 'is_authenticated', return_value=False), \
                    mock.patch('zproject.backends.logging.info') as m:
                # This mock causes AuthFailed to be raised.
                saml_response = self.generate_saml_response(self.email, self.name)
                relay_state = SAMLAuthBackend.put_data_in_redis({"idp": "test_idp"})
                post_params = {"SAMLResponse": saml_response, "RelayState": relay_state}
                result = self.client_post('/complete/saml/',  post_params)
                self.assertEqual(result.status_code, 302)
                self.assertIn('login', result.url)
                m.assert_called_with("Authentication failed: SAML login failed: [] (None)")

    def test_social_auth_complete_when_base_exc_is_raised(self) -> None:
        with mock.patch.object(OneLogin_Saml2_Response, 'is_valid', return_value=True):
            with mock.patch('social_core.backends.saml.SAMLAuth.auth_complete',
                            side_effect=AuthStateForbidden('State forbidden')), \
                    mock.patch('zproject.backends.logging.warning') as m:
                saml_response = self.generate_saml_response(self.email, self.name)
                relay_state = SAMLAuthBackend.put_data_in_redis({"idp": "test_idp"})
                post_params = {"SAMLResponse": saml_response, "RelayState": relay_state}
                result = self.client_post('/complete/saml/',  post_params)
                self.assertEqual(result.status_code, 302)
                self.assertIn('login', result.url)
                m.assert_called_with("Wrong state parameter given.")

    def test_social_auth_complete_bad_params(self) -> None:
        # Simple GET for /complete/saml without the required parameters.
        # This tests the auth_complete wrapped in our SAMLAuthBackend,
        # ensuring it prevents this requests from causing an internal server error.
        with mock.patch('zproject.backends.logging.info') as m:
            result = self.client_get('/complete/saml/')
            self.assertEqual(result.status_code, 302)
            self.assertIn('login', result.url)
            m.assert_called_with("SAML authentication failed: missing RelayState.")

        # Check that POSTing the RelayState, but with missing SAMLResponse,
        # doesn't cause errors either:
        with mock.patch('zproject.backends.logging.info') as m:
            relay_state = SAMLAuthBackend.put_data_in_redis({"idp": "test_idp"})
            post_params = {"RelayState": relay_state}
            result = self.client_post('/complete/saml/',  post_params)
            self.assertEqual(result.status_code, 302)
            self.assertIn('login', result.url)
            m.assert_called_with(
                # OneLogin_Saml2_Error exception:
                "SAML Response not found, Only supported HTTP_POST Binding"
            )

        with mock.patch('zproject.backends.logging.info') as m:
            relay_state = SAMLAuthBackend.put_data_in_redis({"idp": "test_idp"})
            relay_state = relay_state[:-1]  # Break the token by removing the last character
            post_params = {"RelayState": relay_state}
            result = self.client_post('/complete/saml/',  post_params)
            self.assertEqual(result.status_code, 302)
            self.assertIn('login', result.url)
            m.assert_called_with("SAML authentication failed: bad RelayState token.")

    def test_social_auth_saml_bad_idp_param_on_login_page(self) -> None:
        with mock.patch('zproject.backends.logging.info') as m:
            result = self.client_get('/login/saml/')
            self.assertEqual(result.status_code, 302)
            self.assertEqual('/login/', result.url)
            m.assert_called_with("/login/saml/ : Bad idp param.")

        with mock.patch('zproject.backends.logging.info') as m:
            result = self.client_get('/login/saml/?idp=bad_idp')
            self.assertEqual(result.status_code, 302)
            self.assertEqual('/login/', result.url)
            m.assert_called_with("/login/saml/ : Bad idp param.")

    def test_social_auth_invalid_email(self) -> None:
        """
        This test needs an override from the original class. For security reasons,
        the 'next' and 'mobile_flow_otp' params don't get passed on in the session
        if the authentication attempt failed. See SAMLAuthBackend.auth_complete for details.
        """
        account_data_dict = self.get_account_data_dict(email="invalid", name=self.name)
        result = self.social_auth_test(account_data_dict,
                                       expect_choose_email_screen=True,
                                       subdomain='zulip', next='/user_uploads/image')
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result.url, "/login/")

    def test_social_auth_saml_multiple_idps_configured(self) -> None:
        """
        Using multiple IdPs is not supported right now, and having multiple configured
        should lead to misconfiguration page.
        """

        # Setup a new SOCIAL_AUTH_SAML_ENABLED_IDPS dict with two idps.
        # We deepcopy() dictionaries around for the sake of brevity,
        # to avoid having to spell them out explicitly here.
        # The second idp's configuration is a copy of the first one,
        # with name test_idp2 and altered url.
        idps_dict = copy.deepcopy(settings.SOCIAL_AUTH_SAML_ENABLED_IDPS)
        idps_dict['test_idp2'] = copy.deepcopy(idps_dict['test_idp'])
        idps_dict['test_idp2']['url'] = 'https://idp2.example.com/idp/profile/SAML2/Redirect/SSO'
        idps_dict['test_idp2']['display_name'] = 'Second Test IdP'

        # Run tests with multiple idps configured:
        with self.settings(SOCIAL_AUTH_SAML_ENABLED_IDPS=idps_dict):
            # Go to the login page and check that buttons to log in show up for both IdPs:
            result = self.client_get('/accounts/login/')
            self.assert_in_success_response(["Log in with Test IdP"], result)
            self.assert_in_success_response(["/accounts/login/social/saml/test_idp"], result)
            self.assert_in_success_response(["Log in with Second Test IdP"], result)
            self.assert_in_success_response(["/accounts/login/social/saml/test_idp2"], result)

            # Try succesful authentication with the regular idp from all previous tests:
            self.test_social_auth_success()

            # Now test with the second idp:
            original_LOGIN_URL = self.LOGIN_URL
            original_SIGNUP_URL = self.SIGNUP_URL
            original_AUTHORIZATION_URL = self.AUTHORIZATION_URL
            self.LOGIN_URL = "/accounts/login/social/saml/test_idp2"
            self.SIGNUP_URL = "/accounts/register/social/saml/test_idp2"
            self.AUTHORIZATION_URL = idps_dict['test_idp2']['url']

            try:
                self.test_social_auth_success()
            finally:
                # Restore original values at the end, regardless of what happens
                # in the block above, to avoid affecting other tests in unpredictable
                # ways.
                self.LOGIN_URL = original_LOGIN_URL
                self.SIGNUP_URL = original_SIGNUP_URL
                self.AUTHORIZATION_URL = original_AUTHORIZATION_URL

    def test_social_auth_saml_login_bad_idp_arg(self) -> None:
        for action in ['login', 'register']:
            result = self.client_get('/accounts/{}/social/saml'.format(action))
            # Missing idp argument.
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result.url, '/config-error/saml')

            result = self.client_get('/accounts/{}/social/saml/nonexistent_idp'.format(action))
            # No such IdP is configured.
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result.url, '/config-error/saml')

            result = self.client_get('/accounts/{}/social/saml/'.format(action))
            # No matching url pattern.
            self.assertEqual(result.status_code, 404)

class GitHubAuthBackendTest(SocialAuthBase):
    __unittest_skip__ = False

    BACKEND_CLASS = GitHubAuthBackend
    CLIENT_KEY_SETTING = "SOCIAL_AUTH_GITHUB_KEY"
    LOGIN_URL = "/accounts/login/social/github"
    SIGNUP_URL = "/accounts/register/social/github"
    AUTHORIZATION_URL = "https://github.com/login/oauth/authorize"
    ACCESS_TOKEN_URL = "https://github.com/login/oauth/access_token"
    USER_INFO_URL = "https://api.github.com/user"
    AUTH_FINISH_URL = "/complete/github/"
    CONFIG_ERROR_URL = "/config-error/github"

    def register_extra_endpoints(self,
                                 account_data_dict: Dict[str, str],
                                 **extra_data: Any) -> None:
        # Keeping a verified email before the primary email makes sure
        # get_verified_emails puts the primary email at the start of the
        # email list returned as social_associate_user_helper assumes the
        # first email as the primary email.
        email_data = [
            dict(email="notprimary@example.com",
                 verified=True),
            dict(email=account_data_dict["email"],
                 verified=True,
                 primary=True),
            dict(email="ignored@example.com",
                 verified=False),
        ]
        email_data = extra_data.get("email_data", email_data)

        httpretty.register_uri(
            httpretty.GET,
            "https://api.github.com/user/emails",
            status=200,
            body=json.dumps(email_data)
        )

        httpretty.register_uri(
            httpretty.GET,
            "https://api.github.com/teams/zulip-webapp/members/None",
            status=200,
            body=json.dumps(email_data)
        )

        self.email_data = email_data

    def get_account_data_dict(self, email: str, name: str) -> Dict[str, Any]:
        return dict(email=email, name=name)

    def test_social_auth_email_not_verified(self) -> None:
        account_data_dict = self.get_account_data_dict(email=self.email, name=self.name)
        email_data = [
            dict(email=account_data_dict["email"],
                 verified=False,
                 primary=True),
        ]
        with mock.patch('logging.warning') as mock_warning:
            result = self.social_auth_test(account_data_dict,
                                           subdomain='zulip',
                                           email_data=email_data)
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result.url, "/login/")
            mock_warning.assert_called_once_with("Social auth (GitHub) failed "
                                                 "because user has no verified emails")

    @override_settings(SOCIAL_AUTH_GITHUB_TEAM_ID='zulip-webapp')
    def test_social_auth_github_team_not_member_failed(self) -> None:
        account_data_dict = self.get_account_data_dict(email=self.email, name=self.name)
        with mock.patch('social_core.backends.github.GithubTeamOAuth2.user_data',
                        side_effect=AuthFailed('Not found')), \
                mock.patch('logging.info') as mock_info:
            result = self.social_auth_test(account_data_dict,
                                           subdomain='zulip')
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result.url, "/login/")
            mock_info.assert_called_once_with("GitHub user is not member of required team")

    @override_settings(SOCIAL_AUTH_GITHUB_TEAM_ID='zulip-webapp')
    def test_social_auth_github_team_member_success(self) -> None:
        account_data_dict = self.get_account_data_dict(email=self.email, name=self.name)
        with mock.patch('social_core.backends.github.GithubTeamOAuth2.user_data',
                        return_value=account_data_dict):
            result = self.social_auth_test(account_data_dict,
                                           expect_choose_email_screen=True,
                                           subdomain='zulip')
        data = load_subdomain_token(result)
        self.assertEqual(data['email'], self.example_email("hamlet"))
        self.assertEqual(data['name'], self.name)
        self.assertEqual(data['subdomain'], 'zulip')

    @override_settings(SOCIAL_AUTH_GITHUB_ORG_NAME='Zulip')
    def test_social_auth_github_organization_not_member_failed(self) -> None:
        account_data_dict = self.get_account_data_dict(email=self.email, name=self.name)
        with mock.patch('social_core.backends.github.GithubOrganizationOAuth2.user_data',
                        side_effect=AuthFailed('Not found')), \
                mock.patch('logging.info') as mock_info:
            result = self.social_auth_test(account_data_dict,
                                           subdomain='zulip')
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result.url, "/login/")
            mock_info.assert_called_once_with("GitHub user is not member of required organization")

    @override_settings(SOCIAL_AUTH_GITHUB_ORG_NAME='Zulip')
    def test_social_auth_github_organization_member_success(self) -> None:
        account_data_dict = self.get_account_data_dict(email=self.email, name=self.name)
        with mock.patch('social_core.backends.github.GithubOrganizationOAuth2.user_data',
                        return_value=account_data_dict):
            result = self.social_auth_test(account_data_dict,
                                           expect_choose_email_screen=True,
                                           subdomain='zulip')
        data = load_subdomain_token(result)
        self.assertEqual(data['email'], self.example_email("hamlet"))
        self.assertEqual(data['name'], self.name)
        self.assertEqual(data['subdomain'], 'zulip')

    def test_github_auth_enabled(self) -> None:
        with self.settings(AUTHENTICATION_BACKENDS=('zproject.backends.GitHubAuthBackend',)):
            self.assertTrue(github_auth_enabled())

    def test_github_oauth2_success_non_primary(self) -> None:
        account_data_dict = dict(email='nonprimary@zulip.com', name="Non Primary")
        email_data = [
            dict(email=account_data_dict["email"],
                 verified=True),
            dict(email='hamlet@zulip.com',
                 verified=True,
                 primary=True),
            dict(email="ignored@example.com",
                 verified=False),
        ]
        result = self.social_auth_test(account_data_dict,
                                       subdomain='zulip', email_data=email_data,
                                       expect_choose_email_screen=True,
                                       next='/user_uploads/image')
        data = load_subdomain_token(result)
        self.assertEqual(data['email'], 'nonprimary@zulip.com')
        self.assertEqual(data['name'], 'Non Primary')
        self.assertEqual(data['subdomain'], 'zulip')
        self.assertEqual(data['next'], '/user_uploads/image')
        self.assertEqual(result.status_code, 302)
        parsed_url = urllib.parse.urlparse(result.url)
        uri = "{}://{}{}".format(parsed_url.scheme, parsed_url.netloc,
                                 parsed_url.path)
        self.assertTrue(uri.startswith('http://zulip.testserver/accounts/login/subdomain/'))

    def test_github_oauth2_success_single_email(self) -> None:
        # If the user has a single email associated with its GitHub account,
        # the choose email screen should not be shown and the first email
        # should be used for user's signup/login.
        account_data_dict = dict(email='not-hamlet@zulip.com', name=self.name)
        email_data = [
            dict(email='hamlet@zulip.com',
                 verified=True,
                 primary=True),
        ]
        result = self.social_auth_test(account_data_dict,
                                       subdomain='zulip',
                                       email_data=email_data,
                                       expect_choose_email_screen=False,
                                       next='/user_uploads/image')
        data = load_subdomain_token(result)
        self.assertEqual(data['email'], self.example_email("hamlet"))
        self.assertEqual(data['name'], self.name)
        self.assertEqual(data['subdomain'], 'zulip')
        self.assertEqual(data['next'], '/user_uploads/image')
        self.assertEqual(result.status_code, 302)
        parsed_url = urllib.parse.urlparse(result.url)
        uri = "{}://{}{}".format(parsed_url.scheme, parsed_url.netloc,
                                 parsed_url.path)
        self.assertTrue(uri.startswith('http://zulip.testserver/accounts/login/subdomain/'))

    def test_github_oauth2_email_no_reply_dot_github_dot_com(self) -> None:
        # As emails ending with `noreply.github.com` are excluded from
        # verified_emails, choosing it as an email should raise a `email
        # not associated` warning.
        account_data_dict = dict(email="hamlet@users.noreply.github.com", name=self.name)
        email_data = [
            dict(email="notprimary@zulip.com",
                 verified=True),
            dict(email="hamlet@zulip.com",
                 verified=True,
                 primary=True),
            dict(email=account_data_dict["email"],
                 verified=True),
        ]
        with mock.patch('logging.warning') as mock_warning:
            result = self.social_auth_test(account_data_dict,
                                           subdomain='zulip',
                                           expect_choose_email_screen=True,
                                           email_data=email_data)
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result.url, "/login/")
            mock_warning.assert_called_once_with("Social auth (GitHub) failed because user has no verified"
                                                 " emails associated with the account")

    def test_github_oauth2_email_not_associated(self) -> None:
        account_data_dict = dict(email='not-associated@zulip.com', name=self.name)
        email_data = [
            dict(email='nonprimary@zulip.com',
                 verified=True,),
            dict(email='hamlet@zulip.com',
                 verified=True,
                 primary=True),
        ]
        with mock.patch('logging.warning') as mock_warning:
            result = self.social_auth_test(account_data_dict,
                                           subdomain='zulip',
                                           expect_choose_email_screen=True,
                                           email_data=email_data)
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result.url, "/login/")
            mock_warning.assert_called_once_with("Social auth (GitHub) failed because user has no verified"
                                                 " emails associated with the account")

class GoogleAuthBackendTest(SocialAuthBase):
    __unittest_skip__ = False

    BACKEND_CLASS = GoogleAuthBackend
    CLIENT_KEY_SETTING = "SOCIAL_AUTH_GOOGLE_KEY"
    LOGIN_URL = "/accounts/login/social/google"
    SIGNUP_URL = "/accounts/register/social/google"
    AUTHORIZATION_URL = "https://accounts.google.com/o/oauth2/auth"
    ACCESS_TOKEN_URL = "https://accounts.google.com/o/oauth2/token"
    USER_INFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
    AUTH_FINISH_URL = "/complete/google/"
    CONFIG_ERROR_URL = "/config-error/google"

    def get_account_data_dict(self, email: str, name: str) -> Dict[str, Any]:
        return dict(email=email, name=name, email_verified=True)

    def test_social_auth_email_not_verified(self) -> None:
        account_data_dict = dict(email=self.email, name=self.name)
        with mock.patch('logging.warning') as mock_warning:
            result = self.social_auth_test(account_data_dict,
                                           subdomain='zulip')
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result.url, "/login/")
            mock_warning.assert_called_once_with("Social auth (Google) failed "
                                                 "because user has no verified emails")

    def test_social_auth_mobile_success_legacy_url(self) -> None:
        mobile_flow_otp = '1234abcd' * 8
        account_data_dict = self.get_account_data_dict(email=self.email, name='Full Name')
        self.assertEqual(len(mail.outbox), 0)
        self.user_profile.date_joined = timezone_now() - datetime.timedelta(seconds=JUST_CREATED_THRESHOLD + 1)
        self.user_profile.save()

        with self.settings(SEND_LOGIN_EMAILS=True):
            # Verify that the right thing happens with an invalid-format OTP
            result = self.social_auth_test(account_data_dict, subdomain='zulip',
                                           alternative_start_url="/accounts/login/google/",
                                           mobile_flow_otp="1234")
            self.assert_json_error(result, "Invalid OTP")
            result = self.social_auth_test(account_data_dict, subdomain='zulip',
                                           alternative_start_url="/accounts/login/google/",
                                           mobile_flow_otp="invalido" * 8)
            self.assert_json_error(result, "Invalid OTP")

            # Now do it correctly
            result = self.social_auth_test(account_data_dict, subdomain='zulip',
                                           expect_choose_email_screen=True,
                                           alternative_start_url="/accounts/login/google/",
                                           mobile_flow_otp=mobile_flow_otp)
        self.assertEqual(result.status_code, 302)
        redirect_url = result['Location']
        parsed_url = urllib.parse.urlparse(redirect_url)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        self.assertEqual(parsed_url.scheme, 'zulip')
        self.assertEqual(query_params["realm"], ['http://zulip.testserver'])
        self.assertEqual(query_params["email"], [self.example_email("hamlet")])
        encrypted_api_key = query_params["otp_encrypted_api_key"][0]
        hamlet_api_keys = get_all_api_keys(self.example_user('hamlet'))
        self.assertIn(otp_decrypt_api_key(encrypted_api_key, mobile_flow_otp), hamlet_api_keys)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Zulip on Android', mail.outbox[0].body)

    def test_google_auth_enabled(self) -> None:
        with self.settings(AUTHENTICATION_BACKENDS=('zproject.backends.GoogleAuthBackend',)):
            self.assertTrue(google_auth_enabled())

    def get_log_into_subdomain(self, data: Dict[str, Any], *, key: Optional[str]=None, subdomain: str='zulip') -> HttpResponse:
        token = signing.dumps(data, salt=_subdomain_token_salt, key=key)
        url_path = reverse('zerver.views.auth.log_into_subdomain', args=[token])
        return self.client_get(url_path, subdomain=subdomain)

    def test_redirect_to_next_url_for_log_into_subdomain(self) -> None:
        def test_redirect_to_next_url(next: str='') -> HttpResponse:
            data = {'name': 'Hamlet',
                    'email': self.example_email("hamlet"),
                    'subdomain': 'zulip',
                    'is_signup': False,
                    'next': next}
            user_profile = self.example_user('hamlet')
            with mock.patch(
                    'zerver.views.auth.authenticate_remote_user',
                    return_value=user_profile):
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

    def test_log_into_subdomain_when_is_signup_is_true_and_new_user(self) -> None:
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
        self.assert_in_response("We just need you to do one last thing", result)

        # Verify that the user is asked for name but not password
        self.assert_not_in_success_response(['id_password'], result)
        self.assert_in_success_response(['id_full_name'], result)

    def test_log_into_subdomain_when_is_signup_is_false_and_new_user(self) -> None:
        data = {'name': 'New User Name',
                'email': 'new@zulip.com',
                'subdomain': 'zulip',
                'is_signup': False,
                'next': ''}
        result = self.get_log_into_subdomain(data)
        self.assertEqual(result.status_code, 200)
        self.assert_in_response('No account found for', result)
        self.assert_in_response('new@zulip.com.', result)
        self.assert_in_response('action="http://zulip.testserver/accounts/do_confirm/', result)

        url = re.findall('action="(http://zulip.testserver/accounts/do_confirm[^"]*)"', result.content.decode('utf-8'))[0]
        confirmation = Confirmation.objects.all().first()
        confirmation_key = confirmation.confirmation_key
        self.assertIn('do_confirm/' + confirmation_key, url)
        result = self.client_get(url)
        self.assert_in_response('action="/accounts/register/"', result)
        data = {"from_confirmation": "1",
                "full_name": data['name'],
                "key": confirmation_key}
        result = self.client_post('/accounts/register/', data, subdomain="zulip")
        self.assert_in_response("We just need you to do one last thing", result)

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
        create_confirmation_link(multiuse_obj, realm.host, Confirmation.MULTIUSE_INVITE)
        multiuse_confirmation = Confirmation.objects.all().last()
        multiuse_object_key = multiuse_confirmation.confirmation_key

        data["multiuse_object_key"] = multiuse_object_key
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
        self.assert_in_response("We just need you to do one last thing", result)

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
            self.assert_in_success_response(["You need an invitation to join this organization."], result)

    def test_user_cannot_log_into_wrong_subdomain_with_cookie(self) -> None:
        data = {'name': 'Full Name',
                'email': self.example_email("hamlet"),
                'subdomain': 'zephyr'}
        with mock.patch('logging.warning') as mock_warning:
            result = self.get_log_into_subdomain(data)
            mock_warning.assert_called_with("Login attempt on invalid subdomain")
        self.assertEqual(result.status_code, 400)

class JSONFetchAPIKeyTest(ZulipTestCase):
    def setUp(self) -> None:
        super().setUp()
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
        super().setUp()
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

    def test_password_auth_disabled(self) -> None:
        with mock.patch('zproject.backends.password_auth_enabled', return_value=False):
            result = self.client_post("/api/v1/fetch_api_key",
                                      dict(username=self.email,
                                           password=initial_password(self.email)))
            self.assert_json_error_contains(result, "Password auth is disabled", 403)

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_ldap_auth_email_auth_disabled_success(self) -> None:
        self.init_default_ldap_database()
        with self.settings(LDAP_APPEND_DOMAIN='zulip.com'):
            result = self.client_post("/api/v1/fetch_api_key",
                                      dict(username=self.example_email('hamlet'),
                                           password=self.ldap_password()))
        self.assert_json_success(result)

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
        super().setUp()
        self.user_profile = self.example_user('hamlet')
        self.email = self.user_profile.email

    def test_success(self) -> None:
        result = self.client_post("/api/v1/dev_fetch_api_key",
                                  dict(username=self.email))
        self.assert_json_success(result)
        data = result.json()
        self.assertEqual(data["email"], self.email)
        user_api_keys = get_all_api_keys(self.user_profile)
        self.assertIn(data['api_key'], user_api_keys)

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

class ExternalMethodDictsTests(ZulipTestCase):
    def test_get_external_method_dicts_correctly_sorted(self) -> None:
        with self.settings(
            AUTHENTICATION_BACKENDS=('zproject.backends.EmailAuthBackend',
                                     'zproject.backends.GitHubAuthBackend',
                                     'zproject.backends.GoogleAuthBackend',
                                     'zproject.backends.ZulipRemoteUserBackend',
                                     'zproject.backends.SAMLAuthBackend',
                                     'zproject.backends.AzureADAuthBackend')
        ):
            external_auth_methods = get_external_method_dicts()
            # First backends in the list should be SAML:
            self.assertIn('saml:', external_auth_methods[0]['name'])
            self.assertEqual(
                [social_backend['name'] for social_backend in external_auth_methods[1:]],
                [social_backend.name for social_backend in sorted(
                    [ZulipRemoteUserBackend, GitHubAuthBackend, AzureADAuthBackend, GoogleAuthBackend],
                    key=lambda x: x.sort_order,
                    reverse=True
                )]
            )

class FetchAuthBackends(ZulipTestCase):
    def assert_on_error(self, error: Optional[str]) -> None:
        if error:
            raise AssertionError(error)

    def test_get_server_settings(self) -> None:
        def check_result(result: HttpResponse, extra_fields: List[Tuple[str, Validator]]=[]) -> None:
            authentication_methods_list = [
                ('password', check_bool),
            ]
            for backend_name_with_case in AUTH_BACKEND_NAME_MAP:
                authentication_methods_list.append((backend_name_with_case.lower(), check_bool))
            external_auth_methods = get_external_method_dicts()

            self.assert_json_success(result)
            checker = check_dict_only([
                ('authentication_methods', check_dict_only(authentication_methods_list)),
                ('external_authentication_methods', check_list(None, length=len(external_auth_methods))),
                ('email_auth_enabled', check_bool),
                ('is_incompatible', check_bool),
                ('require_email_format_usernames', check_bool),
                ('realm_uri', check_string),
                ('zulip_version', check_string),
                ('push_notifications_enabled', check_bool),
                ('msg', check_string),
                ('result', check_string),
            ] + extra_fields)
            self.assert_on_error(checker("data", result.json()))

        result = self.client_get("/api/v1/server_settings", subdomain="", HTTP_USER_AGENT="")
        check_result(result)
        self.assertEqual(result.json()['external_authentication_methods'], get_external_method_dicts())

        result = self.client_get("/api/v1/server_settings", subdomain="", HTTP_USER_AGENT="ZulipInvalid")
        self.assertTrue(result.json()["is_incompatible"])

        with self.settings(ROOT_DOMAIN_LANDING_PAGE=False):
            result = self.client_get("/api/v1/server_settings", subdomain="", HTTP_USER_AGENT="")
        check_result(result)

        with self.settings(ROOT_DOMAIN_LANDING_PAGE=False):
            result = self.client_get("/api/v1/server_settings", subdomain="zulip", HTTP_USER_AGENT="")
        check_result(result, [
            ('realm_name', check_string),
            ('realm_description', check_string),
            ('realm_icon', check_string),
        ])

        # Verify invalid subdomain
        result = self.client_get("/api/v1/server_settings",
                                 subdomain="invalid")
        self.assert_json_error_contains(result, "Invalid subdomain", 400)

        with self.settings(ROOT_DOMAIN_LANDING_PAGE=True):
            # With ROOT_DOMAIN_LANDING_PAGE, homepage fails
            result = self.client_get("/api/v1/server_settings",
                                     subdomain="")
            self.assert_json_error_contains(result, "Subdomain required", 400)

class TestTwoFactor(ZulipTestCase):
    def test_direct_dev_login_with_2fa(self) -> None:
        email = self.example_email('hamlet')
        user_profile = self.example_user('hamlet')
        with self.settings(TWO_FACTOR_AUTHENTICATION_ENABLED=True):
            data = {'direct_email': email}
            result = self.client_post('/accounts/login/local/', data)
            self.assertEqual(result.status_code, 302)
            self.assert_logged_in_user_id(user_profile.id)
            # User logs in but when otp device doesn't exist.
            self.assertNotIn('otp_device_id', self.client.session.keys())

            self.create_default_device(user_profile)

            data = {'direct_email': email}
            result = self.client_post('/accounts/login/local/', data)
            self.assertEqual(result.status_code, 302)
            self.assert_logged_in_user_id(user_profile.id)
            # User logs in when otp device exists.
            self.assertIn('otp_device_id', self.client.session.keys())

    @mock.patch('two_factor.models.totp')
    def test_two_factor_login_with_ldap(self, mock_totp):
        # type: (mock.MagicMock) -> None
        token = 123456
        email = self.example_email('hamlet')
        password = self.ldap_password()

        user_profile = self.example_user('hamlet')
        user_profile.set_password(password)
        user_profile.save()
        self.create_default_device(user_profile)

        def totp(*args, **kwargs):
            # type: (*Any, **Any) -> int
            return token

        mock_totp.side_effect = totp

        # Setup LDAP
        self.init_default_ldap_database()
        ldap_user_attr_map = {'full_name': 'cn', 'short_name': 'sn'}
        with self.settings(
                AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',),
                TWO_FACTOR_CALL_GATEWAY='two_factor.gateways.fake.Fake',
                TWO_FACTOR_SMS_GATEWAY='two_factor.gateways.fake.Fake',
                TWO_FACTOR_AUTHENTICATION_ENABLED=True,
                POPULATE_PROFILE_VIA_LDAP=True,
                LDAP_APPEND_DOMAIN='zulip.com',
                AUTH_LDAP_USER_ATTR_MAP=ldap_user_attr_map,
        ):
            first_step_data = {"username": email,
                               "password": password,
                               "two_factor_login_view-current_step": "auth"}
            result = self.client_post("/accounts/login/", first_step_data)
            self.assertEqual(result.status_code, 200)

            second_step_data = {"token-otp_token": str(token),
                                "two_factor_login_view-current_step": "token"}
            result = self.client_post("/accounts/login/", second_step_data)
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result['Location'], 'http://zulip.testserver')

            # Going to login page should redirect to `realm.uri` if user is
            # already logged in.
            result = self.client_get('/accounts/login/')
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result['Location'], 'http://zulip.testserver')

class TestDevAuthBackend(ZulipTestCase):
    def test_login_success(self) -> None:
        user_profile = self.example_user('hamlet')
        email = user_profile.email
        data = {'direct_email': email}
        result = self.client_post('/accounts/login/local/', data)
        self.assertEqual(result.status_code, 302)
        self.assert_logged_in_user_id(user_profile.id)

    def test_login_success_with_2fa(self) -> None:
        user_profile = self.example_user('hamlet')
        self.create_default_device(user_profile)
        email = user_profile.email
        data = {'direct_email': email}
        with self.settings(TWO_FACTOR_AUTHENTICATION_ENABLED=True):
            result = self.client_post('/accounts/login/local/', data)
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result.url, 'http://zulip.testserver')
        self.assert_logged_in_user_id(user_profile.id)
        self.assertIn('otp_device_id', list(self.client.session.keys()))

    def test_redirect_to_next_url(self) -> None:
        def do_local_login(formaction: str) -> HttpResponse:
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
        self.assert_logged_in_user_id(user_profile.id)

    def test_choose_realm(self) -> None:
        result = self.client_post('/devlogin/', subdomain="zulip")
        self.assertEqual(result.status_code, 200)
        self.assert_in_success_response(["Click on a user to log in to Zulip Dev!"], result)
        self.assert_in_success_response(["iago@zulip.com", "hamlet@zulip.com"], result)

        result = self.client_post('/devlogin/', subdomain="")
        self.assertEqual(result.status_code, 200)
        self.assert_in_success_response(["Click on a user to log in!"], result)
        self.assert_in_success_response(["iago@zulip.com", "hamlet@zulip.com"], result)
        self.assert_in_success_response(["starnine@mit.edu", "espuser@mit.edu"], result)

        result = self.client_post('/devlogin/', {'new_realm': 'all_realms'},
                                  subdomain="zephyr")
        self.assertEqual(result.status_code, 200)
        self.assert_in_success_response(["starnine@mit.edu", "espuser@mit.edu"], result)
        self.assert_in_success_response(["Click on a user to log in!"], result)
        self.assert_in_success_response(["iago@zulip.com", "hamlet@zulip.com"], result)

        data = {'new_realm': 'zephyr'}
        result = self.client_post('/devlogin/', data, subdomain="zulip")
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result.url, "http://zephyr.testserver")

        result = self.client_get('/devlogin/', subdomain="zephyr")
        self.assertEqual(result.status_code, 200)
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
            self.assert_logged_in_user_id(user_profile.id)

    def test_login_success_with_sso_append_domain(self) -> None:
        username = 'hamlet'
        user_profile = self.example_user('hamlet')
        with self.settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipRemoteUserBackend',),
                           SSO_APPEND_DOMAIN='zulip.com'):
            result = self.client_post('/accounts/login/sso/', REMOTE_USER=username)
            self.assertEqual(result.status_code, 302)
            self.assert_logged_in_user_id(user_profile.id)

    def test_login_failure(self) -> None:
        email = self.example_email("hamlet")
        result = self.client_post('/accounts/login/sso/', REMOTE_USER=email)
        self.assertEqual(result.status_code, 302)

        result = self.client_get(result["Location"])
        self.assert_in_response("Authentication via the REMOTE_USER header is", result)
        self.assert_logged_in_user_id(None)

    def test_login_failure_due_to_nonexisting_user(self) -> None:
        email = 'nonexisting@zulip.com'
        with self.settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipRemoteUserBackend',)):
            result = self.client_post('/accounts/login/sso/', REMOTE_USER=email)
            self.assertEqual(result.status_code, 200)
            self.assert_logged_in_user_id(None)
            self.assert_in_response("No account found for", result)

    def test_login_failure_due_to_invalid_email(self) -> None:
        email = 'hamlet'
        with self.settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipRemoteUserBackend',)):
            result = self.client_post('/accounts/login/sso/', REMOTE_USER=email)
            self.assert_json_error_contains(result, "Enter a valid email address.", 400)

    def test_login_failure_due_to_missing_field(self) -> None:
        with self.settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipRemoteUserBackend',)):
            result = self.client_post('/accounts/login/sso/')
            self.assertEqual(result.status_code, 302)

            result = self.client_get(result["Location"])
            self.assert_in_response("The REMOTE_USER header is not set.", result)

    def test_login_failure_due_to_wrong_subdomain(self) -> None:
        email = self.example_email("hamlet")
        with self.settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipRemoteUserBackend',)):
            with mock.patch('zerver.views.auth.get_subdomain', return_value='acme'):
                result = self.client_post('http://testserver:9080/accounts/login/sso/',
                                          REMOTE_USER=email)
                self.assertEqual(result.status_code, 200)
                self.assert_logged_in_user_id(None)
                self.assert_in_response("You need an invitation to join this organization.", result)

    def test_login_failure_due_to_empty_subdomain(self) -> None:
        email = self.example_email("hamlet")
        with self.settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipRemoteUserBackend',)):
            with mock.patch('zerver.views.auth.get_subdomain', return_value=''):
                result = self.client_post('http://testserver:9080/accounts/login/sso/',
                                          REMOTE_USER=email)
                self.assertEqual(result.status_code, 200)
                self.assert_logged_in_user_id(None)
                self.assert_in_response("You need an invitation to join this organization.", result)

    def test_login_success_under_subdomains(self) -> None:
        user_profile = self.example_user('hamlet')
        email = user_profile.email
        with mock.patch('zerver.views.auth.get_subdomain', return_value='zulip'):
            with self.settings(
                    AUTHENTICATION_BACKENDS=('zproject.backends.ZulipRemoteUserBackend',)):
                result = self.client_post('/accounts/login/sso/', REMOTE_USER=email)
                self.assertEqual(result.status_code, 302)
                self.assert_logged_in_user_id(user_profile.id)

    @override_settings(SEND_LOGIN_EMAILS=True)
    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipRemoteUserBackend',))
    def test_login_mobile_flow_otp_success_email(self) -> None:
        user_profile = self.example_user('hamlet')
        email = user_profile.email
        user_profile.date_joined = timezone_now() - datetime.timedelta(seconds=61)
        user_profile.save()
        mobile_flow_otp = '1234abcd' * 8

        # Verify that the right thing happens with an invalid-format OTP
        result = self.client_post('/accounts/login/sso/',
                                  dict(mobile_flow_otp="1234"),
                                  REMOTE_USER=email,
                                  HTTP_USER_AGENT = "ZulipAndroid")
        self.assert_logged_in_user_id(None)
        self.assert_json_error_contains(result, "Invalid OTP", 400)

        result = self.client_post('/accounts/login/sso/',
                                  dict(mobile_flow_otp="invalido" * 8),
                                  REMOTE_USER=email,
                                  HTTP_USER_AGENT = "ZulipAndroid")
        self.assert_logged_in_user_id(None)
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
        hamlet_api_keys = get_all_api_keys(self.example_user('hamlet'))
        self.assertIn(otp_decrypt_api_key(encrypted_api_key, mobile_flow_otp), hamlet_api_keys)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Zulip on Android', mail.outbox[0].body)

    @override_settings(SEND_LOGIN_EMAILS=True)
    @override_settings(SSO_APPEND_DOMAIN="zulip.com")
    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipRemoteUserBackend',))
    def test_login_mobile_flow_otp_success_username(self) -> None:
        user_profile = self.example_user('hamlet')
        email = user_profile.email
        remote_user = email_to_username(email)
        user_profile.date_joined = timezone_now() - datetime.timedelta(seconds=61)
        user_profile.save()
        mobile_flow_otp = '1234abcd' * 8

        # Verify that the right thing happens with an invalid-format OTP
        result = self.client_post('/accounts/login/sso/',
                                  dict(mobile_flow_otp="1234"),
                                  REMOTE_USER=remote_user,
                                  HTTP_USER_AGENT = "ZulipAndroid")
        self.assert_logged_in_user_id(None)
        self.assert_json_error_contains(result, "Invalid OTP", 400)

        result = self.client_post('/accounts/login/sso/',
                                  dict(mobile_flow_otp="invalido" * 8),
                                  REMOTE_USER=remote_user,
                                  HTTP_USER_AGENT = "ZulipAndroid")
        self.assert_logged_in_user_id(None)
        self.assert_json_error_contains(result, "Invalid OTP", 400)

        result = self.client_post('/accounts/login/sso/',
                                  dict(mobile_flow_otp=mobile_flow_otp),
                                  REMOTE_USER=remote_user,
                                  HTTP_USER_AGENT = "ZulipAndroid")
        self.assertEqual(result.status_code, 302)
        redirect_url = result['Location']
        parsed_url = urllib.parse.urlparse(redirect_url)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        self.assertEqual(parsed_url.scheme, 'zulip')
        self.assertEqual(query_params["realm"], ['http://zulip.testserver'])
        self.assertEqual(query_params["email"], [self.example_email("hamlet")])
        encrypted_api_key = query_params["otp_encrypted_api_key"][0]
        hamlet_api_keys = get_all_api_keys(self.example_user('hamlet'))
        self.assertIn(otp_decrypt_api_key(encrypted_api_key, mobile_flow_otp), hamlet_api_keys)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Zulip on Android', mail.outbox[0].body)

    def test_redirect_to(self) -> None:
        """This test verifies the behavior of the redirect_to logic in
        login_or_register_remote_user."""
        def test_with_redirect_to_param_set_as_next(next: str='') -> HttpResponse:
            user_profile = self.example_user('hamlet')
            email = user_profile.email
            with self.settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipRemoteUserBackend',)):
                result = self.client_post('/accounts/login/sso/?next=' + next, REMOTE_USER=email)
            return result

        res = test_with_redirect_to_param_set_as_next()
        self.assertEqual('http://zulip.testserver', res.url)
        res = test_with_redirect_to_param_set_as_next('/user_uploads/image_path')
        self.assertEqual('http://zulip.testserver/user_uploads/image_path', res.url)

        # Third-party domains are rejected and just send you to root domain
        res = test_with_redirect_to_param_set_as_next('https://rogue.zulip-like.server/login')
        self.assertEqual('http://zulip.testserver', res.url)

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
            self.assert_logged_in_user_id(user_profile.id)

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
            self.assert_logged_in_user_id(None)

            # The /accounts/login/jwt/ endpoint should also handle the case
            # where the authentication attempt throws UserProfile.DoesNotExist.
            with mock.patch(
                    'zerver.views.auth.authenticate',
                    side_effect=UserProfile.DoesNotExist("Do not exist")):
                result = self.client_post('/accounts/login/jwt/', data)
            self.assertEqual(result.status_code, 200)  # This should ideally be not 200.
            self.assert_logged_in_user_id(None)

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
                self.assert_logged_in_user_id(None)

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
                self.assert_logged_in_user_id(None)

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
                self.assert_logged_in_user_id(user_profile.id)

class DjangoToLDAPUsernameTests(ZulipTestCase):
    def setUp(self) -> None:
        self.init_default_ldap_database()
        self.backend = ZulipLDAPAuthBackend()

    def test_django_to_ldap_username_with_append_domain(self) -> None:
        with self.settings(LDAP_APPEND_DOMAIN="zulip.com"):
            self.assertEqual(self.backend.django_to_ldap_username("hamlet"), "hamlet")
            self.assertEqual(self.backend.django_to_ldap_username("hamlet@zulip.com"), "hamlet")
            with self.assertRaisesRegex(ZulipLDAPExceptionOutsideDomain,
                                        'Email hamlet@example.com does not match LDAP domain zulip.com.'):
                self.backend.django_to_ldap_username("hamlet@example.com")

            self.mock_ldap.directory['uid="hamlet@test",ou=users,dc=zulip,dc=com'] = {
                "cn": ["King Hamlet"],
                "uid": ['"hamlet@test"'],
            }
            username = self.backend.django_to_ldap_username('"hamlet@test"@zulip.com')
            self.assertEqual(username, '"hamlet@test"')

            self.mock_ldap.directory['uid="hamlet@test"@zulip,ou=users,dc=zulip,dc=com'] = {
                "cn": ["King Hamlet"],
                "uid": ['"hamlet@test"@zulip'],
            }
            username = self.backend.django_to_ldap_username('"hamlet@test"@zulip')
            self.assertEqual(username, '"hamlet@test"@zulip')

    def test_django_to_ldap_username_with_email_search(self) -> None:
        self.assertEqual(self.backend.django_to_ldap_username("hamlet"),
                         self.ldap_username("hamlet"))
        self.assertEqual(self.backend.django_to_ldap_username("hamlet@zulip.com"),
                         self.ldap_username("hamlet"))
        # If there are no matches through the email search, raise exception:
        with self.assertRaises(ZulipLDAPExceptionNoMatchingLDAPUser):
            self.backend.django_to_ldap_username("no_such_email@example.com")

        self.assertEqual(self.backend.django_to_ldap_username("aaron@zulip.com"),
                         self.ldap_username("aaron"))

        with mock.patch("zproject.backends.logging.warning") as mock_warn:
            with self.assertRaises(ZulipLDAPExceptionNoMatchingLDAPUser):
                self.backend.django_to_ldap_username("shared_email@zulip.com")
            mock_warn.assert_called_with("Multiple users with email shared_email@zulip.com found in LDAP.")

        # Test on a weird case of a user whose uid is an email and his actual "mail"
        # attribute is a different email address:
        self.mock_ldap.directory['uid=some_user@organization_a.com,ou=users,dc=zulip,dc=com'] = {
            "cn": ["Some User"],
            "uid": ['some_user@organization_a.com'],
            "mail": ["some_user@contactaddress.com"]
        }
        self.assertEqual(self.backend.django_to_ldap_username("some_user@contactaddress.com"),
                         "some_user@organization_a.com")
        self.assertEqual(self.backend.django_to_ldap_username("some_user@organization_a.com"),
                         "some_user@organization_a.com")

        # Configure email search for emails in the uid attribute:
        with self.settings(AUTH_LDAP_REVERSE_EMAIL_SEARCH=LDAPSearch("ou=users,dc=zulip,dc=com",
                                                                     ldap.SCOPE_ONELEVEL,
                                                                     "(uid=%(email)s)")):
            self.assertEqual(self.backend.django_to_ldap_username("newuser_email_as_uid@zulip.com"),
                             "newuser_email_as_uid@zulip.com")

            self.mock_ldap.directory['uid="hamlet@test"@zulip.com",ou=users,dc=zulip,dc=com'] = {
                "cn": ["King Hamlet"],
                "uid": ['"hamlet@test"@zulip.com'],
            }
            username = self.backend.django_to_ldap_username('"hamlet@test"@zulip.com')
            self.assertEqual(username, '"hamlet@test"@zulip.com')

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.EmailAuthBackend',
                                                'zproject.backends.ZulipLDAPAuthBackend',))
    def test_authenticate_to_ldap_via_email(self) -> None:
        """
        With AUTH_LDAP_REVERSE_EMAIL_SEARCH configured, django_to_ldap_username
        should be able to translate an email to ldap username,
        and thus it should be possible to authenticate through user_profile.email.
        """
        realm = get_realm("zulip")
        user_profile = self.example_user("hamlet")
        password = "testpassword"
        user_profile.set_password(password)
        user_profile.save()

        with self.settings(LDAP_EMAIL_ATTR='mail'):
            self.assertEqual(
                authenticate(username=user_profile.email, password=self.ldap_password(), realm=realm),
                user_profile)

    @override_settings(LDAP_EMAIL_ATTR='mail', LDAP_DEACTIVATE_NON_MATCHING_USERS=True)
    def test_sync_user_from_ldap_with_email_attr(self) -> None:
        """In LDAP configurations with LDAP_EMAIL_ATTR configured and
        LDAP_DEACTIVATE_NON_MATCHING_USERS set, a possible failure
        mode if django_to_ldap_username isn't configured correctly is
        all LDAP users having their accounts deactivated.  Before the
        introduction of AUTH_LDAP_REVERSE_EMAIL_SEARCH, this would happen
        even in valid LDAP configurations using LDAP_EMAIL_ATTR.

        This test confirms that such a failure mode doesn't happen with
        a valid LDAP configuration.
        """

        user_profile = self.example_user("hamlet")
        with self.settings():
            sync_user_from_ldap(user_profile, mock.Mock())
            # Syncing didn't deactivate the user:
            self.assertTrue(user_profile.is_active)

class ZulipLDAPTestCase(ZulipTestCase):
    def setUp(self) -> None:
        super().setUp()

        self.init_default_ldap_database()

        user_profile = self.example_user('hamlet')
        self.setup_subdomain(user_profile)
        self.backend = ZulipLDAPAuthBackend()

        # Internally `_realm` and `_prereg_user` attributes are automatically set
        # by the `authenticate()` method. But for testing the `get_or_build_user()`
        # method separately, we need to set them manually.
        self.backend._realm = get_realm('zulip')
        self.backend._prereg_user = None

    def setup_subdomain(self, user_profile: UserProfile) -> None:
        realm = user_profile.realm
        realm.string_id = 'zulip'
        realm.save()

class TestLDAP(ZulipLDAPTestCase):
    def test_generate_dev_ldap_dir(self) -> None:
        ldap_dir = generate_dev_ldap_dir('A', 10)
        self.assertEqual(len(ldap_dir), 10)
        regex = re.compile(r'(uid\=)+[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+(\,ou\=users\,dc\=zulip\,dc\=com)')
        common_attrs = ['cn', 'userPassword', 'phoneNumber', 'birthDate']
        for key, value in ldap_dir.items():
            self.assertTrue(regex.match(key))
            self.assertCountEqual(list(value.keys()), common_attrs + ['uid', 'thumbnailPhoto', 'userAccountControl'])

        ldap_dir = generate_dev_ldap_dir('b', 9)
        self.assertEqual(len(ldap_dir), 9)
        regex = re.compile(r'(uid\=)+[a-zA-Z0-9_.+-]+(\,ou\=users\,dc\=zulip\,dc\=com)')
        for key, value in ldap_dir.items():
            self.assertTrue(regex.match(key))
            self.assertCountEqual(list(value.keys()), common_attrs + ['uid', 'jpegPhoto'])

        ldap_dir = generate_dev_ldap_dir('c', 8)
        self.assertEqual(len(ldap_dir), 8)
        regex = re.compile(r'(uid\=)+[a-zA-Z0-9_.+-]+(\,ou\=users\,dc\=zulip\,dc\=com)')
        for key, value in ldap_dir.items():
            self.assertTrue(regex.match(key))
            self.assertCountEqual(list(value.keys()), common_attrs + ['uid', 'email'])

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_dev_ldap_fail_login(self) -> None:
        # Tests that login with a substring of password fails. We had a bug in
        # dev LDAP environment that allowed login via password substrings.
        self.mock_ldap.directory = generate_dev_ldap_dir('B', 8)
        with self.settings(
            AUTH_LDAP_USER_SEARCH = LDAPSearch("ou=users,dc=zulip,dc=com",
                                               ldap.SCOPE_ONELEVEL, "(uid=%(user)s)"),
            AUTH_LDAP_REVERSE_EMAIL_SEARCH = LDAPSearch("ou=users,dc=zulip,dc=com",
                                                        ldap.SCOPE_ONELEVEL, "(email=%(email)s)"),
            LDAP_APPEND_DOMAIN='zulip.com'
        ):
            user_profile = self.backend.authenticate(username='ldapuser1', password='dapu',
                                                     realm=get_realm('zulip'))

            assert(user_profile is None)

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_login_success(self) -> None:
        with self.settings(LDAP_APPEND_DOMAIN='zulip.com'):
            user_profile = self.backend.authenticate(username=self.example_email("hamlet"), password=self.ldap_password(),
                                                     realm=get_realm('zulip'))

            assert(user_profile is not None)
            self.assertEqual(user_profile.email, self.example_email("hamlet"))

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_login_success_with_username(self) -> None:
        with self.settings(LDAP_APPEND_DOMAIN='zulip.com'):
            user_profile = self.backend.authenticate(username="hamlet", password=self.ldap_password(),
                                                     realm=get_realm('zulip'))

            assert(user_profile is not None)
            self.assertEqual(user_profile, self.example_user("hamlet"))

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_login_success_with_email_attr(self) -> None:
        with self.settings(LDAP_EMAIL_ATTR='mail'):
            user_profile = self.backend.authenticate(username=self.ldap_username("aaron"),
                                                     password=self.ldap_password(),
                                                     realm=get_realm('zulip'))

            assert (user_profile is not None)
            self.assertEqual(user_profile, self.example_user("aaron"))

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.EmailAuthBackend',
                                                'zproject.backends.ZulipLDAPAuthBackend',))
    def test_email_and_ldap_backends_together(self) -> None:
        with self.settings(
            LDAP_EMAIL_ATTR='mail',
            AUTH_LDAP_REVERSE_EMAIL_SEARCH = LDAPSearch("ou=users,dc=zulip,dc=com",
                                                        ldap.SCOPE_ONELEVEL,
                                                        "(mail=%(email)s)"),
            AUTH_LDAP_USERNAME_ATTR = "uid"
        ):
            realm = get_realm('zulip')
            self.assertEqual(email_belongs_to_ldap(realm, self.example_email("aaron")), True)
            user_profile = ZulipLDAPAuthBackend().authenticate(username=self.ldap_username("aaron"),
                                                               password=self.ldap_password(),
                                                               realm=realm)
            self.assertEqual(user_profile, self.example_user("aaron"))

            othello = self.example_user('othello')
            password = "testpassword"
            othello.set_password(password)
            othello.save()

            self.assertEqual(email_belongs_to_ldap(realm, othello.email), False)
            user_profile = EmailAuthBackend().authenticate(username=othello.email, password=password,
                                                           realm=realm)
            self.assertEqual(user_profile, othello)

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_login_failure_due_to_wrong_password(self) -> None:
        with self.settings(LDAP_APPEND_DOMAIN='zulip.com'):
            user = self.backend.authenticate(username=self.example_email("hamlet"), password='wrong',
                                             realm=get_realm('zulip'))
            self.assertIs(user, None)

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_login_failure_due_to_nonexistent_user(self) -> None:
        with self.settings(LDAP_APPEND_DOMAIN='zulip.com'):
            user = self.backend.authenticate(username='nonexistent@zulip.com', password=self.ldap_password(),
                                             realm=get_realm('zulip'))
            self.assertIs(user, None)

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_ldap_permissions(self) -> None:
        backend = self.backend
        self.assertFalse(backend.has_perm(None, None))
        self.assertFalse(backend.has_module_perms(None, None))
        self.assertTrue(backend.get_all_permissions(None, None) == set())
        self.assertTrue(backend.get_group_permissions(None, None) == set())

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_user_email_from_ldapuser_with_append_domain(self) -> None:
        backend = self.backend
        with self.settings(LDAP_APPEND_DOMAIN='zulip.com'):
            username = backend.user_email_from_ldapuser('this_argument_is_ignored',
                                                        _LDAPUser(self.backend, username='"hamlet@test"'))
            self.assertEqual(username, '"hamlet@test"@zulip.com')

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_get_or_build_user_when_user_exists(self) -> None:
        class _LDAPUser:
            attrs = {'fn': ['Full Name'], 'sn': ['Short Name']}

        backend = self.backend
        email = self.example_email("hamlet")
        user_profile, created = backend.get_or_build_user(str(email), _LDAPUser())
        self.assertFalse(created)
        self.assertEqual(user_profile.email, email)

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_get_or_build_user_when_user_does_not_exist(self) -> None:
        class _LDAPUser:
            attrs = {'fn': ['Full Name'], 'sn': ['Short Name']}

        ldap_user_attr_map = {'full_name': 'fn', 'short_name': 'sn'}

        with self.settings(AUTH_LDAP_USER_ATTR_MAP=ldap_user_attr_map):
            backend = self.backend
            email = 'newuser@zulip.com'
            user_profile, created = backend.get_or_build_user(email, _LDAPUser())
            self.assertTrue(created)
            self.assertEqual(user_profile.email, email)
            self.assertEqual(user_profile.full_name, 'Full Name')

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_get_or_build_user_when_user_has_invalid_name(self) -> None:
        class _LDAPUser:
            attrs = {'fn': ['<invalid name>'], 'sn': ['Short Name']}

        ldap_user_attr_map = {'full_name': 'fn', 'short_name': 'sn'}

        with self.settings(AUTH_LDAP_USER_ATTR_MAP=ldap_user_attr_map):
            backend = self.backend
            email = 'nonexisting@zulip.com'
            with self.assertRaisesRegex(Exception, "Invalid characters in name!"):
                backend.get_or_build_user(email, _LDAPUser())

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_get_or_build_user_when_realm_is_deactivated(self) -> None:
        class _LDAPUser:
            attrs = {'fn': ['Full Name'], 'sn': ['Short Name']}

        ldap_user_attr_map = {'full_name': 'fn', 'short_name': 'sn'}

        with self.settings(AUTH_LDAP_USER_ATTR_MAP=ldap_user_attr_map):
            backend = self.backend
            email = 'nonexisting@zulip.com'
            do_deactivate_realm(backend._realm)
            with self.assertRaisesRegex(Exception, 'Realm has been deactivated'):
                backend.get_or_build_user(email, _LDAPUser())

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_get_or_build_user_when_ldap_has_no_email_attr(self) -> None:
        class _LDAPUser:
            attrs = {'fn': ['Full Name'], 'sn': ['Short Name']}

        nonexisting_attr = 'email'
        with self.settings(LDAP_EMAIL_ATTR=nonexisting_attr):
            backend = self.backend
            email = 'nonexisting@zulip.com'
            with self.assertRaisesRegex(Exception, 'LDAP user doesn\'t have the needed email attribute'):
                backend.get_or_build_user(email, _LDAPUser())

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_get_or_build_user_email(self) -> None:
        class _LDAPUser:
            attrs = {'fn': ['Test User']}

        ldap_user_attr_map = {'full_name': 'fn'}

        with self.settings(AUTH_LDAP_USER_ATTR_MAP=ldap_user_attr_map):
            realm = self.backend._realm
            realm.emails_restricted_to_domains = False
            realm.disallow_disposable_email_addresses = True
            realm.save()

            email = 'spam@mailnator.com'
            with self.assertRaisesRegex(ZulipLDAPException, 'Email validation failed.'):
                self.backend.get_or_build_user(email, _LDAPUser())

            realm.emails_restricted_to_domains = True
            realm.save(update_fields=['emails_restricted_to_domains'])

            email = 'spam+spam@mailnator.com'
            with self.assertRaisesRegex(ZulipLDAPException, 'Email validation failed.'):
                self.backend.get_or_build_user(email, _LDAPUser())

            email = 'spam@acme.com'
            with self.assertRaisesRegex(ZulipLDAPException, "This email domain isn't allowed in this organization."):
                self.backend.get_or_build_user(email, _LDAPUser())

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_get_or_build_user_when_ldap_has_no_full_name_mapping(self) -> None:
        class _LDAPUser:
            attrs = {'fn': ['Full Name'], 'sn': ['Short Name']}

        with self.settings(AUTH_LDAP_USER_ATTR_MAP={}):
            backend = self.backend
            email = 'nonexisting@zulip.com'
            with self.assertRaisesRegex(Exception, "Missing required mapping for user's full name"):
                backend.get_or_build_user(email, _LDAPUser())

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_login_failure_when_domain_does_not_match(self) -> None:
        with self.settings(LDAP_APPEND_DOMAIN='acme.com'):
            user_profile = self.backend.authenticate(username=self.example_email("hamlet"),
                                                     password=self.ldap_password(),
                                                     realm=get_realm('zulip'))
            self.assertIs(user_profile, None)

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_login_success_with_different_subdomain(self) -> None:
        ldap_user_attr_map = {'full_name': 'cn', 'short_name': 'sn'}

        Realm.objects.create(string_id='acme')
        with self.settings(
                LDAP_APPEND_DOMAIN='zulip.com',
                AUTH_LDAP_USER_ATTR_MAP=ldap_user_attr_map):
            user_profile = self.backend.authenticate(username=self.example_email('hamlet'),
                                                     password=self.ldap_password(),
                                                     realm=get_realm('acme'))
            self.assertEqual(user_profile.email, self.example_email('hamlet'))

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_login_success_with_valid_subdomain(self) -> None:
        with self.settings(LDAP_APPEND_DOMAIN='zulip.com'):
            user_profile = self.backend.authenticate(username=self.example_email("hamlet"),
                                                     password=self.ldap_password(),
                                                     realm=get_realm('zulip'))
            assert(user_profile is not None)
            self.assertEqual(user_profile.email, self.example_email("hamlet"))

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_login_failure_due_to_deactivated_user(self) -> None:
        user_profile = self.example_user("hamlet")
        do_deactivate_user(user_profile)
        with self.settings(LDAP_APPEND_DOMAIN='zulip.com'):
            user_profile = self.backend.authenticate(username=self.example_email("hamlet"),
                                                     password=self.ldap_password(),
                                                     realm=get_realm('zulip'))
            self.assertIs(user_profile, None)

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    @override_settings(AUTH_LDAP_USER_ATTR_MAP={
        "full_name": "cn",
        "avatar": "jpegPhoto",
    })
    def test_login_success_when_user_does_not_exist_with_valid_subdomain(self) -> None:
        RealmDomain.objects.create(realm=self.backend._realm, domain='acme.com')
        with self.settings(LDAP_APPEND_DOMAIN='acme.com'):
            user_profile = self.backend.authenticate(username='newuser@acme.com',
                                                     password=self.ldap_password(),
                                                     realm=get_realm('zulip'))
            assert(user_profile is not None)
            self.assertEqual(user_profile.email, 'newuser@acme.com')
            self.assertEqual(user_profile.full_name, 'New LDAP fullname')
            self.assertEqual(user_profile.realm.string_id, 'zulip')

            # Verify avatar gets created
            self.assertEqual(user_profile.avatar_source, UserProfile.AVATAR_FROM_USER)
            result = self.client_get(avatar_url(user_profile))
            self.assertEqual(result.status_code, 200)

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_login_success_when_user_does_not_exist_with_split_full_name_mapping(self) -> None:
        with self.settings(
                LDAP_APPEND_DOMAIN='zulip.com',
                AUTH_LDAP_USER_ATTR_MAP={'first_name': 'sn', 'last_name': 'cn'}):
            user_profile = self.backend.authenticate(username='newuser_splitname@zulip.com',
                                                     password=self.ldap_password(),
                                                     realm=get_realm('zulip'))
            assert(user_profile is not None)
            self.assertEqual(user_profile.email, 'newuser_splitname@zulip.com')
            self.assertEqual(user_profile.full_name, 'First Last')
            self.assertEqual(user_profile.realm.string_id, 'zulip')

class TestZulipLDAPUserPopulator(ZulipLDAPTestCase):
    def test_authenticate(self) -> None:
        backend = ZulipLDAPUserPopulator()
        result = backend.authenticate(username=self.example_email("hamlet"), password=self.ldap_password(),
                                      realm=get_realm('zulip'))
        self.assertIs(result, None)

    def perform_ldap_sync(self, user_profile: UserProfile) -> None:
        with self.settings(LDAP_APPEND_DOMAIN='zulip.com'):
            result = sync_user_from_ldap(user_profile, mock.Mock())
            self.assertTrue(result)

    @mock.patch("zproject.backends.do_deactivate_user")
    def test_ldaperror_doesnt_deactivate_user(self, mock_deactivate: mock.MagicMock) -> None:
        """
        This is a test for a bug where failure to connect to LDAP in sync_user_from_ldap
        (e.g. due to invalid credentials) would cause the user to be deactivated if
        LDAP_DEACTIVATE_NON_MATCHING_USERS was True.
        Details: https://github.com/zulip/zulip/issues/13130
        """
        with self.settings(
                LDAP_DEACTIVATE_NON_MATCHING_USERS=True,
                LDAP_APPEND_DOMAIN='zulip.com',
                AUTH_LDAP_BIND_PASSWORD='wrongpass'):
            with self.assertRaises(ldap.INVALID_CREDENTIALS):
                sync_user_from_ldap(self.example_user('hamlet'), mock.Mock())
            mock_deactivate.assert_not_called()

        # Make sure other types of LDAPError won't cause deactivation either:
        with mock.patch.object(_LDAPUser, '_get_or_create_user', side_effect=ldap.LDAPError):
            with self.assertRaises(PopulateUserLDAPError):
                sync_user_from_ldap(self.example_user('hamlet'), mock.Mock())
            mock_deactivate.assert_not_called()

    @override_settings(LDAP_EMAIL_ATTR="mail")
    def test_populate_user_returns_none(self) -> None:
        with mock.patch.object(ZulipLDAPUser, 'populate_user', return_value=None):
            with self.assertRaises(PopulateUserLDAPError):
                sync_user_from_ldap(self.example_user('hamlet'), mock.Mock())

    def test_update_full_name(self) -> None:
        self.change_ldap_user_attr('hamlet', 'cn', 'New Name')

        self.perform_ldap_sync(self.example_user('hamlet'))
        hamlet = self.example_user('hamlet')
        self.assertEqual(hamlet.full_name, 'New Name')

    def test_update_with_hidden_emails(self) -> None:
        hamlet = self.example_user('hamlet')
        realm = get_realm("zulip")
        do_set_realm_property(realm, 'email_address_visibility', Realm.EMAIL_ADDRESS_VISIBILITY_ADMINS)
        hamlet.refresh_from_db()

        self.change_ldap_user_attr('hamlet', 'cn', 'New Name')
        self.perform_ldap_sync(hamlet)

        hamlet.refresh_from_db()
        self.assertEqual(hamlet.full_name, 'New Name')

    def test_update_split_full_name(self) -> None:
        self.change_ldap_user_attr('hamlet', 'cn', 'Name')
        self.change_ldap_user_attr('hamlet', 'sn', 'Full')

        with self.settings(AUTH_LDAP_USER_ATTR_MAP={'first_name': 'sn',
                                                    'last_name': 'cn'}):
            self.perform_ldap_sync(self.example_user('hamlet'))
        hamlet = self.example_user('hamlet')
        self.assertEqual(hamlet.full_name, 'Full Name')

    def test_same_full_name(self) -> None:
        with mock.patch('zerver.lib.actions.do_change_full_name') as fn:
            self.perform_ldap_sync(self.example_user('hamlet'))
            fn.assert_not_called()

    def test_too_short_name(self) -> None:
        self.change_ldap_user_attr('hamlet', 'cn', 'a')

        with self.assertRaises(ZulipLDAPException):
            self.perform_ldap_sync(self.example_user('hamlet'))

    def test_deactivate_user(self) -> None:
        self.change_ldap_user_attr('hamlet', 'userAccountControl', '2')

        with self.settings(AUTH_LDAP_USER_ATTR_MAP={'full_name': 'cn',
                                                    'userAccountControl': 'userAccountControl'}):
            self.perform_ldap_sync(self.example_user('hamlet'))
        hamlet = self.example_user('hamlet')
        self.assertFalse(hamlet.is_active)

    @mock.patch("zproject.backends.ZulipLDAPAuthBackendBase.sync_full_name_from_ldap")
    def test_dont_sync_disabled_ldap_user(self, fake_sync: mock.MagicMock) -> None:
        self.change_ldap_user_attr('hamlet', 'userAccountControl', '2')

        with self.settings(AUTH_LDAP_USER_ATTR_MAP={'full_name': 'cn',
                                                    'userAccountControl': 'userAccountControl'}):
            self.perform_ldap_sync(self.example_user('hamlet'))
            fake_sync.assert_not_called()

    def test_reactivate_user(self) -> None:
        do_deactivate_user(self.example_user('hamlet'))

        with self.settings(AUTH_LDAP_USER_ATTR_MAP={'full_name': 'cn',
                                                    'userAccountControl': 'userAccountControl'}):
            self.perform_ldap_sync(self.example_user('hamlet'))
        hamlet = self.example_user('hamlet')
        self.assertTrue(hamlet.is_active)

    def test_user_in_multiple_realms(self) -> None:
        test_realm = do_create_realm('test', 'test', False)
        hamlet = self.example_user('hamlet')
        hamlet2 = do_create_user(hamlet.email, None, test_realm, hamlet.full_name, hamlet.short_name)

        self.change_ldap_user_attr('hamlet', 'cn', 'Second Hamlet')
        expected_call_args = [hamlet2, 'Second Hamlet', None]
        with self.settings(AUTH_LDAP_USER_ATTR_MAP={'full_name': 'cn'}):
            with mock.patch('zerver.lib.actions.do_change_full_name') as f:
                self.perform_ldap_sync(hamlet2)
                f.assert_called_once_with(*expected_call_args)

                # Get the updated model and make sure the full name is changed correctly:
                hamlet2 = get_user(hamlet.email, test_realm)
                self.assertEqual(hamlet2.full_name, "Second Hamlet")
                # Now get the original hamlet and make he still has his name unchanged:
                hamlet = get_user(hamlet.email, get_realm("zulip"))
                self.assertEqual(hamlet.full_name, "King Hamlet")

    def test_user_not_found_in_ldap(self) -> None:
        with self.settings(
                LDAP_DEACTIVATE_NON_MATCHING_USERS=False,
                LDAP_APPEND_DOMAIN='zulip.com'):
            othello = self.example_user("othello")  # othello isn't in our test directory
            mock_logger = mock.MagicMock()
            result = sync_user_from_ldap(othello, mock_logger)
            mock_logger.warning.assert_called_once_with("Did not find %s in LDAP." % (othello.email,))
            self.assertFalse(result)

            do_deactivate_user(othello)
            mock_logger = mock.MagicMock()
            result = sync_user_from_ldap(othello, mock_logger)
            self.assertEqual(mock_logger.method_calls, [])  # In this case the logger shouldn't be used.
            self.assertFalse(result)

    def test_update_user_avatar(self) -> None:
        # Hamlet has jpegPhoto set in our test directory by default.
        with mock.patch('zerver.lib.upload.upload_avatar_image') as fn, \
            self.settings(AUTH_LDAP_USER_ATTR_MAP={'full_name': 'cn',
                                                   'avatar': 'jpegPhoto'}):
            self.perform_ldap_sync(self.example_user('hamlet'))
            fn.assert_called_once()
            hamlet = self.example_user('hamlet')
            self.assertEqual(hamlet.avatar_source, UserProfile.AVATAR_FROM_USER)

            # Verify that the next time we do an LDAP sync, we don't
            # end up updating this user's avatar again if the LDAP
            # data hasn't changed.
            self.perform_ldap_sync(self.example_user('hamlet'))
            fn.assert_called_once()

        # Now verify that if we do change the jpegPhoto image, we
        # will upload a new avatar.
        self.change_ldap_user_attr('hamlet', 'jpegPhoto', static_path("images/logo/zulip-icon-512x512.png"),
                                   binary=True)
        with mock.patch('zerver.lib.upload.upload_avatar_image') as fn, \
            self.settings(AUTH_LDAP_USER_ATTR_MAP={'full_name': 'cn',
                                                   'avatar': 'jpegPhoto'}):
            self.perform_ldap_sync(self.example_user('hamlet'))
            fn.assert_called_once()
            hamlet = self.example_user('hamlet')
            self.assertEqual(hamlet.avatar_source, UserProfile.AVATAR_FROM_USER)

    @use_s3_backend
    def test_update_user_avatar_for_s3(self) -> None:
        bucket = create_s3_buckets(settings.S3_AVATAR_BUCKET)[0]
        test_image_file = get_test_image_file('img.png').name
        with open(test_image_file, 'rb') as f:
            test_image_data = f.read()
        self.change_ldap_user_attr('hamlet', 'jpegPhoto', test_image_data)
        with self.settings(AUTH_LDAP_USER_ATTR_MAP={'full_name': 'cn',
                                                    'avatar': 'jpegPhoto'}):
            self.perform_ldap_sync(self.example_user('hamlet'))

        hamlet = self.example_user('hamlet')
        path_id = user_avatar_path(hamlet)
        original_image_path_id = path_id + ".original"
        medium_path_id = path_id + "-medium.png"

        original_image_key = bucket.get_key(original_image_path_id)
        medium_image_key = bucket.get_key(medium_path_id)

        image_data = original_image_key.get_contents_as_string()
        self.assertEqual(image_data, test_image_data)

        test_medium_image_data = resize_avatar(test_image_data, MEDIUM_AVATAR_SIZE)
        medium_image_data = medium_image_key.get_contents_as_string()
        self.assertEqual(medium_image_data, test_medium_image_data)

        # Try to use invalid data as the image:
        self.change_ldap_user_attr('hamlet', 'jpegPhoto', b'00' + test_image_data)
        with self.settings(AUTH_LDAP_USER_ATTR_MAP={'full_name': 'cn',
                                                    'avatar': 'jpegPhoto'}):
            with mock.patch('logging.warning') as mock_warning:
                self.perform_ldap_sync(self.example_user('hamlet'))
                mock_warning.assert_called_once_with(
                    'Could not parse jpegPhoto field for user %s' % (hamlet.id,))

    def test_deactivate_non_matching_users(self) -> None:
        with self.settings(LDAP_APPEND_DOMAIN='zulip.com',
                           LDAP_DEACTIVATE_NON_MATCHING_USERS=True):
            # othello isn't in our test directory
            result = sync_user_from_ldap(self.example_user('othello'), mock.Mock())

            self.assertTrue(result)
            othello = self.example_user('othello')
            self.assertFalse(othello.is_active)

    def test_update_custom_profile_field(self) -> None:
        with self.settings(AUTH_LDAP_USER_ATTR_MAP={'full_name': 'cn',
                                                    'custom_profile_field__phone_number': 'homePhone',
                                                    'custom_profile_field__birthday': 'birthDate'}):
            self.perform_ldap_sync(self.example_user('hamlet'))
        hamlet = self.example_user('hamlet')
        test_data = [
            {
                'field_name': 'Phone number',
                'expected_value': '123456789',
            },
            {
                'field_name': 'Birthday',
                'expected_value': '1900-09-08',
            },
        ]
        for test_case in test_data:
            field = CustomProfileField.objects.get(realm=hamlet.realm, name=test_case['field_name'])
            field_value = CustomProfileFieldValue.objects.get(user_profile=hamlet, field=field).value
            self.assertEqual(field_value, test_case['expected_value'])

    def test_update_non_existent_profile_field(self) -> None:
        with self.settings(AUTH_LDAP_USER_ATTR_MAP={'full_name': 'cn',
                                                    'custom_profile_field__non_existent': 'homePhone'}):
            with self.assertRaisesRegex(ZulipLDAPException, 'Custom profile field with name non_existent not found'):
                self.perform_ldap_sync(self.example_user('hamlet'))

    def test_update_custom_profile_field_invalid_data(self) -> None:
        self.change_ldap_user_attr('hamlet', 'birthDate', '9999')

        with self.settings(AUTH_LDAP_USER_ATTR_MAP={'full_name': 'cn',
                                                    'custom_profile_field__birthday': 'birthDate'}):
            with self.assertRaisesRegex(ZulipLDAPException, 'Invalid data for birthday field'):
                self.perform_ldap_sync(self.example_user('hamlet'))

    def test_update_custom_profile_field_no_mapping(self) -> None:
        hamlet = self.example_user('hamlet')
        no_op_field = CustomProfileField.objects.get(realm=hamlet.realm, name='Phone number')
        expected_value = CustomProfileFieldValue.objects.get(user_profile=hamlet, field=no_op_field).value

        with self.settings(AUTH_LDAP_USER_ATTR_MAP={'full_name': 'cn',
                                                    'custom_profile_field__birthday': 'birthDate'}):
            self.perform_ldap_sync(self.example_user('hamlet'))

        actual_value = CustomProfileFieldValue.objects.get(user_profile=hamlet, field=no_op_field).value
        self.assertEqual(actual_value, expected_value)

    def test_update_custom_profile_field_no_update(self) -> None:
        hamlet = self.example_user('hamlet')
        phone_number_field = CustomProfileField.objects.get(realm=hamlet.realm, name='Phone number')
        birthday_field = CustomProfileField.objects.get(realm=hamlet.realm, name='Birthday')
        phone_number_field_value = CustomProfileFieldValue.objects.get(user_profile=hamlet,
                                                                       field=phone_number_field)
        phone_number_field_value.value = '123456789'
        phone_number_field_value.save(update_fields=['value'])
        expected_call_args = [hamlet, [
            {
                'id': birthday_field.id,
                'value': '1900-09-08',
            },
        ]]
        with self.settings(AUTH_LDAP_USER_ATTR_MAP={'full_name': 'cn',
                                                    'custom_profile_field__birthday': 'birthDate',
                                                    'custom_profile_field__phone_number': 'homePhone'}):
            with mock.patch('zproject.backends.do_update_user_custom_profile_data_if_changed') as f:
                self.perform_ldap_sync(self.example_user('hamlet'))
                f.assert_called_once_with(*expected_call_args)

    def test_update_custom_profile_field_not_present_in_ldap(self) -> None:
        hamlet = self.example_user('hamlet')
        no_op_field = CustomProfileField.objects.get(realm=hamlet.realm, name='Birthday')
        expected_value = CustomProfileFieldValue.objects.get(user_profile=hamlet, field=no_op_field).value

        with self.settings(AUTH_LDAP_USER_ATTR_MAP={'full_name': 'cn',
                                                    'custom_profile_field__birthday': 'nonExistantAttr'}):
            self.perform_ldap_sync(self.example_user('hamlet'))

        actual_value = CustomProfileFieldValue.objects.get(user_profile=hamlet, field=no_op_field).value
        self.assertEqual(actual_value, expected_value)

class TestQueryLDAP(ZulipLDAPTestCase):

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.EmailAuthBackend',))
    def test_ldap_not_configured(self) -> None:
        values = query_ldap(self.example_email('hamlet'))
        self.assertEqual(values, ['LDAP backend not configured on this server.'])

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_user_not_present(self) -> None:
        # othello doesn't have an entry in our test directory
        values = query_ldap(self.example_email('othello'))
        self.assert_length(values, 1)
        self.assertIn('No such user found', values[0])

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_normal_query(self) -> None:
        with self.settings(AUTH_LDAP_USER_ATTR_MAP={'full_name': 'cn',
                                                    'short_name': 'sn',
                                                    'avatar': 'jpegPhoto',
                                                    'custom_profile_field__birthday': 'birthDate',
                                                    'custom_profile_field__phone_number': 'nonExistentAttr'
                                                    }):
            values = query_ldap(self.example_email('hamlet'))
        self.assertEqual(len(values), 5)
        self.assertIn('full_name: King Hamlet', values)
        self.assertIn('short_name: Hamlet', values)
        self.assertIn('avatar: (An avatar image file)', values)
        self.assertIn('custom_profile_field__birthday: 1900-09-08', values)
        self.assertIn('custom_profile_field__phone_number: LDAP field not present', values)

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_query_email_attr(self) -> None:
        with self.settings(AUTH_LDAP_USER_ATTR_MAP={'full_name': 'cn',
                                                    'short_name': 'sn'},
                           LDAP_EMAIL_ATTR='mail'):
            # This will look up the user by email in our test dictionary,
            # should successfully find hamlet's ldap entry.
            values = query_ldap(self.example_email('hamlet'))
        self.assertEqual(len(values), 3)
        self.assertIn('full_name: King Hamlet', values)
        self.assertIn('short_name: Hamlet', values)
        self.assertIn('email: hamlet@zulip.com', values)

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

        with mock.patch('zerver.views.auth.HomepageForm', return_value=Form()):
            self.assertEqual(PreregistrationUser.objects.all().count(), 0)
            result = maybe_send_to_registration(request, self.example_email("hamlet"), is_signup=True)
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

        with mock.patch('zerver.views.auth.HomepageForm', return_value=Form()):
            self.assertEqual(PreregistrationUser.objects.all().count(), 1)
            result = maybe_send_to_registration(request, email, is_signup=True)
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

class EmailValidatorTestCase(ZulipTestCase):
    def test_valid_email(self) -> None:
        validate_login_email(self.example_email("hamlet"))

    def test_invalid_email(self) -> None:
        with self.assertRaises(JsonableError):
            validate_login_email(u'hamlet')

    def test_validate_email(self) -> None:
        inviter = self.example_user('hamlet')
        cordelia = self.example_user('cordelia')

        error, _ = validate_email(inviter, 'fred+5555@zulip.com')
        self.assertIn('containing + are not allowed', error)

        _, error = validate_email(inviter, cordelia.email)
        self.assertEqual(error, 'Already has an account.')

        cordelia.is_active = False
        cordelia.save()

        _, error = validate_email(inviter, cordelia.email)
        self.assertEqual(error, 'Account has been deactivated.')

        _, error = validate_email(inviter, 'fred-is-fine@zulip.com')
        self.assertEqual(error, None)

class LDAPBackendTest(ZulipTestCase):
    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_non_existing_realm(self) -> None:
        self.init_default_ldap_database()
        email = self.example_email('hamlet')
        data = {'username': email, 'password': initial_password(email)}
        error_type = ZulipLDAPAuthBackend.REALM_IS_NONE_ERROR
        error = ZulipLDAPConfigurationError('Realm is None', error_type)
        with mock.patch('zproject.backends.ZulipLDAPAuthBackend.get_or_build_user',
                        side_effect=error), \
                mock.patch('django_auth_ldap.backend._LDAPUser._authenticate_user_dn'):
            response = self.client_post('/login/', data)
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, reverse('ldap_error_realm_is_none'))
            response = self.client_get(response.url)
            self.assert_in_response('You are trying to login using LDAP '
                                    'without creating an',
                                    response)
