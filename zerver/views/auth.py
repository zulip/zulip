import logging
import secrets
import urllib
from email.headerregistry import Address
from functools import wraps
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Mapping, Optional, cast
from urllib.parse import urlencode

import jwt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.views import LoginView as DjangoLoginView
from django.contrib.auth.views import PasswordResetView as DjangoPasswordResetView
from django.contrib.auth.views import logout_then_login as django_logout_then_login
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.forms import Form
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect, HttpResponseServerError
from django.shortcuts import redirect, render
from django.template.response import SimpleTemplateResponse
from django.urls import reverse
from django.utils.html import escape
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_safe
from markupsafe import Markup
from social_django.utils import load_backend, load_strategy
from two_factor.forms import BackupTokenForm
from two_factor.views import LoginView as BaseTwoFactorLoginView
from typing_extensions import Concatenate, ParamSpec

from confirmation.models import (
    Confirmation,
    ConfirmationKeyError,
    create_confirmation_link,
    get_object_from_key,
    render_confirmation_key_error,
)
from version import API_FEATURE_LEVEL, ZULIP_MERGE_BASE, ZULIP_VERSION
from zerver.context_processors import get_realm_from_request, login_context, zulip_default_context
from zerver.decorator import do_login, log_view_func, process_client, require_post
from zerver.forms import (
    DEACTIVATED_ACCOUNT_ERROR,
    AuthenticationTokenForm,
    HomepageForm,
    OurAuthenticationForm,
    ZulipPasswordResetForm,
)
from zerver.lib.exceptions import (
    AuthenticationFailedError,
    InvalidSubdomainError,
    JsonableError,
    PasswordAuthDisabledError,
    PasswordResetRequiredError,
    RateLimitedError,
    RealmDeactivatedError,
    UserDeactivatedError,
)
from zerver.lib.mobile_auth_otp import otp_encrypt_api_key
from zerver.lib.push_notifications import push_notifications_enabled
from zerver.lib.pysa import mark_sanitized
from zerver.lib.realm_icon import realm_icon_url
from zerver.lib.request import REQ, RequestNotes, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.sessions import set_expirable_session_var
from zerver.lib.subdomains import get_subdomain, is_subdomain_root_or_alias
from zerver.lib.url_encoding import append_url_query_string
from zerver.lib.user_agent import parse_user_agent
from zerver.lib.users import get_api_key, is_2fa_verified
from zerver.lib.utils import has_api_key_format
from zerver.lib.validator import validate_login_email
from zerver.models import (
    MultiuseInvite,
    PreregistrationUser,
    Realm,
    UserProfile,
    filter_to_valid_prereg_users,
    get_realm,
    remote_user_to_email,
)
from zerver.signals import email_on_new_login
from zproject.backends import (
    AUTH_BACKEND_NAME_MAP,
    AppleAuthBackend,
    ExternalAuthDataDict,
    ExternalAuthResult,
    GenericOpenIdConnectBackend,
    SAMLAuthBackend,
    ZulipLDAPAuthBackend,
    ZulipLDAPConfigurationError,
    ZulipRemoteUserBackend,
    auth_enabled_helper,
    dev_auth_enabled,
    ldap_auth_enabled,
    password_auth_enabled,
    saml_auth_enabled,
    validate_otp_params,
)

if TYPE_CHECKING:
    from django.http.request import _ImmutableQueryDict

ParamT = ParamSpec("ParamT")
ExtraContext = Optional[Dict[str, Any]]


def get_safe_redirect_to(url: str, redirect_host: str) -> str:
    is_url_safe = url_has_allowed_host_and_scheme(url=url, allowed_hosts=None)
    if is_url_safe:
        # Mark as safe to prevent Pysa from surfacing false positives for
        # open redirects. In this branch, we have already checked that the URL
        # points to the specified 'redirect_host', or is relative.
        return urllib.parse.urljoin(redirect_host, mark_sanitized(url))
    else:
        return redirect_host


def create_preregistration_user(
    email: str,
    realm: Optional[Realm],
    realm_creation: bool = False,
    password_required: bool = True,
    full_name: Optional[str] = None,
    full_name_validated: bool = False,
    multiuse_invite: Optional[MultiuseInvite] = None,
) -> PreregistrationUser:
    assert not (realm_creation and realm is not None)
    assert not (realm is None and not realm_creation)

    return PreregistrationUser.objects.create(
        email=email,
        realm_creation=realm_creation,
        password_required=password_required,
        realm=realm,
        full_name=full_name,
        full_name_validated=full_name_validated,
        multiuse_invite=multiuse_invite,
    )


def maybe_send_to_registration(
    request: HttpRequest,
    email: str,
    full_name: str = "",
    mobile_flow_otp: Optional[str] = None,
    desktop_flow_otp: Optional[str] = None,
    is_signup: bool = False,
    multiuse_object_key: str = "",
    full_name_validated: bool = False,
) -> HttpResponse:
    """Given a successful authentication for an email address (i.e. we've
    confirmed the user controls the email address) that does not
    currently have a Zulip account in the target realm, send them to
    the registration flow or the "continue to registration" flow,
    depending on is_signup, whether the email address can join the
    organization (checked in HomepageForm), and similar details.
    """

    # In the desktop and mobile registration flows, the sign up
    # happens in the browser so the user can use their
    # already-logged-in social accounts.  Then at the end, with the
    # user account created, we pass the appropriate data to the app
    # via e.g. a `zulip://` redirect.  We store the OTP keys for the
    # mobile/desktop flow in the session with 1-hour expiry, because
    # we want this configuration of having a successful authentication
    # result in being logged into the app to persist if the user makes
    # mistakes while trying to authenticate (E.g. clicks the wrong
    # Google account, hits back, etc.) during a given browser session,
    # rather than just logging into the web app in the target browser.
    #
    # We can't use our usual pre-account-creation state storage
    # approach of putting something in PreregistrationUser, because
    # that would apply to future registration attempts on other
    # devices, e.g. just creating an account on the web on their laptop.
    assert not (mobile_flow_otp and desktop_flow_otp)
    if mobile_flow_otp:
        set_expirable_session_var(
            request.session, "registration_mobile_flow_otp", mobile_flow_otp, expiry_seconds=3600
        )
    elif desktop_flow_otp:
        set_expirable_session_var(
            request.session, "registration_desktop_flow_otp", desktop_flow_otp, expiry_seconds=3600
        )

    try:
        # TODO: This should use get_realm_from_request, but a bunch of tests
        # rely on mocking get_subdomain here, so they'll need to be tweaked first.
        realm: Optional[Realm] = get_realm(get_subdomain(request))
    except Realm.DoesNotExist:
        realm = None

    multiuse_obj: Optional[MultiuseInvite] = None
    from_multiuse_invite = False
    if multiuse_object_key:
        from_multiuse_invite = True
        try:
            confirmation_obj = get_object_from_key(
                multiuse_object_key, [Confirmation.MULTIUSE_INVITE], mark_object_used=False
            )
        except ConfirmationKeyError as exception:
            return render_confirmation_key_error(request, exception)

        assert isinstance(confirmation_obj, MultiuseInvite)
        multiuse_obj = confirmation_obj
        if realm != multiuse_obj.realm:
            return render(request, "confirmation/link_does_not_exist.html", status=404)

        invited_as = multiuse_obj.invited_as
    else:
        invited_as = PreregistrationUser.INVITE_AS["MEMBER"]

    form = HomepageForm(
        {"email": email},
        realm=realm,
        from_multiuse_invite=from_multiuse_invite,
        invited_as=invited_as,
    )
    if form.is_valid():
        # If the email address is allowed to sign up for an account in
        # this organization, construct a PreregistrationUser and
        # Confirmation objects, and then send the user to account
        # creation or confirm-continue-registration depending on
        # is_signup.
        try:
            # If there's an existing, valid PreregistrationUser for this
            # user, we want to fetch it since some values from it will be used
            # as defaults for creating the signed up user.
            existing_prereg_user = filter_to_valid_prereg_users(
                PreregistrationUser.objects.filter(email__iexact=email, realm=realm)
            ).latest("invited_at")
        except PreregistrationUser.DoesNotExist:
            existing_prereg_user = None

        # full_name data passed here as argument should take precedence
        # over the defaults with which the existing PreregistrationUser that we've just fetched
        # was created.
        prereg_user = create_preregistration_user(
            email,
            realm,
            password_required=False,
            full_name=full_name,
            full_name_validated=full_name_validated,
            multiuse_invite=multiuse_obj,
        )

        streams_to_subscribe = None
        if multiuse_obj is not None:
            # If the user came here explicitly via a multiuse invite link, then
            # we use the defaults implied by the invite.
            streams_to_subscribe = list(multiuse_obj.streams.all())
        elif existing_prereg_user:
            # Otherwise, the user is doing this signup not via any invite link,
            # but we can use the pre-existing PreregistrationUser for these values
            # since it tells how they were intended to be, when the user was invited.
            streams_to_subscribe = list(existing_prereg_user.streams.all())
            invited_as = existing_prereg_user.invited_as

        if streams_to_subscribe:
            prereg_user.streams.set(streams_to_subscribe)
        prereg_user.invited_as = invited_as
        prereg_user.multiuse_invite = multiuse_obj
        prereg_user.save()

        confirmation_link = create_confirmation_link(prereg_user, Confirmation.USER_REGISTRATION)
        if is_signup:
            return redirect(confirmation_link)

        context = {"email": email, "continue_link": confirmation_link, "full_name": full_name}
        return render(request, "zerver/confirm_continue_registration.html", context=context)

    # This email address it not allowed to join this organization, so
    # just send the user back to the registration page.
    url = reverse("register")
    context = login_context(request)
    extra_context: Mapping[str, Any] = {
        "form": form,
        "current_url": lambda: url,
        "from_multiuse_invite": from_multiuse_invite,
        "multiuse_object_key": multiuse_object_key,
        "mobile_flow_otp": mobile_flow_otp,
        "desktop_flow_otp": desktop_flow_otp,
    }
    context.update(extra_context)
    return render(request, "zerver/accounts_home.html", context=context)


def register_remote_user(request: HttpRequest, result: ExternalAuthResult) -> HttpResponse:
    # We have verified the user controls an email address, but
    # there's no associated Zulip user account.  Consider sending
    # the request to registration.
    kwargs: Dict[str, Any] = dict(result.data_dict)
    # maybe_send_to_registration doesn't take these arguments, so delete them.
    kwargs.pop("subdomain", None)
    kwargs.pop("redirect_to", None)
    kwargs.pop("is_realm_creation", None)

    return maybe_send_to_registration(request, **kwargs)


def login_or_register_remote_user(request: HttpRequest, result: ExternalAuthResult) -> HttpResponse:
    """Given a successful authentication showing the user controls given
    email address (email) and potentially a UserProfile
    object (if the user already has a Zulip account), redirect the
    browser to the appropriate place:

    * The logged-in app if the user already has a Zulip account and is
      trying to log in, potentially to an initial narrow or page that had been
      saved in the `redirect_to` parameter.
    * The registration form if is_signup was set (i.e. the user is
      trying to create a Zulip account)
    * A special `confirm_continue_registration.html` "do you want to
      register or try another account" if the user doesn't have a
      Zulip account but is_signup is False (i.e. the user tried to log in
      and then did social authentication selecting an email address that does
      not have a Zulip account in this organization).
    * A zulip:// URL to send control back to the mobile or desktop apps if they
      are doing authentication using the mobile_flow_otp or desktop_flow_otp flow.
    """
    user_profile = result.user_profile
    if user_profile is None or user_profile.is_mirror_dummy:
        return register_remote_user(request, result)
    # Otherwise, the user has successfully authenticated to an
    # account, and we need to do the right thing depending whether
    # or not they're using the mobile OTP flow or want a browser session.
    is_realm_creation = result.data_dict.get("is_realm_creation")
    mobile_flow_otp = result.data_dict.get("mobile_flow_otp")
    desktop_flow_otp = result.data_dict.get("desktop_flow_otp")
    if mobile_flow_otp is not None:
        return finish_mobile_flow(request, user_profile, mobile_flow_otp)
    elif desktop_flow_otp is not None:
        return finish_desktop_flow(request, user_profile, desktop_flow_otp)

    do_login(request, user_profile)

    redirect_to = result.data_dict.get("redirect_to", "")
    if is_realm_creation is not None and settings.BILLING_ENABLED:
        from corporate.lib.stripe import is_free_trial_offer_enabled

        if is_free_trial_offer_enabled():
            redirect_to = "{}?onboarding=true".format(reverse("initial_upgrade"))

    redirect_to = get_safe_redirect_to(redirect_to, user_profile.realm.uri)
    return HttpResponseRedirect(redirect_to)


def finish_desktop_flow(request: HttpRequest, user_profile: UserProfile, otp: str) -> HttpResponse:
    """
    The desktop otp flow returns to the app (through the clipboard)
    a token that allows obtaining (through log_into_subdomain) a logged in session
    for the user account we authenticated in this flow.
    The token can only be used once and within ExternalAuthResult.LOGIN_KEY_EXPIRATION_SECONDS
    of being created, as nothing more powerful is needed for the desktop flow
    and this ensures the key can only be used for completing this authentication attempt.
    """
    result = ExternalAuthResult(user_profile=user_profile)
    token = result.store_data()
    key = bytes.fromhex(otp)
    iv = secrets.token_bytes(12)
    desktop_data = (iv + AESGCM(key).encrypt(iv, token.encode(), b"")).hex()
    context = {
        "desktop_data": desktop_data,
        "browser_url": reverse("login_page", kwargs={"template_name": "zerver/login.html"}),
        "realm_icon_url": realm_icon_url(user_profile.realm),
    }
    return render(request, "zerver/desktop_redirect.html", context=context)


def finish_mobile_flow(request: HttpRequest, user_profile: UserProfile, otp: str) -> HttpResponse:
    # For the mobile OAuth flow, we send the API key and other
    # necessary details in a redirect to a zulip:// URI scheme.
    api_key = get_api_key(user_profile)
    response = create_response_for_otp_flow(
        api_key, otp, user_profile, encrypted_key_field_name="otp_encrypted_api_key"
    )

    # Since we are returning an API key instead of going through
    # the Django login() function (which creates a browser
    # session, etc.), the "new login" signal handler (which
    # triggers an email notification new logins) will not run
    # automatically.  So we call it manually here.
    #
    # Arguably, sending a fake 'user_logged_in' signal would be a better approach:
    #   user_logged_in.send(sender=type(user_profile), request=request, user=user_profile)
    email_on_new_login(sender=type(user_profile), request=request, user=user_profile)

    # Mark this request as having a logged-in user for our server logs.
    process_client(request, user_profile)
    RequestNotes.get_notes(request).requestor_for_logs = user_profile.format_requestor_for_logs()

    return response


def create_response_for_otp_flow(
    key: str, otp: str, user_profile: UserProfile, encrypted_key_field_name: str
) -> HttpResponse:
    realm_uri = user_profile.realm.uri

    # Check if the mobile URI is overridden in settings, if so, replace it
    # This block should only apply to the mobile flow, so we if add others, this
    # needs to be conditional.
    if realm_uri in settings.REALM_MOBILE_REMAP_URIS:
        realm_uri = settings.REALM_MOBILE_REMAP_URIS[realm_uri]

    params = {
        encrypted_key_field_name: otp_encrypt_api_key(key, otp),
        "email": user_profile.delivery_email,
        "user_id": user_profile.id,
        "realm": realm_uri,
    }
    # We can't use HttpResponseRedirect, since it only allows HTTP(S) URLs
    response = HttpResponse(status=302)
    response["Location"] = append_url_query_string("zulip://login", urllib.parse.urlencode(params))

    return response


@log_view_func
@has_request_variables
def remote_user_sso(
    request: HttpRequest,
    mobile_flow_otp: Optional[str] = REQ(default=None),
    desktop_flow_otp: Optional[str] = REQ(default=None),
    next: str = REQ(default="/"),
) -> HttpResponse:
    subdomain = get_subdomain(request)
    try:
        realm: Optional[Realm] = get_realm(subdomain)
    except Realm.DoesNotExist:
        realm = None

    if not auth_enabled_helper([ZulipRemoteUserBackend.auth_backend_name], realm):
        return config_error(request, "remote_user_backend_disabled")

    try:
        remote_user = request.META["REMOTE_USER"]
    except KeyError:
        return config_error(request, "remote_user_header_missing")

    # Django invokes authenticate methods by matching arguments, and this
    # authentication flow will not invoke LDAP authentication because of
    # this condition of Django so no need to check if LDAP backend is
    # enabled.
    validate_login_email(remote_user_to_email(remote_user))

    # Here we support the mobile and desktop flow for REMOTE_USER_BACKEND; we
    # validate the data format and then pass it through to
    # login_or_register_remote_user if appropriate.
    validate_otp_params(mobile_flow_otp, desktop_flow_otp)

    if realm is None:
        user_profile = None
    else:
        user_profile = authenticate(remote_user=remote_user, realm=realm)
    if user_profile is not None:
        assert isinstance(user_profile, UserProfile)

    email = remote_user_to_email(remote_user)
    data_dict = ExternalAuthDataDict(
        email=email,
        mobile_flow_otp=mobile_flow_otp,
        desktop_flow_otp=desktop_flow_otp,
        redirect_to=next,
    )
    if realm:
        data_dict["subdomain"] = realm.subdomain
    else:
        data_dict["subdomain"] = ""  # realm creation happens on root subdomain
    result = ExternalAuthResult(user_profile=user_profile, data_dict=data_dict)
    return login_or_register_remote_user(request, result)


@csrf_exempt
@log_view_func
def remote_user_jwt(request: HttpRequest) -> HttpResponse:
    subdomain = get_subdomain(request)
    try:
        key = settings.JWT_AUTH_KEYS[subdomain]["key"]
        algorithms = settings.JWT_AUTH_KEYS[subdomain]["algorithms"]
    except KeyError:
        raise JsonableError(_("Auth key for this subdomain not found."))

    try:
        json_web_token = request.POST["json_web_token"]
        options = {"verify_signature": True}
        payload = jwt.decode(json_web_token, key, algorithms=algorithms, options=options)
    except KeyError:
        raise JsonableError(_("No JSON web token passed in request"))
    except jwt.InvalidTokenError:
        raise JsonableError(_("Bad JSON web token"))

    remote_user = payload.get("user", None)
    if remote_user is None:
        raise JsonableError(_("No user specified in JSON web token claims"))
    email_domain = payload.get("realm", None)
    if email_domain is None:
        raise JsonableError(_("No organization specified in JSON web token claims"))

    email = Address(username=remote_user, domain=email_domain).addr_spec

    try:
        realm = get_realm(subdomain)
    except Realm.DoesNotExist:
        raise JsonableError(_("Wrong subdomain"))

    user_profile = authenticate(username=email, realm=realm, use_dummy_backend=True)
    if user_profile is None:
        result = ExternalAuthResult(
            data_dict={"email": email, "full_name": remote_user, "subdomain": realm.subdomain}
        )
    else:
        assert isinstance(user_profile, UserProfile)
        result = ExternalAuthResult(user_profile=user_profile)

    return login_or_register_remote_user(request, result)


@has_request_variables
def oauth_redirect_to_root(
    request: HttpRequest,
    url: str,
    sso_type: str,
    is_signup: bool = False,
    extra_url_params: Mapping[str, str] = {},
    next: Optional[str] = REQ(default=None),
    multiuse_object_key: str = REQ(default=""),
    mobile_flow_otp: Optional[str] = REQ(default=None),
    desktop_flow_otp: Optional[str] = REQ(default=None),
) -> HttpResponse:
    main_site_uri = settings.ROOT_DOMAIN_URI + url
    if settings.SOCIAL_AUTH_SUBDOMAIN is not None and sso_type == "social":
        main_site_uri = (
            settings.EXTERNAL_URI_SCHEME
            + settings.SOCIAL_AUTH_SUBDOMAIN
            + "."
            + settings.EXTERNAL_HOST
        ) + url

    params = {
        "subdomain": get_subdomain(request),
        "is_signup": "1" if is_signup else "0",
    }

    params["multiuse_object_key"] = multiuse_object_key

    # mobile_flow_otp is a one-time pad provided by the app that we
    # can use to encrypt the API key when passing back to the app.
    validate_otp_params(mobile_flow_otp, desktop_flow_otp)
    if mobile_flow_otp is not None:
        params["mobile_flow_otp"] = mobile_flow_otp
    if desktop_flow_otp is not None:
        params["desktop_flow_otp"] = desktop_flow_otp

    if next:
        params["next"] = next

    params = {**params, **extra_url_params}

    return redirect(append_url_query_string(main_site_uri, urllib.parse.urlencode(params)))


def handle_desktop_flow(
    func: Callable[Concatenate[HttpRequest, ParamT], HttpResponse]
) -> Callable[Concatenate[HttpRequest, ParamT], HttpResponse]:
    @wraps(func)
    def wrapper(
        request: HttpRequest, /, *args: ParamT.args, **kwargs: ParamT.kwargs
    ) -> HttpResponse:
        user_agent = parse_user_agent(request.headers.get("User-Agent", "Missing User-Agent"))
        if user_agent["name"] == "ZulipElectron":
            return render(request, "zerver/desktop_login.html")

        return func(request, *args, **kwargs)

    return wrapper


@handle_desktop_flow
def start_remote_user_sso(request: HttpRequest) -> HttpResponse:
    """
    The purpose of this endpoint is to provide an initial step in the flow
    on which we can handle the special behavior for the desktop app.
    /accounts/login/sso may have Apache intercepting requests to it
    to do authentication, so we need this additional endpoint.
    """
    query = request.META["QUERY_STRING"]
    return redirect(append_url_query_string(reverse(remote_user_sso), query))


@handle_desktop_flow
def start_social_login(
    request: HttpRequest,
    backend: str,
    extra_arg: Optional[str] = None,
) -> HttpResponse:
    backend_url = reverse("social:begin", args=[backend])
    extra_url_params: Dict[str, str] = {}
    if backend == "saml":
        if not SAMLAuthBackend.check_config():
            return config_error(request, "saml")

        # This backend requires the name of the IdP (from the list of configured ones)
        # to be passed as the parameter.
        if not extra_arg or extra_arg not in settings.SOCIAL_AUTH_SAML_ENABLED_IDPS:
            logging.info(
                "Attempted to initiate SAML authentication with wrong idp argument: %s", extra_arg
            )
            return config_error(request, "saml")
        extra_url_params = {"idp": extra_arg}

    if backend == "apple" and not AppleAuthBackend.check_config():
        return config_error(request, "apple")
    if backend == "oidc" and not GenericOpenIdConnectBackend.check_config():
        return config_error(request, "oidc")

    # TODO: Add AzureAD also.
    if backend in ["github", "google", "gitlab"]:
        key_setting = "SOCIAL_AUTH_" + backend.upper() + "_KEY"
        secret_setting = "SOCIAL_AUTH_" + backend.upper() + "_SECRET"
        if not (getattr(settings, key_setting) and getattr(settings, secret_setting)):
            return config_error(request, backend)

    return oauth_redirect_to_root(request, backend_url, "social", extra_url_params=extra_url_params)


@handle_desktop_flow
def start_social_signup(
    request: HttpRequest,
    backend: str,
    extra_arg: Optional[str] = None,
) -> HttpResponse:
    backend_url = reverse("social:begin", args=[backend])
    extra_url_params: Dict[str, str] = {}
    if backend == "saml":
        if not SAMLAuthBackend.check_config():
            return config_error(request, "saml")

        if not extra_arg or extra_arg not in settings.SOCIAL_AUTH_SAML_ENABLED_IDPS:
            logging.info(
                "Attempted to initiate SAML authentication with wrong idp argument: %s", extra_arg
            )
            return config_error(request, "saml")
        extra_url_params = {"idp": extra_arg}
    return oauth_redirect_to_root(
        request, backend_url, "social", is_signup=True, extra_url_params=extra_url_params
    )


_subdomain_token_salt = "zerver.views.auth.log_into_subdomain"


@log_view_func
def log_into_subdomain(request: HttpRequest, token: str) -> HttpResponse:
    """Given a valid authentication token (generated by
    redirect_and_log_into_subdomain called on auth.zulip.example.com),
    call login_or_register_remote_user, passing all the authentication
    result data that has been stored in Redis, associated with this token.
    """
    # The tokens are intended to have the same format as API keys.
    if not has_api_key_format(token):
        logging.warning("log_into_subdomain: Malformed token given: %s", token)
        return HttpResponse(status=400)

    try:
        result = ExternalAuthResult(login_token=token)
    except ExternalAuthResult.InvalidTokenError:
        logging.warning("log_into_subdomain: Invalid token given: %s", token)
        return render(request, "zerver/log_into_subdomain_token_invalid.html", status=400)

    subdomain = get_subdomain(request)
    if result.data_dict["subdomain"] != subdomain:
        raise JsonableError(_("Invalid subdomain"))

    return login_or_register_remote_user(request, result)


def redirect_and_log_into_subdomain(result: ExternalAuthResult) -> HttpResponse:
    token = result.store_data()
    realm = get_realm(result.data_dict["subdomain"])
    subdomain_login_uri = realm.uri + reverse(log_into_subdomain, args=[token])
    return redirect(subdomain_login_uri)


def redirect_to_misconfigured_ldap_notice(request: HttpRequest, error_type: int) -> HttpResponse:
    if error_type == ZulipLDAPAuthBackend.REALM_IS_NONE_ERROR:
        return config_error(request, "ldap")
    else:
        raise AssertionError("Invalid error type")


def show_deactivation_notice(request: HttpRequest) -> HttpResponse:
    realm = get_realm_from_request(request)
    if realm and realm.deactivated:
        context = {"deactivated_domain_name": realm.name}
        if realm.deactivated_redirect is not None:
            context["deactivated_redirect"] = realm.deactivated_redirect
        return render(request, "zerver/deactivated.html", context=context)

    return HttpResponseRedirect(reverse("login_page"))


def redirect_to_deactivation_notice() -> HttpResponse:
    return HttpResponseRedirect(reverse(show_deactivation_notice))


def update_login_page_context(request: HttpRequest, context: Dict[str, Any]) -> None:
    for key in ("email", "already_registered"):
        try:
            context[key] = request.GET[key]
        except KeyError:
            pass

    deactivated_email = request.GET.get("is_deactivated")
    if deactivated_email is None:
        return
    try:
        validate_email(deactivated_email)
        context["deactivated_account_error"] = Markup(
            DEACTIVATED_ACCOUNT_ERROR.format(username=escape(deactivated_email))
        )
    except ValidationError:
        logging.info("Invalid email in is_deactivated param to login page: %s", deactivated_email)


class TwoFactorLoginView(BaseTwoFactorLoginView):
    extra_context: ExtraContext = None
    form_list = (
        ("auth", OurAuthenticationForm),
        ("token", AuthenticationTokenForm),
        ("backup", BackupTokenForm),
    )

    def __init__(self, extra_context: ExtraContext = None, *args: Any, **kwargs: Any) -> None:
        self.extra_context = extra_context
        super().__init__(*args, **kwargs)

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        if self.extra_context is not None:
            context.update(self.extra_context)
        update_login_page_context(self.request, context)

        realm = get_realm_from_request(self.request)
        redirect_to = realm.uri if realm else "/"
        context["next"] = self.request.POST.get(
            "next",
            self.request.GET.get("next", redirect_to),
        )
        return context

    def done(self, form_list: List[Form], **kwargs: Any) -> HttpResponse:
        """
        Log in the user and redirect to the desired page.

        We need to override this function so that we can redirect to
        realm.uri instead of '/'.
        """
        realm_uri = self.get_user().realm.uri
        # This mock.patch business is an unpleasant hack that we'd
        # ideally like to remove by instead patching the upstream
        # module to support better configurability of the
        # LOGIN_REDIRECT_URL setting.  But until then, it works.  We
        # import mock.patch here because mock has an expensive import
        # process involving pbr -> pkgresources (which is really slow).
        from unittest.mock import patch

        with patch.object(settings, "LOGIN_REDIRECT_URL", realm_uri):
            return super().done(form_list, **kwargs)


@has_request_variables
def login_page(
    request: HttpRequest,
    /,
    next: str = REQ(default="/"),
    **kwargs: Any,
) -> HttpResponse:
    if settings.SOCIAL_AUTH_SUBDOMAIN == get_subdomain(request):
        return social_auth_subdomain_login_page(request)

    # To support previewing the Zulip login pages, we have a special option
    # that disables the default behavior of redirecting logged-in users to the
    # logged-in app.
    is_preview = "preview" in request.GET
    if settings.TWO_FACTOR_AUTHENTICATION_ENABLED:
        if request.user.is_authenticated and is_2fa_verified(request.user):
            return HttpResponseRedirect(request.user.realm.uri)
    elif request.user.is_authenticated and not is_preview:
        return HttpResponseRedirect(request.user.realm.uri)
    if is_subdomain_root_or_alias(request) and settings.ROOT_DOMAIN_LANDING_PAGE:
        redirect_url = reverse("realm_redirect")
        if request.GET:
            redirect_url = append_url_query_string(redirect_url, request.GET.urlencode())
        return HttpResponseRedirect(redirect_url)

    realm = get_realm_from_request(request)
    if realm and realm.deactivated:
        return redirect_to_deactivation_notice()

    extra_context = kwargs.pop("extra_context", {})
    extra_context["next"] = next
    if dev_auth_enabled() and kwargs.get("template_name") == "zerver/development/dev_login.html":
        from zerver.views.development.dev_login import add_dev_login_context

        if "new_realm" in request.POST:
            try:
                realm = get_realm(request.POST["new_realm"])
            except Realm.DoesNotExist:
                realm = None

        add_dev_login_context(realm, extra_context)
        if realm and "new_realm" in request.POST:
            # If we're switching realms, redirect to that realm, but
            # only if it actually exists.
            return HttpResponseRedirect(realm.uri)

    if "username" in request.POST:
        extra_context["email"] = request.POST["username"]
    extra_context.update(login_context(request))

    if settings.TWO_FACTOR_AUTHENTICATION_ENABLED:
        return start_two_factor_auth(request, extra_context=extra_context, **kwargs)

    try:
        template_response = DjangoLoginView.as_view(
            authentication_form=OurAuthenticationForm, extra_context=extra_context, **kwargs
        )(request)
    except ZulipLDAPConfigurationError as e:
        assert len(e.args) > 1
        return redirect_to_misconfigured_ldap_notice(request, e.args[1])

    if isinstance(template_response, SimpleTemplateResponse):
        # Only those responses that are rendered using a template have
        # context_data attribute. This attribute doesn't exist otherwise. It is
        # added in SimpleTemplateResponse class, which is a derived class of
        # HttpResponse. See django.template.response.SimpleTemplateResponse,
        # https://github.com/django/django/blob/2.0/django/template/response.py#L19
        assert template_response.context_data is not None
        update_login_page_context(request, template_response.context_data)

    assert isinstance(template_response, HttpResponse)
    return template_response


def social_auth_subdomain_login_page(request: HttpRequest) -> HttpResponse:
    origin_subdomain = request.session.get("subdomain")
    if origin_subdomain is not None:
        try:
            origin_realm = get_realm(origin_subdomain)
            return HttpResponseRedirect(origin_realm.uri)
        except Realm.DoesNotExist:
            pass

    return render(request, "zerver/auth_subdomain.html", status=400)


def start_two_factor_auth(
    request: HttpRequest, extra_context: ExtraContext = None, **kwargs: Any
) -> HttpResponse:
    two_fa_form_field = "two_factor_login_view-current_step"
    if two_fa_form_field not in request.POST:
        # Here we inject the 2FA step in the request context if it's missing to
        # force the user to go to the first step of 2FA authentication process.
        # This seems a bit hackish but simplifies things from testing point of
        # view. I don't think this can result in anything bad because all the
        # authentication logic runs after the auth step.
        #
        # If we don't do this, we will have to modify a lot of auth tests to
        # insert this variable in the request.
        new_query_dict = request.POST.copy()
        new_query_dict[two_fa_form_field] = "auth"
        new_query_dict._mutable = False
        request.POST = cast("_ImmutableQueryDict", new_query_dict)

    """
    This is how Django implements as_view(), so extra_context will be passed
    to the __init__ method of TwoFactorLoginView.

    def as_view(cls, **initkwargs):
        def view(request, *args, **kwargs):
            self = cls(**initkwargs)
            ...

        return view
    """
    two_fa_view = TwoFactorLoginView.as_view(extra_context=extra_context, **kwargs)
    return two_fa_view(request, **kwargs)


@csrf_exempt
@require_post
@has_request_variables
def api_fetch_api_key(
    request: HttpRequest, username: str = REQ(), password: str = REQ()
) -> HttpResponse:
    return_data: Dict[str, bool] = {}

    realm = get_realm_from_request(request)
    if realm is None:
        raise InvalidSubdomainError()

    if not ldap_auth_enabled(realm=realm):
        # In case we don't authenticate against LDAP, check for a valid
        # email. LDAP backend can authenticate against a non-email.
        validate_login_email(username)
    user_profile = authenticate(
        request=request, username=username, password=password, realm=realm, return_data=return_data
    )
    if return_data.get("inactive_user"):
        raise UserDeactivatedError()
    if return_data.get("inactive_realm"):
        raise RealmDeactivatedError()
    if return_data.get("password_auth_disabled"):
        raise PasswordAuthDisabledError()
    if return_data.get("password_reset_needed"):
        raise PasswordResetRequiredError()
    if user_profile is None:
        raise AuthenticationFailedError()

    assert user_profile.is_authenticated

    # Maybe sending 'user_logged_in' signal is the better approach:
    #   user_logged_in.send(sender=type(user_profile), request=request, user=user_profile)
    # Not doing this only because over here we don't add the user information
    # in the session. If the signal receiver assumes that we do then that
    # would cause problems.
    email_on_new_login(sender=type(user_profile), request=request, user=user_profile)

    # Mark this request as having a logged-in user for our server logs.
    assert isinstance(user_profile, UserProfile)
    process_client(request, user_profile)
    RequestNotes.get_notes(request).requestor_for_logs = user_profile.format_requestor_for_logs()

    api_key = get_api_key(user_profile)
    return json_success(request, data={"api_key": api_key, "email": user_profile.delivery_email})


def get_auth_backends_data(request: HttpRequest) -> Dict[str, Any]:
    """Returns which authentication methods are enabled on the server"""
    subdomain = get_subdomain(request)
    try:
        realm = Realm.objects.get(string_id=subdomain)
    except Realm.DoesNotExist:
        # If not the root subdomain, this is an error
        if subdomain != Realm.SUBDOMAIN_FOR_ROOT_DOMAIN:
            raise JsonableError(_("Invalid subdomain"))
        # With the root subdomain, it's an error or not depending
        # whether ROOT_DOMAIN_LANDING_PAGE (which indicates whether
        # there are some realms without subdomains on this server)
        # is set.
        if settings.ROOT_DOMAIN_LANDING_PAGE:
            raise JsonableError(_("Subdomain required"))
        else:
            realm = None
    result = {
        "password": password_auth_enabled(realm),
    }
    for auth_backend_name in AUTH_BACKEND_NAME_MAP:
        key = auth_backend_name.lower()
        result[key] = auth_enabled_helper([auth_backend_name], realm)
    return result


def check_server_incompatibility(request: HttpRequest) -> bool:
    user_agent = parse_user_agent(request.headers.get("User-Agent", "Missing User-Agent"))
    return user_agent["name"] == "ZulipInvalid"


@require_safe
@csrf_exempt
def api_get_server_settings(request: HttpRequest) -> HttpResponse:
    # Log which client is making this request.
    process_client(request)
    result = dict(
        authentication_methods=get_auth_backends_data(request),
        zulip_version=ZULIP_VERSION,
        zulip_merge_base=ZULIP_MERGE_BASE,
        zulip_feature_level=API_FEATURE_LEVEL,
        push_notifications_enabled=push_notifications_enabled(),
        is_incompatible=check_server_incompatibility(request),
    )
    context = zulip_default_context(request)
    context.update(login_context(request))
    # IMPORTANT NOTE:
    # realm_name, realm_icon, etc. are not guaranteed to appear in the response.
    # * If they do, that means the server URL has only one realm on it
    # * If they don't, the server has multiple realms, and it's not clear which is
    #   the requested realm, so we can't send back these data.
    for settings_item in [
        "email_auth_enabled",
        "require_email_format_usernames",
        "realm_uri",
        "realm_name",
        "realm_icon",
        "realm_description",
        "realm_web_public_access_enabled",
        "external_authentication_methods",
    ]:
        if context[settings_item] is not None:
            result[settings_item] = context[settings_item]
    return json_success(request, data=result)


@has_request_variables
def json_fetch_api_key(
    request: HttpRequest, user_profile: UserProfile, password: str = REQ(default="")
) -> HttpResponse:
    realm = get_realm_from_request(request)
    if realm is None:
        raise JsonableError(_("Invalid subdomain"))
    if password_auth_enabled(user_profile.realm):
        if not authenticate(
            request=request, username=user_profile.delivery_email, password=password, realm=realm
        ):
            raise JsonableError(_("Password is incorrect."))

    api_key = get_api_key(user_profile)
    return json_success(request, data={"api_key": api_key, "email": user_profile.delivery_email})


logout_then_login = require_post(django_logout_then_login)


def password_reset(request: HttpRequest) -> HttpResponse:
    if is_subdomain_root_or_alias(request) and settings.ROOT_DOMAIN_LANDING_PAGE:
        redirect_url = append_url_query_string(
            reverse("realm_redirect"), urlencode({"next": reverse("password_reset")})
        )
        return HttpResponseRedirect(redirect_url)

    try:
        response = DjangoPasswordResetView.as_view(
            template_name="zerver/reset.html",
            form_class=ZulipPasswordResetForm,
            success_url="/accounts/password/reset/done/",
        )(request)
    except RateLimitedError as e:
        assert e.secs_to_freedom is not None
        return render(
            request,
            "zerver/rate_limit_exceeded.html",
            context={"retry_after": int(e.secs_to_freedom)},
            status=429,
        )
    assert isinstance(response, HttpResponse)
    return response


@csrf_exempt
def saml_sp_metadata(request: HttpRequest) -> HttpResponse:  # nocoverage
    """
    This is the view function for generating our SP metadata
    for SAML authentication. It's meant for helping check the correctness
    of the configuration when setting up SAML, or for obtaining the XML metadata
    if the IdP requires it.
    Taken from https://python-social-auth.readthedocs.io/en/latest/backends/saml.html
    """
    if not saml_auth_enabled():
        return config_error(request, "saml")

    complete_url = reverse("social:complete", args=("saml",))
    saml_backend = load_backend(load_strategy(request), "saml", complete_url)
    metadata, errors = saml_backend.generate_metadata_xml()
    if not errors:
        return HttpResponse(content=metadata, content_type="text/xml")

    return HttpResponseServerError(content=", ".join(errors))


def config_error(request: HttpRequest, error_category_name: str) -> HttpResponse:
    contexts: Dict[str, Dict[str, object]] = {
        "apple": {"social_backend_name": "apple", "has_markdown_file": True},
        "google": {"social_backend_name": "google", "has_markdown_file": True},
        "github": {"social_backend_name": "github", "has_markdown_file": True},
        "gitlab": {"social_backend_name": "gitlab", "has_markdown_file": True},
        "ldap": {"error_name": "ldap_error_realm_is_none"},
        "dev": {"error_name": "dev_not_supported_error"},
        "saml": {"social_backend_name": "saml"},
        "smtp": {"error_name": "smtp_error"},
        "remote_user_backend_disabled": {"error_name": "remoteuser_error_backend_disabled"},
        "remote_user_header_missing": {"error_name": "remoteuser_error_remote_user_header_missing"},
        # TODO: Improve the config error page for OIDC.
        "oidc": {"error_name": "oidc_error"},
    }

    return render(request, "zerver/config_error.html", contexts[error_category_name])
