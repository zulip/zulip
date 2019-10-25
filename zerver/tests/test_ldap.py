# -*- coding: utf-8 -*-
from django.contrib.auth import authenticate
from django.test.utils import override_settings

from zerver.lib.test_classes import ZulipTestCase
from zerver.models import get_realm
from zproject.backends import ZulipLDAPAuthBackend, ZulipLDAPExceptionOutsideDomain, \
    ZulipLDAPExceptionNoMatchingLDAPUser, sync_user_from_ldap

from django_auth_ldap.config import LDAPSearch

import ldap
import mock

"""
This is a file for additional LDAP tests, that don't belong
anywhere else.
"""

class DjangoToLDAPUsernameTests(ZulipTestCase):
    def setUp(self) -> None:
        self.init_default_ldap_database()
        self.backend = ZulipLDAPAuthBackend()

    def test_django_to_ldap_username_with_append_domain(self) -> None:
        with self.settings(LDAP_APPEND_DOMAIN="zulip.com"):
            self.assertEqual(self.backend.django_to_ldap_username("hamlet"), "hamlet")
            self.assertEqual(self.backend.django_to_ldap_username("hamlet@zulip.com"), "hamlet")
            with self.assertRaises(ZulipLDAPExceptionOutsideDomain):
                self.backend.django_to_ldap_username("hamlet@example.com")

    def test_django_to_ldap_username_without_email_search(self) -> None:
        with self.settings(AUTH_LDAP_REVERSE_EMAIL_SEARCH=None):
            self.assertEqual(self.backend.django_to_ldap_username("hamlet"), "hamlet")
            self.assertEqual(self.backend.django_to_ldap_username("newuser_email_as_uid@zulip.com"),
                             "newuser_email_as_uid@zulip.com")
            with self.assertRaises(ZulipLDAPExceptionNoMatchingLDAPUser):
                self.backend.django_to_ldap_username("hamlet@example.com")

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

        # Without email search, can't login via ldap:
        with self.settings(AUTH_LDAP_REVERSE_EMAIL_SEARCH=None, LDAP_EMAIL_ATTR='mail'):
            # Using hamlet's ldap password fails without email search:
            self.assertEqual(
                authenticate(username=user_profile.email, password=self.ldap_password(), realm=realm),
                None)
            # Need hamlet's zulip password to login (via email backend)
            self.assertEqual(
                authenticate(username=user_profile.email, password="testpassword", realm=realm),
                user_profile)
            # To login via ldap, username needs to be the ldap username, not email:
            self.assertEqual(
                authenticate(username=self.ldap_username("hamlet"), password=self.ldap_password(),
                             realm=realm),
                user_profile)

        # With email search:
        with self.settings(LDAP_EMAIL_ATTR='mail'):
            # Ldap password works now:
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

        with self.settings(AUTH_LDAP_REVERSE_EMAIL_SEARCH=None):
            # Without email search, the user will get deactivated.
            sync_user_from_ldap(user_profile, mock.Mock())
            self.assertFalse(user_profile.is_active)
