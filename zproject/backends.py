from __future__ import absolute_import

import logging
from typing import Any, Dict, List, Set, Tuple, Optional, Text

from django.contrib.auth.backends import RemoteUserBackend
from django.conf import settings
from django.http import HttpResponse
import django.contrib.auth

from django_auth_ldap.backend import LDAPBackend, _LDAPUser
from zerver.lib.actions import do_create_user

from zerver.models import UserProfile, Realm, get_user_profile_by_id, \
    get_user_profile_by_email, remote_user_to_email, email_to_username, \
    get_realm, get_realm_by_email_domain

from apiclient.sample_tools import client as googleapiclient
from oauth2client.crypt import AppIdentityError
from social_core.backends.github import GithubOAuth2, GithubOrganizationOAuth2, \
    GithubTeamOAuth2
from social_core.exceptions import AuthFailed, SocialAuthBaseException
from django.contrib.auth import authenticate
from zerver.lib.users import check_full_name
from zerver.lib.request import JsonableError
from zerver.lib.utils import check_subdomain, get_subdomain

from social_django.models import DjangoStorage
from social_django.strategy import DjangoStrategy

def pad_method_dict(method_dict):
    # type: (Dict[Text, bool]) -> Dict[Text, bool]
    """Pads an authentication methods dict to contain all auth backends
    supported by the software, regardless of whether they are
    configured on this server"""
    for key in AUTH_BACKEND_NAME_MAP:
        if key not in method_dict:
            method_dict[key] = False
    return method_dict

def auth_enabled_helper(backends_to_check, realm):
    # type: (List[Text], Optional[Realm]) -> bool
    if realm is not None:
        enabled_method_dict = realm.authentication_methods_dict()
        pad_method_dict(enabled_method_dict)
    else:
        enabled_method_dict = dict((method, True) for method in Realm.AUTHENTICATION_FLAGS)
        pad_method_dict(enabled_method_dict)
    for supported_backend in django.contrib.auth.get_backends():
        for backend_name in backends_to_check:
            backend = AUTH_BACKEND_NAME_MAP[backend_name]
            if enabled_method_dict[backend_name] and isinstance(supported_backend, backend):
                return True
    return False

def ldap_auth_enabled(realm=None):
    # type: (Optional[Realm]) -> bool
    return auth_enabled_helper([u'LDAP'], realm)

def email_auth_enabled(realm=None):
    # type: (Optional[Realm]) -> bool
    return auth_enabled_helper([u'Email'], realm)

def password_auth_enabled(realm=None):
    # type: (Optional[Realm]) -> bool
    return ldap_auth_enabled(realm) or email_auth_enabled(realm)

def dev_auth_enabled(realm=None):
    # type: (Optional[Realm]) -> bool
    return auth_enabled_helper([u'Dev'], realm)

def google_auth_enabled(realm=None):
    # type: (Optional[Realm]) -> bool
    return auth_enabled_helper([u'Google'], realm)

def github_auth_enabled(realm=None):
    # type: (Optional[Realm]) -> bool
    return auth_enabled_helper([u'GitHub'], realm)

def any_oauth_backend_enabled(realm=None):
    # type: (Optional[Realm]) -> bool
    """Used by the login page process to determine whether to show the
    'OR' for login with Google"""
    return auth_enabled_helper([u'GitHub', u'Google'], realm)

def require_email_format_usernames(realm=None):
    # type: (Optional[Realm]) -> bool
    if ldap_auth_enabled(realm):
        if settings.LDAP_EMAIL_ATTR or settings.LDAP_APPEND_DOMAIN:
            return False
    return True

def common_get_active_user_by_email(email, return_data=None):
    # type: (Text, Optional[Dict[str, Any]]) -> Optional[UserProfile]
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
        # type: (int) -> Optional[UserProfile]
        """ Get a UserProfile object from the user_profile_id. """
        try:
            return get_user_profile_by_id(user_profile_id)
        except UserProfile.DoesNotExist:
            return None

class SocialAuthMixin(ZulipAuthMixin):
    auth_backend_name = None  # type: Text

    def get_email_address(self, *args, **kwargs):
        # type: (*Any, **Any) -> Text
        raise NotImplementedError

    def get_full_name(self, *args, **kwargs):
        # type: (*Any, **Any) -> Text
        raise NotImplementedError

    def authenticate(self,
                     realm_subdomain='',  # type: Optional[Text]
                     storage=None,  # type: Optional[DjangoStorage]
                     strategy=None,  # type: Optional[DjangoStrategy]
                     user=None,  # type: Optional[Dict[str, Any]]
                     return_data=None,  # type: Optional[Dict[str, Any]]
                     response=None,  # type: Optional[Dict[str, Any]]
                     backend=None  # type: Optional[GithubOAuth2]
                     ):
        # type: (...) -> Optional[UserProfile]
        """
        Django decides which `authenticate` to call by inspecting the
        arguments. So it's better to create `authenticate` function
        with well defined arguments.

        Keeping this function separate so that it can easily be
        overridden.
        """
        if user is None:
            user = {}

        if return_data is None:
            return_data = {}

        if response is None:
            response = {}

        return self._common_authenticate(self,
                                         realm_subdomain=realm_subdomain,
                                         storage=storage,
                                         strategy=strategy,
                                         user=user,
                                         return_data=return_data,
                                         response=response,
                                         backend=backend)

    def _common_authenticate(self, *args, **kwargs):
        # type: (*Any, **Any) -> Optional[UserProfile]
        return_data = kwargs.get('return_data', {})

        email_address = self.get_email_address(*args, **kwargs)
        if not email_address:
            return_data['invalid_email'] = True
            return None

        try:
            user_profile = get_user_profile_by_email(email_address)
        except UserProfile.DoesNotExist:
            return_data["valid_attestation"] = True
            return None

        if not user_profile.is_active:
            return_data["inactive_user"] = True
            return None

        if user_profile.realm.deactivated:
            return_data["inactive_realm"] = True
            return None

        if not check_subdomain(kwargs.get("realm_subdomain"),
                               user_profile.realm.subdomain):
            return_data["invalid_subdomain"] = True
            return None

        if not auth_enabled_helper([self.auth_backend_name], user_profile.realm):
            return_data["auth_backend_disabled"] = True
            return None

        return user_profile

    def process_do_auth(self, user_profile, *args, **kwargs):
        # type: (UserProfile, *Any, **Any) -> Optional[HttpResponse]
        # These functions need to be imported here to avoid cyclic
        # dependency.
        from zerver.views.auth import (login_or_register_remote_user,
                                       redirect_to_subdomain_login_url)
        from zerver.views.registration import redirect_and_log_into_subdomain

        return_data = kwargs.get('return_data', {})

        inactive_user = return_data.get('inactive_user')
        inactive_realm = return_data.get('inactive_realm')
        invalid_subdomain = return_data.get('invalid_subdomain')
        invalid_email = return_data.get('invalid_email')

        if inactive_user or inactive_realm:
            # Redirect to login page. We can't send to registration
            # workflow with these errors. We will redirect to login page.
            return None

        if invalid_email:
            # In case of invalid email, we will end up on registration page.
            # This seems better than redirecting to login page.
            logging.warning(
                "{} got invalid email argument.".format(self.auth_backend_name)
            )

        strategy = self.strategy  # type: ignore # This comes from Python Social Auth.
        request = strategy.request
        email_address = self.get_email_address(*args, **kwargs)
        full_name = self.get_full_name(*args, **kwargs)
        is_signup = strategy.session_get('is_signup') == '1'

        subdomain = strategy.session_get('subdomain')
        if not subdomain:
            return login_or_register_remote_user(request, email_address,
                                                 user_profile, full_name,
                                                 invalid_subdomain=bool(invalid_subdomain),
                                                 is_signup=is_signup)
        try:
            realm = Realm.objects.get(string_id=subdomain)
        except Realm.DoesNotExist:
            return redirect_to_subdomain_login_url()

        return redirect_and_log_into_subdomain(realm, full_name, email_address,
                                               is_signup=is_signup)

    def auth_complete(self, *args, **kwargs):
        # type: (*Any, **Any) -> Optional[HttpResponse]
        """
        Returning `None` from this function will redirect the browser
        to the login page.
        """
        try:
            # Call the auth_complete method of BaseOAuth2 is Python Social Auth
            return super(SocialAuthMixin, self).auth_complete(*args, **kwargs)  # type: ignore # monkey-patching
        except AuthFailed:
            return None
        except SocialAuthBaseException as e:
            logging.exception(e)
            return None

class ZulipDummyBackend(ZulipAuthMixin):
    """
    Used when we want to log you in but we don't know which backend to use.
    """

    def authenticate(self, username=None, realm_subdomain=None, use_dummy_backend=False,
                     return_data=None):
        # type: (Optional[Text], Optional[Text], bool, Optional[Dict[str, Any]]) -> Optional[UserProfile]
        assert username is not None
        if use_dummy_backend:
            user_profile = common_get_active_user_by_email(username)
            if user_profile is None:
                return None
            if not check_subdomain(realm_subdomain, user_profile.realm.subdomain):
                if return_data is not None:
                    return_data["invalid_subdomain"] = True
                return None
            return user_profile
        return None

class EmailAuthBackend(ZulipAuthMixin):
    """
    Email Authentication Backend

    Allows a user to sign in using an email/password pair rather than
    a username/password pair.
    """

    def authenticate(self, username=None, password=None, realm_subdomain=None, return_data=None):
        # type: (Optional[Text], Optional[str], Optional[Text], Optional[Dict[str, Any]]) -> Optional[UserProfile]
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
        if not email_auth_enabled(user_profile.realm):
            if return_data is not None:
                return_data['email_auth_disabled'] = True
            return None
        if user_profile.check_password(password):
            if not check_subdomain(realm_subdomain, user_profile.realm.subdomain):
                if return_data is not None:
                    return_data["invalid_subdomain"] = True
                return None
            return user_profile
        return None

class GoogleMobileOauth2Backend(ZulipAuthMixin):
    """
    Google Apps authentication for mobile devices

    Allows a user to sign in using a Google-issued OAuth2 token.

    Ref:
        https://developers.google.com/+/mobile/android/sign-in#server-side_access_for_your_app
        https://developers.google.com/accounts/docs/CrossClientAuth#offlineAccess

    """

    def authenticate(self, google_oauth2_token=None, realm_subdomain=None, return_data=None):
        # type: (Optional[str], Optional[Text], Optional[Dict[str, Any]]) -> Optional[UserProfile]
        if return_data is None:
            return_data = {}

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
            if not check_subdomain(realm_subdomain, user_profile.realm.subdomain):
                return_data["invalid_subdomain"] = True
                return None
            if not google_auth_enabled(realm=user_profile.realm):
                return_data["google_auth_disabled"] = True
                return None
            return user_profile
        else:
            return_data["valid_attestation"] = False
            return None

class ZulipRemoteUserBackend(RemoteUserBackend):
    create_unknown_user = False

    def authenticate(self, remote_user, realm_subdomain=None):
        # type: (Optional[str], Optional[Text]) -> Optional[UserProfile]
        if not remote_user:
            return None

        email = remote_user_to_email(remote_user)
        user_profile = common_get_active_user_by_email(email)
        if user_profile is None:
            return None
        if not check_subdomain(realm_subdomain, user_profile.realm.subdomain):
            return None
        if not auth_enabled_helper([u"RemoteUser"], user_profile.realm):
            return None
        return user_profile

class ZulipLDAPException(Exception):
    pass

class ZulipLDAPAuthBackendBase(ZulipAuthMixin, LDAPBackend):
    # Don't use Django LDAP's permissions functions
    def has_perm(self, user, perm, obj=None):
        # type: (Optional[UserProfile], Any, Any) -> bool
        # Using Any type is safe because we are not doing anything with
        # the arguments.
        return False

    def has_module_perms(self, user, app_label):
        # type: (Optional[UserProfile], Optional[str]) -> bool
        return False

    def get_all_permissions(self, user, obj=None):
        # type: (Optional[UserProfile], Any) -> Set
        # Using Any type is safe because we are not doing anything with
        # the arguments.
        return set()

    def get_group_permissions(self, user, obj=None):
        # type: (Optional[UserProfile], Any) -> Set
        # Using Any type is safe because we are not doing anything with
        # the arguments.
        return set()

    def django_to_ldap_username(self, username):
        # type: (Text) -> Text
        if settings.LDAP_APPEND_DOMAIN:
            if not username.endswith("@" + settings.LDAP_APPEND_DOMAIN):
                raise ZulipLDAPException("Username does not match LDAP domain.")
            return email_to_username(username)
        return username

    def ldap_to_django_username(self, username):
        # type: (str) -> str
        if settings.LDAP_APPEND_DOMAIN:
            return "@".join((username, settings.LDAP_APPEND_DOMAIN))
        return username

class ZulipLDAPAuthBackend(ZulipLDAPAuthBackendBase):
    def authenticate(self, username, password, realm_subdomain=None, return_data=None):
        # type: (Text, str, Optional[Text], Optional[Dict[str, Any]]) -> Optional[UserProfile]
        try:
            if settings.REALMS_HAVE_SUBDOMAINS:
                self._realm = get_realm(realm_subdomain)
            elif settings.LDAP_EMAIL_ATTR is not None:
                self._realm = get_realm_by_email_domain(username)
            username = self.django_to_ldap_username(username)
            user_profile = ZulipLDAPAuthBackendBase.authenticate(self, username, password)
            if user_profile is None:
                return None
            if not check_subdomain(realm_subdomain, user_profile.realm.subdomain):
                return None
            return user_profile
        except Realm.DoesNotExist:
            return None
        except ZulipLDAPException:
            return None

    def get_or_create_user(self, username, ldap_user):
        # type: (str, _LDAPUser) -> Tuple[UserProfile, bool]
        try:
            if settings.LDAP_EMAIL_ATTR is not None:
                # Get email from ldap attributes.
                if settings.LDAP_EMAIL_ATTR not in ldap_user.attrs:
                    raise ZulipLDAPException("LDAP user doesn't have the needed %s attribute" % (settings.LDAP_EMAIL_ATTR,))

                username = ldap_user.attrs[settings.LDAP_EMAIL_ATTR][0]
                self._realm = get_realm_by_email_domain(username)

            user_profile = get_user_profile_by_email(username)
            if not user_profile.is_active or user_profile.realm.deactivated:
                raise ZulipLDAPException("Realm has been deactivated")
            if not ldap_auth_enabled(user_profile.realm):
                raise ZulipLDAPException("LDAP Authentication is not enabled")
            return user_profile, False
        except UserProfile.DoesNotExist:
            if self._realm is None:
                raise ZulipLDAPException("Realm is None")
            # No need to check for an inactive user since they don't exist yet
            if self._realm.deactivated:
                raise ZulipLDAPException("Realm has been deactivated")

            full_name_attr = settings.AUTH_LDAP_USER_ATTR_MAP["full_name"]
            short_name = full_name = ldap_user.attrs[full_name_attr][0]
            try:
                full_name = check_full_name(full_name)
            except JsonableError as e:
                raise ZulipLDAPException(e.msg)
            if "short_name" in settings.AUTH_LDAP_USER_ATTR_MAP:
                short_name_attr = settings.AUTH_LDAP_USER_ATTR_MAP["short_name"]
                short_name = ldap_user.attrs[short_name_attr][0]

            user_profile = do_create_user(username, None, self._realm, full_name, short_name)
            return user_profile, True

# Just like ZulipLDAPAuthBackend, but doesn't let you log in.
class ZulipLDAPUserPopulator(ZulipLDAPAuthBackendBase):
    def authenticate(self, username, password, realm_subdomain=None):
        # type: (Text, str, Optional[Text]) -> None
        return None

class DevAuthBackend(ZulipAuthMixin):
    # Allow logging in as any user without a password.
    # This is used for convenience when developing Zulip.
    def authenticate(self, username, realm_subdomain=None, return_data=None):
        # type: (Text, Optional[Text], Optional[Dict[str, Any]]) -> Optional[UserProfile]
        user_profile = common_get_active_user_by_email(username, return_data=return_data)
        if user_profile is None:
            return None
        if not dev_auth_enabled(user_profile.realm):
            return None
        return user_profile

class GitHubAuthBackend(SocialAuthMixin, GithubOAuth2):
    auth_backend_name = u"GitHub"

    def get_email_address(self, *args, **kwargs):
        # type: (*Any, **Any) -> Optional[Text]
        try:
            return kwargs['response']['email']
        except KeyError:
            return None

    def get_full_name(self, *args, **kwargs):
        # type: (*Any, **Any) -> Text
        # In case of any error return an empty string. Name is used by
        # the registration page to pre-populate the name field. However,
        # if it is not supplied, our registration process will make sure
        # that the user enters a valid name.
        try:
            name = kwargs['response']['name']
        except KeyError:
            name = ''

        if name is None:
            return ''

        return name

    def do_auth(self, *args, **kwargs):
        # type: (*Any, **Any) -> Optional[HttpResponse]
        """
        This function is called once the OAuth2 workflow is complete. We
        override this function to:
            1. Inject `return_data` and `realm_admin` kwargs. These will
               be used by `authenticate()` function to make the decision.
            2. Call the proper `do_auth` function depending on whether
               we are doing individual, team or organization based GitHub
               authentication.
        The actual decision on authentication is done in
        SocialAuthMixin._common_authenticate().
        """
        kwargs['return_data'] = {}

        request = self.strategy.request
        kwargs['realm_subdomain'] = get_subdomain(request)

        user_profile = None

        team_id = settings.SOCIAL_AUTH_GITHUB_TEAM_ID
        org_name = settings.SOCIAL_AUTH_GITHUB_ORG_NAME

        if (team_id is None and org_name is None):
            try:
                user_profile = GithubOAuth2.do_auth(self, *args, **kwargs)
            except AuthFailed:
                logging.info("User authentication failed.")
                user_profile = None

        elif (team_id):
            backend = GithubTeamOAuth2(self.strategy, self.redirect_uri)
            try:
                user_profile = backend.do_auth(*args, **kwargs)
            except AuthFailed:
                logging.info("User is not member of GitHub team.")
                user_profile = None

        elif (org_name):
            backend = GithubOrganizationOAuth2(self.strategy, self.redirect_uri)
            try:
                user_profile = backend.do_auth(*args, **kwargs)
            except AuthFailed:
                logging.info("User is not member of GitHub organization.")
                user_profile = None

        return self.process_do_auth(user_profile, *args, **kwargs)

AUTH_BACKEND_NAME_MAP = {
    u'Dev': DevAuthBackend,
    u'Email': EmailAuthBackend,
    u'GitHub': GitHubAuthBackend,
    u'Google': GoogleMobileOauth2Backend,
    u'LDAP': ZulipLDAPAuthBackend,
    u'RemoteUser': ZulipRemoteUserBackend,
}  # type: Dict[Text, Any]
