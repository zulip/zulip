# Documentation for Zulip's authentication backends is split across a few places:
#
# * https://zulip.readthedocs.io/en/latest/production/authentication-methods.html and
#   zproject/prod_settings_template.py have user-level configuration documentation.
# * https://zulip.readthedocs.io/en/latest/subsystems/auth.html has developer-level
#   documentation, especially on testing authentication backends in the Zulip
#   development environment.
#
# Django upstream's documentation for authentication backends is also
# helpful background.  The most important detail to understand for
# reading this file is that the Django authenticate() function will
# call the authenticate methods of all backends registered in
# settings.AUTHENTICATION_BACKENDS that have a function signature
# matching the args/kwargs passed in the authenticate() call.
import copy
import logging
import magic
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from django_auth_ldap.backend import LDAPBackend, _LDAPUser
from django.contrib.auth import get_backends
from django.contrib.auth.backends import RemoteUserBackend
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from requests import HTTPError
from social_core.backends.github import GithubOAuth2, GithubOrganizationOAuth2, \
    GithubTeamOAuth2
from social_core.backends.azuread import AzureADOAuth2
from social_core.backends.base import BaseAuth
from social_core.backends.google import GoogleOAuth2
from social_core.backends.oauth import BaseOAuth2
from social_core.pipeline.partial import partial
from social_core.exceptions import AuthFailed, SocialAuthBaseException

from zerver.lib.actions import do_create_user, do_reactivate_user, do_deactivate_user, \
    do_update_user_custom_profile_data, validate_email_for_realm
from zerver.lib.avatar import is_avatar_new, avatar_url
from zerver.lib.avatar_hash import user_avatar_content_hash
from zerver.lib.dev_ldap_directory import init_fakeldap
from zerver.lib.request import JsonableError
from zerver.lib.users import check_full_name, validate_user_custom_profile_field
from zerver.models import CustomProfileField, DisposableEmailError, DomainNotAllowedForRealmError, \
    EmailContainsPlusError, PreregistrationUser, UserProfile, Realm, custom_profile_fields_for_realm, \
    email_allowed_for_realm, get_default_stream_groups, get_user_profile_by_id, remote_user_to_email, \
    email_to_username, get_realm, get_user_by_delivery_email, supported_auth_backends

# This first batch of methods is used by other code in Zulip to check
# whether a given authentication backend is enabled for a given realm.
# In each case, we both needs to check at the server level (via
# `settings.AUTHENTICATION_BACKENDS`, queried via
# `django.contrib.auth.get_backends`) and at the realm level (via the
# `Realm.authentication_methods` BitField).
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
    for supported_backend in supported_auth_backends():
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

def any_oauth_backend_enabled(realm: Optional[Realm]=None) -> bool:
    """Used by the login page process to determine whether to show the
    'OR' for login with Google"""
    return auth_enabled_helper(OAUTH_BACKEND_NAMES, realm)

def require_email_format_usernames(realm: Optional[Realm]=None) -> bool:
    if ldap_auth_enabled(realm):
        if settings.LDAP_EMAIL_ATTR or settings.LDAP_APPEND_DOMAIN:
            return False
    return True

def common_get_active_user(email: str, realm: Realm,
                           return_data: Optional[Dict[str, Any]]=None) -> Optional[UserProfile]:
    """This is the core common function used by essentially all
    authentication backends to check if there's an active user account
    with a given email address in the organization, handling both
    user-level and realm-level deactivation correctly.
    """
    try:
        user_profile = get_user_by_delivery_email(email, realm)
    except UserProfile.DoesNotExist:
        # If the user doesn't have an account in the target realm, we
        # check whether they might have an account in another realm,
        # and if so, provide a helpful error message via
        # `invalid_subdomain`.
        if not UserProfile.objects.filter(delivery_email__iexact=email).exists():
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
    """This common mixin is used to override Django's default behavior for
    looking up a logged-in user by ID to use a version that fetches
    from memcached before checking the database (avoiding a database
    query in most cases).
    """
    def get_user(self, user_profile_id: int) -> Optional[UserProfile]:
        """Override the Django method for getting a UserProfile object from
        the user_profile_id,."""
        try:
            return get_user_profile_by_id(user_profile_id)
        except UserProfile.DoesNotExist:
            return None

class ZulipDummyBackend(ZulipAuthMixin):
    """Used when we want to log you in without checking any
    authentication (i.e. new user registration or when otherwise
    authentication has already been checked earlier in the process).

    We ensure that this backend only ever successfully authenticates
    when explicitly requested by including the use_dummy_backend kwarg.
    """

    def authenticate(self, *, username: str, realm: Realm,
                     use_dummy_backend: bool=False,
                     return_data: Optional[Dict[str, Any]]=None) -> Optional[UserProfile]:
        if use_dummy_backend:
            return common_get_active_user(username, realm, return_data)
        return None

class EmailAuthBackend(ZulipAuthMixin):
    """
    Email+Password Authentication Backend (the default).

    Allows a user to sign in using an email/password pair.
    """

    def authenticate(self, *, username: str, password: str,
                     realm: Realm,
                     return_data: Optional[Dict[str, Any]]=None) -> Optional[UserProfile]:
        """ Authenticate a user based on email address as the user name. """
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

class ZulipRemoteUserBackend(RemoteUserBackend):
    """Authentication backend that reads the Apache REMOTE_USER variable.
    Used primarily in enterprise environments with an SSO solution
    that has an Apache REMOTE_USER integration.  For manual testing, see

      https://zulip.readthedocs.io/en/latest/production/authentication-methods.html

    See also remote_user_sso in zerver/views/auth.py.
    """
    create_unknown_user = False

    def authenticate(self, *, remote_user: str, realm: Realm,
                     return_data: Optional[Dict[str, Any]]=None) -> Optional[UserProfile]:
        if not auth_enabled_helper(["RemoteUser"], realm):
            return None

        email = remote_user_to_email(remote_user)
        return common_get_active_user(email, realm, return_data=return_data)

def is_valid_email(email: str) -> bool:
    try:
        validate_email(email)
    except ValidationError:
        return False
    return True

def email_belongs_to_ldap(realm: Realm, email: str) -> bool:
    """Used to make determinations on whether a user's email address is
    managed by LDAP.  For environments using both LDAP and
    Email+Password authentication, we do not allow EmailAuthBackend
    authentication for email addresses managed by LDAP (to avoid a
    security issue where one create separate credentials for an LDAP
    user), and this function is used to enforce that rule.
    """
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

LDAP_USER_ACCOUNT_CONTROL_DISABLED_MASK = 2

class ZulipLDAPAuthBackendBase(ZulipAuthMixin, LDAPBackend):
    """Common code between LDAP authentication (ZulipLDAPAuthBackend) and
    using LDAP just to sync user data (ZulipLDAPUserPopulator).

    To fully understand our LDAP backend, you may want to skim
    django_auth_ldap/backend.py from the upstream django-auth-ldap
    library.  It's not a lot of code, and searching around in that
    file makes the flow for LDAP authentication clear.
    """
    def __init__(self) -> None:
        # Used to initialize a fake LDAP directly for both manual
        # and automated testing in a development environment where
        # there is no actual LDAP server.
        if settings.DEVELOPMENT and settings.FAKE_LDAP_MODE:  # nocoverage
            init_fakeldap()

    # Disable django-auth-ldap's permissions functions -- we don't use
    # the standard Django user/group permissions system because they
    # are prone to performance issues.
    def has_perm(self, user: Optional[UserProfile], perm: Any, obj: Any=None) -> bool:
        return False

    def has_module_perms(self, user: Optional[UserProfile], app_label: Optional[str]) -> bool:
        return False

    def get_all_permissions(self, user: Optional[UserProfile], obj: Any=None) -> Set[Any]:
        return set()

    def get_group_permissions(self, user: Optional[UserProfile], obj: Any=None) -> Set[Any]:
        return set()

    def django_to_ldap_username(self, username: str) -> str:
        if settings.LDAP_APPEND_DOMAIN:
            if is_valid_email(username):
                if not username.endswith("@" + settings.LDAP_APPEND_DOMAIN):
                    raise ZulipLDAPExceptionOutsideDomain("Email %s does not match LDAP domain %s." % (
                        username, settings.LDAP_APPEND_DOMAIN))
                return email_to_username(username)
        return username

    def ldap_to_django_username(self, username: str) -> str:
        if settings.LDAP_APPEND_DOMAIN:
            return "@".join((username, settings.LDAP_APPEND_DOMAIN))
        return username

    def sync_avatar_from_ldap(self, user: UserProfile, ldap_user: _LDAPUser) -> None:
        if 'avatar' in settings.AUTH_LDAP_USER_ATTR_MAP:
            # We do local imports here to avoid import loops
            from zerver.lib.upload import upload_avatar_image
            from zerver.lib.actions import do_change_avatar_fields
            from io import BytesIO

            avatar_attr_name = settings.AUTH_LDAP_USER_ATTR_MAP['avatar']
            if avatar_attr_name not in ldap_user.attrs:  # nocoverage
                # If this specific user doesn't have e.g. a
                # thumbnailPhoto set in LDAP, just skip that user.
                return

            ldap_avatar = ldap_user.attrs[avatar_attr_name][0]

            avatar_changed = is_avatar_new(ldap_avatar, user)
            if not avatar_changed:
                # Don't do work to replace the avatar with itself.
                return

            io = BytesIO(ldap_avatar)
            # Structurally, to make the S3 backend happy, we need to
            # provide a Content-Type; since that isn't specified in
            # any metadata, we auto-detect it.
            content_type = magic.from_buffer(copy.deepcopy(io).read()[0:1024], mime=True)
            if content_type.startswith("image/"):
                upload_avatar_image(io, user, user, content_type=content_type)
                do_change_avatar_fields(user, UserProfile.AVATAR_FROM_USER)
                # Update avatar hash.
                user.avatar_hash = user_avatar_content_hash(ldap_avatar)
                user.save(update_fields=["avatar_hash"])
            else:
                logging.warning("Could not parse %s field for user %s" %
                                (avatar_attr_name, user.id))

    def is_account_control_disabled_user(self, ldap_user: _LDAPUser) -> bool:
        """Implements the userAccountControl check for whether a user has been
        disabled in an Active Directory server being integrated with
        Zulip via LDAP."""
        account_control_value = ldap_user.attrs[settings.AUTH_LDAP_USER_ATTR_MAP['userAccountControl']][0]
        ldap_disabled = bool(int(account_control_value) & LDAP_USER_ACCOUNT_CONTROL_DISABLED_MASK)
        return ldap_disabled

    @classmethod
    def get_mapped_name(cls, ldap_user: _LDAPUser) -> Tuple[str, str]:
        """Constructs the user's Zulip full_name and short_name fields from
        the LDAP data"""
        if "full_name" in settings.AUTH_LDAP_USER_ATTR_MAP:
            full_name_attr = settings.AUTH_LDAP_USER_ATTR_MAP["full_name"]
            short_name = full_name = ldap_user.attrs[full_name_attr][0]
        elif all(key in settings.AUTH_LDAP_USER_ATTR_MAP for key in {"first_name", "last_name"}):
            first_name_attr = settings.AUTH_LDAP_USER_ATTR_MAP["first_name"]
            last_name_attr = settings.AUTH_LDAP_USER_ATTR_MAP["last_name"]
            short_name = ldap_user.attrs[first_name_attr][0]
            full_name = short_name + ' ' + ldap_user.attrs[last_name_attr][0]
        else:
            raise ZulipLDAPException("Missing required mapping for user's full name")

        if "short_name" in settings.AUTH_LDAP_USER_ATTR_MAP:
            short_name_attr = settings.AUTH_LDAP_USER_ATTR_MAP["short_name"]
            short_name = ldap_user.attrs[short_name_attr][0]

        return full_name, short_name

    def sync_full_name_from_ldap(self, user_profile: UserProfile,
                                 ldap_user: _LDAPUser) -> None:
        from zerver.lib.actions import do_change_full_name
        full_name, _ = self.get_mapped_name(ldap_user)
        if full_name != user_profile.full_name:
            try:
                full_name = check_full_name(full_name)
            except JsonableError as e:
                raise ZulipLDAPException(e.msg)
            do_change_full_name(user_profile, full_name, None)

    def sync_custom_profile_fields_from_ldap(self, user_profile: UserProfile,
                                             ldap_user: _LDAPUser) -> None:
        values_by_var_name = {}   # type: Dict[str, Union[int, str, List[int]]]
        for attr, ldap_attr in settings.AUTH_LDAP_USER_ATTR_MAP.items():
            if not attr.startswith('custom_profile_field__'):
                continue
            var_name = attr.split('custom_profile_field__')[1]
            try:
                value = ldap_user.attrs[ldap_attr][0]
            except KeyError:
                # If this user doesn't have this field set then ignore this
                # field and continue syncing other fields. `django-auth-ldap`
                # automatically logs error about missing field.
                continue
            values_by_var_name[var_name] = value

        fields_by_var_name = {}   # type: Dict[str, CustomProfileField]
        custom_profile_fields = custom_profile_fields_for_realm(user_profile.realm.id)
        for field in custom_profile_fields:
            var_name = '_'.join(field.name.lower().split(' '))
            fields_by_var_name[var_name] = field

        existing_values = {}
        for data in user_profile.profile_data:
            var_name = '_'.join(data['name'].lower().split(' '))
            existing_values[var_name] = data['value']

        profile_data = []   # type: List[Dict[str, Union[int, str, List[int]]]]
        for var_name, value in values_by_var_name.items():
            try:
                field = fields_by_var_name[var_name]
            except KeyError:
                raise ZulipLDAPException('Custom profile field with name %s not found.' % (var_name,))
            if existing_values.get(var_name) == value:
                continue
            result = validate_user_custom_profile_field(user_profile.realm.id, field, value)
            if result is not None:
                raise ZulipLDAPException('Invalid data for %s field: %s' % (var_name, result))
            profile_data.append({
                'id': field.id,
                'value': value,
            })
        do_update_user_custom_profile_data(user_profile, profile_data)

    def get_or_build_user(self, username: str,
                          ldap_user: _LDAPUser) -> Tuple[UserProfile, bool]:
        """This is used only in non-authentication contexts such as:
             ./manage.py sync_ldap_user_data
           In authentication contexts, this is overriden in ZulipLDAPAuthBackend.
        """
        (user, built) = super().get_or_build_user(username, ldap_user)
        self.sync_avatar_from_ldap(user, ldap_user)
        self.sync_full_name_from_ldap(user, ldap_user)
        self.sync_custom_profile_fields_from_ldap(user, ldap_user)
        if 'userAccountControl' in settings.AUTH_LDAP_USER_ATTR_MAP:
            user_disabled_in_ldap = self.is_account_control_disabled_user(ldap_user)
            if user_disabled_in_ldap and user.is_active:
                logging.info("Deactivating user %s because they are disabled in LDAP." %
                             (user.email,))
                do_deactivate_user(user)
                return (user, built)
            if not user_disabled_in_ldap and not user.is_active:
                logging.info("Reactivating user %s because they are not disabled in LDAP." %
                             (user.email,))
                do_reactivate_user(user)
        return (user, built)

class ZulipLDAPAuthBackend(ZulipLDAPAuthBackendBase):
    REALM_IS_NONE_ERROR = 1

    def authenticate(self, *, username: str, password: str, realm: Realm,
                     prereg_user: Optional[PreregistrationUser]=None,
                     return_data: Optional[Dict[str, Any]]=None) -> Optional[UserProfile]:
        self._realm = realm
        self._prereg_user = prereg_user
        if not ldap_auth_enabled(realm):
            return None

        try:
            username = self.django_to_ldap_username(username)
        except ZulipLDAPExceptionOutsideDomain:
            if return_data is not None:
                return_data['outside_ldap_domain'] = True
            return None

        # Call into (ultimately) the django-auth-ldap authenticate
        # function.  This will check the username/password pair
        # against the LDAP database, and assuming those are correct,
        # end up calling `self.get_or_build_user` with the
        # authenticated user's data from LDAP.
        return ZulipLDAPAuthBackendBase.authenticate(self,
                                                     request=None,
                                                     username=username,
                                                     password=password)

    def get_or_build_user(self, username: str, ldap_user: _LDAPUser) -> Tuple[UserProfile, bool]:
        """The main function of our authentication backend extension of
        django-auth-ldap.  When this is called (from `authenticate`),
        django-auth-ldap will already have verified that the provided
        username and password match those in the LDAP database.

        This function's responsibility is to check (1) whether the
        email address for this user obtained from LDAP has an active
        account in this Zulip realm.  If so, it will log them in.

        Otherwise, to provide a seamless Single Sign-On experience
        with LDAP, this function can automatically create a new Zulip
        user account in the realm (assuming the realm is configured to
        allow that email address to sign up).
        """
        return_data = {}  # type: Dict[str, Any]

        if settings.LDAP_EMAIL_ATTR is not None:
            # Get email from ldap attributes.
            if settings.LDAP_EMAIL_ATTR not in ldap_user.attrs:
                return_data["ldap_missing_attribute"] = settings.LDAP_EMAIL_ATTR
                raise ZulipLDAPException("LDAP user doesn't have the needed %s attribute" % (
                    settings.LDAP_EMAIL_ATTR,))

            username = ldap_user.attrs[settings.LDAP_EMAIL_ATTR][0]

        if 'userAccountControl' in settings.AUTH_LDAP_USER_ATTR_MAP:  # nocoverage
            ldap_disabled = self.is_account_control_disabled_user(ldap_user)
            if ldap_disabled:
                # Treat disabled users as deactivated in Zulip.
                return_data["inactive_user"] = True
                raise ZulipLDAPException("User has been deactivated")

        user_profile = common_get_active_user(username, self._realm, return_data)
        if user_profile is not None:
            # An existing user, successfully authed; return it.
            return user_profile, False

        if return_data.get("inactive_realm"):
            # This happens if there is a user account in a deactivated realm
            raise ZulipLDAPException("Realm has been deactivated")
        if return_data.get("inactive_user"):
            raise ZulipLDAPException("User has been deactivated")
        # An invalid_subdomain `return_data` value here is ignored,
        # since that just means we're trying to create an account in a
        # second realm on the server (`ldap_auth_enabled(realm)` would
        # have been false if this user wasn't meant to have an account
        # in this second realm).
        if self._realm.deactivated:
            # This happens if no account exists, but the realm is
            # deactivated, so we shouldn't create a new user account
            raise ZulipLDAPException("Realm has been deactivated")

        # Makes sure that email domain hasn't be restricted for this
        # realm.  The main thing here is email_allowed_for_realm; but
        # we also call validate_email_for_realm just for consistency,
        # even though its checks were already done above.
        try:
            email_allowed_for_realm(username, self._realm)
            validate_email_for_realm(self._realm, username)
        except DomainNotAllowedForRealmError:
            raise ZulipLDAPException("This email domain isn't allowed in this organization.")
        except (DisposableEmailError, EmailContainsPlusError):
            raise ZulipLDAPException("Email validation failed.")

        # We have valid LDAP credentials; time to create an account.
        full_name, short_name = self.get_mapped_name(ldap_user)
        try:
            full_name = check_full_name(full_name)
        except JsonableError as e:
            raise ZulipLDAPException(e.msg)

        opts = {}   # type: Dict[str, Any]
        if self._prereg_user:
            invited_as = self._prereg_user.invited_as
            opts['prereg_user'] = self._prereg_user
            opts['is_realm_admin'] = invited_as == PreregistrationUser.INVITE_AS['REALM_ADMIN']
            opts['is_guest'] = invited_as == PreregistrationUser.INVITE_AS['GUEST_USER']
            opts['default_stream_groups'] = get_default_stream_groups(self._realm)

        user_profile = do_create_user(username, None, self._realm, full_name, short_name, **opts)
        self.sync_avatar_from_ldap(user_profile, ldap_user)
        self.sync_custom_profile_fields_from_ldap(user_profile, ldap_user)

        return user_profile, True

class ZulipLDAPUserPopulator(ZulipLDAPAuthBackendBase):
    """Just like ZulipLDAPAuthBackend, but doesn't let you log in.  Used
    for syncing data like names, avatars, and custom profile fields
    from LDAP in `manage.py sync_ldap_user_data` as well as in
    registration for organizations that use a different SSO solution
    for managing login (often via RemoteUserBackend).
    """
    def authenticate(self, *, username: str, password: str, realm: Realm,
                     return_data: Optional[Dict[str, Any]]=None) -> Optional[UserProfile]:
        return None

def sync_user_from_ldap(user_profile: UserProfile) -> bool:
    backend = ZulipLDAPUserPopulator()
    updated_user = backend.populate_user(backend.django_to_ldap_username(user_profile.email))
    if not updated_user:
        if settings.LDAP_DEACTIVATE_NON_MATCHING_USERS:
            do_deactivate_user(user_profile)
        return False
    return True

# Quick tool to test whether you're correctly authenticating to LDAP
def query_ldap(email: str) -> List[str]:
    values = []
    backend = next((backend for backend in get_backends() if isinstance(backend, LDAPBackend)), None)
    if backend is not None:
        ldap_attrs = _LDAPUser(backend, backend.django_to_ldap_username(email)).attrs
        if ldap_attrs is None:
            values.append("No such user found")
        else:
            for django_field, ldap_field in settings.AUTH_LDAP_USER_ATTR_MAP.items():
                value = ldap_attrs.get(ldap_field, ["LDAP field not present", ])[0]
                if django_field == "avatar":
                    if isinstance(value, bytes):
                        value = "(An avatar image file)"
                values.append("%s: %s" % (django_field, value))
            if settings.LDAP_EMAIL_ATTR is not None:
                values.append("%s: %s" % ('email', ldap_attrs[settings.LDAP_EMAIL_ATTR][0]))
    else:
        values.append("LDAP backend not configured on this server.")
    return values

class DevAuthBackend(ZulipAuthMixin):
    """Allow logging in as any user without a password.  This is used for
    convenience when developing Zulip, and is disabled in production."""
    def authenticate(self, *, dev_auth_username: str, realm: Realm,
                     return_data: Optional[Dict[str, Any]]=None) -> Optional[UserProfile]:
        if not dev_auth_enabled(realm):
            return None
        return common_get_active_user(dev_auth_username, realm, return_data=return_data)

def redirect_deactivated_user_to_login() -> HttpResponseRedirect:
    # Specifying the template name makes sure that the user is not redirected to dev_login in case of
    # a deactivated account on a test server.
    login_url = reverse('zerver.views.auth.login_page', kwargs = {'template_name': 'zerver/login.html'})
    redirect_url = login_url + '?is_deactivated=true'
    return HttpResponseRedirect(redirect_url)

def social_associate_user_helper(backend: BaseAuth, return_data: Dict[str, Any],
                                 *args: Any, **kwargs: Any) -> Optional[UserProfile]:
    """Responsible for doing the Zulip-account lookup and validation parts
    of the Zulip Social auth pipeline (similar to the authenticate()
    methods in most other auth backends in this file).

    Returns a UserProfile object for successful authentication, and None otherwise.
    """
    subdomain = backend.strategy.session_get('subdomain')
    try:
        realm = get_realm(subdomain)
    except Realm.DoesNotExist:
        return_data["invalid_realm"] = True
        return None
    return_data["realm_id"] = realm.id

    if not auth_enabled_helper([backend.auth_backend_name], realm):
        return_data["auth_backend_disabled"] = True
        return None

    if 'auth_failed_reason' in kwargs.get('response', {}):
        return_data["social_auth_failed_reason"] = kwargs['response']["auth_failed_reason"]
        return None
    elif hasattr(backend, 'get_verified_emails'):
        # Some social backends, like GitHubAuthBackend, don't
        # guarantee that the `details` data is validated (i.e., it's
        # possible users can put any string they want in the "email"
        # field of the `details` object).  For those backends, we have
        # custom per-backend code to properly fetch only verified
        # email addresses from the appropriate third-party API.
        verified_emails = backend.get_verified_emails(*args, **kwargs)
        verified_emails_length = len(verified_emails)
        if verified_emails_length == 0:
            # TODO: Provide a nice error message screen to the user
            # for this case, rather than just logging a warning.
            logging.warning("Social auth (%s) failed because user has no verified emails" %
                            (backend.auth_backend_name,))
            return_data["email_not_verified"] = True
            return None

        if verified_emails_length == 1:
            chosen_email = verified_emails[0]
        else:
            chosen_email = backend.strategy.request_data().get('email')

        if not chosen_email:
            avatars = {}  # Dict[str, str]
            for email in verified_emails:
                existing_account = common_get_active_user(email, realm, {})
                if existing_account is not None:
                    avatars[email] = avatar_url(existing_account)

            return render(backend.strategy.request, 'zerver/social_auth_select_email.html', context = {
                'primary_email': verified_emails[0],
                'verified_non_primary_emails': verified_emails[1:],
                'backend': 'github',
                'avatar_urls': avatars,
            })

        try:
            validate_email(chosen_email)
        except ValidationError:
            return_data['invalid_email'] = True
            return None

        if chosen_email not in verified_emails:
            # If a user edits the submit value for the choose email form, we might
            # end up with a wrong email associated with the account. The below code
            # takes care of that.
            logging.warning("Social auth (%s) failed because user has no verified"
                            " emails associated with the account" %
                            (backend.auth_backend_name,))
            return_data["email_not_associated"] = True
            return None

        validated_email = chosen_email
    else:  # nocoverage
        # This code path isn't used by GitHubAuthBackend
        validated_email = kwargs["details"].get("email")

    if not validated_email:  # nocoverage
        # This code path isn't used with GitHubAuthBackend, but may be relevant for other
        # social auth backends.
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

@partial
def social_auth_associate_user(
        backend: BaseAuth,
        *args: Any,
        **kwargs: Any) -> Union[HttpResponse, Dict[str, Any]]:
    """A simple wrapper function to reformat the return data from
    social_associate_user_helper as a dictionary.  The
    python-social-auth infrastructure will then pass those values into
    later stages of settings.SOCIAL_AUTH_PIPELINE, such as
    social_auth_finish, as kwargs.
    """
    partial_token = backend.strategy.request_data().get('partial_token')
    return_data = {}  # type: Dict[str, Any]
    user_profile = social_associate_user_helper(
        backend, return_data, *args, **kwargs)

    if type(user_profile) == HttpResponse:
        return user_profile
    else:
        return {'user_profile': user_profile,
                'return_data': return_data,
                'partial_token': partial_token,
                'partial_backend_name': backend}

def social_auth_finish(backend: Any,
                       details: Dict[str, Any],
                       response: HttpResponse,
                       *args: Any,
                       **kwargs: Any) -> Optional[UserProfile]:
    """Given the determination in social_auth_associate_user for whether
    the user should be authenticated, this takes care of actually
    logging in the user (if appropriate) and redirecting the browser
    to the appropriate next page depending on the situation.  Read the
    comments below as well as login_or_register_remote_user in
    `zerver/views/auth.py` for the details on how that dispatch works.
    """
    from zerver.views.auth import (login_or_register_remote_user,
                                   redirect_and_log_into_subdomain)

    user_profile = kwargs['user_profile']
    return_data = kwargs['return_data']

    no_verified_email = return_data.get("email_not_verified")
    auth_backend_disabled = return_data.get('auth_backend_disabled')
    inactive_user = return_data.get('inactive_user')
    inactive_realm = return_data.get('inactive_realm')
    invalid_realm = return_data.get('invalid_realm')
    invalid_email = return_data.get('invalid_email')
    auth_failed_reason = return_data.get("social_auth_failed_reason")
    email_not_associated = return_data.get("email_not_associated")

    if invalid_realm:
        from zerver.views.auth import redirect_to_subdomain_login_url
        return redirect_to_subdomain_login_url()

    if inactive_user:
        return redirect_deactivated_user_to_login()

    if auth_backend_disabled or inactive_realm or no_verified_email or email_not_associated:
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

    strategy = backend.strategy
    email_address = return_data['validated_email']
    full_name = return_data['full_name']
    is_signup = strategy.session_get('is_signup') == '1'
    redirect_to = strategy.session_get('next')
    realm = Realm.objects.get(id=return_data["realm_id"])
    multiuse_object_key = strategy.session_get('multiuse_object_key', '')
    mobile_flow_otp = strategy.session_get('mobile_flow_otp')

    # At this point, we have now confirmed that the user has
    # demonstrated control over the target email address.
    #
    # The next step is to call login_or_register_remote_user, but
    # there are two code paths here because of an optimization to save
    # a redirect on mobile.

    if mobile_flow_otp is not None:
        # For mobile app authentication, login_or_register_remote_user
        # will redirect to a special zulip:// URL that is handled by
        # the app after a successful authentication; so we can
        # redirect directly from here, saving a round trip over what
        # we need to do to create session cookies on the right domain
        # in the web login flow (below).
        return login_or_register_remote_user(strategy.request, email_address,
                                             user_profile, full_name,
                                             mobile_flow_otp=mobile_flow_otp,
                                             is_signup=is_signup,
                                             redirect_to=redirect_to)

    # If this authentication code were executing on
    # subdomain.zulip.example.com, we would just call
    # login_or_register_remote_user as in the mobile code path.
    # However, because third-party SSO providers generally don't allow
    # wildcard addresses in their redirect URLs, for multi-realm
    # servers, we will have just completed authentication on e.g.
    # auth.zulip.example.com (depending on
    # settings.SOCIAL_AUTH_SUBDOMAIN), which cannot store cookies on
    # the subdomain.zulip.example.com domain.  So instead we serve a
    # redirect (encoding the authentication result data in a
    # cryptographically signed token) to a route on
    # subdomain.zulip.example.com that will verify the signature and
    # then call login_or_register_remote_user.
    return redirect_and_log_into_subdomain(realm, full_name, email_address,
                                           is_signup=is_signup,
                                           redirect_to=redirect_to,
                                           multiuse_object_key=multiuse_object_key)

class SocialAuthMixin(ZulipAuthMixin):
    auth_backend_name = "undeclared"
    # Used to determine how to order buttons on login form, backend with
    # higher sort order are displayed first.
    sort_order = 0

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
    sort_order = 100

    def get_verified_emails(self, *args: Any, **kwargs: Any) -> List[str]:
        access_token = kwargs["response"]["access_token"]
        try:
            emails = self._user_data(access_token, '/emails')
        except (HTTPError, ValueError, TypeError):  # nocoverage
            # We don't really need an explicit test for this code
            # path, since the outcome will be the same as any other
            # case without any verified emails
            emails = []

        verified_emails = []  # type: List[str]
        for email_obj in self.filter_usable_emails(emails):
            # social_associate_user_helper assumes that the first email in
            # verified_emails is primary.
            if email_obj.get("primary"):
                verified_emails.insert(0, email_obj["email"])
            else:
                verified_emails.append(email_obj["email"])

        return verified_emails

    def filter_usable_emails(self, emails: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        # We only let users login using email addresses that are
        # verified by GitHub, because the whole point is for the user
        # to demonstrate that they control the target email address.
        # We also disallow the
        # @noreply.github.com/@users.noreply.github.com email
        # addresses, because structurally, we only want to allow email
        # addresses that can receive emails, and those cannot.
        return [
            email for email in emails
            if email.get('verified') and not email["email"].endswith("noreply.github.com")
        ]

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

class AzureADAuthBackend(SocialAuthMixin, AzureADOAuth2):
    sort_order = 50
    auth_backend_name = "AzureAD"

class GoogleAuthBackend(SocialAuthMixin, GoogleOAuth2):
    sort_order = 150
    auth_backend_name = "Google"
    name = "google"

    def get_verified_emails(self, *args: Any, **kwargs: Any) -> List[str]:
        verified_emails = []    # type: List[str]
        details = kwargs["response"]
        email_verified = details.get("email_verified")
        if email_verified:
            verified_emails.append(details["email"])
        return verified_emails

AUTH_BACKEND_NAME_MAP = {
    'Dev': DevAuthBackend,
    'Email': EmailAuthBackend,
    'LDAP': ZulipLDAPAuthBackend,
    'RemoteUser': ZulipRemoteUserBackend,
}  # type: Dict[str, Any]
OAUTH_BACKEND_NAMES = []  # type: List[str]
SOCIAL_AUTH_BACKENDS = []  # type: List[BaseOAuth2]

# Authomatically add all of our social auth backends to relevant data structures.
for social_auth_subclass in SocialAuthMixin.__subclasses__():
    AUTH_BACKEND_NAME_MAP[social_auth_subclass.auth_backend_name] = social_auth_subclass
    if issubclass(social_auth_subclass, BaseOAuth2):
        OAUTH_BACKEND_NAMES.append(social_auth_subclass.auth_backend_name)
        SOCIAL_AUTH_BACKENDS.append(social_auth_subclass)

# Provide this alternative name for backwards compatibility with
# installations that had the old backend enabled.
GoogleMobileOauth2Backend = GoogleAuthBackend
