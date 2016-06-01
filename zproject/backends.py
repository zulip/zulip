from __future__ import absolute_import

from django.contrib.auth.backends import RemoteUserBackend
from django.conf import settings
import django.contrib.auth

from django_auth_ldap.backend import LDAPBackend
from zerver.lib.actions import do_create_user

from zerver.models import UserProfile, Realm, get_user_profile_by_id, \
    get_user_profile_by_email, remote_user_to_email, email_to_username, \
    resolve_email_to_domain, get_realm

from apiclient.sample_tools import client as googleapiclient
from oauth2client.crypt import AppIdentityError

def password_auth_enabled(realm):
    if realm is not None:
        if realm.domain == 'zulip.com' and settings.PRODUCTION:
            # the dropbox realm is SSO only, but the unit tests still need to be
            # able to login
            return False

    for backend in django.contrib.auth.get_backends():
         if isinstance(backend, EmailAuthBackend):
             return True
         if isinstance(backend, ZulipLDAPAuthBackend):
             return True
    return False

def dev_auth_enabled():
    for backend in django.contrib.auth.get_backends():
        if isinstance(backend, DevAuthBackend):
            return True
    return False

def google_auth_enabled():
    for backend in django.contrib.auth.get_backends():
        if isinstance(backend, GoogleMobileOauth2Backend):
            return True
    return False

def common_get_active_user_by_email(email, return_data=None):
    try:
        user_profile = get_user_profile_by_email(email)
    except UserProfile.DoesNotExist:
        return None
    if not user_profile.is_active:
        if return_data is not None:
            return_data['inactive_user'] = True
        return None
    if user_profile.realm.deactivated:
        if return_data is not None:
            return_data['inactive_realm'] = True
        return None
    return user_profile

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
            return common_get_active_user_by_email(username)
        return None

class EmailAuthBackend(ZulipAuthMixin):
    """
    Email Authentication Backend

    Allows a user to sign in using an email/password pair rather than
    a username/password pair.
    """

    def authenticate(self, username=None, password=None, return_data=None):
        """ Authenticate a user based on email address as the user name. """
        if username is None or password is None:
            # Return immediately.  Otherwise we will look for a SQL row with
            # NULL username.  While that's probably harmless, it's needless
            # exposure.
            return None

        user_profile = common_get_active_user_by_email(username, return_data=return_data)
        if user_profile is None:
            return None
        if not password_auth_enabled(user_profile.realm):
            if return_data is not None:
                return_data['password_auth_disabled'] = True
            return None
        if user_profile.check_password(password):
            return user_profile

class GoogleMobileOauth2Backend(ZulipAuthMixin):
    """
    Google Apps authentication for mobile devices

    Allows a user to sign in using a Google-issued OAuth2 token.

    Ref:
        https://developers.google.com/+/mobile/android/sign-in#server-side_access_for_your_app
        https://developers.google.com/accounts/docs/CrossClientAuth#offlineAccess

    """
    def authenticate(self, google_oauth2_token=None, return_data={}):
        try:
            token_payload = googleapiclient.verify_id_token(google_oauth2_token, settings.GOOGLE_CLIENT_ID)
        except AppIdentityError:
            return None
        if token_payload["email_verified"] in (True, "true"):
            try:
                user_profile = get_user_profile_by_email(token_payload["email"])
            except UserProfile.DoesNotExist:
                return_data["valid_attestation"] = True
                return None
            if not user_profile.is_active:
                return_data["inactive_user"] = True
                return None
            if user_profile.realm.deactivated:
                return_data["inactive_realm"] = True
                return None
            return user_profile
        else:
            return_data["valid_attestation"] = False

class ZulipRemoteUserBackend(RemoteUserBackend):
    create_unknown_user = False

    def authenticate(self, remote_user):
        if not remote_user:
            return None

        email = remote_user_to_email(remote_user)
        return common_get_active_user_by_email(email)

class ZulipLDAPException(Exception):
    pass

class ZulipLDAPAuthBackendBase(ZulipAuthMixin, LDAPBackend):
    # Don't use Django LDAP's permissions functions
    def has_perm(self, user, perm, obj=None):
        return False
    def has_module_perms(self, user, app_label):
        return False
    def get_all_permissions(self, user, obj=None):
        return set()
    def get_group_permissions(self, user, obj=None):
        return set()

    def django_to_ldap_username(self, username):
        if settings.LDAP_APPEND_DOMAIN:
            if not username.endswith("@" + settings.LDAP_APPEND_DOMAIN):
                raise ZulipLDAPException("Username does not match LDAP domain.")
            return email_to_username(username)
        return username
    def ldap_to_django_username(self, username):
        if settings.LDAP_APPEND_DOMAIN:
            return "@".join((username, settings.LDAP_APPEND_DOMAIN))
        return username

class ZulipLDAPAuthBackend(ZulipLDAPAuthBackendBase):
    def authenticate(self, username, password):
        try:
            username = self.django_to_ldap_username(username)
            return ZulipLDAPAuthBackendBase.authenticate(self, username, password)
        except Realm.DoesNotExist:
            return None
        except ZulipLDAPException:
            return None

    def get_or_create_user(self, username, ldap_user):
        try:
            user_profile = get_user_profile_by_email(username)
            if not user_profile.is_active or user_profile.realm.deactivated:
                raise ZulipLDAPException("Realm has been deactivated")
            return user_profile, False
        except UserProfile.DoesNotExist:
            domain = resolve_email_to_domain(username)
            realm = get_realm(domain)
            # No need to check for an inactive user since they don't exist yet
            if realm.deactivated:
                raise ZulipLDAPException("Realm has been deactivated")

            full_name_attr = settings.AUTH_LDAP_USER_ATTR_MAP["full_name"]
            short_name = full_name = ldap_user.attrs[full_name_attr][0]
            if "short_name" in settings.AUTH_LDAP_USER_ATTR_MAP:
                short_name_attr = settings.AUTH_LDAP_USER_ATTR_MAP["short_name"]
                short_name = ldap_user.attrs[short_name_attr][0]

            user_profile = do_create_user(username, None, realm, full_name, short_name)
            return user_profile, False

# Just like ZulipLDAPAuthBackend, but doesn't let you log in.
class ZulipLDAPUserPopulator(ZulipLDAPAuthBackendBase):
    def authenticate(self, username, password):
        return None

class DevAuthBackend(ZulipAuthMixin):
    # Allow logging in as any user without a password.
    # This is used for convenience when developing Zulip.

    def authenticate(self, username, return_data=None):
        return common_get_active_user_by_email(username, return_data=return_data)
