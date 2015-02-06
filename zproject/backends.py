from __future__ import absolute_import

from django.contrib.auth.backends import RemoteUserBackend
from django.conf import settings
import django.contrib.auth

from django_auth_ldap.backend import LDAPBackend

from zerver.models import UserProfile, get_user_profile_by_id, \
    get_user_profile_by_email, remote_user_to_email, email_to_username

from openid.consumer.consumer import SUCCESS
from apiclient.sample_tools import client as googleapiclient
from oauth2client.crypt import AppIdentityError

def password_auth_enabled(realm):
    if realm.domain == 'employees.customer16.invalid':
        return False
    elif realm.domain == 'zulip.com' and not settings.TEST_SUITE:
        # the dropbox realm is SSO only, but the unit tests still need to be
        # able to login
        return False

    for backend in django.contrib.auth.get_backends():
         if isinstance(backend, EmailAuthBackend):
             return True
    return False

class ZulipAuthMixin(object):
    def get_user(self, user_profile_id):
        """ Get a UserProfile object from the user_profile_id. """
        try:
            return get_user_profile_by_id(user_profile_id)
        except UserProfile.DoesNotExist:
            return None

class ZulipDummyBackend(ZulipAuthMixin):
    """
    Used when we want to log you in but we don't know which backend to use.
    """
    def authenticate(self, username=None, use_dummy_backend=False):
        if use_dummy_backend:
            try:
                return get_user_profile_by_email(username)
            except UserProfile.DoesNotExist:
                pass
        return None

class EmailAuthBackend(ZulipAuthMixin):
    """
    Email Authentication Backend

    Allows a user to sign in using an email/password pair rather than
    a username/password pair.
    """

    def authenticate(self, username=None, password=None):
        """ Authenticate a user based on email address as the user name. """
        if username is None or password is None:
            # Return immediately.  Otherwise we will look for a SQL row with
            # NULL username.  While that's probably harmless, it's needless
            # exposure.
            return None

        try:
            user_profile = get_user_profile_by_email(username)
            if not password_auth_enabled(user_profile.realm):
                return None
            if user_profile.check_password(password):
                return user_profile
        except UserProfile.DoesNotExist:
            return None

class GoogleMobileOauth2Backend(ZulipAuthMixin):
    """
    Google Apps authentication for mobile devices

    Allows a user to sign in using a Google-issued OAuth2 token.

    Ref:
        https://developers.google.com/+/mobile/android/sign-in#server-side_access_for_your_app
        https://developers.google.com/accounts/docs/CrossClientAuth#offlineAccess

    This backend is not currently supported on enterprise.
    """
    def authenticate(self, google_oauth2_token=None, return_data={}):
        try:
            token_payload = googleapiclient.verify_id_token(google_oauth2_token, settings.GOOGLE_CLIENT_ID)
        except AppIdentityError:
            return None
        if token_payload["email_verified"] in (True, "true"):
            try:
                return get_user_profile_by_email(token_payload["email"])
            except UserProfile.DoesNotExist:
                return_data["valid_attestation"] = True
                return None
        else:
            return_data["valid_attestation"] = False

# Adapted from http://djangosnippets.org/snippets/2183/ by user Hangya (September 1, 2010)

class GoogleBackend(ZulipAuthMixin):
    def authenticate(self, openid_response):
        if openid_response is None:
            return None
        if openid_response.status != SUCCESS:
            return None

        google_email = openid_response.getSigned('http://openid.net/srv/ax/1.0', 'value.email')

        try:
            user_profile = get_user_profile_by_email(google_email)
        except UserProfile.DoesNotExist:
            # create a new user, or send a message to admins, etc.
            return None

        if user_profile.is_mirror_dummy:
            # mirror dummies can not login, but they can convert to real users
            return None

        return user_profile

class ZulipRemoteUserBackend(RemoteUserBackend):
    create_unknown_user = False

    def authenticate(self, remote_user):
        if not remote_user:
            return

        email = remote_user_to_email(remote_user)

        try:
            return get_user_profile_by_email(email)
        except UserProfile.DoesNotExist:
            return None

class ZulipLDAPAuthBackend(ZulipAuthMixin, LDAPBackend):
    def django_to_ldap_username(self, username):
        if settings.LDAP_APPEND_DOMAIN is not None:
            return email_to_username(username)
        return username

    def ldap_to_django_username(self, username):
        if settings.LDAP_APPEND_DOMAIN is not None:
            return "@".join((username, settings.LDAP_APPEND_DOMAIN))
        return username

    def get_or_create_user(self, username, ldap_user):
        try:
            return get_user_profile_by_email(username), False
        except UserProfile.DoesNotExist:
            return UserProfile(), False

class ZulipLDAPUserPopulator(ZulipLDAPAuthBackend):
    # Just like ZulipLDAPAuthBackend, but doesn't let you log in.

    def authenticate(self, username, password):
        return None
