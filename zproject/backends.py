from __future__ import absolute_import

from django.contrib.auth.backends import RemoteUserBackend
from django.conf import settings
import django.contrib.auth

from django_auth_ldap.backend import LDAPBackend

from zerver.models import UserProfile, get_user_profile_by_id, \
    get_user_profile_by_email, remote_user_to_email, email_to_username

from openid.consumer.consumer import SUCCESS

def password_auth_enabled():
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
            if user_profile.check_password(password):
                return user_profile
        except UserProfile.DoesNotExist:
            return None

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
            return username + settings.LDAP_APPEND_DOMAIN
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
