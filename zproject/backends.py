import logging
from typing import Any, Dict, List, Set, Tuple, Optional, Text

from apiclient.sample_tools import client as googleapiclient
from django_auth_ldap.backend import LDAPBackend, _LDAPUser
import django.contrib.auth
from django.contrib.auth.backends import RemoteUserBackend
from django.conf import settings
from django.http import HttpResponse
from oauth2client.crypt import AppIdentityError
from social_core.backends.github import GithubOAuth2, GithubOrganizationOAuth2, \
    GithubTeamOAuth2
from social_core.utils import handle_http_errors
from social_core.exceptions import AuthFailed, SocialAuthBaseException
from social_django.models import DjangoStorage
from social_django.strategy import DjangoStrategy

from zerver.lib.actions import do_create_user
from zerver.lib.request import JsonableError
from zerver.lib.subdomains import user_matches_subdomain, get_subdomain
from zerver.lib.users import check_full_name
from zerver.models import UserProfile, Realm, get_user_profile_by_id, \
    remote_user_to_email, email_to_username, get_realm, get_user

def pad_method_dict(method_dict: Dict[Text, bool]) -> Dict[Text, bool]:
    """Pads an authentication methods dict to contain all auth backends
    supported by the software, regardless of whether they are
    configured on this server"""
    for key in AUTH_BACKEND_NAME_MAP:
        if key not in method_dict:
            method_dict[key] = False
    return method_dict

def auth_enabled_helper(backends_to_check: List[Text], realm: Optional[Realm]) -> bool:
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

def ldap_auth_enabled(realm: Optional[Realm]=None) -> bool:
    return auth_enabled_helper(['LDAP'], realm)

def email_auth_enabled(realm: Optional[Realm]=None) -> bool:
    return auth_enabled_helper(['Email'], realm)

def password_auth_enabled(realm: Optional[Realm]=None) -> bool:
    return ldap_auth_enabled(realm) or email_auth_enabled(realm)

def dev_auth_enabled(realm: Optional[Realm]=None) -> bool:
    return auth_enabled_helper(['Dev'], realm)

def google_auth_enabled(realm: Optional[Realm]=None) -> bool:
    return auth_enabled_helper(['Google'], realm)

def github_auth_enabled(realm: Optional[Realm]=None) -> bool:
    return auth_enabled_helper(['GitHub'], realm)

def remote_auth_enabled(realm: Optional[Realm]=None) -> bool:
    return auth_enabled_helper(['RemoteUser'], realm)

def any_oauth_backend_enabled(realm: Optional[Realm]=None) -> bool:
    """Used by the login page process to determine whether to show the
    'OR' for login with Google"""
    return auth_enabled_helper(['GitHub', 'Google'], realm)

def require_email_format_usernames(realm: Optional[Realm]=None) -> bool:
    if ldap_auth_enabled(realm):
        if settings.LDAP_EMAIL_ATTR or settings.LDAP_APPEND_DOMAIN:
            return False
    return True

def common_get_active_user(email: str, realm: Realm,
                           return_data: Dict[str, Any]=None) -> Optional[UserProfile]:
    try:
        user_profile = get_user(email, realm)
    except UserProfile.DoesNotExist:
        # If the user doesn't have an account in the target realm, we
        # check whether they might have an account in another realm,
        # and if so, provide a helpful error message via
        # `invalid_subdomain`.
        if not UserProfile.objects.filter(email__iexact=email).exists():
            return None
        if return_data is not None:
            return_data['invalid_subdomain'] = True
        return None
    if not user_profile.is_active:
        if return_data is not None:
            if user_profile.is_mirror_dummy:
                # Record whether it's a mirror dummy account
                return_data['is_mirror_dummy'] = True
            return_data['inactive_user'] = True
        return None
    if user_profile.realm.deactivated:
        if return_data is not None:
            return_data['inactive_realm'] = True
        return None
    return user_profile

class ZulipAuthMixin:
    def get_user(self, user_profile_id: int) -> Optional[UserProfile]:
        """ Get a UserProfile object from the user_profile_id. """
        try:
            return get_user_profile_by_id(user_profile_id)
        except UserProfile.DoesNotExist:
            return None

class SocialAuthMixin(ZulipAuthMixin):
    auth_backend_name = None  # type: Text

    def get_email_address(self, *args: Any, **kwargs: Any) -> Text:
        raise NotImplementedError

    def get_full_name(self, *args: Any, **kwargs: Any) -> Text:
        raise NotImplementedError

    def get_authenticated_user(self, *args: Any, **kwargs: Any) -> Optional[UserProfile]:
        raise NotImplementedError

    @handle_http_errors
    def do_auth(self, *args: Any, **kwargs: Any) -> Optional[HttpResponse]:
        """
        This function is called once the authentication workflow is complete.
        We override this function to:
            1. Inject `return_data` and `realm_subdomain` kwargs. These will be
               used by `authenticate()` functions of backends to make the
               decision.
            2. Call the proper authentication function to get the user in
               `get_authenticated_user`.

        The actual decision on authentication is done in
        SocialAuthMixin._common_authenticate().

        SocialAuthMixin.get_authenticated_user is expected to be overridden by
        the derived class to add custom logic for authenticating the user and
        returning the user.
        """
        kwargs['return_data'] = {}
        subdomain = self.strategy.session_get('subdomain')  # type: ignore # `strategy` comes from Python Social Auth.
        realm = get_realm(subdomain)
        kwargs['realm'] = realm
        user_profile = self.get_authenticated_user(*args, **kwargs)
        return self.process_do_auth(user_profile, *args, **kwargs)

    def authenticate(self,
                     realm: Optional[Realm]=None,
                     storage: Optional[DjangoStorage]=None,
                     strategy: Optional[DjangoStrategy]=None,
                     user: Optional[Dict[str, Any]]=None,
                     return_data: Optional[Dict[str, Any]]=None,
                     response: Optional[Dict[str, Any]]=None,
                     backend: Optional[GithubOAuth2]=None
                     ) -> Optional[UserProfile]:
        """
        Django decides which `authenticate` to call by inspecting the
        arguments. So it's better to create `authenticate` function
        with well defined arguments.

        Keeping this function separate so that it can easily be
        overridden.
        """
        if user is None:
            user = {}

        assert return_data is not None
        assert response is not None

        return self._common_authenticate(self,
                                         realm=realm,
                                         storage=storage,
                                         strategy=strategy,
                                         user=user,
                                         return_data=return_data,
                                         response=response,
                                         backend=backend)

    def _common_authenticate(self, *args: Any, **kwargs: Any) -> Optional[UserProfile]:
        return_data = kwargs.get('return_data', {})
        realm = kwargs.get("realm")
        if realm is None:
            return None
        if not auth_enabled_helper([self.auth_backend_name], realm):
            return_data["auth_backend_disabled"] = True
            return None

        email_address = self.get_email_address(*args, **kwargs)
        if not email_address:
            return_data['invalid_email'] = True
            return None

        return_data["valid_attestation"] = True
        return common_get_active_user(email_address, realm, return_data)

    def process_do_auth(self, user_profile: UserProfile, *args: Any,
                        **kwargs: Any) -> Optional[HttpResponse]:
        # These functions need to be imported here to avoid cyclic
        # dependency.
        from zerver.views.auth import (login_or_register_remote_user,
                                       redirect_to_subdomain_login_url,
                                       redirect_and_log_into_subdomain)

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
            return None

        strategy = self.strategy  # type: ignore # This comes from Python Social Auth.
        request = strategy.request
        email_address = self.get_email_address(*args, **kwargs)
        full_name = self.get_full_name(*args, **kwargs)
        is_signup = strategy.session_get('is_signup') == '1'
        redirect_to = strategy.session_get('next')

        mobile_flow_otp = strategy.session_get('mobile_flow_otp')
        subdomain = strategy.session_get('subdomain')
        if not subdomain:
            # At least in our tests, this can be None; and it's not
            # clear what the exact semantics of `session_get` are or
            # what values it might return.  Historically we treated
            # any falsy value here as the root domain, so defensively
            # continue that behavior.
            subdomain = Realm.SUBDOMAIN_FOR_ROOT_DOMAIN
        if (subdomain == Realm.SUBDOMAIN_FOR_ROOT_DOMAIN
                or mobile_flow_otp is not None):
            return login_or_register_remote_user(request, email_address,
                                                 user_profile, full_name,
                                                 invalid_subdomain=bool(invalid_subdomain),
                                                 mobile_flow_otp=mobile_flow_otp,
                                                 is_signup=is_signup,
                                                 redirect_to=redirect_to)
        realm = get_realm(subdomain)
        if realm is None:
            return redirect_to_subdomain_login_url()
        return redirect_and_log_into_subdomain(realm, full_name, email_address,
                                               is_signup=is_signup,
                                               redirect_to=redirect_to)

    def auth_complete(self, *args: Any, **kwargs: Any) -> Optional[HttpResponse]:
        """
        Returning `None` from this function will redirect the browser
        to the login page.
        """
        try:
            # Call the auth_complete method of social_core.backends.oauth.BaseOAuth2
            return super().auth_complete(*args, **kwargs)  # type: ignore # monkey-patching
        except AuthFailed:
            return None
        except SocialAuthBaseException as e:
            logging.warning(str(e))
            return None

class ZulipDummyBackend(ZulipAuthMixin):
    """
    Used when we want to log you in without checking any
    authentication (i.e. new user registration or when otherwise
    authentication has already been checked earlier in the process).
    """

    def authenticate(self, username: Optional[str]=None, realm: Optional[Realm]=None,
                     use_dummy_backend: bool=False,
                     return_data: Dict[str, Any]=None) -> Optional[UserProfile]:
        if use_dummy_backend:
            # These are kwargs only for readability; they should never be None
            assert username is not None
            assert realm is not None
            return common_get_active_user(username, realm, return_data)
        return None

class EmailAuthBackend(ZulipAuthMixin):
    """
    Email Authentication Backend

    Allows a user to sign in using an email/password pair rather than
    a username/password pair.
    """

    def authenticate(self, username: Optional[str]=None, password: Optional[str]=None,
                     realm: Optional[Realm]=None,
                     return_data: Optional[Dict[str, Any]]=None) -> Optional[UserProfile]:
        """ Authenticate a user based on email address as the user name. """
        if username is None or password is None:
            # Because of how we structure our auth calls to always
            # specify which backend to use when not using
            # EmailAuthBackend, username and password should always be set.
            raise AssertionError("Invalid call to authenticate for EmailAuthBackend")
        if realm is None:
            return None
        if not password_auth_enabled(realm):
            if return_data is not None:
                return_data['password_auth_disabled'] = True
            return None
        if not email_auth_enabled(realm):
            if return_data is not None:
                return_data['email_auth_disabled'] = True
            return None

        user_profile = common_get_active_user(username, realm, return_data=return_data)
        if user_profile is None:
            return None
        if user_profile.check_password(password):
            return user_profile
        return None

class GoogleMobileOauth2Backend(ZulipAuthMixin):
    """
    Google Apps authentication for the legacy Android app.
    DummyAuthBackend is what's actually used for our modern Google auth,
    both for web and mobile (the latter via the mobile_flow_otp feature).

    Allows a user to sign in using a Google-issued OAuth2 token.

    Ref:
        https://developers.google.com/+/mobile/android/sign-in#server-side_access_for_your_app
        https://developers.google.com/accounts/docs/CrossClientAuth#offlineAccess
    """

    def authenticate(self, google_oauth2_token: str=None, realm: Optional[Realm]=None,
                     return_data: Optional[Dict[str, Any]]=None) -> Optional[UserProfile]:
        if realm is None:
            return None
        if return_data is None:
            return_data = {}

        if not google_auth_enabled(realm=realm):
            return_data["google_auth_disabled"] = True
            return None

        try:
            token_payload = googleapiclient.verify_id_token(google_oauth2_token, settings.GOOGLE_CLIENT_ID)
        except AppIdentityError:
            return None

        if token_payload["email_verified"] not in (True, "true"):
            return_data["valid_attestation"] = False
            return None

        return_data["valid_attestation"] = True
        return common_get_active_user(token_payload["email"], realm, return_data)

class ZulipRemoteUserBackend(RemoteUserBackend):
    create_unknown_user = False

    def authenticate(self, remote_user: Optional[str],
                     realm: Optional[Realm]=None) -> Optional[UserProfile]:
        assert remote_user is not None
        if realm is None:
            return None
        if not auth_enabled_helper(["RemoteUser"], realm):
            return None

        email = remote_user_to_email(remote_user)
        return common_get_active_user(email, realm)

class ZulipLDAPException(_LDAPUser.AuthenticationFailed):
    pass

class ZulipLDAPConfigurationError(Exception):
    pass

class ZulipLDAPAuthBackendBase(ZulipAuthMixin, LDAPBackend):
    # Don't use Django LDAP's permissions functions
    def has_perm(self, user: Optional[UserProfile], perm: Any, obj: Any=None) -> bool:
        # Using Any type is safe because we are not doing anything with
        # the arguments.
        return False

    def has_module_perms(self, user: Optional[UserProfile], app_label: Optional[str]) -> bool:
        return False

    def get_all_permissions(self, user: Optional[UserProfile], obj: Any=None) -> Set[Any]:
        # Using Any type is safe because we are not doing anything with
        # the arguments and always return empty set.
        return set()

    def get_group_permissions(self, user: Optional[UserProfile], obj: Any=None) -> Set[Any]:
        # Using Any type is safe because we are not doing anything with
        # the arguments and always return empty set.
        return set()

    def django_to_ldap_username(self, username: Text) -> Text:
        if settings.LDAP_APPEND_DOMAIN:
            if not username.endswith("@" + settings.LDAP_APPEND_DOMAIN):
                raise ZulipLDAPException("Username does not match LDAP domain.")
            return email_to_username(username)
        return username

    def ldap_to_django_username(self, username: str) -> str:
        if settings.LDAP_APPEND_DOMAIN:
            return "@".join((username, settings.LDAP_APPEND_DOMAIN))
        return username

class ZulipLDAPAuthBackend(ZulipLDAPAuthBackendBase):
    REALM_IS_NONE_ERROR = 1

    def authenticate(self, username: str, password: str, realm: Optional[Realm]=None,
                     return_data: Optional[Dict[str, Any]]=None) -> Optional[UserProfile]:
        if realm is None:
            return None
        self._realm = realm
        if not ldap_auth_enabled(realm):
            return None

        try:
            username = self.django_to_ldap_username(username)
            return ZulipLDAPAuthBackendBase.authenticate(self,
                                                         username=username,
                                                         password=password)
        except ZulipLDAPException:
            return None  # nocoverage # TODO: this may no longer be possible

    def get_or_create_user(self, username: str, ldap_user: _LDAPUser) -> Tuple[UserProfile, bool]:

        if settings.LDAP_EMAIL_ATTR is not None:
            # Get email from ldap attributes.
            if settings.LDAP_EMAIL_ATTR not in ldap_user.attrs:
                raise ZulipLDAPException("LDAP user doesn't have the needed %s attribute" % (
                    settings.LDAP_EMAIL_ATTR,))

            username = ldap_user.attrs[settings.LDAP_EMAIL_ATTR][0]

        return_data = {}  # type: Dict[str, Any]
        user_profile = common_get_active_user(username, self._realm, return_data)
        if user_profile is not None:
            # An existing user, successfully authed; return it.
            return user_profile, False

        if return_data.get("inactive_realm"):
            # This happens if there is a user account in a deactivated realm
            raise ZulipLDAPException("Realm has been deactivated")
        if return_data.get("inactive_user"):
            raise ZulipLDAPException("User has been deactivated")
        if return_data.get("invalid_subdomain"):
            # TODO: Implement something in the caller for this to
            # provide a nice user-facing error message for this
            # situation (right now it just acts like any other auth
            # failure).
            raise ZulipLDAPException("Wrong subdomain")
        if self._realm.deactivated:
            # This happens if no account exists, but the realm is
            # deactivated, so we shouldn't create a new user account
            raise ZulipLDAPException("Realm has been deactivated")

        # We have valid LDAP credentials; time to create an account.
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
    def authenticate(self, username: str, password: str, realm: Optional[Realm]=None,
                     return_data: Optional[Dict[str, Any]]=None) -> None:
        return None

class DevAuthBackend(ZulipAuthMixin):
    # Allow logging in as any user without a password.
    # This is used for convenience when developing Zulip.
    def authenticate(self, dev_auth_username: Optional[str]=None, realm: Optional[Realm]=None,
                     return_data: Optional[Dict[str, Any]]=None) -> Optional[UserProfile]:
        assert dev_auth_username is not None
        if realm is None:
            return None
        if not dev_auth_enabled(realm):
            return None
        return common_get_active_user(dev_auth_username, realm, return_data=return_data)

class GitHubAuthBackend(SocialAuthMixin, GithubOAuth2):
    auth_backend_name = "GitHub"

    def get_email_address(self, *args: Any, **kwargs: Any) -> Optional[Text]:
        try:
            return kwargs['response']['email']
        except KeyError:  # nocoverage # TODO: investigate
            return None

    def get_full_name(self, *args: Any, **kwargs: Any) -> Text:
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

    def get_authenticated_user(self, *args: Any, **kwargs: Any) -> Optional[UserProfile]:
        """
        This function is called once the OAuth2 workflow is complete. We
        override this function to call the proper `do_auth` function depending
        on whether we are doing individual, team or organization based GitHub
        authentication. The actual decision on authentication is done in
        SocialAuthMixin._common_authenticate().
        """
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

        return user_profile

AUTH_BACKEND_NAME_MAP = {
    'Dev': DevAuthBackend,
    'Email': EmailAuthBackend,
    'GitHub': GitHubAuthBackend,
    'Google': GoogleMobileOauth2Backend,
    'LDAP': ZulipLDAPAuthBackend,
    'RemoteUser': ZulipRemoteUserBackend,
}  # type: Dict[Text, Any]
