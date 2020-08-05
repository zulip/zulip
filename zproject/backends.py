# Documentation for Zulip's authentication backends is split across a few places:
#
# * https://zulip.readthedocs.io/en/latest/production/authentication-methods.html and
#   zproject/prod_settings_template.py have user-level configuration documentation.
# * https://zulip.readthedocs.io/en/latest/development/authentication.html
#   has developer-level documentation, especially on testing authentication backends
#   in the Zulip development environment.
#
# Django upstream's documentation for authentication backends is also
# helpful background.  The most important detail to understand for
# reading this file is that the Django authenticate() function will
# call the authenticate methods of all backends registered in
# settings.AUTHENTICATION_BACKENDS that have a function signature
# matching the args/kwargs passed in the authenticate() call.
import binascii
import copy
import logging
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Type, TypeVar, Union, cast

import magic
import ujson
from decorator import decorator
from django.conf import settings
from django.contrib.auth import authenticate, get_backends
from django.contrib.auth.backends import RemoteUserBackend
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.dispatch import Signal, receiver
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import ugettext as _
from django_auth_ldap.backend import LDAPBackend, LDAPReverseEmailSearch, _LDAPUser, ldap_error
from lxml.etree import XMLSyntaxError
from onelogin.saml2.errors import OneLogin_Saml2_Error
from onelogin.saml2.response import OneLogin_Saml2_Response
from onelogin.saml2.settings import OneLogin_Saml2_Settings
from requests import HTTPError
from social_core.backends.apple import AppleIdAuth
from social_core.backends.azuread import AzureADOAuth2
from social_core.backends.base import BaseAuth
from social_core.backends.github import GithubOAuth2, GithubOrganizationOAuth2, GithubTeamOAuth2
from social_core.backends.gitlab import GitLabOAuth2
from social_core.backends.google import GoogleOAuth2
from social_core.backends.saml import SAMLAuth, SAMLIdentityProvider
from social_core.exceptions import (
    AuthCanceled,
    AuthFailed,
    AuthMissingParameter,
    AuthStateForbidden,
    SocialAuthBaseException,
)
from social_core.pipeline.partial import partial
from typing_extensions import TypedDict
from zxcvbn import zxcvbn

from zerver.decorator import client_is_exempt_from_rate_limiting
from zerver.lib.actions import (
    do_create_user,
    do_deactivate_user,
    do_reactivate_user,
    do_update_user_custom_profile_data_if_changed,
)
from zerver.lib.avatar import avatar_url, is_avatar_new
from zerver.lib.avatar_hash import user_avatar_content_hash
from zerver.lib.create_user import get_role_for_new_user
from zerver.lib.dev_ldap_directory import init_fakeldap
from zerver.lib.email_validation import email_allowed_for_realm, validate_email_not_already_in_realm
from zerver.lib.mobile_auth_otp import is_valid_otp
from zerver.lib.rate_limiter import RateLimitedObject
from zerver.lib.redis_utils import get_dict_from_redis, get_redis_client, put_dict_in_redis
from zerver.lib.request import JsonableError
from zerver.lib.subdomains import get_subdomain
from zerver.lib.users import check_full_name, validate_user_custom_profile_field
from zerver.models import (
    CustomProfileField,
    DisposableEmailError,
    DomainNotAllowedForRealmError,
    EmailContainsPlusError,
    PreregistrationUser,
    Realm,
    UserProfile,
    custom_profile_fields_for_realm,
    email_to_username,
    get_realm,
    get_user_by_delivery_email,
    get_user_profile_by_id,
    remote_user_to_email,
    supported_auth_backends,
)

redis_client = get_redis_client()

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
        enabled_method_dict = {method: True for method in Realm.AUTHENTICATION_FLAGS}
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

def gitlab_auth_enabled(realm: Optional[Realm]=None) -> bool:
    return auth_enabled_helper(['GitLab'], realm)

def apple_auth_enabled(realm: Optional[Realm]=None) -> bool:
    return auth_enabled_helper(['Apple'], realm)

def saml_auth_enabled(realm: Optional[Realm]=None) -> bool:
    return auth_enabled_helper(['SAML'], realm)

def any_social_backend_enabled(realm: Optional[Realm]=None) -> bool:
    """Used by the login page process to determine whether to show the
    'OR' for login with Google"""
    social_backend_names = [social_auth_subclass.auth_backend_name
                            for social_auth_subclass in EXTERNAL_AUTH_METHODS]
    return auth_enabled_helper(social_backend_names, realm)

def redirect_to_config_error(error_type: str) -> HttpResponseRedirect:
    return HttpResponseRedirect(f"/config-error/{error_type}")

def require_email_format_usernames(realm: Optional[Realm]=None) -> bool:
    if ldap_auth_enabled(realm):
        if settings.LDAP_EMAIL_ATTR or settings.LDAP_APPEND_DOMAIN:
            return False
    return True

def is_user_active(user_profile: UserProfile, return_data: Optional[Dict[str, Any]]=None) -> bool:
    if not user_profile.is_active:
        if return_data is not None:
            if user_profile.is_mirror_dummy:
                # Record whether it's a mirror dummy account
                return_data['is_mirror_dummy'] = True
            return_data['inactive_user'] = True
            return_data['inactive_user_id'] = user_profile.id
        return False
    if user_profile.realm.deactivated:
        if return_data is not None:
            return_data['inactive_realm'] = True
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
    if not is_user_active(user_profile, return_data):
        return None

    return user_profile

AuthFuncT = TypeVar('AuthFuncT', bound=Callable[..., Optional[UserProfile]])
rate_limiting_rules = settings.RATE_LIMITING_RULES['authenticate_by_username']

class RateLimitedAuthenticationByUsername(RateLimitedObject):
    def __init__(self, username: str) -> None:
        self.username = username
        super().__init__()

    def key(self) -> str:
        return f"{type(self).__name__}:{self.username}"

    def rules(self) -> List[Tuple[int, int]]:
        return rate_limiting_rules

def rate_limit_authentication_by_username(request: HttpRequest, username: str) -> None:
    RateLimitedAuthenticationByUsername(username).rate_limit_request(request)

def auth_rate_limiting_already_applied(request: HttpRequest) -> bool:
    if not hasattr(request, '_ratelimits_applied'):
        return False

    return any(isinstance(r.entity, RateLimitedAuthenticationByUsername)
               for r in request._ratelimits_applied)

# Django's authentication mechanism uses introspection on the various authenticate() functions
# defined by backends, so we need a decorator that doesn't break function signatures.
# @decorator does this for us.
# The usual @wraps from functools breaks signatures, so it can't be used here.
@decorator
def rate_limit_auth(auth_func: AuthFuncT, *args: Any, **kwargs: Any) -> Optional[UserProfile]:
    if not settings.RATE_LIMITING_AUTHENTICATE:
        return auth_func(*args, **kwargs)

    request = args[1]
    username = kwargs['username']
    if not hasattr(request, 'client') or not client_is_exempt_from_rate_limiting(request):
        # Django cycles through enabled authentication backends until one succeeds,
        # or all of them fail. If multiple backends are tried like this, we only want
        # to execute rate_limit_authentication_* once, on the first attempt:
        if auth_rate_limiting_already_applied(request):
            pass
        else:
            # Apply rate limiting. If this request is above the limit,
            # RateLimited will be raised, interrupting the authentication process.
            # From there, the code calling authenticate() can either catch the exception
            # and handle it on its own, or it will be processed by RateLimitMiddleware.
            rate_limit_authentication_by_username(request, username)

    result = auth_func(*args, **kwargs)
    if result is not None:
        # Authentication succeeded, clear the rate-limiting record.
        RateLimitedAuthenticationByUsername(username).clear_history()

    return result

class ZulipAuthMixin:
    """This common mixin is used to override Django's default behavior for
    looking up a logged-in user by ID to use a version that fetches
    from memcached before checking the database (avoiding a database
    query in most cases).
    """
    name = "undefined"
    _logger = None

    @property
    def logger(self) -> logging.Logger:
        if self._logger is None:
            self._logger = logging.getLogger(f"zulip.auth.{self.name}")
        return self._logger

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

    def authenticate(self, request: Optional[HttpRequest]=None, *,
                     username: str, realm: Realm,
                     use_dummy_backend: bool=False,
                     return_data: Optional[Dict[str, Any]]=None) -> Optional[UserProfile]:
        if use_dummy_backend:
            return common_get_active_user(username, realm, return_data)
        return None

def check_password_strength(password: str) -> bool:
    """
    Returns True if the password is strong enough,
    False otherwise.
    """
    if len(password) < settings.PASSWORD_MIN_LENGTH:
        return False

    if password == '':
        # zxcvbn throws an exception when passed the empty string, so
        # we need a special case for the empty string password here.
        return False

    if int(zxcvbn(password)['guesses']) < settings.PASSWORD_MIN_GUESSES:
        return False

    return True

class EmailAuthBackend(ZulipAuthMixin):
    """
    Email+Password Authentication Backend (the default).

    Allows a user to sign in using an email/password pair.
    """

    name = 'email'

    @rate_limit_auth
    def authenticate(self, request: Optional[HttpRequest]=None, *,
                     username: str, password: str,
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
        if password == "":
            # Never allow an empty password.  This is defensive code;
            # a user having password "" should only be possible
            # through a bug somewhere else.
            return None

        user_profile = common_get_active_user(username, realm, return_data=return_data)
        if user_profile is None:
            return None
        if user_profile.check_password(password):
            return user_profile
        return None

def is_valid_email(email: str) -> bool:
    try:
        validate_email(email)
    except ValidationError:
        return False
    return True

def check_ldap_config() -> None:
    if not settings.LDAP_APPEND_DOMAIN:
        # Email search needs to be configured in this case.
        assert settings.AUTH_LDAP_USERNAME_ATTR and settings.AUTH_LDAP_REVERSE_EMAIL_SEARCH

def find_ldap_users_by_email(email: str) -> Optional[List[_LDAPUser]]:
    """
    Returns list of _LDAPUsers matching the email search,
    or None if no matches are found.
    """
    email_search = LDAPReverseEmailSearch(LDAPBackend(), email)
    return email_search.search_for_users(should_populate=False)

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

    check_ldap_config()
    if settings.LDAP_APPEND_DOMAIN:
        # Check if the email ends with LDAP_APPEND_DOMAIN
        return email.strip().lower().endswith("@" + settings.LDAP_APPEND_DOMAIN)

    # If we don't have an LDAP domain, we have to do a lookup for the email.
    if find_ldap_users_by_email(email):
        return True
    else:
        return False

ldap_logger = logging.getLogger("zulip.ldap")
class ZulipLDAPException(_LDAPUser.AuthenticationFailed):
    """Since this inherits from _LDAPUser.AuthenticationFailed, these will
    be caught and logged at debug level inside django-auth-ldap's authenticate()"""

class ZulipLDAPExceptionNoMatchingLDAPUser(ZulipLDAPException):
    pass

class ZulipLDAPExceptionOutsideDomain(ZulipLDAPExceptionNoMatchingLDAPUser):
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

    name = "ldap"

    def __init__(self) -> None:
        # Used to initialize a fake LDAP directly for both manual
        # and automated testing in a development environment where
        # there is no actual LDAP server.
        if settings.DEVELOPMENT and settings.FAKE_LDAP_MODE:  # nocoverage
            init_fakeldap()

        check_ldap_config()

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
        """
        Translates django username (user_profile.email or whatever the user typed in the login
        field when authenticating via the ldap backend) into ldap username.
        Guarantees that the username it returns actually has an entry in the ldap directory.
        Raises ZulipLDAPExceptionNoMatchingLDAPUser if that's not possible.
        """
        result = username
        if settings.LDAP_APPEND_DOMAIN:
            if is_valid_email(username):
                if not username.endswith("@" + settings.LDAP_APPEND_DOMAIN):
                    raise ZulipLDAPExceptionOutsideDomain(f"Email {username} does not match LDAP domain {settings.LDAP_APPEND_DOMAIN}.")
                result = email_to_username(username)
        else:
            # We can use find_ldap_users_by_email
            if is_valid_email(username):
                email_search_result = find_ldap_users_by_email(username)
                if email_search_result is None:
                    result = username
                elif len(email_search_result) == 1:
                    return email_search_result[0]._username
                elif len(email_search_result) > 1:
                    # This is possible, but strange, so worth logging a warning about.
                    # We can't translate the email to a unique username,
                    # so we don't do anything else here.
                    logging.warning("Multiple users with email %s found in LDAP.", username)
                    result = username

        if _LDAPUser(self, result).attrs is None:
            # Check that there actually is an ldap entry matching the result username
            # we want to return. Otherwise, raise an exception.
            error_message = "No ldap user matching django_to_ldap_username result: {}. Input username: {}"
            raise ZulipLDAPExceptionNoMatchingLDAPUser(
                error_message.format(result, username),
            )

        return result

    def user_email_from_ldapuser(self, username: str, ldap_user: _LDAPUser) -> str:
        if hasattr(ldap_user, '_username'):
            # In tests, we sometimes pass a simplified _LDAPUser without _username attr,
            # and with the intended username in the username argument.
            username = ldap_user._username

        if settings.LDAP_APPEND_DOMAIN:
            return "@".join((username, settings.LDAP_APPEND_DOMAIN))

        if settings.LDAP_EMAIL_ATTR is not None:
            # Get email from ldap attributes.
            if settings.LDAP_EMAIL_ATTR not in ldap_user.attrs:
                raise ZulipLDAPException(f"LDAP user doesn't have the needed {settings.LDAP_EMAIL_ATTR} attribute")
            else:
                return ldap_user.attrs[settings.LDAP_EMAIL_ATTR][0]

        return username

    def ldap_to_django_username(self, username: str) -> str:
        """
        This is called inside django_auth_ldap with only one role:
        to convert _LDAPUser._username to django username (so in Zulip, the email)
        and pass that as "username" argument to get_or_build_user(username, ldapuser).
        In many cases, the email is stored in the _LDAPUser's attributes, so it can't be
        constructed just from the username. We choose to do nothing in this function,
        and our overrides of get_or_build_user() obtain that username from the _LDAPUser
        object on their own, through our user_email_from_ldapuser function.
        """
        return username

    def sync_avatar_from_ldap(self, user: UserProfile, ldap_user: _LDAPUser) -> None:
        if 'avatar' in settings.AUTH_LDAP_USER_ATTR_MAP:
            # We do local imports here to avoid import loops
            from io import BytesIO

            from zerver.lib.actions import do_change_avatar_fields
            from zerver.lib.upload import upload_avatar_image

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
                do_change_avatar_fields(user, UserProfile.AVATAR_FROM_USER, acting_user=None)
                # Update avatar hash.
                user.avatar_hash = user_avatar_content_hash(ldap_avatar)
                user.save(update_fields=["avatar_hash"])
            else:
                logging.warning("Could not parse %s field for user %s",
                                avatar_attr_name, user.id)

    def is_account_control_disabled_user(self, ldap_user: _LDAPUser) -> bool:
        """Implements the userAccountControl check for whether a user has been
        disabled in an Active Directory server being integrated with
        Zulip via LDAP."""
        account_control_value = ldap_user.attrs[settings.AUTH_LDAP_USER_ATTR_MAP['userAccountControl']][0]
        ldap_disabled = bool(int(account_control_value) & LDAP_USER_ACCOUNT_CONTROL_DISABLED_MASK)
        return ldap_disabled

    @classmethod
    def get_mapped_name(cls, ldap_user: _LDAPUser) -> str:
        """Constructs the user's Zulip full_name from the LDAP data"""
        if "full_name" in settings.AUTH_LDAP_USER_ATTR_MAP:
            full_name_attr = settings.AUTH_LDAP_USER_ATTR_MAP["full_name"]
            full_name = ldap_user.attrs[full_name_attr][0]
        elif all(key in settings.AUTH_LDAP_USER_ATTR_MAP for key in {"first_name", "last_name"}):
            first_name_attr = settings.AUTH_LDAP_USER_ATTR_MAP["first_name"]
            last_name_attr = settings.AUTH_LDAP_USER_ATTR_MAP["last_name"]
            first_name = ldap_user.attrs[first_name_attr][0]
            last_name = ldap_user.attrs[last_name_attr][0]
            full_name = f"{first_name} {last_name}"
        else:
            raise ZulipLDAPException("Missing required mapping for user's full name")

        return full_name

    def sync_full_name_from_ldap(self, user_profile: UserProfile,
                                 ldap_user: _LDAPUser) -> None:
        from zerver.lib.actions import do_change_full_name
        full_name = self.get_mapped_name(ldap_user)
        if full_name != user_profile.full_name:
            try:
                full_name = check_full_name(full_name)
            except JsonableError as e:
                raise ZulipLDAPException(e.msg)
            do_change_full_name(user_profile, full_name, None)

    def sync_custom_profile_fields_from_ldap(self, user_profile: UserProfile,
                                             ldap_user: _LDAPUser) -> None:
        values_by_var_name: Dict[str, Union[int, str, List[int]]] = {}
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

        fields_by_var_name: Dict[str, CustomProfileField] = {}
        custom_profile_fields = custom_profile_fields_for_realm(user_profile.realm.id)
        for field in custom_profile_fields:
            var_name = '_'.join(field.name.lower().split(' '))
            fields_by_var_name[var_name] = field

        existing_values = {}
        for data in user_profile.profile_data:
            var_name = '_'.join(data['name'].lower().split(' '))
            existing_values[var_name] = data['value']

        profile_data: List[Dict[str, Union[int, str, List[int]]]] = []
        for var_name, value in values_by_var_name.items():
            try:
                field = fields_by_var_name[var_name]
            except KeyError:
                raise ZulipLDAPException(f'Custom profile field with name {var_name} not found.')
            if existing_values.get(var_name) == value:
                continue
            try:
                validate_user_custom_profile_field(user_profile.realm.id, field, value)
            except ValidationError as error:
                raise ZulipLDAPException(f'Invalid data for {var_name} field: {error.message}')
            profile_data.append({
                'id': field.id,
                'value': value,
            })
        do_update_user_custom_profile_data_if_changed(user_profile, profile_data)

class ZulipLDAPAuthBackend(ZulipLDAPAuthBackendBase):
    REALM_IS_NONE_ERROR = 1

    @rate_limit_auth
    def authenticate(self, request: Optional[HttpRequest]=None, *,
                     username: str, password: str, realm: Realm,
                     prereg_user: Optional[PreregistrationUser]=None,
                     return_data: Optional[Dict[str, Any]]=None) -> Optional[UserProfile]:
        self._realm = realm
        self._prereg_user = prereg_user
        if not ldap_auth_enabled(realm):
            return None

        try:
            # We want to pass the user's LDAP username into
            # authenticate() below.  If an email address was entered
            # in the login form, we need to use
            # django_to_ldap_username to translate the email address
            # to the user's LDAP username before calling the
            # django-auth-ldap authenticate().
            username = self.django_to_ldap_username(username)
        except ZulipLDAPExceptionNoMatchingLDAPUser as e:
            ldap_logger.debug("%s: %s", self.__class__.__name__, e)
            if return_data is not None:
                return_data['no_matching_ldap_user'] = True
            return None

        # Call into (ultimately) the django-auth-ldap authenticate
        # function.  This will check the username/password pair
        # against the LDAP database, and assuming those are correct,
        # end up calling `self.get_or_build_user` with the
        # authenticated user's data from LDAP.
        return super().authenticate(request=request, username=username, password=password)

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
        return_data: Dict[str, Any] = {}

        username = self.user_email_from_ldapuser(username, ldap_user)

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
        # we also call validate_email_not_already_in_realm just for consistency,
        # even though its checks were already done above.
        try:
            email_allowed_for_realm(username, self._realm)
            validate_email_not_already_in_realm(self._realm, username)
        except DomainNotAllowedForRealmError:
            raise ZulipLDAPException("This email domain isn't allowed in this organization.")
        except (DisposableEmailError, EmailContainsPlusError):
            raise ZulipLDAPException("Email validation failed.")

        # We have valid LDAP credentials; time to create an account.
        full_name = self.get_mapped_name(ldap_user)
        try:
            full_name = check_full_name(full_name)
        except JsonableError as e:
            raise ZulipLDAPException(e.msg)

        opts: Dict[str, Any] = {}
        if self._prereg_user:
            invited_as = self._prereg_user.invited_as
            realm_creation = self._prereg_user.realm_creation
            opts['prereg_user'] = self._prereg_user
            opts['role'] = get_role_for_new_user(invited_as, realm_creation)
            opts['realm_creation'] = realm_creation
            # TODO: Ideally, we should add a mechanism for the user
            # entering which default stream groups they've selected in
            # the LDAP flow.
            opts['default_stream_groups'] = []

        user_profile = do_create_user(username, None, self._realm, full_name, acting_user=None, **opts)
        self.sync_avatar_from_ldap(user_profile, ldap_user)
        self.sync_custom_profile_fields_from_ldap(user_profile, ldap_user)

        return user_profile, True

class ZulipLDAPUser(_LDAPUser):
    """
    This is an extension of the _LDAPUser class, with a realm attribute
    attached to it. It's purpose is to call its inherited method
    populate_user() which will sync the ldap data with the corresponding
    UserProfile. The realm attribute serves to uniquely identify the UserProfile
    in case the ldap user is registered to multiple realms.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.realm: Realm = kwargs['realm']
        del kwargs['realm']

        super().__init__(*args, **kwargs)

class ZulipLDAPUserPopulator(ZulipLDAPAuthBackendBase):
    """Just like ZulipLDAPAuthBackend, but doesn't let you log in.  Used
    for syncing data like names, avatars, and custom profile fields
    from LDAP in `manage.py sync_ldap_user_data` as well as in
    registration for organizations that use a different SSO solution
    for managing login (often via RemoteUserBackend).
    """

    def authenticate(self, request: Optional[HttpRequest]=None, *,
                     username: str, password: str, realm: Realm,
                     return_data: Optional[Dict[str, Any]]=None) -> Optional[UserProfile]:
        return None

    def get_or_build_user(self, username: str,
                          ldap_user: ZulipLDAPUser) -> Tuple[UserProfile, bool]:
        """This is used only in non-authentication contexts such as:
             ./manage.py sync_ldap_user_data
        """
        # Obtain the django username from the ldap_user object:
        username = self.user_email_from_ldapuser(username, ldap_user)

        # We set the built flag (which tells django-auth-ldap whether the user object
        # was taken from the database or freshly built) to False - because in this codepath
        # the user we're syncing of course already has to exist in the database.
        user = get_user_by_delivery_email(username, ldap_user.realm)
        built = False
        # Synchronise the UserProfile with its LDAP attributes:
        if 'userAccountControl' in settings.AUTH_LDAP_USER_ATTR_MAP:
            user_disabled_in_ldap = self.is_account_control_disabled_user(ldap_user)
            if user_disabled_in_ldap:
                if user.is_active:
                    ldap_logger.info("Deactivating user %s because they are disabled in LDAP.",
                                     user.delivery_email)
                    do_deactivate_user(user)
                # Do an early return to avoid trying to sync additional data.
                return (user, built)
            elif not user.is_active:
                ldap_logger.info("Reactivating user %s because they are not disabled in LDAP.",
                                 user.delivery_email)
                do_reactivate_user(user)

        self.sync_avatar_from_ldap(user, ldap_user)
        self.sync_full_name_from_ldap(user, ldap_user)
        self.sync_custom_profile_fields_from_ldap(user, ldap_user)
        return (user, built)

class PopulateUserLDAPError(ZulipLDAPException):
    pass

@receiver(ldap_error, sender=ZulipLDAPUserPopulator)
def catch_ldap_error(signal: Signal, **kwargs: Any) -> None:
    """
    Inside django_auth_ldap populate_user(), if LDAPError is raised,
    e.g. due to invalid connection credentials, the function catches it
    and emits a signal (ldap_error) to communicate this error to others.
    We normally don't use signals, but here there's no choice, so in this function
    we essentially convert the signal to a normal exception that will properly
    propagate out of django_auth_ldap internals.
    """
    if kwargs['context'] == 'populate_user':
        # The exception message can contain the password (if it was invalid),
        # so it seems better not to log that, and only use the original exception's name here.
        raise PopulateUserLDAPError(kwargs['exception'].__class__.__name__)

def sync_user_from_ldap(user_profile: UserProfile, logger: logging.Logger) -> bool:
    backend = ZulipLDAPUserPopulator()
    try:
        ldap_username = backend.django_to_ldap_username(user_profile.delivery_email)
    except ZulipLDAPExceptionNoMatchingLDAPUser:
        if (
            settings.ONLY_LDAP
            if settings.LDAP_DEACTIVATE_NON_MATCHING_USERS is None
            else settings.LDAP_DEACTIVATE_NON_MATCHING_USERS
        ):
            do_deactivate_user(user_profile)
            logger.info("Deactivated non-matching user: %s", user_profile.delivery_email)
            return True
        elif user_profile.is_active:
            logger.warning("Did not find %s in LDAP.", user_profile.delivery_email)
        return False

    # What one would expect to see like to do here is just a call to
    # `backend.populate_user`, which in turn just creates the
    # `_LDAPUser` object and calls `ldap_user.populate_user()` on
    # that.  Unfortunately, that will produce incorrect results in the
    # case that the server has multiple Zulip users in different
    # realms associated with a single LDAP user, because
    # `django-auth-ldap` isn't implemented with the possibility of
    # multiple realms on different subdomains in mind.
    #
    # To address this, we construct a version of the _LDAPUser class
    # extended to store the realm of the target user, and call its
    # `.populate_user` function directly.
    #
    # Ideally, we'd contribute changes to `django-auth-ldap` upstream
    # making this flow possible in a more directly supported fashion.
    updated_user = ZulipLDAPUser(backend, ldap_username, realm=user_profile.realm).populate_user()
    if updated_user:
        logger.info("Updated %s.", user_profile.delivery_email)
        return True

    raise PopulateUserLDAPError(f"populate_user unexpectedly returned {updated_user}")

# Quick tool to test whether you're correctly authenticating to LDAP
def query_ldap(email: str) -> List[str]:
    values = []
    backend = next((backend for backend in get_backends() if isinstance(backend, LDAPBackend)), None)
    if backend is not None:
        try:
            ldap_username = backend.django_to_ldap_username(email)
        except ZulipLDAPExceptionNoMatchingLDAPUser as e:
            values.append(f"No such user found: {e}")
            return values

        ldap_attrs = _LDAPUser(backend, ldap_username).attrs

        for django_field, ldap_field in settings.AUTH_LDAP_USER_ATTR_MAP.items():
            value = ldap_attrs.get(ldap_field, ["LDAP field not present"])[0]
            if django_field == "avatar":
                if isinstance(value, bytes):
                    value = "(An avatar image file)"
            values.append(f"{django_field}: {value}")
        if settings.LDAP_EMAIL_ATTR is not None:
            values.append("{}: {}".format('email', ldap_attrs[settings.LDAP_EMAIL_ATTR][0]))
    else:
        values.append("LDAP backend not configured on this server.")
    return values

class DevAuthBackend(ZulipAuthMixin):
    """Allow logging in as any user without a password.  This is used for
    convenience when developing Zulip, and is disabled in production."""

    name = 'dev'

    def authenticate(self, request: Optional[HttpRequest]=None, *,
                     dev_auth_username: str, realm: Realm,
                     return_data: Optional[Dict[str, Any]]=None) -> Optional[UserProfile]:
        if not dev_auth_enabled(realm):
            return None
        return common_get_active_user(dev_auth_username, realm, return_data=return_data)

class ExternalAuthMethodDictT(TypedDict):
    name: str
    display_name: str
    display_icon: Optional[str]
    login_url: str
    signup_url: str

class ExternalAuthMethod(ABC):
    """
    To register a backend as an external_authentication_method, it should
    subclass ExternalAuthMethod and define its dict_representation
    classmethod, and finally use the external_auth_method class decorator to
    get added to the EXTERNAL_AUTH_METHODS list.
    """
    auth_backend_name = "undeclared"
    name = "undeclared"
    display_icon: Optional[str] = None

    # Used to determine how to order buttons on login form, backend with
    # higher sort order are displayed first.
    sort_order = 0

    @classmethod
    @abstractmethod
    def dict_representation(cls, realm: Optional[Realm]=None) -> List[ExternalAuthMethodDictT]:
        """
        Method returning dictionaries representing the authentication methods
        corresponding to the backend that subclasses this. The documentation
        for the external_authentication_methods field of the /server_settings endpoint
        explains the details of these dictionaries.
        This returns a list, because one backend can support configuring multiple methods,
        that are all serviced by that backend - our SAML backend is an example of that.
        """

EXTERNAL_AUTH_METHODS: List[Type[ExternalAuthMethod]] = []

def external_auth_method(cls: Type[ExternalAuthMethod]) -> Type[ExternalAuthMethod]:
    assert issubclass(cls, ExternalAuthMethod)

    EXTERNAL_AUTH_METHODS.append(cls)
    return cls

# We want to be able to store this data in redis, so it has to be easy to serialize.
# That's why we avoid having fields that could pose a problem for that.
class ExternalAuthDataDict(TypedDict, total=False):
    subdomain: str
    full_name: str
    email: str
    is_signup: bool
    is_realm_creation: bool
    redirect_to: str
    mobile_flow_otp: Optional[str]
    desktop_flow_otp: Optional[str]
    multiuse_object_key: str
    full_name_validated: bool

class ExternalAuthResult:
    LOGIN_KEY_PREFIX = "login_key_"
    LOGIN_KEY_FORMAT = LOGIN_KEY_PREFIX + "{token}"
    LOGIN_KEY_EXPIRATION_SECONDS = 15
    LOGIN_TOKEN_LENGTH = UserProfile.API_KEY_LENGTH

    def __init__(self, *, user_profile: Optional[UserProfile]=None,
                 data_dict: Optional[ExternalAuthDataDict]=None,
                 login_token: Optional[str]=None,
                 delete_stored_data: bool=True) -> None:
        if data_dict is None:
            data_dict = {}

        if login_token is not None:
            assert (not data_dict) and (user_profile is None), ("Passing in data_dict or user_profile " +
                                                                "with login_token is disallowed.")
            self.instantiate_with_token(login_token, delete_stored_data)
        else:
            self.data_dict = data_dict.copy()
            self.user_profile = user_profile

        if self.user_profile is not None:
            # Ensure data inconsistent with the user_profile wasn't passed in inside the data_dict argument.
            assert 'full_name' not in data_dict or data_dict['full_name'] == self.user_profile.full_name
            assert 'email' not in data_dict or data_dict['email'].lower() == self.user_profile.delivery_email.lower()
            # Update these data_dict fields to ensure consistency with self.user_profile. This is mostly
            # defensive code, but is useful in these scenarios:
            # 1. user_profile argument was passed in, and no full_name or email_data in the data_dict arg.
            # 2. We're instantiating from the login_token and the user has changed their full_name since
            #    the data was stored under the token.
            self.data_dict['full_name'] = self.user_profile.full_name
            self.data_dict['email'] = self.user_profile.delivery_email

            if 'subdomain' not in self.data_dict:
                self.data_dict['subdomain'] = self.user_profile.realm.subdomain
            if not self.user_profile.is_mirror_dummy:
                self.data_dict['is_signup'] = False

    def store_data(self) -> str:
        key = put_dict_in_redis(redis_client, self.LOGIN_KEY_FORMAT, self.data_dict,
                                expiration_seconds=self.LOGIN_KEY_EXPIRATION_SECONDS,
                                token_length=self.LOGIN_TOKEN_LENGTH)
        token = key.split(self.LOGIN_KEY_PREFIX, 1)[1]  # remove the prefix
        return token

    def instantiate_with_token(self, token: str, delete_stored_data: bool=True) -> None:
        key = self.LOGIN_KEY_FORMAT.format(token=token)
        data = get_dict_from_redis(redis_client, self.LOGIN_KEY_FORMAT, key)
        if data is None or None in [data.get("email"), data.get("subdomain")]:
            raise self.InvalidTokenError

        if delete_stored_data:
            redis_client.delete(key)

        self.data_dict = cast(ExternalAuthDataDict, data)

        # Here we refetch the UserProfile object (if any) for this
        # ExternalAuthResult.  Using authenticate() will re-check for
        # (unlikely) races like the realm or user having been deactivated
        # between generating this ExternalAuthResult and accessing it.
        #
        # In theory, we should return_data here so the caller can do
        # more customized error messages for those unlikely races, but
        # it's likely not worth implementing.
        realm = get_realm(data['subdomain'])
        self.user_profile = authenticate(username=data['email'], realm=realm,
                                         use_dummy_backend=True)

    class InvalidTokenError(Exception):
        pass

@external_auth_method
class ZulipRemoteUserBackend(RemoteUserBackend, ExternalAuthMethod):
    """Authentication backend that reads the Apache REMOTE_USER variable.
    Used primarily in enterprise environments with an SSO solution
    that has an Apache REMOTE_USER integration.  For manual testing, see

      https://zulip.readthedocs.io/en/latest/production/authentication-methods.html

    See also remote_user_sso in zerver/views/auth.py.
    """
    auth_backend_name = "RemoteUser"
    name = "remoteuser"
    display_icon = None
    sort_order = 9000  # If configured, this backend should have its button near the top of the list.

    create_unknown_user = False

    def authenticate(self, request: Optional[HttpRequest]=None, *,
                     remote_user: str, realm: Realm,
                     return_data: Optional[Dict[str, Any]]=None) -> Optional[UserProfile]:
        if not auth_enabled_helper(["RemoteUser"], realm):
            return None

        email = remote_user_to_email(remote_user)
        return common_get_active_user(email, realm, return_data=return_data)

    @classmethod
    def dict_representation(cls, realm: Optional[Realm]=None) -> List[ExternalAuthMethodDictT]:
        return [dict(
            name=cls.name,
            display_name="SSO",
            display_icon=cls.display_icon,
            # The user goes to the same URL for both login and signup:
            login_url=reverse('start-login-sso'),
            signup_url=reverse('start-login-sso'),
        )]

def redirect_deactivated_user_to_login() -> HttpResponseRedirect:
    # Specifying the template name makes sure that the user is not redirected to dev_login in case of
    # a deactivated account on a test server.
    login_url = reverse('zerver.views.auth.login_page', kwargs = {'template_name': 'zerver/login.html'})
    redirect_url = login_url + '?is_deactivated=true'
    return HttpResponseRedirect(redirect_url)

def social_associate_user_helper(backend: BaseAuth, return_data: Dict[str, Any],
                                 *args: Any, **kwargs: Any) -> Union[HttpResponse, Optional[UserProfile]]:
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
    return_data["realm_string_id"] = realm.string_id

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
        verified_emails = backend.get_verified_emails(realm, *args, **kwargs)
        verified_emails_length = len(verified_emails)
        if verified_emails_length == 0:
            # TODO: Provide a nice error message screen to the user
            # for this case, rather than just logging a warning.
            backend.logger.warning("Social auth (%s) failed because user has no verified emails",
                                   backend.auth_backend_name)
            return_data["email_not_verified"] = True
            return None

        if verified_emails_length == 1:
            chosen_email = verified_emails[0]
        else:
            chosen_email = backend.strategy.request_data().get('email')

        if not chosen_email:
            avatars = {}  # Dict[str, str]
            existing_account_emails = []
            for email in verified_emails:
                existing_account = common_get_active_user(email, realm, {})
                if existing_account is not None:
                    existing_account_emails.append(email)
                    avatars[email] = avatar_url(existing_account)

            if (len(existing_account_emails) != 1 or backend.strategy.session_get('is_signup') == '1'):
                unverified_emails = []
                if hasattr(backend, 'get_unverified_emails'):
                    unverified_emails = backend.get_unverified_emails(realm, *args, **kwargs)
                return render(backend.strategy.request, 'zerver/social_auth_select_email.html', context = {
                    'primary_email': verified_emails[0],
                    'verified_non_primary_emails': verified_emails[1:],
                    'unverified_emails': unverified_emails,
                    'backend': 'github',
                    'avatar_urls': avatars,
                })
            else:
                chosen_email = existing_account_emails[0]

        try:
            validate_email(chosen_email)
        except ValidationError:
            return_data['invalid_email'] = True
            return None

        if chosen_email not in verified_emails:
            # If a user edits the submit value for the choose email form, we might
            # end up with a wrong email associated with the account. The below code
            # takes care of that.
            backend.logger.warning("Social auth (%s) failed because user has no verified"
                                   " emails associated with the account",
                                   backend.auth_backend_name)
            return_data["email_not_associated"] = True
            return None

        validated_email = chosen_email
    else:
        try:
            validate_email(kwargs["details"].get("email"))
        except ValidationError:
            return_data['invalid_email'] = True
            return None
        validated_email = kwargs["details"].get("email")

    if not validated_email:  # nocoverage
        # This code path isn't used with GitHubAuthBackend, but may be relevant for other
        # social auth backends.
        return_data['invalid_email'] = True
        return None

    return_data["valid_attestation"] = True
    return_data['validated_email'] = validated_email
    user_profile = common_get_active_user(validated_email, realm, return_data)

    full_name = kwargs['details'].get('fullname')
    first_name = kwargs['details'].get('first_name')
    last_name = kwargs['details'].get('last_name')
    if all(name is None for name in [full_name, first_name, last_name]) and backend.name != "apple":
        # Apple authentication provides the user's name only the very first time a user tries to login.
        # So if the user aborts login or otherwise is doing this the second time,
        # we won't have any name data. So, this case is handled with the code below
        # setting full name to empty string.

        # We need custom code here for any social auth backends
        # that don't provide name details feature.
        raise AssertionError("Social auth backend doesn't provide name")

    if full_name:
        return_data["full_name"] = full_name
    else:
        # Some authentications methods like Apple and SAML send
        # first name and last name as seperate attributes. In that case
        # we construct the full name from them.
        return_data["full_name"] = f"{first_name or ''} {last_name or ''}".strip()  # strip removes the unnecessary ' '

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
    return_data: Dict[str, Any] = {}
    user_profile = social_associate_user_helper(
        backend, return_data, *args, **kwargs)

    if isinstance(user_profile, HttpResponse):
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
                       **kwargs: Any) -> Optional[HttpResponse]:
    """Given the determination in social_auth_associate_user for whether
    the user should be authenticated, this takes care of actually
    logging in the user (if appropriate) and redirecting the browser
    to the appropriate next page depending on the situation.  Read the
    comments below as well as login_or_register_remote_user in
    `zerver/views/auth.py` for the details on how that dispatch works.
    """
    from zerver.views.auth import login_or_register_remote_user, redirect_and_log_into_subdomain

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
        # User has passed an invalid subdomain param - this shouldn't happen in the normal flow,
        # unless the user manually edits the param. In any case, it's most appropriate to just take
        # them to find_account, as there isn't even an appropriate subdomain to take them to the login
        # form on.
        return HttpResponseRedirect(reverse('zerver.views.registration.find_account'))

    if inactive_user:
        backend.logger.info("Failed login attempt for deactivated account: %s@%s",
                            return_data['inactive_user_id'], return_data['realm_string_id'])
        return redirect_deactivated_user_to_login()

    if auth_backend_disabled or inactive_realm or no_verified_email or email_not_associated:
        # Redirect to login page. We can't send to registration
        # workflow with these errors. We will redirect to login page.
        return None

    if invalid_email:
        # In case of invalid email, we will end up on registration page.
        # This seems better than redirecting to login page.
        backend.logger.warning(
            "%s got invalid email argument.", backend.auth_backend_name,
        )
        return None

    if auth_failed_reason:
        backend.logger.info(auth_failed_reason)
        return None

    # Structurally, all the cases where we don't have an authenticated
    # email for the user should be handled above; this assertion helps
    # prevent any violations of that contract from resulting in a user
    # being incorrectly authenticated.
    assert return_data.get('valid_attestation') is True

    strategy = backend.strategy
    full_name_validated = backend.full_name_validated
    email_address = return_data['validated_email']
    full_name = return_data['full_name']
    redirect_to = strategy.session_get('next')
    realm = Realm.objects.get(id=return_data["realm_id"])
    multiuse_object_key = strategy.session_get('multiuse_object_key', '')

    mobile_flow_otp = strategy.session_get('mobile_flow_otp')
    desktop_flow_otp = strategy.session_get('desktop_flow_otp')
    validate_otp_params(mobile_flow_otp, desktop_flow_otp)

    if user_profile is None or user_profile.is_mirror_dummy:
        is_signup = strategy.session_get('is_signup') == '1'
    else:
        is_signup = False

    # At this point, we have now confirmed that the user has
    # demonstrated control over the target email address.
    #
    # The next step is to call login_or_register_remote_user, but
    # there are two code paths here because of an optimization to save
    # a redirect on mobile and desktop.
    data_dict = ExternalAuthDataDict(
        subdomain=realm.subdomain,
        is_signup=is_signup,
        redirect_to=redirect_to,
        multiuse_object_key=multiuse_object_key,
        full_name_validated=full_name_validated,
        mobile_flow_otp=mobile_flow_otp,
        desktop_flow_otp=desktop_flow_otp,
    )
    if user_profile is None:
        data_dict.update(dict(full_name=full_name, email=email_address))

    result = ExternalAuthResult(user_profile=user_profile, data_dict=data_dict)

    if mobile_flow_otp or desktop_flow_otp:
        if user_profile is not None and not user_profile.is_mirror_dummy:
            # For mobile and desktop app authentication, login_or_register_remote_user
            # will redirect to a special zulip:// URL that is handled by
            # the app after a successful authentication; so we can
            # redirect directly from here, saving a round trip over what
            # we need to do to create session cookies on the right domain
            # in the web login flow (below).
            return login_or_register_remote_user(strategy.request, result)
        else:
            # The user needs to register, so we need to go the realm's
            # subdomain for that.
            pass

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
    return redirect_and_log_into_subdomain(result)

class SocialAuthMixin(ZulipAuthMixin, ExternalAuthMethod, BaseAuth):
    # Whether we expect that the full_name value obtained by the
    # social backend is definitely how the user should be referred to
    # in Zulip, which in turn determines whether we should always show
    # a registration form in the event with a default value of the
    # user's name when using this social backend so they can change
    # it.  For social backends like SAML that are expected to be a
    # central database, this should be True; for backends like GitHub
    # where the user might not have a name set or have it set to
    # something other than the name they will prefer to use in Zulip,
    # it should be False.
    full_name_validated = False

    standard_relay_params = settings.SOCIAL_AUTH_FIELDS_STORED_IN_SESSION + ['next']

    def auth_complete(self, *args: Any, **kwargs: Any) -> Optional[HttpResponse]:
        """This is a small wrapper around the core `auth_complete` method of
        python-social-auth, designed primarily to prevent 500s for
        exceptions in the social auth code from situations that are
        really user errors.  Returning `None` from this function will
        redirect the browser to the login page.
        """
        try:
            # Call the auth_complete method of social_core.backends.oauth.BaseOAuth2
            return super().auth_complete(*args, **kwargs)
        except (AuthFailed, HTTPError) as e:
            # When a user's social authentication fails (e.g. because
            # they did something funny with reloading in the middle of
            # the flow or the IdP is unreliable and returns a bad http response),
            # don't throw a 500, just send them back to the
            # login page and record the event at the info log level.
            self.logger.info("%s: %s", e.__class__.__name__, str(e))
            return None
        except SocialAuthBaseException as e:
            # Other python-social-auth exceptions are likely
            # interesting enough that we should log a warning.
            self.logger.warning(str(e))
            return None

    @classmethod
    def dict_representation(cls, realm: Optional[Realm]=None) -> List[ExternalAuthMethodDictT]:
        return [dict(
            name=cls.name,
            display_name=cls.auth_backend_name,
            display_icon=cls.display_icon,
            login_url=reverse('login-social', args=(cls.name,)),
            signup_url=reverse('signup-social', args=(cls.name,)),
        )]

@external_auth_method
class GitHubAuthBackend(SocialAuthMixin, GithubOAuth2):
    name = "github"
    auth_backend_name = "GitHub"
    sort_order = 100
    display_icon = "/static/images/landing-page/logos/github-icon.png"

    def get_all_associated_email_objects(self, *args: Any, **kwargs: Any) -> List[Dict[str, Any]]:
        access_token = kwargs["response"]["access_token"]
        try:
            emails = self._user_data(access_token, '/emails')
        except (HTTPError, ValueError, TypeError):  # nocoverage
            # We don't really need an explicit test for this code
            # path, since the outcome will be the same as any other
            # case without any verified emails
            emails = []
        return emails

    def get_unverified_emails(self, realm: Realm, *args: Any, **kwargs: Any) -> List[str]:
        return [
            email_obj['email'] for email_obj in self.get_usable_email_objects(realm, *args, **kwargs)
            if not email_obj.get('verified')
        ]

    def get_verified_emails(self, realm: Realm, *args: Any, **kwargs: Any) -> List[str]:
        # We only let users login using email addresses that are
        # verified by GitHub, because the whole point is for the user
        # to demonstrate that they control the target email address.
        verified_emails: List[str] = []
        for email_obj in [obj for obj in self.get_usable_email_objects(realm, *args, **kwargs)
                          if obj.get('verified')]:
            # social_associate_user_helper assumes that the first email in
            # verified_emails is primary.
            if email_obj.get("primary"):
                verified_emails.insert(0, email_obj["email"])
            else:
                verified_emails.append(email_obj["email"])

        return verified_emails

    def get_usable_email_objects(self, realm: Realm, *args: Any, **kwargs: Any) -> List[Dict[str, Any]]:
        # We disallow creation of new accounts with
        # @noreply.github.com/@users.noreply.github.com email
        # addresses, because structurally, we only want to allow email
        # addresses that can receive emails, and those cannot.

        # However, if an account with this address already exists in
        # the realm (which could happen e.g. as a result of data
        # import from another chat tool), we will allow signing in to
        # it.
        email_objs = self.get_all_associated_email_objects(*args, **kwargs)
        return [
            email for email in email_objs
            if (not email["email"].endswith("@users.noreply.github.com")
                or common_get_active_user(email["email"], realm) is not None)
        ]

    def user_data(self, access_token: str, *args: Any, **kwargs: Any) -> Dict[str, str]:
        """This patched user_data function lets us combine together the 3
        social auth backends into a single Zulip backend for GitHub OAuth2"""
        team_id = settings.SOCIAL_AUTH_GITHUB_TEAM_ID
        org_name = settings.SOCIAL_AUTH_GITHUB_ORG_NAME

        if team_id is None and org_name is None:
            # I believe this can't raise AuthFailed, so we don't try to catch it here.
            return super().user_data(
                access_token, *args, **kwargs,
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

@external_auth_method
class AzureADAuthBackend(SocialAuthMixin, AzureADOAuth2):
    sort_order = 50
    name = "azuread-oauth2"
    auth_backend_name = "AzureAD"
    display_icon = "/static/images/landing-page/logos/azuread-icon.png"

@external_auth_method
class GitLabAuthBackend(SocialAuthMixin, GitLabOAuth2):
    sort_order = 75
    name = "gitlab"
    auth_backend_name = "GitLab"
    display_icon = "/static/images/landing-page/logos/gitlab-icon.png"

    # Note: GitLab as of early 2020 supports having multiple email
    # addresses connected with a GitLab account, and we could access
    # those emails, but its APIs don't indicate which of those email
    # addresses were verified, so we cannot use them for
    # authentication like we do for the GitHub integration.  Instead,
    # we just use the primary email address, which is always verified.
    # (No code is required to do so, as that's the default behavior).

@external_auth_method
class GoogleAuthBackend(SocialAuthMixin, GoogleOAuth2):
    sort_order = 150
    auth_backend_name = "Google"
    name = "google"
    display_icon = "/static/images/landing-page/logos/googl_e-icon.png"

    def get_verified_emails(self, *args: Any, **kwargs: Any) -> List[str]:
        verified_emails: List[str] = []
        details = kwargs["response"]
        email_verified = details.get("email_verified")
        if email_verified:
            verified_emails.append(details["email"])
        return verified_emails

@external_auth_method
class AppleAuthBackend(SocialAuthMixin, AppleIdAuth):
    """
    Authentication backend for "Sign in with Apple".  This supports two flows:
    1. The web flow, usable in a browser, like our other social auth methods.
       It is a slightly modified Oauth2 authorization flow, where the response
       returning the access_token also contains a JWT id_token containing the user's
       identity, signed with Apple's private keys.
       https://developer.apple.com/documentation/sign_in_with_apple/tokenresponse
    2. The native flow, intended for users on an Apple device.  In the native flow,
       the device handles authentication of the user with Apple's servers and ends up
       with the JWT id_token (like in the web flow).  The client-side details aren't
       relevant to us; the app should simply send the id_token as a param to the
       /complete/apple/ endpoint, together with native_flow=true and any other
       appropriate params, such as mobile_flow_otp.
    """
    sort_order = 10
    name = "apple"
    auth_backend_name = "Apple"
    display_icon = "/static/images/landing-page/logos/apple-icon.png"

    # Apple only sends `name` in its response the first time a user
    # tries to sign up, so we won't have it in consecutive attempts.
    # But if Apple does send us the user's name, it will be validated,
    # so it's appropriate to set full_name_validated here.
    full_name_validated = True
    REDIS_EXPIRATION_SECONDS = 60*10

    SCOPE_SEPARATOR = "%20"  # https://github.com/python-social-auth/social-core/issues/470

    @classmethod
    def check_config(cls) -> Optional[HttpResponse]:
        obligatory_apple_settings_list = [
            settings.SOCIAL_AUTH_APPLE_TEAM,
            settings.SOCIAL_AUTH_APPLE_SERVICES_ID,
            settings.SOCIAL_AUTH_APPLE_KEY,
            settings.SOCIAL_AUTH_APPLE_SECRET,
        ]
        if any(not setting for setting in obligatory_apple_settings_list):
            return redirect_to_config_error("apple")

        return None

    def is_native_flow(self) -> bool:
        return self.strategy.request_data().get('native_flow', False)

    # This method replaces a method from python-social-auth; it is adapted to store
    # the state_token data in redis.
    def get_or_create_state(self) -> str:
        '''Creates the Oauth2 state parameter in first step of the flow,
        before redirecting the user to the IdP (aka Apple).

        Apple will send the user back to us with a POST
        request. Normally, we rely on being able to store certain
        parameters in the user's session and use them after the
        redirect.  But because we've configured our session cookies to
        use the Django default of in SameSite Lax mode, the browser
        won't send the session cookies to our server in delivering the
        POST request coming from Apple.

        To work around this, we replace python-social-auth's default
        session-based storage with storing the parameters in redis
        under a random token derived from the state. That will allow
        us to validate the state and retrieve the params after the
        redirect - by querying redis for the key derived from the
        state sent in the POST redirect.
        '''
        request_data = self.strategy.request_data().dict()
        data_to_store = {
            key: request_data[key] for key in self.standard_relay_params
            if key in request_data
        }

        # Generate a random string of 32 alphanumeric characters.
        state = self.state_token()
        put_dict_in_redis(redis_client, 'apple_auth_{token}',
                          data_to_store, self.REDIS_EXPIRATION_SECONDS,
                          token=state)
        return state

    def validate_state(self) -> Optional[str]:
        """
        This method replaces a method from python-social-auth; it is
        adapted to retrieve the data stored in redis, save it in
        the session so that it can be accessed by the social pipeline.
        """
        request_state = self.get_request_state()

        if not request_state:
            self.logger.info("Sign in with Apple failed: missing state parameter.")
            raise AuthMissingParameter(self, 'state')

        formatted_request_state = "apple_auth_" + request_state
        redis_data = get_dict_from_redis(redis_client, "apple_auth_{token}",
                                         formatted_request_state)
        if redis_data is None:
            self.logger.info("Sign in with Apple failed: bad state token.")
            raise AuthStateForbidden(self)

        for param, value in redis_data.items():
            if param in self.standard_relay_params:
                self.strategy.session_set(param, value)
        return request_state

    def auth_complete(self, *args: Any, **kwargs: Any) -> Optional[HttpResponse]:
        if not self.is_native_flow():
            # The default implementation in python-social-auth is the browser flow.
            return super().auth_complete(*args, **kwargs)

        # We handle the Apple's native flow on our own.  In this flow,
        # before contacting the server, the client obtains an id_token
        # from Apple directly, and then sends that to /complete/apple/
        # (the endpoint handled by this function), together with any
        # other desired parameters from self.standard_relay_params.
        #
        # What we'd like to do with the payload is just pass it into
        # the common code path for the web flow.  In the web flow,
        # before sending a request to Apple, python-social-auth sets
        # various values about the intended authentication in the
        # session, before the redirect.
        #
        # Thus, we need to set those session variables here, before
        # processing the id_token we received using the common do_auth.
        request_data = self.strategy.request_data()
        if 'id_token' not in request_data:
            raise JsonableError(_("Missing id_token parameter"))

        for param in self.standard_relay_params:
            self.strategy.session_set(param, request_data.get(param))

        # We should get the subdomain from the hostname of the request.
        self.strategy.session_set('subdomain', get_subdomain(self.strategy.request))

        try:
            # Things are now ready to be handled by the superclass code. It will
            # validate the id_token and push appropriate user data to the social pipeline.
            result = self.do_auth(request_data['id_token'], *args, **kwargs)
            return result
        except (AuthFailed, AuthCanceled) as e:
            # AuthFailed is a general "failure" exception from
            # python-social-auth that we should convert to None return
            # value here to avoid getting tracebacks.
            #
            # AuthCanceled is raised in the Apple backend
            # implementation in python-social-auth in certain cases,
            # though AuthFailed would have been more correct.
            #
            # We have an open PR to python-social-auth to clean this up.
            logging.info("/complete/apple/: %s", str(e))
            return None

@external_auth_method
class SAMLAuthBackend(SocialAuthMixin, SAMLAuth):
    auth_backend_name = "SAML"
    REDIS_EXPIRATION_SECONDS = 60 * 15
    SAMLRESPONSE_PARSING_EXCEPTIONS = (OneLogin_Saml2_Error, binascii.Error, XMLSyntaxError)
    name = "saml"
    # Organization which go through the trouble of setting up SAML are most likely
    # to have it as their main authentication method, so it seems appropriate to have
    # SAML buttons at the top.
    sort_order = 9999
    # There's no common default logo for SAML authentication.
    display_icon = None

    # The full_name provided by the IdP is very likely the standard
    # employee directory name for the user, and thus what they and
    # their organization want to use in Zulip.  So don't unnecessarily
    # provide a registration flow prompt for them to set their name.
    full_name_validated = True

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        if settings.SAML_REQUIRE_LIMIT_TO_SUBDOMAINS:
            idps_without_limit_to_subdomains = [
                idp_name for idp_name, idp_dict in settings.SOCIAL_AUTH_SAML_ENABLED_IDPS.items()
                if 'limit_to_subdomains' not in idp_dict
            ]
            if idps_without_limit_to_subdomains:
                self.logger.error("SAML_REQUIRE_LIMIT_TO_SUBDOMAINS is enabled and the following " +
                                  "IdPs don't have limit_to_subdomains specified and will be ignored: " +
                                  f"{idps_without_limit_to_subdomains}")
                for idp_name in idps_without_limit_to_subdomains:
                    del settings.SOCIAL_AUTH_SAML_ENABLED_IDPS[idp_name]
        super().__init__(*args, **kwargs)

    def auth_url(self) -> str:
        """Get the URL to which we must redirect in order to
        authenticate the user. Overriding the original SAMLAuth.auth_url.
        Runs when someone accesses the /login/saml/ endpoint."""
        try:
            idp_name = self.strategy.request_data()['idp']
            auth = self._create_saml_auth(idp=self.get_idp(idp_name))
        except KeyError as e:
            # If the above raise KeyError, it means invalid or no idp was specified,
            # we should log that and redirect to the login page.
            self.logger.info("/login/saml/ : Bad idp param: KeyError: %s.", str(e))
            return reverse('zerver.views.auth.login_page',
                           kwargs = {'template_name': 'zerver/login.html'})

        # This where we change things.  We need to pass some params
        # (`mobile_flow_otp`, `next`, etc.) through RelayState, which
        # then the IdP will pass back to us so we can read those
        # parameters in the final part of the authentication flow, at
        # the /complete/saml/ endpoint.
        #
        # To protect against network eavesdropping of these
        # parameters, we send just a random token to the IdP in
        # RelayState, which is used as a key into our redis data store
        # for fetching the actual parameters after the IdP has
        # returned a successful authentication.
        params_to_relay = self.standard_relay_params
        request_data = self.strategy.request_data().dict()
        data_to_relay = {
            key: request_data[key] for key in params_to_relay if key in request_data
        }
        relay_state = ujson.dumps({"state_token": self.put_data_in_redis(data_to_relay)})

        return auth.login(return_to=relay_state)

    @classmethod
    def put_data_in_redis(cls, data_to_relay: Dict[str, Any]) -> str:
        return put_dict_in_redis(redis_client, "saml_token_{token}",
                                 data_to_store=data_to_relay,
                                 expiration_seconds=cls.REDIS_EXPIRATION_SECONDS)

    @classmethod
    def get_data_from_redis(cls, key: str) -> Optional[Dict[str, Any]]:
        data = None
        if key.startswith('saml_token_'):
            # Safety if statement, to not allow someone to poke around arbitrary redis keys here.
            data = get_dict_from_redis(redis_client, "saml_token_{token}", key)

        return data

    def get_issuing_idp(self, SAMLResponse: str) -> Optional[str]:
        """
        Given a SAMLResponse, returns which of the configured IdPs is declared as the issuer.
        This value MUST NOT be trusted as the true issuer!
        The signatures are not validated, so it can be tampered with by the user.
        That's not a problem for this function,
        and true validation happens later in the underlying libraries, but it's important
        to note this detail. The purpose of this function is merely as a helper to figure out which
        of the configured IdPs' information to use for parsing and validating the response.
        """
        try:
            config = self.generate_saml_config()
            saml_settings = OneLogin_Saml2_Settings(config, sp_validation_only=True)
            resp = OneLogin_Saml2_Response(settings=saml_settings, response=SAMLResponse)
            issuers = resp.get_issuers()
        except self.SAMLRESPONSE_PARSING_EXCEPTIONS:
            self.logger.info("Error while parsing SAMLResponse:", exc_info=True)
            return None

        for idp_name, idp_config in settings.SOCIAL_AUTH_SAML_ENABLED_IDPS.items():
            if idp_config['entity_id'] in issuers:
                return idp_name

        return None

    def get_relayed_params(self) -> Dict[str, Any]:
        request_data = self.strategy.request_data()
        if 'RelayState' not in request_data:
            return {}

        relay_state = request_data['RelayState']
        try:
            data = ujson.loads(relay_state)
            if 'state_token' in data:
                # SP-initiated sign in. We stored relevant information in the first
                # step of the flow
                return self.get_data_from_redis(data['state_token']) or {}
            else:
                # IdP-initiated sign in. Right now we only support transporting subdomain through json in
                # RelayState, but this format is nice in that it allows easy extensibility here.
                return {'subdomain': data.get('subdomain')}
        except (ValueError, TypeError):
            return {}

    def choose_subdomain(self, relayed_params: Dict[str, Any]) -> Optional[str]:
        subdomain = relayed_params.get("subdomain")
        if subdomain is not None:
            return subdomain

        # If not specified otherwise, the intended subdomain for this
        # authentication attempt is the subdomain of the request.
        request_subdomain = get_subdomain(self.strategy.request)
        try:
            # We only want to do a basic sanity-check here for whether
            # this subdomain has a realm one could try to authenticate
            # to.  True validation of whether the realm is active, the
            # IdP is appropriate for the subdomain, etc. happens
            # elsewhere in the flow and we shouldn't duplicate such
            # logic here.
            get_realm(request_subdomain)
        except Realm.DoesNotExist:
            return None
        else:
            return request_subdomain

    def _check_entitlements(self, idp: SAMLIdentityProvider, attributes: Dict[str, List[str]]) -> None:
        """
        Below is the docstring from the social_core SAML backend.

        Additional verification of a SAML response before
        authenticating the user.

        Subclasses can override this method if they need custom
        validation code, such as requiring the presence of an
        eduPersonEntitlement.

        raise social_core.exceptions.AuthForbidden if the user should not
        be authenticated, or do nothing to allow the login pipeline to
        continue.
        """
        org_membership_attribute = idp.conf.get('attr_org_membership', None)
        if org_membership_attribute is None:
            return

        subdomain = self.strategy.session_get('subdomain')
        entitlements: Union[str, List[str]] = attributes.get(org_membership_attribute, [])
        if subdomain in entitlements:
            return

        # The root subdomain is a special case, as sending an
        # empty string in the list of values of the attribute may
        # not be viable. So, any of the ROOT_SUBDOMAIN_ALIASES can
        # be used to signify the user is authorized for the root
        # subdomain.
        if (subdomain == Realm.SUBDOMAIN_FOR_ROOT_DOMAIN
                and not settings.ROOT_DOMAIN_LANDING_PAGE
                and any(alias in entitlements for alias in settings.ROOT_SUBDOMAIN_ALIASES)):
            return

        error_msg = f"SAML user from IdP {idp.name} rejected due to missing entitlement " + \
                    f"for subdomain '{subdomain}'. User entitlements: {entitlements}."
        raise AuthFailed(self, error_msg)

    def auth_complete(self, *args: Any, **kwargs: Any) -> Optional[HttpResponse]:
        """
        Additional ugly wrapping on top of auth_complete in SocialAuthMixin.
        We handle two things here:
            1. Working around bad RelayState or SAMLResponse parameters in the request.
            Both parameters should be present if the user came to /complete/saml/ through
            the IdP as intended. The errors can happen if someone simply types the endpoint into
            their browsers, or generally tries messing with it in some ways.

            2. The first part of our SAML authentication flow will encode important parameters
            into the RelayState. We need to read them and set those values in the session,
            and then change the RelayState param to the idp_name, because that's what
            SAMLAuth.auth_complete() expects.
        """
        SAMLResponse = self.strategy.request_data().get('SAMLResponse')
        if SAMLResponse is None:
            self.logger.info("/complete/saml/: No SAMLResponse in request.")
            return None

        relayed_params = self.get_relayed_params()

        subdomain = self.choose_subdomain(relayed_params)
        if subdomain is None:
            error_msg = "/complete/saml/: Can't figure out subdomain for this authentication request. " + \
                "relayed_params: %s"
            self.logger.info(error_msg, relayed_params)
            return None

        idp_name = self.get_issuing_idp(SAMLResponse)
        if idp_name is None:
            self.logger.info("/complete/saml/: No valid IdP as issuer of the SAMLResponse.")
            return None

        idp_valid = self.validate_idp_for_subdomain(idp_name, subdomain)
        if not idp_valid:
            error_msg = "/complete/saml/: Authentication request with IdP %s but this provider is not " + \
                        "enabled for this subdomain %s."
            self.logger.info(error_msg, idp_name, subdomain)
            return None

        result = None
        try:
            params = relayed_params.copy()
            params['subdomain'] = subdomain
            for param, value in params.items():
                if param in self.standard_relay_params:
                    self.strategy.session_set(param, value)

            # super().auth_complete expects to have RelayState set to the idp_name,
            # so we need to replace this param.
            post_params = self.strategy.request.POST.copy()
            post_params['RelayState'] = idp_name
            self.strategy.request.POST = post_params

            # Call the auth_complete method of SocialAuthMixIn
            result = super().auth_complete(*args, **kwargs)
        except self.SAMLRESPONSE_PARSING_EXCEPTIONS:
            # These can be raised if SAMLResponse is missing or badly formatted.
            self.logger.info("/complete/saml/: error while parsing SAMLResponse:", exc_info=True)
            # Fall through to returning None.
        finally:
            if result is None:
                for param in self.standard_relay_params:
                    # If an attacker managed to eavesdrop on the RelayState token,
                    # they may pass it here to the endpoint with an invalid SAMLResponse.
                    # We remove these potentially sensitive parameters that we have set in the session
                    # earlier, to avoid leaking their values.
                    self.strategy.session_set(param, None)

        return result

    @classmethod
    def validate_idp_for_subdomain(cls, idp_name: str, subdomain: str) -> bool:
        idp_dict = settings.SOCIAL_AUTH_SAML_ENABLED_IDPS.get(idp_name)
        if idp_dict is None:
            raise AssertionError(f"IdP: {idp_name} not found")
        if 'limit_to_subdomains' in idp_dict and subdomain not in idp_dict['limit_to_subdomains']:
            return False

        return True

    @classmethod
    def check_config(cls) -> Optional[HttpResponse]:
        obligatory_saml_settings_list = [
            settings.SOCIAL_AUTH_SAML_SP_ENTITY_ID,
            settings.SOCIAL_AUTH_SAML_ORG_INFO,
            settings.SOCIAL_AUTH_SAML_TECHNICAL_CONTACT,
            settings.SOCIAL_AUTH_SAML_SUPPORT_CONTACT,
            settings.SOCIAL_AUTH_SAML_ENABLED_IDPS,
        ]
        if any(not setting for setting in obligatory_saml_settings_list):
            return redirect_to_config_error("saml")

        return None

    @classmethod
    def dict_representation(cls, realm: Optional[Realm]=None) -> List[ExternalAuthMethodDictT]:
        result: List[ExternalAuthMethodDictT] = []
        for idp_name, idp_dict in settings.SOCIAL_AUTH_SAML_ENABLED_IDPS.items():
            if realm and not cls.validate_idp_for_subdomain(idp_name, realm.subdomain):
                continue
            if realm is None and 'limit_to_subdomains' in idp_dict:
                # If queried without a realm, only return IdPs that can be used on all realms.
                continue

            saml_dict: ExternalAuthMethodDictT = dict(
                name=f'saml:{idp_name}',
                display_name=idp_dict.get('display_name', cls.auth_backend_name),
                display_icon=idp_dict.get('display_icon', cls.display_icon),
                login_url=reverse('login-social-extra-arg', args=('saml', idp_name)),
                signup_url=reverse('signup-social-extra-arg', args=('saml', idp_name)),
            )
            result.append(saml_dict)

        return result

def validate_otp_params(mobile_flow_otp: Optional[str]=None,
                        desktop_flow_otp: Optional[str]=None) -> None:
    for otp in [mobile_flow_otp, desktop_flow_otp]:
        if otp is not None and not is_valid_otp(otp):
            raise JsonableError(_("Invalid OTP"))

    if mobile_flow_otp and desktop_flow_otp:
        raise JsonableError(_("Can't use both mobile_flow_otp and desktop_flow_otp together."))

def get_external_method_dicts(realm: Optional[Realm]=None) -> List[ExternalAuthMethodDictT]:
    """
    Returns a list of dictionaries that represent social backends, sorted
    in the order in which they should be displayed.
    """
    result: List[ExternalAuthMethodDictT] = []
    for backend in EXTERNAL_AUTH_METHODS:
        # EXTERNAL_AUTH_METHODS is already sorted in the correct order,
        # so we don't need to worry about sorting here.
        if auth_enabled_helper([backend.auth_backend_name], realm):
            result.extend(backend.dict_representation(realm))

    return result

AUTH_BACKEND_NAME_MAP: Dict[str, Any] = {
    'Dev': DevAuthBackend,
    'Email': EmailAuthBackend,
    'LDAP': ZulipLDAPAuthBackend,
}

for external_method in EXTERNAL_AUTH_METHODS:
    AUTH_BACKEND_NAME_MAP[external_method.auth_backend_name] = external_method

EXTERNAL_AUTH_METHODS = sorted(EXTERNAL_AUTH_METHODS, key=lambda x: x.sort_order, reverse=True)

# Provide this alternative name for backwards compatibility with
# installations that had the old backend enabled.
GoogleMobileOauth2Backend = GoogleAuthBackend
