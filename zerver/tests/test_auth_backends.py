import base64
import copy
import datetime
import json
import re
import time
import urllib
from contextlib import contextmanager
from typing import Any, Callable, Dict, Iterator, List, Mapping, Optional, Sequence, Tuple
from unittest import mock

import jwt
import ldap
import requests
import responses
import ujson
from bs4 import BeautifulSoup
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings
from django.contrib.auth import authenticate
from django.core import mail
from django.http import HttpRequest, HttpResponse
from django.test import override_settings
from django.test.client import RequestFactory
from django.urls import reverse
from django.utils.timezone import now as timezone_now
from django_auth_ldap.backend import LDAPSearch, _LDAPUser
from jwt.exceptions import PyJWTError
from onelogin.saml2.auth import OneLogin_Saml2_Auth
from onelogin.saml2.response import OneLogin_Saml2_Response
from social_core.exceptions import AuthFailed, AuthStateForbidden
from social_django.storage import BaseDjangoStorage
from social_django.strategy import DjangoStrategy

from confirmation.models import Confirmation, create_confirmation_link
from zerver.lib.actions import (
    do_create_realm,
    do_create_user,
    do_deactivate_realm,
    do_deactivate_user,
    do_invite_users,
    do_reactivate_realm,
    do_reactivate_user,
    do_set_realm_property,
    ensure_stream,
)
from zerver.lib.avatar import avatar_url
from zerver.lib.avatar_hash import user_avatar_path
from zerver.lib.dev_ldap_directory import generate_dev_ldap_dir
from zerver.lib.email_validation import (
    get_existing_user_errors,
    get_realm_email_validator,
    validate_email_is_valid,
)
from zerver.lib.exceptions import RateLimited
from zerver.lib.initial_password import initial_password
from zerver.lib.mobile_auth_otp import otp_decrypt_api_key
from zerver.lib.rate_limiter import add_ratelimit_rule, remove_ratelimit_rule
from zerver.lib.request import JsonableError
from zerver.lib.storage import static_path
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import (
    create_s3_buckets,
    get_test_image_file,
    load_subdomain_token,
    use_s3_backend,
)
from zerver.lib.upload import MEDIUM_AVATAR_SIZE, resize_avatar
from zerver.lib.users import get_all_api_keys
from zerver.lib.utils import generate_random_token
from zerver.lib.validator import (
    Validator,
    check_bool,
    check_dict_only,
    check_int,
    check_list,
    check_none_or,
    check_string,
    validate_login_email,
)
from zerver.models import (
    CustomProfileField,
    CustomProfileFieldValue,
    MultiuseInvite,
    PasswordTooWeakError,
    PreregistrationUser,
    Realm,
    RealmDomain,
    UserProfile,
    clear_supported_auth_backends_cache,
    email_to_username,
    get_realm,
    get_user_by_delivery_email,
)
from zerver.signals import JUST_CREATED_THRESHOLD
from zerver.views.auth import maybe_send_to_registration
from zproject.backends import (
    AUTH_BACKEND_NAME_MAP,
    AppleAuthBackend,
    AzureADAuthBackend,
    DevAuthBackend,
    EmailAuthBackend,
    ExternalAuthDataDict,
    ExternalAuthResult,
    GitHubAuthBackend,
    GitLabAuthBackend,
    GoogleAuthBackend,
    PopulateUserLDAPError,
    RateLimitedAuthenticationByUsername,
    SAMLAuthBackend,
    SocialAuthMixin,
    ZulipAuthMixin,
    ZulipDummyBackend,
    ZulipLDAPAuthBackend,
    ZulipLDAPConfigurationError,
    ZulipLDAPException,
    ZulipLDAPExceptionNoMatchingLDAPUser,
    ZulipLDAPExceptionOutsideDomain,
    ZulipLDAPUser,
    ZulipLDAPUserPopulator,
    ZulipRemoteUserBackend,
    apple_auth_enabled,
    check_password_strength,
    dev_auth_enabled,
    email_belongs_to_ldap,
    get_external_method_dicts,
    github_auth_enabled,
    gitlab_auth_enabled,
    google_auth_enabled,
    password_auth_enabled,
    query_ldap,
    require_email_format_usernames,
    saml_auth_enabled,
    sync_user_from_ldap,
)


class AuthBackendTest(ZulipTestCase):
    def get_username(self, email_to_username: Optional[Callable[[str], str]]=None) -> str:
        username = self.example_email('hamlet')
        if email_to_username is not None:
            username = email_to_username(self.example_email('hamlet'))

        return username

    def verify_backend(self, backend: Any, *, good_kwargs: Dict[str, Any], bad_kwargs: Optional[Dict[str, Any]]=None) -> None:
        clear_supported_auth_backends_cache()
        user_profile = self.example_user('hamlet')

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
            return_data: Dict[str, bool] = {}
            user = EmailAuthBackend().authenticate(request=mock.MagicMock(),
                                                   username=user_profile.delivery_email,
                                                   realm=get_realm("zulip"),
                                                   password=password,
                                                   return_data=return_data)
            self.assertEqual(user, None)
            self.assertTrue(return_data['email_auth_disabled'])

        self.verify_backend(EmailAuthBackend(),
                            good_kwargs=dict(request=mock.MagicMock(),
                                             password=password,
                                             username=username,
                                             realm=get_realm('zulip'),
                                             return_data=dict()),
                            bad_kwargs=dict(request=mock.MagicMock(),
                                            password=password,
                                            username=username,
                                            realm=get_realm('zephyr'),
                                            return_data=dict()))
        self.verify_backend(EmailAuthBackend(),
                            good_kwargs=dict(request=mock.MagicMock(),
                                             password=password,
                                             username=username,
                                             realm=get_realm('zulip'),
                                             return_data=dict()),
                            bad_kwargs=dict(request=mock.MagicMock(),
                                            password=password,
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
        self.assertIsNotNone(EmailAuthBackend().authenticate(request=mock.MagicMock(),
                                                             username=self.example_email('hamlet'),
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
        self.assertIsNone(EmailAuthBackend().authenticate(request=mock.MagicMock(),
                                                          username=self.example_email('hamlet'),
                                                          password=password,
                                                          realm=get_realm("zulip")))

    def test_email_auth_backend_disabled_password_auth(self) -> None:
        user_profile = self.example_user('hamlet')
        password = "testpassword"
        user_profile.set_password(password)
        user_profile.save()
        # Verify if a realm has password auth disabled, correct password is rejected
        with mock.patch('zproject.backends.password_auth_enabled', return_value=False):
            self.assertIsNone(EmailAuthBackend().authenticate(request=mock.MagicMock(),
                                                              username=self.example_email('hamlet'),
                                                              password=password,
                                                              realm=get_realm("zulip")))

    def test_login_preview(self) -> None:
        # Test preview=true displays organization login page
        # instead of redirecting to app
        self.login('iago')
        realm = get_realm("zulip")
        result = self.client_get('/login/?preview=true')
        self.assertEqual(result.status_code, 200)
        self.assert_in_response(realm.description, result)
        assert realm.name is not None
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
        email = user_profile.delivery_email
        password = self.ldap_password('hamlet')
        self.setup_subdomain(user_profile)

        username = self.get_username()
        backend = ZulipLDAPAuthBackend()

        # Test LDAP auth fails when LDAP server rejects password
        self.assertIsNone(backend.authenticate(request=mock.MagicMock(), username=email,
                                               password="wrongpass", realm=get_realm("zulip")))

        self.verify_backend(backend,
                            bad_kwargs=dict(request=mock.MagicMock(),
                                            username=username,
                                            password=password,
                                            realm=get_realm('zephyr')),
                            good_kwargs=dict(request=mock.MagicMock(),
                                             username=username,
                                             password=password,
                                             realm=get_realm('zulip')))
        self.verify_backend(backend,
                            bad_kwargs=dict(request=mock.MagicMock(),
                                            username=username,
                                            password=password,
                                            realm=get_realm('zephyr')),
                            good_kwargs=dict(request=mock.MagicMock(),
                                             username=username,
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
            'token_type': 'bearer',
        }
        github_email_data = [
            dict(email=user.delivery_email,
                 verified=True,
                 primary=True),
            dict(email="nonprimary@zulip.com",
                 verified=True),
            dict(email="ignored@example.com",
                 verified=False),
        ]
        google_email_data = dict(email=user.delivery_email,
                                 name=user.full_name,
                                 email_verified=True)
        backends_to_test: Dict[str, Any] = {
            'google': {
                'urls': [
                    # The limited process that we test here doesn't require mocking any urls.
                ],
                'backend': GoogleAuthBackend,
            },
            'github': {
                'urls': [
                    {
                        'url': "https://api.github.com/user/emails",
                        'method': responses.GET,
                        'status': 200,
                        'body': json.dumps(github_email_data),
                    },
                ],
                'backend': GitHubAuthBackend,
            },
        }

        def patched_authenticate(
            request: Optional[HttpResponse] = None,
            **kwargs: Any,
        ) -> Any:
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
                return {'email': user.delivery_email}
            backend.strategy.request_data = return_email

            result = orig_authenticate(backend, request, **kwargs)
            return result

        def patched_get_verified_emails(*args: Any, **kwargs: Any) -> Any:
            return google_email_data['email']

        for backend_name in backends_to_test:
            with responses.RequestsMock(assert_all_requests_are_fired=True) as requests_mock:
                urls: List[Dict[str, Any]] = backends_to_test[backend_name]['urls']
                for details in urls:
                    requests_mock.add(
                        details['method'],
                        details['url'],
                        status=details['status'],
                        body=details['body'])
                backend_class = backends_to_test[backend_name]['backend']

                # We're creating a new class instance here, so the
                # monkey-patching of the instance that we're about to
                # do will be discarded at the end of this test.
                backend = backend_class()
                backend.strategy = DjangoStrategy(storage=BaseDjangoStorage())

                orig_authenticate = backend_class.authenticate
                backend.authenticate = patched_authenticate
                if backend_name == "google":
                    backend.get_verified_emails = patched_get_verified_emails

                good_kwargs = dict(backend=backend, strategy=backend.strategy,
                                   storage=backend.strategy.storage,
                                   response=token_data_dict,
                                   subdomain='zulip')
                bad_kwargs = dict(subdomain='acme')
                logger_name = f'zulip.auth.{backend.name}'

                with mock.patch(
                    'zerver.views.auth.redirect_and_log_into_subdomain',
                    return_value=user
                ), self.assertLogs(logger_name, level="INFO") as info_log:
                    self.verify_backend(backend,
                                        good_kwargs=good_kwargs,
                                        bad_kwargs=bad_kwargs)
                    bad_kwargs['subdomain'] = "zephyr"
                    self.verify_backend(backend,
                                        good_kwargs=good_kwargs,
                                        bad_kwargs=bad_kwargs)
                # Verify logging for deactivated users
                self.assertEqual(info_log.output, [
                    f'INFO:{logger_name}:Failed login attempt for deactivated account: {user.id}@{user.realm.string_id}',
                    f'INFO:{logger_name}:Failed login attempt for deactivated account: {user.id}@{user.realm.string_id}'
                ])


class RateLimitAuthenticationTests(ZulipTestCase):
    @override_settings(RATE_LIMITING_AUTHENTICATE=True)
    def do_test_auth_rate_limiting(self,
                                   attempt_authentication_func: Callable[[HttpRequest, str, str],
                                                                         Optional[UserProfile]],
                                   username: str, correct_password: str, wrong_password: str,
                                   expected_user_profile: UserProfile) -> None:
        # We have to mock RateLimitedAuthenticationByUsername.key to avoid key collisions
        # if tests run in parallel.
        original_key_method = RateLimitedAuthenticationByUsername.key
        salt = generate_random_token(32)

        def _mock_key(self: RateLimitedAuthenticationByUsername) -> str:
            return f"{salt}:{original_key_method(self)}"

        def attempt_authentication(username: str, password: str) -> Optional[UserProfile]:
            request = HttpRequest()
            return attempt_authentication_func(request, username, password)

        add_ratelimit_rule(10, 2, domain='authenticate_by_username')
        with mock.patch.object(RateLimitedAuthenticationByUsername, 'key', new=_mock_key):
            try:
                start_time = time.time()
                with mock.patch('time.time', return_value=start_time):
                    self.assertIsNone(attempt_authentication(username, wrong_password))
                    self.assertIsNone(attempt_authentication(username, wrong_password))
                    # 2 failed attempts is the limit, so the next ones should get blocked,
                    # even with the correct password.
                    with self.assertRaises(RateLimited):
                        attempt_authentication(username, correct_password)
                    with self.assertRaises(RateLimited):
                        attempt_authentication(username, wrong_password)

                # After enough time passes, more authentication attempts can be made:
                with mock.patch('time.time', return_value=start_time + 11.0):
                    self.assertIsNone(attempt_authentication(username, wrong_password))

                    self.assertEqual(attempt_authentication(username, correct_password), expected_user_profile)  # Correct password
                    # A correct login attempt should reset the rate limits for this user profile,
                    # so the next two attempts shouldn't get limited:
                    self.assertIsNone(attempt_authentication(username, wrong_password))
                    self.assertIsNone(attempt_authentication(username, wrong_password))
                    # But the third attempt goes over the limit:
                    with self.assertRaises(RateLimited):
                        attempt_authentication(username, wrong_password)
            finally:
                # Clean up to avoid affecting other tests.
                RateLimitedAuthenticationByUsername(username).clear_history()
                remove_ratelimit_rule(10, 2, domain='authenticate_by_username')

    def test_email_auth_backend_user_based_rate_limiting(self) -> None:
        user_profile = self.example_user('hamlet')
        password = "testpassword"
        user_profile.set_password(password)
        user_profile.save()

        def attempt_authentication(request: HttpRequest, username: str, password: str) -> Optional[UserProfile]:
            return EmailAuthBackend().authenticate(request=request,
                                                   username=username,
                                                   realm=get_realm("zulip"),
                                                   password=password,
                                                   return_data=dict())

        self.do_test_auth_rate_limiting(attempt_authentication,
                                        user_profile.delivery_email,
                                        password, 'wrong_password',
                                        user_profile)

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',),
                       LDAP_EMAIL_ATTR="mail")
    def test_ldap_backend_user_based_rate_limiting(self) -> None:
        self.init_default_ldap_database()
        user_profile = self.example_user('hamlet')
        password = self.ldap_password('hamlet')

        def attempt_authentication(request: HttpRequest, username: str, password: str) -> Optional[UserProfile]:
            return ZulipLDAPAuthBackend().authenticate(request=request,
                                                       username=username,
                                                       realm=get_realm("zulip"),
                                                       password=password,
                                                       return_data=dict())

        self.do_test_auth_rate_limiting(attempt_authentication,
                                        user_profile.delivery_email,
                                        password, 'wrong_password',
                                        user_profile)

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.EmailAuthBackend',
                                                'zproject.backends.ZulipLDAPAuthBackend'),
                       LDAP_EMAIL_ATTR="mail")
    def test_email_and_ldap_backends_user_based_rate_limiting(self) -> None:
        self.init_default_ldap_database()
        user_profile = self.example_user('hamlet')
        ldap_password = self.ldap_password('hamlet')

        email_password = "email_password"
        user_profile.set_password(email_password)
        user_profile.save()

        def attempt_authentication(request: HttpRequest, username: str, password: str) -> Optional[UserProfile]:
            return authenticate(request=request,
                                username=username,
                                realm=get_realm("zulip"),
                                password=password,
                                return_data=dict())

        self.do_test_auth_rate_limiting(attempt_authentication,
                                        user_profile.delivery_email,
                                        email_password, 'wrong_password',
                                        user_profile)
        self.do_test_auth_rate_limiting(attempt_authentication,
                                        user_profile.delivery_email,
                                        ldap_password, 'wrong_password',
                                        user_profile)

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

class DesktopFlowTestingLib(ZulipTestCase):
    def verify_desktop_flow_app_page(self, response: HttpResponse) -> None:
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"<h1>Finish desktop login</h1>", response.content)

    def verify_desktop_flow_end_page(self, response: HttpResponse, email: str,
                                     desktop_flow_otp: str) -> None:
        self.assertEqual(response.status_code, 200)

        soup = BeautifulSoup(response.content, "html.parser")
        desktop_data = soup.find("input", value=True)["value"]
        browser_url = soup.find("a", href=True)["href"]

        self.assertEqual(browser_url, '/login/')
        decrypted_key = self.verify_desktop_data_and_return_key(desktop_data, desktop_flow_otp)

        result = self.client_get(f'http://zulip.testserver/accounts/login/subdomain/{decrypted_key}')
        self.assertEqual(result.status_code, 302)
        realm = get_realm("zulip")
        user_profile = get_user_by_delivery_email(email, realm)
        self.assert_logged_in_user_id(user_profile.id)

    def verify_desktop_data_and_return_key(self, desktop_data: str, desktop_flow_otp: str) -> str:
        key = bytes.fromhex(desktop_flow_otp)
        data = bytes.fromhex(desktop_data)
        iv = data[:12]
        ciphertext = data[12:]
        return AESGCM(key).decrypt(iv, ciphertext, b"").decode()

class SocialAuthBase(DesktopFlowTestingLib, ZulipTestCase):
    """This is a base class for testing social-auth backends. These
    methods are often overridden by subclasses:

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
        self.email = self.user_profile.delivery_email
        self.name = self.user_profile.full_name
        self.backend = self.BACKEND_CLASS
        self.backend.strategy = DjangoStrategy(storage=BaseDjangoStorage())
        self.user_profile.backend = self.backend
        self.logger_string = f'zulip.auth.{self.backend.name}'

        # This is a workaround for the fact that Python social auth
        # caches the set of authentication backends that are enabled
        # the first time that `social_django.utils` is imported.  See
        # https://github.com/python-social-auth/social-app-django/pull/162
        # for details.
        from social_core.backends.utils import load_backends
        load_backends(settings.AUTHENTICATION_BACKENDS, force_load=True)

    def logger_output(self, output_string: str, type: str) -> str:
        return f'{type.upper()}:zulip.auth.{self.backend.name}:{output_string}'

    def register_extra_endpoints(self, requests_mock: responses.RequestsMock,
                                 account_data_dict: Dict[str, str],
                                 **extra_data: Any) -> None:
        pass

    def prepare_login_url_and_headers(
        self,
        subdomain: str,
        mobile_flow_otp: Optional[str]=None,
        desktop_flow_otp: Optional[str]=None,
        is_signup: bool=False,
        next: str='',
        multiuse_object_key: str='',
        alternative_start_url: Optional[str]=None,
        *,
        user_agent: Optional[str]=None,
    ) -> Tuple[str, Dict[str, Any]]:
        url = self.LOGIN_URL
        if alternative_start_url is not None:
            url = alternative_start_url

        params = {}
        headers = {}
        if subdomain == '':
            # "testserver" may trip up some libraries' URL validation,
            # so let's use the equivalent www. version.
            headers['HTTP_HOST'] = 'www.testserver'
        else:
            headers['HTTP_HOST'] = subdomain + ".testserver"
        if mobile_flow_otp is not None:
            params['mobile_flow_otp'] = mobile_flow_otp
            headers['HTTP_USER_AGENT'] = "ZulipAndroid"
        if desktop_flow_otp is not None:
            params['desktop_flow_otp'] = desktop_flow_otp
        if is_signup:
            url = self.SIGNUP_URL
        params['next'] = next
        params['multiuse_object_key'] = multiuse_object_key
        if len(params) > 0:
            url += f"?{urllib.parse.urlencode(params)}"
        if user_agent is not None:
            headers['HTTP_USER_AGENT'] = user_agent

        return url, headers

    def social_auth_test_finish(self, result: HttpResponse,
                                account_data_dict: Dict[str, str],
                                expect_choose_email_screen: bool,
                                headers: Any,
                                **extra_data: Any) -> HttpResponse:
        parsed_url = urllib.parse.urlparse(result.url)
        csrf_state = urllib.parse.parse_qs(parsed_url.query)['state']
        result = self.client_get(self.AUTH_FINISH_URL,
                                 dict(state=csrf_state), **headers)
        return result

    def generate_access_url_payload(self, account_data_dict: Dict[str, str]) -> str:
        return json.dumps({
            'access_token': 'foobar',
            'token_type': 'bearer',
        })

    def social_auth_test(self, account_data_dict: Dict[str, str],
                         *, subdomain: str,
                         mobile_flow_otp: Optional[str]=None,
                         desktop_flow_otp: Optional[str]=None,
                         is_signup: bool=False,
                         next: str='',
                         multiuse_object_key: str='',
                         expect_choose_email_screen: bool=False,
                         alternative_start_url: Optional[str]=None,
                         user_agent: Optional[str]=None,
                         **extra_data: Any) -> HttpResponse:
        """Main entrypoint for all social authentication tests.

        * account_data_dict: Dictionary containing the name/email data
          that should be returned by the social auth backend.
        * subdomain: Which organization's login page is being accessed.
        * desktop_flow_otp / mobile_flow_otp: Token to be used for
          mobile or desktop authentication flow testing.
        * is_signup: Whether we're testing the social flow for
          /register (True) or /login (False).  This is important
          because we need to verify behavior like the
          "Continue to registration" if you try to login using an
          account that doesn't exist but is allowed to signup.
        * next: Parameter passed through in production authentication
          to redirect the user to (e.g.) the specific page in the webapp
          that they clicked a link to before being presented with the login
          page.
        * expect_choose_email_screen: Some social auth backends, like
          GitHub, simultaneously authenticate for multiple email addresses.
          Set this to True if we expect to show the "Choose Email" screen
          in this test should the backend have that feature.
        * multiuse_object_key: Used when the user has clicked a multi-use
          reusable invitation link.
        * alternative_start_url: Used to test legacy mobile app behavior.
        * user_agent: What user-agent to use for the HTTP requests.
        """

        url, headers = self.prepare_login_url_and_headers(
            subdomain, mobile_flow_otp, desktop_flow_otp, is_signup, next,
            multiuse_object_key, alternative_start_url,
            user_agent=user_agent,
        )

        result = self.client_get(url, **headers)

        expected_result_url_prefix = f'http://testserver/login/{self.backend.name}/'
        if settings.SOCIAL_AUTH_SUBDOMAIN is not None:
            expected_result_url_prefix = f'http://{settings.SOCIAL_AUTH_SUBDOMAIN}.testserver/login/{self.backend.name}/'

        if result.status_code != 302 or not result.url.startswith(expected_result_url_prefix):
            return result

        result = self.client_get(result.url, **headers)
        self.assertEqual(result.status_code, 302)
        assert self.AUTHORIZATION_URL in result.url

        self.client.cookies = result.cookies

        # Next, the browser requests result["Location"], and gets
        # redirected back to the registered redirect uri.

        # We register callbacks for the key URLs on Identity Provider that
        # auth completion url will call
        with responses.RequestsMock(assert_all_requests_are_fired=False) as requests_mock:
            requests_mock.add(
                requests_mock.POST,
                self.ACCESS_TOKEN_URL,
                match_querystring=False,
                status=200,
                body=self.generate_access_url_payload(account_data_dict))
            requests_mock.add(
                requests_mock.GET,
                self.USER_INFO_URL,
                status=200,
                body=json.dumps(account_data_dict),
            )
            self.register_extra_endpoints(requests_mock, account_data_dict, **extra_data)

            result = self.social_auth_test_finish(result, account_data_dict,
                                                  expect_choose_email_screen,
                                                  headers=headers,
                                                  **extra_data)
        return result

    def test_social_auth_no_key(self) -> None:
        account_data_dict = self.get_account_data_dict(email=self.email, name=self.name)
        with self.settings(**{self.CLIENT_KEY_SETTING: None}):
            result = self.social_auth_test(account_data_dict,
                                           subdomain='zulip', next='/user_uploads/image')
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result.url, self.CONFIG_ERROR_URL)

    def test_config_error_development(self) -> None:
        if hasattr(self, 'CLIENT_KEY_SETTING') and hasattr(self, 'CLIENT_SECRET_SETTING'):
            with self.settings(**{self.CLIENT_KEY_SETTING: None}):
                result = self.client_get(self.LOGIN_URL)
                self.assertEqual(result.status_code, 302)
                self.assertEqual(result.url, self.CONFIG_ERROR_URL)
                result = self.client_get(result.url)
                self.assert_in_success_response([self.CLIENT_KEY_SETTING.lower()], result)
                self.assert_in_success_response([self.CLIENT_SECRET_SETTING.lower()], result)
                self.assert_in_success_response(["zproject/dev-secrets.conf"], result)
                self.assert_not_in_success_response([self.CLIENT_KEY_SETTING], result)
                self.assert_not_in_success_response(["zproject/dev_settings.py"], result)
                self.assert_not_in_success_response(["/etc/zulip/settings.py"], result)
                self.assert_not_in_success_response(["/etc/zulip/zulip-secrets.conf"], result)

    @override_settings(DEVELOPMENT=False)
    def test_config_error_production(self) -> None:
        if hasattr(self, 'CLIENT_KEY_SETTING') and hasattr(self, 'CLIENT_SECRET_SETTING'):
            with self.settings(**{self.CLIENT_KEY_SETTING: None}):
                result = self.client_get(self.LOGIN_URL)
                self.assertEqual(result.status_code, 302)
                self.assertEqual(result.url, self.CONFIG_ERROR_URL)
                result = self.client_get(result.url)
                self.assert_in_success_response([self.CLIENT_KEY_SETTING], result)
                self.assert_in_success_response(["/etc/zulip/settings.py"], result)
                self.assert_in_success_response([self.CLIENT_SECRET_SETTING.lower()], result)
                self.assert_in_success_response(["/etc/zulip/zulip-secrets.conf"], result)
                self.assert_not_in_success_response([self.CLIENT_KEY_SETTING.lower()], result)
                self.assert_not_in_success_response(["zproject/dev_settings.py"], result)
                self.assert_not_in_success_response(["zproject/dev-secrets.conf"], result)

    def test_social_auth_success(self) -> None:
        account_data_dict = self.get_account_data_dict(email=self.email, name=self.name)
        result = self.social_auth_test(account_data_dict,
                                       expect_choose_email_screen=False,
                                       subdomain='zulip', next='/user_uploads/image')
        data = load_subdomain_token(result)
        self.assertEqual(data['email'], self.example_email("hamlet"))
        self.assertEqual(data['full_name'], self.name)
        self.assertEqual(data['subdomain'], 'zulip')
        self.assertEqual(data['redirect_to'], '/user_uploads/image')
        self.assertEqual(result.status_code, 302)
        parsed_url = urllib.parse.urlparse(result.url)
        uri = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
        self.assertTrue(uri.startswith('http://zulip.testserver/accounts/login/subdomain/'))

    @override_settings(SOCIAL_AUTH_SUBDOMAIN=None)
    def test_when_social_auth_subdomain_is_not_set(self) -> None:
        account_data_dict = self.get_account_data_dict(email=self.email, name=self.name)
        result = self.social_auth_test(account_data_dict,
                                       subdomain='zulip',
                                       expect_choose_email_screen=False,
                                       next='/user_uploads/image')
        data = load_subdomain_token(result)
        self.assertEqual(data['email'], self.example_email("hamlet"))
        self.assertEqual(data['full_name'], self.name)
        self.assertEqual(data['subdomain'], 'zulip')
        self.assertEqual(data['redirect_to'], '/user_uploads/image')
        self.assertEqual(result.status_code, 302)
        parsed_url = urllib.parse.urlparse(result.url)
        uri = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
        self.assertTrue(uri.startswith('http://zulip.testserver/accounts/login/subdomain/'))

    def test_social_auth_deactivated_user(self) -> None:
        user_profile = self.example_user("hamlet")
        do_deactivate_user(user_profile)
        account_data_dict = self.get_account_data_dict(email=self.email, name=self.name)
        # We expect to go through the "choose email" screen here,
        # because there won't be an existing user account we can
        # auto-select for the user.
        with self.assertLogs(self.logger_string, level='INFO') as m:
            result = self.social_auth_test(account_data_dict,
                                           expect_choose_email_screen=True,
                                           subdomain='zulip')
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result.url, "/login/?is_deactivated=true")
        self.assertEqual(m.output, [self.logger_output(f"Failed login attempt for deactivated account: {user_profile.id}@zulip", 'info')])
        # TODO: verify whether we provide a clear error message

    def test_social_auth_invalid_realm(self) -> None:
        account_data_dict = self.get_account_data_dict(email=self.email, name=self.name)
        with mock.patch('zerver.middleware.get_realm', return_value=get_realm("zulip")):
            # This mock.patch case somewhat hackishly arranges it so
            # that we switch realms halfway through the test
            result = self.social_auth_test(account_data_dict,
                                           subdomain='invalid', next='/user_uploads/image')
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result.url, "/accounts/find/")

    def test_social_auth_invalid_email(self) -> None:
        account_data_dict = self.get_account_data_dict(email="invalid", name=self.name)
        with self.assertLogs(self.logger_string, level='INFO') as m:
            result = self.social_auth_test(account_data_dict,
                                           expect_choose_email_screen=True,
                                           subdomain='zulip', next='/user_uploads/image')
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result.url, "/login/?next=/user_uploads/image")
        self.assertEqual(m.output, [self.logger_output("{} got invalid email argument.".format(self.backend.auth_backend_name), 'warning')])

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
                                           expect_choose_email_screen=False,
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

    def test_social_auth_desktop_success(self) -> None:
        desktop_flow_otp = '1234abcd' * 8
        account_data_dict = self.get_account_data_dict(email=self.email, name='Full Name')

        # Verify that the right thing happens with an invalid-format OTP
        result = self.social_auth_test(account_data_dict, subdomain='zulip',
                                       desktop_flow_otp="1234")
        self.assert_json_error(result, "Invalid OTP")
        result = self.social_auth_test(account_data_dict, subdomain='zulip',
                                       desktop_flow_otp="invalido" * 8)
        self.assert_json_error(result, "Invalid OTP")

        # Now do it correctly
        result = self.social_auth_test(
            account_data_dict,
            subdomain='zulip',
            expect_choose_email_screen=False,
            desktop_flow_otp=desktop_flow_otp,
            user_agent="ZulipElectron/5.0.0",
        )
        self.verify_desktop_flow_app_page(result)
        result = self.social_auth_test(account_data_dict, subdomain='zulip',
                                       expect_choose_email_screen=False,
                                       desktop_flow_otp=desktop_flow_otp)
        self.verify_desktop_flow_end_page(result, self.email, desktop_flow_otp)

    def test_social_auth_session_fields_cleared_correctly(self) -> None:
        mobile_flow_otp = '1234abcd' * 8

        def initiate_auth(mobile_flow_otp: Optional[str]=None) -> None:
            url, headers = self.prepare_login_url_and_headers(subdomain='zulip',
                                                              mobile_flow_otp=mobile_flow_otp)
            result = self.client_get(url, **headers)
            self.assertEqual(result.status_code, 302)

            result = self.client_get(result.url, **headers)
            self.assertEqual(result.status_code, 302)

        # Start social auth with mobile_flow_otp param. It should get saved into the session
        # on SOCIAL_AUTH_SUBDOMAIN.
        initiate_auth(mobile_flow_otp)
        self.assertEqual(self.client.session['mobile_flow_otp'], mobile_flow_otp)

        # Make a request without mobile_flow_otp param and verify the field doesn't persist
        # in the session from the previous request.
        initiate_auth()
        self.assertEqual(self.client.session.get('mobile_flow_otp'), None)

    def test_social_auth_mobile_and_desktop_flow_in_one_request_error(self) -> None:
        otp = '1234abcd' * 8
        account_data_dict = self.get_account_data_dict(email=self.email, name='Full Name')

        result = self.social_auth_test(account_data_dict, subdomain='zulip',
                                       expect_choose_email_screen=False,
                                       desktop_flow_otp=otp, mobile_flow_otp=otp)
        self.assert_json_error(result, "Can't use both mobile_flow_otp and desktop_flow_otp together.")

    def test_social_auth_registration_existing_account(self) -> None:
        """If the user already exists, signup flow just logs them in"""
        email = "hamlet@zulip.com"
        name = 'Full Name'
        account_data_dict = self.get_account_data_dict(email=email, name=name)
        result = self.social_auth_test(account_data_dict,
                                       expect_choose_email_screen=True,
                                       subdomain='zulip', is_signup=True)
        data = load_subdomain_token(result)
        self.assertEqual(data['email'], self.example_email("hamlet"))
        # Verify data has the full_name consistent with the user we're logging in as.
        self.assertEqual(data['full_name'], self.example_user("hamlet").full_name)
        self.assertEqual(data['subdomain'], 'zulip')
        self.assertEqual(result.status_code, 302)
        parsed_url = urllib.parse.urlparse(result.url)
        uri = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
        self.assertTrue(uri.startswith('http://zulip.testserver/accounts/login/subdomain/'))
        hamlet = self.example_user("hamlet")
        # Name wasn't changed at all
        self.assertEqual(hamlet.full_name, "King Hamlet")

    def stage_two_of_registration(self, result: HttpResponse, realm: Realm, subdomain: str,
                                  email: str, name: str, expected_final_name: str,
                                  skip_registration_form: bool,
                                  mobile_flow_otp: Optional[str]=None,
                                  desktop_flow_otp: Optional[str]=None,
                                  expect_confirm_registration_page: bool=False,
                                  expect_full_name_prepopulated: bool=True) -> None:
        data = load_subdomain_token(result)
        self.assertEqual(data['email'], email)
        self.assertEqual(data['full_name'], name)
        self.assertEqual(data['subdomain'], 'zulip')
        self.assertEqual(result.status_code, 302)
        parsed_url = urllib.parse.urlparse(result.url)
        uri = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
        self.assertTrue(uri.startswith('http://zulip.testserver/accounts/login/subdomain/'))

        result = self.client_get(result.url)

        if expect_confirm_registration_page:
            self.assertEqual(result.status_code, 200)
        else:
            self.assertEqual(result.status_code, 302)
        confirmation = Confirmation.objects.all().last()
        confirmation_key = confirmation.confirmation_key
        if expect_confirm_registration_page:
            self.assert_in_success_response(['do_confirm/' + confirmation_key], result)
            do_confirm_url = '/accounts/do_confirm/' + confirmation_key
        else:
            self.assertIn('do_confirm/' + confirmation_key, result.url)
            do_confirm_url = result.url
        result = self.client_get(do_confirm_url, name = name)
        self.assert_in_response('action="/accounts/register/"', result)
        confirmation_data = {"from_confirmation": "1",
                             "key": confirmation_key}
        result = self.client_post('/accounts/register/', confirmation_data)
        if not skip_registration_form:
            self.assert_in_response("We just need you to do one last thing", result)

            # Verify that the user is asked for name but not password
            self.assert_not_in_success_response(['id_password'], result)
            self.assert_in_success_response(['id_full_name'], result)
            if expect_full_name_prepopulated:
                # Verify the name field gets correctly pre-populated:
                self.assert_in_success_response([expected_final_name], result)

            # Click confirm registration button.
            result = self.client_post(
                '/accounts/register/',
                {'full_name': expected_final_name,
                 'key': confirmation_key,
                 'terms': True})

        # Mobile and desktop flow have additional steps:
        if mobile_flow_otp:
            self.assertEqual(result.status_code, 302)
            redirect_url = result['Location']
            parsed_url = urllib.parse.urlparse(redirect_url)
            query_params = urllib.parse.parse_qs(parsed_url.query)
            self.assertEqual(parsed_url.scheme, 'zulip')
            self.assertEqual(query_params["realm"], ['http://zulip.testserver'])
            self.assertEqual(query_params["email"], [email])
            encrypted_api_key = query_params["otp_encrypted_api_key"][0]
            user_api_keys = get_all_api_keys(get_user_by_delivery_email(email, realm))
            self.assertIn(otp_decrypt_api_key(encrypted_api_key, mobile_flow_otp), user_api_keys)
            return
        elif desktop_flow_otp:
            self.verify_desktop_flow_end_page(result, email, desktop_flow_otp)
            # Now the desktop app is logged in, continue with the logged in check.
        else:
            self.assertEqual(result.status_code, 302)

        user_profile = get_user_by_delivery_email(email, realm)
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
                                       subdomain=subdomain, is_signup=True)
        self.stage_two_of_registration(result, realm, subdomain, email, name, name,
                                       self.BACKEND_CLASS.full_name_validated)

    @override_settings(TERMS_OF_SERVICE=None)
    def test_social_auth_mobile_registration(self) -> None:
        email = "newuser@zulip.com"
        name = 'Full Name'
        subdomain = 'zulip'
        realm = get_realm("zulip")
        mobile_flow_otp = '1234abcd' * 8
        account_data_dict = self.get_account_data_dict(email=email, name=name)

        result = self.social_auth_test(account_data_dict, subdomain='zulip',
                                       expect_choose_email_screen=True,
                                       is_signup=True,
                                       mobile_flow_otp=mobile_flow_otp)
        self.stage_two_of_registration(result, realm, subdomain, email, name, name,
                                       self.BACKEND_CLASS.full_name_validated,
                                       mobile_flow_otp=mobile_flow_otp)

    @override_settings(TERMS_OF_SERVICE=None)
    def test_social_auth_desktop_registration(self) -> None:
        email = "newuser@zulip.com"
        name = 'Full Name'
        subdomain = 'zulip'
        realm = get_realm("zulip")
        desktop_flow_otp = '1234abcd' * 8
        account_data_dict = self.get_account_data_dict(email=email, name=name)

        result = self.social_auth_test(account_data_dict, subdomain='zulip',
                                       expect_choose_email_screen=True,
                                       is_signup=True,
                                       desktop_flow_otp=desktop_flow_otp)
        self.stage_two_of_registration(result, realm, subdomain, email, name, name,
                                       self.BACKEND_CLASS.full_name_validated,
                                       desktop_flow_otp=desktop_flow_otp)

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
                                       subdomain=subdomain, is_signup=True)
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
        create_confirmation_link(multiuse_obj, Confirmation.MULTIUSE_INVITE)
        multiuse_confirmation = Confirmation.objects.all().last()
        multiuse_object_key = multiuse_confirmation.confirmation_key
        account_data_dict = self.get_account_data_dict(email=email, name=name)

        # First, try to signup for closed realm without using an invitation
        result = self.social_auth_test(account_data_dict,
                                       expect_choose_email_screen=True,
                                       subdomain=subdomain, is_signup=True)
        result = self.client_get(result.url)
        # Verify that we're unable to signup, since this is a closed realm
        self.assertEqual(result.status_code, 200)
        self.assert_in_success_response(["Sign up"], result)

        result = self.social_auth_test(account_data_dict, subdomain=subdomain, is_signup=True,
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
        self.assertEqual(data['full_name'], name)
        self.assertEqual(data['subdomain'], 'zulip')
        self.assertEqual(result.status_code, 302)
        parsed_url = urllib.parse.urlparse(result.url)
        uri = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
        self.assertTrue(uri.startswith('http://zulip.testserver/accounts/login/subdomain/'))

        result = self.client_get(result.url)
        self.assertEqual(result.status_code, 200)
        self.assert_in_response("No account found for newuser@zulip.com.", result)

    def test_social_auth_registration_without_is_signup_closed_realm(self) -> None:
        """If the user doesn't exist yet in closed realm, give an error"""
        realm = get_realm("zulip")
        do_set_realm_property(realm, "emails_restricted_to_domains", True)
        email = "nonexisting@phantom.com"
        name = 'Full Name'
        account_data_dict = self.get_account_data_dict(email=email, name=name)
        result = self.social_auth_test(account_data_dict,
                                       expect_choose_email_screen=True,
                                       subdomain='zulip')
        self.assertEqual(result.status_code, 302)
        data = load_subdomain_token(result)
        self.assertEqual(data['email'], email)
        self.assertEqual(data['full_name'], name)
        self.assertEqual(data['subdomain'], 'zulip')
        self.assertEqual(result.status_code, 302)
        parsed_url = urllib.parse.urlparse(result.url)
        uri = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
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

        backend_path = f'zproject.backends.{self.BACKEND_CLASS.__name__}'
        with self.settings(
                POPULATE_PROFILE_VIA_LDAP=True,
                LDAP_APPEND_DOMAIN='zulip.com',
                AUTH_LDAP_USER_ATTR_MAP=ldap_user_attr_map,
                AUTHENTICATION_BACKENDS=(backend_path,
                                         'zproject.backends.ZulipLDAPUserPopulator',
                                         'zproject.backends.ZulipDummyBackend'),
        ), self.assertLogs(level='WARNING') as log_warn:
            result = self.social_auth_test(account_data_dict,
                                           expect_choose_email_screen=True,
                                           subdomain=subdomain, is_signup=True)
            # Full name should get populated from ldap:
            self.stage_two_of_registration(result, realm, subdomain, email, name, "New LDAP fullname",
                                           skip_registration_form=True)

            # Now try a user that doesn't exist in ldap:
            email = self.nonreg_email("alice")
            name = "Alice Social"
            account_data_dict = self.get_account_data_dict(email=email, name=name)
            result = self.social_auth_test(account_data_dict,
                                           expect_choose_email_screen=True,
                                           subdomain=subdomain, is_signup=True)
            # Full name should get populated as provided by the social backend, because
            # this user isn't in the ldap dictionary:
            self.stage_two_of_registration(result, realm, subdomain, email, name, name,
                                           skip_registration_form=self.BACKEND_CLASS.full_name_validated)
        self.assertEqual(log_warn.output, [f'WARNING:root:New account email {email} could not be found in LDAP'])

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

        backend_path = f'zproject.backends.{self.BACKEND_CLASS.__name__}'
        with self.settings(
                POPULATE_PROFILE_VIA_LDAP=True,
                LDAP_EMAIL_ATTR='mail',
                AUTH_LDAP_USER_ATTR_MAP=ldap_user_attr_map,
                AUTHENTICATION_BACKENDS=(backend_path,
                                         'zproject.backends.ZulipLDAPAuthBackend',
                                         'zproject.backends.ZulipDummyBackend'),
        ), self.assertLogs('zulip.ldap', level='DEBUG') as log_debug, self.assertLogs(level='WARNING') as log_warn:
            account_data_dict = self.get_account_data_dict(email=email, name=name)
            result = self.social_auth_test(account_data_dict,
                                           expect_choose_email_screen=True,
                                           subdomain=subdomain, is_signup=True)
            # Full name should get populated as provided by the social backend, because
            # this user isn't in the ldap dictionary:
            self.stage_two_of_registration(result, realm, subdomain, email, name, name,
                                           skip_registration_form=self.BACKEND_CLASS.full_name_validated)
        self.assertEqual(log_warn.output, [f'WARNING:root:New account email {email} could not be found in LDAP'])
        self.assertEqual(log_debug.output, [f'DEBUG:zulip.ldap:ZulipLDAPAuthBackend: No ldap user matching django_to_ldap_username result: {email}. Input username: {email}'])

    def test_social_auth_complete(self) -> None:
        with mock.patch('social_core.backends.oauth.BaseOAuth2.process_error',
                        side_effect=AuthFailed('Not found')), self.assertLogs(self.logger_string, level='INFO') as m:
            result = self.client_get(reverse('social:complete', args=[self.backend.name]))
            self.assertEqual(result.status_code, 302)
            self.assertIn('login', result.url)
        self.assertEqual(m.output, [
            self.logger_output("AuthFailed: Authentication failed: ", 'info'),
        ])

        with mock.patch('social_core.backends.oauth.BaseOAuth2.auth_complete',
                        side_effect=requests.exceptions.HTTPError), self.assertLogs(self.logger_string, level='INFO') as m:
            result = self.client_get(reverse('social:complete', args=[self.backend.name]))
            self.assertEqual(result.status_code, 302)
            self.assertIn('login', result.url)
        self.assertEqual(m.output, [
            self.logger_output("HTTPError: ", 'info'),
        ])

    def test_social_auth_complete_when_base_exc_is_raised(self) -> None:
        with mock.patch('social_core.backends.oauth.BaseOAuth2.auth_complete',
                        side_effect=AuthStateForbidden('State forbidden')), \
                self.assertLogs(self.logger_string, level='WARNING'):
            result = self.client_get(reverse('social:complete', args=[self.backend.name]))
            self.assertEqual(result.status_code, 302)
            self.assertIn('login', result.url)

    @override_settings(TERMS_OF_SERVICE=None)
    def test_social_auth_invited_as_admin_but_expired(self) -> None:
        iago = self.example_user("iago")
        email = self.nonreg_email("alice")
        name = 'Alice Jones'

        do_invite_users(iago, [email], [], invite_as=PreregistrationUser.INVITE_AS['REALM_ADMIN'])
        expired_date = timezone_now() - datetime.timedelta(days=settings.INVITATION_LINK_VALIDITY_DAYS + 1)
        PreregistrationUser.objects.filter(email=email).update(invited_at=expired_date)

        subdomain = 'zulip'
        realm = get_realm("zulip")
        account_data_dict = self.get_account_data_dict(email=email, name=name)
        result = self.social_auth_test(account_data_dict,
                                       expect_choose_email_screen=True,
                                       subdomain=subdomain, is_signup=True)
        self.stage_two_of_registration(result, realm, subdomain, email, name, name,
                                       self.BACKEND_CLASS.full_name_validated)

        # The invitation is expired, so the user should be created as normal member only.
        created_user = get_user_by_delivery_email(email, realm)
        self.assertEqual(created_user.role, UserProfile.ROLE_MEMBER)

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
                         *, subdomain: str,
                         mobile_flow_otp: Optional[str]=None,
                         desktop_flow_otp: Optional[str]=None,
                         is_signup: bool=False,
                         next: str='',
                         multiuse_object_key: str='',
                         user_agent: Optional[str]=None,
                         extra_attributes: Mapping[str, List[str]]={},
                         **extra_data: Any) -> HttpResponse:
        url, headers = self.prepare_login_url_and_headers(
            subdomain,
            mobile_flow_otp,
            desktop_flow_otp,
            is_signup,
            next,
            multiuse_object_key,
            user_agent=user_agent,
        )

        result = self.client_get(url, **headers)

        expected_result_url_prefix = f'http://testserver/login/{self.backend.name}/'
        if settings.SOCIAL_AUTH_SUBDOMAIN is not None:
            expected_result_url_prefix = (
                f'http://{settings.SOCIAL_AUTH_SUBDOMAIN}.testserver/login/{self.backend.name}/'
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
        data = SAMLAuthBackend.get_data_from_redis(ujson.loads(relay_state)['state_token'])
        assert data is not None
        if next:
            self.assertEqual(data['next'], next)
        if is_signup:
            self.assertEqual(data['is_signup'], '1')

        saml_response = self.generate_saml_response(email=account_data_dict['email'],
                                                    name=account_data_dict['name'],
                                                    extra_attributes=extra_attributes)
        post_params = {"SAMLResponse": saml_response, "RelayState": relay_state}
        # The mock below is necessary, so that python3-saml accepts our SAMLResponse,
        # and doesn't verify the cryptographic signatures etc., since generating
        # a perfectly valid SAMLResponse for the purpose of these tests would be too complex,
        # and we simply use one loaded from a fixture file.
        with mock.patch.object(OneLogin_Saml2_Response, 'is_valid', return_value=True):
            # We are simulating a cross-domain POST request here. Session is a Lax cookie, meaning
            # it won't be sent by the browser in this request. To simulate that effect with the django
            # test client, we flush the session before the request.
            self.client.session.flush()
            result = self.client_post(self.AUTH_FINISH_URL, post_params, **headers)

        return result

    def generate_saml_response(self, email: str, name: str, extra_attributes: Mapping[str, List[str]]={}) -> str:
        """
        The samlresponse.txt fixture has a pre-generated SAMLResponse,
        with {email}, {first_name}, {last_name} placeholders, that can
        be filled out with the data we want.
        """
        name_parts = name.split(' ')
        first_name = name_parts[0]
        last_name = name_parts[1]

        extra_attrs = ''
        for extra_attr_name, extra_attr_values in extra_attributes.items():
            values = ''.join(
                ['<saml2:AttributeValue xmlns:xs="http://www.w3.org/2001/XMLSchema" ' +
                 'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="xs:string">' +
                 f'{value}</saml2:AttributeValue>' for value in extra_attr_values]
            )
            extra_attrs += f'<saml2:Attribute Name="{extra_attr_name}" ' + \
                           'NameFormat="urn:oasis:names:tc:SAML:2.0:attrname-format:unspecified">' + \
                           f'{values}</saml2:Attribute>'

        unencoded_saml_response = self.fixture_data("samlresponse.txt", type="saml").format(
            email=email,
            first_name=first_name,
            last_name=last_name,
            extra_attrs=extra_attrs,
        )
        # SAMLResponse needs to be base64-encoded.
        saml_response: str = base64.b64encode(unencoded_saml_response.encode()).decode()

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
            result = self.social_auth_test(account_data_dict, is_signup=True,
                                           subdomain='zulip', next='/user_uploads/image')
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result.url, self.CONFIG_ERROR_URL)

    def test_config_error_page(self) -> None:
        with self.assertLogs(level='INFO') as info_log:
            result = self.client_get("/accounts/login/social/saml")
        self.assertEqual(info_log.output, [
            'INFO:root:Attempted to initiate SAML authentication with wrong idp argument: None'
        ])
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result.url, '/config-error/saml')
        result = self.client_get(result.url)
        self.assert_in_success_response(["SAML authentication"], result)

    def test_saml_auth_works_without_private_public_keys(self) -> None:
        with self.settings(SOCIAL_AUTH_SAML_SP_PUBLIC_CERT='', SOCIAL_AUTH_SAML_SP_PRIVATE_KEY=''):
            self.test_social_auth_success()

    def test_saml_auth_enabled(self) -> None:
        with self.settings(AUTHENTICATION_BACKENDS=('zproject.backends.SAMLAuthBackend',)):
            self.assertTrue(saml_auth_enabled())
            result = self.client_get("/saml/metadata.xml")
            self.assert_in_success_response(
                [f'entityID="{settings.SOCIAL_AUTH_SAML_SP_ENTITY_ID}"'], result,
            )

    def test_social_auth_complete(self) -> None:
        with mock.patch.object(OneLogin_Saml2_Response, 'is_valid', return_value=True):
            with mock.patch.object(OneLogin_Saml2_Auth, 'is_authenticated', return_value=False), \
                    self.assertLogs(self.logger_string, level='INFO') as m:
                # This mock causes AuthFailed to be raised.
                saml_response = self.generate_saml_response(self.email, self.name)
                relay_state = ujson.dumps(dict(
                    state_token=SAMLAuthBackend.put_data_in_redis({"subdomain": "zulip"}),
                ))
                post_params = {"SAMLResponse": saml_response, "RelayState": relay_state}
                result = self.client_post('/complete/saml/',  post_params)
                self.assertEqual(result.status_code, 302)
                self.assertIn('login', result.url)
            self.assertEqual(m.output, [self.logger_output("AuthFailed: Authentication failed: SAML login failed: [] (None)",
                                                           'info')])

    def test_social_auth_complete_when_base_exc_is_raised(self) -> None:
        with mock.patch.object(OneLogin_Saml2_Response, 'is_valid', return_value=True):
            with mock.patch('social_core.backends.saml.SAMLAuth.auth_complete',
                            side_effect=AuthStateForbidden('State forbidden')), \
                    self.assertLogs(self.logger_string, level='WARNING') as m:
                saml_response = self.generate_saml_response(self.email, self.name)
                relay_state = ujson.dumps(dict(
                    state_token=SAMLAuthBackend.put_data_in_redis({"subdomain": "zulip"}),
                ))
                post_params = {"SAMLResponse": saml_response, "RelayState": relay_state}
                result = self.client_post('/complete/saml/',  post_params)
                self.assertEqual(result.status_code, 302)
                self.assertIn('login', result.url)
            self.assertEqual(m.output, [self.logger_output("Wrong state parameter given.", 'warning')])

    def test_social_auth_complete_bad_params(self) -> None:
        # Simple GET for /complete/saml without the required parameters.
        # This tests the auth_complete wrapped in our SAMLAuthBackend,
        # ensuring it prevents this requests from causing an internal server error.
        with self.assertLogs(self.logger_string, level='INFO') as m:
            result = self.client_get('/complete/saml/')
            self.assertEqual(result.status_code, 302)
            self.assertIn('login', result.url)
        self.assertEqual(m.output, [self.logger_output("/complete/saml/: No SAMLResponse in request.", 'info')])

        # Check that POSTing the RelayState, but with missing SAMLResponse,
        # doesn't cause errors either:
        with self.assertLogs(self.logger_string, level='INFO') as m:
            relay_state = ujson.dumps(dict(
                state_token=SAMLAuthBackend.put_data_in_redis({"subdomain": "zulip"}),
            ))
            post_params = {"RelayState": relay_state}
            result = self.client_post('/complete/saml/',  post_params)
            self.assertEqual(result.status_code, 302)
            self.assertIn('login', result.url)
        self.assertEqual(m.output, [self.logger_output("/complete/saml/: No SAMLResponse in request.", 'info')])

        # Now test bad SAMLResponses.
        with self.assertLogs(self.logger_string, level='INFO') as m:
            relay_state = ujson.dumps(dict(
                state_token=SAMLAuthBackend.put_data_in_redis({"subdomain": "zulip"}),
            ))
            post_params = {"RelayState": relay_state, 'SAMLResponse': ''}
            result = self.client_post('/complete/saml/',  post_params)
            self.assertEqual(result.status_code, 302)
            self.assertIn('login', result.url)
        self.assertTrue(m.output != '')

        with self.assertLogs(self.logger_string, level='INFO') as m:
            relay_state = ujson.dumps(dict(
                state_token=SAMLAuthBackend.put_data_in_redis({"subdomain": "zulip"}),
            ))
            post_params = {"RelayState": relay_state, 'SAMLResponse': 'b'}
            result = self.client_post('/complete/saml/',  post_params)
            self.assertEqual(result.status_code, 302)
            self.assertIn('login', result.url)
        self.assertTrue(m.output != '')

        with self.assertLogs(self.logger_string, level='INFO') as m:
            relay_state = ujson.dumps(dict(
                state_token=SAMLAuthBackend.put_data_in_redis({"subdomain": "zulip"}),
            ))
            post_params = {"RelayState": relay_state, 'SAMLResponse': 'dGVzdA=='}  # base64 encoded 'test'
            result = self.client_post('/complete/saml/',  post_params)
            self.assertEqual(result.status_code, 302)
            self.assertIn('login', result.url)
        self.assertTrue(m.output != '')

    def test_social_auth_complete_no_subdomain(self) -> None:
        with self.assertLogs(self.logger_string, level='INFO') as m:
            post_params = {"RelayState": '',
                           'SAMLResponse': self.generate_saml_response(email=self.example_email("hamlet"),
                                                                       name="King Hamlet")}
            with mock.patch.object(SAMLAuthBackend, 'choose_subdomain', return_value=None):
                result = self.client_post('/complete/saml/',  post_params)
            self.assertEqual(result.status_code, 302)
            self.assertEqual('/login/', result.url)
        self.assertEqual(m.output, [self.logger_output(
            "/complete/saml/: Can't figure out subdomain for this authentication request. relayed_params: {}".format("{}"),
            'info',
        )])

    def test_social_auth_complete_wrong_issuing_idp(self) -> None:
        relay_state = ujson.dumps(dict(
            state_token=SAMLAuthBackend.put_data_in_redis({"subdomain": "zulip"}),
        ))
        saml_response = self.generate_saml_response(email=self.example_email("hamlet"),
                                                    name="King Hamlet")

        # We change the entity_id of the configured test IdP, which means it won't match
        # the Entity ID in the SAMLResponse generated above.
        idps_dict = copy.deepcopy(settings.SOCIAL_AUTH_SAML_ENABLED_IDPS)
        idps_dict['test_idp']['entity_id'] = 'https://different.idp.example.com/'
        with self.settings(SOCIAL_AUTH_SAML_ENABLED_IDPS=idps_dict):
            with self.assertLogs(self.logger_string, level='INFO') as m:
                post_params = {"RelayState": relay_state,
                               "SAMLResponse": saml_response}
                result = self.client_post('/complete/saml/',  post_params)
                self.assertEqual(result.status_code, 302)
                self.assertEqual('/login/', result.url)
            self.assertEqual(m.output, [self.logger_output("/complete/saml/: No valid IdP as issuer of the SAMLResponse.", "info")])

    def test_social_auth_complete_valid_get_idp_bad_samlresponse(self) -> None:
        """
        This tests for a hypothetical scenario where our basic parsing of the SAMLResponse
        successfully returns the issuing IdP, but it fails further down the line, during proper
        validation in the underlying libraries.
        """

        with self.assertLogs(self.logger_string, level='INFO') as m, \
                mock.patch.object(SAMLAuthBackend, 'get_issuing_idp', return_value='test_idp'):
            relay_state = ujson.dumps(dict(
                state_token=SAMLAuthBackend.put_data_in_redis({"subdomain": "zulip"}),
            ))
            post_params = {"RelayState": relay_state, 'SAMLResponse': 'dGVzdA=='}
            result = self.client_post('/complete/saml/',  post_params)
            self.assertEqual(result.status_code, 302)
            self.assertIn('login', result.url)

        self.assertTrue(m.output != '')

    def test_social_auth_saml_bad_idp_param_on_login_page(self) -> None:
        with self.assertLogs(self.logger_string, level='INFO') as m:
            result = self.client_get('/login/saml/')
            self.assertEqual(result.status_code, 302)
            self.assertEqual('/login/', result.url)
        self.assertEqual(m.output, [self.logger_output("/login/saml/ : Bad idp param: KeyError: {}.".format("'idp'"), 'info')])

        with self.assertLogs(self.logger_string, level='INFO') as m:
            result = self.client_get('/login/saml/?idp=bad_idp')
            self.assertEqual(result.status_code, 302)
            self.assertEqual('/login/', result.url)
        self.assertEqual(m.output, [self.logger_output("/login/saml/ : Bad idp param: KeyError: {}.".format("'bad_idp'"), 'info')])

    def test_social_auth_invalid_email(self) -> None:
        """
        This test needs an override from the original class. For security reasons,
        the 'next' and 'mobile_flow_otp' params don't get passed on in the session
        if the authentication attempt failed. See SAMLAuthBackend.auth_complete for details.
        """
        account_data_dict = self.get_account_data_dict(email="invalid", name=self.name)
        with self.assertLogs(self.logger_string, "WARNING") as warn_log:
            result = self.social_auth_test(account_data_dict,
                                           expect_choose_email_screen=True,
                                           subdomain='zulip', next='/user_uploads/image')
        self.assertEqual(warn_log.output, [
            self.logger_output('SAML got invalid email argument.', 'warning')])
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result.url, "/login/")

    def test_social_auth_saml_multiple_idps_configured(self) -> None:
        # Setup a new SOCIAL_AUTH_SAML_ENABLED_IDPS dict with two idps.
        # We deepcopy() dictionaries around for the sake of brevity,
        # to avoid having to spell them out explicitly here.
        # The second idp's configuration is a copy of the first one,
        # with name test_idp2 and altered url. It is also configured to be
        # limited to the zulip realm, so that we get to test both types
        # of configs here.
        idps_dict = copy.deepcopy(settings.SOCIAL_AUTH_SAML_ENABLED_IDPS)
        idps_dict['test_idp2'] = copy.deepcopy(idps_dict['test_idp'])
        idps_dict['test_idp2']['url'] = 'https://idp2.example.com/idp/profile/SAML2/Redirect/SSO'
        idps_dict['test_idp2']['display_name'] = 'Second Test IdP'
        idps_dict['test_idp2']['limit_to_subdomains'] = ['zulip']

        # Run tests with multiple idps configured:
        with self.settings(SOCIAL_AUTH_SAML_ENABLED_IDPS=idps_dict):
            # Go to the login page and check that buttons to log in show up for both IdPs:
            result = self.client_get('/accounts/login/')
            self.assert_in_success_response(["Log in with Test IdP"], result)
            self.assert_in_success_response(["/accounts/login/social/saml/test_idp"], result)
            self.assert_in_success_response(["Log in with Second Test IdP"], result)
            self.assert_in_success_response(["/accounts/login/social/saml/test_idp2"], result)

            # Try successful authentication with the regular idp from all previous tests:
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

    def test_social_auth_saml_idp_limited_to_subdomains_success(self) -> None:
        idps_dict = copy.deepcopy(settings.SOCIAL_AUTH_SAML_ENABLED_IDPS)
        idps_dict['test_idp']['limit_to_subdomains'] = ['zulip']
        with self.settings(SOCIAL_AUTH_SAML_ENABLED_IDPS=idps_dict):
            self.test_social_auth_success()

    def test_social_auth_saml_idp_limited_to_subdomains_attempt_wrong_realm(self) -> None:
        idps_dict = copy.deepcopy(settings.SOCIAL_AUTH_SAML_ENABLED_IDPS)
        idps_dict['test_idp']['limit_to_subdomains'] = ['zulip']
        with self.settings(SOCIAL_AUTH_SAML_ENABLED_IDPS=idps_dict):
            account_data_dict = self.get_account_data_dict(email=self.email, name=self.name)
            with self.assertLogs(self.logger_string, level='INFO') as m:
                result = self.social_auth_test(account_data_dict, subdomain='zephyr')
        self.assertEqual(result.status_code, 302)
        self.assertEqual('/login/', result.url)
        self.assertEqual(m.output, [self.logger_output(
            '/complete/saml/: Authentication request with IdP test_idp but this provider is not enabled '
            'for this subdomain zephyr.', 'info',
        )])

    def test_social_auth_saml_login_bad_idp_arg(self) -> None:
        for action in ['login', 'register']:
            with self.assertLogs(level='INFO') as info_log:
                result = self.client_get(f'/accounts/{action}/social/saml')
            # Missing idp argument.
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result.url, '/config-error/saml')
            self.assertEqual(info_log.output, [
                'INFO:root:Attempted to initiate SAML authentication with wrong idp argument: None'
            ])

            with self.assertLogs(level='INFO') as info_log:
                result = self.client_get(f'/accounts/{action}/social/saml/nonexistent_idp')
            # No such IdP is configured.
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result.url, '/config-error/saml')
            self.assertEqual(info_log.output, [
                'INFO:root:Attempted to initiate SAML authentication with wrong idp argument: nonexistent_idp'
            ])

            result = self.client_get(f'/accounts/{action}/social/saml/')
            # No matching url pattern.
            self.assertEqual(result.status_code, 404)

    def test_social_auth_saml_require_limit_to_subdomains(self) -> None:
        idps_dict = copy.deepcopy(settings.SOCIAL_AUTH_SAML_ENABLED_IDPS)
        idps_dict['test_idp2'] = copy.deepcopy(idps_dict['test_idp'])
        idps_dict['test_idp2']['url'] = 'https://idp2.example.com/idp/profile/SAML2/Redirect/SSO'
        idps_dict['test_idp2']['display_name'] = 'Second Test IdP'
        idps_dict['test_idp2']['limit_to_subdomains'] = ['zulip']

        with self.settings(SOCIAL_AUTH_SAML_ENABLED_IDPS=idps_dict,
                           SAML_REQUIRE_LIMIT_TO_SUBDOMAINS=True):
            with self.assertLogs(self.logger_string, level="ERROR") as m:
                # Initialization of the backend should validate the configured IdPs
                # with respect to the SAML_REQUIRE_LIMIT_TO_SUBDOMAINS setting and remove
                # the non-compliant ones.
                SAMLAuthBackend()
            self.assertEqual(list(settings.SOCIAL_AUTH_SAML_ENABLED_IDPS.keys()),
                             ['test_idp2'])
        self.assertEqual(m.output, [self.logger_output(
            "SAML_REQUIRE_LIMIT_TO_SUBDOMAINS is enabled and the following "
            "IdPs don't have limit_to_subdomains specified and will be ignored: "
            "['test_idp']", 'error',
        )])

    def test_idp_initiated_signin_subdomain_specified(self) -> None:
        post_params = {
            "RelayState": '{"subdomain": "zulip"}',
            "SAMLResponse": self.generate_saml_response(email=self.email, name=self.name),
        }

        with mock.patch.object(OneLogin_Saml2_Response, 'is_valid', return_value=True):
            # We're not able to generate valid signatures in tests, so we need the mock.
            result = self.client_post('/complete/saml/',  post_params)

        data = load_subdomain_token(result)
        self.assertEqual(data['email'], self.example_email("hamlet"))
        self.assertEqual(data['full_name'], self.name)
        self.assertEqual(data['subdomain'], 'zulip')
        self.assertEqual(result.status_code, 302)
        parsed_url = urllib.parse.urlparse(result.url)
        uri = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
        self.assertTrue(uri.startswith('http://zulip.testserver/accounts/login/subdomain/'))

        self.client_get(uri)
        self.assert_logged_in_user_id(self.example_user("hamlet").id)

    def test_choose_subdomain_invalid_subdomain_specified(self) -> None:
        post_params = {
            "RelayState": '{"subdomain": "invalid"}',
            "SAMLResponse": self.generate_saml_response(email=self.email, name=self.name),
        }

        with mock.patch.object(OneLogin_Saml2_Response, 'is_valid', return_value=True):
            # We're not able to generate valid signatures in tests, so we need the mock.
            result = self.client_post('/complete/saml/',  post_params)

        self.assertEqual(result.status_code, 302)
        self.assertEqual(result.url, "/accounts/find/")

    def test_idp_initiated_signin_subdomain_implicit(self) -> None:
        post_params = {
            "RelayState": '',
            "SAMLResponse": self.generate_saml_response(email=self.email, name=self.name),
        }

        with mock.patch.object(OneLogin_Saml2_Response, 'is_valid', return_value=True):
            # We're not able to generate valid signatures in tests, so we need the mock.
            result = self.client_post('http://zulip.testserver/complete/saml/',  post_params)

        data = load_subdomain_token(result)
        self.assertEqual(data['email'], self.example_email("hamlet"))
        self.assertEqual(data['full_name'], self.name)
        self.assertEqual(data['subdomain'], 'zulip')
        self.assertEqual(result.status_code, 302)
        parsed_url = urllib.parse.urlparse(result.url)
        uri = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
        self.assertTrue(uri.startswith('http://zulip.testserver/accounts/login/subdomain/'))

        self.client_get(uri)
        self.assert_logged_in_user_id(self.example_user("hamlet").id)

    def test_idp_initiated_signin_subdomain_implicit_no_relaystate_param(self) -> None:
        post_params = {
            "SAMLResponse": self.generate_saml_response(email=self.email, name=self.name),
        }

        with mock.patch.object(OneLogin_Saml2_Response, 'is_valid', return_value=True):
            # We're not able to generate valid signatures in tests, so we need the mock.
            result = self.client_post('http://zulip.testserver/complete/saml/',  post_params)

        data = load_subdomain_token(result)
        self.assertEqual(data['email'], self.example_email("hamlet"))
        self.assertEqual(data['full_name'], self.name)
        self.assertEqual(data['subdomain'], 'zulip')
        self.assertEqual(result.status_code, 302)
        parsed_url = urllib.parse.urlparse(result.url)
        uri = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
        self.assertTrue(uri.startswith('http://zulip.testserver/accounts/login/subdomain/'))

        self.client_get(uri)
        self.assert_logged_in_user_id(self.example_user("hamlet").id)

    def test_idp_initiated_signin_subdomain_implicit_invalid(self) -> None:
        post_params = {
            "RelayState": '',
            "SAMLResponse": self.generate_saml_response(email=self.email, name=self.name),
        }

        with self.assertLogs(self.logger_string, level='INFO') as m:
            with mock.patch('zproject.backends.get_subdomain', return_value='invalid'):
                # Due to the quirks of our test setup, get_subdomain on all these `some_subdomain.testserver`
                # requests returns 'zulip', so we need to mock it here.
                result = self.client_post('http://invalid.testserver/complete/saml/',  post_params)

            self.assertEqual(result.status_code, 302)
            self.assertEqual('/login/', result.url)
        self.assertEqual(m.output, [self.logger_output(
            "/complete/saml/: Can't figure out subdomain for this authentication request. relayed_params: {}",
            "info",
        )])

    def test_social_auth_saml_idp_org_membership_success(self) -> None:
        idps_dict = copy.deepcopy(settings.SOCIAL_AUTH_SAML_ENABLED_IDPS)
        idps_dict['test_idp']['attr_org_membership'] = 'member'
        with self.settings(SOCIAL_AUTH_SAML_ENABLED_IDPS=idps_dict):
            account_data_dict = self.get_account_data_dict(email=self.email, name=self.name)
            result = self.social_auth_test(account_data_dict,
                                           subdomain='zulip',
                                           expect_choose_email_screen=False,
                                           extra_attributes=dict(member=['zulip']))
            data = load_subdomain_token(result)
            self.assertEqual(data['email'], self.email)
            self.assertEqual(data['full_name'], self.name)
            self.assertEqual(data['subdomain'], 'zulip')
            self.assertEqual(result.status_code, 302)

    def test_social_auth_saml_idp_org_membership_root_subdomain(self) -> None:
        realm = get_realm("zulip")
        realm.string_id = ''
        realm.save()

        idps_dict = copy.deepcopy(settings.SOCIAL_AUTH_SAML_ENABLED_IDPS)
        idps_dict['test_idp']['attr_org_membership'] = 'member'
        with self.settings(SOCIAL_AUTH_SAML_ENABLED_IDPS=idps_dict):
            # Having one of the settings.ROOT_SUBDOMAIN_ALIASES in the membership attributes
            # authorizes the user to access the root subdomain.
            account_data_dict = self.get_account_data_dict(email=self.email, name=self.name)
            result = self.social_auth_test(account_data_dict,
                                           subdomain='',
                                           expect_choose_email_screen=False,
                                           extra_attributes=dict(member=['www']))
            data = load_subdomain_token(result)
            self.assertEqual(data['email'], self.email)
            self.assertEqual(data['full_name'], self.name)
            self.assertEqual(data['subdomain'], '')
            self.assertEqual(result.status_code, 302)

            # Failure, the user doesn't have entitlements for the root subdomain.
            account_data_dict = self.get_account_data_dict(email=self.email, name=self.name)
            with self.assertLogs(self.logger_string, level='INFO') as m:
                result = self.social_auth_test(account_data_dict,
                                               subdomain='',
                                               expect_choose_email_screen=False,
                                               extra_attributes=dict(member=['zephyr']))
            self.assertEqual(result.status_code, 302)
            self.assertEqual(m.output, [self.logger_output(
                "AuthFailed: Authentication failed: SAML user from IdP test_idp rejected due to " +
                "missing entitlement for subdomain ''. User entitlements: ['zephyr'].",
                "info",
            )])

    def test_social_auth_saml_idp_org_membership_failed(self) -> None:
        idps_dict = copy.deepcopy(settings.SOCIAL_AUTH_SAML_ENABLED_IDPS)
        idps_dict['test_idp']['attr_org_membership'] = 'member'
        with self.settings(SOCIAL_AUTH_SAML_ENABLED_IDPS=idps_dict):
            account_data_dict = self.get_account_data_dict(email=self.email, name=self.name)
            with self.assertLogs(self.logger_string, level='INFO') as m:
                result = self.social_auth_test(account_data_dict, subdomain='zulip',
                                               extra_attributes=dict(member=['zephyr', 'othersubdomain']))
        self.assertEqual(result.status_code, 302)
        self.assertEqual('/login/', result.url)
        self.assertEqual(m.output, [self.logger_output(
            "AuthFailed: Authentication failed: SAML user from IdP test_idp rejected due to " +
            "missing entitlement for subdomain 'zulip'. User entitlements: ['zephyr', 'othersubdomain'].",
            "info",
        )])

class AppleAuthMixin:
    BACKEND_CLASS = AppleAuthBackend
    CLIENT_KEY_SETTING = "SOCIAL_AUTH_APPLE_KEY"
    AUTHORIZATION_URL = "https://appleid.apple.com/auth/authorize"
    ACCESS_TOKEN_URL = "https://appleid.apple.com/auth/token"
    AUTH_FINISH_URL = "/complete/apple/"
    CONFIG_ERROR_URL = "/config-error/apple"

    def generate_id_token(self, account_data_dict: Dict[str, str], audience: Optional[str]=None) -> str:
        payload = account_data_dict

        # This setup is important because python-social-auth decodes `id_token`
        # with `SOCIAL_AUTH_APPLE_CLIENT` as the `audience`
        payload['aud'] = settings.SOCIAL_AUTH_APPLE_CLIENT

        if audience is not None:
            payload['aud'] = audience

        headers = {"kid": "SOMEKID"}
        private_key = settings.APPLE_ID_TOKEN_GENERATION_KEY

        id_token = jwt.encode(payload, private_key, algorithm='RS256',
                              headers=headers).decode('utf-8')

        return id_token

    def get_account_data_dict(self, email: str, name: str) -> Dict[str, Any]:
        name_parts = name.split(' ')
        first_name = name_parts[0]
        last_name = ''
        if (len(name_parts) > 0):
            last_name = name_parts[-1]
        name_dict = {'firstName': first_name, 'lastName': last_name}
        return dict(email=email, name=name_dict, email_verified=True)

class AppleIdAuthBackendTest(AppleAuthMixin, SocialAuthBase):
    __unittest_skip__ = False

    LOGIN_URL = "/accounts/login/social/apple"
    SIGNUP_URL = "/accounts/register/social/apple"

    # This URL isn't used in the Apple auth flow, so we just set a
    # dummy value to keep SocialAuthBase common code happy.
    USER_INFO_URL = '/invalid-unused-url'

    def social_auth_test_finish(self, result: HttpResponse,
                                account_data_dict: Dict[str, str],
                                expect_choose_email_screen: bool,
                                headers: Any,
                                **extra_data: Any) -> HttpResponse:
        parsed_url = urllib.parse.urlparse(result.url)
        state = urllib.parse.parse_qs(parsed_url.query)['state']
        self.client.session.flush()
        result = self.client_post(self.AUTH_FINISH_URL,
                                  dict(state=state), **headers)
        return result

    def register_extra_endpoints(self, requests_mock: responses.RequestsMock,
                                 account_data_dict: Dict[str, str],
                                 **extra_data: Any) -> None:
        # This is an URL of an endpoint on Apple servers that returns
        # the public keys to be used for verifying the signature
        # on the JWT id_token.
        requests_mock.add(
            requests_mock.GET,
            self.BACKEND_CLASS.JWK_URL,
            status=200,
            json=json.loads(settings.APPLE_JWK),
        )

    def generate_access_url_payload(self, account_data_dict: Dict[str, str]) -> str:
        # The ACCESS_TOKEN_URL endpoint works a bit different in standard Oauth2,
        # where the token_data_dict contains some essential data. we add that data here.
        return json.dumps({
            'access_token': 'foobar',
            'expires_in': time.time() + 60*5,
            'id_token': self.generate_id_token(account_data_dict),
            'token_type': 'bearer',
        })

    def test_apple_auth_enabled(self) -> None:
        with self.settings(AUTHENTICATION_BACKENDS=('zproject.backends.AppleAuthBackend',)):
            self.assertTrue(apple_auth_enabled())

    def test_auth_registration_with_no_name_sent_from_apple(self) -> None:
        """
        Apple doesn't send the name in consecutive attempts if user registration
        fails the first time. This tests verifies that the social pipeline is able
        to handle the case of the backend not providing this information.
        """
        email = "newuser@zulip.com"
        subdomain = "zulip"
        realm = get_realm("zulip")
        account_data_dict = self.get_account_data_dict(email=email, name='')
        result = self.social_auth_test(account_data_dict,
                                       expect_choose_email_screen=True,
                                       subdomain=subdomain, is_signup=True)
        self.stage_two_of_registration(result, realm, subdomain, email, '', 'Full Name',
                                       skip_registration_form=False,
                                       expect_full_name_prepopulated=False)

    def test_id_token_verification_failure(self) -> None:
        account_data_dict = self.get_account_data_dict(email=self.email, name=self.name)
        with self.assertLogs(self.logger_string, level='INFO') as m:
            with mock.patch("jwt.decode", side_effect=PyJWTError):
                result = self.social_auth_test(account_data_dict,
                                               expect_choose_email_screen=True,
                                               subdomain='zulip', is_signup=True)
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result.url, "/login/")
        self.assertEqual(m.output, [
            self.logger_output("AuthFailed: Authentication failed: Token validation failed", "info"),
        ])

    def test_validate_state(self) -> None:
        with self.assertLogs(self.logger_string, level='INFO') as m:

            # (1) check if auth fails if no state value is sent.
            result = self.client_post('/complete/apple/')
            self.assertEqual(result.status_code, 302)
            self.assertIn('login', result.url)

            # (2) Check if auth fails when a state sent has no valid data stored in redis.
            fake_state = "fa42e4ccdb630f0070c1daab70ad198d8786d4b639cd7a1b4db4d5a13c623060"
            result = self.client_post('/complete/apple/', {'state': fake_state})
            self.assertEqual(result.status_code, 302)
            self.assertIn('login', result.url)
        self.assertEqual(m.output, [
            self.logger_output("Sign in with Apple failed: missing state parameter.", "info"),  # (1)
            self.logger_output("Missing needed parameter state", "warning"),
            self.logger_output("Sign in with Apple failed: bad state token.", "info"),  # (2)
            self.logger_output("Wrong state parameter given.", "warning"),
        ])

class AppleAuthBackendNativeFlowTest(AppleAuthMixin, SocialAuthBase):
    __unittest_skip__ = False

    SIGNUP_URL = '/complete/apple/'
    LOGIN_URL = '/complete/apple/'

    def prepare_login_url_and_headers(
        self,
        subdomain: str,
        mobile_flow_otp: Optional[str]=None,
        desktop_flow_otp: Optional[str]=None,
        is_signup: bool=False,
        next: str='',
        multiuse_object_key: str='',
        alternative_start_url: Optional[str]=None,
        id_token: Optional[str]=None,
        *,
        user_agent: Optional[str]=None,
    ) -> Tuple[str, Dict[str, Any]]:
        url, headers = super().prepare_login_url_and_headers(
            subdomain, mobile_flow_otp, desktop_flow_otp, is_signup, next,
            multiuse_object_key, alternative_start_url=alternative_start_url,
            user_agent=user_agent,
        )

        params = {'native_flow': 'true'}

        if id_token is not None:
            params['id_token'] = id_token

        if is_signup:
            params['is_signup'] = '1'

        if subdomain:
            params['subdomain'] = subdomain

        url += f"&{urllib.parse.urlencode(params)}"
        return url, headers

    def social_auth_test(self, account_data_dict: Dict[str, str],
                         *, subdomain: str,
                         mobile_flow_otp: Optional[str]=None,
                         desktop_flow_otp: Optional[str]=None,
                         is_signup: bool=False,
                         next: str='',
                         multiuse_object_key: str='',
                         alternative_start_url: Optional[str]=None,
                         skip_id_token: bool=False,
                         user_agent: Optional[str]=None,
                         **extra_data: Any) -> HttpResponse:
        """In Apple's native authentication flow, the client app authenticates
        with Apple and receives the JWT id_token, before contacting
        the Zulip server.  The app sends an appropriate request with
        it to /complete/apple/ to get logged in.  See the backend
        class for details.

        As a result, we need a custom social_auth_test function that
        effectively just does the second half of the flow (i.e. the
        part after the redirect from this third-party authentication
        provider) with a properly generated id_token.
        """

        if not skip_id_token:
            id_token: Optional[str] = self.generate_id_token(account_data_dict, settings.SOCIAL_AUTH_APPLE_APP_ID)
        else:
            id_token = None

        url, headers = self.prepare_login_url_and_headers(
            subdomain, mobile_flow_otp, desktop_flow_otp, is_signup, next,
            multiuse_object_key, alternative_start_url=self.AUTH_FINISH_URL,
            user_agent=user_agent, id_token=id_token,
        )

        with self.apple_jwk_url_mock():
            result = self.client_get(url, **headers)

        return result

    @contextmanager
    def apple_jwk_url_mock(self) -> Iterator[None]:
        with responses.RequestsMock(assert_all_requests_are_fired=False) as requests_mock:
            # The server fetches public keys for validating the id_token
            # from Apple servers. We need to mock that URL to return our key,
            # created for these tests.
            requests_mock.add(
                requests_mock.GET,
                self.BACKEND_CLASS.JWK_URL,
                status=200,
                json=json.loads(settings.APPLE_JWK),
            )
            yield

    def test_no_id_token_sent(self) -> None:
        account_data_dict = self.get_account_data_dict(email=self.email, name=self.name)
        result = self.social_auth_test(account_data_dict,
                                       expect_choose_email_screen=False,
                                       subdomain='zulip', next='/user_uploads/image',
                                       skip_id_token=True)
        self.assert_json_error(result, "Missing id_token parameter")

    def test_social_auth_session_fields_cleared_correctly(self) -> None:
        mobile_flow_otp = '1234abcd' * 8

        def initiate_auth(mobile_flow_otp: Optional[str]=None) -> None:
            url, headers = self.prepare_login_url_and_headers(subdomain='zulip',
                                                              id_token='invalid',
                                                              mobile_flow_otp=mobile_flow_otp)
            result = self.client_get(url, **headers)
            self.assertEqual(result.status_code, 302)

        with self.assertLogs(level='INFO') as info_log:
            # Start Apple auth with mobile_flow_otp param. It should get saved into the session
            # on SOCIAL_AUTH_SUBDOMAIN.
            initiate_auth(mobile_flow_otp)

        self.assertEqual(self.client.session['mobile_flow_otp'], mobile_flow_otp)
        self.assertEqual(info_log.output, [
            'INFO:root:/complete/apple/: Authentication failed: Token validation failed'
        ])

        with self.assertLogs(level='INFO') as info_log:
            # Make a request without mobile_flow_otp param and verify the field doesn't persist
            # in the session from the previous request.
            initiate_auth()

        self.assertEqual(self.client.session.get('mobile_flow_otp'), None)
        self.assertEqual(info_log.output, [
            'INFO:root:/complete/apple/: Authentication failed: Token validation failed'
        ])

    def test_id_token_with_invalid_aud_sent(self) -> None:
        account_data_dict = self.get_account_data_dict(email=self.email, name=self.name)
        url, headers = self.prepare_login_url_and_headers(
            subdomain='zulip', alternative_start_url=self.AUTH_FINISH_URL,
            id_token=self.generate_id_token(account_data_dict, audience='com.different.app'),
        )

        with self.apple_jwk_url_mock(), mock.patch('logging.info') as mock_info:
            result = self.client_get(url, **headers)
            mock_info.assert_called_once_with('/complete/apple/: %s',
                                              'Authentication failed: Token validation failed')
        return result

    def test_social_auth_desktop_success(self) -> None:
        """
        The desktop app doesn't use the native flow currently and the desktop app flow in its
        current form happens in the browser, thus only the webflow is viable there.
        """
        pass

    def test_social_auth_no_key(self) -> None:
        """
        The basic validation of server configuration is handled on the
        /login/social/apple/ endpoint which isn't even a part of the native flow.
        """
        pass

class GitHubAuthBackendTest(SocialAuthBase):
    __unittest_skip__ = False

    BACKEND_CLASS = GitHubAuthBackend
    CLIENT_KEY_SETTING = "SOCIAL_AUTH_GITHUB_KEY"
    CLIENT_SECRET_SETTING = "SOCIAL_AUTH_GITHUB_SECRET"
    LOGIN_URL = "/accounts/login/social/github"
    SIGNUP_URL = "/accounts/register/social/github"
    AUTHORIZATION_URL = "https://github.com/login/oauth/authorize"
    ACCESS_TOKEN_URL = "https://github.com/login/oauth/access_token"
    USER_INFO_URL = "https://api.github.com/user"
    AUTH_FINISH_URL = "/complete/github/"
    CONFIG_ERROR_URL = "/config-error/github"
    email_data: List[Dict[str, Any]] = []

    def social_auth_test_finish(self, result: HttpResponse,
                                account_data_dict: Dict[str, str],
                                expect_choose_email_screen: bool,
                                headers: Any,
                                expect_noreply_email_allowed: bool=False,
                                **extra_data: Any) -> HttpResponse:
        parsed_url = urllib.parse.urlparse(result.url)
        csrf_state = urllib.parse.parse_qs(parsed_url.query)['state']
        result = self.client_get(self.AUTH_FINISH_URL,
                                 dict(state=csrf_state), **headers)

        if expect_choose_email_screen:
            # As GitHub authenticates multiple email addresses,
            # we'll have an additional screen where the user selects
            # which email address to login using (this screen is a
            # "partial" state of the python-social-auth pipeline).
            #
            # TODO: Generalize this testing code for use with other
            # authentication backends when a new authentacation backend
            # that requires "choose email" screen;
            self.assert_in_success_response(["Select account"], result)
            # Verify that all the emails returned by GitHub auth
            # are in the "choose email" screen.
            all_emails_verified = True
            for email_data_dict in self.email_data:
                email = email_data_dict["email"]
                if email.endswith("@users.noreply.github.com") and not expect_noreply_email_allowed:
                    self.assert_not_in_success_response([email], result)
                elif email_data_dict.get('verified'):
                    self.assert_in_success_response([email], result)
                else:
                    # We may change this if we provide a way to see
                    # the list of emails the user had.
                    self.assert_not_in_success_response([email], result)
                    all_emails_verified = False

            if all_emails_verified:
                self.assert_not_in_success_response(["also has unverified email"], result)
            else:
                self.assert_in_success_response(["also has unverified email"], result)
            result = self.client_get(self.AUTH_FINISH_URL,
                                     dict(state=csrf_state, email=account_data_dict['email']), **headers)

        return result

    def register_extra_endpoints(self, requests_mock: responses.RequestsMock,
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

        requests_mock.add(
            requests_mock.GET,
            "https://api.github.com/user/emails",
            status=200,
            body=json.dumps(email_data),
        )

        requests_mock.add(
            requests_mock.GET,
            "https://api.github.com/teams/zulip-webapp/members/None",
            status=200,
            body=json.dumps(email_data),
        )

        self.email_data = email_data

    def get_account_data_dict(self, email: str, name: str, user_avatar_url: str='') -> Dict[str, Any]:
        return dict(email=email, name=name, user_avatar_url=user_avatar_url)

    def test_social_auth_email_not_verified(self) -> None:
        account_data_dict = self.get_account_data_dict(email=self.email, name=self.name)
        email_data = [
            dict(email=account_data_dict["email"],
                 verified=False,
                 primary=True),
        ]
        with self.assertLogs(self.logger_string, level='WARNING') as m:
            result = self.social_auth_test(account_data_dict,
                                           subdomain='zulip',
                                           email_data=email_data)
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result.url, "/login/")
        self.assertEqual(m.output, [self.logger_output(
            "Social auth ({}) failed because user has no verified emails".format('GitHub'),
            "warning",
        )])

    @override_settings(SOCIAL_AUTH_GITHUB_TEAM_ID='zulip-webapp')
    def test_social_auth_github_team_not_member_failed(self) -> None:
        account_data_dict = self.get_account_data_dict(email=self.email, name=self.name)
        with mock.patch('social_core.backends.github.GithubTeamOAuth2.user_data',
                        side_effect=AuthFailed('Not found')), \
                self.assertLogs(self.logger_string, level='INFO') as mock_info:
            result = self.social_auth_test(account_data_dict,
                                           subdomain='zulip')
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result.url, "/login/")
        self.assertEqual(mock_info.output, [self.logger_output(
            "GitHub user is not member of required team", 'info',
        )])

    @override_settings(SOCIAL_AUTH_GITHUB_TEAM_ID='zulip-webapp')
    def test_social_auth_github_team_member_success(self) -> None:
        account_data_dict = self.get_account_data_dict(email=self.email, name=self.name)
        with mock.patch('social_core.backends.github.GithubTeamOAuth2.user_data',
                        return_value=account_data_dict):
            result = self.social_auth_test(account_data_dict,
                                           expect_choose_email_screen=False,
                                           subdomain='zulip')
        data = load_subdomain_token(result)
        self.assertEqual(data['email'], self.example_email("hamlet"))
        self.assertEqual(data['full_name'], self.name)
        self.assertEqual(data['subdomain'], 'zulip')

    @override_settings(SOCIAL_AUTH_GITHUB_ORG_NAME='Zulip')
    def test_social_auth_github_organization_not_member_failed(self) -> None:
        account_data_dict = self.get_account_data_dict(email=self.email, name=self.name)
        with mock.patch('social_core.backends.github.GithubOrganizationOAuth2.user_data',
                        side_effect=AuthFailed('Not found')), \
                self.assertLogs(self.logger_string, level='INFO') as mock_info:
            result = self.social_auth_test(account_data_dict,
                                           subdomain='zulip')
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result.url, "/login/")
        self.assertEqual(mock_info.output, [self.logger_output(
            "GitHub user is not member of required organization", "info",
        )])

    @override_settings(SOCIAL_AUTH_GITHUB_ORG_NAME='Zulip')
    def test_social_auth_github_organization_member_success(self) -> None:
        account_data_dict = self.get_account_data_dict(email=self.email, name=self.name)
        with mock.patch('social_core.backends.github.GithubOrganizationOAuth2.user_data',
                        return_value=account_data_dict):
            result = self.social_auth_test(account_data_dict,
                                           expect_choose_email_screen=False,
                                           subdomain='zulip')
        data = load_subdomain_token(result)
        self.assertEqual(data['email'], self.example_email("hamlet"))
        self.assertEqual(data['full_name'], self.name)
        self.assertEqual(data['subdomain'], 'zulip')

    def test_github_auth_enabled(self) -> None:
        with self.settings(AUTHENTICATION_BACKENDS=('zproject.backends.GitHubAuthBackend',)):
            self.assertTrue(github_auth_enabled())

    def test_github_oauth2_success_non_primary(self) -> None:
        account_data_dict = self.get_account_data_dict(email='nonprimary@zulip.com', name="Non Primary")
        email_data = [
            dict(email=account_data_dict["email"],
                 verified=True),
            dict(email='hamlet@zulip.com',
                 verified=True,
                 primary=True),
            dict(email="aaron@zulip.com",
                 verified=True),
            dict(email="ignored@example.com",
                 verified=False),
        ]
        result = self.social_auth_test(account_data_dict,
                                       subdomain='zulip', email_data=email_data,
                                       expect_choose_email_screen=True,
                                       next='/user_uploads/image')
        data = load_subdomain_token(result)
        self.assertEqual(data['email'], 'nonprimary@zulip.com')
        self.assertEqual(data['full_name'], 'Non Primary')
        self.assertEqual(data['subdomain'], 'zulip')
        self.assertEqual(data['redirect_to'], '/user_uploads/image')
        self.assertEqual(result.status_code, 302)
        parsed_url = urllib.parse.urlparse(result.url)
        uri = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
        self.assertTrue(uri.startswith('http://zulip.testserver/accounts/login/subdomain/'))

    def test_github_oauth2_success_single_email(self) -> None:
        # If the user has a single email associated with its GitHub account,
        # the choose email screen should not be shown and the first email
        # should be used for user's signup/login.
        account_data_dict = self.get_account_data_dict(email='not-hamlet@zulip.com', name=self.name)
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
        self.assertEqual(data['full_name'], self.name)
        self.assertEqual(data['subdomain'], 'zulip')
        self.assertEqual(data['redirect_to'], '/user_uploads/image')
        self.assertEqual(result.status_code, 302)
        parsed_url = urllib.parse.urlparse(result.url)
        uri = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
        self.assertTrue(uri.startswith('http://zulip.testserver/accounts/login/subdomain/'))

    def test_github_oauth2_login_only_one_account_exists(self) -> None:
        # In a login flow, if only one of the user's verified emails
        # is associated with an existing account, the user should be
        # just logged in (skipping the "choose email screen").  We
        # only want that screen if the user were instead trying to
        # register a new account, which they're not.
        account_data_dict = self.get_account_data_dict(email=self.email, name=self.name)
        email_data = [
            dict(email=account_data_dict["email"],
                 verified=True),
            dict(email="notprimary@zulip.com",
                 verified=True),
            dict(email="verifiedemail@zulip.com",
                 verified=True),
        ]
        result = self.social_auth_test(account_data_dict,
                                       subdomain='zulip',
                                       email_data=email_data,
                                       expect_choose_email_screen=False,
                                       next='/user_uploads/image')
        data = load_subdomain_token(result)
        self.assertEqual(data['email'], account_data_dict["email"])
        self.assertEqual(data['full_name'], self.name)
        self.assertEqual(data['subdomain'], 'zulip')
        self.assertEqual(data['redirect_to'], '/user_uploads/image')
        self.assertEqual(result.status_code, 302)
        parsed_url = urllib.parse.urlparse(result.url)
        uri = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
        self.assertTrue(uri.startswith('http://zulip.testserver/accounts/login/subdomain/'))

    def test_github_oauth2_login_multiple_accounts_exist(self) -> None:
        # In the login flow, if multiple of the user's verified emails
        # are associated with existing accounts, we expect the choose
        # email screen to select which account to use.
        hamlet = self.example_user("hamlet")
        account_data_dict = self.get_account_data_dict(email='hamlet@zulip.com', name="Hamlet")
        email_data = [
            dict(email=account_data_dict["email"],
                 verified=True),
            dict(email='hamlet@zulip.com',
                 verified=True,
                 primary=True),
            dict(email="aaron@zulip.com",
                 verified=True),
            dict(email="ignored@example.com",
                 verified=False),
        ]
        result = self.social_auth_test(account_data_dict,
                                       subdomain='zulip', email_data=email_data,
                                       expect_choose_email_screen=True,
                                       next='/user_uploads/image')
        data = load_subdomain_token(result)
        self.assertEqual(data['email'], 'hamlet@zulip.com')
        self.assertEqual(data['full_name'], hamlet.full_name)
        self.assertEqual(data['subdomain'], 'zulip')
        self.assertEqual(data['redirect_to'], '/user_uploads/image')
        self.assertEqual(result.status_code, 302)
        parsed_url = urllib.parse.urlparse(result.url)
        uri = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
        self.assertTrue(uri.startswith('http://zulip.testserver/accounts/login/subdomain/'))

    def test_github_oauth2_login_no_account_exists(self) -> None:
        # In the login flow, if the user has multiple verified emails,
        # none of which are associated with an existing account, the
        # choose email screen should be shown (which will lead to a
        # "continue to registration" choice).
        account_data_dict = self.get_account_data_dict(email="not-hamlet@zulip.com", name="Not Hamlet")
        email_data = [
            dict(email=account_data_dict["email"],
                 verified=True),
            dict(email="notprimary@zulip.com",
                 verified=True),
            dict(email="verifiedemail@zulip.com",
                 verified=True),
        ]
        result = self.social_auth_test(account_data_dict,
                                       subdomain='zulip',
                                       email_data=email_data,
                                       expect_choose_email_screen=True)
        email = account_data_dict['email']
        name = account_data_dict['name']
        subdomain = 'zulip'
        realm = get_realm("zulip")
        self.stage_two_of_registration(result, realm, subdomain, email, name, name,
                                       expect_confirm_registration_page=True,
                                       skip_registration_form=False)

    def test_github_oauth2_signup_choose_existing_account(self) -> None:
        # In the sign up flow, if the user has chosen an email of an
        # existing account, the user will be logged in.
        account_data_dict = self.get_account_data_dict(email=self.email, name=self.name)
        email_data = [
            dict(email=account_data_dict["email"],
                 verified=True),
            dict(email="notprimary@zulip.com",
                 verified=True),
            dict(email="verifiedemail@zulip.com",
                 verified=True),
        ]
        result = self.social_auth_test(account_data_dict,
                                       email_data=email_data,
                                       is_signup=True,
                                       subdomain='zulip',
                                       expect_choose_email_screen=True,
                                       next='/user_uploads/image')
        data = load_subdomain_token(result)
        self.assertEqual(data['email'], account_data_dict["email"])
        self.assertEqual(data['full_name'], account_data_dict["name"])
        self.assertEqual(data['subdomain'], 'zulip')
        self.assertEqual(data['redirect_to'], '/user_uploads/image')
        self.assertEqual(result.status_code, 302)
        parsed_url = urllib.parse.urlparse(result.url)
        uri = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
        self.assertTrue(uri.startswith('http://zulip.testserver/accounts/login/subdomain/'))

    def test_github_oauth2_signup_choose_new_email_to_register(self) -> None:
        # In the sign up flow, if the user has multiple verified
        # emails, we show the "choose email" screen, even if the user
        # has another verified email with an existing account,
        # allowing the user to register a second account associated
        # with the second email.
        email = "newuser@zulip.com"
        name = 'Full Name'
        subdomain = 'zulip'
        realm = get_realm("zulip")
        account_data_dict = self.get_account_data_dict(email=email, name=name)
        email_data = [
            dict(email="hamlet@zulip.com",
                 verified=True),
            dict(email=email,
                 verified=True),
            dict(email="verifiedemail@zulip.com",
                 verified=True),
        ]
        result = self.social_auth_test(account_data_dict,
                                       email_data = email_data,
                                       expect_choose_email_screen=True,
                                       subdomain=subdomain, is_signup=True)
        self.stage_two_of_registration(result, realm, subdomain, email, name, name,
                                       self.BACKEND_CLASS.full_name_validated)

    def test_github_oauth2_email_no_reply_dot_github_dot_com(self) -> None:
        # As emails ending with `noreply.github.com` are excluded from
        # verified_emails unless an account with that email already exists,
        # choosing it as an email should raise a `email not associated` warning.
        noreply_email = "hamlet@users.noreply.github.com"
        account_data_dict = self.get_account_data_dict(email=noreply_email, name=self.name)
        email_data = [
            dict(email="notprimary@zulip.com",
                 verified=True),
            dict(email="hamlet@zulip.com",
                 verified=True,
                 primary=True),
            dict(email="aaron@zulip.com",
                 verified=True),
            dict(email=account_data_dict["email"],
                 verified=True),
        ]
        with self.assertLogs(self.logger_string, level='WARNING') as m:
            result = self.social_auth_test(account_data_dict,
                                           subdomain='zulip',
                                           expect_choose_email_screen=True,
                                           email_data=email_data)
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result.url, "/login/")
        self.assertEqual(m.output, [self.logger_output(
            "Social auth (GitHub) failed because user has no verified"
            " emails associated with the account",
            "warning",
        )])

        # Now we create the user account with the noreply email and verify that it's
        # possible to sign in to it.
        realm = get_realm("zulip")
        do_create_user(noreply_email, 'password', realm, account_data_dict["name"])
        result = self.social_auth_test(account_data_dict,
                                       subdomain='zulip',
                                       expect_choose_email_screen=True,
                                       expect_noreply_email_allowed=True,
                                       email_data=email_data)
        data = load_subdomain_token(result)
        self.assertEqual(data['email'], account_data_dict["email"])
        self.assertEqual(data['full_name'], account_data_dict["name"])
        self.assertEqual(data['subdomain'], 'zulip')
        self.assertEqual(result.status_code, 302)
        parsed_url = urllib.parse.urlparse(result.url)
        uri = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
        self.assertTrue(uri.startswith('http://zulip.testserver/accounts/login/subdomain/'))

    def test_github_oauth2_email_not_associated(self) -> None:
        account_data_dict = self.get_account_data_dict(email='not-associated@zulip.com', name=self.name)
        email_data = [
            dict(email='nonprimary@zulip.com',
                 verified=True),
            dict(email='hamlet@zulip.com',
                 verified=True,
                 primary=True),
            dict(email="aaron@zulip.com",
                 verified=True),
        ]
        with self.assertLogs(self.logger_string, level='WARNING') as m:
            result = self.social_auth_test(account_data_dict,
                                           subdomain='zulip',
                                           expect_choose_email_screen=True,
                                           email_data=email_data)
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result.url, "/login/")
        self.assertEqual(m.output, [self.logger_output(
            "Social auth (GitHub) failed because user has no verified"
            " emails associated with the account",
            "warning",
        )])

    def test_github_unverified_email_with_existing_account(self) -> None:
        # check if a user is denied to login if the user manages to
        # send an unverified email that has an existing account in
        # organisation through `email` GET parameter.
        account_data_dict = self.get_account_data_dict(email='hamlet@zulip.com', name=self.name)
        email_data = [
            dict(email='iago@zulip.com',
                 verified=True),
            dict(email='hamlet@zulip.com',
                 verified=False),
            dict(email="aaron@zulip.com",
                 verified=True,
                 primary=True),
        ]
        with self.assertLogs(self.logger_string, level='WARNING') as m:
            result = self.social_auth_test(account_data_dict,
                                           subdomain='zulip',
                                           expect_choose_email_screen=True,
                                           email_data=email_data)
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result.url, "/login/")
        self.assertEqual(m.output, [self.logger_output(
            "Social auth ({}) failed because user has no verified emails associated with the account".format("GitHub"),
            "warning",
        )])

class GitLabAuthBackendTest(SocialAuthBase):
    __unittest_skip__ = False

    BACKEND_CLASS = GitLabAuthBackend
    CLIENT_KEY_SETTING = "SOCIAL_AUTH_GITLAB_KEY"
    CLIENT_SECRET_SETTING = "SOCIAL_AUTH_GITLAB_SECRET"
    LOGIN_URL = "/accounts/login/social/gitlab"
    SIGNUP_URL = "/accounts/register/social/gitlab"
    AUTHORIZATION_URL = "https://gitlab.com/oauth/authorize"
    ACCESS_TOKEN_URL = "https://gitlab.com/oauth/token"
    USER_INFO_URL = "https://gitlab.com/api/v4/user"
    AUTH_FINISH_URL = "/complete/gitlab/"
    CONFIG_ERROR_URL = "/config-error/gitlab"

    def test_gitlab_auth_enabled(self) -> None:
        with self.settings(AUTHENTICATION_BACKENDS=('zproject.backends.GitLabAuthBackend',)):
            self.assertTrue(gitlab_auth_enabled())

    def get_account_data_dict(self, email: str, name: str) -> Dict[str, Any]:
        return dict(email=email, name=name, email_verified=True)

class GoogleAuthBackendTest(SocialAuthBase):
    __unittest_skip__ = False

    BACKEND_CLASS = GoogleAuthBackend
    CLIENT_KEY_SETTING = "SOCIAL_AUTH_GOOGLE_KEY"
    CLIENT_SECRET_SETTING = "SOCIAL_AUTH_GOOGLE_SECRET"
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
        with self.assertLogs(self.logger_string, level='WARNING') as m:
            result = self.social_auth_test(account_data_dict,
                                           subdomain='zulip')
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result.url, "/login/")
        self.assertEqual(m.output, [self.logger_output(
            "Social auth ({}) failed because user has no verified emails".format("Google"),
            "warning",
        )])

    def test_social_auth_mobile_realm_uri(self) -> None:
        mobile_flow_otp = '1234abcd' * 8
        account_data_dict = self.get_account_data_dict(email=self.email, name='Full Name')

        with self.settings(REALM_MOBILE_REMAP_URIS={'http://zulip.testserver': 'http://zulip-mobile.testserver'}):
            result = self.social_auth_test(account_data_dict, subdomain='zulip',
                                           expect_choose_email_screen=True,
                                           alternative_start_url="/accounts/login/google/",
                                           mobile_flow_otp=mobile_flow_otp)

        self.assertEqual(result.status_code, 302)
        redirect_url = result['Location']
        parsed_url = urllib.parse.urlparse(redirect_url)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        self.assertEqual(parsed_url.scheme, 'zulip')
        self.assertEqual(query_params["realm"], ['http://zulip-mobile.testserver'])
        self.assertEqual(query_params["email"], [self.example_email("hamlet")])
        encrypted_api_key = query_params["otp_encrypted_api_key"][0]
        hamlet_api_keys = get_all_api_keys(self.example_user('hamlet'))
        self.assertIn(otp_decrypt_api_key(encrypted_api_key, mobile_flow_otp), hamlet_api_keys)

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

    def get_log_into_subdomain(self, data: ExternalAuthDataDict, *, subdomain: str='zulip',
                               force_token: Optional[str]=None) -> HttpResponse:
        if force_token is None:
            token = ExternalAuthResult(data_dict=data).store_data()
        else:
            token = force_token
        url_path = reverse('zerver.views.auth.log_into_subdomain', args=[token])
        return self.client_get(url_path, subdomain=subdomain)

    def test_redirect_to_next_url_for_log_into_subdomain(self) -> None:
        def test_redirect_to_next_url(next: str='') -> HttpResponse:
            data: ExternalAuthDataDict = {
                'full_name': 'Hamlet',
                'email': self.example_email("hamlet"),
                'subdomain': 'zulip',
                'is_signup': False,
                'redirect_to': next,
            }
            user_profile = self.example_user('hamlet')
            with mock.patch(
                    'zerver.views.auth.authenticate',
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

    def test_log_into_subdomain_when_token_is_malformed(self) -> None:
        data: ExternalAuthDataDict = {
            'full_name': 'Full Name',
            'email': self.example_email("hamlet"),
            'subdomain': 'zulip',
            'is_signup': False,
            'redirect_to': '',
        }
        with mock.patch("logging.warning") as mock_warn:
            result = self.get_log_into_subdomain(data, force_token='nonsense')
            mock_warn.assert_called_once_with("log_into_subdomain: Malformed token given: %s", "nonsense")
        self.assertEqual(result.status_code, 400)

    def test_log_into_subdomain_when_token_not_found(self) -> None:
        data: ExternalAuthDataDict = {
            'full_name': 'Full Name',
            'email': self.example_email("hamlet"),
            'subdomain': 'zulip',
            'is_signup': False,
            'redirect_to': '',
        }
        with mock.patch("logging.warning") as mock_warn:
            token = generate_random_token(ExternalAuthResult.LOGIN_TOKEN_LENGTH)
            result = self.get_log_into_subdomain(data, force_token=token)
            mock_warn.assert_called_once_with("log_into_subdomain: Invalid token given: %s", token)
        self.assertEqual(result.status_code, 400)
        self.assert_in_response("Invalid or expired login session.", result)

    def test_prevent_duplicate_signups(self) -> None:
        existing_user = self.example_user('hamlet')
        existing_user.delivery_email = 'existing@zulip.com'
        existing_user.email = 'whatever@zulip.com'
        existing_user.save()

        data: ExternalAuthDataDict = {
            'full_name': 'Full Name',
            'email': 'existing@zulip.com',
            'subdomain': 'zulip',
            'is_signup': True,
            'redirect_to': '',
        }
        result = self.get_log_into_subdomain(data)

        # Should simply get logged into the existing account:
        self.assertEqual(result.status_code, 302)
        self.assert_logged_in_user_id(existing_user.id)

    def test_log_into_subdomain_when_is_signup_is_true_and_new_user(self) -> None:
        data: ExternalAuthDataDict = {
            'full_name': 'New User Name',
            'email': 'new@zulip.com',
            'subdomain': 'zulip',
            'is_signup': True,
            'redirect_to': '',
        }
        result = self.get_log_into_subdomain(data)
        self.assertEqual(result.status_code, 302)
        confirmation = Confirmation.objects.all().first()
        confirmation_key = confirmation.confirmation_key
        self.assertIn('do_confirm/' + confirmation_key, result.url)
        result = self.client_get(result.url)
        self.assert_in_response('action="/accounts/register/"', result)
        confirmation_data = {"from_confirmation": "1",
                             "full_name": data['full_name'],
                             "key": confirmation_key}
        result = self.client_post('/accounts/register/', confirmation_data, subdomain="zulip")
        self.assert_in_response("We just need you to do one last thing", result)

        # Verify that the user is asked for name but not password
        self.assert_not_in_success_response(['id_password'], result)
        self.assert_in_success_response(['id_full_name'], result)

    def test_log_into_subdomain_when_is_signup_is_false_and_new_user(self) -> None:
        data: ExternalAuthDataDict = {
            'full_name': 'New User Name',
            'email': 'new@zulip.com',
            'subdomain': 'zulip',
            'is_signup': False,
            'redirect_to': '',
        }
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
        confirmation_data = {"from_confirmation": "1",
                             "full_name": data['full_name'],
                             "key": confirmation_key}
        result = self.client_post('/accounts/register/', confirmation_data, subdomain="zulip")
        self.assert_in_response("We just need you to do one last thing", result)

        # Verify that the user is asked for name but not password
        self.assert_not_in_success_response(['id_password'], result)
        self.assert_in_success_response(['id_full_name'], result)

    def test_log_into_subdomain_when_using_invite_link(self) -> None:
        data: ExternalAuthDataDict = {
            'full_name': 'New User Name',
            'email': 'new@zulip.com',
            'subdomain': 'zulip',
            'is_signup': True,
            'redirect_to': '',
        }

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
        create_confirmation_link(multiuse_obj, Confirmation.MULTIUSE_INVITE)
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
                 "full_name": data['full_name'],
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
        new_user = get_user_by_delivery_email('new@zulip.com', realm)
        new_streams = self.get_streams(new_user)
        self.assertEqual(sorted(new_streams), stream_names)

    def test_log_into_subdomain_when_email_is_none(self) -> None:
        data: ExternalAuthDataDict = {
            'subdomain': 'zulip',
            'is_signup': False,
            'redirect_to': '',
        }

        with mock.patch('logging.warning') as mock_warn:
            result = self.get_log_into_subdomain(data)
            self.assertEqual(result.status_code, 400)
            mock_warn.assert_called_once()

    def test_user_cannot_log_into_wrong_subdomain(self) -> None:
        data: ExternalAuthDataDict = {
            'full_name': 'Full Name',
            'email': self.example_email("hamlet"),
            'subdomain': 'zephyr',
        }
        result = self.get_log_into_subdomain(data)
        self.assert_json_error(result, "Invalid subdomain")

class JSONFetchAPIKeyTest(ZulipTestCase):
    def test_success(self) -> None:
        user = self.example_user('hamlet')
        self.login_user(user)
        result = self.client_post("/json/fetch_api_key",
                                  dict(user_profile=user,
                                       password=initial_password(user.delivery_email)))
        self.assert_json_success(result)

    def test_not_loggedin(self) -> None:
        user = self.example_user('hamlet')
        result = self.client_post("/json/fetch_api_key",
                                  dict(user_profile=user,
                                       password=initial_password(user.delivery_email)))
        self.assert_json_error(result,
                               "Not logged in: API authentication or user session required", 401)

    def test_wrong_password(self) -> None:
        user = self.example_user('hamlet')
        self.login_user(user)
        result = self.client_post("/json/fetch_api_key",
                                  dict(user_profile=user,
                                       password="wrong"))
        self.assert_json_error(result, "Your username or password is incorrect.", 400)

class FetchAPIKeyTest(ZulipTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.user_profile = self.example_user('hamlet')
        self.email = self.user_profile.delivery_email

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
                                           password=self.ldap_password('hamlet')))
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
        self.email = self.user_profile.delivery_email

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
            self.assert_json_error_contains(result, "DevAuthBackend not enabled.", 400)

class DevGetEmailsTest(ZulipTestCase):
    def test_success(self) -> None:
        result = self.client_get("/api/v1/dev_list_users")
        self.assert_json_success(result)
        self.assert_in_response("direct_admins", result)
        self.assert_in_response("direct_users", result)

    def test_dev_auth_disabled(self) -> None:
        with mock.patch('zerver.views.auth.dev_auth_enabled', return_value=False):
            result = self.client_get("/api/v1/dev_list_users")
            self.assert_json_error_contains(result, "DevAuthBackend not enabled.", 400)

        with override_settings(PRODUCTION=True):
            result = self.client_get("/api/v1/dev_list_users")
            self.assert_json_error_contains(result, "Endpoint not available in production.", 400)

class ExternalMethodDictsTests(ZulipTestCase):
    def get_configured_saml_backend_idp_names(self) -> List[str]:
        return settings.SOCIAL_AUTH_SAML_ENABLED_IDPS.keys()

    def test_get_external_method_dicts_correctly_sorted(self) -> None:
        with self.settings(
            AUTHENTICATION_BACKENDS=('zproject.backends.EmailAuthBackend',
                                     'zproject.backends.GitHubAuthBackend',
                                     'zproject.backends.GoogleAuthBackend',
                                     'zproject.backends.ZulipRemoteUserBackend',
                                     'zproject.backends.SAMLAuthBackend',
                                     'zproject.backends.AzureADAuthBackend'),
        ):
            external_auth_methods = get_external_method_dicts()
            # First backends in the list should be SAML:
            self.assertIn('saml:', external_auth_methods[0]['name'])
            self.assertEqual(
                [social_backend['name'] for social_backend in external_auth_methods[1:]],
                [social_backend.name for social_backend in sorted(
                    [ZulipRemoteUserBackend, GitHubAuthBackend, AzureADAuthBackend, GoogleAuthBackend],
                    key=lambda x: x.sort_order,
                    reverse=True,
                )],
            )

    def test_get_external_method_buttons(self) -> None:
        with self.settings(
            AUTHENTICATION_BACKENDS=('zproject.backends.EmailAuthBackend',
                                     'zproject.backends.GitHubAuthBackend',
                                     'zproject.backends.GoogleAuthBackend',
                                     'zproject.backends.SAMLAuthBackend'),
        ):
            saml_idp_names = self.get_configured_saml_backend_idp_names()
            expected_button_id_strings = [
                'id="{}_auth_button_github"',
                'id="{}_auth_button_google"',
            ]
            for name in saml_idp_names:
                expected_button_id_strings.append(f'id="{{}}_auth_button_saml:{name}"')

            result = self.client_get("/login/")
            self.assert_in_success_response([string.format("login") for string in expected_button_id_strings],
                                            result)

            result = self.client_get("/register/")
            self.assert_in_success_response([string.format("register") for string in expected_button_id_strings],
                                            result)

    def test_get_external_method_dicts_multiple_saml_idps(self) -> None:
        idps_dict = copy.deepcopy(settings.SOCIAL_AUTH_SAML_ENABLED_IDPS)
        # Create another IdP config, by copying the original one and changing some details.idps_dict['test_idp'])
        idps_dict['test_idp2'] = copy.deepcopy(idps_dict['test_idp'])
        idps_dict['test_idp2']['url'] = 'https://idp2.example.com/idp/profile/SAML2/Redirect/SSO'
        idps_dict['test_idp2']['display_name'] = 'Second Test IdP'
        idps_dict['test_idp2']['limit_to_subdomains'] = ['zephyr']
        with self.settings(
            SOCIAL_AUTH_SAML_ENABLED_IDPS=idps_dict,
            AUTHENTICATION_BACKENDS=('zproject.backends.EmailAuthBackend',
                                     'zproject.backends.GitHubAuthBackend',
                                     'zproject.backends.SAMLAuthBackend'),
        ):
            # Calling get_external_method_dicts without a realm returns all methods configured on the server:
            external_auth_methods = get_external_method_dicts()
            # 1 IdP enabled for all realms + a dict for github auth
            self.assert_length(external_auth_methods, 2)
            self.assertEqual([external_auth_methods[0]['name'], external_auth_methods[1]['name']],
                             ['saml:test_idp', 'github'])

            external_auth_methods = get_external_method_dicts(get_realm("zulip"))
            # Only test_idp enabled for the zulip realm, + github auth.
            self.assert_length(external_auth_methods, 2)
            self.assertEqual([external_auth_methods[0]['name'], external_auth_methods[1]['name']],
                             ['saml:test_idp', 'github'])

            external_auth_methods = get_external_method_dicts(get_realm("zephyr"))
            # Both idps enabled for the zephyr realm, + github auth.
            self.assert_length(external_auth_methods, 3)
            self.assertEqual({external_auth_methods[0]['name'], external_auth_methods[1]['name']},
                             {'saml:test_idp', 'saml:test_idp2'})

class FetchAuthBackends(ZulipTestCase):
    def test_get_server_settings(self) -> None:
        def check_result(result: HttpResponse, extra_fields: Sequence[Tuple[str, Validator[object]]] = []) -> None:
            authentication_methods_list = [
                ('password', check_bool),
            ]
            for backend_name_with_case in AUTH_BACKEND_NAME_MAP:
                authentication_methods_list.append((backend_name_with_case.lower(), check_bool))
            external_auth_methods = get_external_method_dicts()

            self.assert_json_success(result)
            checker = check_dict_only([
                ('authentication_methods', check_dict_only(authentication_methods_list)),
                ('external_authentication_methods', check_list(
                    check_dict_only([
                        ('display_icon', check_none_or(check_string)),
                        ('display_name', check_string),
                        ('login_url', check_string),
                        ('name', check_string),
                        ('signup_url', check_string),
                    ]),
                    length=len(external_auth_methods)
                )),
                ('email_auth_enabled', check_bool),
                ('is_incompatible', check_bool),
                ('require_email_format_usernames', check_bool),
                ('realm_uri', check_string),
                ('zulip_version', check_string),
                ('zulip_feature_level', check_int),
                ('push_notifications_enabled', check_bool),
                ('msg', check_string),
                ('result', check_string),
                *extra_fields,
            ])
            checker("data", result.json())

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
    def test_two_factor_login_with_ldap(self, mock_totp: mock.MagicMock) -> None:
        token = 123456
        email = self.example_email('hamlet')
        password = self.ldap_password('hamlet')

        user_profile = self.example_user('hamlet')
        user_profile.set_password(password)
        user_profile.save()
        self.create_default_device(user_profile)

        def totp(*args: Any, **kwargs: Any) -> int:
            return token

        mock_totp.side_effect = totp

        # Setup LDAP
        self.init_default_ldap_database()
        ldap_user_attr_map = {'full_name': 'cn'}
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
            with self.assertLogs('two_factor.gateways.fake', 'INFO') as info_log:
                result = self.client_post("/accounts/login/", first_step_data)
            self.assertEqual(result.status_code, 200)
            self.assertEqual(info_log.output, [
                'INFO:two_factor.gateways.fake:Fake SMS to +12125550100: "Your token is: 123456"'
            ])

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
        email = user_profile.delivery_email
        data = {'direct_email': email}
        result = self.client_post('/accounts/login/local/', data)
        self.assertEqual(result.status_code, 302)
        self.assert_logged_in_user_id(user_profile.id)

    def test_login_success_with_2fa(self) -> None:
        user_profile = self.example_user('hamlet')
        self.create_default_device(user_profile)
        email = user_profile.delivery_email
        data = {'direct_email': email}
        with self.settings(TWO_FACTOR_AUTHENTICATION_ENABLED=True):
            result = self.client_post('/accounts/login/local/', data)
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result.url, 'http://zulip.testserver/')
        self.assert_logged_in_user_id(user_profile.id)
        self.assertIn('otp_device_id', list(self.client.session.keys()))

    def test_redirect_to_next_url(self) -> None:
        def do_local_login(formaction: str) -> HttpResponse:
            user_email = self.example_email('hamlet')
            data = {'direct_email': user_email}
            return self.client_post(formaction, data)

        res = do_local_login('/accounts/login/local/')
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, 'http://zulip.testserver/')

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
        email = user_profile.delivery_email
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
            response = self.client_post('/accounts/login/local/', data)
            self.assertRedirects(response, reverse('config_error', kwargs={'error_category_name': 'dev'}))

    def test_dev_direct_production_config_error(self) -> None:
        result = self.client_get("/config-error/dev")
        self.assertEqual(result.status_code, 200)
        self.assert_in_success_response(["DevAuthBackend"], result)

    def test_login_failure_due_to_nonexistent_user(self) -> None:
        email = 'nonexisting@zulip.com'
        data = {'direct_email': email}

        response = self.client_post('/accounts/login/local/', data)
        self.assertRedirects(response, reverse('config_error', kwargs={'error_category_name': 'dev'}))

class TestZulipRemoteUserBackend(DesktopFlowTestingLib, ZulipTestCase):
    def test_start_remote_user_sso(self) -> None:
        result = self.client_get('/accounts/login/start/sso/?param1=value1&params=value2')
        self.assertEqual(result.status_code, 302)

        url = result.url
        parsed_url = urllib.parse.urlparse(url)
        self.assertEqual(parsed_url.path, '/accounts/login/sso/')
        self.assertEqual(parsed_url.query, 'param1=value1&params=value2')

    def test_start_remote_user_sso_with_desktop_app(self) -> None:
        headers = dict(HTTP_USER_AGENT="ZulipElectron/5.0.0")
        result = self.client_get('/accounts/login/start/sso/', **headers)
        self.verify_desktop_flow_app_page(result)

    def test_login_success(self) -> None:
        user_profile = self.example_user('hamlet')
        email = user_profile.delivery_email
        with self.settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipRemoteUserBackend',)):
            result = self.client_get('/accounts/login/sso/', REMOTE_USER=email)
            self.assertEqual(result.status_code, 302)
            self.assert_logged_in_user_id(user_profile.id)

    def test_login_success_with_sso_append_domain(self) -> None:
        username = 'hamlet'
        user_profile = self.example_user('hamlet')
        with self.settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipRemoteUserBackend',),
                           SSO_APPEND_DOMAIN='zulip.com'):
            result = self.client_get('/accounts/login/sso/', REMOTE_USER=username)
            self.assertEqual(result.status_code, 302)
            self.assert_logged_in_user_id(user_profile.id)

    def test_login_case_insensitive(self) -> None:
        user_profile = self.example_user('hamlet')
        email_upper = user_profile.delivery_email.upper()
        with self.settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipRemoteUserBackend',)):
            result = self.client_get('/accounts/login/sso/', REMOTE_USER=email_upper)
            self.assertEqual(result.status_code, 302)
            self.assert_logged_in_user_id(user_profile.id)

    def test_login_failure(self) -> None:
        email = self.example_email("hamlet")
        result = self.client_get('/accounts/login/sso/', REMOTE_USER=email)
        self.assertEqual(result.status_code, 302)

        result = self.client_get(result["Location"])
        self.assert_in_response("Authentication via the REMOTE_USER header is", result)
        self.assert_logged_in_user_id(None)

    def test_login_failure_due_to_nonexisting_user(self) -> None:
        email = 'nonexisting@zulip.com'
        with self.settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipRemoteUserBackend',)):
            result = self.client_get('/accounts/login/sso/', REMOTE_USER=email)
            self.assertEqual(result.status_code, 200)
            self.assert_logged_in_user_id(None)
            self.assert_in_response("No account found for", result)

    def test_login_failure_due_to_invalid_email(self) -> None:
        email = 'hamlet'
        with self.settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipRemoteUserBackend',)):
            result = self.client_get('/accounts/login/sso/', REMOTE_USER=email)
            self.assert_json_error_contains(result, "Enter a valid email address.", 400)

    def test_login_failure_due_to_missing_field(self) -> None:
        with self.settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipRemoteUserBackend',)):
            result = self.client_get('/accounts/login/sso/')
            self.assertEqual(result.status_code, 302)

            result = self.client_get(result["Location"])
            self.assert_in_response("The REMOTE_USER header is not set.", result)

    def test_login_failure_due_to_wrong_subdomain(self) -> None:
        email = self.example_email("hamlet")
        with self.settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipRemoteUserBackend',)):
            with mock.patch('zerver.views.auth.get_subdomain', return_value='acme'):
                result = self.client_get('http://testserver:9080/accounts/login/sso/',
                                         REMOTE_USER=email)
                self.assertEqual(result.status_code, 200)
                self.assert_logged_in_user_id(None)
                self.assert_in_response("You need an invitation to join this organization.", result)

    def test_login_failure_due_to_empty_subdomain(self) -> None:
        email = self.example_email("hamlet")
        with self.settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipRemoteUserBackend',)):
            with mock.patch('zerver.views.auth.get_subdomain', return_value=''):
                result = self.client_get('http://testserver:9080/accounts/login/sso/',
                                         REMOTE_USER=email)
                self.assertEqual(result.status_code, 200)
                self.assert_logged_in_user_id(None)
                self.assert_in_response("You need an invitation to join this organization.", result)

    def test_login_success_under_subdomains(self) -> None:
        user_profile = self.example_user('hamlet')
        email = user_profile.delivery_email
        with mock.patch('zerver.views.auth.get_subdomain', return_value='zulip'):
            with self.settings(
                    AUTHENTICATION_BACKENDS=('zproject.backends.ZulipRemoteUserBackend',)):
                result = self.client_get('/accounts/login/sso/', REMOTE_USER=email)
                self.assertEqual(result.status_code, 302)
                self.assert_logged_in_user_id(user_profile.id)

    @override_settings(SEND_LOGIN_EMAILS=True)
    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipRemoteUserBackend',))
    def test_login_mobile_flow_otp_success_email(self) -> None:
        user_profile = self.example_user('hamlet')
        email = user_profile.delivery_email
        user_profile.date_joined = timezone_now() - datetime.timedelta(seconds=61)
        user_profile.save()
        mobile_flow_otp = '1234abcd' * 8

        # Verify that the right thing happens with an invalid-format OTP
        result = self.client_get('/accounts/login/sso/',
                                 dict(mobile_flow_otp="1234"),
                                 REMOTE_USER=email,
                                 HTTP_USER_AGENT = "ZulipAndroid")
        self.assert_logged_in_user_id(None)
        self.assert_json_error_contains(result, "Invalid OTP", 400)

        result = self.client_get('/accounts/login/sso/',
                                 dict(mobile_flow_otp="invalido" * 8),
                                 REMOTE_USER=email,
                                 HTTP_USER_AGENT = "ZulipAndroid")
        self.assert_logged_in_user_id(None)
        self.assert_json_error_contains(result, "Invalid OTP", 400)

        result = self.client_get('/accounts/login/sso/',
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
        email = user_profile.delivery_email
        remote_user = email_to_username(email)
        user_profile.date_joined = timezone_now() - datetime.timedelta(seconds=61)
        user_profile.save()
        mobile_flow_otp = '1234abcd' * 8

        # Verify that the right thing happens with an invalid-format OTP
        result = self.client_get('/accounts/login/sso/',
                                 dict(mobile_flow_otp="1234"),
                                 REMOTE_USER=remote_user,
                                 HTTP_USER_AGENT = "ZulipAndroid")
        self.assert_logged_in_user_id(None)
        self.assert_json_error_contains(result, "Invalid OTP", 400)

        result = self.client_get('/accounts/login/sso/',
                                 dict(mobile_flow_otp="invalido" * 8),
                                 REMOTE_USER=remote_user,
                                 HTTP_USER_AGENT = "ZulipAndroid")
        self.assert_logged_in_user_id(None)
        self.assert_json_error_contains(result, "Invalid OTP", 400)

        result = self.client_get('/accounts/login/sso/',
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

    @override_settings(SEND_LOGIN_EMAILS=True)
    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipRemoteUserBackend',
                                                'zproject.backends.ZulipDummyBackend'))
    def test_login_desktop_flow_otp_success_email(self) -> None:
        user_profile = self.example_user('hamlet')
        email = user_profile.delivery_email
        user_profile.date_joined = timezone_now() - datetime.timedelta(seconds=61)
        user_profile.save()
        desktop_flow_otp = '1234abcd' * 8

        # Verify that the right thing happens with an invalid-format OTP
        result = self.client_get('/accounts/login/sso/',
                                 dict(desktop_flow_otp="1234"),
                                 REMOTE_USER=email)
        self.assert_logged_in_user_id(None)
        self.assert_json_error_contains(result, "Invalid OTP", 400)

        result = self.client_get('/accounts/login/sso/',
                                 dict(desktop_flow_otp="invalido" * 8),
                                 REMOTE_USER=email)
        self.assert_logged_in_user_id(None)
        self.assert_json_error_contains(result, "Invalid OTP", 400)

        result = self.client_get('/accounts/login/sso/',
                                 dict(desktop_flow_otp=desktop_flow_otp),
                                 REMOTE_USER=email)
        self.verify_desktop_flow_end_page(result, email, desktop_flow_otp)

    @override_settings(SEND_LOGIN_EMAILS=True)
    @override_settings(SSO_APPEND_DOMAIN="zulip.com")
    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipRemoteUserBackend',
                                                'zproject.backends.ZulipDummyBackend'))
    def test_login_desktop_flow_otp_success_username(self) -> None:
        user_profile = self.example_user('hamlet')
        email = user_profile.delivery_email
        remote_user = email_to_username(email)
        user_profile.date_joined = timezone_now() - datetime.timedelta(seconds=61)
        user_profile.save()
        desktop_flow_otp = '1234abcd' * 8

        # Verify that the right thing happens with an invalid-format OTP
        result = self.client_get('/accounts/login/sso/',
                                 dict(desktop_flow_otp="1234"),
                                 REMOTE_USER=remote_user)
        self.assert_logged_in_user_id(None)
        self.assert_json_error_contains(result, "Invalid OTP", 400)

        result = self.client_get('/accounts/login/sso/',
                                 dict(desktop_flow_otp="invalido" * 8),
                                 REMOTE_USER=remote_user)
        self.assert_logged_in_user_id(None)
        self.assert_json_error_contains(result, "Invalid OTP", 400)

        result = self.client_get('/accounts/login/sso/',
                                 dict(desktop_flow_otp=desktop_flow_otp),
                                 REMOTE_USER=remote_user)
        self.verify_desktop_flow_end_page(result, email, desktop_flow_otp)

    def test_redirect_to(self) -> None:
        """This test verifies the behavior of the redirect_to logic in
        login_or_register_remote_user."""
        def test_with_redirect_to_param_set_as_next(next: str='') -> HttpResponse:
            user_profile = self.example_user('hamlet')
            email = user_profile.delivery_email
            with self.settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipRemoteUserBackend',)):
                result = self.client_get('/accounts/login/sso/?next=' + next, REMOTE_USER=email)
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
        with self.settings(JWT_AUTH_KEYS={'zulip': {'key': 'key', 'algorithms': ['HS256']}}):
            email = self.example_email("hamlet")
            realm = get_realm('zulip')
            key = settings.JWT_AUTH_KEYS['zulip']['key']
            [algorithm] = settings.JWT_AUTH_KEYS['zulip']['algorithms']
            web_token = jwt.encode(payload, key, algorithm).decode('utf8')

            user_profile = get_user_by_delivery_email(email, realm)
            data = {'json_web_token': web_token}
            result = self.client_post('/accounts/login/jwt/', data)
            self.assertEqual(result.status_code, 302)
            self.assert_logged_in_user_id(user_profile.id)

    def test_login_failure_when_user_is_missing(self) -> None:
        payload = {'realm': 'zulip.com'}
        with self.settings(JWT_AUTH_KEYS={'zulip': {'key': 'key', 'algorithms': ['HS256']}}):
            key = settings.JWT_AUTH_KEYS['zulip']['key']
            [algorithm] = settings.JWT_AUTH_KEYS['zulip']['algorithms']
            web_token = jwt.encode(payload, key, algorithm).decode('utf8')
            data = {'json_web_token': web_token}
            result = self.client_post('/accounts/login/jwt/', data)
            self.assert_json_error_contains(result, "No user specified in JSON web token claims", 400)

    def test_login_failure_when_realm_is_missing(self) -> None:
        payload = {'user': 'hamlet'}
        with self.settings(JWT_AUTH_KEYS={'zulip': {'key': 'key', 'algorithms': ['HS256']}}):
            key = settings.JWT_AUTH_KEYS['zulip']['key']
            [algorithm] = settings.JWT_AUTH_KEYS['zulip']['algorithms']
            web_token = jwt.encode(payload, key, algorithm).decode('utf8')
            data = {'json_web_token': web_token}
            result = self.client_post('/accounts/login/jwt/', data)
            self.assert_json_error_contains(result, "No organization specified in JSON web token claims", 400)

    def test_login_failure_when_key_does_not_exist(self) -> None:
        data = {'json_web_token': 'not relevant'}
        result = self.client_post('/accounts/login/jwt/', data)
        self.assert_json_error_contains(result, "Auth key for this subdomain not found.", 400)

    def test_login_failure_when_key_is_missing(self) -> None:
        with self.settings(JWT_AUTH_KEYS={'zulip': {'key': 'key', 'algorithms': ['HS256']}}):
            result = self.client_post('/accounts/login/jwt/')
            self.assert_json_error_contains(result, "No JSON web token passed in request", 400)

    def test_login_failure_when_bad_token_is_passed(self) -> None:
        with self.settings(JWT_AUTH_KEYS={'zulip': {'key': 'key', 'algorithms': ['HS256']}}):
            result = self.client_post('/accounts/login/jwt/')
            self.assert_json_error_contains(result, "No JSON web token passed in request", 400)
            data = {'json_web_token': 'bad token'}
            result = self.client_post('/accounts/login/jwt/', data)
            self.assert_json_error_contains(result, "Bad JSON web token", 400)

    def test_login_failure_when_user_does_not_exist(self) -> None:
        payload = {'user': 'nonexisting', 'realm': 'zulip.com'}
        with self.settings(JWT_AUTH_KEYS={'zulip': {'key': 'key', 'algorithms': ['HS256']}}):
            key = settings.JWT_AUTH_KEYS['zulip']['key']
            [algorithm] = settings.JWT_AUTH_KEYS['zulip']['algorithms']
            web_token = jwt.encode(payload, key, algorithm).decode('utf8')
            data = {'json_web_token': web_token}
            result = self.client_post('/accounts/login/jwt/', data)
            self.assertEqual(result.status_code, 200)  # This should ideally be not 200.
            self.assert_logged_in_user_id(None)

    def test_login_failure_due_to_wrong_subdomain(self) -> None:
        payload = {'user': 'hamlet', 'realm': 'zulip.com'}
        with self.settings(JWT_AUTH_KEYS={'acme': {'key': 'key', 'algorithms': ['HS256']}}):
            with mock.patch('zerver.views.auth.get_subdomain', return_value='acme'), \
                    mock.patch('logging.warning'):
                key = settings.JWT_AUTH_KEYS['acme']['key']
                [algorithm] = settings.JWT_AUTH_KEYS['acme']['algorithms']
                web_token = jwt.encode(payload, key, algorithm).decode('utf8')

                data = {'json_web_token': web_token}
                result = self.client_post('/accounts/login/jwt/', data)
                self.assert_json_error_contains(result, "Wrong subdomain", 400)
                self.assert_logged_in_user_id(None)

    def test_login_failure_due_to_empty_subdomain(self) -> None:
        payload = {'user': 'hamlet', 'realm': 'zulip.com'}
        with self.settings(JWT_AUTH_KEYS={'': {'key': 'key', 'algorithms': ['HS256']}}):
            with mock.patch('zerver.views.auth.get_subdomain', return_value=''), \
                    mock.patch('logging.warning'):
                key = settings.JWT_AUTH_KEYS['']['key']
                [algorithm] = settings.JWT_AUTH_KEYS['']['algorithms']
                web_token = jwt.encode(payload, key, algorithm).decode('utf8')

                data = {'json_web_token': web_token}
                result = self.client_post('/accounts/login/jwt/', data)
                self.assert_json_error_contains(result, "Wrong subdomain", 400)
                self.assert_logged_in_user_id(None)

    def test_login_success_under_subdomains(self) -> None:
        payload = {'user': 'hamlet', 'realm': 'zulip.com'}
        with self.settings(JWT_AUTH_KEYS={'zulip': {'key': 'key', 'algorithms': ['HS256']}}):
            with mock.patch('zerver.views.auth.get_subdomain', return_value='zulip'):
                key = settings.JWT_AUTH_KEYS['zulip']['key']
                [algorithm] = settings.JWT_AUTH_KEYS['zulip']['algorithms']
                web_token = jwt.encode(payload, key, algorithm).decode('utf8')

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
            mock_warn.assert_called_with("Multiple users with email %s found in LDAP.", "shared_email@zulip.com")

        # Test on a weird case of a user whose uid is an email and his actual "mail"
        # attribute is a different email address:
        self.mock_ldap.directory['uid=some_user@organization_a.com,ou=users,dc=zulip,dc=com'] = {
            "cn": ["Some User"],
            "uid": ['some_user@organization_a.com'],
            "mail": ["some_user@contactaddress.com"],
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
                                                'zproject.backends.ZulipLDAPAuthBackend'))
    def test_authenticate_to_ldap_via_email(self) -> None:
        """
        With AUTH_LDAP_REVERSE_EMAIL_SEARCH configured, django_to_ldap_username
        should be able to translate an email to ldap username,
        and thus it should be possible to authenticate through user_profile.delivery_email.
        """
        realm = get_realm("zulip")
        user_profile = self.example_user("hamlet")
        password = "testpassword"
        user_profile.set_password(password)
        user_profile.save()

        with self.settings(LDAP_EMAIL_ATTR='mail'):
            self.assertEqual(
                authenticate(request=mock.MagicMock(), username=user_profile.delivery_email,
                             password=self.ldap_password('hamlet'), realm=realm),
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
            LDAP_APPEND_DOMAIN='zulip.com',
        ):
            user_profile = self.backend.authenticate(request=mock.MagicMock(),
                                                     username='ldapuser1', password='dapu',
                                                     realm=get_realm('zulip'))

            assert(user_profile is None)

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_login_success(self) -> None:
        with self.settings(LDAP_APPEND_DOMAIN='zulip.com'):
            user_profile = self.backend.authenticate(request=mock.MagicMock(),
                                                     username=self.example_email("hamlet"),
                                                     password=self.ldap_password('hamlet'),
                                                     realm=get_realm('zulip'))

            assert(user_profile is not None)
            self.assertEqual(user_profile.delivery_email, self.example_email("hamlet"))

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_login_success_with_username(self) -> None:
        with self.settings(LDAP_APPEND_DOMAIN='zulip.com'):
            user_profile = self.backend.authenticate(request=mock.MagicMock(),
                                                     username="hamlet", password=self.ldap_password('hamlet'),
                                                     realm=get_realm('zulip'))

            assert(user_profile is not None)
            self.assertEqual(user_profile, self.example_user("hamlet"))

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_login_success_with_email_attr(self) -> None:
        with self.settings(LDAP_EMAIL_ATTR='mail'):
            username = self.ldap_username("aaron")
            user_profile = self.backend.authenticate(request=mock.MagicMock(),
                                                     username=username,
                                                     password=self.ldap_password(username),
                                                     realm=get_realm('zulip'))

            assert (user_profile is not None)
            self.assertEqual(user_profile, self.example_user("aaron"))

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.EmailAuthBackend',
                                                'zproject.backends.ZulipLDAPAuthBackend'))
    def test_email_and_ldap_backends_together(self) -> None:
        with self.settings(
            LDAP_EMAIL_ATTR='mail',
            AUTH_LDAP_REVERSE_EMAIL_SEARCH = LDAPSearch("ou=users,dc=zulip,dc=com",
                                                        ldap.SCOPE_ONELEVEL,
                                                        "(mail=%(email)s)"),
            AUTH_LDAP_USERNAME_ATTR = "uid",
        ):
            realm = get_realm('zulip')
            self.assertEqual(email_belongs_to_ldap(realm, self.example_email("aaron")), True)
            username = self.ldap_username("aaron")
            user_profile = ZulipLDAPAuthBackend().authenticate(request=mock.MagicMock(),
                                                               username=username,
                                                               password=self.ldap_password(username),
                                                               realm=realm)
            self.assertEqual(user_profile, self.example_user("aaron"))

            othello = self.example_user('othello')
            password = "testpassword"
            othello.set_password(password)
            othello.save()

            self.assertEqual(email_belongs_to_ldap(realm, othello.delivery_email), False)
            user_profile = EmailAuthBackend().authenticate(request=mock.MagicMock(),
                                                           username=othello.delivery_email,
                                                           password=password,
                                                           realm=realm)
            self.assertEqual(user_profile, othello)

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_login_failure_due_to_wrong_password(self) -> None:
        with self.settings(LDAP_APPEND_DOMAIN='zulip.com'):
            user = self.backend.authenticate(request=mock.MagicMock(),
                                             username=self.example_email("hamlet"), password='wrong',
                                             realm=get_realm('zulip'))
            self.assertIs(user, None)

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_login_failure_due_to_nonexistent_user(self) -> None:
        with self.settings(LDAP_APPEND_DOMAIN='zulip.com'), \
                self.assertLogs('zulip.ldap', level='DEBUG') as log_debug:
            user = self.backend.authenticate(request=mock.MagicMock(),
                                             username='nonexistent@zulip.com',
                                             password="doesnt_matter",
                                             realm=get_realm('zulip'))
            self.assertEqual(log_debug.output, [
                'DEBUG:zulip.ldap:ZulipLDAPAuthBackend: No ldap user matching django_to_ldap_username result: nonexistent. Input username: nonexistent@zulip.com'
            ])
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
        self.assertEqual(user_profile.delivery_email, email)

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_get_or_build_user_when_user_does_not_exist(self) -> None:
        class _LDAPUser:
            attrs = {'fn': ['Full Name']}

        ldap_user_attr_map = {'full_name': 'fn'}

        with self.settings(AUTH_LDAP_USER_ATTR_MAP=ldap_user_attr_map):
            backend = self.backend
            email = 'newuser@zulip.com'
            user_profile, created = backend.get_or_build_user(email, _LDAPUser())
            self.assertTrue(created)
            self.assertEqual(user_profile.delivery_email, email)
            self.assertEqual(user_profile.full_name, 'Full Name')

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_get_or_build_user_when_user_has_invalid_name(self) -> None:
        class _LDAPUser:
            attrs = {'fn': ['<invalid name>']}

        ldap_user_attr_map = {'full_name': 'fn'}

        with self.settings(AUTH_LDAP_USER_ATTR_MAP=ldap_user_attr_map):
            backend = self.backend
            email = 'nonexisting@zulip.com'
            with self.assertRaisesRegex(Exception, "Invalid characters in name!"):
                backend.get_or_build_user(email, _LDAPUser())

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_get_or_build_user_when_realm_is_deactivated(self) -> None:
        class _LDAPUser:
            attrs = {'fn': ['Full Name']}

        ldap_user_attr_map = {'full_name': 'fn'}

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
        with self.settings(LDAP_APPEND_DOMAIN='acme.com'), self.assertLogs('zulip.ldap', 'DEBUG') as debug_log:
            user_profile = self.backend.authenticate(request=mock.MagicMock(),
                                                     username=self.example_email("hamlet"),
                                                     password=self.ldap_password('hamlet'),
                                                     realm=get_realm('zulip'))
            self.assertIs(user_profile, None)
        self.assertEqual(debug_log.output, [
            'DEBUG:zulip.ldap:ZulipLDAPAuthBackend: Email hamlet@zulip.com does not match LDAP domain acme.com.'
        ])

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_login_success_with_different_subdomain(self) -> None:
        ldap_user_attr_map = {'full_name': 'cn'}

        Realm.objects.create(string_id='acme')
        with self.settings(
                LDAP_APPEND_DOMAIN='zulip.com',
                AUTH_LDAP_USER_ATTR_MAP=ldap_user_attr_map):
            user_profile = self.backend.authenticate(request=mock.MagicMock(),
                                                     username=self.example_email('hamlet'),
                                                     password=self.ldap_password('hamlet'),
                                                     realm=get_realm('acme'))
            self.assertEqual(user_profile.delivery_email, self.example_email('hamlet'))

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_login_success_with_valid_subdomain(self) -> None:
        with self.settings(LDAP_APPEND_DOMAIN='zulip.com'):
            user_profile = self.backend.authenticate(request=mock.MagicMock(),
                                                     username=self.example_email("hamlet"),
                                                     password=self.ldap_password('hamlet'),
                                                     realm=get_realm('zulip'))
            assert(user_profile is not None)
            self.assertEqual(user_profile.delivery_email, self.example_email("hamlet"))

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_login_failure_due_to_deactivated_user(self) -> None:
        user_profile = self.example_user("hamlet")
        do_deactivate_user(user_profile)
        with self.settings(LDAP_APPEND_DOMAIN='zulip.com'):
            user_profile = self.backend.authenticate(request=mock.MagicMock(),
                                                     username=self.example_email("hamlet"),
                                                     password=self.ldap_password('hamlet'),
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
            user_profile = self.backend.authenticate(request=mock.MagicMock(),
                                                     username='newuser@acme.com',
                                                     password=self.ldap_password("newuser"),
                                                     realm=get_realm('zulip'))
            assert(user_profile is not None)
            self.assertEqual(user_profile.delivery_email, 'newuser@acme.com')
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
            user_profile = self.backend.authenticate(request=mock.MagicMock(),
                                                     username='newuser_splitname@zulip.com',
                                                     password=self.ldap_password("newuser_splitname"),
                                                     realm=get_realm('zulip'))
            assert(user_profile is not None)
            self.assertEqual(user_profile.delivery_email, 'newuser_splitname@zulip.com')
            self.assertEqual(user_profile.full_name, 'First Last')
            self.assertEqual(user_profile.realm.string_id, 'zulip')

class TestZulipLDAPUserPopulator(ZulipLDAPTestCase):
    def test_authenticate(self) -> None:
        backend = ZulipLDAPUserPopulator()
        result = backend.authenticate(username=self.example_email("hamlet"),
                                      password=self.ldap_password("hamlet"),
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

        with self.assertRaises(ZulipLDAPException), \
                self.assertLogs('django_auth_ldap', 'WARNING') as warn_log:
            self.perform_ldap_sync(self.example_user('hamlet'))
        self.assertEqual(warn_log.output, ['WARNING:django_auth_ldap:Name too short! while authenticating hamlet'])

    def test_deactivate_user(self) -> None:
        self.change_ldap_user_attr('hamlet', 'userAccountControl', '2')

        with self.settings(AUTH_LDAP_USER_ATTR_MAP={'full_name': 'cn',
                                                    'userAccountControl': 'userAccountControl'}), \
                self.assertLogs('zulip.ldap') as info_logs:
            self.perform_ldap_sync(self.example_user('hamlet'))
        hamlet = self.example_user('hamlet')
        self.assertFalse(hamlet.is_active)
        self.assertEqual(info_logs.output, [
            'INFO:zulip.ldap:Deactivating user hamlet@zulip.com because they are disabled in LDAP.'
        ])

    @mock.patch("zproject.backends.ZulipLDAPAuthBackendBase.sync_full_name_from_ldap")
    def test_dont_sync_disabled_ldap_user(self, fake_sync: mock.MagicMock) -> None:
        self.change_ldap_user_attr('hamlet', 'userAccountControl', '2')

        with self.settings(AUTH_LDAP_USER_ATTR_MAP={'full_name': 'cn',
                                                    'userAccountControl': 'userAccountControl'}), \
                self.assertLogs('zulip.ldap') as info_logs:
            self.perform_ldap_sync(self.example_user('hamlet'))
            fake_sync.assert_not_called()
        self.assertEqual(info_logs.output, [
            'INFO:zulip.ldap:Deactivating user hamlet@zulip.com because they are disabled in LDAP.'
        ])

    def test_reactivate_user(self) -> None:
        do_deactivate_user(self.example_user('hamlet'))

        with self.settings(AUTH_LDAP_USER_ATTR_MAP={'full_name': 'cn',
                                                    'userAccountControl': 'userAccountControl'}), \
                self.assertLogs('zulip.ldap') as info_logs:
            self.perform_ldap_sync(self.example_user('hamlet'))
        hamlet = self.example_user('hamlet')
        self.assertTrue(hamlet.is_active)
        self.assertEqual(info_logs.output, [
            'INFO:zulip.ldap:Reactivating user hamlet@zulip.com because they are not disabled in LDAP.'
        ])

    def test_user_in_multiple_realms(self) -> None:
        test_realm = do_create_realm('test', 'test', False)
        hamlet = self.example_user('hamlet')
        email = hamlet.delivery_email
        hamlet2 = do_create_user(
            email,
            None,
            test_realm,
            hamlet.full_name,
        )

        self.change_ldap_user_attr('hamlet', 'cn', 'Second Hamlet')
        expected_call_args = [hamlet2, 'Second Hamlet', None]
        with self.settings(AUTH_LDAP_USER_ATTR_MAP={'full_name': 'cn'}):
            with mock.patch('zerver.lib.actions.do_change_full_name') as f:
                self.perform_ldap_sync(hamlet2)
                f.assert_called_once_with(*expected_call_args)

                # Get the updated model and make sure the full name is changed correctly:
                hamlet2 = get_user_by_delivery_email(email, test_realm)
                self.assertEqual(hamlet2.full_name, "Second Hamlet")
                # Now get the original hamlet and make he still has his name unchanged:
                hamlet = self.example_user('hamlet')
                self.assertEqual(hamlet.full_name, "King Hamlet")

    def test_user_not_found_in_ldap(self) -> None:
        with self.settings(
                LDAP_DEACTIVATE_NON_MATCHING_USERS=False,
                LDAP_APPEND_DOMAIN='zulip.com'):
            othello = self.example_user("othello")  # othello isn't in our test directory
            mock_logger = mock.MagicMock()
            result = sync_user_from_ldap(othello, mock_logger)
            mock_logger.warning.assert_called_once_with(
                "Did not find %s in LDAP.", othello.delivery_email)
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

        original_image_key = bucket.Object(original_image_path_id)
        medium_image_key = bucket.Object(medium_path_id)

        image_data = original_image_key.get()['Body'].read()
        self.assertEqual(image_data, test_image_data)

        test_medium_image_data = resize_avatar(test_image_data, MEDIUM_AVATAR_SIZE)
        medium_image_data = medium_image_key.get()['Body'].read()
        self.assertEqual(medium_image_data, test_medium_image_data)

        # Try to use invalid data as the image:
        self.change_ldap_user_attr('hamlet', 'jpegPhoto', b'00' + test_image_data)
        with self.settings(AUTH_LDAP_USER_ATTR_MAP={'full_name': 'cn',
                                                    'avatar': 'jpegPhoto'}):
            with mock.patch('logging.warning') as mock_warning:
                self.perform_ldap_sync(self.example_user('hamlet'))
                mock_warning.assert_called_once_with(
                    'Could not parse %s field for user %s', 'jpegPhoto', hamlet.id,
                )

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
            with self.assertRaisesRegex(ZulipLDAPException, 'Custom profile field with name non_existent not found'), \
                    self.assertLogs('django_auth_ldap', 'WARNING') as warn_log:
                self.perform_ldap_sync(self.example_user('hamlet'))
            self.assertEqual(warn_log.output, [
                'WARNING:django_auth_ldap:Custom profile field with name non_existent not found. while authenticating hamlet'
            ])

    def test_update_custom_profile_field_invalid_data(self) -> None:
        self.change_ldap_user_attr('hamlet', 'birthDate', '9999')

        with self.settings(AUTH_LDAP_USER_ATTR_MAP={'full_name': 'cn',
                                                    'custom_profile_field__birthday': 'birthDate'}):
            with self.assertRaisesRegex(ZulipLDAPException, 'Invalid data for birthday field'), \
                    self.assertLogs('django_auth_ldap', 'WARNING') as warn_log:
                self.perform_ldap_sync(self.example_user('hamlet'))
            self.assertEqual(warn_log.output, [
                'WARNING:django_auth_ldap:Invalid data for birthday field: Birthday is not a date while authenticating hamlet'
            ])

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
                                                    'custom_profile_field__birthday': 'nonExistantAttr'}), self.assertLogs('django_auth_ldap', 'WARNING') as warn_log:
            self.perform_ldap_sync(self.example_user('hamlet'))

        actual_value = CustomProfileFieldValue.objects.get(user_profile=hamlet, field=no_op_field).value
        self.assertEqual(actual_value, expected_value)
        self.assertEqual(warn_log.output, [
            'WARNING:django_auth_ldap:uid=hamlet,ou=users,dc=zulip,dc=com does not have a value for the attribute nonExistantAttr'
        ])

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
                                                    'avatar': 'jpegPhoto',
                                                    'custom_profile_field__birthday': 'birthDate',
                                                    'custom_profile_field__phone_number': 'nonExistentAttr',
                                                    }):
            values = query_ldap(self.example_email('hamlet'))
        self.assertEqual(len(values), 4)
        self.assertIn('full_name: King Hamlet', values)
        self.assertIn('avatar: (An avatar image file)', values)
        self.assertIn('custom_profile_field__birthday: 1900-09-08', values)
        self.assertIn('custom_profile_field__phone_number: LDAP field not present', values)

    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_query_email_attr(self) -> None:
        with self.settings(AUTH_LDAP_USER_ATTR_MAP={'full_name': 'cn'},
                           LDAP_EMAIL_ATTR='mail'):
            # This will look up the user by email in our test dictionary,
            # should successfully find hamlet's ldap entry.
            values = query_ldap(self.example_email('hamlet'))
        self.assertEqual(len(values), 2)
        self.assertIn('full_name: King Hamlet', values)
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
        self.assert_in_response(f'value="{confirmation_key}" name="key"', result)

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
        self.login('iago')
        result = self.client_patch("/json/realm", {
            'authentication_methods': ujson.dumps({'Email': False, 'Dev': True})})
        self.assert_json_error(result, 'Must be an organization owner')

        self.login('desdemona')
        result = self.client_patch("/json/realm", {
            'authentication_methods': ujson.dumps({'Email': False, 'Dev': True})})
        self.assert_json_success(result)
        realm = get_realm('zulip')
        self.assertFalse(password_auth_enabled(realm))
        self.assertTrue(dev_auth_enabled(realm))

    def test_disable_all_backends(self) -> None:
        # Log in as admin
        self.login('desdemona')
        result = self.client_patch("/json/realm", {
            'authentication_methods': ujson.dumps({'Email': False, 'Dev': False})})
        self.assert_json_error(result, 'At least one authentication method must be enabled.')
        realm = get_realm('zulip')
        self.assertTrue(password_auth_enabled(realm))
        self.assertTrue(dev_auth_enabled(realm))

    def test_supported_backends_only_updated(self) -> None:
        # Log in as admin
        self.login('desdemona')
        # Set some supported and unsupported backends
        result = self.client_patch("/json/realm", {
            'authentication_methods': ujson.dumps({'Email': False, 'Dev': True, 'GitHub': False})})
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
            validate_login_email('hamlet')

    def test_validate_email(self) -> None:
        inviter = self.example_user('hamlet')
        cordelia = self.example_user('cordelia')

        realm = inviter.realm
        do_set_realm_property(realm, 'emails_restricted_to_domains', True)
        inviter.realm.refresh_from_db()
        error = validate_email_is_valid(
            'fred+5555@zulip.com',
            get_realm_email_validator(realm),
        )
        self.assertIn('containing + are not allowed', error)

        cordelia_email = cordelia.delivery_email
        errors = get_existing_user_errors(realm, {cordelia_email})
        error, is_deactivated = errors[cordelia_email]
        self.assertEqual(False, is_deactivated)
        self.assertEqual(error, 'Already has an account.')

        cordelia.is_active = False
        cordelia.save()

        errors = get_existing_user_errors(realm, {cordelia_email})
        error, is_deactivated = errors[cordelia_email]
        self.assertEqual(True, is_deactivated)
        self.assertEqual(error, 'Account has been deactivated.')

        errors = get_existing_user_errors(realm, {'fred-is-fine@zulip.com'})
        self.assertEqual(errors, {})

class LDAPBackendTest(ZulipTestCase):
    @override_settings(AUTHENTICATION_BACKENDS=('zproject.backends.ZulipLDAPAuthBackend',))
    def test_non_existing_realm(self) -> None:
        self.init_default_ldap_database()
        user = self.example_user('hamlet')

        data = dict(
            username=user.delivery_email,
            password=initial_password(user.delivery_email),
        )
        error_type = ZulipLDAPAuthBackend.REALM_IS_NONE_ERROR
        error = ZulipLDAPConfigurationError('Realm is None', error_type)
        with mock.patch('zproject.backends.ZulipLDAPAuthBackend.get_or_build_user',
                        side_effect=error), \
                mock.patch('django_auth_ldap.backend._LDAPUser._authenticate_user_dn'), \
                self.assertLogs('django_auth_ldap', 'WARNING') as warn_log:
            response = self.client_post('/login/', data)
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, reverse('config_error', kwargs={'error_category_name': 'ldap'}))
            response = self.client_get(response.url)
            self.assert_in_response('You are trying to login using LDAP '
                                    'without creating an',
                                    response)
        self.assertEqual(warn_log.output, [
            "WARNING:django_auth_ldap:('Realm is None', 1) while authenticating hamlet"
        ])
