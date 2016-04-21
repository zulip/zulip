# -*- coding: utf-8 -*-
from django.conf import settings
from django.test import TestCase
from django_auth_ldap.backend import _LDAPUser

import mock

from zerver.lib.actions import do_deactivate_realm, do_deactivate_user, \
    do_reactivate_realm, do_reactivate_user
from zerver.lib.test_helpers import (
    AuthedTestCase,
)
from zerver.models import \
    get_realm, get_user_profile_by_email, email_to_username

from zproject.backends import ZulipDummyBackend, EmailAuthBackend, \
    GoogleMobileOauth2Backend, ZulipRemoteUserBackend, ZulipLDAPAuthBackend, \
    ZulipLDAPUserPopulator, DevAuthBackend

import ujson

class AuthBackendTest(TestCase):
    def verify_backend(self, backend, good_args={},
                       good_kwargs={}, bad_kwargs=None,
                       email_to_username=None):
        email = "hamlet@zulip.com"
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
        self.verify_backend(ZulipDummyBackend(),
                            good_kwargs=dict(use_dummy_backend=True),
                            bad_kwargs=dict(use_dummy_backend=False))

    def test_email_auth_backend(self):
        email = "hamlet@zulip.com"
        user_profile = get_user_profile_by_email(email)
        password = "testpassword"
        user_profile.set_password(password)
        user_profile.save()
        self.verify_backend(EmailAuthBackend(),
                            bad_kwargs=dict(password=''),
                            good_kwargs=dict(password=password))

    def test_email_auth_backend_disabled_password_auth(self):
        email = "hamlet@zulip.com"
        user_profile = get_user_profile_by_email(email)
        password = "testpassword"
        user_profile.set_password(password)
        user_profile.save()
        # Verify if a realm has password auth disabled, correct password is rejected
        with mock.patch('zproject.backends.password_auth_enabled', return_value=False):
            self.assertIsNone(EmailAuthBackend().authenticate(email, dict(password=password)))

    def test_google_backend(self):
        email = "hamlet@zulip.com"
        user_profile = get_user_profile_by_email(email)
        backend = GoogleMobileOauth2Backend()
        payload = dict(email_verified=True,
                       email=email)
        with mock.patch('apiclient.sample_tools.client.verify_id_token', return_value=payload):
            self.verify_backend(backend)

        # Verify valid_attestation parameter is set correctly
        unverified_payload = dict(email_verified=False)
        with mock.patch('apiclient.sample_tools.client.verify_id_token', return_value=unverified_payload):
            ret = dict()
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
        email = "hamlet@zulip.com"
        user_profile = get_user_profile_by_email(email)
        password = "test_password"
        backend = ZulipLDAPAuthBackend()
        payload = dict(email_verified=True,
                       email=email)

        # Test LDAP auth fails when LDAP server rejects password
        with mock.patch('django_auth_ldap.backend._LDAPUser._authenticate_user_dn', \
                        side_effect=_LDAPUser.AuthenticationFailed("Failed")) as mock_auth_user_dn, \
             mock.patch('django_auth_ldap.backend._LDAPUser._check_requirements') as mock_check_requirements, \
             mock.patch('django_auth_ldap.backend._LDAPUser._get_user_attrs',
                        return_value=dict(full_name=['Hamlet'])) as mock_get_user_attrs:
            self.assertIsNone(backend.authenticate(email, password))

        # For this backend, we mock the internals of django_auth_ldap
        with mock.patch('django_auth_ldap.backend._LDAPUser._authenticate_user_dn') as mock_auth_user_dn, \
             mock.patch('django_auth_ldap.backend._LDAPUser._check_requirements') as mock_check_requirements, \
             mock.patch('django_auth_ldap.backend._LDAPUser._get_user_attrs',
                        return_value=dict(full_name=['Hamlet'])) as mock_get_user_attrs:
            self.verify_backend(backend, good_args=dict(password=password))

    def test_devauth_backend(self):
        self.verify_backend(DevAuthBackend())

    def test_remote_user_backend(self):
        self.verify_backend(ZulipRemoteUserBackend())

    def test_remote_user_backend_sso_append_domain(self):
        with self.settings(SSO_APPEND_DOMAIN='zulip.com'):
            self.verify_backend(ZulipRemoteUserBackend(),
                                email_to_username=email_to_username)
