import logging
import mock
from typing import Any, Dict, List, Set, Tuple, Optional, Sequence

from django_auth_ldap.backend import LDAPBackend, _LDAPUser
import django.contrib.auth
from django.contrib.auth.backends import RemoteUserBackend
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.http import HttpResponse
from requests import HTTPError
from social_core.backends.github import GithubOAuth2, GithubOrganizationOAuth2, \
    GithubTeamOAuth2
from social_core.backends.base import BaseAuth
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

def pad_method_dict(method_dict: Dict[str, bool]) -> Dict[str, bool]:
    """Pads an authentication methods dict to contain all auth backends
    supported by the software, regardless of whether they are
    configured on this server"""
    for key in AUTH_BACKEND_NAME_MAP:
        if key not in method_dict:
            method_dict[key] = False
    return method_dict

def auth_enabled_helper(backends_to_check: List[str], realm: Optional[Realm]) -> bool:
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

def generate_dev_ldap_dir(mode: str, num_users: int=8) -> Dict[str, Dict[str, Sequence[str]]]:
    mode = mode.lower()
    names = []
    for i in range(1, num_users+1):
        names.append(('LDAP User %d' % (i,), 'ldapuser%d@zulip.com' % (i,)))

    ldap_dir = {}
    if mode == 'a':
        for name in names:
            email = name[1].lower()
            email_username = email.split('@')[0]
            ldap_dir['uid=' + email + ',ou=users,dc=zulip,dc=com'] = {
                'cn': [name[0], ],
                'userPassword':  email_username,
            }
    elif mode == 'b':
        for name in names:
            email = name[1].lower()
            email_username = email.split('@')[0]
            ldap_dir['uid=' + email_username + ',ou=users,dc=zulip,dc=com'] = {
                'cn': [name[0], ],
                'userPassword': email_username,
            }
    elif mode == 'c':
        for name in names:
            email = name[1].lower()
            email_username = email.split('@')[0]
            ldap_dir['uid=' + email_username + ',ou=users,dc=zulip,dc=com'] = {
                'cn': [name[0], ],
                'userPassword': email_username + '_test',
                'email': email,
            }

    return ldap_dir

class ZulipAuthMixin:
    def get_user(self, user_profile_id: int) -> Optional[UserProfile]:
        """ Get a UserProfile object from the user_profile_id. """
        try:
            return get_user_profile_by_id(user_profile_id)
        except UserProfile.DoesNotExist:
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
        # We lazily import apiclient as part of optimizing the base
        # import time for a Zulip management command, since it's only
        # used in this one code path and takes 30-50ms to import.
        from apiclient.sample_tools import client as googleapiclient
        from oauth2client.crypt import AppIdentityError
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

    def authenticate(self, remote_user: Optional[str], realm: Optional[Realm]=None,
                     return_data: Optional[Dict[str, Any]]=None) -> Optional[UserProfile]:
        assert remote_user is not None
        if realm is None:
            return None
        if not auth_enabled_helper(["RemoteUser"], realm):
            return None

        email = remote_user_to_email(remote_user)
        return common_get_active_user(email, realm, return_data=return_data)

def email_belongs_to_ldap(realm: Realm, email: str) -> bool:
    if not ldap_auth_enabled(realm):
        return False

    # If we don't have an LDAP domain, it's impossible to tell which
    # accounts are LDAP accounts, so treat all of them as LDAP
    # accounts
    if not settings.LDAP_APPEND_DOMAIN:
        return True

    # Otherwise, check if the email ends with LDAP_APPEND_DOMAIN
    return email.strip().lower().endswith("@" + settings.LDAP_APPEND_DOMAIN)

class ZulipLDAPException(_LDAPUser.AuthenticationFailed):
    """Since this inherits from _LDAPUser.AuthenticationFailed, these will
    be caught and logged at debug level inside django-auth-ldap's authenticate()"""
    pass

class ZulipLDAPExceptionOutsideDomain(ZulipLDAPException):
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

    def django_to_ldap_username(self, username: str) -> str:
        if settings.LDAP_APPEND_DOMAIN:
            if not username.endswith("@" + settings.LDAP_APPEND_DOMAIN):
                raise ZulipLDAPExceptionOutsideDomain("Email %s does not match LDAP domain %s." % (
                    username, settings.LDAP_APPEND_DOMAIN))
            return email_to_username(username)
        return username

    def ldap_to_django_username(self, username: str) -> str:
        if settings.LDAP_APPEND_DOMAIN:
            return "@".join((username, settings.LDAP_APPEND_DOMAIN))
        return username

class ZulipLDAPAuthBackend(ZulipLDAPAuthBackendBase):
    REALM_IS_NONE_ERROR = 1

    def __init__(self) -> None:
        if settings.DEVELOPMENT and settings.FAKE_LDAP_MODE:  # nocoverage # We only use this in development
            from fakeldap import MockLDAP

            ldap_patcher = mock.patch('django_auth_ldap.config.ldap.initialize')
            self.mock_initialize = ldap_patcher.start()
            self.mock_ldap = MockLDAP()
            self.mock_initialize.return_value = self.mock_ldap

            self.mock_ldap.directory = generate_dev_ldap_dir(settings.FAKE_LDAP_MODE,
                                                             settings.FAKE_LDAP_NUM_USERS)

    def authenticate(self, username: str, password: str, realm: Optional[Realm]=None,
                     return_data: Optional[Dict[str, Any]]=None) -> Optional[UserProfile]:
        if realm is None:
            return None
        self._realm = realm
        if not ldap_auth_enabled(realm):
            return None

        try:
            username = self.django_to_ldap_username(username)
        except ZulipLDAPExceptionOutsideDomain:
            return_data['outside_ldap_domain'] = True
            return None

        return ZulipLDAPAuthBackendBase.authenticate(self,
                                                     request=None,
                                                     username=username,
                                                     password=password)

    def get_or_build_user(self, username: str, ldap_user: _LDAPUser) -> Tuple[UserProfile, bool]:
        return_data = {}  # type: Dict[str, Any]

        if settings.LDAP_EMAIL_ATTR is not None:
            # Get email from ldap attributes.
            if settings.LDAP_EMAIL_ATTR not in ldap_user.attrs:
                return_data["ldap_missing_attribute"] = settings.LDAP_EMAIL_ATTR
                raise ZulipLDAPException("LDAP user doesn't have the needed %s attribute" % (
                    settings.LDAP_EMAIL_ATTR,))

            username = ldap_user.attrs[settings.LDAP_EMAIL_ATTR][0]

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

def social_associate_user_helper(backend: BaseAuth, return_data: Dict[str, Any],
                                 *args: Any, **kwargs: Any) -> Optional[UserProfile]:
    """Responsible for doing the Zulip-account lookup and validation parts
    of the Zulip Social auth pipeline (similar to the authenticate()
    methods in most other auth backends in this file).
    """
    subdomain = backend.strategy.session_get('subdomain')
    realm = get_realm(subdomain)
    if realm is None:
        return_data["invalid_realm"] = True
        return None
    return_data["realm"] = realm

    if not auth_enabled_helper([backend.auth_backend_name], realm):
        return_data["auth_backend_disabled"] = True
        return None

    if 'auth_failed_reason' in kwargs.get('response', {}):
        return_data["social_auth_failed_reason"] = kwargs['response']["auth_failed_reason"]
        return None
    elif hasattr(backend, 'get_verified_emails'):
        # Some social backends, like GitHubAuthBackend, don't guarantee that
        # the `details` data is validated.
        verified_emails = backend.get_verified_emails(*args, **kwargs)
        if len(verified_emails) == 0:
            # TODO: Provide a nice error message screen to the user
            # for this case, rather than just logging a warning.
            logging.warning("Social auth (%s) failed because user has no verified emails" %
                            (backend.auth_backend_name,))
            return_data["email_not_verified"] = True
            return None
        # TODO: ideally, we'd prompt the user for which email they
        # want to use with another pipeline stage here.
        validated_email = verified_emails[0]
    else:  # nocoverage
        # This code path isn't used by GitHubAuthBackend
        validated_email = kwargs["details"].get("email")

    if not validated_email:  # nocoverage
        # This code path isn't used with GitHubAuthBackend, but may be relevant for other
        # social auth backends.
        return_data['invalid_email'] = True
        return None
    try:
        validate_email(validated_email)
    except ValidationError:
        return_data['invalid_email'] = True
        return None

    return_data["valid_attestation"] = True
    return_data['validated_email'] = validated_email
    user_profile = common_get_active_user(validated_email, realm, return_data)

    if 'fullname' in kwargs["details"]:
        return_data["full_name"] = kwargs["details"]["fullname"]
    else:
        # If we add support for any of the social auth backends that
        # don't provide this feature, we'll need to add code here.
        raise AssertionError("Social auth backend doesn't provide fullname")

    return user_profile

def social_auth_associate_user(
        backend: BaseAuth,
        *args: Any,
        **kwargs: Any) -> Dict[str, Any]:
    return_data = {}  # type: Dict[str, Any]
    user_profile = social_associate_user_helper(
        backend, return_data, *args, **kwargs)

    return {'user_profile': user_profile,
            'return_data': return_data}

def social_auth_finish(backend: Any,
                       details: Dict[str, Any],
                       response: HttpResponse,
                       *args: Any,
                       **kwargs: Any) -> Optional[UserProfile]:
    from zerver.views.auth import (login_or_register_remote_user,
                                   redirect_and_log_into_subdomain)

    user_profile = kwargs['user_profile']
    return_data = kwargs['return_data']

    no_verified_email = return_data.get("email_not_verified")
    auth_backend_disabled = return_data.get('auth_backend_disabled')
    inactive_user = return_data.get('inactive_user')
    inactive_realm = return_data.get('inactive_realm')
    invalid_realm = return_data.get('invalid_realm')
    invalid_subdomain = return_data.get('invalid_subdomain')
    invalid_email = return_data.get('invalid_email')
    auth_failed_reason = return_data.get("social_auth_failed_reason")

    if invalid_realm:
        from zerver.views.auth import redirect_to_subdomain_login_url
        return redirect_to_subdomain_login_url()
    if auth_backend_disabled or inactive_user or inactive_realm or no_verified_email:
        # Redirect to login page. We can't send to registration
        # workflow with these errors. We will redirect to login page.
        return None

    if invalid_email:
        # In case of invalid email, we will end up on registration page.
        # This seems better than redirecting to login page.
        logging.warning(
            "{} got invalid email argument.".format(backend.auth_backend_name)
        )
        return None

    if auth_failed_reason:
        logging.info(auth_failed_reason)
        return None

    # Structurally, all the cases where we don't have an authenticated
    # email for the user should be handled above; this assertion helps
    # prevent any violations of that contract from resulting in a user
    # being incorrectly authenticated.
    assert return_data.get('valid_attestation') is True

    strategy = backend.strategy  # type: ignore # This comes from Python Social Auth.
    email_address = return_data['validated_email']
    full_name = return_data['full_name']
    is_signup = strategy.session_get('is_signup') == '1'
    redirect_to = strategy.session_get('next')
    realm = return_data["realm"]

    mobile_flow_otp = strategy.session_get('mobile_flow_otp')
    if mobile_flow_otp is not None:
        return login_or_register_remote_user(strategy.request, email_address,
                                             user_profile, full_name,
                                             invalid_subdomain=bool(invalid_subdomain),
                                             mobile_flow_otp=mobile_flow_otp,
                                             is_signup=is_signup,
                                             redirect_to=redirect_to)
    return redirect_and_log_into_subdomain(realm, full_name, email_address,
                                           is_signup=is_signup,
                                           redirect_to=redirect_to)

class SocialAuthMixin(ZulipAuthMixin):
    def auth_complete(self, *args: Any, **kwargs: Any) -> Optional[HttpResponse]:
        """This is a small wrapper around the core `auth_complete` method of
        python-social-auth, designed primarily to prevent 500s for
        exceptions in the social auth code from situations that are
        really user errors.  Returning `None` from this function will
        redirect the browser to the login page.
        """
        try:
            # Call the auth_complete method of social_core.backends.oauth.BaseOAuth2
            return super().auth_complete(*args, **kwargs)  # type: ignore # monkey-patching
        except AuthFailed as e:
            # When a user's social authentication fails (e.g. because
            # they did something funny with reloading in the middle of
            # the flow), don't throw a 500, just send them back to the
            # login page and record the event at the info log level.
            logging.info(str(e))
            return None
        except SocialAuthBaseException as e:
            # Other python-social-auth exceptions are likely
            # interesting enough that we should log a warning.
            logging.warning(str(e))
            return None

class GitHubAuthBackend(SocialAuthMixin, GithubOAuth2):
    auth_backend_name = "GitHub"

    def get_verified_emails(self, *args: Any, **kwargs: Any) -> List[str]:
        access_token = kwargs["response"]["access_token"]
        try:
            emails = self._user_data(access_token, '/emails')
        except (HTTPError, ValueError, TypeError):  # nocoverage
            # We don't really need an explicit test for this code
            # path, since the outcome will be the same as any other
            # case without any verified emails
            emails = []

        verified_emails = []
        for email_obj in emails:
            if not email_obj.get("verified"):
                continue
            # TODO: When we add a screen to let the user select an email, remove this line.
            if not email_obj.get("primary"):
                continue
            verified_emails.append(email_obj["email"])

        return verified_emails

    def user_data(self, access_token: str, *args: Any, **kwargs: Any) -> Dict[str, str]:
        """This patched user_data function lets us combine together the 3
        social auth backends into a single Zulip backend for GitHub Oauth2"""
        team_id = settings.SOCIAL_AUTH_GITHUB_TEAM_ID
        org_name = settings.SOCIAL_AUTH_GITHUB_ORG_NAME

        if team_id is None and org_name is None:
            # I believe this can't raise AuthFailed, so we don't try to catch it here.
            return super().user_data(
                access_token, *args, **kwargs
            )
        elif team_id is not None:
            backend = GithubTeamOAuth2(self.strategy, self.redirect_uri)
            try:
                return backend.user_data(access_token, *args, **kwargs)
            except AuthFailed:
                return dict(auth_failed_reason="GitHub user is not member of required team")
        elif org_name is not None:
            backend = GithubOrganizationOAuth2(self.strategy, self.redirect_uri)
            try:
                return backend.user_data(access_token, *args, **kwargs)
            except AuthFailed:
                return dict(auth_failed_reason="GitHub user is not member of required organization")

        raise AssertionError("Invalid configuration")

AUTH_BACKEND_NAME_MAP = {
    'Dev': DevAuthBackend,
    'Email': EmailAuthBackend,
    'GitHub': GitHubAuthBackend,
    'Google': GoogleMobileOauth2Backend,
    'LDAP': ZulipLDAPAuthBackend,
    'RemoteUser': ZulipRemoteUserBackend,
}  # type: Dict[str, Any]
